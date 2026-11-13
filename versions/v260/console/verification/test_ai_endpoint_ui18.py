"""Provider endpointing stays automatic; local diagnostics never submit input."""
from pathlib import Path
import sys
import threading
import unittest

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from ai_doubao import DoubaoNative
from ai_runtime import AIHub
from telemetry import Store
from verification.test_ai_hat import Hub


class AutomaticEndpointTests(unittest.TestCase):
    def setUp(self):
        self.hub=Hub();self.hub.gate.speaking_enabled=True
        self.p=DoubaoNative(self.hub,'fixture','fixture',None,None,threading.Event())
        self.now=[0.0];self.p.clock=lambda:self.now[0]
        self.sent=[];self.p._send=self.sent.append

    def delta(self,text='请拍照'):
        self.p._handle({'type':'conversation.item.input_audio_transcription.delta','item_id':'u1','delta':text})

    def test_stalled_partial_only_warns_once_and_never_becomes_a_local_final(self):
        self.delta()
        for elapsed in (1.5,6,10,35,60,300):
            self.now[0]=elapsed;self.p._poll_input()
        self.assertFalse(self.sent)
        self.assertFalse(self.p.asr_pending['committed'])
        self.assertFalse(any(e['kind']=='transcript' and e['final'] for e in self.hub.events))
        warnings=[e for e in self.hub.events if e['kind']=='input_turn_wait']
        self.assertEqual(len(warnings),1)
        self.assertEqual(warnings[0]['stage'],'endpoint')
        self.assertIn('自动断句',warnings[0]['message'])

    def test_actual_meter_levels_including_silence_do_not_trigger_commit(self):
        self.delta()
        for dbfs in (-96,-60,-50,-20):
            for i in range(100):
                self.now[0]+=.1
                self.hub.log('mic_level',dbfs=dbfs,peak=0 if dbfs==-96 else .01,uploaded_seconds=self.now[0])
                self.p._poll_input()
        self.assertFalse(self.sent)

    def test_server_final_remains_authoritative_and_reply_timeout_is_diagnostic_only(self):
        self.delta();self.now[0]=7;self.p._poll_input()
        self.p._handle({'type':'conversation.item.input_audio_transcription.completed','item_id':'u1','transcript':'请拍照。'})
        final=self.hub.events[-1]
        self.assertTrue(final['final']);self.assertEqual(final['text'],'请拍照。')
        self.now[0]=30;self.p._poll_input()
        self.assertFalse(self.sent)
        self.assertEqual(self.hub.events[-1]['stage'],'reply')

    def test_model_output_before_final_suppresses_stalled_input_warning(self):
        self.delta()
        self.p._handle({'type':'response.output_text.delta','item_id':'a1','delta':'好的'})
        self.now[0]=30;self.p._poll_input()
        self.assertFalse(self.sent)
        self.assertFalse(any(e['kind']=='input_turn_wait' for e in self.hub.events))

    def test_waiting_note_preserves_partial_text_and_does_not_claim_a_reply_is_pending(self):
        hub=AIHub(Store('service'))
        try:
            hub.log('provider_session',event='session.created')
            hub.log('transcript',text='请拍照',item_id='u1',final=False)
            hub.log('input_turn_wait',stage='endpoint',message='正在等待豆包自动断句')
            state=hub.conversation.snapshot()
            self.assertEqual(state['phase'],'transcribing')
            self.assertEqual(state['messages'][-1]['text'],'请拍照')
            self.assertFalse(state['messages'][-1]['final'])
        finally:hub.close()


if __name__=='__main__':unittest.main()

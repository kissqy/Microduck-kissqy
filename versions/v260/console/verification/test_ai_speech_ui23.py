"""Manual speech permission blocks provider PCM while official WAV remains audible."""
import base64
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from ai_action_gate import ActionDenied
from ai_doubao import DoubaoNative
from ai_remote import RemoteAI
from ai_runtime import AIHub
from ai_zero import ZeroHub
from telemetry import Store
from verification import test_ai_ui22 as ui22
import service_rpc


class SpeechPermissionTests(unittest.TestCase):
    def setUp(self):
        self.stop=threading.Event()
        self.hub=ZeroHub({'api_key':'fixture','tools':[
            {'name':'stay_silent','description':'normal conversation'}],'voice_enabled':True},self.stop)
        self.events=[];self.sent=[]
        self.hub.log=lambda kind,**fields:self.events.append({'kind':kind,**fields})
        self.p=DoubaoNative(self.hub,'fixture','voice',None,None,self.stop)
        self.hub.provider=self.p;self.p._send=self.sent.append
        self.addCleanup(self.hub.vision.close)

    def disable_speech(self):self.p.set_speech(False,'a'*32)

    def voice(self,text,item='real-mic-1',final=True):
        self.p._handle({'type':'conversation.item.input_audio_transcription.'+('completed' if final else 'delta'),
                        'item_id':item,'transcript':text} if final else
                       {'type':'conversation.item.input_audio_transcription.delta','item_id':item,'delta':text})

    def audio(self,response='r1'):
        self.p._handle({'type':'response.output_audio.delta','response_id':response,
                        'delta':base64.b64encode(b'\x01\x02'*320).decode()})


    def test_asr_and_model_text_cannot_open_hat_by_themselves(self):
        self.disable_speech()
        self.voice('你不解释解释吗？',final=False)
        self.assertFalse(self.hub.gate.speaking_enabled)
        self.p._handle({'type':'response.output_text.done','text':'你不解释解释吗？'})
        self.voice('不要说你不解释解释吗','other-voice')
        self.assertFalse(self.hub.gate.speaking_enabled)
        original_session=self.p._session()
        sent_before_unlock=len(self.sent)
        self.voice('你不解释解释吗？')
        self.assertFalse(self.hub.gate.speaking_enabled)
        self.p.set_speech(True,'d'*32)
        self.assertTrue(self.hub.gate.speaking_enabled)
        self.assertFalse(self.p.playback_cancel.is_set())
        self.assertEqual(self.p._session(),original_session,'unlock affects HAT playback, not model context')
        self.assertEqual(len(self.sent),sent_before_unlock,'unlock must not send a session update')
        sent_count=len(self.sent);self.voice('你不解释解释吗？')
        self.assertEqual(len(self.sent),sent_count,'duplicate final ASR does not send another update')
        self.assertFalse(any(e['kind']=='action_request' for e in self.events),'the command never scripts motion')

    def test_no_spoken_wording_is_a_local_unlock_command(self):
        self.disable_speech()
        for index,text in enumerate(('你不解释解释吗？','你不自己解释一下吗？','那你解释一下',
                                     '如果我说你不解释解释吗','解除声音限制')):
            self.voice(text,'input-'+str(index))
            self.assertFalse(self.hub.gate.speaking_enabled,text)
        self.assertFalse(any(e['kind']=='action_request' for e in self.events))

    def test_unlock_discards_old_pcm_and_late_frames_but_allows_a_new_reply(self):
        self.p.audio_queue.put(b'old queued voice');self.disable_speech()
        self.assertTrue(self.p.audio_queue.empty())
        self.audio('blocked-old');self.assertTrue(self.p.audio_queue.empty())
        self.p.set_speech(True,'d'*32)
        self.audio('blocked-old');self.assertTrue(self.p.audio_queue.empty(),'do not release the tail of an earlier blocked response')
        self.audio('new-reply');self.assertEqual(self.p.audio_queue.get_nowait(),b'\x01\x02'*320)

    def test_global_mute_and_expression_end_cannot_enable_speech(self):
        self.disable_speech();self.p.set_muted(True);self.p.set_muted(False)
        self.assertTrue(self.p.playback_cancel.is_set());self.assertFalse(self.hub.muted)
        self.p.end_expression_audio();self.assertTrue(self.p.playback_cancel.is_set())
        self.p.set_muted(True);self.p.set_speech(True,'d'*32)
        self.assertTrue(self.hub.gate.speaking_enabled);self.assertTrue(self.hub.muted)
        self.audio('new-reply');self.assertTrue(self.p.audio_queue.empty())
        self.p.set_muted(False);self.assertFalse(self.p.playback_cancel.is_set())



    def test_lock_stops_current_native_pcm_and_official_expression_still_yields_the_device(self):
        opened=threading.Event();played=threading.Event();closed=threading.Event();writes=[]
        class Speaker:
            def __init__(self,*_):pass
            def __enter__(self):return self
            def __exit__(self,*_):self.close()
            def close(self):opened.clear();closed.set()
            def finish(self):self.close();return True
            def write(self,pcm):writes.append(pcm);opened.set();played.set();return True
        def log(kind,**fields):
            self.events.append({'kind':kind,**fields})
            if kind=='action_request':
                self.assertFalse(opened.is_set())
                self.assertTrue(self.p._input_state()[1],'duck WAV still blocks speaker echo')
                self.hub.gate.feedback(fields['request_id'],{'accepted':True,'status':'completed'})
        self.hub.log=log
        worker=threading.Thread(target=self.p._speaker,daemon=True)
        with patch('ai_doubao.NativeSpeaker',Speaker):
            worker.start()
            try:
                self.p.audio_queue.put(b'playing');self.assertTrue(played.wait(1));closed.clear()
                self.disable_speech();self.assertTrue(closed.wait(1),'manual permission closes ongoing native provider playback')
                self.assertFalse(self.hub.muted)
                result=self.hub.gate.execute('express_emotion',{'emotion':'excited'})
                self.assertEqual(result['status'],'completed')
                self.assertTrue(self.p.playback_cancel.is_set(),'duck WAV must not clear the language restriction')
                self.audio('blocked');self.assertTrue(self.p.audio_queue.empty())
                self.assertEqual(writes,[b'playing'])
            finally:self.stop.set();worker.join(1)
        self.assertFalse(worker.is_alive())


class SpeechControlPathTests(unittest.TestCase):
    def test_language_lock_preserves_native_official_sound_selection(self):
        f=ui22.OfficialSoundGateTests().fixture();f.gate.speaking_enabled=False
        result=f.gate.execute('express_emotion',{'emotion':'excited'})
        self.assertFalse(result['silent']);self.assertEqual(f.robot.calls[0],('robot.do',{'skill':'emotion_excited'}))
        f.gate.transcript('解除声音限制',final=True)
        with self.assertRaises(ActionDenied):f.gate.execute('unlock_speech',{})





if __name__=='__main__':unittest.main()

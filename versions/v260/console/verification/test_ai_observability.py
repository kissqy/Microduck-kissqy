"""PCM metering and official Seeduplex event shapes, without cloud or devices."""
import math
import base64
from pathlib import Path
import struct
import sys
import threading
import unittest

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from ai_audio_meter import AudioMeter
from ai_doubao import DoubaoNative
from verification.test_ai_hat import Hub


class MeterTests(unittest.TestCase):
    def test_silence_dc_peak_and_update_rate(self):
        now=[0.0];meter=AudioMeter(lambda:now[0])
        silent=meter.update(b'\0'*640)
        self.assertEqual((silent['rms'],silent['peak'],silent['dbfs']),(0,0,-96))
        self.assertIsNone(meter.update(struct.pack('<h',16384)*320))
        now[0]=.11
        half=meter.update(struct.pack('<h',16384)*320)
        self.assertEqual(half['rms'],.5);self.assertEqual(half['peak'],.5)
        self.assertAlmostEqual(half['dbfs'],-6,delta=.1)
        self.assertEqual(half['packets'],3);self.assertEqual(half['uploaded_seconds'],.06)
        self.assertNotIn('audio',half)

    def test_waveform_bounds_come_from_actual_samples(self):
        meter=AudioMeter()
        values=[-32768,0,32767,0]*80
        result=meter.update(struct.pack('<320h',*values))
        self.assertEqual(result['minimum'],-1)
        self.assertAlmostEqual(result['maximum'],32767/32768,places=5)
        self.assertAlmostEqual(result['rms'],math.sqrt(sum(x*x for x in values)/320)/32768,places=5)
        for bad in (b'',b'odd'):
            with self.assertRaises(ValueError):meter.update(bad)


class EventTests(unittest.TestCase):
    def setUp(self):
        self.hub=Hub()
        self.p=DoubaoNative(self.hub,'fixture-key','fixture',None,None,threading.Event())

    def test_official_asr_delta_field_and_final_transcript(self):
        self.p._handle({'type':'conversation.item.input_audio_transcription.delta','item_id':'item_1','content_index':0,'delta':'Hey'})
        self.p._handle({'type':'conversation.item.input_audio_transcription.delta','item_id':'item_1','content_index':0,'delta':'Hey, can you hear me?'})
        self.assertEqual(self.hub.events[-1]['text'],'Hey, can you hear me?')
        self.p._handle({'type':'conversation.item.input_audio_transcription.completed','item_id':'item_1','content_index':0,'transcript':'Hey, can you hear me?'})
        self.assertTrue(self.hub.events[-1]['final'])
        self.assertEqual(self.hub.events[-1]['text'],'Hey, can you hear me?')

    def test_model_reply_deltas_are_shown_in_order(self):
        self.hub.gate.speaking_enabled=True
        for word in ['我','在这里。']:
            self.p._handle({'type':'response.output_text.delta','item_id':'a1','delta':word})
        self.p._handle({'type':'response.output_text.done','item_id':'a1','text':'我在这里。'})
        replies=[e for e in self.hub.events if e['kind']=='assistant_text']
        self.assertEqual([e['text'] for e in replies],['我','我在这里。','我在这里。'])
        self.assertTrue(replies[-1]['final'])

    def test_reply_is_logged_even_when_speech_lock_blocks_it(self):
        self.p._handle({'type':'response.output_text.delta','delta':'你好'})
        self.assertFalse(self.p.stop_event.is_set())
        reply=next(e for e in self.hub.events if e['kind']=='assistant_text')
        self.assertTrue(reply['blocked']);self.assertEqual(reply['text'],'你好')

    def test_official_audio_delta_reaches_playback_queue(self):
        self.hub.gate.speaking_enabled=True
        pcm=struct.pack('<h',123)*480
        self.p._handle({'type':'response.output_audio.delta','response_id':'resp_001',
                        'delta':base64.b64encode(pcm).decode()})
        self.assertEqual(self.p.audio_queue.get_nowait(),pcm)
        self.p._handle({'type':'response.output_audio.done'})
        self.assertIsNone(self.p.audio_queue.get_nowait())

    def test_function_name_args_result_and_call_id_are_preserved(self):
        sent=[];self.p._send=sent.append
        self.p._tool_calls({'type':'response.function_call_arguments.done','items':[
            {'name':'perform_skill','arguments':'{"skill":"flamingo"}','call_id':'call_fixture'}]})
        events=self.hub.events
        call=next(e for e in events if e['kind']=='tool_call')
        self.assertEqual(call['arguments'],{'skill':'flamingo'})
        self.assertTrue(any(e['kind']=='ipc_accepted' for e in events))
        feedback=next(e for e in events if e['kind']=='tool_feedback')
        self.assertEqual(feedback['call_id'],'call_fixture')
        self.assertTrue(feedback['result']['accepted'])
        self.assertEqual(sent[-1]['items'][0]['call_id'],'call_fixture')


if __name__=='__main__':unittest.main()

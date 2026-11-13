"""Generic velocity limits and actual-PCM mouth scheduling."""
import threading
import time
import unittest

from ai_remote import SpeechMouth
from verification.test_ai_hat import Hub


class SpeechMotionTests(unittest.TestCase):
    def test_requested_point_three_speed_reaches_existing_walk_for_three_seconds_without_scaling(self):
        hub=Hub();gate=hub.gate
        schema=next(t for t in gate.tool_definitions() if t['name']=='walk_short')['parameters']['properties']
        self.assertEqual(schema['vx']['maximum'],.3)
        start=hub.robot.clock()
        result=gate.execute('walk_short',{'vx':.3,'vy':0,'vyaw':0,'seconds':3})
        self.assertEqual(result['status'],'stop_intent_sent');self.assertAlmostEqual(hub.robot.clock()-start,3.)
        self.assertGreater(len(hub.robot.calls),1)
        self.assertTrue(all(row==('robot.move',{'vx':.3,'vy':0.,'vyaw':0.}) for row in hub.robot.calls[:-1]))
        self.assertEqual(hub.robot.calls[-1],('robot.move',{'vx':0,'vy':0,'vyaw':0}))
        with self.assertRaises(ValueError):gate.execute('walk_short',{'vx':.3001,'vy':0,'vyaw':0,'seconds':3})

    def test_actual_pcm_frames_drive_mouth_on_audio_clock_without_text_timer(self):
        calls=[]
        class Gate:
            def follow_speech_mouth(self,opening):calls.append((time.monotonic(),opening));return True
        mouth=SpeechMouth(Gate());self.addCleanup(mouth.close)
        mouth.set_active(True,'actual-pcm')
        begin=time.monotonic()
        mouth.feed('actual-pcm',1.,.05,.1)
        mouth.feed('actual-pcm',.2,.15,.1)
        mouth.feed('actual-pcm',.9,.25,.1)
        self.assertFalse(calls,'wait for the scheduled sound, not text receipt')
        end=begin+1
        while len(calls)<3 and time.monotonic()<end:threading.Event().wait(.005)
        self.assertEqual([v for _,v in calls],[1.,.2,.9])
        self.assertGreaterEqual(calls[0][0]-begin,.045)
        self.assertGreaterEqual(calls[2][0]-begin,.245)
        mouth.set_active(False)
        end=time.monotonic()+1
        while calls[-1][1]!=0 and time.monotonic()<end:threading.Event().wait(.005)
        self.assertEqual(calls[-1][1],0.)

    def test_speech_mouth_uses_native_expression_range_without_second_pad_scaling(self):
        hub=Hub();gate=hub.gate;state=gate.monitor
        gate.monitor=lambda:{**state(),'mouth_percent':60}
        for opening in (1.,.2,0.):self.assertTrue(gate.follow_speech_mouth(opening))
        self.assertEqual(hub.robot.calls,[('robot.mouth',{'open':1.}),
                                         ('robot.mouth',{'open':.2}),('robot.mouth',{'open':0.})])


if __name__=='__main__':unittest.main()

"""Local playback-to-mouth ordering with fake HAT and robot IPC; no hardware."""
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ai_action_gate import ActionDenied
from ai_doubao import DoubaoNative,PlaybackPCM
from ai_remote import RemoteAI,SpeechMouth
from verification.test_ai_hat import Hub


class SpeechMouthTests(unittest.TestCase):
    def until(self,predicate):
        end=time.monotonic()+1
        while not predicate() and time.monotonic()<end:threading.Event().wait(.005)
        self.assertTrue(predicate())

    def fixture(self):
        hub=Hub();hub.gate.speaking_enabled=True;hub.muted=False
        stop=threading.Event();remote=RemoteAI(hub,None,stop)
        self.addCleanup(remote.close_mouth)
        return hub,stop,remote

    def plan(self,remote):
        remote._event({'kind':'assistant_text','audio_id':'fixture-reply','text':'鸭鸭'})
        remote._event({'kind':'speaker_audio_duration','audio_id':'fixture-reply','seconds':.5})

    def test_only_real_hat_playback_opens_and_drain_completion_closes_mouth(self):
        hub,stop,remote=self.fixture();played=threading.Event();draining=threading.Event();release=threading.Event()
        original=hub.log
        def log(kind,**fields):
            if kind in ('speaker_playback_started','speaker_playback_finished','speaker_mouth'):remote._event({'kind':kind,**fields})
            else:original(kind,**fields)
        provider=DoubaoNative(SimpleNamespace(gate=hub.gate,muted=False,error='',log=log),
                              'fixture','voice',None,None,stop)
        class Speaker:
            def __init__(self,*_):pass
            def __enter__(self):return self
            def __exit__(self,*_):pass
            def write(self,pcm):
                self.pcm_observer(pcm,time.monotonic(),.02);played.set();return True
            def finish(self):draining.set();release.wait(1);return True
            def close(self):pass
        self.plan(remote)
        remote._event({'kind':'assistant_audio_end'})
        self.assertIsNone(remote.mouth);self.assertFalse(hub.robot.calls)
        worker=threading.Thread(target=provider._speaker)
        with patch('ai_doubao.NativeSpeaker',Speaker):
            worker.start()
            try:
                provider.audio_queue.put(PlaybackPCM(b'\x10\x02'*480,'fixture-reply'));self.assertTrue(played.wait(1))
                self.until(lambda:len(hub.robot.calls)>=2)
                provider.audio_queue.put(None);self.assertTrue(draining.wait(1))
                self.assertTrue(remote.mouth.active,'cloud audio.done does not close before physical drain')
                release.set();self.until(lambda:hub.robot.calls[-1]==('robot.mouth',{'open':0.}))
            finally:release.set();stop.set();worker.join(1);remote.close_mouth()
        openings=[args['open'] for name,args in hub.robot.calls if name=='robot.mouth']
        self.assertGreater(len(set(openings[:-1])),1,'cycle the duck mouth while speech actually plays')
        self.assertEqual(openings[-1],0.)
        self.assertTrue(all(name=='robot.mouth' for name,_ in hub.robot.calls))
        self.assertFalse(worker.is_alive())

    def test_no_hat_permission_or_failed_write_never_starts_mouth(self):
        for enabled in (False,True):
            with self.subTest(enabled=enabled):
                hub,stop,remote=self.fixture();hub.gate.speaking_enabled=enabled
                finished=threading.Event();original=hub.log
                def log(kind,**fields):
                    remote._event({'kind':kind,**fields})
                    if kind=='speaker_ready':finished.set()
                hub.log=log
                class Speaker:
                    def __init__(self,*_):pass
                    def __enter__(self):return self
                    def __exit__(self,*_):pass
                    def write(self,pcm):finished.set();stop.set();return False
                    def close(self):pass
                provider=DoubaoNative(hub,'fixture','voice',None,None,stop)
                worker=threading.Thread(target=provider._speaker)
                # RemoteAI logs through Hub, not the forwarding Zero log.
                hub.log=original
                provider.hub=SimpleNamespace(gate=hub.gate,muted=False,error='',
                    log=log)
                with patch('ai_doubao.NativeSpeaker',Speaker):
                    worker.start()
                    try:
                        provider.audio_queue.put(b'pcm');self.assertTrue(finished.wait(1))
                    finally:stop.set();worker.join(1)
                self.assertIsNone(remote.mouth);self.assertFalse(hub.robot.calls)

    def test_expression_handoff_and_speaker_failure_both_close_active_mouth(self):
        for mode in ('expression','failure'):
            with self.subTest(mode=mode):
                hub,stop,remote=self.fixture();played=threading.Event();failed=threading.Event()
                self.plan(remote)
                original=hub.log
                def log(kind,**fields):
                    remote._event({'kind':kind,**fields})
                    if kind=='speaker_error':failed.set()
                provider=DoubaoNative(SimpleNamespace(gate=hub.gate,muted=False,error='',log=log),
                                      'fixture','voice',None,None,stop)
                class Speaker:
                    def __init__(self,*_):self.writes=0
                    def __enter__(self):return self
                    def __exit__(self,*_):pass
                    def write(self,pcm):
                        self.writes+=1
                        if self.writes>1:raise OSError('fixture speaker failed')
                        self.pcm_observer(pcm,time.monotonic(),.02);played.set();return True
                    def close(self):pass
                worker=threading.Thread(target=provider._speaker)
                with patch('ai_doubao.NativeSpeaker',Speaker):
                    worker.start()
                    try:
                        provider.audio_queue.put(PlaybackPCM(b'\x10\x02'*480,'fixture-reply'));self.assertTrue(played.wait(1))
                        self.until(lambda:bool(hub.robot.calls))
                        if mode=='expression':
                            provider.expression_audio.set();self.assertTrue(provider.expression_audio_ready.wait(1))
                        else:
                            provider.audio_queue.put(b'failure');self.assertTrue(failed.wait(1))
                        self.until(lambda:hub.robot.calls[-1]==('robot.mouth',{'open':0.}))
                        self.assertFalse(remote.mouth.active)
                    finally:stop.set();worker.join(1);remote.close_mouth()
                self.assertFalse(worker.is_alive())

    def test_slow_or_failed_mouth_ipc_does_not_block_audio_events_or_replay_old_open(self):
        begun=threading.Event();release=threading.Event();calls=[]
        class Gate:
            def follow_speech_mouth(self,opening):
                calls.append(opening)
                if len(calls)==1:begun.set();release.wait(1)
                if opening:raise OSError('fixture mouth IPC unavailable')
                return True
        mouth=SpeechMouth(Gate());self.addCleanup(mouth.close)
        try:
            mouth.set_active(True,'fixture-reply');mouth.feed('fixture-reply',1.,0.,.2);self.assertTrue(begun.wait(1))
            begin=time.monotonic();mouth.set_active(False)
            self.assertLess(time.monotonic()-begin,.05,'event delivery must not await mouth RPC')
            release.set();self.until(lambda:len(calls)>=2)
            self.assertEqual(calls[1:], [0.])
        finally:release.set();mouth.close()
        self.assertFalse(mouth.worker.is_alive());self.assertEqual(calls[-1],0.)

    def test_mouth_can_follow_speech_during_walk_but_yields_to_official_expression(self):
        hub,_,_=self.fixture();gate=hub.gate
        ready=threading.Event();release=threading.Event()
        def hold():
            with gate._exclusive('walk_short'):ready.set();release.wait(1)
        worker=threading.Thread(target=hold);worker.start()
        try:
            self.assertTrue(ready.wait(1));self.assertTrue(gate.follow_speech_mouth(.5))
        finally:release.set();worker.join(1)
        self.assertEqual(hub.robot.calls,[('robot.mouth',{'open':.5})])
        with gate._exclusive('express_emotion'):self.assertFalse(gate.follow_speech_mouth(.5))
        hub.robot.ready=False
        with self.assertRaises(ActionDenied):gate.follow_speech_mouth(.5)
        self.assertEqual(len(hub.robot.calls),1)

    def test_close_stops_the_loop_and_sends_only_mouth_zero(self):
        hub,_,remote=self.fixture()
        self.plan(remote)
        remote._event({'kind':'speaker_playback_started','audio_id':'fixture-reply'})
        remote._event({'kind':'speaker_mouth','audio_id':'fixture-reply','open':1.,'delay_seconds':0.,'seconds':.2})
        self.until(lambda:bool(hub.robot.calls))
        remote.close_mouth()
        self.assertFalse(remote.mouth.worker.is_alive())
        self.assertEqual(hub.robot.calls[-1],('robot.mouth',{'open':0.}))
        self.assertTrue(all(name=='robot.mouth' for name,_ in hub.robot.calls))


if __name__=='__main__':unittest.main()

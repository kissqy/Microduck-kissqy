"""Playback input suppression, capture-buffer cleanup, and personality wiring."""
import base64
import os
from pathlib import Path
import queue
import sys
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from ai_doubao import DoubaoNative
from ai_hat_audio import NativeMicrophone
from ai_persona import TOOL_RULES
from verification.test_ai_hat import Hub


class InputTests(unittest.TestCase):
    def provider(self):
        hub=Hub();hub.gate.speaking_enabled=True;hub.muted=False
        return DoubaoNative(hub,'fixture','voice',None,None,threading.Event())

    def test_real_playback_lifetime_masks_input_through_drain_and_tail_then_resumes(self):
        p=self.provider();now=[0.0];p.clock=lambda:now[0]
        frames=queue.Queue();sent=[];cv=threading.Condition();opened=[];flushed=threading.Event()
        wrote=threading.Event();allow_write=threading.Event();draining=threading.Event();allow_drain=threading.Event()
        def send(event):
            if event['type']=='input_audio_buffer.append':
                with cv:sent.append(base64.b64decode(event['audio']));cv.notify_all()
            return True
        p._send=send
        class Mic:
            def __init__(self,*_):pass
            def __enter__(self):opened.append(True);return self
            def __exit__(self,*_):pass
            def read(self):
                while not p.stop_event.is_set():
                    try:return frames.get(timeout=.05) or b''
                    except queue.Empty:pass
                return b''
            def discard_pending(self):
                flushed.set()
                while True:
                    try:frames.get_nowait()
                    except queue.Empty:return
        class Speaker:
            def __init__(self,*_):pass
            def __enter__(self):return self
            def __exit__(self,*_):pass
            def write(self,pcm):wrote.set();allow_write.wait(1);return True
            def finish(self):draining.set();allow_drain.wait(1);return True
            def close(self):pass
        def pump(pcm):
            with cv:
                count=len(sent);frames.put(pcm)
                self.assertTrue(cv.wait_for(lambda:len(sent)>count,timeout=1),'mic stream stalled')
                return sent[-1]
        human=b'\x23\x01'*320;echo=b'\x45\x06'*320
        mic=threading.Thread(target=p._microphone);speaker=threading.Thread(target=p._speaker)
        with patch('ai_doubao.NativeMicrophone',Mic),patch('ai_doubao.NativeSpeaker',Speaker):
            mic.start();speaker.start()
            try:
                self.assertEqual(pump(human),human)
                p.audio_queue.put(b'\x01\x02'*480)
                self.assertTrue(wrote.wait(1))
                self.assertEqual(pump(echo),b'\0'*640,'block before the first speaker write completes')
                allow_write.set()
                self.assertEqual(pump(echo),b'\0'*640,'temporary absence of new cloud audio must not reopen input')
                p.audio_queue.put(None)
                self.assertTrue(draining.wait(1))
                self.assertEqual(pump(echo),b'\0'*640,'cloud audio.done is earlier than actual speaker completion')
                allow_drain.set()
                deadline=time.monotonic()+1
                while p._input_state()[2]!='tail' and time.monotonic()<deadline:threading.Event().wait(.005)
                self.assertEqual(p._input_state()[2],'tail')
                now[0]=.1;self.assertEqual(pump(echo),b'\0'*640)
                now[0]=1.0;self.assertEqual(pump(echo),b'\0'*640,'discard the frame that straddles reopening')
                self.assertTrue(flushed.wait(1))
                self.assertEqual(pump(human),human)
                p.set_muted(True)
                self.assertEqual(pump(human),human,'speaker mute must leave human input available')
            finally:
                allow_write.set();allow_drain.set();p.stop_event.set();frames.put(None)
                mic.join(1);speaker.join(1)
        self.assertFalse(mic.is_alive());self.assertFalse(speaker.is_alive())
        self.assertEqual(opened,[True],'keep capture open instead of repeatedly reopening ALSA')
        self.assertFalse(p.input_playing)
        self.assertFalse(any(e['kind'] in ('mic_error','speaker_error') for e in p.hub.events))
        self.assertEqual([e['blocked'] for e in p.hub.events if e['kind']=='input_gate'],[True,False])

    def test_playback_begin_and_end_inside_one_capture_frame_cannot_leak_echo(self):
        p=self.provider();now=[0.0];p.clock=lambda:now[0];sent=[]
        p._send=lambda event:sent.append(base64.b64decode(event['audio']))
        class Mic:
            def __init__(self,*_):self.count=0
            def __enter__(self):return self
            def __exit__(self,*_):pass
            def read(self):
                self.count+=1
                if self.count>1:p.stop_event.set();return b''
                p._playback_input(True);p._playback_input(False);now[0]=1.0
                return b'\x56\x12'*320
        with patch('ai_doubao.NativeMicrophone',Mic):p._microphone()
        self.assertEqual(sent,[b'\0'*640],'check playback transitions across the entire capture read')

    def test_resume_discards_old_capture_pipe_bytes_before_reading_new_input(self):
        read_fd,write_fd=os.pipe();reader=os.fdopen(read_fd,'rb',buffering=0)
        try:
            os.set_blocking(read_fd,False)
            mic=NativeMicrophone('plughw:aic3104');mic.proc=SimpleNamespace(stdout=reader)
            echo=b'\x45\x06'*1280;human=b'\x23\x01'*320
            os.write(write_fd,echo)
            self.assertEqual(mic.discard_pending(),len(echo))
            os.write(write_fd,human)
            self.assertEqual(mic.read(),human)
            mic.proc=None
        finally:reader.close();os.close(write_fd)

    def test_custom_personality_is_in_create_and_update_with_tool_result_rules(self):
        p=self.provider();p.hub.persona='你是一只一本正经讲冷笑话的小鸭。'
        for mode in ('create','update'):
            prompt=p._session(mode)['session']['instructions']
            self.assertTrue(prompt.startswith(p.hub.persona))
            self.assertIn(TOOL_RULES,prompt)
            self.assertNotIn('严禁',prompt)


if __name__=='__main__':unittest.main()

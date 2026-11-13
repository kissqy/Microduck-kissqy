"""Real owned subprocesses reproduce tail playback and deliberate cancellation."""
from pathlib import Path
import queue
import struct
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from ai_hat_audio import NativeSpeaker,AudioError
from ai_doubao import DoubaoNative
from verification.test_ai_hat import Hub


class PlaybackTests(unittest.TestCase):
    def executable(self,directory,body):
        p=Path(directory)/'aplay'
        p.write_text('#!'+sys.executable+'\n'+body)
        p.chmod(0o700)
        return str(p)

    def test_tail_longer_than_one_second_finishes_without_terminating_player(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'played.pcm'
            exe=self.executable(directory,
                'import signal,sys,time\nfrom pathlib import Path\n'
                'def interrupted(*_):\n sys.stderr.write("aplay: pcm_write:2178: write error: Interrupted system call\\n");sys.stderr.flush();sys.exit(1)\n'
                'signal.signal(signal.SIGTERM,interrupted)\n'
                'data=sys.stdin.buffer.read()\ntime.sleep(1.3)\n'
                'Path('+repr(str(output))+').write_bytes(data)\n')
            pcm=struct.pack('<h',321)*48000
            with patch('ai_hat_audio.shutil.which',return_value=exe):
                with NativeSpeaker('plughw:aic3104') as speaker:
                    speaker.write(pcm);proc=speaker.proc
                    started=time.monotonic()
                    self.assertTrue(speaker.finish())
                    self.assertGreater(time.monotonic()-started,1.2)
                    self.assertEqual(proc.returncode,0)
                    self.assertIsNone(speaker.proc)
            self.assertEqual(output.read_bytes(),pcm)

    def test_network_pause_does_not_finish_or_restart_the_same_audio_reply(self):
        hub=Hub();hub.gate.speaking_enabled=True;hub.muted=False
        stop=threading.Event();provider=DoubaoNative(hub,'fixture','voice',None,None,stop)
        played=[];finishes=[];first=threading.Event();finished=threading.Event()
        class Speaker:
            def __init__(self,*_):pass
            def __enter__(self):return self
            def __exit__(self,*_):pass
            def write(self,pcm):played.append(pcm);first.set();return True
            def finish(self):finishes.append(True);finished.set();return True
            def close(self):pass
        worker=threading.Thread(target=provider._speaker)
        with patch('ai_doubao.NativeSpeaker',Speaker):
            worker.start()
            try:
                provider.audio_queue.put(b'\x01\x02'*480)
                self.assertTrue(first.wait(1))
                self.assertFalse(finished.wait(.25),'a 100ms gap must not drain the current response')
                provider.audio_queue.put(b'\x03\x04'*480)
                provider.audio_queue.put(None)
                self.assertTrue(finished.wait(1))
                self.assertFalse(stop.is_set())
            finally:stop.set();worker.join(1)
        self.assertFalse(worker.is_alive())
        self.assertEqual(played,[b'\x01\x02'*480,b'\x03\x04'*480])
        self.assertEqual(len(finishes),1)
        self.assertEqual(sum(e['kind']=='speaker_playback_started' for e in hub.events),1)
        self.assertFalse(any(e['kind']=='speaker_error' for e in hub.events))

    def test_mute_or_session_stop_cancels_drain_promptly_without_a_false_eintr_error(self):
        for which in ('mute','stop','mute_then_unmute'):
            with self.subTest(which=which),tempfile.TemporaryDirectory() as directory:
                ready=Path(directory)/'draining'
                terminated=Path(directory)/'cancelled'
                exe=self.executable(directory,
                    'import signal,sys,time\nfrom pathlib import Path\n'
                    'def interrupted(*_):\n Path('+repr(str(terminated))+').touch()\n time.sleep(.15)\n sys.stderr.write("aplay: pcm_write:2178: write error: Interrupted system call\\n");sys.stderr.flush();sys.exit(1)\n'
                    'signal.signal(signal.SIGTERM,interrupted)\n'
                    'sys.stdin.buffer.read()\nPath('+repr(str(ready))+').touch()\ntime.sleep(10)\n')
                stop=threading.Event();mute=threading.Event();results=[];errors=[]
                with patch('ai_hat_audio.shutil.which',return_value=exe):
                    with NativeSpeaker('plughw:aic3104',stop,mute) as speaker:
                        speaker.write(b'\0\0'*480);proc=speaker.proc
                        def finish():
                            try:results.append(speaker.finish())
                            except Exception as exc:errors.append(exc)
                        worker=threading.Thread(target=finish);worker.start()
                        deadline=time.monotonic()+2
                        while not ready.exists() and time.monotonic()<deadline:threading.Event().wait(.01)
                        self.assertTrue(ready.exists())
                        (stop if which=='stop' else mute).set()
                        if which=='mute_then_unmute':
                            deadline=time.monotonic()+1
                            while not terminated.exists() and time.monotonic()<deadline:threading.Event().wait(.01)
                            self.assertTrue(terminated.exists())
                            mute.clear()
                        worker.join(1)
                        self.assertFalse(worker.is_alive(),'mute and stop must not wait for tail audio')
                        self.assertIsNotNone(proc.poll())
                        self.assertEqual(errors,[])
                        self.assertEqual(results,[False])

    def test_unexpected_player_failure_is_reported_instead_of_silently_swallowed(self):
        for detail in ('Device or resource busy','Interrupted system call'):
            with self.subTest(detail=detail),tempfile.TemporaryDirectory() as directory:
                exe=self.executable(directory,'import sys\nsys.stdin.buffer.read()\nsys.stderr.write('+repr(detail+'\n')+');sys.exit(1)\n')
                with patch('ai_hat_audio.shutil.which',return_value=exe):
                    with NativeSpeaker('plughw:aic3104') as speaker:
                        speaker.write(b'\0\0'*480)
                        with self.assertRaisesRegex(AudioError,detail):speaker.finish()


if __name__=='__main__':unittest.main()

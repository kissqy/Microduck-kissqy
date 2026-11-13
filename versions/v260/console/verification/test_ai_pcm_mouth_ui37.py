"""Sound-driven beak frames and successful native PCM write timing; fake ALSA."""
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from ai_hat_audio import NativeSpeaker
from ai_doubao import MouthEnvelope
from verification import test_ai_hat as hat


class PCMMouthTests(unittest.TestCase):
    def test_actual_sound_envelope_has_official_full_open_and_partial_close(self):
        e=MouthEnvelope()
        self.assertEqual(e.update(struct.pack('<h',16000)*1024),1.)
        medium=e.update(struct.pack('<h',5000)*1024)
        self.assertGreater(medium,.2);self.assertLess(medium,1.)
        self.assertEqual(e.update(b'\0\0'*1024),.2)
        self.assertEqual(e.update(struct.pack('<h',18000)*1024),1.)

    def test_mouth_observer_tracks_written_bytes_and_cannot_break_native_audio(self):
        for fail in (False,True):
            with self.subTest(observer_fails=fail),tempfile.TemporaryDirectory() as directory:
                output=Path(directory)/'played.pcm'
                source='import sys\nfrom pathlib import Path\nPath('+repr(str(output))+').write_bytes(sys.stdin.buffer.read())\n'
                executable=hat.ALSATests().executable(directory,'aplay',source)
                pcm=struct.pack('<h',321)*6000;frames=[]
                def observer(data,at,seconds):
                    frames.append((data,at,seconds))
                    if fail:raise OSError('fixture mouth observer failed')
                with patch('ai_hat_audio.shutil.which',return_value=executable):
                    with NativeSpeaker('plughw:aic3104') as speaker:
                        speaker.pcm_observer=observer
                        self.assertTrue(speaker.write(pcm));self.assertTrue(speaker.finish())
                self.assertEqual(output.read_bytes(),pcm)
                self.assertEqual(b''.join(data for data,_,_ in frames),pcm)
                self.assertAlmostEqual(sum(seconds for _,_,seconds in frames),len(pcm)/48000)
                for a,b in zip(frames,frames[1:]):self.assertGreaterEqual(b[1],a[1]+a[2])


if __name__=='__main__':unittest.main()

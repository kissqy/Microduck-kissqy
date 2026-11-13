"""Original photo forwarding: no image workers, byte identity and honest timing."""
import base64
import io
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch
import zipfile

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
import ai_vision as vision
from ai_remote import worker_bundle
from verification.test_ai_vision_ui13 import PNG


class OriginalPhotoTests(unittest.TestCase):
    def test_image_workers_never_start_and_legacy_processing_flag_is_ignored(self):
        events=[]
        with patch('subprocess.Popen',side_effect=AssertionError('do not start an encoder')), \
             patch('ai_vision.capture_png',return_value=PNG) as capture, \
             patch('ai_vision.understand_png',return_value='物品。') as observe:
            service=vision.VisualService(vision.validate_vision('fixture-vision-key',backlight=True),threading.Event(),
                lambda kind,**fields:events.append({'kind':kind,**fields}))
            try:
                self.assertTrue(service.inspect({'question':'看看'})['accepted'])
                self.assertTrue(service.wait_preview())
            finally:service.close()
        self.assertEqual(capture.call_count,1);self.assertEqual(observe.call_args.args[0],PNG)
        self.assertFalse(service.settings['backlight'])
        assembler=vision.FrameAssembler();frame=None
        for event in events:
            if event['kind'].startswith('vision_frame_'):frame=assembler.feed(event) or frame
        self.assertEqual(frame[1],PNG)
        info=next(e for e in events if e['kind']=='vision_image')
        self.assertFalse(info['lift_applied']);self.assertEqual(info['capture_backend'],'mediad_original_png')

    def test_original_fetch_time_is_not_hidden_as_zero_image_processing(self):
        with patch('ai_vision.capture_png',return_value=PNG),patch('ai_vision.time.monotonic',side_effect=[0,.204,.205]):
            data,info=vision.capture_image(threading.Event(),lambda *a,**k:None)
        self.assertEqual(data,PNG)
        self.assertEqual(info['read_ms'],204);self.assertEqual(info['image_ms'],1);self.assertEqual(info['capture_ms'],205)

    def test_invalid_or_oversized_photo_never_reaches_the_model(self):
        for bad in (b'bad image',b'x'*(vision.MAX_IMAGE_BYTES+1)):
            with self.subTest(size=len(bad)),patch('ai_vision.capture_png',return_value=bad), \
                 patch('ai_vision.understand_png') as observe:
                service=vision.VisualService(vision.validate_vision('fixture-vision-key'),threading.Event(),lambda *a,**k:None)
                try:self.assertFalse(service.inspect({'question':'看看'})['accepted'])
                finally:service.close()
                observe.assert_not_called()

    def test_zero_worker_bundle_no_longer_includes_photo_filter_modules(self):
        data,_=worker_bundle()
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(data))) as archive:
            self.assertNotIn('ai_image.py',archive.namelist())
            self.assertNotIn('ai_fast_image.py',archive.namelist())
            source=archive.read('ai_vision.py').decode()
            self.assertNotIn('encode_jpeg',source);self.assertNotIn('lift_png',source)

    def test_stopped_capture_never_uploads_a_photo(self):
        stop=threading.Event();stop.set()
        with patch('ai_vision.capture_png') as capture,patch('ai_vision.understand_png') as observe:
            service=vision.VisualService(vision.validate_vision('fixture-vision-key'),stop,lambda *a,**k:None)
            try:self.assertFalse(service.inspect({'question':'看看'})['accepted'])
            finally:service.close()
        capture.assert_not_called();observe.assert_not_called()


if __name__=='__main__':unittest.main()

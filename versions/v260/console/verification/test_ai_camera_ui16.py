"""Warm-frame fast path, independent previews and bounded diagnostics output."""
import base64
import contextlib
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
import ai_vision as vision
from ai_zero import EventWriter
from ai_runtime import AIHub
from ai_preferences import AIPreferences
from telemetry import Store
from verification.test_ai_vision_ui13 import PNG,FixtureServer

JPEG=(ROOT/'verification/fixtures/vision-ui16.jpg').read_bytes()


class FastFrameTests(unittest.TestCase):
    def test_warm_stream_reads_one_original_photo_without_a_lease_or_exposure_wait(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture=FixtureServer(directory);fixture.active=True;fixture.capture_path.write_text('{"status":"active"}')
            try:
                with patch('ai_vision.CameraLease',side_effect=AssertionError('do not reopen capture')), \
                     patch('ai_vision.wait_camera_exposure',side_effect=AssertionError('do not wait for AE')), \
                     patch('ai_vision.raw_frame',side_effect=AssertionError('do not fetch another raw frame')):
                    data,info=vision.capture_image(threading.Event(),lambda *a,**k:None,
                        url='http://127.0.0.1:'+str(fixture.port)+'/frame',capture_path=fixture.capture_path)
                self.assertEqual(data,PNG);self.assertEqual(fixture.frames,1)
                self.assertEqual(info['capture_backend'],'mediad_original_png');self.assertFalse(info['lift_applied'])
            finally:fixture.close()

    def test_cold_camera_keeps_the_existing_exposure_warmup(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture=FixtureServer(directory)
            @contextlib.contextmanager
            def wake(*_):
                fixture.active=True;fixture.capture_path.write_text('{"status":"active"}')
                yield
            try:
                with patch('ai_vision.CameraLease',side_effect=wake) as lease,patch('ai_vision.wait_camera_exposure') as wait:
                    data,_=vision.capture_image(threading.Event(),lambda *a,**k:None,
                        url='http://127.0.0.1:'+str(fixture.port)+'/frame',capture_path=fixture.capture_path)
                self.assertEqual(data,PNG);self.assertEqual(lease.call_count,1);self.assertEqual(wait.call_count,1)
            finally:fixture.close()

    def test_warm_png_compatibility_route_also_skips_reopening_and_ae_wait(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture=FixtureServer(directory);fixture.active=True;fixture.capture_path.write_text('{"status":"active"}')
            try:
                with patch('ai_vision.CameraLease',side_effect=AssertionError('do not reopen')), \
                     patch('ai_vision.wait_camera_exposure',side_effect=AssertionError('do not wait')):
                    data=vision.capture_png(threading.Event(),'http://127.0.0.1:'+str(fixture.port)+'/frame',fixture.capture_path)
                self.assertEqual(data,PNG);self.assertEqual(fixture.frames,1)
            finally:fixture.close()


    def test_real_jpeg_geometry_and_mime_are_validated_for_preview_and_upload(self):
        self.assertEqual(vision.image_geometry(JPEG),(32,16));self.assertEqual(vision.image_mime(JPEG),'image/jpeg')
        with self.assertRaises(ValueError):vision.image_geometry(JPEG[:-2])
        with tempfile.TemporaryDirectory() as directory:
            fixture=FixtureServer(directory)
            try:
                with patch('ai_vision.ARK_URL','http://127.0.0.1:'+str(fixture.port)+'/ark'):
                    vision.understand_png(JPEG,'眼前是什么？','fixture-vision-key',vision.DEFAULT_VISION_MODEL)
                body=next(x[2] for x in fixture.calls if x[0]=='ark')
                url=body['messages'][1]['content'][0]['image_url']['url']
                self.assertTrue(url.startswith('data:image/jpeg;base64,'))
                self.assertEqual(base64.b64decode(url.split(',',1)[1]),JPEG)
            finally:fixture.close()

    def test_frame_relay_refuses_a_jpeg_mislabeled_as_png(self):
        frame={'kind':'vision_frame_start','capture_id':'a'*32,'width':32,'height':16,
               'size':len(JPEG),'parts':1,'sha256':__import__('hashlib').sha256(JPEG).hexdigest(),'captured_at_ms':1,'mime':'image/png'}
        assembler=vision.FrameAssembler();assembler.feed(frame)
        assembler.feed({'kind':'vision_frame_chunk','capture_id':'a'*32,'index':0,'data':base64.b64encode(JPEG).decode()})
        with self.assertRaisesRegex(ValueError,'类型'):assembler.feed({'kind':'vision_frame_end','capture_id':'a'*32})


class ParallelTests(unittest.TestCase):
    def service(self,log,stop=None):
        service=vision.VisualService(vision.validate_vision('fixture-vision-key'),stop or threading.Event(),log)
        self.addCleanup(service.close);return service

    def test_model_result_returns_while_the_preview_is_still_blocked(self):
        entered=threading.Event();release=threading.Event();events=[]
        self.addCleanup(release.set)
        def log(kind,**fields):
            if kind=='vision_frame_chunk':entered.set();release.wait(2)
            events.append({'kind':kind,**fields})
        service=self.service(log);started=time.monotonic()
        def observe(*args):self.assertTrue(entered.wait(1));return '物品。'
        with patch('ai_vision.capture_png',return_value=PNG),patch('ai_vision.understand_png',side_effect=observe):
            result=service.inspect({'question':'看看'})
        self.assertTrue(result['accepted']);self.assertLess(time.monotonic()-started,1)
        self.assertFalse(any(x['kind']=='vision_frame_end' for x in events))
        release.set();self.assertTrue(service.wait_preview())

    def test_real_output_pipe_backpressure_does_not_block_the_model_or_shutdown(self):
        reader,fd=os.pipe();stop=threading.Event();writer=EventWriter(fd,stop)
        try:
            while True:
                try:os.write(fd,b'x'*4096)
                except BlockingIOError:break
            service=self.service(lambda kind,**fields:writer.send(kind,json.dumps({'kind':kind,**fields})),stop)
            started=time.monotonic()
            with patch('ai_vision.capture_png',return_value=PNG),patch('ai_vision.understand_png',return_value='物品。'):
                self.assertTrue(service.inspect({'question':'看看'})['accepted'])
            self.assertLess(time.monotonic()-started,.5)
            service.close();started=time.monotonic();writer.close()
            self.assertLess(time.monotonic()-started,1.2);self.assertFalse(writer.thread.is_alive())
        finally:
            writer.close();os.close(reader);os.close(fd)

    def test_preview_queue_is_bounded_and_retains_earlier_chat_photos(self):
        entered=threading.Event();release=threading.Event();completed=[]
        self.addCleanup(release.set)
        def log(kind,**fields):
            if kind=='vision_frame_start' and fields['capture_id']=='a'*32:entered.set();release.wait(2)
            if kind=='vision_frame_end':completed.append(fields['capture_id'])
        service=self.service(log)
        def meta(letter):return {'capture_id':letter*32,'width':32,'height':16,'captured_at_ms':1}
        service._queue_preview(JPEG,meta('a'));self.assertTrue(entered.wait(1))
        service._queue_preview(JPEG,meta('b'));service._queue_preview(JPEG,meta('c'))
        self.assertEqual(service.preview_queue.qsize(),2)
        self.assertFalse(service._queue_preview(JPEG,meta('d')))
        release.set();self.assertTrue(service.wait_preview());self.assertEqual(completed,['a'*32,'b'*32,'c'*32])

    def test_delayed_preview_cannot_replace_a_new_request(self):
        with tempfile.TemporaryDirectory() as directory:
            hub=AIHub(Store('service'),preferences=AIPreferences(Path(directory)/'prefs.json'))
            try:
                hub.log('vision_state',phase='capturing',request_id='b'*32,message='new photo')
                old={'capture_id':'a'*32,'width':32,'height':16,'captured_at_ms':1}
                self.assertFalse(hub.update_vision_frame(old,JPEG));self.assertIsNone(hub.vision_frame)
                self.assertTrue(hub.update_vision_frame({**old,'capture_id':'b'*32},JPEG))
            finally:hub.close()


if __name__=='__main__':unittest.main()

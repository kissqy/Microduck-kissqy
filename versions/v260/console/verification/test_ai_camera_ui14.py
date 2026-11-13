"""Official raw-frame metering, bounded AE warmup and unchanged PNG capture.

Real local stream/HTTP/WebSocket fixtures; no sensor, motor or cloud writes.
This test host prohibits AF_UNIX, so only Unix connection addressing is adapted
to loopback TCP; production still uses the official local Unix stream socket.
"""
import contextlib
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
import ai_vision as vision
from ai_preferences import AIPreferences
from ai_runtime import AIHub
from telemetry import Store
from verification.test_ai_vision_ui13 import FixtureServer,PNG


class ClockStop:
    def __init__(self,cancel_at=None):self.now=0.;self.cancel_at=cancel_at;self.cancelled=False
    def is_set(self):return self.cancelled
    def wait(self,seconds):
        self.now+=seconds
        if self.cancel_at is not None and self.now>=self.cancel_at:self.cancelled=True
        return self.cancelled


class MeterTests(unittest.TestCase):
    def raw(self,meta,payload):
        directory=tempfile.TemporaryDirectory();path=Path(directory.name)/'media.sock'
        listener=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        listener.bind(('127.0.0.1',0));listener.listen(1)
        address=listener.getsockname()
        class LocalStream:
            def __init__(self,family,kind):
                assert family==socket.AF_UNIX and kind==socket.SOCK_STREAM
                self.peer=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
            def connect(self,requested):
                assert requested==str(path)
                self.peer.connect(address)
            def __getattr__(self,name):return getattr(self.peer,name)
            def __enter__(self):return self
            def __exit__(self,*args):self.peer.close()
        api=SimpleNamespace(socket=LocalStream,AF_UNIX=socket.AF_UNIX,
                            SOCK_STREAM=socket.SOCK_STREAM,timeout=socket.timeout)
        received=[]
        def serve():
            try:
                with listener.accept()[0] as peer:
                    data=bytearray()
                    while b'\n' not in data:data.extend(peer.recv(4096))
                    received.append(json.loads(data))
                    packet=json.dumps({'jsonrpc':'2.0','id':1,'result':meta}).encode()+b'\n'+payload
                    # Header and pixels may share a packet or split anywhere.
                    with contextlib.suppress(BrokenPipeError):
                        for a,b in ((0,7),(7,63),(63,len(packet))):peer.sendall(packet[a:b])
            finally:listener.close()
        worker=threading.Thread(target=serve);worker.start()
        try:
            with patch('ai_vision.socket',api):
                return vision.frame_luma(threading.Event(),path),received
        finally:worker.join(2);directory.cleanup()

    def test_stream_rpc_samples_only_fresh_uyvy_luma_not_chroma(self):
        meta={'width':16,'height':2,'format':'UYVY','bytes':64,'captured_at_unix_us':12345,'rotate':90}
        sample,requests=self.raw(meta,bytes([200,64,200,64])*16)
        self.assertEqual(sample,(64.,12345))
        self.assertEqual(requests,[{'jsonrpc':'2.0','id':1,'method':'media.frame','params':{}}])

    def test_bad_geometry_or_wrong_format_is_refused_before_reading_pixels(self):
        meta={'width':16,'height':2,'format':'UYVY','bytes':64,'captured_at_unix_us':12345}
        for change in ({'format':'NV12'},{'bytes':200_000_000},{'width':15},{'captured_at_unix_us':0}):
            with self.subTest(change=change),self.assertRaises(ValueError):self.raw({**meta,**change},b'')

    def settle(self,values,*,cold=True,stop=None):
        stop=stop or ClockStop();events=[];counter=[0]
        def reader():
            i=counter[0];counter[0]+=1
            value=values[min(i,len(values)-1)]
            return value if isinstance(value,tuple) else (value,i+1)
        def log(kind,**fields):events.append({'kind':kind,**fields})
        vision.wait_camera_exposure(stop,cold,progress=log,clock=lambda:stop.now,reader=reader)
        return stop,events,counter[0]

    def test_cold_start_discards_dark_samples_until_official_target_is_stable(self):
        stop,events,count=self.settle([8,20,38,60,76,88,90])
        self.assertTrue(events[-1]['exposure_ready'])
        self.assertEqual(events[-1]['mean_luma'],90)
        self.assertGreaterEqual(stop.now,2)
        self.assertEqual(count,7)
        self.assertEqual(vision.CAMERA_TARGET_Y,90)
        self.assertEqual(vision.CAMERA_AE_DEADBAND,.12)

    def test_warm_camera_returns_after_two_fresh_stable_samples(self):
        stop,events,count=self.settle([90,90],cold=False)
        self.assertEqual(count,2);self.assertEqual(stop.now,.5)
        self.assertTrue(events[-1]['exposure_ready'])

    def test_repeated_cached_timestamp_cannot_pretend_to_be_stable_fresh_frames(self):
        stop,events,count=self.settle([(90,1)])
        self.assertFalse(events[-1]['exposure_ready'])
        self.assertEqual(events[-1]['sample_count'],1)
        self.assertEqual(stop.now,vision.CAMERA_SETTLE_LIMIT)
        self.assertIn('上限',events[-1]['exposure_warning'])

    def test_dark_or_overbright_scene_has_a_deadline_and_explicit_diagnostic(self):
        for level in (5,240):
            with self.subTest(level=level):
                stop,events,count=self.settle([level])
                self.assertFalse(events[-1]['exposure_ready'])
                self.assertEqual(events[-1]['mean_luma'],level)
                self.assertEqual(stop.now,vision.CAMERA_SETTLE_LIMIT)
                self.assertLessEqual(count,24)

    def test_missing_raw_socket_keeps_png_compatibility_without_claiming_a_metered_result(self):
        stop=ClockStop();events=[]
        def log(kind,**fields):events.append(fields)
        def missing():raise PermissionError('fixture permission')
        vision.wait_camera_exposure(stop,True,progress=log,clock=lambda:stop.now,reader=missing)
        self.assertEqual(stop.now,3)
        self.assertFalse(events[-1]['exposure_ready'])
        self.assertIn('未读取到',events[-1]['exposure_warning'])

    def test_stop_interrupts_exposure_wait_instead_of_continuing_to_take_a_photo(self):
        stop=ClockStop(cancel_at=.5)
        with self.assertRaisesRegex(ValueError,'停止'):self.settle([10],stop=stop)
        self.assertEqual(stop.now,.5)


class CaptureTests(unittest.TestCase):
    def test_signalling_lease_is_held_through_exposure_settling_then_one_original_png_is_taken(self):
        with tempfile.TemporaryDirectory() as directory:
            server=FixtureServer(directory);lease=vision.CameraLease;seen=[];levels=iter([10,40,70,88,90])
            events=[]
            def meter(stop,path):
                self.assertTrue(server.active,'do not let demand capture sleep while AE is converging')
                self.assertEqual(server.frames,0,'do not encode/upload the first dark PNG')
                seen.append(True);return next(levels),len(seen)
            try:
                with patch('ai_vision.CameraLease',lambda stop:lease(stop,'ws://127.0.0.1:'+str(server.port))), \
                     patch('ai_vision.frame_luma',side_effect=meter):
                    image=vision.capture_png(threading.Event(),'http://127.0.0.1:'+str(server.port)+'/frame',
                        server.capture_path,progress=lambda kind,**fields:events.append(fields))
                self.assertEqual(image,PNG,'no gamma/brightness alteration of the uploaded image')
                self.assertEqual(server.frames,1)
                self.assertEqual(server.signals[-1],{'type':'endSession','sessionId':'our-photo-lease'})
                self.assertTrue(events[-1]['exposure_ready'])
            finally:server.close()

    def test_status_retains_numeric_exposure_diagnostics_and_clears_them_for_a_new_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            hub=AIHub(Store('service'),preferences=AIPreferences(Path(directory)/'prefs.json'))
            try:
                hub.log('camera_exposure',mean_luma=88.2,exposure_ready=True,exposure_warning='',message='曝光稳定')
                self.assertEqual(hub.status()['vision']['mean_luma'],88.2)
                self.assertTrue(hub.status()['vision']['exposure_ready'])
                hub.log('vision_state',phase='capturing',message='下一张')
                self.assertNotIn('mean_luma',hub.status()['vision'])
                self.assertNotIn('exposure_ready',hub.status()['vision'])
            finally:hub.close()


if __name__=='__main__':unittest.main()

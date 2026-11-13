"""Real loopback HTTP/WebSocket fixtures; actual camera/cloud/HAT are not claimed.

Exercises official mediad signalling + PNG /frame, official Ark JSON, Zero FC
receipt -> native speech, bounded preview bytes, saved keys and console routes.
"""
import base64
import contextlib
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import queue
import socket
import struct
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import urllib.error
import zlib

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0, str(ROOT))
import ai_vision as vision
from ai_doubao import DoubaoNative, URL as VOICE_URL
from ai_preferences import AIPreferences
from ai_remote import RemoteAI
from ai_runtime import AIHub
from ai_zero import ZeroHub
from console import handler_for
from telemetry import Store
from _ai_vendor import websocket
from service_channel import ServiceChannel
from verification.test_ai_hat import Hub
import verification.test_ai_hat as hat_fixture

VOICE_KEY = 'fixture-speech-key-123456'
VISION_KEY = 'fixture-vision-key-654321'


def png_fixture():
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 2, 1, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(b'\0\xff\0\0\0\0\xff')) + chunk(b'IEND', b'')


PNG = png_fixture()


class FixtureServer:
    def __init__(self, directory):
        self.capture_path = Path(directory) / 'capture.json'
        self.capture_path.write_text('{"status":"asleep"}')
        self.frames = 0;self.calls = [];self.signals = [];self.active = False
        self.error = 0;self.delay = .04
        self.seen_upload = threading.Event()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):pass

            def do_GET(self):
                if self.headers.get('Upgrade', '').lower() == 'websocket':return self.signalling()
                if self.path != '/frame':return self.reply(404, b'not found')
                owner.frames += 1
                if not owner.active:return self.reply(503, b'Camera snapshot unavailable')
                owner.calls.append(('frame', dict(self.headers)))
                self.reply(200, PNG, 'image/png')

            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                owner.calls.append(('ark', dict(self.headers), payload));owner.seen_upload.set()
                threading.Event().wait(owner.delay)
                if owner.error:return self.reply(owner.error, b'{"error":{"message":"fixture failure"}}', 'application/json')
                self.reply(200, json.dumps({'choices': [{'finish_reason': 'stop', 'message': {'content': '这是红蓝色块。'}}]}).encode(), 'application/json')

            def reply(self, code, data, mime='text/plain'):
                self.send_response(code);self.send_header('Content-Type', mime)
                self.send_header('Content-Length', str(len(data)));self.end_headers()
                with contextlib.suppress(BrokenPipeError):self.wfile.write(data)

            def signalling(self):
                key = self.headers['Sec-WebSocket-Key']
                accept = base64.b64encode(hashlib.sha1((key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
                self.send_response(101);self.send_header('Upgrade', 'websocket');self.send_header('Connection', 'Upgrade')
                self.send_header('Sec-WebSocket-Accept', accept);self.end_headers()
                self.connection.settimeout(3)

                def send(event):
                    data = json.dumps(event).encode()
                    header = bytes([129, len(data)]) if len(data) < 126 else b'\x81\x7e' + struct.pack('>H', len(data))
                    self.wfile.write(header + data);self.wfile.flush()

                send({'type': 'welcome', 'peerId': 'fixture-viewer'})
                try:
                    while True:
                        first = self.rfile.read(2)
                        if not first:return
                        opcode, length = first[0] & 15, first[1] & 127
                        if length == 126:length = struct.unpack('>H', self.rfile.read(2))[0]
                        if length == 127:length = struct.unpack('>Q', self.rfile.read(8))[0]
                        mask = self.rfile.read(4) if first[1] & 128 else b''
                        data = self.rfile.read(length)
                        if opcode == 8:
                            self.wfile.write(b'\x88\0');self.wfile.flush();return
                        if mask:data = bytes(c ^ mask[i % 4] for i, c in enumerate(data))
                        event = json.loads(data);owner.signals.append(event)
                        if event['type'] == 'list':send({'type': 'list', 'producers': [{'id': 'real-head-camera'}]})
                        elif event['type'] == 'startSession':
                            owner.active = True;owner.capture_path.write_text('{"status":"active"}')
                            send({'type': 'sessionStarted', 'sessionId': 'our-photo-lease'})
                        elif event['type'] == 'endSession':
                            self.assert_session(event)
                            owner.active = False;owner.capture_path.write_text('{"status":"asleep"}')
                except (OSError, ValueError):pass
                finally:owner.active = False

            def assert_session(self, event):
                if event['sessionId'] != 'our-photo-lease':raise AssertionError('ended another viewer')

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.daemon_threads = True
        self.port = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True);self.thread.start()

    @contextlib.contextmanager
    def route_camera(self):
        # Route the production capture helper to real loopback HTTP + WebSocket,
        # not a fake capture implementation or a camera file.
        original_lease = vision.CameraLease
        original_capture = vision.capture_png
        def local_capture(stop,url=None,capture_path=None,*,meter_path=None,progress=None):
            return original_capture(stop,'http://127.0.0.1:'+str(self.port)+'/frame',
                                    self.capture_path,meter_path=None,progress=progress)
        with patch('ai_vision.CameraLease', lambda stop: original_lease(stop, 'ws://127.0.0.1:' + str(self.port))), \
             patch('ai_vision.capture_png', local_capture), \
             patch('ai_vision.ARK_URL', 'http://127.0.0.1:' + str(self.port) + '/chat/completions'):
            yield

    def close(self):
        self.server.shutdown();self.server.server_close();self.thread.join(2)


class VisionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.fixture = FixtureServer(self.directory.name)
        self.stop = threading.Event();self.events = [];self.services=[]

    def tearDown(self):
        self.stop.set()
        for service in self.services:service.close()
        self.fixture.close();self.directory.cleanup()

    def log(self, kind, **fields):self.events.append({'kind': kind, **fields})

    def service(self):
        service=vision.VisualService(vision.validate_vision(VISION_KEY), self.stop, self.log)
        self.services.append(service);return service

    def test_explicit_single_frame_uses_installed_camera_and_ark_without_device_takeover(self):
        service = self.service()
        self.assertEqual(self.fixture.frames, 0, 'constructing a voice/vision session must not capture')
        with self.fixture.route_camera():result = service.inspect({'question': '这是什么颜色？'})
        self.assertTrue(service.wait_preview())
        self.assertTrue(result['accepted'], result)
        self.assertEqual(self.fixture.frames, 1)
        self.assertEqual([x['type'] for x in self.fixture.signals], ['list', 'startSession', 'endSession'])
        self.assertEqual(self.fixture.signals[-1]['sessionId'], 'our-photo-lease')
        self.assertFalse(self.fixture.active)
        ark = next(x for x in self.fixture.calls if x[0] == 'ark')
        self.assertEqual(ark[1]['Authorization'], 'Bearer ' + VISION_KEY)
        self.assertNotIn(VOICE_KEY, json.dumps(ark))
        body = ark[2]
        self.assertEqual(body['model'], vision.DEFAULT_VISION_MODEL)
        self.assertEqual(body['thinking'], {'type': 'disabled'})
        self.assertFalse(body['stream'])
        self.assertIn('最多20字', body['messages'][0]['content'])
        self.assertEqual(body['messages'][1]['content'][1]['text'], '这是什么颜色？')
        image = body['messages'][1]['content'][0]['image_url']['url']
        self.assertEqual(base64.b64decode(image.split(',', 1)[1]), PNG)
        assembler = vision.FrameAssembler();frame = None
        for event in self.events:
            if event['kind'].startswith('vision_frame_'):frame = assembler.feed(event) or frame
        self.assertEqual(frame[1], PNG, 'preview and uploaded image must be exactly the same bytes')
        self.assertEqual((frame[0]['width'], frame[0]['height']), (2, 1))
        self.assertEqual(result['observation'], '这是红蓝色块。')
        self.assertTrue(all(len(json.dumps(x, ensure_ascii=False).encode()) <= 65536 for x in self.events))

    def test_key_model_and_question_validation_do_not_capture_or_accept_arbitrary_operations(self):
        for value in ('key\r\nAuthorization: bad', 'short', ['key']):
            with self.subTest(value=value), self.assertRaises(ValueError):vision.validate_vision(value)
        with self.assertRaises(ValueError):vision.validate_vision(VISION_KEY, '../../run')
        for args in ({}, {'question': 'x', 'url': 'http://elsewhere'}, {'question': 'x' * 301}, {'question': 5}):
            with self.subTest(args=args), self.assertRaises(ValueError):self.service().inspect(args)
        service = vision.VisualService(vision.validate_vision(), self.stop, self.log)
        self.assertFalse(service.inspect({'question': '看看'})['accepted'])
        self.assertEqual(self.fixture.frames, 0)

    def test_failed_visual_auth_has_one_attempt_and_does_not_stop_voice(self):
        self.fixture.error = 401
        with self.fixture.route_camera():result = self.service().inspect({'question': '这是什么？'})
        self.assertFalse(result['accepted']);self.assertIn('方舟', result['reason'])
        self.assertFalse(self.stop.is_set())
        self.assertEqual(self.fixture.frames, 1)
        self.assertEqual(sum(x[0] == 'ark' for x in self.fixture.calls), 1, 'no automatic retry')
        self.assertEqual(self.events[-1]['phase'], 'error')

    def test_busy_and_stop_prevent_duplicate_or_late_uploads(self):
        service = self.service();service.lock.acquire()
        try:self.assertIn('稍候', service.inspect({'question': '看看'})['reason'])
        finally:service.lock.release()
        self.stop.set()
        with self.fixture.route_camera():result = service.inspect({'question': '看看'})
        self.assertFalse(result['accepted']);self.assertEqual(self.fixture.frames, 0)
        self.assertFalse(self.fixture.calls)

    def test_failed_camera_never_uploads_any_image(self):
        with patch('ai_vision.capture_png', side_effect=ValueError('摄像头未就绪')), patch('ai_vision.understand_png') as understand:
            result = self.service().inspect({'question': '看看'})
        understand.assert_not_called();self.assertIn('摄像头', result['reason'])
        self.assertFalse(self.stop.is_set())

    def test_frame_assembler_rejects_missing_order_corruption_and_oversize(self):
        start = {'kind': 'vision_frame_start', 'capture_id': 'a' * 32, 'width': 2, 'height': 1,
                 'size': len(PNG), 'sha256': hashlib.sha256(PNG).hexdigest(), 'parts': 1, 'captured_at_ms': 1}
        for changed in ({'size': vision.MAX_IMAGE_BYTES + 1}, {'parts': 264}, {'capture_id': '../x'}):
            with self.assertRaises(ValueError):vision.FrameAssembler().feed({**start, **changed})
        assembler = vision.FrameAssembler();assembler.feed(start)
        with self.assertRaises(ValueError):assembler.feed({'kind': 'vision_frame_end', 'capture_id': 'a' * 32})
        assembler.feed(start)
        with self.assertRaises(ValueError):assembler.feed({'kind': 'vision_frame_chunk', 'capture_id': 'a' * 32, 'index': 1, 'data': 'xxxx'})
        assembler.reset();assembler.feed(start)
        assembler.feed({'kind': 'vision_frame_chunk', 'capture_id': 'a' * 32, 'index': 0, 'data': base64.b64encode(PNG[:-1] + b'x').decode()})
        with self.assertRaisesRegex(ValueError, '校验'):assembler.feed({'kind': 'vision_frame_end', 'capture_id': 'a' * 32})
        with self.assertRaises(ValueError):vision.png_geometry(PNG[:-1])


class IntegrationTests(unittest.TestCase):
    def test_actual_service_channel_sends_vision_settings_and_button_to_extracted_zero_worker(self):
        channel=ServiceChannel(None,'/tmp/fixture-unused.sock')
        hub=Hub();hub.vision_settings=vision.validate_vision(VISION_KEY)
        remote=RemoteAI(hub,channel,threading.Event())
        bundle=hat_fixture.RelayTests().fake_bundle()
        with patch('ai_remote.worker_bundle',return_value=bundle):
            thread=threading.Thread(target=remote.run);thread.start()
            try:
                deadline=time.monotonic()+4
                while not any(e['kind']=='fixture_action_finished' for e in hub.events) and time.monotonic()<deadline:
                    threading.Event().wait(.01)
                self.assertTrue(hub.provider_ready)
                remote.inspect_scene('看看镜头前的物品')
                deadline=time.monotonic()+2
                while not any(e['kind']=='fixture_vision_button' for e in hub.events) and time.monotonic()<deadline:
                    threading.Event().wait(.01)
                settings=next(e for e in hub.events if e['kind']=='fixture_vision_settings')
                self.assertEqual(settings['model'],vision.DEFAULT_VISION_MODEL)
                self.assertFalse(settings['enabled'],'continuous capture defaults off while recognition remains available')
                self.assertTrue(settings['credential_present'])
                button=next(e for e in hub.events if e['kind']=='fixture_vision_button')
                self.assertEqual(button['question'],'看看镜头前的物品')
                self.assertEqual(button['message'],'[REDACTED]')
                self.assertNotIn(VISION_KEY,json.dumps(hub.events))
            finally:remote.close();thread.join(3);channel.close()
        self.assertFalse(thread.is_alive())

    def test_real_zero_native_fc_path_keeps_audio_uplink_during_vision_then_plays_provider_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = FixtureServer(directory)
            stop = threading.Event();events = [];sent = [];played = [];finished = threading.Event()
            hub = ZeroHub({'api_key': VOICE_KEY, 'voice_id': 'voice_a', 'tools': [],
                'voice_enabled': True, 'vision': vision.validate_vision(VISION_KEY)}, stop)
            def log(kind,**fields):
                events.append({'kind':kind,**fields})
                if kind=='action_request' and fields.get('name')=='wait_capture_model':
                    hub.gate.feedback(fields['request_id'],{'accepted':True,'status':'model_idle','model_completed_t_ns':1})
            hub.log=log
            hub.vision.log = hub.log
            provider = DoubaoNative(hub, VOICE_KEY, 'voice_a', None, None, stop)
            pcm = struct.pack('<h', 321) * 480

            class VoiceSocket:
                def __init__(self):self.events = queue.Queue();self.audio_packets = 0;self.pending = False;self.feedback_at = 0
                def settimeout(self, _):pass
                def send(self, raw):
                    event = json.loads(raw);sent.append(event)
                    if event['type'] == 'session.create':self.events.put({'type': 'session.created', 'session': {'id': 'fixture'}})
                    elif event['type'] == 'input_audio_buffer.append':
                        self.audio_packets += 1
                        if self.pending:return
                        self.pending = True
                        self.events.put({'type': 'conversation.item.input_audio_transcription.completed', 'item_id': 'u1', 'transcript': '看看这是什么颜色？'})
                        self.events.put({'type': 'response.function_call_arguments.done', 'items': [{'name': 'inspect_scene',
                            'call_id': 'vision-call-1', 'arguments': '{"question":"眼前是什么颜色？"}'}]})
                    elif event['type'] == 'conversation.item.create':
                        self.feedback_at = self.audio_packets
                        result = json.loads(event['items'][0]['content'][0]['text'])
                        if result['accepted'] is not True:raise AssertionError(result)
                        self.events.put({'type': 'response.output_text.done', 'item_id': 'a1', 'text': '这是红蓝色块。'})
                        self.events.put({'type': 'response.output_audio.delta', 'delta': base64.b64encode(pcm).decode()})
                        self.events.put({'type': 'response.output_audio.done'})
                        self.events.put({'type': 'response.done'})
                def recv(self):
                    if finished.is_set():stop.set();return '{}'
                    try:return json.dumps(self.events.get(timeout=.01))
                    except queue.Empty:raise websocket.WebSocketTimeoutException()
                def close(self, **_):pass

            class Mic:
                def __init__(self, *_):pass
                def __enter__(self):return self
                def __exit__(self, *_):pass
                def read(self):stop.wait(.005);return b'\0' * 640 if not stop.is_set() else b''

            class Speaker:
                def __init__(self, *_):pass
                def __enter__(self):return self
                def __exit__(self, *_):pass
                def write(self, data):played.append(data)
                def finish(self):
                    if played:finished.set()
                def close(self):pass

            ws = VoiceSocket();original_connect = websocket.create_connection
            def connect(url, **kwargs):return ws if url == VOICE_URL else original_connect(url, **kwargs)
            timer = threading.Timer(5, stop.set);timer.start()
            try:
                with fixture.route_camera(), patch.object(websocket, 'create_connection', side_effect=connect), \
                     patch('ai_doubao.NativeMicrophone', Mic), patch('ai_doubao.NativeSpeaker', Speaker):provider.run()
                self.assertTrue(finished.is_set(), events)
                self.assertGreaterEqual(ws.feedback_at, 5, 'camera/vision must not block the realtime mic/receiver')
                self.assertEqual(b''.join(played), pcm)
                self.assertEqual(fixture.frames, 1)
                session = next(e['session'] for e in sent if e['type'] == 'session.create')
                self.assertEqual([x['name'] for x in session['tools']], ['inspect_scene','list_voices','switch_voice'])
                self.assertIn('最多20字', session['instructions']);self.assertIn('只读拍照识图', session['instructions'])
                feedback = next(e for e in sent if e['type'] == 'conversation.item.create')
                self.assertEqual(feedback['items'][0]['call_id'], 'vision-call-1')
                self.assertEqual(feedback['items'][0]['role'], 'tool')
                self.assertTrue(any(e['kind'] == 'assistant_text' and e['text'] == '这是红蓝色块。' for e in events))
                self.assertFalse(any(e['type'] == 'response.create' or e['type'].startswith('speech_text_buffer') for e in sent))
                self.assertTrue(all(e.get('name') in ('read_distance','wait_capture_model') for e in events if e['kind']=='action_request'), 'vision may read cached model state and TOF, never request motion')
            finally:
                timer.cancel();provider.close();fixture.close()

    def test_manual_button_adds_real_visual_context_without_inventing_native_reply_or_tts(self):
        stop = threading.Event()
        hub = ZeroHub({'api_key': VOICE_KEY, 'tools': [], 'voice_enabled': True,
                       'vision': vision.validate_vision(VISION_KEY)}, stop)
        events = [];hub.log = lambda kind, **fields:events.append((kind, fields))
        provider = DoubaoNative(hub, VOICE_KEY, 'voice_a', None, None, stop)
        sent = [];provider._send = sent.append
        result = {'accepted': True, 'capture_id': 'a' * 32, 'observation': '这是一个杯子。',
                  'distance':{'available':True,'center_m':.8,'note':'前方测距，未逐像素配准'}}
        with patch.object(hub.vision, 'inspect', return_value=result) as inspect:
            provider.inspect_scene('眼前是什么？')
            deadline = time.monotonic() + 1
            while time.monotonic() < deadline:
                with provider.tool_lock:threads = list(provider.tool_threads)
                if not threads:break
                for t in threads:t.join(.05)
            inspect.assert_called_once_with({'question': '眼前是什么？'}, source='button')
        self.assertEqual([e['type'] for e in sent], ['conversation.item.create'])
        self.assertEqual([x['role'] for x in sent[0]['items']], ['user', 'assistant'])
        self.assertIn(result['observation'], sent[0]['items'][1]['content'][0]['text'])
        self.assertIn(json.dumps(result['distance'],ensure_ascii=False),sent[0]['items'][1]['content'][0]['text'])
        self.assertFalse(any(kind == 'assistant_text' for kind, _ in events), 'button output is labelled vision, not fake realtime text')
        self.assertTrue(provider.audio_queue.empty())

    def test_both_keys_survive_restart_dpapi_and_never_leak_into_status_trace_or_images(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = AIPreferences(Path(directory) / 'ai-voice.json')
            hub = AIHub(Store('service'), preferences=settings)
            try:
                hub.configure({'api_key': VOICE_KEY, 'vision_api_key': VISION_KEY,
                    'vision_model': vision.DEFAULT_VISION_MODEL, 'vision_enabled': True})
                restored = AIHub(Store('service'), preferences=settings)
                try:
                    self.assertEqual(restored.vision_settings, vision.validate_vision(VISION_KEY,enabled=True))
                    restored.configure({'vision_enabled': False})
                    self.assertEqual(settings.load()['vision']['api_key'], VISION_KEY)
                    restored.log('fixture_untrusted', message='echo ' + VISION_KEY + ' ' + VOICE_KEY)
                    exported = json.dumps(restored.tail()) + restored.trace_file.read_text()
                    for key in (VOICE_KEY, VISION_KEY):self.assertNotIn(key, exported)
                    remote = RemoteAI(restored, None, threading.Event())
                    service_events = []
                    def log(kind, **kw):service_events.append({'kind': kind, **kw})
                    service = vision.VisualService(vision.validate_vision(VISION_KEY), threading.Event(), log)
                    with patch('ai_vision.capture_png', return_value=PNG), patch('ai_vision.understand_png', return_value='杯子。'):
                        service.inspect({'question': '看看'})
                    self.assertTrue(service.wait_preview());service.close()
                    for event in service_events:remote._event(event)
                    capture_id = restored.status()['vision']['capture_id']
                    self.assertEqual(restored.get_vision_frame(capture_id), PNG)
                    self.assertIsNone(restored.get_vision_frame('wrong'))
                    log_text = restored.trace_file.read_text()
                    self.assertNotIn(base64.b64encode(PNG).decode(), log_text)
                    self.assertNotIn('vision_frame_chunk', log_text)
                    before = settings.path.read_bytes()
                    with patch('ai_preferences.os.replace', side_effect=OSError('denied')):
                        with self.assertRaises(ValueError):restored.configure({'vision_api_key': 'fixture-replacement-key'})
                    self.assertEqual(settings.path.read_bytes(), before)
                    self.assertEqual(restored.vision_settings['api_key'], VISION_KEY)
                finally:restored.close()
            finally:hub.close()
            def crypt(data, decrypt=False):return bytes(x ^ 0xa7 for x in data)
            with patch('ai_preferences.sys.platform', 'win32'), patch('sudo_credential._windows_protect', side_effect=crypt):
                settings.save(VOICE_KEY, 'voice_a', vision=vision.validate_vision(VISION_KEY))
                raw = settings.path.read_text()
                self.assertNotIn(VOICE_KEY, raw);self.assertNotIn(VISION_KEY, raw)
                loaded = settings.load()
                self.assertEqual(loaded['vision']['api_key'], VISION_KEY)
                self.assertEqual(loaded['api_key'], VOICE_KEY)

    def test_actual_console_vision_routes_keep_origin_token_and_readonly_frame_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            hub = AIHub(Store('service'), preferences=AIPreferences(Path(directory) / 'ai.json'))
            hub.configure({'api_key': VOICE_KEY, 'vision_api_key': VISION_KEY})
            class Provider:
                def __init__(self):self.questions = []
                def inspect_scene(self, text):self.questions.append(text)
                def close(self):pass
            provider = Provider();hub.provider = provider;hub.provider_ready = True
            cfg = {'bind': '127.0.0.1', 'control_token': 'fixture-control-token'}
            server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(hub.store, cfg, ai_hub=hub))
            thread = threading.Thread(target=server.serve_forever, daemon=True);thread.start()
            host = '127.0.0.1:' + str(server.server_port)
            def request(method, path, payload=None, token=True):
                c = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
                c.request(method, path, body=json.dumps(payload) if payload is not None else None,
                    headers={'Host': host, 'Origin': 'http://' + host, 'Content-Type': 'application/json',
                        'X-Control-Token': 'fixture-control-token' if token else 'bad'})
                response = c.getresponse();result = response.status, response.read(), dict(response.getheaders());c.close();return result
            try:
                self.assertEqual(request('POST', '/api/ai/vision', {'question': '看看'}, False)[0], 403)
                code, body, _ = request('POST', '/api/ai/vision', {'question': '看看这是什么？'})
                self.assertEqual(code, 200, body);self.assertEqual(provider.questions, ['看看这是什么？'])
                self.assertEqual(request('POST', '/api/ai/vision', {'question': '看看'})[0], 400, 'busy request must not reissue')
                hub.log('vision_state',phase='capturing',request_id='b'*32,message='fixture capture')
                hub.update_vision_frame({'capture_id': 'b' * 32, 'width': 2, 'height': 1, 'captured_at_ms': 1}, PNG)
                code, body, headers = request('GET', '/api/ai/vision/frame?id=' + 'b' * 32)
                self.assertEqual((code, body), (200, PNG));self.assertEqual(headers['Content-Type'], 'image/png')
                self.assertEqual(headers['Cache-Control'], 'no-store')
                self.assertEqual(request('GET', '/api/ai/vision/frame?id=stale')[0], 404)
                self.assertNotIn(VISION_KEY.encode(), request('GET', '/api/ai/status')[1])
            finally:hub.close();server.shutdown();server.server_close();thread.join(2)

    def test_bad_visual_preferences_keep_the_saved_voice_key_and_role_usable(self):
        with tempfile.TemporaryDirectory() as directory:
            settings=AIPreferences(Path(directory)/'ai.json')
            settings.save(VOICE_KEY,'voice_a','你是小鸭，最多20字。',vision=vision.validate_vision(VISION_KEY))
            raw=json.loads(settings.path.read_text());raw['vision']['model']='bad/model'
            settings.path.write_text(json.dumps(raw))
            hub=AIHub(Store('service'),preferences=settings)
            try:
                self.assertEqual(hub.api_key,VOICE_KEY)
                self.assertEqual(hub.voice_id,'voice_a')
                self.assertEqual(hub.persona,'你是小鸭，最多20字。')
                self.assertTrue(hub.status()['credentials_present'])
                self.assertFalse(hub.status()['vision']['credentials_present'])
                self.assertIn('保留语音',hub.status()['configuration_error'])
            finally:hub.close()


if __name__ == '__main__':unittest.main()

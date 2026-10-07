"""Raw robot telemetry relay. SSH and WebSocket carry the daemon's original bytes.

The PC keeps a 10 Hz compatibility mirror for existing maintenance checks. Display
adaptation and the bounded recording live in the browser; no observer runs on Zero.
"""
import base64
import hashlib
import json
import math
import queue
import secrets
import socket
import struct
import threading
import time

from telemetry import TTL
from ssh_connect import SSHConnectError

MAX_FRAME = 8 * 1024 * 1024
PROTOCOL = 'r17-telemetry'
TOF_IDLE_SECONDS = 5
GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'


def json_object(payload):
    def numeric(value):
        number = float(value)
        if not math.isfinite(number): raise ValueError('原始遥测包含非有限数')
        return number
    result = json.loads(payload, parse_float=numeric, parse_constant=numeric)
    if not isinstance(result, dict): raise ValueError('原始遥测消息必须是对象')
    return result


def decode_tree(payload):
    view, offset = memoryview(payload), 0
    def take(size):
        nonlocal offset
        if size < 0 or offset + size > len(view):
            raise ValueError('原始遥测帧被截断')
        value = view[offset:offset + size]
        offset += size
        return value
    def integer():
        return struct.unpack('<I', take(4))[0]
    def string():
        return bytes(take(integer())).decode('utf-8')
    def value(depth=0):
        if depth > 64:
            raise ValueError('原始遥测嵌套过深')
        tag = take(1)[0]
        if tag < 3:
            return (None, False, True)[tag]
        if tag in (3, 4, 5):
            number = struct.unpack({3:'<q', 4:'<Q', 5:'<d'}[tag], take(8))[0]
            # serde_json historically presents nonfinite measurements as null.
            # The forwarded binary record retains the original IEEE bits.
            return None if tag == 5 and not math.isfinite(number) else number
        if tag == 6:
            return string()
        if tag in (7, 8):
            size = integer()
            if size > len(view) - offset:
                raise ValueError('原始遥测集合长度无效')
            if tag == 7:
                return [value(depth + 1) for _ in range(size)]
            result = {}
            for _ in range(size):
                key = string()
                if key in result:
                    raise ValueError('原始遥测包含重复字段')
                result[key] = value(depth + 1)
            return result
        raise ValueError('原始遥测类型无效')
    result = value()
    if offset != len(view) or not isinstance(result, dict):
        raise ValueError('原始遥测根或尾部无效')
    return result


def merge(base, current):
    """Only metadata is inherited. Missing dynamic fields never retain an old sample."""
    result = dict(base)
    for key, value in current.items():
        result[key] = merge(base.get(key, {}), value) if isinstance(value, dict) and isinstance(base.get(key), dict) else value
    return result


class Mirror:
    def __init__(self, emit):
        self.emit, self.base = emit, {}
        self.last = -1
    def accept(self, frame):
        kind, payload = frame[4], frame[5:]
        now = time.monotonic()
        if kind == 1:
            meta = json_object(payload)
            if meta.get('schema') != 'r17.raw.v1':
                raise ValueError('原始遥测协议版本不符')
            self.base = meta.get('channels', {})
            if not isinstance(self.base, dict): raise ValueError('原始遥测元数据无效')
            for channel in ('calibration', 'capabilities'):
                if isinstance(meta.get(channel), dict):
                    self.emit({'channel': channel, 'data': meta[channel]})
            return
        if kind == 2 and now - self.last < .095:
            return
        if kind not in (2, 4):
            raise ValueError('原始遥测帧类型无效')
        data = decode_tree(payload)
        if kind == 2:
            self.last = now
        for channel, value in data.items():
            if channel in TTL and isinstance(value, dict):
                self.emit({'channel': channel, 'data': merge(self.base.get(channel, {}), value)})


class Hub:
    def __init__(self):
        self.lock = threading.RLock()
        self.clients = set()
        self.cache = {}
        self.generation = 0
    def reset(self, clear=True):
        with self.lock:
            self.cache.clear()
            self.generation += 1
            self._publish(1, json.dumps({'reset': self.generation, 'preserve':not clear}).encode())
    def _publish(self, opcode, data):
        for client in tuple(self.clients):
            try:
                client.put_nowait((opcode, data))
            except queue.Full:
                # A slow browser must reconnect, rather than receive an unbounded
                # backlog and accidentally present an old control sample as live.
                self.clients.discard(client)
                close = getattr(client, 'close_stream', None)
                if close: close()
                while True:
                    try: client.get_nowait()
                    except queue.Empty: break
                client.put_nowait(None)
    def raw(self, frame, generation=None, metadata=False):
        with self.lock:
            if generation is not None and generation != self.generation: return
            if frame[4] == 1 or metadata: self.cache[frame[4]] = frame
            self._publish(2, frame)
    def event(self, event, generation=None):
        with self.lock:
            if generation is not None and generation != self.generation: return
            self._publish(1, json.dumps({'event':event}, ensure_ascii=False, allow_nan=False).encode())
    def subscribe(self):
        client = queue.Queue(maxsize=128)
        with self.lock:
            client.put_nowait((1, json.dumps({'reset':self.generation}).encode()))
            # Cached measurements have no new arrival time: only replay the
            # static definition, and wait for genuinely new live samples.
            for kind in (1, 3):
                if kind in self.cache:
                    client.put_nowait((2, self.cache[kind]))
            self.clients.add(client)
        return client
    def unsubscribe(self, client):
        with self.lock:
            self.clients.discard(client)


def exact(stream, size, stop, pause=None):
    output = bytearray()
    while len(output) < size:
        if stop.is_set() or pause is not None and pause.is_set():
            raise EOFError('遥测连接已关闭')
        try:
            part = stream.recv(size-len(output))
        except socket.timeout:
            continue
        if not part:
            raise EOFError('遥测连接已关闭')
        output.extend(part)
    return bytes(output)


def line(stream, stop, limit=262144):
    result = bytearray()
    while len(result) < limit:
        result.extend(exact(stream, 1, stop))
        if result[-1] == 10:
            return bytes(result)
    raise ValueError('IPC 消息超出上限')


def raw_loop(target, config, emit, stop, system_log=None, connection_pause=None):
    from socket_transport import open_remote_socket
    hub = config['hub']
    generation = hub.generation
    def tof_loop():
        refreshed = False
        while not stop.is_set():
            if connection_pause is not None and connection_pause.is_set():
                stop.wait(.2)
                continue
            try:
                with open_remote_socket(target, config['tofd_socket'], system_log, stop=stop) as stream:
                    stream.settimeout(.5)
                    stream.sendall(b'{"jsonrpc":"2.0","id":1,"method":"tof.stream","params":{}}\n')
                    # A buffered reader preserves a partial line across socket
                    # timeouts; recv chunks avoid one syscall for every pixel byte.
                    pending = bytearray()
                    accepted = False
                    last_receive = time.monotonic()
                    while not stop.is_set() and not (connection_pause and connection_pause.is_set()):
                        try: chunk = stream.recv(65536)
                        except socket.timeout:
                            if not refreshed and time.monotonic() - last_receive >= TOF_IDLE_SECONDS:
                                if not accepted: raise TimeoutError('测距订阅未收到回执')
                                # tofd publishes availability in its acknowledgement.
                                # Refresh once per quiet period, since a frame-less
                                # server only retires old subscribers on its next frame.
                                refreshed = True
                                break
                            continue
                        if not chunk: raise EOFError('测距连接已关闭')
                        last_receive = time.monotonic()
                        pending.extend(chunk)
                        while b'\n' in pending:
                            raw, _, tail = pending.partition(b'\n')
                            pending = bytearray(tail)
                            if len(raw) + 1 > 262144: raise ValueError('测距帧过长')
                            message = json_object(raw)
                            event = None
                            if message.get('id') == 1:
                                result = message.get('result')
                                if not isinstance(result, dict) or not result.get('accepted'):
                                    raise ValueError(str(message.get('error') or '测距订阅未接受'))
                                accepted = True
                                event = {'channel':'tof', 'data':{'subscription':result}}
                            elif message.get('method') == 'tof.frame' and isinstance(message.get('params'), dict):
                                refreshed = False
                                event = {'channel':'tof', 'data':message['params']}
                            if event:
                                emit(event)
                                payload = b'\x03' + raw + b'\n'
                                hub.raw(struct.pack('<I', len(payload)) + payload, generation, metadata=message.get('id') == 1)
                        if len(pending) > 262144: raise ValueError('测距帧过长')
            except (ValueError, OSError, EOFError, SSHConnectError) as exc:
                if not stop.is_set():
                    event = {'channel':'tof', 'error':str(exc)}
                    emit(event); hub.event(event, generation)
            stop.wait(2)
    worker = threading.Thread(target=tof_loop, daemon=True)
    worker.start()
    try:
        while not stop.is_set():
            if connection_pause is not None and connection_pause.is_set():
                stop.wait(.2)
                continue
            try:
                with open_remote_socket(target, config['robotd_socket'], system_log, stop=stop) as stream:
                    stream.settimeout(.5)
                    stream.sendall(b'{"jsonrpc":"2.0","id":1,"method":"robot.rawSubscribe","params":{}}\n')
                    response = json_object(line(stream, stop))
                    result = response.get('result')
                    if not isinstance(result, dict): result = {}
                    if response.get('id') != 1 or response.get('error') or result.get('accepted') is not True or result.get('schema') != 'r17.raw.v1' or result.get('framing') != 'u32le':
                        raise ValueError('固件未提供 R17 原始遥测流，请安装同版固件')
                    mirror = Mirror(emit)
                    while not stop.is_set() and not (connection_pause and connection_pause.is_set()):
                        header = exact(stream, 4, stop, connection_pause)
                        size = struct.unpack('<I', header)[0]
                        if not 1 < size <= MAX_FRAME: raise ValueError('原始遥测帧长度无效')
                        frame = header + exact(stream, size, stop, connection_pause)
                        mirror.accept(frame)
                        hub.raw(frame, generation)
            except (ValueError, OSError, EOFError, SSHConnectError) as exc:
                if not stop.is_set() and not (connection_pause is not None and connection_pause.is_set()):
                    if system_log: system_log.add('原始遥测', str(exc))
                    for channel in TTL:
                        if channel == 'tof': continue
                        event = {'channel':channel, 'error':str(exc)}
                        emit(event); hub.event(event, generation)
            stop.wait(2)
    finally:
        worker.join(timeout=1)


def send_frame(writer, opcode, payload):
    size = len(payload)
    header = bytes((128|opcode, size)) if size < 126 else bytes((128|opcode, 126)) + struct.pack('!H', size) if size < 65536 else bytes((128|opcode,127)) + struct.pack('!Q', size)
    writer.write(header + payload)
    writer.flush()


def upgrade(handler, config, hub, auxiliary):
    host = handler.headers.get('Host', '')
    protocols = [s.strip() for s in handler.headers.get('Sec-WebSocket-Protocol', '').split(',')]
    auth = next((s[9:] for s in protocols if s.startswith('r17-auth.')), '')
    if handler.headers.get('Origin') != 'http://' + host or not config.get('control_token') or not secrets.compare_digest(auth, config['control_token']):
        return handler.reply({'error':'遥测连接凭据或来源无效'},403)
    try:
        key = handler.headers.get('Sec-WebSocket-Key', '')
        if (handler.headers.get('Upgrade', '').lower() != 'websocket' or 'upgrade' not in [s.strip() for s in handler.headers.get('Connection','').lower().split(',')] or handler.headers.get('Sec-WebSocket-Version') != '13' or PROTOCOL not in protocols or len(base64.b64decode(key, validate=True)) != 16):
            raise ValueError('无效握手')
    except ValueError:
        return handler.reply({'error':'遥测 WebSocket 握手无效'},400)
    handler.protocol_version = 'HTTP/1.1'
    handler.send_response_only(101)
    for key, value in [('Upgrade','websocket'), ('Connection','Upgrade'), ('Sec-WebSocket-Accept',base64.b64encode(hashlib.sha1((key+GUID).encode()).digest()).decode()), ('Sec-WebSocket-Protocol',PROTOCOL)]:
        handler.send_header(key,value)
    handler.end_headers()
    handler.connection.settimeout(2)
    handler.connection.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)
    handler.close_connection = True
    client = hub.subscribe()
    def close_stream():
        try: handler.connection.shutdown(socket.SHUT_RDWR)
        except OSError: pass
    client.close_stream = close_stream
    closed = threading.Event()
    write_lock = threading.Lock()
    def send(opcode,payload):
        with write_lock: send_frame(handler.wfile,opcode,payload)
    def receive():
        from control_socket import read_frame
        try:
            while not closed.is_set():
                fin, opcode, payload = read_frame(handler.rfile)
                if opcode == 8:
                    send(8,payload); break
                if opcode == 9: send(10,payload)
                elif opcode != 10: raise ValueError('遥测连接只接收服务器数据')
        except (EOFError, OSError, ValueError):
            pass
        finally: closed.set()
    # Buffered readers must not time out in the middle of a frame. A full
    # bounded queue shuts down a slow socket, waking both reader and writer.
    handler.connection.settimeout(None)
    threading.Thread(target=receive,daemon=True).start()
    next_aux = time.monotonic() + .1
    try:
        while not closed.is_set():
            now = time.monotonic()
            if now >= next_aux:
                generation = hub.generation
                state = auxiliary()
                if generation == hub.generation:
                    send(1,json.dumps({'aux':state,'generation':generation},ensure_ascii=False,allow_nan=False).encode())
                next_aux = now + .1
            try: entry = client.get(timeout=max(.001,next_aux-time.monotonic()))
            except queue.Empty: continue
            if entry is None: break
            send(*entry)
    except (OSError, ValueError):
        pass
    finally:
        closed.set(); hub.unsubscribe(client)
        try: handler.connection.shutdown(socket.SHUT_RDWR)
        except OSError: pass

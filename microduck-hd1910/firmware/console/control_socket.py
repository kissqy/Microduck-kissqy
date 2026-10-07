"""Persistent browser input channel; existing Controller remains the only dispatcher."""
import base64
import hashlib
import json
import secrets
import socket
import struct
import time

MAX_MESSAGE = 4096
PROTOCOL = 'r17-control'
GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'


class ProtocolError(ValueError):
    pass


def exact(reader, size):
    value = reader.read(size)
    if len(value) != size:
        raise EOFError('手柄连接已关闭')
    return value


def read_frame(reader):
    a, b = exact(reader, 2)
    fin, opcode, size = bool(a & 128), a & 15, b & 127
    if a & 112 or not b & 128 or opcode not in (0, 1, 8, 9, 10):
        raise ProtocolError('无效 WebSocket 帧')
    if size == 126:
        size = struct.unpack('!H', exact(reader, 2))[0]
        if size < 126:
            raise ProtocolError('无效 WebSocket 长度')
    elif size == 127:
        size = struct.unpack('!Q', exact(reader, 8))[0]
        if size < 65536:
            raise ProtocolError('无效 WebSocket 长度')
    if size > MAX_MESSAGE or opcode >= 8 and (not fin or size > 125):
        raise ProtocolError('手柄消息过长或无效')
    mask = exact(reader, 4)
    payload = exact(reader, size)
    return fin, opcode, bytes(v ^ mask[i % 4] for i, v in enumerate(payload))


def send_frame(writer, opcode, payload):
    size = len(payload)
    header = bytes((128 | opcode, size)) if size < 126 else bytes((128 | opcode, 126)) + struct.pack('!H', size)
    writer.write(header + payload)
    writer.flush()


def upgrade(handler, config, controller):
    """Authenticate once. No query-string credentials, input polling, or action replay."""
    host = handler.headers.get('Host', '')
    token = config.get('control_token', '')
    protocols = [s.strip() for s in handler.headers.get('Sec-WebSocket-Protocol', '').split(',')]
    auth = next((s[len('r17-auth.'):] for s in protocols if s.startswith('r17-auth.')), '')
    if not controller or handler.headers.get('Origin') != 'http://' + host or not token or not secrets.compare_digest(auth, token):
        return handler.reply({'error': '手柄连接凭据或来源无效'}, 403)
    try:
        key = handler.headers.get('Sec-WebSocket-Key', '')
        if (handler.headers.get('Upgrade', '').lower() != 'websocket'
                or 'upgrade' not in [s.strip() for s in handler.headers.get('Connection', '').lower().split(',')]
                or handler.headers.get('Sec-WebSocket-Version') != '13'
                or PROTOCOL not in protocols or len(base64.b64decode(key, validate=True)) != 16):
            raise ProtocolError('无效 WebSocket 握手')
    except ValueError:
        return handler.reply({'error': '手柄长连接握手无效'}, 400)
    handler.protocol_version = 'HTTP/1.1'
    handler.send_response_only(101)
    handler.send_header('Upgrade', 'websocket')
    handler.send_header('Connection', 'Upgrade')
    handler.send_header('Sec-WebSocket-Accept', base64.b64encode(hashlib.sha1((key + GUID).encode('ascii')).digest()).decode('ascii'))
    handler.send_header('Sec-WebSocket-Protocol', PROTOCOL)
    handler.end_headers()
    handler.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    handler.connection.settimeout(None)
    handler.close_connection = True
    owner = None
    transport = controller.transport
    chunks = None
    log = getattr(controller, 'log', None) or getattr(controller.transport, 'log', None)
    if log:
        log.add('手柄长连接', '网页 WebSocket 已连接；Zero 输入接口只在操作时连接，无空闲动作轮询')
    try:
        while True:
            fin, opcode, payload = read_frame(handler.rfile)
            if opcode == 8:
                send_frame(handler.wfile, 8, payload)
                break
            if opcode == 9:
                send_frame(handler.wfile, 10, payload)
                continue
            if opcode == 10:
                continue
            if opcode == 1:
                if chunks is not None:
                    raise ProtocolError('消息分片顺序无效')
                chunks = bytearray(payload)
            elif chunks is None:
                raise ProtocolError('消息分片顺序无效')
            else:
                chunks.extend(payload)
            if len(chunks) > MAX_MESSAGE:
                raise ProtocolError('手柄消息过长')
            if not fin:
                continue
            started = time.monotonic()
            row = json.loads(chunks.decode('utf-8'))
            chunks = None
            if not isinstance(row, dict) or set(row) != {'id', 'payload'} or type(row['id']) is not int or not 0 < row['id'] < 2**53:
                raise ProtocolError('无效手柄消息')
            command = row['payload']
            if controller.transport is not transport:
                raise ProtocolError('SSH 地址已更换，请重新建立手柄连接')
            if not isinstance(command, dict) or command.get('action') not in ('webpad_state', 'webpad_close'):
                raise ProtocolError('长连接仅处理手柄输入')
            if owner is not None and command.get('client') != owner:
                raise ProtocolError('手柄来源发生变化')
            try:
                result = controller.handle(command)
                if command['action'] == 'webpad_state':
                    owner = command['client']
                answer = {'id': row['id'], 'result': result, 'elapsed_ms': round((time.monotonic() - started) * 1000, 1)}
            except Exception as exc:
                answer = {'id': row['id'], 'error': str(exc) or type(exc).__name__, 'status': getattr(exc, 'status', 503)}
            send_frame(handler.wfile, 1, json.dumps(answer, ensure_ascii=False).encode('utf-8'))
    except (EOFError, OSError):
        pass
    except (ValueError, UnicodeError) as exc:
        if log:
            log.add('手柄长连接错误', str(exc))
        try:
            send_frame(handler.wfile, 8, struct.pack('!H', 1002))
        except OSError:
            pass
    finally:
        if owner is not None and controller.transport is transport:
            controller.release_owner(owner)
        if log:
            log.add('手柄长连接', '连接已关闭，撤销该网页的输入；动作不重发')

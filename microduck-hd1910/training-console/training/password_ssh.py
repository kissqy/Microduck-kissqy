"""Password SSH connection and loopback forwards; credentials stay in memory."""
import base64
import hashlib
import importlib
import io
from pathlib import Path
import socket
import socketserver
import subprocess
import sys
import threading
import time

_INSTALL_LOCK = threading.Lock()


def dependency(directory, report):
    with _INSTALL_LOCK:
        try:
            return importlib.import_module('paramiko')
        except ImportError:
            pass
        target = directory / 'ssh-password-client' / ('python-%d.%d' % sys.version_info[:2])
        if target.is_dir() and str(target) not in sys.path:
            sys.path.insert(0, str(target))
            importlib.invalidate_caches()
            try:
                return importlib.import_module('paramiko')
            except ImportError:
                pass
        report('首次使用密码登录，正在准备SSH客户端组件…')
        target.mkdir(parents=True, exist_ok=True)
        result = subprocess.run([sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check',
                                 '--no-input', '--target', str(target), '--upgrade', 'paramiko==4.0.0'],
                                cwd=directory, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=240,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode:
            raise ValueError('密码SSH组件安装失败；请确认本机Python有pip并能下载软件包。')
        if str(target) not in sys.path:
            sys.path.insert(0, str(target))
        importlib.invalidate_caches()
        return importlib.import_module('paramiko')


class UnknownHostKey(ValueError):
    def __init__(self, hostname, key):
        self.details = {'hostname': hostname, 'key_type': key.get_name(), 'key': key.get_base64(),
                        'fingerprint': 'SHA256:' + base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')}
        super().__init__('首次连接：请核对页面显示的服务器SSH指纹，然后点击确认并继续。')


class PasswordClient:
    def __init__(self, directory, connection, password, report):
        self.report = report
        paramiko = dependency(directory, report)
        self.client = paramiko.SSHClient()
        self.client.load_system_host_keys()
        host_file = directory / 'password_ssh_known_hosts'
        if host_file.is_file():
            self.client.load_host_keys(str(host_file))
        if connection.get('known_hosts'):
            self.client.load_host_keys(connection['known_hosts'])
        class Policy(paramiko.MissingHostKeyPolicy):
            def missing_host_key(self, client, hostname, key):
                raise UnknownHostKey(hostname, key)
        self.client.set_missing_host_key_policy(Policy())
        report('正在通过密码登录SSH服务器…')
        try:
            self.client.connect(connection['host'], port=connection['port'], username=connection['user'],
                                password=password, allow_agent=False, look_for_keys=False,
                                timeout=15, auth_timeout=20, banner_timeout=20)
            self.transport = self.client.get_transport()
            self.transport.set_keepalive(15)
        except Exception as error:
            self.client.close()
            if isinstance(error, paramiko.AuthenticationException):
                raise ValueError('SSH密码登录失败，请检查用户名、密码及服务器密码登录权限。') from None
            if isinstance(error, paramiko.BadHostKeyException):
                raise ValueError('服务器SSH指纹发生变化；已拒绝连接，请核对服务器身份。') from None
            raise

    def execute(self, command, packed=b'', timeout=480):
        channel = self.transport.open_session(timeout=20)
        channel.settimeout(30)
        errors = []
        try:
            channel.exec_command(command)
            def upload():
                try:
                    if packed:
                        channel.sendall(packed)
                    channel.shutdown_write()
                except Exception as error:
                    errors.append(error)
            writer = threading.Thread(target=upload, daemon=True)
            writer.start()
            output, diagnostics = io.BytesIO(), io.BytesIO()
            progress_buffer = bytearray()
            deadline = time.monotonic() + timeout
            while True:
                if channel.recv_ready():
                    chunk = channel.recv(65536)
                    output.write(chunk)
                    progress_buffer.extend(chunk)
                    while b'\n' in progress_buffer:
                        line, _, remainder = progress_buffer.partition(b'\n')
                        progress_buffer = bytearray(remainder)
                        if line.startswith(b'MICRODUCK_SETUP '):
                            self.report(line[len(b'MICRODUCK_SETUP '):].decode('utf-8', errors='replace'))

                if channel.recv_stderr_ready():
                    diagnostics.write(channel.recv_stderr(65536))
                if output.tell() + diagnostics.tell() > 16 * 1024 * 1024:
                    raise ValueError('SSH部署输出超出上限。')
                if errors:
                    raise ValueError('SSH上传中断；未自动重试，请重新连接。')
                if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
                    return subprocess.CompletedProcess('SSH backend', channel.recv_exit_status(), output.getvalue(), diagnostics.getvalue())
                if not self.transport.is_active():
                    raise ValueError('SSH连接中断，请重新连接。')
                if time.monotonic() >= deadline:
                    raise ValueError('SSH操作超时；后台服务状态需重连确认。')
                time.sleep(.01)
        finally:
            channel.close()
            if 'writer' in locals():
                writer.join(timeout=2)

    def forward(self, port):
        return Tunnel(self.transport, port)

    def close(self):
        self.client.close()


class Tunnel:
    """Process-shaped lifecycle for existing RemoteTraining tunnel management."""
    def __init__(self, transport, remote_port):
        self.transport, self.stopped = transport, threading.Event()
        owner = self
        class Server(socketserver.ThreadingTCPServer):
            daemon_threads = True
            allow_reuse_address = True
            def handle_error(self, request, client_address):
                pass
        class Relay(socketserver.BaseRequestHandler):
            def handle(self):
                channel = None
                finished = threading.Event()
                peer = self.request
                try:
                    channel = transport.open_channel('direct-tcpip', ('127.0.0.1', remote_port), self.client_address, timeout=15)
                    peer.settimeout(30)
                    channel.settimeout(30)
                    def upload():
                        try:
                            while not finished.is_set() and not owner.stopped.is_set():
                                try:
                                    data = peer.recv(65536)
                                except socket.timeout:
                                    continue
                                if not data:
                                    channel.shutdown_write()
                                    return
                                channel.sendall(data)
                        except Exception:
                            finished.set()
                    upstream = threading.Thread(target=upload, daemon=True)
                    upstream.start()
                    while not finished.is_set() and not owner.stopped.is_set():
                        if not channel.recv_ready():
                            if channel.closed or channel.eof_received or not transport.is_active():
                                break
                            finished.wait(.05)
                            continue
                        data = channel.recv(65536)
                        if not data:
                            break
                        peer.sendall(data)
                except Exception:
                    pass
                finally:
                    finished.set()
                    if channel:
                        channel.close()
                    try:
                        peer.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
        self.server = Server(('127.0.0.1', 0), Relay)
        self.local_port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .1}, daemon=True)
        self.thread.start()

    def poll(self):
        return 0 if self.stopped.is_set() else None if self.transport.is_active() else 255

    def terminate(self):
        if not self.stopped.is_set():
            self.stopped.set()
            self.server.shutdown()
            self.server.server_close()

    def wait(self, timeout=None):
        self.thread.join(timeout)
        if self.thread.is_alive():
            raise subprocess.TimeoutExpired('SSH forward', timeout)
        return 0

    kill = terminate


def trust_host(directory, details):
    paramiko = dependency(directory, lambda message: None)
    path = directory / 'password_ssh_known_hosts'
    keys = paramiko.HostKeys(str(path)) if path.is_file() else paramiko.HostKeys()
    data = base64.b64decode(details['key'])
    entry = paramiko.hostkeys.HostKeyEntry.from_line(details['hostname'] + ' ' + details['key_type'] + ' ' + details['key'])
    if not entry or entry.key is None:
        raise ValueError('服务器主机公钥无效。')
    existing = keys.lookup(details['hostname'])
    if existing and details['key_type'] in existing and existing[details['key_type']].asbytes() != data:
        raise ValueError('服务器指纹与已保存记录冲突，未覆盖。')
    keys.add(details['hostname'], details['key_type'], entry.key)
    directory.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    keys.save(str(temporary))
    temporary.chmod(0o600)
    temporary.replace(path)

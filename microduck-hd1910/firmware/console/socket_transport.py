"""Authenticated byte transport to a robot Unix socket; no remote interpreter.

An OpenSSH local forward is shared while streams to the same endpoint exist.
Only opening a stream connects the remote socket: reserving the local listener
must not wake a socket-activated input adapter or send a robot command.
"""
import contextlib
import re
import socket
import subprocess
import threading
import time

from ssh_connect import normalize_target, ssh_command, ssh_process_options, SSHConnectError

_registry = {}
_registry_lock = threading.RLock()


def _path(value):
    if (not isinstance(value, str) or not value.startswith('/')
            or len(value.encode('utf-8')) > 103 or any(c in value for c in '\r\n\0:')):
        raise ValueError('远端接口须为有效的 Unix socket 绝对路径')
    return value


def forward_command(target, remote_path, port):
    """Keep the destination last; never turn a socket path into a shell command."""
    original = ssh_command(target)
    return [*original[:-1], '-N', '-o', 'ExitOnForwardFailure=yes',
            '-o', 'LogLevel=DEBUG1', '-L', f'127.0.0.1:{port}:{_path(remote_path)}', original[-1]]


class _Forward:
    def __init__(self, target, path, log):
        self.target, self.path, self.log = target, path, log
        self.refs = 0
        self.process = None
        self.port = None
        self.ready = threading.Event()
        self.start_lock = threading.Lock()
        self.thread = None
        self.errors = []
        self.started = False
        self.listening = False
        self.closed = False
        self.start_error = None

    def start(self):
        with self.start_lock:
            if self.started:
                return
            if self.closed:
                raise ConnectionAbortedError('SSH 字节通道已关闭')
            self.started = True
            try:
                # OpenSSH does not allocate an ephemeral -L port. A collision
                # after releasing this reservation fails startup; it is never
                # treated as a successful connection to an unrelated listener.
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
                    reservation.bind(('127.0.0.1', 0))
                    self.port = reservation.getsockname()[1]
                self.process = subprocess.Popen(
                    forward_command(self.target, self.path, self.port),
                    **ssh_process_options(self.target), stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, bufsize=0)
                self.thread = threading.Thread(target=self._stderr, daemon=True)
                self.thread.start()
                if self.log:
                    self.log.add('SSH 字节通道', f'连接 {self.target} → {self.path}；不启动远端采集程序')
            except Exception as exc:
                self.start_error = exc
                self.ready.set()

    def _stderr(self):
        expected = f'Local forwarding listening on 127.0.0.1 port {self.port}.'
        attempted = False
        try:
            for raw in self.process.stderr:
                line = raw.decode('utf-8', errors='replace').strip()
                if expected in line:
                    attempted = True
                # OpenSSH prints the port line *before* bind/listen. The
                # client loop starts only after forward setup has succeeded
                # (ExitOnForwardFailure=yes); waiting for both prevents a
                # port collision from connecting us to somebody else's socket.
                if attempted and line == 'debug1: Entering interactive session.':
                    self.listening = True
                    self.ready.set()
                # Debug output is only a readiness signal. Do not put every
                # key exchange, identity path or forwarded frame in the log.
                if line and not re.match(r'^debug[123]:', line):
                    self.errors.append(line[:1000])
                    del self.errors[:-8]
        except (OSError, ValueError):
            pass
        finally:
            self.ready.set()

    def open(self, timeout, stop):
        self.start()
        deadline = time.monotonic() + timeout
        while not self.ready.wait(.05):
            self._check(deadline, stop)
        self._check(deadline, stop)
        if self.start_error is not None:
            raise SSHConnectError(str(self.start_error)) from self.start_error
        if not self.listening:
            raise SSHConnectError('SSH 未建立本地转发：' + (' / '.join(self.errors) or self.path))
        self._check(deadline, stop)
        stream = socket.create_connection(('127.0.0.1', self.port),
                                          timeout=max(.01, deadline-time.monotonic()))
        try:
            self._check(deadline, stop)
            stream.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            stream.settimeout(None)
            return stream
        except Exception:
            stream.close()
            raise

    def _check(self, deadline, stop):
        if stop is not None and stop.is_set():
            raise ConnectionAbortedError('接口连接已取消')
        if self.closed:
            raise ConnectionAbortedError('SSH 字节通道已关闭')
        if self.start_error is not None:
            raise SSHConnectError(str(self.start_error)) from self.start_error
        if self.process is not None and self.process.poll() is not None:
            raise SSHConnectError('SSH 接口转发失败：' + (' / '.join(self.errors) or
                                                       f'退出码 {self.process.returncode}'))
        if time.monotonic() >= deadline:
            raise TimeoutError('SSH 接口连接超时：' + (' / '.join(self.errors) or self.path))

    def close(self):
        with self.start_lock:
            if self.closed:
                return
            self.closed = True
            process = self.process
            self.ready.set()
        if process is not None:
            if process.poll() is None:
                with contextlib.suppress(OSError):
                    process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                with contextlib.suppress(OSError):
                    process.kill()
                with contextlib.suppress(subprocess.TimeoutExpired, OSError):
                    process.wait(timeout=1)
            if process.stderr is not None:
                with contextlib.suppress(OSError, ValueError):
                    process.stderr.close()
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(timeout=.2)
        if self.log and process is not None:
            self.log.add('SSH 字节通道', f'{self.path} 最后一个连接已关闭')


def _release(forward):
    close = False
    with _registry_lock:
        forward.refs -= 1
        if forward.refs == 0:
            key = (forward.target, forward.path)
            if _registry.get(key) is forward:
                del _registry[key]
            close = True
    if close:
        forward.close()


class RemoteSocket:
    """A socket with endpoint ownership. Closing a stream never closes its peers."""
    def __init__(self, stream, forward=None):
        self.socket, self.forward = stream, forward
        self.closed = False
        self._close_lock = threading.Lock()

    @property
    def process(self):
        return self.forward.process if self.forward else None

    def __getattr__(self, name):
        return getattr(self.socket, name)

    def close(self):
        with self._close_lock:
            if self.closed:
                return
            self.closed = True
        # Wake a reader blocked in makefile().read() before retiring the SSH
        # child. The caller still owns and closes any file objects it made.
        with contextlib.suppress(OSError, ValueError):
            self.socket.shutdown(socket.SHUT_RDWR)
        self.socket.close()
        if self.forward is not None:
            _release(self.forward)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def open_remote_socket(target, remote_path, system_log=None, timeout=10, stop=None):
    """Connect once, without sending a payload or retrying an uncertain action."""
    path = _path(remote_path)
    if not isinstance(timeout, (int, float)) or not 0 < timeout <= 60:
        raise ValueError('接口连接超时须为 0～60 秒')
    if stop is not None and stop.is_set():
        raise ConnectionAbortedError('接口连接已取消')
    if not target:
        stream = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            stream.settimeout(timeout)
            stream.connect(path)
            stream.settimeout(None)
            return RemoteSocket(stream)
        except Exception:
            stream.close()
            raise
    target = normalize_target(target)
    key = (target, path)
    with _registry_lock:
        forward = _registry.get(key)
        if forward is None or forward.closed or (forward.process is not None
                                                and forward.process.poll() is not None):
            forward = _Forward(target, path, system_log)
            _registry[key] = forward
        forward.refs += 1
    try:
        return RemoteSocket(forward.open(timeout, stop), forward)
    except Exception:
        _release(forward)
        raise

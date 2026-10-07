"""Reuse one private Linux/WSL stdio connection; isolate each job in a child."""
import base64
import io
import json
import queue
import secrets
import subprocess
import threading
from pathlib import Path


class _Output(io.RawIOBase):
    def __init__(self):
        super().__init__()
        self.items = queue.Queue()
        self.pending = bytearray()
        self.eof = False

    def readable(self): return True

    def readinto(self, target):
        while not self.pending and not self.eof:
            data = self.items.get()
            if data is None: self.eof = True
            else: self.pending.extend(data)
        size = min(len(target), len(self.pending))
        target[:size] = self.pending[:size]
        del self.pending[:size]
        return size


class _Input:
    def __init__(self, job):
        self.job, self.closed = job, False

    def write(self, data):
        if self.closed or self.job.poll() is not None: raise BrokenPipeError('任务输入已关闭。')
        self.job.session.send({'op':'input', 'id':self.job.key, 'data':base64.b64encode(data).decode('ascii')})
        return len(data)

    def flush(self): pass

    def close(self):
        if self.closed: return
        self.closed = True
        if self.job.poll() is None:
            self.job.session.send({'op':'eof', 'id':self.job.key})


class SessionProcess:
    def __init__(self, session, key):
        self.session, self.key = session, key
        self.returncode = None
        self.done = threading.Event()
        self.output = _Output()
        self.stdout = io.BufferedReader(self.output)
        self.stdin = _Input(self)

    def poll(self): return self.returncode

    def wait(self, timeout=None):
        if not self.done.wait(timeout): raise subprocess.TimeoutExpired('training session job', timeout)
        return self.returncode

    def kill(self):
        if self.poll() is None: self.session.send({'op':'kill', 'id':self.key})

    def finish(self, code, error=None):
        if self.done.is_set(): return
        if error: self.output.items.put((error+'\n').encode('utf-8'))
        self.returncode = code
        self.output.items.put(None)
        self.done.set()


class PersistentSession:
    def __init__(self, profile, command_factory):
        self.jobs = {}
        self.lock = threading.RLock()
        self.write_lock = threading.Lock()
        self.ready = threading.Event()
        self.alive = True
        self.pid = None
        self.diagnostics = []
        source = Path(__file__).with_name('session_agent.py').read_bytes()
        self.proc = subprocess.Popen(command_factory(profile, len(source)), stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        threading.Thread(target=self._read, daemon=True).start()
        try:
            self.proc.stdin.write(source)
            self.proc.stdin.flush()
            if not self.ready.wait(30) or not self.alive:
                raise OSError('无法建立训练执行通道。'+''.join(self.diagnostics)[-1000:])
        except Exception:
            self.close()
            raise

    def _read(self):
        try:
            for raw in self.proc.stdout:
                try: message = json.loads(raw)
                except (ValueError, UnicodeError):
                    self.diagnostics = (self.diagnostics+[raw.decode('utf-8', errors='replace')])[-10:]
                    continue
                if message.get('type') == 'ready':
                    self.pid = message['pid'];self.ready.set();continue
                with self.lock: job = self.jobs.get(message.get('id'))
                if not job: continue
                kind = message.get('type')
                if kind == 'data': job.output.items.put(base64.b64decode(message['data']))
                elif kind in ('exit','error'):
                    job.finish(message.get('code',1),message.get('message'))
                    with self.lock: self.jobs.pop(job.key,None)
        except (OSError, ValueError, TypeError):
            pass
        finally:
            with self.lock:
                self.alive = False
                for job in self.jobs.values():
                    job.finish(255,'训练执行连接已断开；任务未自动重试，请查看运行日志。')
                self.jobs.clear()
            self.ready.set()
            self.proc.stdout.close()

    def send(self, message):
        with self.write_lock:
            if not self.alive or self.proc.poll() is not None: raise BrokenPipeError('训练执行连接已断开。')
            try:
                self.proc.stdin.write((json.dumps(message,separators=(',',':'))+'\n').encode('utf-8'))
                self.proc.stdin.flush()
            except (OSError, ValueError):
                raise BrokenPipeError('训练执行连接已断开。') from None

    def start(self, code):
        job = SessionProcess(self, secrets.token_hex(12))
        with self.lock:
            if not self.alive: raise BrokenPipeError('训练执行连接已断开。')
            self.jobs[job.key] = job
        try: self.send({'op':'start','id':job.key,'code':base64.b64encode(code).decode('ascii')})
        except Exception:
            with self.lock: self.jobs.pop(job.key,None)
            job.finish(255)
            raise
        return job

    def close(self):
        try: self.send({'op':'shutdown'})
        except (OSError, ValueError): pass
        try: self.proc.stdin.close()
        except (OSError, ValueError): pass
        try: self.proc.wait(timeout=18)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=3)
        self.alive = False


class SessionPool:
    def __init__(self, command_factory):
        self.command_factory = command_factory
        self.lock = threading.Lock()
        self.sessions = {}
        self.closed = False

    def start(self, profile, code, channel="jobs"):
        # Repository/task/model changes reuse a session within each lane.
        # A viewer transport failure must not close the training connection.
        key = (profile['mode'],profile.get('distro') if profile['mode']=='wsl' else '',channel)
        with self.lock:
            if self.closed: raise OSError('训练台正在退出。')
            session = self.sessions.get(key)
            if not session or not session.alive or session.proc.poll() is not None:
                if session: session.close()
                session = self.sessions[key] = PersistentSession(profile,self.command_factory)
            # Do not replay a command after a lost acknowledgement, especially deletion.
            return session.start(code)

    def run(self, profile, code, data=b'', timeout=120):
        proc = self.start(profile,code)
        chunks = []
        reader = threading.Thread(target=lambda: chunks.append(proc.stdout.read()),daemon=True)
        reader.start()
        try:
            if data: proc.stdin.write(data)
            proc.stdin.close()
            code = proc.wait(timeout)
            reader.join(timeout=3)
            if reader.is_alive(): raise OSError('模型数据接收未完成。')
            return subprocess.CompletedProcess('persistent training session',code,b''.join(chunks),b'')
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
            raise
        finally:
            try: proc.stdin.close()
            except (OSError, ValueError): pass
            reader.join(timeout=3)
            if not reader.is_alive(): proc.stdout.close()

    def close(self):
        with self.lock:
            self.closed = True
            sessions = list(self.sessions.values())
            self.sessions.clear()
        for session in sessions: session.close()

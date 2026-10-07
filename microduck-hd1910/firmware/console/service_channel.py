"""Concurrent requests over one warm SSH process; actions are never replayed."""
import json
from pathlib import Path
import queue
import shlex
import subprocess
import sys
import threading

from ssh_connect import ssh_command, ssh_process_options
from process_lifecycle import retire_process


class ServiceChannel:
    def __init__(self, target, socket_path, system_log=None):
        self.target, self.path = target, socket_path
        self.log = system_log
        self.lock = threading.RLock()
        self.pending = {}
        self.proc = None
        self.reader = None
        self.counter = 0
        self.closed = False

    def warm(self):
        try:
            with self.lock: self._ensure()
        except Exception:
            pass  # The next explicit operation reports connection failures.

    def _ensure(self):
        if self.closed: raise RuntimeError('服务连接已关闭')
        if self.proc is not None and self.proc.poll() is None and self.reader is not None and self.reader.is_alive(): return
        if self.proc is not None:
            retire_process(self.proc)
            self.proc = None
        source = Path(__file__).with_name('service_rpc.py').read_text(encoding='utf-8')
        command = ['python3' if self.target else sys.executable, '-u', '-c', source, self.path, '--stream']
        argv = ssh_command(self.target) + [shlex.join(command)] if self.target else command
        if self.log: self.log.add('服务 SSH',f'建立持久连接 {self.target or '本机'} → service_rpc / {self.path}')
        proc = subprocess.Popen(argv, **ssh_process_options(self.target), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        def drain():
            try:
                for line in proc.stderr:
                    if self.log: self.log.add('服务 SSH / stderr',line.decode(errors='replace'))
            except (OSError,ValueError):pass
            finally: proc.stderr.close()
        threading.Thread(target=drain,daemon=True).start()
        self.proc = proc
        self.reader = threading.Thread(target=self._read, args=(proc,), daemon=True)
        self.reader.start()

    def _read(self, proc):
        try:
            for line in proc.stdout:
                reply = json.loads(line)
                with self.lock:
                    entry = self.pending.get(reply.get('channel_id'))
                if entry and entry[0] is proc:
                    if 'channel_progress' in reply:
                        if entry[2]:
                            try:entry[2](reply['channel_progress'])
                            except Exception as exc:
                                if self.log:self.log.add('服务日志回调错误',str(exc))
                    else:
                        try:entry[1].put_nowait(reply)
                        except queue.Full:pass
        except Exception as exc:
            if self.log:self.log.add('服务 SSH / 响应错误',str(exc))
        finally:
            with self.lock:
                if self.proc is proc:
                    self.proc = None
                    self.reader = None
                for owner, response, progress in self.pending.values():
                    if owner is proc:
                        try: response.put_nowait({'channel_error':'服务连接中断；指令未重发，请检查实际状态'})
                        except queue.Full: pass
            retire_process(proc)

    def request(self, request, timeout, progress=None):
        response = queue.Queue(maxsize=1)
        with self.lock:
            self._ensure()
            self.counter += 1
            ident = self.counter
            self.pending[ident] = (self.proc, response, progress)
            try:
                self.proc.stdin.write((json.dumps({**request, 'channel_id':ident})+'\n').encode())
                self.proc.stdin.flush()
            except Exception:
                self.pending.pop(ident, None)
                failed, self.proc = self.proc, None
                threading.Thread(target=retire_process,args=(failed,),daemon=True).start()
                raise RuntimeError('服务连接写入失败；指令未重发') from None
        try:
            reply = response.get(timeout=timeout)
            if reply.get('channel_error'): raise RuntimeError(reply['channel_error'])
            return reply['payload']
        except queue.Empty:
            raise TimeoutError('服务回执超时；指令未重发，请检查实际状态') from None
        finally:
            with self.lock: self.pending.pop(ident, None)

    def close(self):
        with self.lock:self.closed=True
        self.disconnect()

    def disconnect(self):
        with self.lock:
            proc, self.proc = self.proc, None
            self.reader = None
        retire_process(proc)

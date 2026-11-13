"""One bounded writer per viewer; HTTP requests never wait for pipe I/O."""
import json
import threading
import time
from collections import deque


class ControlChannel:
    def __init__(self, proc, pipe_lock):
        self.proc, self.pipe_lock = proc, pipe_lock
        self.condition = threading.Condition()
        self.pending = deque()
        self.closed = False
        self.error = None
        self.thread = threading.Thread(target=self._write, daemon=True)
        self.thread.start()

    def submit(self, message):
        with self.condition:
            if self.error: raise ValueError(self.error)
            if self.closed: raise ValueError('仿真控制连接已关闭。')
            # A fresh direction or release supersedes all unsent movements.
            # Keep one-shot actions in order; never replay them after a timeout.
            pending = deque(m for m in self.pending if m['action'] != 'move')
            if len(pending) >= 16: raise ValueError('仿真操作过于频繁，请稍后重试。')
            pending.append(message)
            self.pending = pending
            self.condition.notify()

    def close(self):
        with self.condition:
            self.closed = True
            self.pending.clear()
            self.condition.notify_all()

    def _write(self):
        while True:
            with self.condition:
                self.condition.wait_for(lambda: self.closed or self.pending)
                if self.closed: return
                message = self.pending.popleft()
            try:
                with self.pipe_lock:
                    if self.closed or self.proc.poll() is not None: return
                    if message['action'] == 'move' and message['expires_at'] <= time.time():
                        continue
                    self.proc.stdin.write((json.dumps(message)+'\n').encode('utf-8'))
                    self.proc.stdin.flush()
            except (OSError, ValueError):
                with self.condition:
                    self.error = '仿真控制连接已断开。'
                    self.closed = True
                    self.pending.clear()
                return

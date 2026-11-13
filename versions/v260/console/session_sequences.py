"""Bounded replay windows; historical tabs must not exhaust live connections."""
from collections import Counter, OrderedDict
from contextlib import contextmanager
import threading
import time


class SequenceWindow(OrderedDict):
    def __init__(self, limit=128, ttl=300, clock=time.monotonic):
        super().__init__()
        self.limit, self.ttl, self.clock = limit, ttl, clock
        self.seen = {}
        self.retired = OrderedDict()
        self.active = Counter()
        self.lock = threading.RLock()

    @contextmanager
    def protect(self, key):
        with self.lock:
            self.active[key] += 1
        try:
            yield
        finally:
            with self.lock:
                self.active[key] -= 1
                if not self.active[key]:
                    del self.active[key]

    def retire(self, key):
        with self.lock:
            if key in self:
                self.retired[key] = (super().pop(key), self.clock())
                self.seen.pop(key, None)
                self.retired.move_to_end(key)
                while len(self.retired) > max(2048, self.limit * 8):
                    self.retired.popitem(last=False)

    def accept(self, key, seq):
        with self.lock:
            now = self.clock()
            for old in list(self):
                if not self.active[old] and now - self.seen[old] >= self.ttl:
                    self.retire(old)
            for old, (_, at) in list(self.retired.items()):
                if now - at >= self.ttl:
                    self.retired.pop(old)
            previous = max(self.get(key, -1), self.retired.get(key, (-1, 0))[0])
            if seq <= previous:
                raise ValueError('已丢弃重复或过期指令')
            if key not in self and len(self) >= self.limit:
                oldest = next((old for old in self if not self.active[old]), None)
                if oldest is None:
                    raise ValueError('同时执行的页面请求过多，请稍后再试')
                self.retire(oldest)
            self[key] = seq
            self.seen[key] = now
            self.move_to_end(key)
            self.retired.pop(key, None)

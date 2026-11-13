"""An initial attempt plus three retries, ten seconds apart; then manual only."""
import time


class RetryStopped(OSError):
    pass


class ConnectionRetry:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.failures = 0
        self.until = 0
        self.connected_at = None

    @property
    def exhausted(self):return self.failures >= 4

    def connected(self):
        if self.connected_at is None:self.connected_at = self.clock()

    def failed(self):
        now = self.clock()
        # A flapping login must not buy another three immediate attempts.
        if self.connected_at is not None and now - self.connected_at >= 30:
            self.failures = 0
        self.connected_at = None
        self.failures += 1
        self.until = now + 10
        return 10

    def remaining(self):return max(0, self.until - self.clock())

    def message(self):
        if self.exhausted:return '自动重试 3 次仍失败，已停止；请点击重连'
        return f'10 秒后自动重试（{self.failures}/3）'

    def check(self):
        if self.exhausted:raise RetryStopped(self.message())
        remaining = self.remaining()
        if remaining:raise RetryStopped(f'等待重试，约 {remaining:.0f} 秒后可连接')

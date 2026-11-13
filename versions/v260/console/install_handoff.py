"""Installation completion wakes existing telemetry readers; no readiness polling."""
import copy
import threading


class InstallHandoff:
    def __init__(self):
        self.condition = threading.Condition()
        self.paused = False
        self.recovery_pending = False
        self.peers = set()
        self.ready_report = None

    def begin(self):
        with self.condition:
            self.paused = True
            self.ready_report = None
            self.recovery_pending = False
            peers = tuple(self.peers)
        for peer in peers:
            peer.close()

    def complete(self, after_install=False, startup_report=None):
        with self.condition:
            self.paused = False
            self.recovery_pending = after_install
            self.ready_report = copy.deepcopy(startup_report)
            self.condition.notify_all()

    def connected(self):
        with self.condition:
            self.recovery_pending = False
            self.ready_report = None

    def failed_attempt(self):
        with self.condition:
            if not self.recovery_pending:return False
            self.recovery_pending = False
            self.paused = True
            return True

    def wake(self):
        with self.condition:
            self.condition.notify_all()

    def wait(self, stop):
        with self.condition:
            while self.paused and not stop.is_set():
                self.condition.wait()
            return not stop.is_set()

    def attach(self, peer):
        with self.condition:
            if not self.paused:
                self.peers.add(peer)
                return True
        peer.close()
        return False

    def detach(self, peer):
        with self.condition:
            self.peers.discard(peer)

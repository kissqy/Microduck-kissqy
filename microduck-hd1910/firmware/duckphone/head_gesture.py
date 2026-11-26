"""Idle head gestures for the duckphone bridge.

The sound director decides *when* the robot is idle; this module only performs
the head movement. It sends frames at 10 Hz so the bridge's 250 ms head watchdog
does not zero the pose mid-gesture, and it gives way to any user input.
"""

from __future__ import annotations

import logging
import threading
import time

LOG = logging.getLogger("duckphone.gesture")

CENTER = (0.0, 0.0, 0.0, 0.0)

# name -> [(duration seconds, (neck, pitch, yaw, roll))]
SEQUENCES = {
    "I1": [(1.2, (0.0, -0.30, 0.0, 0.0))],
    "I2": [
        (0.8, (0.0, -0.18, 0.30, 0.0)),
        (0.8, (0.0, -0.18, -0.30, 0.0)),
    ],
}


class HeadGesture:
    """Run one idle gesture at a time; a new one replaces the old one."""

    def __init__(
        self,
        head,
        *,
        allowed=None,
        clock=time.monotonic,
        hz: float = 10.0,
        sleep=time.sleep,
    ) -> None:
        self._head = head
        self._allowed = allowed or (lambda: True)
        self._clock = clock
        self._interval = 1.0 / hz
        self._sleep = sleep
        self._lock = threading.Lock()
        self._gen = 0
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def run(self, name: str) -> bool:
        if name not in SEQUENCES or not self._allowed():
            return False
        with self._lock:
            self._gen += 1
            gen = self._gen
        thread = threading.Thread(
            target=self._run, args=(name, gen), name=f"duck-gesture-{name}", daemon=True)
        self._thread = thread
        thread.start()
        return True

    def cancel(self) -> None:
        with self._lock:
            self._gen += 1

    def wait(self, timeout: float = 1.0) -> None:
        thread = self._thread
        if thread is not None:
            thread.join(timeout)

    def _current(self, gen: int) -> bool:
        with self._lock:
            return gen == self._gen

    def _run(self, name: str, gen: int) -> None:
        try:
            for duration, pose in SEQUENCES[name]:
                end = self._clock() + duration
                while self._clock() < end:
                    if not self._current(gen) or not self._allowed():
                        return
                    self._head(*pose)
                    self._sleep(self._interval)
            if self._current(gen):
                self._head(*CENTER)
        except Exception as exc:  # robotd offline, head refused, etc.
            LOG.info("空闲头部动作 %s 失败：%s", name, exc)

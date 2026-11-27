"""Scripted head / mouth / body-pose actions for the duckphone bridge.

These are the “preset actions” the phone can play and the library the idle
director picks from. A robotd client can only send intents, so an action is a
short sequence of `robot.head`, `robot.mouth` and `robot.pose` notifications,
refreshed often enough that the bridge's 250 ms head watchdog does not zero
them mid-action. Ending an action also zeroes `robot.move` and deactivates the
body pose, so a cancelled action never leaves a stale intent behind.

The player is deliberately small: one worker thread, one action at a time. Any
user input, stop, takeover, dynamic-sound off or P0 alarm cancels it; the
caller can also cancel explicitly.
"""

from __future__ import annotations

import logging
import math
import threading
import time

LOG = logging.getLogger("duckphone.actions")

CENTER = (0.0, 0.0, 0.0, 0.0)

ACTIONS = {
    "look_up": {
        "label": "抬头",
        "sound": "coo",
        "duration": 1.2,
        "beats": [0.0, 0.7],
        "requires_walk": True,
    },
    "look_around": {
        "label": "左右看",
        "sound": "inquire",
        "duration": 1.6,
        "beats": [0.0, 0.6, 1.2],
        "requires_walk": True,
    },
    "circle": {
        "label": "画圈",
        "sound": "greet",
        "duration": 3.9,
        "beats": [0.0, 0.8, 1.6, 2.4, 3.2],
        "requires_walk": True,
    },
    "quack": {
        "label": "张嘴",
        "sound": "chirp",
        "duration": 2.1,
        # One short chirp per mouth opening.
        "beats": [0.0, 0.7, 1.4],
        "requires_walk": True,
    },
}

IDLE_ACTION_NAMES = tuple(ACTIONS)

# name -> [(duration seconds, (neck, pitch, yaw, roll))]
HEAD_SEQUENCES = {
    "look_up": [(1.2, (0.0, -0.30, 0.0, 0.0))],
    "look_around": [
        (0.8, (0.0, -0.18, 0.30, 0.0)),
        (0.8, (0.0, -0.18, -0.30, 0.0)),
    ],
}

CIRCLE_PERIOD = 1.3
CIRCLE_TURNS = 3
QUACK_CYCLE = 0.7
QUACK_OPEN_S = 0.35


class _Beats:
    """Play the action's sound beats after the first one, from the action thread."""

    def __init__(self, name: str) -> None:
        entry = ACTIONS.get(name, {})
        self._plan = list(entry.get("beats") or [0.0])
        self._tag = entry.get("sound")
        self._index = 1          # beat 0 is played by the caller before `run`

    def tick(self, elapsed: float, play) -> None:
        if play is None or not self._tag:
            return
        while self._index < len(self._plan) and elapsed >= self._plan[self._index]:
            play(self._tag)
            self._index += 1


class ActionPlayer:
    """Run one scripted action at a time.

    ``head`` / ``mouth`` / ``move`` / ``pose`` are the bridge's intent methods;
    ``play_sound`` is called for the remaining beats of the action's sound
    pattern (the first beat is played by the caller, so an idle action only
    starts after robotd accepted its sound). ``allowed`` is checked on every
    frame; when it turns false the action stops and neutralises. ``on_change``
    receives ``(name, idle)`` on start and ``(None, False)`` when the action ends
    or is cancelled.
    """

    def __init__(
        self,
        head,
        mouth,
        move,
        pose,
        *,
        play_sound=None,
        allowed=None,
        on_change=None,
        clock=time.monotonic,
        sleep=time.sleep,
    ) -> None:
        self._head = head
        self._mouth = mouth
        self._move = move
        self._pose = pose
        self._play_sound = play_sound
        self._allowed = allowed or (lambda: True)
        self._on_change = on_change
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._gen = 0
        self._current: str | None = None
        self._idle = False
        self._thread: threading.Thread | None = None

    # ── public ───────────────────────────────────────────────────────────
    def run(self, name: str, *, idle: bool = False) -> tuple[bool, str]:
        """Start an action; returns ``(accepted, reason)``."""
        if name not in ACTIONS:
            return False, f"未知动作：{name}"
        if not self._allowed():
            return False, "机器人未站立或正在移动"
        with self._lock:
            self._gen += 1
            gen = self._gen
            self._current = name
            self._idle = bool(idle)
        # A new action replaces the old one; neutralise the previous frame after
        # invalidating its generation, so a head-only action cannot inherit an
        # open mouth or a body roll.
        self._neutral()
        self._notify(name, bool(idle))
        thread = threading.Thread(
            target=self._run, args=(name, gen), name=f"duck-action-{name}", daemon=True)
        self._thread = thread
        thread.start()
        return True, ""

    def cancel(self, neutral: bool = True) -> None:
        with self._lock:
            had = self._current is not None
            self._gen += 1
            self._current = None
            self._idle = False
        if had:
            self._notify(None, False)
            if neutral:
                self._neutral()

    def wait(self, timeout: float = 1.0) -> None:
        thread = self._thread
        if thread is not None:
            thread.join(timeout)

    def current(self) -> str | None:
        with self._lock:
            return self._current

    def is_idle(self) -> bool:
        with self._lock:
            return self._idle

    # ── worker ───────────────────────────────────────────────────────────
    def _ok(self, gen: int) -> bool:
        with self._lock:
            if gen != self._gen:
                return False
        try:
            return bool(self._allowed())
        except Exception:
            return False

    def _run(self, name: str, gen: int) -> None:
        beats = _Beats(name)
        start = self._clock()
        try:
            if name in HEAD_SEQUENCES:
                self._run_head(name, gen, beats, start)
            elif name == "circle":
                self._run_circle(gen, beats, start)
            elif name == "quack":
                self._run_quack(gen, beats, start)
        except Exception as exc:  # robotd offline, head refused, etc.
            LOG.info("动作 %s 失败：%s", name, exc)
        finally:
            with self._lock:
                current = gen == self._gen
                if current:
                    self._current = None
                    self._idle = False
            if current:
                self._neutral()
                self._notify(None, False)

    def _run_head(self, name: str, gen: int, beats: _Beats, start: float) -> None:
        for duration, pose in HEAD_SEQUENCES[name]:
            end = self._clock() + duration
            while self._clock() < end:
                if not self._ok(gen):
                    return
                self._head(*pose)
                beats.tick(self._clock() - start, self._sound)
                self._sleep(0.1)

    def _run_circle(self, gen: int, beats: _Beats, start: float) -> None:
        total = CIRCLE_PERIOD * CIRCLE_TURNS
        while self._clock() - start < total:
            if not self._ok(gen):
                return
            phase = 2.0 * math.pi * (self._clock() - start) / CIRCLE_PERIOD
            self._head(
                0.0,
                -0.20 + 0.25 * math.cos(phase),
                1.00 * math.sin(phase),
                0.08 * math.sin(phase),
            )
            beats.tick(self._clock() - start, self._sound)
            self._sleep(0.1)

    def _run_quack(self, gen: int, beats: _Beats, start: float) -> None:
        while self._clock() - start < ACTIONS["quack"]["duration"]:
            if not self._ok(gen):
                return
            phase = (self._clock() - start) % QUACK_CYCLE
            self._mouth(0.9 if phase < QUACK_OPEN_S else 0.0)
            beats.tick(self._clock() - start, self._sound)
            self._sleep(0.1)

    # ── intents ──────────────────────────────────────────────────────────
    def _sound(self, tag: str) -> None:
        """Play one beat; a missing voice must not abort the motion."""
        if self._play_sound is None:
            return
        try:
            self._play_sound(tag)
        except Exception as exc:
            LOG.info("动作声音 %s 失败：%s", tag, exc)

    def _neutral(self) -> None:
        try:
            self._head(*CENTER)
            self._mouth(0.0)
            self._move(0.0, 0.0)
            self._pose(0.0, 0.0, 0.0, False)
        except Exception as exc:
            LOG.debug("动作收尾失败：%s", exc)

    def _notify(self, name: str | None, idle: bool) -> None:
        if self._on_change is None:
            return
        try:
            self._on_change(name, idle)
        except Exception:
            LOG.debug("动作状态回调失败", exc_info=True)


def action_sound(name: str) -> str | None:
    entry = ACTIONS.get(name)
    return entry["sound"] if entry else None

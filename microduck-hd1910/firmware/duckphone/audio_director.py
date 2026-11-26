"""Event-driven sounds for the duckphone bridge.

The bridge already receives the 20 Hz robot state and the 1 Hz health, so the
director can decide when a sound is worth playing without touching robotd. It
never plays over a manual button press: manual sounds call :meth:`note_manual`
and the director suppresses its own P1/P2 sounds for a moment.

Priorities are deliberately small integers: 0 is a safety alarm, 2 is an
action acknowledgement, 3 is social/idle. Manual playback is outside this
module and always wins except against P0.
"""

from __future__ import annotations

import copy
import logging
import threading
import time
from dataclasses import dataclass

from audio_settings import DEFAULTS

LOG = logging.getLogger("duckphone.audio")

P0 = 0
P1 = 2
P2 = 3

BASE_POLICIES = {"", "walk", "held", "homing", "limp"}


@dataclass
class _Play:
    tag: str
    trigger: str
    priority: int


class AudioDirector:
    """Turn robot state changes into ``robot.sound`` calls.

    ``play`` is called from one worker thread with a tag; ``enabled`` and
    ``driver_active`` are callables so the director always sees the current
    bridge/session state. ``clock`` is injectable for tests.
    """

    def __init__(
        self,
        play,
        enabled,
        driver_active,
        *,
        settings=None,
        gesture=None,
        cancel_gesture=None,
        clock=time.monotonic,
    ) -> None:
        self._play = play
        self._enabled = enabled
        self._driver_active = driver_active
        self._settings = settings or (lambda: copy.deepcopy(DEFAULTS))
        self._gesture = gesture
        self._cancel_gesture = cancel_gesture
        self._clock = clock

        self._cv = threading.Condition()
        self._pending: _Play | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

        self._last_enabled = False
        self._last_trigger: dict[str, float] = {}
        self._last_play = 0.0
        self._manual_until = 0.0

        self._last_input = clock()
        self._idle_sent = False
        self._idle_next = 0.0
        self._idle_times: list[float] = []

        self._last_policy = ""
        self._fall = False
        self._fall_at = 0.0
        self._fall_clear_at = 0.0
        self._fall_count = 0
        self._fall_next = 0.0
        self._tilt_next = 0.0
        self._batt_low_armed = True
        self._batt_crit = False
        self._batt_next = 0.0
        self._hz_low_since: float | None = None

    # ── lifecycle ────────────────────────────────────────────────────────
    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._worker, name="duckphone-audio", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        with self._cv:
            self._cv.notify_all()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    # ── public hooks ─────────────────────────────────────────────────────
    def note_input(self) -> None:
        """Any drive/head/command/button means the robot is not idle."""
        self._last_input = self._clock()
        self._idle_sent = False
        self._idle_next = 0.0
        # A user input always wins over a cute idle head movement.
        if self._cancel_gesture:
            self._cancel_gesture()

    def note_manual(self) -> None:
        """A manual sound was just requested; give it the floor."""
        now = self._clock()
        self._manual_until = now + self._settings()["advanced"]["manual_hold_s"]
        self.note_input()

    def on_event(self, kind: str, **data) -> None:
        cfg = self._settings()
        if kind == "driver_start":
            self.note_input()
            if cfg["actions"]["takeover"]:
                self._submit("greet", "L2", P1, cooldown=60.0, cfg=cfg)
        elif kind == "driver_end":
            if cfg["actions"]["handback"]:
                self._submit("coo", "L3", P2, cooldown=30.0, cfg=cfg)
        elif kind == "enable":
            self.note_input()
            if cfg["actions"]["enable"]:
                if data.get("on"):
                    self._submit("greet", "A2", P1, cooldown=5.0, cfg=cfg)
                else:
                    self._submit("coo", "A3", P1, cooldown=5.0, cfg=cfg)
        elif kind == "refusal":
            if cfg["actions"]["refusal"]:
                self._submit("inquire", "A8", P1, cooldown=3.0, cfg=cfg)

    def on_state(self, s: dict) -> None:
        now = self._clock()
        cfg = self._settings()
        on = bool(self._enabled())
        if on != self._last_enabled:
            self._last_enabled = on
            if on:
                # Don't greet with an idle sound the instant it is switched on.
                self.note_input()
            else:
                with self._cv:
                    self._pending = None
                if self._cancel_gesture:
                    self._cancel_gesture()
        if not on or s.get("ro"):
            return

        self._check_policy(s, now, cfg)
        policy = str(s.get("pol") or "")
        # A skill deliberately tilts or tumbles the body; that is not a fall.
        # Battery/temperature/bus alarms still run inside `_check_alarms`.
        self._check_alarms(s, now, cfg, in_skill=policy not in BASE_POLICIES and policy != "")
        self._check_idle(s, now, cfg)

    # ── rules ────────────────────────────────────────────────────────────
    def _check_policy(self, s: dict, now: float, cfg: dict) -> None:
        policy = str(s.get("pol") or "")
        prev = self._last_policy
        self._last_policy = policy
        was_skill = prev not in BASE_POLICIES and prev != ""
        is_skill = policy not in BASE_POLICIES and policy != ""
        if is_skill and not was_skill:
            # A skill is user activity; the idle timer starts when it ends.
            self.note_input()
            if cfg["actions"]["skill_start"]:
                self._submit("chirp", "A4", P1, cooldown=2.0, cfg=cfg)
        elif was_skill and not is_skill:
            self.note_input()
            if cfg["actions"]["skill_end"]:
                self._submit("coo", "A5", P2, cooldown=2.0, cfg=cfg)

    def _check_alarms(self, s: dict, now: float, cfg: dict, *, in_skill: bool = False) -> None:
        tilt = float(s.get("tilt") or 0.0)
        fall = bool(s.get("fall"))
        alerts = cfg["alerts"]
        fall_cfg = cfg["fall"]
        tilt_cfg = cfg["tilt"]

        if in_skill:
            # Do not latch or repeat fall/tilt while a skill runs. If the body is
            # still down after the skill ends, the next non-skill frame raises E1.
            self._fall_clear_at = 0.0
        elif alerts["fall"] and fall:
            self._fall_clear_at = 0.0
            if not self._fall:
                self._fall = True
                self._fall_at = now
                self._fall_count = 1
                self._fall_next = now + fall_cfg["repeat_s"]
                self._submit("alarm", "E1", P0, cooldown=0.0, cfg=cfg)
            elif now >= self._fall_next:
                self._submit("alarm", "E1", P0, cooldown=0.0, cfg=cfg)
                self._fall_count += 1
                self._fall_next = now + (
                    fall_cfg["repeat_s"] if self._fall_count < fall_cfg["max_repeats"]
                    else fall_cfg["tail_s"])
        elif alerts["fall"] and self._fall:
            # Fall detection flickers while the body is rolling or being pushed.
            # Require two quiet seconds before restarting the repeat cadence.
            if self._fall_clear_at == 0.0:
                self._fall_clear_at = now
            elif now - self._fall_clear_at >= 2.0:
                self._fall = False
                self._fall_clear_at = 0.0
                if now - self._fall_at >= 3.0:
                    self._submit("coo", "E9", P2, cooldown=10.0, cfg=cfg)

        # `_tilt_next` is a cooldown, not a latch reset: a brief dip below the
        # threshold must not let the next frame alarm again.
        if (alerts["tilt"] and not in_skill and not fall
                and tilt >= tilt_cfg["deg"] and now >= self._tilt_next):
            self._submit("alarm", "E2", P0, cooldown=0.0, cfg=cfg)
            self._tilt_next = now + tilt_cfg["repeat_s"]

        advanced = cfg["advanced"]
        bat = s.get("bat")
        pct = None
        if isinstance(bat, (list, tuple)) and len(bat) >= 2:
            try:
                pct = float(bat[1])
            except (TypeError, ValueError):
                pct = None
        if alerts["battery"] and pct is not None:
            low = advanced["battery_low_pct"]
            crit = advanced["battery_critical_pct"]
            if pct < crit:
                if not self._batt_crit:
                    self._batt_crit = True
                    self._batt_next = now + 60.0
                    self._submit("alarm", "E4", P0, cooldown=0.0, cfg=cfg)
                elif now >= self._batt_next:
                    self._batt_next = now + 60.0
                    self._submit("alarm", "E4", P0, cooldown=0.0, cfg=cfg)
            else:
                if pct >= crit + 3.0:
                    self._batt_crit = False
                if pct < low and self._batt_low_armed:
                    self._batt_low_armed = False
                    self._submit("inquire", "E3", P1, cooldown=600.0, cfg=cfg)
                elif pct >= low + 3.0:
                    self._batt_low_armed = True

        temp = s.get("temp")
        if alerts["motor"] and isinstance(temp, (int, float)):
            if temp >= advanced["motor_hot_c"]:
                self._submit("alarm", "E5", P0, cooldown=60.0, cfg=cfg)
            elif temp >= advanced["motor_warm_c"]:
                self._submit("inquire", "E5w", P1, cooldown=120.0, cfg=cfg)

        cpu = s.get("cpu")
        if alerts["cpu"] and isinstance(cpu, (int, float)) and cpu >= advanced["cpu_hot_c"]:
            self._submit("alarm", "E6", P1, cooldown=300.0, cfg=cfg)

        hz = s.get("hz")
        if alerts["loop"] and isinstance(hz, (int, float)) and 0 < hz < advanced["loop_min_hz"]:
            if self._hz_low_since is None:
                self._hz_low_since = now
            elif now - self._hz_low_since >= advanced["loop_low_s"]:
                self._submit("alarm", "E7", P1, cooldown=60.0, cfg=cfg)
        else:
            self._hz_low_since = None

        err = s.get("err")
        if alerts["bus"] and isinstance(err, (int, float)) and err >= advanced["bus_error_count"]:
            self._submit("alarm", "E8", P0, cooldown=30.0, cfg=cfg)

    def _check_idle(self, s: dict, now: float, cfg: dict) -> None:
        idle_cfg = cfg["idle"]
        policy = str(s.get("pol") or "")
        eligible = (
            bool(self._driver_active())
            and not s.get("limp")
            and not s.get("fall")
            and float(s.get("tilt") or 0.0) < cfg["tilt"]["deg"]
            and policy in ("walk", "held")
        )
        if not eligible:
            self._idle_sent = False
            self._idle_next = 0.0
            return
        idle = now - self._last_input
        if not self._idle_sent:
            if idle >= idle_cfg["after_s"]:
                self._idle_sent = True
                self._idle_next = now + idle_cfg["repeat_s"]
                self._idle_times = [t for t in self._idle_times if now - t < 3600.0]
                if len(self._idle_times) < idle_cfg["max_per_hour"]:
                    self._idle_times.append(now)
                    self._submit("coo", "I1", P2, cooldown=0.0, cfg=cfg)
        elif now >= self._idle_next:
            self._idle_next = now + idle_cfg["repeat_s"]
            self._idle_times = [t for t in self._idle_times if now - t < 3600.0]
            if len(self._idle_times) < idle_cfg["max_per_hour"]:
                self._idle_times.append(now)
                self._submit("inquire", "I2", P2, cooldown=0.0, cfg=cfg)

    # ── playback queue: one worker, latest wins ──────────────────────────
    def _submit(self, tag: str, trigger: str, priority: int, *, cooldown: float,
                cfg: dict | None = None) -> None:
        now = self._clock()
        cfg = cfg or self._settings()
        if not self._enabled():
            return
        if priority > P0 and now < self._manual_until:
            return
        last = self._last_trigger.get(trigger)
        if cooldown and last is not None and now - last < cooldown:
            return
        if priority >= P1 and now - self._last_play < cfg["advanced"]["min_gap_s"]:
            return
        self._last_trigger[trigger] = now
        if priority == P0 and self._cancel_gesture:
            # A safety alarm should not be accompanied by a cute head movement.
            self._cancel_gesture()
        req = _Play(tag, trigger, priority)
        with self._cv:
            if self._pending is None or priority <= self._pending.priority:
                self._pending = req
                self._cv.notify()

    def _worker(self) -> None:
        while not self._stop.is_set():
            with self._cv:
                while self._pending is None and not self._stop.is_set():
                    self._cv.wait(timeout=0.5)
                req = self._pending
                self._pending = None
            if req is None:
                continue
            if not self._enabled():
                continue
            if req.priority > P0 and self._clock() < self._manual_until:
                continue
            try:
                result = self._play(req.tag)
                accepted = not isinstance(result, dict) or result.get("accepted", True)
                if accepted:
                    self._last_play = self._clock()
                    LOG.info("动态声音 %s（%s，P%d）", req.tag, req.trigger, req.priority)
                    if req.trigger in ("I1", "I2") and self._gesture:
                        if self._settings()["idle"]["gesture"]:
                            self._gesture(req.trigger)
                else:
                    LOG.info("动态声音 %s 被拒绝：%s", req.tag, result.get("reason"))
            except Exception as exc:  # robotd offline, no voice bank, etc.
                LOG.info("动态声音 %s 失败：%s", req.tag, exc)

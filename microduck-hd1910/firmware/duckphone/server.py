#!/usr/bin/env python3
"""duckphone bridge — HTTP + WebSocket in front of `robotd`, standard library only.

One process, two jobs:

  * serve the PWA (static files, no framework, no CDN)
  * hold exactly one driving session and translate the page's JSON messages into
    `robotd` intents, with a 250 ms watchdog behind every stick frame

Why a bridge at all: the browser cannot open a unix socket, and it should not be
able to send arbitrary JSON-RPC — the page asks for `drive`/`init`/`relax`, and
this process decides what that means, clamps it, and stops it when the phone
goes quiet.

Run on the robot (as `duck`, member of group `robot`):

    python3 server.py --static ./static

Nothing here needs root. `--padd-control` shells out to
`sudo -n systemctl stop padd`, which works because `duck` has NOPASSWD; without
it the page falls back to showing the command to copy.
"""

from __future__ import annotations

import argparse
import hmac
import json
import logging
import math
import mimetypes
import os
import re
import secrets
import socket
import subprocess
import sys
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import ws as wsproto
from actions import ACTIONS, ActionPlayer, action_sound
from audio_director import AudioDirector
from audio_settings import AudioSettings
from rpc import RobotRPC, RobotUnavailable

LOG = logging.getLogger("duckphone")

DEFAULT_PORT = 8001
DEFAULT_TOKEN_FILE = "/etc/duckphone/token"

# Where the installer leaves the daemon's build manifest. The IPC health reply
# deliberately says nothing about the release, so this is the only cheap answer.
VERSION_CANDIDATES = (
    # Where the R17 bundle actually puts it (verified on the robot).
    "/opt/robot/feetech-ft5-r5/BUILD.json",
    "/opt/robot/daemon/current/BUILD.json",
    "/opt/robot/BUILD.json",
)

# The trained twist envelope is wider than this; the phone is the coarse control
# and the robot is on a mat in a room, so the bridge is the conservative one.
VX_MIN, VX_MAX = -0.25, 0.35
VYAW_MAX = 0.8

DRIVE_HZ_MAX = 50.0
DRIVE_TIMEOUT = 0.25        # page must refresh the stick this often
SESSION_TIMEOUT = 5.0       # no message at all for this long → drop the session
HEALTH_PERIOD = 1.0
PADD_PERIOD = 2.0

# ── head / voice ────────────────────────────────────────────────────────────
# The phone joystick sends at most 0.8 rad, but preset actions (the head circle)
# need more; robotd still applies the calibrated joint limits after this.
HEAD_MAX = 1.2
HEAD_HZ_MAX = 50.0
HEAD_TIMEOUT = 0.25         # robotd has no deadman for head; the bridge is it
SOUND_TAGS = frozenset({"chirp", "greet", "inquire", "coo", "alarm", "peck", "wheee"})
SOUND_HOLD_TAGS = frozenset({"wheee"})

# The codec setup file the installer leaves behind; absent → card "0".
VOICE_SETUP = "/opt/robot/feetech-ft5-r5/voice-device.json"
VOLUME_CONTROL = "PCM Playback Volume"
MUTE_CONTROL = "Line Playback Switch"
ALSACTL = "/usr/sbin/alsactl"
# Patched by tests; a module attribute so nothing else has to know about amixer.
MIXER_RUNNER = subprocess.run

# ── policy bar ──────────────────────────────────────────────────────────────
# The biped slots, in the order the bar shows them. `walk` is the resting state
# — nothing is sent to get back to it, the robot returns there by itself when a
# skill's window expires. Everything else is one `robot.do {skill}`.
#
# `kind` is what the UI needs to know about the aftermath:
#   walk     stays put, no request at all
#   oneshot  runs for `dur` seconds, then the cascade falls back to walk
#   latch    keeps the robot there until it is toggled back (sit <-> stand)
#
# `dur` is display only — the bridge never times anything out, robotd does. It is
# copied from the config for the kick skills and computed for the two built-ins:
#   sit_toggle   latched, no duration; 0.0 means "until you press it again"
#   ground_pick  4.0 s period x 0.7 end phase = 2.8 s  (robotd-params:
#                `ground_pick_period`, `DEFAULT_GROUND_PICK_END_PHASE`)
# Both are absences from the `skill` table that `robot.do` answers to anyway —
# `do_names()` in main.rs adds them ahead of the configured skills. `roulade`
# carries `chain = true`, so pressing it again mid-roll extends the roll instead
# of being refused; the label does not need to say so.
POLICY_SLOTS = (
    {"slot": "walk", "short": "行走", "label": "行走／保持", "kind": "walk", "skill": None, "dur": 0.0},
    {"slot": "sitstand", "short": "坐下/站起", "label": "坐下／站起", "kind": "latch", "skill": "sit_toggle", "dur": 0.0},
    {"slot": "ground_pick", "short": "拾取", "label": "地面捡取", "kind": "oneshot", "skill": "ground_pick", "dur": 2.8},
    {"slot": "kick_left", "short": "左脚踢", "label": "左脚踢球", "kind": "oneshot", "skill": "kick_left", "dur": 0.5},
    {"slot": "kick_right", "short": "右脚踢", "label": "右脚踢球", "kind": "oneshot", "skill": "kick_right", "dur": 0.5},
    {"slot": "roulade", "short": "前滚翻", "label": "前滚翻", "kind": "oneshot", "skill": "roulade", "dur": 1.0},
)
POLICY_SKILLS = {row["skill"] for row in POLICY_SLOTS if row["skill"]}
POLICY_CACHE_S = 3.0

# Where the installed policy packages live. Read for display names only; a
# package that cannot be read is shown by its slot name rather than dropped,
# because the slot is what `robot.policies` actually reports.
MODEL_DIR_CANDIDATES = (
    "/opt/robot/feetech-ft5-r5/models",
    "/opt/robot/daemon/current/models",
)

# ── helpers ─────────────────────────────────────────────────────────────────
def clamp(value: float, lo: float, hi: float) -> float:
    return lo if value < lo else hi if value > hi else value


def as_float(value, default: float | None = None) -> float | None:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(float(value)) else default
    return default


def volume_raw(percent: int) -> int:
    """Percent → the codec's 0..127 register, the same curve the console uses."""
    if percent <= 0:
        return 0
    return max(0, min(127, round(127 + 40 * math.log10(percent / 100))))


def volume_percent(raw: int) -> int:
    return max(0, min(100, round(100 * 10 ** ((raw - 127) / 40))))


def alsa_card() -> str:
    """The codec card name/ID, from the installer's setup file or the env."""
    override = os.environ.get("DUCKPHONE_ALSA_CARD", "").strip()
    if override:
        return override
    try:
        with open(VOICE_SETUP, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        card = data.get("card") if isinstance(data, dict) else None
        if isinstance(card, str) and re.fullmatch(r"[A-Za-z0-9_-]+", card):
            return card
    except (OSError, ValueError):
        pass
    return "0"


def trim(value, digits: int = 3) -> float:
    return round(float(value), digits)


def tilt_from_gravity(gravity) -> float:
    """Degrees away from upright, from `safety.gravity` (upright ≈ [0,0,-1])."""
    try:
        gx, gy, gz = (float(v) for v in gravity[:3])
    except (TypeError, ValueError, IndexError):
        return 0.0
    norm = math.sqrt(gx * gx + gy * gy + gz * gz)
    if norm <= 1e-6:
        return 0.0
    cos = clamp(-gz / norm, -1.0, 1.0)
    return math.degrees(math.acos(cos))


def package_display_name(model_dir: str | None, path: str | None) -> tuple[str, str]:
    """(轮数标签, 说明) for one `.onnx`, from the package it sits in.

    The slot is authoritative and the package is decoration: a missing or
    unreadable `model-info.json` leaves the label empty so the page falls back
    to the slot's own name instead of hiding the slot entirely.
    """
    if not model_dir or not path:
        return "", ""
    try:
        folder = Path(path).parent
        with open(folder / "model-info.json", "r", encoding="utf-8") as fh:
            info = json.load(fh)
    except (OSError, ValueError):
        info = {}
    name = ""
    if isinstance(info, dict):
        candidate = info.get("name")
        if isinstance(candidate, str):
            name = candidate.strip()[:60]
    desc = ""
    try:
        with open(Path(path).parent / "manifest.json", "r", encoding="utf-8") as fh:
            manifest = json.load(fh)
    except (OSError, ValueError):
        manifest = {}
    if isinstance(manifest, dict):
        candidate = manifest.get("description")
        if isinstance(candidate, str):
            desc = candidate.strip()[:90]
    return name, desc


def first_existing_dir(candidates) -> str | None:
    for candidate in candidates:
        if os.path.isdir(candidate):
            return candidate
    return None


def build_policy_bar(report: dict, model_dir: str | None) -> list[dict]:
    """Join `robot.policies` (what is loaded) with the static slot table.

    `robot.policies` is what robotd will actually accept `robot.do` for, so it
    decides `ready`; the table decides order, wording and what happens after.
    Slots robotd does not mention (an older daemon, a robot without sitstand)
    are left out rather than shown as broken.
    """
    slots = {}
    for row in (report.get("slots") or []):
        if isinstance(row, dict) and isinstance(row.get("slot"), str):
            slots[row["slot"]] = row

    bar = []
    for meta in POLICY_SLOTS:
        row = slots.get(meta["slot"])
        if row is None:
            continue
        path = row.get("path") if isinstance(row.get("path"), str) else None
        # walk always resolves (every other slot falls back to it); the rest are
        # only runnable when they actually hold a file.
        ready = bool(path) if meta["kind"] != "walk" else True
        name, desc = package_display_name(model_dir, path)
        bar.append({
            "slot": meta["slot"],
            "short": meta["short"],
            "label": meta["label"],
            "kind": meta["kind"],
            "skill": meta["skill"],
            "dur": meta["dur"],
            "ready": ready,
            "name": name or meta["label"],
            "desc": desc,
            "error": row.get("error") if isinstance(row.get("error"), str) else None,
        })
    return bar


def detect_robotd_version() -> str:
    """The daemon's version, for the status footer.

    `robot.health` does not carry it (HealthResult is about the robot, not the
    release), so this reads the build manifest the installer leaves behind.
    Absent is fine: the page shows `—` rather than inventing a number.
    """
    override = os.environ.get("DUCKPHONE_ROBOTD_VERSION", "").strip()
    if override:
        return override
    for candidate in VERSION_CANDIDATES:
        try:
            with open(candidate, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            for key in ("official_version", "version", "robotd_version"):
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    return ""


THERMAL_ROOT = "/sys/class/thermal"


def cpu_temp_from_sysfs() -> float | None:
    """Hottest thermal zone, read straight from sysfs.

    The bridge needs this because the `robotd` build on this board predates
    `cpu_temp_c` in its health reply — the daemon samples the same zones and
    prints them to its journal, but does not put them on the IPC wire. sysfs is
    world-readable, so a fallback here needs no privilege and no firmware change.

    Returns None when there is nothing readable (not Linux, no thermal driver).
    """
    try:
        entries = os.listdir(THERMAL_ROOT)
    except OSError:
        return None
    hottest: float | None = None
    for name in entries:
        if not name.startswith("thermal_zone"):
            continue
        try:
            with open(f"{THERMAL_ROOT}/{name}/temp", "r", encoding="ascii") as fh:
                celsius = float(fh.read().strip()) / 1000.0
        except (OSError, ValueError):
            continue
        if celsius <= 0:      # a zone reading zero is a sensor fault, not cold
            continue
        if hottest is None or celsius > hottest:
            hottest = celsius
    return hottest


def padd_running() -> bool:
    """Is the gamepad service holding the move slot?

    Scanning `/proc/*/comm` beats shelling out to systemctl twice a second and it
    answers the actual question — "is something else writing `robot.move`" —
    which is broader than "is the unit active".
    """
    try:
        entries = os.listdir("/proc")
    except OSError:
        return False
    for entry in entries:
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/comm", "rb") as fh:
                if fh.read(32).strip() == b"padd":
                    return True
        except OSError:
            continue
    return False


# ── token ───────────────────────────────────────────────────────────────────
class Pairing:
    """Six-digit code, constant-time compare, and a lockout after repeated misses."""

    MAX_FAILURES = 5
    LOCK_SECONDS = 60.0

    def __init__(self, path: str | None, enabled: bool = True) -> None:
        self.enabled = enabled and bool(path)
        self.path = path
        self.token = ""
        self._lock = threading.Lock()
        self._failures: dict[str, deque[float]] = {}
        self._locked_until: dict[str, float] = {}
        if self.enabled:
            self.token = self._load_or_create(path)

    @staticmethod
    def _load_or_create(path: str) -> str:
        p = Path(path)
        try:
            existing = p.read_text(encoding="utf-8").strip()
            if existing:
                return existing
        except FileNotFoundError:
            pass
        except OSError as exc:
            LOG.warning("配对码文件不可读（%s），本次使用临时配对码", exc)
            return f"{secrets.randbelow(1_000_000):06d}"

        token = f"{secrets.randbelow(1_000_000):06d}"
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(token + "\n", encoding="utf-8")
            os.chmod(p, 0o600)
        except OSError as exc:
            LOG.warning("配对码写入失败（%s），本次使用临时配对码", exc)
        return token

    def locked_for(self, ip: str) -> float:
        until = self._locked_until.get(ip, 0.0)
        remaining = until - time.monotonic()
        return remaining if remaining > 0 else 0.0

    def verify(self, ip: str, candidate: str) -> tuple[bool, str, int]:
        """(ok, reason, remaining_tries)."""
        if not self.enabled:
            return True, "", self.MAX_FAILURES
        with self._lock:
            if self.locked_for(ip) > 0:
                return False, "locked", 0
            if not isinstance(candidate, str):
                candidate = ""
            # A device that has never paired sends nothing. That is not a guess,
            # so it must not spend one of the five tries.
            if not candidate.strip():
                return False, "need_token", self.MAX_FAILURES
            if hmac.compare_digest(candidate.strip(), self.token):
                self._failures.pop(ip, None)
                return True, "", self.MAX_FAILURES
            bucket = self._failures.setdefault(ip, deque())
            now = time.monotonic()
            while bucket and now - bucket[0] > self.LOCK_SECONDS:
                bucket.popleft()
            bucket.append(now)
            if len(bucket) >= self.MAX_FAILURES:
                self._locked_until[ip] = now + self.LOCK_SECONDS
                bucket.clear()
                return False, "locked", 0
            return False, "bad_token", self.MAX_FAILURES - len(bucket)


# ── robot bridge ────────────────────────────────────────────────────────────
class RobotBridge:
    """Owns the robotd link, merges the 20 Hz state stream with the 1 Hz health."""

    def __init__(self, socket_path: str, *, subscribe_hz: int = 20, padd_control: bool = True) -> None:
        self.padd_control = padd_control
        self._listeners: list = []
        self._lock = threading.Lock()
        self._state: dict | None = None
        self._health: dict = {}
        self._padd = False
        self._last_padd_check = 0.0
        self._online = False
        self.link_error = ""
        self._link_logged = 0.0
        self._last_link_error = ""
        self.robotd_version = detect_robotd_version()
        self.policy_names: dict = {}
        self.model_dir: str | None = None
        self._policy_lock = threading.Lock()
        self._policy_sent: dict | None = None
        self._policy_at = 0.0
        self._volume_lock = threading.Lock()
        # Dynamic sound is a bridge-level preference: the phone and the debug
        # console toggle the same value. Off until a phone takes the wheel.
        self.dynamic_sound = False
        # The action currently playing, if any; read by `snapshot` for the UI.
        self.action_name: str | None = None
        self.action_idle = False
        self._rpc = RobotRPC(
            socket_path,
            subscribe_hz=subscribe_hz,
            on_state=self._on_state,
            on_link=self._on_link,
        )

    # ── lifecycle ────────────────────────────────────────────────────────
    def start(self) -> None:
        self._rpc.start()
        threading.Thread(target=self._health_loop, name="duckphone-health", daemon=True).start()
        threading.Thread(target=self._padd_loop, name="duckphone-padd", daemon=True).start()

    def stop(self) -> None:
        self._rpc.stop()

    def add_listener(self, fn) -> None:
        with self._lock:
            self._listeners.append(fn)

    def remove_listener(self, fn) -> None:
        with self._lock:
            if fn in self._listeners:
                self._listeners.remove(fn)

    # ── robotd stream ────────────────────────────────────────────────────
    def _on_state(self, frame: dict) -> None:
        with self._lock:
            self._state = frame
            snapshot = self.snapshot_locked()
        self._emit(snapshot)

    def _on_link(self, up: bool, error: str) -> None:
        self._online = up
        self.link_error = error
        now = time.monotonic()
        if up:
            LOG.info("robotd 已连接")
            self._link_logged = 0.0
            self._last_link_error = ""
        else:
            # 重连退避每 3 s 一次，逐次记 warning 会把 journal 刷满。
            # 同一个原因 30 s 记一条，换原因立刻记。
            quiet = (error == self._last_link_error and now - self._link_logged < 30.0)
            if not quiet:
                LOG.warning("robotd 未连接：%s", error)
                self._link_logged = now
                self._last_link_error = error
            with self._lock:
                self._state = None
        self._emit(self.snapshot())

    def _health_loop(self) -> None:
        while True:
            time.sleep(HEALTH_PERIOD)
            # `connected` is socket-level on purpose: in commissioning mode the
            # state stream is refused but `robot.health` still answers, and that
            # is the only live data the page can show.
            if not self._rpc.connected:
                continue
            try:
                raw = self._rpc.health()
            except RobotUnavailable as exc:
                LOG.debug("robot.health 失败：%s", exc)
                continue
            with self._lock:
                self._health = raw
                version = raw.get("version")
                if isinstance(version, str):
                    self.robotd_version = version
            # In commissioning mode there is no 20 Hz state stream, so this poll is
            # the *only* thing that ever produces a state frame. Without the emit
            # the page would sit on stale numbers while the board answered happily.
            self._emit(self.snapshot())

    def _padd_loop(self) -> None:
        while True:
            running = padd_running()
            if running != self._padd:
                LOG.info("手柄服务 padd：%s", "运行中" if running else "已停止")
            self._padd = running
            time.sleep(PADD_PERIOD)

    def _emit(self, snapshot: dict) -> None:
        with self._lock:
            listeners = list(self._listeners)
        for fn in listeners:
            try:
                fn(snapshot)
            except Exception:  # one dead client must not stop the rest
                LOG.debug("state listener failed", exc_info=True)

    # ── snapshot ─────────────────────────────────────────────────────────
    def snapshot(self) -> dict:
        with self._lock:
            return self.snapshot_locked()

    def snapshot_locked(self) -> dict:
        frame = self._state or {}
        move = frame.get("move") or {}
        safety = frame.get("safety") or {}
        loop = frame.get("loop") or {}

        req = move.get("requested") or [0.0, 0.0, 0.0]
        app = move.get("applied") or [0.0, 0.0, 0.0]
        limited = move.get("limited_by") or []

        out: dict = {
            "t": "state",
            "ts": round(time.time(), 3),
            # "ok" means robotd answers. In commissioning mode it answers and
            # refuses to move — that is `ro`, not a broken link. Conflating the
            # two made the page paint itself offline while showing live numbers.
            "ok": self._online,
            "mv": [trim(v) for v in list(req)[:3]],
            "ap": [trim(v) for v in list(app)[:3]],
            "lim": [str(x) for x in limited],
            # The head command robotd last fed the policy, in joint order
            # [neck_pitch, head_pitch, head_yaw, head_roll]. Rounded to 2 dp:
            # this rides the 20 Hz stream and the page only draws degrees.
            "head": [trim(v, 2) for v in (frame.get("head") or [0.0, 0.0, 0.0, 0.0])[:4]]
            if isinstance(frame.get("head"), list) else [0.0, 0.0, 0.0, 0.0],
            "pol": str(frame.get("policy") or "held"),
            "limp": bool(safety.get("limp")),
            "fall": bool(safety.get("fallen")),
            "hz": trim(loop.get("hz") or 0.0, 2),
            "missed": int(loop.get("missed") or 0),
            "tilt": trim(tilt_from_gravity(safety.get("gravity") or []), 1),
            "padd": self._padd,
            "paddCanStop": bool(self.padd_control),
            "dyn": bool(self.dynamic_sound),
            "robotd": self.robotd_version,
            # robotd 在标定模式时拒绝 robot.subscribe：连接是好的，只是不能动。
            "ro": bool(self._rpc.subscribe_error),
            "roReason": self._rpc.subscribe_error,
        }
        # Only present while an action runs: the idle state stream is 20 Hz and
        # two null fields on every frame are not worth the bytes.
        if self.action_name:
            out["act"] = self.action_name
            out["actIdle"] = bool(self.action_idle)

        health = self._health or {}
        battery = health.get("battery") or {}
        volts = as_float(battery.get("volts"))
        percent = as_float(battery.get("percent"))
        out["bat"] = [trim(volts, 2), trim(percent, 1)] if volts is not None and percent is not None else None

        motors = health.get("motors") or {}
        out["temp"] = trim(as_float(motors.get("max_c")), 1) if as_float(motors.get("max_c")) is not None else None
        cpu = as_float(health.get("cpu_temp_c"))
        if cpu is None:
            cpu = cpu_temp_from_sysfs()
        out["cpu"] = trim(cpu, 1) if cpu is not None else None

        control = health.get("control_loop") or {}
        achieved = as_float(control.get("achieved_hz"))
        if achieved is not None and not out["hz"]:
            # The stream carries the rate too, but it is zero for the first
            # second after robotd starts; health knows the windowed figure.
            out["hz"] = trim(achieved, 2)

        bus = health.get("bus") or {}
        out["err"] = int(as_float(bus.get("consecutive_errors"), 0) or 0)
        return out

    # ── intents ──────────────────────────────────────────────────────────
    def drive(self, vx: float, vyaw: float) -> None:
        self._rpc.move(clamp(vx, VX_MIN, VX_MAX), 0.0, clamp(vyaw, -VYAW_MAX, VYAW_MAX))

    def head(self, neck_pitch: float, head_pitch: float, head_yaw: float, head_roll: float) -> None:
        self._rpc.head(
            clamp(neck_pitch, -HEAD_MAX, HEAD_MAX),
            clamp(head_pitch, -HEAD_MAX, HEAD_MAX),
            clamp(head_yaw, -HEAD_MAX, HEAD_MAX),
            clamp(head_roll, -HEAD_MAX, HEAD_MAX),
        )

    def mouth(self, open: float) -> None:
        self._rpc.mouth(open)

    def pose(self, z: float, roll: float, pitch: float, active: bool = True) -> None:
        self._rpc.pose(z, roll, pitch, active)

    def sound(self, tag: str, hold: bool | None = None) -> dict:
        return self._rpc.sound(tag, hold)

    def sound_async(self, tag: str) -> None:
        """A beat inside an action: do not wait for an ack, or the 500 ms
        robotd deadman would fire while the sound request is in flight."""
        self._rpc.sound_async(tag)

    def set_action_state(self, name: str | None, idle: bool) -> None:
        """Called by the action player so the 20 Hz state carries `act`."""
        self.action_name = name
        self.action_idle = bool(idle)

    def action_allowed(self) -> bool:
        """Whether a preset action may move the robot right now.

        The page also checks this, but the bridge is the one that can see the
        real state: a stale page must not start an action while the robot is
        already moving, and padd would fight the action for `robot.move`.
        """
        if not self._online or self.read_only or self._padd:
            return False
        with self._lock:
            frame = self._state or {}
        if not frame:
            return False
        move = frame.get("move") or {}
        safety = frame.get("safety") or {}
        if str(frame.get("policy") or "") != "walk":
            return False
        if safety.get("limp") or safety.get("fallen"):
            return False
        if tilt_from_gravity(safety.get("gravity") or []) >= 30.0:
            return False
        # While an action is running, `requested` is the action's own move
        # command; treating that as "someone else is driving" cancelled every
        # moving action on the first frame. User input cancels via `note_input`.
        if self.action_name:
            return True
        requested = move.get("requested") or [0.0, 0.0, 0.0]
        try:
            vx, _, vyaw = (float(v) for v in list(requested)[:3])
        except (TypeError, ValueError):
            return False
        return abs(vx) < 0.02 and abs(vyaw) < 0.02

    def set_dynamic_sound(self, on: bool) -> dict:
        """One global switch for the phone page and the debug console."""
        self.dynamic_sound = bool(on)
        # The phone paints from `state`, so a toggle must produce one immediately
        # instead of waiting for the next 20 Hz frame (or 1 Hz health poll).
        self._emit(self.snapshot())
        LOG.info("动态声音：%s", "开启" if self.dynamic_sound else "关闭")
        return {"accepted": True, "enabled": self.dynamic_sound}

    # ── system volume ────────────────────────────────────────────────────
    def _mixer(self, card: str, args: list[str]):
        return MIXER_RUNNER(
            ["amixer", "-c", card, *args],
            capture_output=True, text=True, errors="replace", timeout=4,
        )

    def volume_status(self) -> dict:
        """Read the codec's current volume, 0..100, and whether it is muted."""
        try:
            card = alsa_card()
            proc = self._mixer(card, ["cget", "name=" + VOLUME_CONTROL])
            if proc.returncode != 0:
                raise RuntimeError((proc.stderr or proc.stdout or "").strip()[-200:] or "amixer 读取失败")
            match = re.search(r": values=(\d+)", proc.stdout)
            if not match:
                raise RuntimeError("未取得声卡音量回读")
            muted = False
            switch = self._mixer(card, ["cget", "name=" + MUTE_CONTROL])
            if switch.returncode == 0:
                muted = bool(re.search(r": values=(?:off|0)(?:,|$)", switch.stdout, re.M))
            percent = 0 if muted else volume_percent(int(match.group(1)))
            return {"accepted": True, "volume": percent, "muted": muted}
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            return {"accepted": False, "reason": f"音量不可用：{exc}"}

    def set_volume(self, level) -> dict:
        """Apply 0..100 to the codec and persist it when sudo allows."""
        if isinstance(level, bool) or not isinstance(level, (int, float)) or not math.isfinite(float(level)):
            return {"accepted": False, "reason": "音量必须是 0～100 的整数"}
        percent = int(level)
        if percent < 0 or percent > 100:
            return {"accepted": False, "reason": "音量必须是 0～100 的整数"}
        raw = volume_raw(percent)
        try:
            with self._volume_lock:
                card = alsa_card()
                proc = self._mixer(card, ["cset", "name=" + VOLUME_CONTROL, str(raw)])
                if proc.returncode != 0:
                    raise RuntimeError((proc.stderr or proc.stdout or "").strip()[-200:] or "amixer 写入失败")
                match = re.search(r": values=(\d+)", proc.stdout)
                if not match or int(match.group(1)) != raw:
                    raise RuntimeError("音量实际回读不符")
                switch = self._mixer(
                    card, ["cset", "name=" + MUTE_CONTROL, "off,off" if percent == 0 else "on,on"],
                )
                if switch.returncode != 0:
                    raise RuntimeError((switch.stderr or switch.stdout or "").strip()[-200:] or "静音开关写入失败")
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            return {"accepted": False, "reason": f"音量设置失败：{exc}"}

        saved, message = False, ""
        try:
            stored = subprocess.run(
                ["sudo", "-n", ALSACTL, "store", card],
                capture_output=True, text=True, timeout=4, check=False,
            )
            if stored.returncode == 0:
                saved = True
            else:
                message = "音量已生效，但保存到 ALSA 失败（重启后可能恢复默认）"
        except (OSError, subprocess.SubprocessError):
            message = "音量已生效，但保存到 ALSA 失败（重启后可能恢复默认）"
        return {"accepted": True, "volume": percent, "muted": percent == 0,
                "saved": saved, "message": message}

    def stop(self) -> dict:
        return self._rpc.stop()

    def init(self) -> dict:
        return self._rpc.init()

    def enable(self, on: bool) -> dict:
        return self._rpc.enable(on)

    def relax(self) -> dict:
        return self._rpc.relax()

    def reboot_motors(self, ids: list[int] | None = None) -> dict:
        return self._rpc.reboot_motors(ids)

    # ── policies ─────────────────────────────────────────────────────────
    def policies(self, fresh: bool = False) -> dict:
        """The policy bar: every biped slot, what fills it, whether it runs.

        Cached for a few seconds because opening the bar and then opening it
        again is one user action, and each read is an RPC plus a handful of
        file reads. `fresh` skips the cache after anything that changes it.
        """
        with self._policy_lock:
            now = time.monotonic()
            if not fresh and self._policy_sent is not None and now - self._policy_at < POLICY_CACHE_S:
                return self._policy_sent
        try:
            report = self._rpc.policies()
        except RobotUnavailable as exc:
            payload = {"ok": False, "reason": str(exc), "chips": [], "mode": "", "sitting": None}
            with self._policy_lock:
                self._policy_sent = payload
                self._policy_at = time.monotonic()
            return payload

        if self.model_dir is None:
            self.model_dir = first_existing_dir(MODEL_DIR_CANDIDATES)
        payload = {
            "ok": True,
            "mode": str(report.get("mode") or ""),
            "homed": report.get("homed"),
            "sitting": report.get("sitting"),
            "chips": build_policy_bar(report, self.model_dir),
        }
        with self._policy_lock:
            self._policy_sent = payload
            self._policy_at = time.monotonic()
        return payload

    def run_skill(self, skill: str) -> dict:
        """One `robot.do`. The robot returns to walk by itself afterwards."""
        if skill not in POLICY_SKILLS:
            return {"accepted": False, "reason": f"不支持的策略：{skill}"}
        result = self._rpc.do_skill(skill)
        self.policies(fresh=True)
        return result

    def stop_padd(self) -> tuple[bool, str]:
        if not self.padd_control:
            return False, "未启用 padd 控制"
        try:
            proc = subprocess.run(
                ["sudo", "-n", "systemctl", "stop", "padd"],
                capture_output=True, text=True, timeout=8.0, check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return False, f"无法执行 systemctl：{exc}"
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip().splitlines()
            return False, detail[-1] if detail else f"systemctl 退出码 {proc.returncode}"
        time.sleep(0.2)
        self._padd = padd_running()
        return True, ""

    @property
    def online(self) -> bool:
        return self._online

    @property
    def read_only(self) -> bool:
        """robotd refuses intents because it is being commissioned.

        Not a fault, and not a reason to stop talking to it — but a reason not to
        forward 20 Hz of `robot.move` notifications it has said it will ignore.
        """
        return bool(self._rpc.subscribe_error)


# ── sessions ────────────────────────────────────────────────────────────────
class Session:
    def __init__(self, sid: str, ws: wsproto.WebSocket, ip: str) -> None:
        self.id = sid
        self.ws = ws
        self.ip = ip
        self.name = "手机"
        self.role = "readonly"
        self.ready = False
        self.last_rx = time.monotonic()
        self.last_drive = 0.0
        self.last_head = 0.0
        self.driving = False
        self.hello_count = 0
        self._send_lock = threading.Lock()
        self.closed = False

    def send(self, payload: dict) -> None:
        if self.closed:
            return
        data = json.dumps(payload, separators=(",", ":"))
        try:
            with self._send_lock:
                self.ws.send_text(data)
        except (OSError, wsproto.WSError):
            self.closed = True

    def close(self, code: int = wsproto.CLOSE_NORMAL, reason: str = "") -> None:
        self.closed = True
        try:
            self.ws.close(code, reason)
        except Exception:
            pass


class SessionManager:
    """Exactly one driver, everyone else watches."""

    def __init__(self, bridge: RobotBridge) -> None:
        self.bridge = bridge
        self._sessions: dict[str, Session] = {}
        self._driver: str | None = None
        self._lock = threading.Lock()

    def add(self, session: Session) -> None:
        with self._lock:
            self._sessions[session.id] = session

    def remove(self, session: Session) -> None:
        with self._lock:
            self._sessions.pop(session.id, None)
            was_driver = self._driver == session.id
            if was_driver:
                self._driver = None
        if was_driver:
            self._safe_stop("驾驶会话结束")

    def promote(self, session: Session) -> None:
        # The old driver's head pose is an absolute intent that outlives it;
        # returning the head to neutral is part of handing over.
        try:
            self.bridge.head(0.0, 0.0, 0.0, 0.0)
            self.bridge.sound("wheee", False)
        except RobotUnavailable:
            pass
        with self._lock:
            self._driver = session.id
            session.role = "driver"
            others = [s for s in self._sessions.values() if s.id != session.id]
        for other in others:
            if other.role == "driver":
                other.role = "readonly"
                other.send({
                    "t": "session", "role": "readonly",
                    "reason": "已被另一台设备接管", "driver": session.name,
                })
        session.send({"t": "session", "role": "driver", "driver": session.name})

    def claim(self, session: Session) -> str:
        """First hello takes the wheel; later ones watch until they ask for it."""
        with self._lock:
            free = self._driver is None
            if free:
                self._driver = session.id
                session.role = "driver"
        return "driver" if free else "readonly"

    @property
    def driver(self) -> Session | None:
        with self._lock:
            sid = self._driver
            return self._sessions.get(sid) if sid else None

    def driver_name(self) -> str:
        d = self.driver
        return d.name if d else ""

    def broadcast(self, payload: dict) -> None:
        with self._lock:
            targets = [s for s in self._sessions.values() if s.ready]
        for session in targets:
            session.send(payload)

    def _safe_stop(self, why: str) -> None:
        try:
            self.bridge.stop()
            LOG.info("已归零（%s）", why)
        except RobotUnavailable as exc:
            LOG.warning("归零失败（%s）：%s", why, exc)
        try:
            self.bridge.head(0.0, 0.0, 0.0, 0.0)
        except RobotUnavailable as exc:
            LOG.warning("头部回正失败（%s）：%s", why, exc)
        try:
            self.bridge.sound("wheee", False)   # end a held long call, if any
        except RobotUnavailable as exc:
            LOG.warning("收声失败（%s）：%s", why, exc)


# ── watchdog ────────────────────────────────────────────────────────────────
class Watchdog:
    """Stops the robot when the driver goes quiet, and reaps dead sessions."""

    def __init__(self, manager: SessionManager, bridge: RobotBridge) -> None:
        self.manager = manager
        self.bridge = bridge
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_forward = 0.0
        self._last_head = 0.0
        self._head_active = False

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="duckphone-watchdog", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def mark_drive(self) -> None:
        self._last_forward = time.monotonic()

    def mark_head(self, active: bool) -> None:
        """Refresh the head deadline; `active` says whether it is off-neutral."""
        self._last_head = time.monotonic()
        self._head_active = bool(active)

    # 20 ms, not 50: the deadline is 250 ms and a 50 ms tick alone can add a
    # fifth of it. Measured on the robot, the old tick showed 375 ms end to end.
    TICK = 0.02

    def _run(self) -> None:
        while not self._stop.wait(self.TICK):
            driver = self.manager.driver
            now = time.monotonic()
            if driver is None or driver.closed:
                continue
            if now - driver.last_rx > SESSION_TIMEOUT:
                LOG.info("会话 %s 超时，断开", driver.id)
                driver.close(wsproto.CLOSE_NORMAL, "timeout")
                self.manager.remove(driver)
                continue
            if driver.driving and now - self._last_forward > DRIVE_TIMEOUT:
                driver.driving = False
                try:
                    self.bridge.stop()
                    LOG.info("摇杆超时，已归零")
                except RobotUnavailable as exc:
                    LOG.warning("看门狗归零失败：%s", exc)
            # robotd has no freshness gate on `robot.head`; an absolute pose would
            # otherwise outlive the page that asked for it.
            if self._head_active and now - self._last_head > HEAD_TIMEOUT:
                self._head_active = False
                try:
                    self.bridge.head(0.0, 0.0, 0.0, 0.0)
                    LOG.info("头部意图超时，已回正")
                except RobotUnavailable as exc:
                    LOG.warning("头部回正失败：%s", exc)


# ── HTTP / WebSocket handler ────────────────────────────────────────────────
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".webmanifest": "application/manifest+json; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".txt": "text/plain; charset=utf-8",
}

CACHE_IMMUTABLE = "public, max-age=0, must-revalidate"


class Handler(BaseHTTPRequestHandler):
    server_version = "duckphone/1"
    protocol_version = "HTTP/1.1"

    # injected by make_server
    static_dir: Path
    bridge: RobotBridge
    manager: SessionManager
    pairing: Pairing
    watchdog: Watchdog
    director: AudioDirector
    audio_settings: AudioSettings
    actions: ActionPlayer

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003 - stdlib signature
        LOG.debug("%s - %s", self.address_string(), fmt % args)

    # ── static ───────────────────────────────────────────────────────────
    def _resolve(self, path: str) -> Path | None:
        rel = path.split("?", 1)[0].lstrip("/")
        if rel in ("", "/"):
            rel = "index.html"
        candidate = (self.static_dir / rel).resolve()
        try:
            candidate.relative_to(self.static_dir.resolve())
        except ValueError:
            return None
        return candidate if candidate.is_file() else None

    def _send_file(self, file: Path) -> None:
        data = file.read_bytes()
        ctype = CONTENT_TYPES.get(file.suffix.lower()) or mimetypes.guess_type(str(file))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", CACHE_IMMUTABLE)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _send_text(self, code: int, text: str) -> None:
        body = text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        # The debug console is served from a different port on the same board.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802 - stdlib naming
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "86400")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_HEAD(self) -> None:  # noqa: N802 - stdlib naming
        self.do_GET()

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/healthz":
            # Distinguishes "the daemon is not there" from "it is there but will
            # refuse to move", which are different phone calls.
            if not self.bridge.online:
                self._send_text(503, "robotd-unreachable\n")
            elif self.bridge.read_only:
                self._send_text(200, "read-only\n")
            else:
                self._send_text(200, "ok\n")
            return
        if path == "/ws":
            self._serve_websocket()
            return
        if path == "/api/status":
            self._send_json(200, {"online": self.bridge.online,
                                  "sessions": self.manager.driver_name(),
                                  "dynamicSound": bool(self.bridge.dynamic_sound)})
            return
        if path == "/api/dynamic-sound":
            self._send_json(200, {"enabled": bool(self.bridge.dynamic_sound)})
            return
        if path == "/api/audio-config":
            self._send_json(200, {"accepted": True, "config": self.audio_settings.snapshot()})
            return

        file = self._resolve(path)
        if file is None:
            self._send_text(404, "not found\n")
            return
        self._send_file(file)

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        length = int(self.headers.get("Content-Length") or 0)
        raw = b""
        if length:
            try:
                raw = self.rfile.read(min(length, 4096))
            except OSError:
                pass
        if path == "/api/dynamic-sound":
            try:
                msg = json.loads(raw or b"{}")
            except ValueError:
                self._send_json(400, {"accepted": False, "reason": "bad_json"})
                return
            if not isinstance(msg, dict):
                self._send_json(400, {"accepted": False, "reason": "bad_json"})
                return
            if "enabled" in msg:
                on = msg.get("enabled")
                if not isinstance(on, bool):
                    self._send_json(400, {"accepted": False, "reason": "enabled 必须是布尔值"})
                    return
            elif msg.get("toggle") is True:
                on = not self.bridge.dynamic_sound
            else:
                self._send_json(400, {"accepted": False, "reason": "需要 enabled 或 toggle"})
                return
            self._send_json(200, self.bridge.set_dynamic_sound(on))
            self.director.note_input()
            return
        if path == "/api/audio-config":
            try:
                msg = json.loads(raw or b"{}")
            except ValueError:
                self._send_json(400, {"accepted": False, "reason": "bad_json"})
                return
            if not isinstance(msg, dict):
                self._send_json(400, {"accepted": False, "reason": "bad_json"})
                return
            try:
                if msg.get("reset") is True:
                    config = self.audio_settings.reset()
                else:
                    if "patch" in msg:
                        patch = msg["patch"]
                        if not isinstance(patch, dict):
                            self._send_json(400, {"accepted": False, "reason": "patch 必须是对象"})
                            return
                    else:
                        patch = msg
                    config = self.audio_settings.update(patch)
            except ValueError as exc:
                self._send_json(400, {"accepted": False, "reason": str(exc)})
                return
            self.director.note_input()
            self.manager.broadcast({"t": "audioConfig", "config": config})
            self._send_json(200, {"accepted": True, "config": config})
            return
        if path == "/stop":
            # `sendBeacon` on pagehide/visibilitychange. A stop is always safe to
            # honour without a token — the worst a stranger can do is halt a robot.
            driver = self.manager.driver
            # Logged because otherwise "did the beacon actually arrive?" is
            # unanswerable from the outside, and that question decides whether a
            # vanished page left the robot running.
            LOG.info("收到 /stop beacon（%s）", driver.name if driver else "无驾驶者")
            if driver is not None:
                driver.driving = False
            try:
                self.actions.cancel()
                self.bridge.stop()
                self.bridge.head(0.0, 0.0, 0.0, 0.0)
                self.bridge.sound("wheee", False)
            except RobotUnavailable:
                pass
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self._send_text(404, "not found\n")

    # ── websocket ────────────────────────────────────────────────────────
    def _serve_websocket(self) -> None:
        if (self.headers.get("Upgrade") or "").lower() != "websocket":
            self._send_text(400, "expected websocket upgrade\n")
            return
        if not self.headers.get("Sec-WebSocket-Key"):
            self._send_text(400, "missing Sec-WebSocket-Key\n")
            return

        self.wfile.write(wsproto.handshake_bytes(self.headers))
        self.wfile.flush()
        self.close_connection = True

        sock = self.connection
        sock.settimeout(None)
        websocket = wsproto.WebSocket(sock, is_server=True, reader=self.rfile)
        session = Session(secrets.token_hex(6), websocket, self.client_address[0])
        self.manager.add(session)
        LOG.info("会话 %s 已连接（%s）", session.id, session.ip)
        try:
            self._pump(session)
        except wsproto.WSError as exc:
            if exc.code != wsproto.CLOSE_NORMAL:
                LOG.info("会话 %s 关闭：%s（%s）", session.id, exc, exc.code)
        except (OSError, ValueError) as exc:
            # The session watchdog may close the socket while this thread is in
            # `read()`; CPython then raises ValueError("read of closed file").
            LOG.info("会话 %s 断开：%s", session.id, exc)
        finally:
            was_driver = session.role == "driver"
            session.closed = True
            self.manager.remove(session)
            if was_driver:
                self.director.note_input()
                self.director.on_event("driver_end")
            websocket.close()
            LOG.info("会话 %s 结束", session.id)

    def _pump(self, session: Session) -> None:
        while True:
            text = session.ws.recv_message()
            if text is None:
                return
            session.last_rx = time.monotonic()
            try:
                msg = json.loads(text)
            except ValueError:
                session.send({"t": "error", "reason": "bad_json"})
                continue
            if isinstance(msg, dict):
                self._dispatch(session, msg)

    def _dispatch(self, session: Session, msg: dict) -> None:
        kind = msg.get("t")

        if kind == "hello":
            self._hello(session, msg)
            return

        if not session.ready:
            session.send({"t": "error", "reason": "not_paired"})
            return

        if kind == "ping":
            session.send({"t": "pong", "ts": round(time.time(), 3)})
            return

        if kind == "drive":
            if session.role != "driver":
                return
            self.director.note_input()
            if self.bridge.read_only:
                # robotd has said it will refuse; sending anyway is 20 Hz of noise
                # on a socket that also carries the health poll.
                return
            vx = as_float(msg.get("vx"), 0.0) or 0.0
            vyaw = as_float(msg.get("vyaw"), 0.0) or 0.0
            if not (math.isfinite(vx) and math.isfinite(vyaw)):
                return
            now = time.monotonic()
            if now - session.last_drive < 1.0 / DRIVE_HZ_MAX and (vx or vyaw):
                return
            session.last_drive = now
            self.watchdog.mark_drive()
            session.driving = bool(vx or vyaw)
            try:
                self.bridge.drive(vx, vyaw)
            except RobotUnavailable:
                pass
            return

        if kind == "head":
            if session.role != "driver" or self.bridge.read_only:
                return
            self.director.note_input()
            values = [
                as_float(msg.get("neck_pitch"), 0.0) or 0.0,
                as_float(msg.get("head_pitch"), 0.0) or 0.0,
                as_float(msg.get("head_yaw"), 0.0) or 0.0,
                as_float(msg.get("head_roll"), 0.0) or 0.0,
            ]
            if not all(math.isfinite(v) for v in values):
                return
            now = time.monotonic()
            nonzero = any(abs(v) > 1e-6 for v in values)
            if now - session.last_head < 1.0 / HEAD_HZ_MAX and nonzero:
                return
            session.last_head = now
            values = [clamp(v, -HEAD_MAX, HEAD_MAX) for v in values]
            try:
                self.bridge.head(*values)
            except RobotUnavailable:
                pass
            self.watchdog.mark_head(nonzero)
            return

        if kind == "takeover":
            was = session.role
            self.director.note_input()
            self.manager.promote(session)
            if was != "driver":
                # A fresh phone takeover is the documented default-on moment.
                self.bridge.set_dynamic_sound(True)
                self.director.on_event("driver_start")
            self.manager.broadcast({"t": "state_owner", "driver": session.name})
            return

        if kind == "cmd":
            self._command(session, msg)
            return

    def _hello(self, session: Session, msg: dict) -> None:
        session.hello_count += 1
        ok, reason, remaining = self.pairing.verify(session.ip, msg.get("token"))
        if not ok:
            payload = {"t": "hello", "ok": False, "reason": reason}
            if reason == "need_token":
                payload["remaining"] = self.pairing.MAX_FAILURES
            elif reason == "locked":
                payload["retryAfter"] = round(self.pairing.locked_for(session.ip), 1)
            else:
                payload["remaining"] = remaining
            session.send(payload)
            if session.hello_count >= 8:
                session.close(wsproto.CLOSE_NORMAL, "too many attempts")
            return

        name = str(msg.get("name") or "手机")[:40]
        session.name = name
        was = session.role
        role = self.manager.claim(session)
        session.ready = True
        session.send({
            "t": "hello",
            "ok": True,
            "role": role,
            "name": session.name,
            "driver": self.manager.driver_name(),
            "paddCanStop": bool(self.bridge.padd_control),
            "audio": self.audio_settings.snapshot(),
            "clamp": {"vx": [VX_MIN, VX_MAX], "vyaw": [-VYAW_MAX, VYAW_MAX]},
        })
        if role == "driver" and was != "driver":
            # Takeover defaults dynamic sound on; the page can turn it off.
            self.bridge.set_dynamic_sound(True)
            self.director.on_event("driver_start")
        session.send(self._annotated_state())
        LOG.info("会话 %s 配对成功，角色 %s", session.id, role)

    def _annotated_state(self) -> dict:
        state = self.bridge.snapshot()
        state["t"] = "state"
        return state

    def _command(self, session: Session, msg: dict) -> None:
        cmd_id = msg.get("id")
        name = str(msg.get("name") or "")
        # 只读数据：另一台设备在驾驶时也该看得到有哪些策略在跑什么。
        # 放在角色检查之前，否则只读会话的策略条是空的。
        if name == "policies":
            payload = self.bridge.policies(fresh=bool(msg.get("fresh")))
            payload["t"] = "policies"
            session.send(payload)
            return
        if name == "audioConfig":
            session.send({"t": "audioConfig", "ok": True,
                          "config": self.audio_settings.snapshot()})
            return

        if session.role != "driver":
            session.send({"t": "ack", "id": cmd_id, "ok": False, "reason": "readonly", "name": name})
            return

        self.director.note_input()
        try:
            if name == "setAudioConfig":
                patch = msg.get("patch")
                if not isinstance(patch, dict):
                    session.send({"t": "ack", "id": cmd_id, "ok": False,
                                  "reason": "patch 必须是对象", "name": name})
                    return
                config = self.audio_settings.update(patch)
                self.manager.broadcast({"t": "audioConfig", "config": config})
                session.send({"t": "ack", "id": cmd_id, "ok": True, "name": name,
                              "config": config})
                return
            if name == "resetAudioConfig":
                config = self.audio_settings.reset()
                self.manager.broadcast({"t": "audioConfig", "config": config})
                session.send({"t": "ack", "id": cmd_id, "ok": True, "name": name,
                              "config": config})
                return
            if name == "dynamicSound":
                on = msg.get("on")
                if not isinstance(on, bool):
                    session.send({"t": "ack", "id": cmd_id, "ok": False,
                                  "reason": "on 必须是布尔值", "name": name})
                    return
                result = self.bridge.set_dynamic_sound(on)
                self.director.note_input()
                session.send({"t": "ack", "id": cmd_id, "ok": True, "name": name,
                              "enabled": result["enabled"]})
                return
            if name == "action":
                action = str(msg.get("action") or "")
                if action not in ACTIONS:
                    session.send({"t": "ack", "id": cmd_id, "ok": False,
                                  "reason": f"不支持的动作：{action}", "name": name})
                    return
                self.director.note_manual()
                sound_ok = True
                tag = action_sound(action)
                if tag:
                    # Play the voice first: if robotd refuses the sound request,
                    # the action must not start behind a failed ack.
                    sound_ok = bool(self.bridge.sound(tag).get("accepted", True))
                ok, reason = self.actions.run(action, idle=False)
                session.send({
                    "t": "ack", "id": cmd_id, "ok": ok, "name": name,
                    "action": action, "reason": reason or None, "sound": sound_ok,
                })
                return
            if name == "cancelAction":
                self.actions.cancel()
                session.send({"t": "ack", "id": cmd_id, "ok": True, "name": name})
                return
            if name == "init":
                result = self.bridge.init()
            elif name == "enable":
                result = self.bridge.enable(bool(msg.get("on")))
                if result.get("accepted", True):
                    self.director.on_event("enable", on=bool(msg.get("on")))
                else:
                    self.director.on_event("refusal")
            elif name == "stop":
                session.driving = False
                result = self.bridge.stop()
                try:
                    self.bridge.head(0.0, 0.0, 0.0, 0.0)
                except RobotUnavailable:
                    pass
            elif name == "relax":
                if msg.get("confirm") != "RELAX":
                    session.send({"t": "ack", "id": cmd_id, "ok": False,
                                  "reason": "需要确认", "name": name})
                    return
                session.driving = False
                result = self.bridge.relax()
            elif name == "rebootMotors":
                session.driving = False
                result = self.bridge.reboot_motors([])
            elif name == "sound":
                tag = str(msg.get("tag") or "")
                if tag not in SOUND_TAGS:
                    session.send({"t": "ack", "id": cmd_id, "ok": False,
                                  "reason": f"不支持的声音：{tag}", "name": name})
                    return
                hold = msg.get("hold")
                if tag not in SOUND_HOLD_TAGS or not isinstance(hold, bool):
                    hold = None
                result = self.bridge.sound(tag, hold)
                if result.get("accepted", True):
                    self.director.note_manual()
            elif name == "volume":
                level = msg.get("level")
                result = (self.bridge.set_volume(level) if level is not None
                          else self.bridge.volume_status())
            elif name == "policyDo":
                skill = str(msg.get("skill") or "")
                session.driving = False
                result = self.bridge.run_skill(skill)
                accepted = result.get("accepted", True)
                session.send({
                    "t": "ack", "id": cmd_id, "ok": bool(accepted), "name": name,
                    "skill": skill, "reason": result.get("reason") or None,
                    "policies": self.bridge.policies(),
                })
                if not accepted:
                    self.director.on_event("refusal")
                LOG.info("策略执行 %s：%s", skill, "ok" if accepted else result.get("reason"))
                return
            elif name == "padd":
                action = str(msg.get("action") or "")
                if action != "stop":
                    session.send({"t": "ack", "id": cmd_id, "ok": False,
                                  "reason": "不支持的动作", "name": name})
                    return
                ok, reason = self.bridge.stop_padd()
                session.send({"t": "ack", "id": cmd_id, "ok": ok, "reason": reason or None,
                              "name": name, "padd": self.bridge.snapshot().get("padd")})
                if ok:
                    LOG.info("已按页面请求停止 padd")
                return
            else:
                session.send({"t": "ack", "id": cmd_id, "ok": False,
                              "reason": "未知命令", "name": name})
                return
        except RobotUnavailable as exc:
            session.send({"t": "ack", "id": cmd_id, "ok": False, "reason": str(exc), "name": name})
            return

        accepted = result.get("accepted", True)
        reason = result.get("reason")
        if not accepted and name not in ("sound", "volume"):
            self.director.on_event("refusal")
        extra = {key: result[key] for key in ("volume", "muted", "saved", "message")
                 if key in result}
        session.send({
            "t": "ack", "id": cmd_id, "ok": bool(accepted), "name": name,
            "reason": reason if reason else None, **extra,
        })
        if name in ("init", "enable", "stop", "relax", "rebootMotors"):
            session.send(self._annotated_state())


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address) -> None:
        # A phone that closes the page or loses wifi resets the HTTP socket while
        # socketserver is still reading the request line. That is not a bridge
        # failure and should not print a traceback into the robot's journal.
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionResetError, BrokenPipeError)):
            LOG.debug("客户端断开：%s", client_address)
            return
        super().handle_error(request, client_address)


def make_server(cfg: argparse.Namespace) -> Server:
    bridge = RobotBridge(
        cfg.robot_socket,
        subscribe_hz=cfg.subscribe_hz,
        padd_control=not cfg.no_padd_control,
    )
    manager = SessionManager(bridge)
    watchdog = Watchdog(manager, bridge)
    pairing = Pairing(cfg.token_file, enabled=bool(cfg.auth))

    def broadcast(snapshot: dict) -> None:
        manager.broadcast(snapshot)

    bridge.add_listener(broadcast)
    settings = AudioSettings(getattr(cfg, "audio_config", None))

    def action_allowed() -> bool:
        return (bridge.online and not bridge.read_only
                and manager.driver is not None and bridge.action_allowed())

    actions = ActionPlayer(
        bridge.head,
        bridge.mouth,
        bridge.drive,
        bridge.pose,
        play_sound=bridge.sound_async,
        allowed=action_allowed,
        on_change=bridge.set_action_state,
    )
    director = AudioDirector(
        play=bridge.sound,
        enabled=lambda: bridge.dynamic_sound,
        driver_active=lambda: manager.driver is not None,
        settings=settings.snapshot,
        action=actions.run,
        cancel_action=actions.cancel,
    )
    bridge.add_listener(director.on_state)
    director.start()

    handler = type("BoundHandler", (Handler,), {
        "static_dir": Path(cfg.static).resolve(),
        "bridge": bridge,
        "manager": manager,
        "pairing": pairing,
        "watchdog": watchdog,
        "director": director,
        "audio_settings": settings,
        "actions": actions,
    })
    httpd = Server((cfg.host, cfg.port), handler)
    httpd.bridge = bridge          # type: ignore[attr-defined]
    httpd.manager = manager        # type: ignore[attr-defined]
    httpd.watchdog = watchdog      # type: ignore[attr-defined]
    httpd.pairing = pairing        # type: ignore[attr-defined]
    httpd.director = director      # type: ignore[attr-defined]
    httpd.audio_settings = settings  # type: ignore[attr-defined]
    httpd.actions = actions        # type: ignore[attr-defined]
    return httpd


def lan_addresses() -> list[str]:
    out: list[str] = []
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            addr = info[4][0]
            if addr not in out and not addr.startswith("127."):
                out.append(addr)
    except OSError:
        pass
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="duckphone 桥（HTTP + WebSocket）")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--static", default=str(Path(__file__).with_name("static")))
    ap.add_argument("--robot-socket", default="/run/robotd.sock")
    ap.add_argument("--token-file", default=DEFAULT_TOKEN_FILE)
    ap.add_argument("--audio-config", default="/etc/duckphone/audio.json")
    # 默认不校验：手机页面上已经没有输入配对码的地方了，默认要求配对码会让
    # 每个新设备都卡在"未配对"。要恢复校验时用 --auth。
    ap.add_argument("--auth", action="store_true", help="启用 6 位配对码（默认关闭）")
    ap.add_argument("--no-padd-control", action="store_true", help="不允许页面停掉手柄服务")
    ap.add_argument("--subscribe-hz", type=int, default=20)
    ap.add_argument("-v", "--verbose", action="store_true")
    cfg = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if cfg.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    httpd = make_server(cfg)
    bridge: RobotBridge = httpd.bridge          # type: ignore[attr-defined]
    pairing: Pairing = httpd.pairing            # type: ignore[attr-defined]
    watchdog: Watchdog = httpd.watchdog         # type: ignore[attr-defined]

    bridge.start()
    watchdog.start()

    addrs = lan_addresses() or ["127.0.0.1"]
    LOG.info("duckphone 已启动：%s", ", ".join(f"http://{a}:{cfg.port}/" for a in addrs))
    if pairing.enabled:
        LOG.info("配对码校验已开启：%s（%s）", pairing.token, cfg.token_file)
    else:
        LOG.info("配对码校验已关闭（默认；需要时加 --auth）")
    if cfg.no_padd_control:
        LOG.info("页面不能停 padd，只能复制命令")

    try:
        httpd.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        LOG.info("收到 Ctrl-C，正在退出")
    finally:
        watchdog.stop()
        bridge.stop()
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Persistent dynamic-sound settings for the duckphone bridge.

The phone and the debug console share one file, `/etc/duckphone/audio.json`.
The director reads a snapshot on every state frame, so a save applies without a
restart. Missing or broken files fall back to the defaults instead of keeping the
bridge from starting.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import tempfile
import threading
from pathlib import Path

LOG = logging.getLogger("duckphone.audio.settings")

DEFAULTS = {
    "version": 2,
    "idle": {
        "after_s": 30,
        "repeat_s": 300,
        "max_per_hour": 12,
        "gesture": True,
    },
    "fall": {
        "repeat_s": 5,
        "max_repeats": 6,
        "tail_s": 60,
    },
    "tilt": {
        "deg": 30,
        "repeat_s": 10,
    },
    "actions": {
        "takeover": True,
        "handback": True,
        "skill_start": True,
        "skill_end": True,
        "enable": True,
        "refusal": True,
    },
    "alerts": {
        "fall": True,
        "tilt": True,
        "battery": True,
        "motor": True,
        "cpu": True,
        "loop": True,
        "bus": True,
    },
    "advanced": {
        "min_gap_s": 1.5,
        "manual_hold_s": 1.5,
        "battery_low_pct": 25,
        "battery_critical_pct": 15,
        "motor_warm_c": 50,
        "motor_hot_c": 60,
        "cpu_hot_c": 85,
        "loop_min_hz": 45,
        "loop_low_s": 3,
        "bus_error_count": 3,
    },
}

# section -> key -> (type, low, high). Bools are handled separately.
NUMBERS = {
    "idle": {
        "after_s": (float, 5.0, 3600.0),
        "repeat_s": (float, 5.0, 3600.0),
        "max_per_hour": (int, 1, 60),
    },
    "fall": {
        "repeat_s": (float, 2.0, 30.0),
        "max_repeats": (int, 1, 20),
        "tail_s": (float, 10.0, 600.0),
    },
    "tilt": {
        "deg": (float, 10.0, 60.0),
        "repeat_s": (float, 5.0, 120.0),
    },
    "advanced": {
        "min_gap_s": (float, 0.2, 10.0),
        "manual_hold_s": (float, 0.0, 10.0),
        "battery_low_pct": (float, 5.0, 50.0),
        "battery_critical_pct": (float, 1.0, 30.0),
        "motor_warm_c": (float, 30.0, 80.0),
        "motor_hot_c": (float, 40.0, 100.0),
        "cpu_hot_c": (float, 60.0, 110.0),
        "loop_min_hz": (float, 20.0, 49.0),
        "loop_low_s": (float, 1.0, 30.0),
        "bus_error_count": (int, 1, 20),
    },
}

BOOLS = {
    "idle": ("gesture",),
    "actions": ("takeover", "handback", "skill_start", "skill_end", "enable", "refusal"),
    "alerts": ("fall", "tilt", "battery", "motor", "cpu", "loop", "bus"),
}


def _number(value, default, cast, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    try:
        number = cast(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


class AudioSettings:
    """Load, validate, save and hand out a snapshot of the audio config."""

    def __init__(self, path: str | os.PathLike | None = None) -> None:
        self.path = Path(path) if path else None
        self._lock = threading.Lock()
        self._config = self._load()

    # ── public ───────────────────────────────────────────────────────────
    def snapshot(self) -> dict:
        with self._lock:
            return copy.deepcopy(self._config)

    def update(self, patch: dict) -> dict:
        if not isinstance(patch, dict):
            raise ValueError("配置必须是对象")
        with self._lock:
            self._config = self._merge(self._config, patch)
            self._save_locked()
            return copy.deepcopy(self._config)

    def reset(self) -> dict:
        with self._lock:
            self._config = copy.deepcopy(DEFAULTS)
            self._save_locked()
            return copy.deepcopy(self._config)

    # ── loading / merging ────────────────────────────────────────────────
    def _load(self) -> dict:
        if self.path is None:
            return copy.deepcopy(DEFAULTS)
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return copy.deepcopy(DEFAULTS)
        except (OSError, ValueError) as exc:
            LOG.warning("动态声音配置读取失败，使用默认值：%s", exc)
            return copy.deepcopy(DEFAULTS)
        if not isinstance(raw, dict):
            LOG.warning("动态声音配置不是对象，使用默认值")
            return copy.deepcopy(DEFAULTS)
        return self._merge(DEFAULTS, raw)

    def _merge(self, base: dict, patch: dict) -> dict:
        out = copy.deepcopy(base)
        out["version"] = 2
        for section, keys in NUMBERS.items():
            incoming = patch.get(section)
            if not isinstance(incoming, dict):
                continue
            for key, (cast, low, high) in keys.items():
                if key in incoming:
                    out[section][key] = _number(incoming[key], out[section][key], cast, low, high)
        for section, keys in BOOLS.items():
            incoming = patch.get(section)
            if not isinstance(incoming, dict):
                continue
            for key in keys:
                if key in incoming and isinstance(incoming[key], bool):
                    out[section][key] = incoming[key]
        # A repeat shorter than the first prompt would make the cadence collapse.
        out["idle"]["repeat_s"] = max(out["idle"]["repeat_s"], out["idle"]["after_s"])
        return out

    # ── persistence ──────────────────────────────────────────────────────
    def _save_locked(self) -> None:
        if self.path is None:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            body = json.dumps(self._config, ensure_ascii=False, indent=2) + "\n"
            fd, tmp = tempfile.mkstemp(prefix=".audio-", dir=str(self.path.parent))
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write(body)
                    fh.flush()
                    os.fsync(fh.fileno())
                os.chmod(tmp, 0o600)
                os.replace(tmp, self.path)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
        except OSError as exc:
            LOG.warning("动态声音配置保存失败：%s", exc)

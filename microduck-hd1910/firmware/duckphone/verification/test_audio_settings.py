#!/usr/bin/env python3
"""Audio config persistence and validation."""

from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audio_settings import AudioSettings, DEFAULTS  # noqa: E402


class AudioSettingsTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="duckphone-audio-"))
        self.path = self.dir / "audio.json"

    def tearDown(self):
        for p in self.dir.glob("*"):
            p.unlink(missing_ok=True)
        self.dir.rmdir()

    def settings(self) -> AudioSettings:
        return AudioSettings(self.path)

    def test_missing_file_uses_defaults(self):
        self.assertEqual(self.settings().snapshot(), DEFAULTS)

    def test_partial_update_merges_and_persists(self):
        s = self.settings()
        cfg = s.update({"idle": {"after_s": 45, "gesture": False}})
        self.assertEqual(cfg["idle"]["after_s"], 45)
        self.assertFalse(cfg["idle"]["gesture"])
        self.assertEqual(cfg["idle"]["repeat_s"], 300)
        self.assertTrue(self.path.exists())
        self.assertEqual(stat.S_IMODE(os.stat(self.path).st_mode), 0o600)
        self.assertEqual(self.settings().snapshot()["idle"]["after_s"], 45)

    def test_values_are_clamped_and_repeat_follows_after(self):
        s = self.settings()
        cfg = s.update({"idle": {"after_s": 5000, "repeat_s": 1}})
        self.assertEqual(cfg["idle"]["after_s"], 3600)
        self.assertEqual(cfg["idle"]["repeat_s"], 3600)
        cfg = s.update({"fall": {"repeat_s": 0, "max_repeats": 99}})
        self.assertEqual(cfg["fall"]["repeat_s"], 2)
        self.assertEqual(cfg["fall"]["max_repeats"], 20)

    def test_bad_types_fall_back_to_current_values(self):
        s = self.settings()
        s.update({"tilt": {"deg": 45}})
        cfg = s.update({"tilt": {"deg": "hot"}, "idle": {"gesture": "yes"}})
        self.assertEqual(cfg["tilt"]["deg"], 45)
        self.assertTrue(cfg["idle"]["gesture"])

    def test_unknown_keys_are_ignored(self):
        s = self.settings()
        cfg = s.update({"idle": {"nope": 1}, "nonsense": {"x": 2}})
        self.assertEqual(cfg, DEFAULTS)

    def test_snapshot_is_a_copy(self):
        s = self.settings()
        cfg = s.snapshot()
        cfg["idle"]["after_s"] = 1
        self.assertEqual(s.snapshot()["idle"]["after_s"], 30)

    def test_broken_file_falls_back_to_defaults(self):
        self.path.write_text("{not json", encoding="utf-8")
        self.assertEqual(self.settings().snapshot(), DEFAULTS)

    def test_reset_restores_defaults(self):
        s = self.settings()
        s.update({"idle": {"after_s": 45}})
        self.assertEqual(s.reset()["idle"]["after_s"], 30)
        self.assertEqual(self.settings().snapshot()["idle"]["after_s"], 30)

    def test_in_memory_mode_does_not_write(self):
        s = AudioSettings(None)
        cfg = s.update({"idle": {"after_s": 12}})
        self.assertEqual(cfg["idle"]["after_s"], 12)
        self.assertFalse(self.path.exists())

    def test_file_content_keeps_known_sections(self):
        s = self.settings()
        s.update({"actions": {"refusal": False}})
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(raw["version"], 2)
        self.assertFalse(raw["actions"]["refusal"])
        self.assertIn("advanced", raw)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""动作库与播放器：帧序列、收尾与取消。"""

from __future__ import annotations

import sys
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from actions import ACTIONS, ActionPlayer  # noqa: E402


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


class Recorder:
    def __init__(self) -> None:
        self.heads: list[tuple] = []
        self.mouths: list[float] = []
        self.moves: list[tuple[float, float]] = []
        self.poses: list[tuple[float, float, float, bool]] = []
        self.changes: list[tuple[str | None, bool]] = []
        self.sounds: list[str] = []

    def head(self, *values) -> None:
        self.heads.append(tuple(values))

    def mouth(self, value: float) -> None:
        self.mouths.append(value)

    def move(self, vx: float, vyaw: float) -> None:
        self.moves.append((vx, vyaw))

    def pose(self, z: float, roll: float, pitch: float, active: bool) -> None:
        self.poses.append((z, roll, pitch, active))

    def change(self, name: str | None, idle: bool) -> None:
        self.changes.append((name, idle))

    def sound(self, tag: str) -> None:
        self.sounds.append(tag)


def player(rec: Recorder, *, allowed=None, fake: FakeClock | None = None,
           sleep=None) -> ActionPlayer:
    if fake is None:
        return ActionPlayer(rec.head, rec.mouth, rec.move, rec.pose,
                            allowed=allowed, on_change=rec.change, sleep=sleep)
    return ActionPlayer(rec.head, rec.mouth, rec.move, rec.pose,
                        allowed=allowed, on_change=rec.change,
                        clock=fake.clock, sleep=fake.sleep)


class ActionPlayerTest(unittest.TestCase):
    def setUp(self):
        self.rec = Recorder()
        self.fake = FakeClock()
        self.p = player(self.rec, fake=self.fake)

    def test_unknown_action_is_refused(self):
        ok, reason = self.p.run("nope")
        self.assertFalse(ok)
        self.assertIn("未知动作", reason)

    def test_allowed_false_refuses(self):
        p = player(self.rec, allowed=lambda: False)
        ok, reason = p.run("look_up")
        self.assertFalse(ok)
        self.assertIn("未站立", reason)
        self.assertEqual(self.rec.heads, [])

    def test_look_up_ends_at_centre(self):
        ok, _ = self.p.run("look_up")
        self.assertTrue(ok)
        self.p.wait(1.0)
        self.assertEqual(self.rec.heads[0], (0.0, 0.0, 0.0, 0.0))
        self.assertTrue(any(abs(head[1] + 0.30) < 1e-6 for head in self.rec.heads))
        self.assertEqual(self.rec.heads[-1], (0.0, 0.0, 0.0, 0.0))
        self.assertEqual(self.rec.mouths[-1], 0.0)
        self.assertFalse(self.rec.poses[-1][3])

    def test_circle_spans_the_designed_range(self):
        ok, _ = self.p.run("circle")
        self.assertTrue(ok)
        self.p.wait(1.0)
        self.assertTrue(any(head[2] > 0.95 for head in self.rec.heads))
        self.assertTrue(any(head[2] < -0.95 for head in self.rec.heads))
        self.assertTrue(any(head[1] > 0.04 for head in self.rec.heads))
        self.assertTrue(any(head[1] < -0.44 for head in self.rec.heads))
        self.assertEqual(self.rec.heads[-1], (0.0, 0.0, 0.0, 0.0))

    def test_quack_opens_and_closes_the_mouth(self):
        ok, _ = self.p.run("quack")
        self.assertTrue(ok)
        self.p.wait(1.0)
        self.assertTrue(any(value > 0.8 for value in self.rec.mouths))
        self.assertIn(0.0, self.rec.mouths)
        self.assertEqual(self.rec.mouths[-1], 0.0)

    def test_cancel_stops_and_neutralises(self):
        p = ActionPlayer(self.rec.head, self.rec.mouth, self.rec.move, self.rec.pose,
                         on_change=self.rec.change)
        self.assertTrue(p.run("circle")[0])
        time.sleep(0.05)
        p.cancel()
        p.wait(1.0)
        self.assertIsNone(p.current())
        self.assertEqual(self.rec.heads[-1], (0.0, 0.0, 0.0, 0.0))
        self.assertEqual(self.rec.mouths[-1], 0.0)

    def test_start_and_end_are_reported(self):
        self.p.run("look_up", idle=True)
        self.p.wait(1.0)
        self.assertEqual(self.rec.changes[0], ("look_up", True))
        self.assertEqual(self.rec.changes[-1], (None, False))

    def test_allowed_turning_false_stops_the_action(self):
        flag = threading.Event()
        flag.set()
        p = ActionPlayer(self.rec.head, self.rec.mouth, self.rec.move, self.rec.pose,
                         allowed=flag.is_set)
        self.assertTrue(p.run("circle")[0])
        time.sleep(0.05)
        flag.clear()
        p.wait(1.0)
        self.assertIsNone(p.current())
        self.assertEqual(self.rec.heads[-1], (0.0, 0.0, 0.0, 0.0))

    def test_every_action_has_a_sound_and_duration(self):
        for name, entry in ACTIONS.items():
            self.assertIn("sound", entry, name)
            self.assertGreater(entry["duration"], 0, name)
            self.assertEqual(entry["beats"][0], 0.0, name)

    def test_remaining_sound_beats_follow_the_first(self):
        rec = Recorder()
        p = ActionPlayer(rec.head, rec.mouth, rec.move, rec.pose,
                         play_sound=rec.sound, clock=self.fake.clock,
                         sleep=self.fake.sleep)
        self.assertTrue(p.run("quack")[0])
        p.wait(1.0)
        self.assertEqual(rec.sounds, ["chirp", "chirp"])
        rec.sounds.clear()
        self.assertTrue(p.run("circle")[0])
        p.wait(1.0)
        self.assertEqual(rec.sounds, ["greet"] * 4)


if __name__ == "__main__":
    unittest.main()

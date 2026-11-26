#!/usr/bin/env python3
"""Idle head gesture sequence and cancellation."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from head_gesture import CENTER, HeadGesture  # noqa: E402


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class HeadGestureTest(unittest.TestCase):
    def test_i1_looks_up_then_centers(self):
        clock = FakeClock()
        frames = []

        def head(neck, pitch, yaw, roll):
            frames.append((neck, pitch, yaw, roll))

        g = HeadGesture(head, clock=clock, sleep=clock.sleep)
        self.assertTrue(g.run("I1"))
        g.wait()
        self.assertGreaterEqual(len(frames), 12)
        self.assertTrue(all(p == (0.0, -0.30, 0.0, 0.0) for p in frames[:-1]))
        self.assertEqual(frames[-1], CENTER)

    def test_i2_looks_right_then_left(self):
        clock = FakeClock()
        frames = []

        def head(neck, pitch, yaw, roll):
            frames.append((neck, pitch, yaw, roll))

        g = HeadGesture(head, clock=clock, sleep=clock.sleep)
        self.assertTrue(g.run("I2"))
        g.wait()
        yaws = [p[2] for p in frames[:-1]]
        self.assertIn(0.30, yaws)
        self.assertIn(-0.30, yaws)
        self.assertEqual(yaws[0], 0.30)
        self.assertEqual(frames[-1], CENTER)

    def test_cancel_stops_the_gesture_without_centering(self):
        clock = FakeClock()
        frames = []

        def head(*pose):
            frames.append(pose)
            g.cancel()

        g = HeadGesture(head, clock=clock, sleep=clock.sleep)
        g.run("I1")
        g.wait()
        self.assertEqual(frames, [(0.0, -0.30, 0.0, 0.0)])

    def test_not_allowed_means_no_frames(self):
        clock = FakeClock()
        frames = []
        g = HeadGesture(frames.append, allowed=lambda: False, clock=clock, sleep=clock.sleep)
        self.assertFalse(g.run("I1"))
        self.assertEqual(frames, [])

    def test_unknown_gesture_is_ignored(self):
        clock = FakeClock()
        frames = []
        g = HeadGesture(frames.append, clock=clock, sleep=clock.sleep)
        self.assertFalse(g.run("I9"))
        self.assertEqual(frames, [])


if __name__ == "__main__":
    unittest.main()

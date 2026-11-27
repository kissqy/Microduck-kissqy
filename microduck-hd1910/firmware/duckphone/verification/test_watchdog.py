#!/usr/bin/env python3
"""Watchdog and session-ownership tests.

The three behaviours pinned here are the ones that decide whether a runaway robot
is possible: the stick must go quiet within 250 ms, a dead page must lose the
wheel, and only one page may drive at a time.
"""

from __future__ import annotations

import sys
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import server  # noqa: E402


class StubBridge:
    """Records what the bridge would have told robotd."""

    def __init__(self) -> None:
        self.stops = 0
        self.drives: list[tuple[float, float]] = []
        self.padd_control = True
        self.online = True
        self.calls: list[str] = []
        self.heads: list[tuple[float, float, float, float]] = []

    def drive(self, vx, vyaw):
        self.drives.append((vx, vyaw))

    def head(self, neck_pitch, head_pitch, head_yaw, head_roll):
        self.heads.append((neck_pitch, head_pitch, head_yaw, head_roll))

    def sound(self, tag, hold=None):
        self.calls.append(f"sound:{tag}:{hold}")
        return {"accepted": True}

    def stop(self):
        self.stops += 1
        self.calls.append("stop")
        return {"accepted": True}

    def init(self):
        self.calls.append("init")
        return {"accepted": True}

    def enable(self, on):
        self.calls.append(f"enable:{on}")
        return {"accepted": True}

    def relax(self):
        self.calls.append("relax")
        return {"accepted": True}

    def reboot_motors(self, ids=None):
        self.calls.append("reboot")
        return {"accepted": True}

    def snapshot(self):
        return {"t": "state", "padd": False}

    def stop_padd(self):
        self.calls.append("padd")
        return True, ""


class FakeWS:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send_text(self, text):
        import json
        self.sent.append(json.loads(text))

    def close(self, *args, **kwargs):
        pass


def make_session(manager, name="Mate 40 Pro"):
    session = server.Session("s1", FakeWS(), "192.168.110.9")
    session.name = name
    session.ready = True
    manager.add(session)
    return session


class WatchdogTest(unittest.TestCase):
    def setUp(self):
        self.bridge = StubBridge()
        self.manager = server.SessionManager(self.bridge)
        self.watchdog = server.Watchdog(self.manager, self.bridge)

    def tearDown(self):
        self.watchdog.stop()

    def test_first_session_becomes_driver(self):
        session = make_session(self.manager)
        self.assertEqual(self.manager.claim(session), "driver")

    def test_second_session_is_readonly(self):
        first = make_session(self.manager)
        self.manager.claim(first)
        second = server.Session("s2", FakeWS(), "192.168.110.10")
        second.ready = True
        self.manager.add(second)
        self.assertEqual(self.manager.claim(second), "readonly")

    def test_takeover_demotes_the_old_driver(self):
        first = make_session(self.manager)
        self.manager.claim(first)
        second = server.Session("s2", FakeWS(), "192.168.110.10")
        second.ready = True
        second.name = "iPad"
        self.manager.add(second)
        self.manager.claim(second)

        self.manager.promote(second)

        self.assertEqual(second.role, "driver")
        self.assertEqual(first.role, "readonly")
        self.assertIs(self.manager.driver, second)
        self.assertTrue(any(m.get("reason") == "已被另一台设备接管" for m in first.ws.sent))

    def test_driver_leaving_stops_the_robot(self):
        session = make_session(self.manager)
        self.manager.claim(session)
        self.manager.remove(session)
        self.assertEqual(self.bridge.stops, 1)
        self.assertIsNone(self.manager.driver)
        # The head is an absolute intent with no robotd deadman; losing the
        # driver must put it back to neutral too.
        self.assertEqual(self.bridge.heads[-1], (0.0, 0.0, 0.0, 0.0))

    def test_stale_joystick_is_zeroed(self):
        session = make_session(self.manager)
        self.manager.claim(session)
        session.driving = True
        self.watchdog.mark_drive()
        self.watchdog.start()
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline and self.bridge.stops == 0:
            time.sleep(0.02)
        self.assertEqual(self.bridge.stops, 1, "摇杆超时后必须归零")
        self.assertFalse(session.driving)

    def test_live_joystick_is_not_zeroed(self):
        session = make_session(self.manager)
        self.manager.claim(session)
        session.driving = True
        self.watchdog.start()
        for _ in range(12):          # ~600 ms of a held stick
            self.watchdog.mark_drive()
            time.sleep(0.05)
        self.assertEqual(self.bridge.stops, 0)

    def test_stale_head_is_returned_to_neutral(self):
        session = make_session(self.manager)
        self.manager.claim(session)
        self.watchdog.mark_head(True)
        self.watchdog.start()
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline and not self.bridge.heads:
            time.sleep(0.02)
        self.assertEqual(self.bridge.heads[-1], (0.0, 0.0, 0.0, 0.0))

    def test_live_head_is_not_zeroed(self):
        session = make_session(self.manager)
        self.manager.claim(session)
        self.watchdog.start()
        for _ in range(12):          # ~600 ms of a held head pose
            self.watchdog.mark_head(True)
            time.sleep(0.05)
        self.assertFalse(self.bridge.heads, "持续刷新的头部意图不该被回正")

    def test_zero_head_does_not_arm_the_watchdog(self):
        session = make_session(self.manager)
        self.manager.claim(session)
        self.watchdog.mark_head(False)
        self.watchdog.start()
        time.sleep(0.5)
        self.assertFalse(self.bridge.heads)

    def test_silent_session_is_dropped(self):
        session = make_session(self.manager)
        self.manager.claim(session)
        session.last_rx = time.monotonic() - (server.SESSION_TIMEOUT + 1)
        self.watchdog.start()
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline and self.manager.driver is not None:
            time.sleep(0.02)
        self.assertIsNone(self.manager.driver)
        self.assertTrue(session.closed)


class ClampTest(unittest.TestCase):
    def test_clamp_bounds(self):
        self.assertEqual(server.clamp(0.9, -0.25, 0.35), 0.35)
        self.assertEqual(server.clamp(-0.9, -0.25, 0.35), -0.25)
        self.assertEqual(server.clamp(0.1, -0.25, 0.35), 0.1)

    def test_tilt_upright_is_zero(self):
        self.assertAlmostEqual(server.tilt_from_gravity([0, 0, -1]), 0.0, places=3)

    def test_tilt_sideways_is_ninety(self):
        self.assertAlmostEqual(server.tilt_from_gravity([-1, 0, 0]), 90.0, places=3)

    def test_tilt_survives_garbage(self):
        self.assertEqual(server.tilt_from_gravity(None), 0.0)
        self.assertEqual(server.tilt_from_gravity([]), 0.0)
        self.assertEqual(server.tilt_from_gravity(["x"]), 0.0)


class PairingTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.dir = tempfile.mkdtemp(prefix="duckphone-pair-")
        self.path = str(Path(self.dir) / "token")

    def test_token_is_created_and_stable(self):
        first = server.Pairing(self.path)
        self.assertTrue(first.enabled)
        self.assertEqual(len(first.token), 6)
        again = server.Pairing(self.path)
        self.assertEqual(first.token, again.token)
        self.assertEqual(Path(self.path).stat().st_mode & 0o777, 0o600)

    def test_wrong_token_counts_down_then_locks(self):
        pairing = server.Pairing(self.path)
        ok, reason, remaining = pairing.verify("10.0.0.1", "000000" if pairing.token != "000000" else "111111")
        self.assertFalse(ok)
        self.assertEqual(reason, "bad_token")
        self.assertEqual(remaining, server.Pairing.MAX_FAILURES - 1)

        for _ in range(server.Pairing.MAX_FAILURES - 1):
            pairing.verify("10.0.0.1", "nope")
        ok, reason, _ = pairing.verify("10.0.0.1", pairing.token)
        self.assertFalse(ok)
        self.assertEqual(reason, "locked")
        self.assertGreater(pairing.locked_for("10.0.0.1"), 0)

    def test_lockout_is_per_address(self):
        pairing = server.Pairing(self.path)
        for _ in range(server.Pairing.MAX_FAILURES):
            pairing.verify("10.0.0.1", "nope")
        ok, reason, _ = pairing.verify("10.0.0.2", pairing.token)
        self.assertTrue(ok, reason)

    def test_missing_token_does_not_spend_a_try(self):
        pairing = server.Pairing(self.path)
        for _ in range(server.Pairing.MAX_FAILURES + 2):
            ok, reason, remaining = pairing.verify("10.0.0.1", "")
            self.assertFalse(ok)
            self.assertEqual(reason, "need_token")
            self.assertEqual(remaining, server.Pairing.MAX_FAILURES)
        # 空着点几次之后，正确的码仍然能进
        ok, _, _ = pairing.verify("10.0.0.1", pairing.token)
        self.assertTrue(ok)

    def test_auth_can_be_disabled(self):
        pairing = server.Pairing(None, enabled=False)
        ok, _, _ = pairing.verify("10.0.0.1", "")
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()

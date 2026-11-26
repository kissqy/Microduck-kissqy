#!/usr/bin/env python3
"""动态声音引擎的单测：规则、节奏、优先级与总开关。

这些用例不碰 robotd：`play` 直接记下 tag，时钟注入成可推进的假表。
"""

from __future__ import annotations

import copy
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audio_director import AudioDirector  # noqa: E402
from audio_settings import DEFAULTS  # noqa: E402


def state(**overrides) -> dict:
    """一站到位的健康状态：只有用例关心的字段会被改。"""
    s = {
        "pol": "walk", "limp": False, "fall": False, "tilt": 0.0,
        "bat": [7.60, 80.0], "temp": 30.0, "cpu": 40.0,
        "hz": 49.9, "err": 0, "ro": False,
    }
    s.update(overrides)
    return s


class Harness:
    def __init__(self, *, enabled: bool = True, driver: bool = True) -> None:
        self.now = 1000.0
        self.plays: list[str] = []
        self.gestures: list[str] = []
        self.cancelled = 0
        self.enabled = enabled
        self.driver = driver
        self.cfg = copy.deepcopy(DEFAULTS)
        self.d = AudioDirector(
            play=self.play,
            enabled=lambda: self.enabled,
            driver_active=lambda: self.driver,
            settings=lambda: self.cfg,
            gesture=self.gesture,
            cancel_gesture=self.cancel,
            clock=lambda: self.now,
        )
        self.d.start()

    def play(self, tag: str) -> dict:
        self.plays.append(tag)
        return {"accepted": True}

    def gesture(self, name: str) -> bool:
        self.gestures.append(name)
        return True

    def cancel(self) -> None:
        self.cancelled += 1

    def advance(self, seconds: float) -> None:
        self.now += seconds

    def wait(self, count: int, timeout: float = 1.5) -> list[str]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and len(self.plays) < count:
            time.sleep(0.01)
        return list(self.plays)

    def quiet(self, seconds: float = 0.15) -> list[str]:
        time.sleep(seconds)
        return list(self.plays)

    def close(self) -> None:
        self.d.stop()


class SwitchTest(unittest.TestCase):
    def setUp(self):
        self.h = Harness(enabled=False)

    def tearDown(self):
        self.h.close()

    def test_off_by_default_plays_nothing(self):
        self.h.d.on_event("driver_start")
        self.assertEqual(self.h.quiet(), [])

    def test_on_after_switch_greets(self):
        self.h.enabled = True
        self.h.d.on_event("driver_start")
        self.assertEqual(self.h.wait(1), ["greet"])

    def test_turning_off_drops_queued_sound(self):
        self.h.enabled = True
        self.h.d.note_manual()          # 拖住动作声，让队列里留一条
        self.h.d.on_event("refusal")
        self.h.enabled = False
        self.h.d.on_state(state())
        self.assertEqual(self.h.quiet(), [])


class ManualTest(unittest.TestCase):
    def setUp(self):
        self.h = Harness()

    def tearDown(self):
        self.h.close()

    def test_manual_sound_suppresses_action_sounds_for_a_moment(self):
        self.h.d.note_manual()
        self.h.d.on_event("refusal")
        self.assertEqual(self.h.quiet(), [])
        self.h.advance(2.0)
        self.h.d.on_event("refusal")
        self.assertEqual(self.h.wait(1), ["inquire"])

    def test_safety_alarm_still_plays_over_a_manual_sound(self):
        self.h.d.note_manual()
        self.h.d.on_state(state(fall=True))
        self.assertEqual(self.h.wait(1), ["alarm"])


class ActionTest(unittest.TestCase):
    def setUp(self):
        self.h = Harness()

    def tearDown(self):
        self.h.close()

    def test_driver_start_and_end(self):
        self.h.d.on_event("driver_start")
        self.assertEqual(self.h.wait(1), ["greet"])
        self.h.advance(61.0)
        self.h.d.on_event("driver_end")
        self.assertEqual(self.h.wait(2), ["greet", "coo"])

    def test_enable_and_disable_acknowledge(self):
        self.h.d.on_event("enable", on=True)
        self.assertEqual(self.h.wait(1), ["greet"])
        self.h.advance(6.0)
        self.h.d.on_event("enable", on=False)
        self.assertEqual(self.h.wait(2), ["greet", "coo"])

    def test_skill_start_and_end(self):
        self.h.d.on_state(state(pol="roulade"))
        self.assertEqual(self.h.wait(1), ["chirp"])
        self.h.advance(3.0)
        self.h.d.on_state(state(pol="walk"))
        self.assertEqual(self.h.wait(2), ["chirp", "coo"])

    def test_staying_in_a_skill_does_not_repeat(self):
        self.h.d.on_state(state(pol="roulade"))
        self.assertEqual(self.h.wait(1), ["chirp"])
        for _ in range(5):
            self.h.advance(1.0)
            self.h.d.on_state(state(pol="roulade"))
        self.assertEqual(self.h.quiet(), ["chirp"])


class IdleTest(unittest.TestCase):
    def setUp(self):
        self.h = Harness()

    def tearDown(self):
        self.h.close()

    def test_first_after_30s_then_every_300s(self):
        self.h.d.on_state(state())          # 打开开关的第一帧：从这里开始计时
        self.h.advance(29.0)
        self.h.d.on_state(state())
        self.assertEqual(self.h.quiet(), [])

        self.h.advance(1.5)
        self.h.d.on_state(state())
        self.assertEqual(self.h.wait(1), ["coo"])

        self.h.advance(299.0)
        self.h.d.on_state(state())
        self.assertEqual(self.h.quiet(), ["coo"])

        self.h.advance(2.0)
        self.h.d.on_state(state())
        self.assertEqual(self.h.wait(2), ["coo", "inquire"])

    def test_input_restarts_the_clock(self):
        self.h.d.on_state(state())
        self.h.advance(25.0)
        self.h.d.note_input()
        self.h.advance(25.0)                 # 距离上一次输入只有 25 s
        self.h.d.on_state(state())
        self.assertEqual(self.h.quiet(), [])

    def test_idle_is_skipped_when_not_driving_or_not_walking(self):
        self.h.driver = False
        self.h.d.on_state(state())
        self.h.advance(40.0)
        self.h.d.on_state(state())
        self.assertEqual(self.h.quiet(), [])

        self.h.driver = True
        for bad in ({"pol": "limp"}, {"pol": "homing"}, {"limp": True}):
            self.h.d.on_state(state(**bad))
            self.h.advance(40.0)
            self.h.d.on_state(state(**bad))
            self.assertEqual(self.h.quiet(), [], bad)

    def test_idle_is_skipped_while_tilted(self):
        self.h.d.on_state(state(tilt=35.0))
        self.h.advance(31.0)
        self.h.d.on_state(state(tilt=35.0))
        self.assertNotIn("coo", self.h.plays)

    def test_idle_triggers_i1_and_i2_gestures(self):
        self.h.cfg["idle"].update({"after_s": 10, "repeat_s": 15})
        self.h.d.on_state(state())
        self.h.advance(10.5)
        self.h.d.on_state(state())
        self.assertEqual(self.h.wait(1), ["coo"])
        self.h.advance(15.5)
        self.h.d.on_state(state())
        self.assertEqual(self.h.wait(2), ["coo", "inquire"])
        self.assertEqual(self.h.gestures, ["I1", "I2"])

    def test_idle_gesture_can_be_switched_off(self):
        self.h.cfg["idle"].update({"after_s": 10, "gesture": False})
        self.h.d.on_state(state())
        self.h.advance(10.5)
        self.h.d.on_state(state())
        self.assertEqual(self.h.wait(1), ["coo"])
        self.assertEqual(self.h.gestures, [])


class AlarmTest(unittest.TestCase):
    def setUp(self):
        # 驾驶者不在时不应有闲时声音，时间推进只留下告警节奏。
        self.h = Harness(driver=False)

    def tearDown(self):
        self.h.close()

    def test_fall_cadence_is_5s_six_times_then_60s(self):
        self.h.d.on_state(state(fall=True))
        self.assertEqual(self.h.wait(1), ["alarm"])
        for count in range(2, 7):
            self.h.advance(5.1)
            self.h.d.on_state(state(fall=True))
            self.assertEqual(len(self.h.wait(count)), count)

        self.h.advance(30.0)                 # 已过第 6 次 30 s，但还没到 60 s
        self.h.d.on_state(state(fall=True))
        self.assertEqual(self.h.quiet(), ["alarm"] * 6)

        self.h.advance(31.0)
        self.h.d.on_state(state(fall=True))
        self.assertEqual(len(self.h.wait(7)), 7)

    def test_getting_up_answers_with_a_coo(self):
        self.h.d.on_state(state(fall=True))
        self.assertEqual(self.h.wait(1), ["alarm"])
        self.h.advance(4.0)
        self.h.d.on_state(state(fall=False))
        # 2 s of quiet before the fall is considered cleared.
        self.assertEqual(self.h.quiet(), ["alarm"])
        self.h.advance(2.1)
        self.h.d.on_state(state(fall=False))
        self.assertEqual(self.h.wait(2), ["alarm", "coo"])

    def test_fall_flicker_does_not_restart_the_5s_cadence(self):
        self.h.d.on_state(state(fall=True))
        self.assertEqual(self.h.wait(1), ["alarm"])
        self.h.advance(5.1)
        self.h.d.on_state(state(fall=True))
        self.assertEqual(len(self.h.wait(2)), 2)

        # A brief false frame while rolling must not reset the cadence.
        self.h.advance(0.5)
        self.h.d.on_state(state(fall=False))
        self.h.advance(0.5)
        self.h.d.on_state(state(fall=True))
        self.assertEqual(self.h.quiet(), ["alarm", "alarm"])

        self.h.advance(4.2)
        self.h.d.on_state(state(fall=True))
        self.assertEqual(len(self.h.wait(3)), 3)

    def test_tilt_flicker_does_not_repeat_before_10s(self):
        self.h.d.on_state(state(tilt=35.0))
        self.assertEqual(self.h.wait(1), ["alarm"])
        self.h.advance(1.0)
        self.h.d.on_state(state(tilt=20.0))
        self.h.advance(1.0)
        self.h.d.on_state(state(tilt=35.0))
        self.assertEqual(self.h.quiet(), ["alarm"])
        self.h.advance(8.1)
        self.h.d.on_state(state(tilt=35.0))
        self.assertEqual(len(self.h.wait(2)), 2)

    def test_skill_tilt_and_fall_do_not_alarm(self):
        self.h.d.on_state(state())
        self.h.d.on_state(state(pol="roulade", fall=True, tilt=60.0))
        self.assertEqual(self.h.wait(1), ["chirp"])
        self.h.advance(1.0)
        self.h.d.on_state(state(pol="roulade", fall=True, tilt=60.0))
        self.assertEqual(self.h.quiet(), ["chirp"])

        # Still down after the skill ends: the next walk frame raises E1.
        self.h.d.on_state(state(pol="walk", fall=True, tilt=60.0))
        self.assertIn("alarm", self.h.wait(2))

    def test_fall_cadence_comes_from_settings(self):
        self.h.cfg["fall"].update({"repeat_s": 2, "max_repeats": 2, "tail_s": 10})
        self.h.d.on_state(state(fall=True))
        self.assertEqual(self.h.wait(1), ["alarm"])
        self.h.advance(2.1)
        self.h.d.on_state(state(fall=True))
        self.assertEqual(len(self.h.wait(2)), 2)
        self.h.advance(2.1)
        self.h.d.on_state(state(fall=True))
        self.assertEqual(self.h.quiet(), ["alarm", "alarm"])   # tail, not 2 s
        self.h.advance(8.1)
        self.h.d.on_state(state(fall=True))
        self.assertEqual(len(self.h.wait(3)), 3)

    def test_alert_and_action_switches_disable_their_category(self):
        self.h.cfg["alerts"]["fall"] = False
        self.h.d.on_state(state(fall=True))
        self.assertEqual(self.h.quiet(), [])

        self.h.cfg["actions"]["refusal"] = False
        self.h.d.on_event("refusal")
        self.assertEqual(self.h.quiet(), [])

    def test_tilt_alarm_repeats_every_10s(self):
        self.h.d.on_state(state(tilt=35.0))
        self.assertEqual(self.h.wait(1), ["alarm"])
        self.h.advance(9.0)
        self.h.d.on_state(state(tilt=35.0))
        self.assertEqual(self.h.quiet(), ["alarm"])
        self.h.advance(2.0)
        self.h.d.on_state(state(tilt=35.0))
        self.assertEqual(self.h.wait(2), ["alarm", "alarm"])

    def test_low_battery_warns_once_until_it_recovers(self):
        self.h.d.on_state(state(bat=[7.0, 20.0]))
        self.assertEqual(self.h.wait(1), ["inquire"])
        for _ in range(3):
            self.h.advance(60.0)
            self.h.d.on_state(state(bat=[7.0, 20.0]))
        self.assertEqual(self.h.quiet(), ["inquire"])
        self.h.d.on_state(state(bat=[7.6, 40.0]))
        self.h.advance(601.0)                # 冷却 10 分钟，恢复电量后才会再提醒
        self.h.d.on_state(state(bat=[7.0, 20.0]))
        self.assertEqual(self.h.wait(2), ["inquire", "inquire"])

    def test_bus_errors_raise_an_alarm(self):
        self.h.d.on_state(state(err=3))
        self.assertEqual(self.h.wait(1), ["alarm"])

    def test_read_only_state_never_speaks(self):
        self.h.d.on_state(state(ro=True, fall=True, tilt=90.0))
        self.assertEqual(self.h.quiet(), [])


if __name__ == "__main__":
    unittest.main()

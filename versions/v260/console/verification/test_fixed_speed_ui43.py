"""Fixed walking translation, independent of retired speed preferences."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from controls import ControlError
from remote_input import AXES, Input
from service_control import validate


class Robot:
    def __init__(self):
        self.calls = []

    def notify(self, calls):
        self.calls.extend(calls)


class FixedSpeedTests(unittest.TestCase):
    def send(self, report, **axes):
        robot = Robot()
        with patch('remote_input.drive_reader', return_value=lambda: report):
            control = Input(robot, lambda: 0)
        frame = {'axes': dict.fromkeys(AXES, 0), 'buttons': []}
        frame['axes'].update(axes)
        result = control.command({'action': 'state', 'owner': 'fixed-speed-ui43', 'frame': frame})
        move = next(params for method, params in robot.calls if method == 'robot.move')
        return move, result

    def test_forward_backward_and_both_strafes_use_point_three(self):
        for axes, expected in [
            ({'ly': -1}, (.3, 0)),
            ({'ly': 1}, (-.3, 0)),
            ({'lx': -1}, (0, .3)),
            ({'lx': 1}, (0, -.3)),
        ]:
            with self.subTest(axes=axes):
                move, result = self.send({}, **axes)
                self.assertTrue(result['accepted'])
                self.assertEqual((move['vx'], move['vy']), expected)
                self.assertEqual(move['vyaw'], 0)

    def test_old_or_invalid_speed_report_cannot_change_walking(self):
        for report in [
            {'saved_speed': .1, 'speed': .1},
            {'saved_speed': .2, 'speed': .2},
            {'saved_speed': 'broken', 'speed': None, 'error': 'old settings invalid'},
            {'supported': False},
            {},
        ]:
            with self.subTest(report=report):
                move, result = self.send(report, lx=1, ly=-1)
                self.assertTrue(result['accepted'])
                self.assertEqual(move, {'vx': .3, 'vy': -.3, 'vyaw': 0})

    def test_partial_deflection_retains_proportional_control(self):
        move, _ = self.send({}, lx=.5, ly=.5, rx=.5)
        self.assertEqual(move, {'vx': -.15, 'vy': -.15, 'vyaw': -.75})

    def test_neutral_deadzone_and_turning_limits_are_preserved(self):
        move, _ = self.send({}, lx=.09, ly=-.09, rx=1)
        self.assertEqual(move, {'vx': 0, 'vy': 0, 'vyaw': -1.5})
        move, _ = self.send({}, rx=-1)
        self.assertEqual(move, {'vx': 0, 'vy': 0, 'vyaw': 1.5})
        move, _ = self.send({})
        self.assertEqual(move, {'vx': 0, 'vy': 0, 'vyaw': 0})

    def test_recorder_status_is_still_forwarded(self):
        recorder = {'available': True, 'phase': 'recording', 'elapsed_ms': 1000}
        _, result = self.send({'recorder': recorder}, ly=-1)
        self.assertEqual(result['drive_speed']['recorder'], recorder)

    def test_retired_speed_action_is_rejected(self):
        for speed in (.1, .2, .3):
            with self.subTest(speed=speed), self.assertRaises(ControlError) as caught:
                validate({'action': 'set-drive-speed', 'speed': speed, 'supported': True})
            self.assertEqual(caught.exception.status, 400)
        command = {'action': 'set-pad-settings', 'mouth_percent': 60, 'head_rad': .5, 'supported': True}
        self.assertEqual(validate(command), command)


if __name__ == '__main__':
    unittest.main()

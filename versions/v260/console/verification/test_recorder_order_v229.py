"""A resumed command waiter must not overwrite a newer SSH recorder status."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from controls import ControlError, Transport


def recorder_status(seconds, accepted=True):
    return {
        'accepted': accepted,
        'available': True,
        'event_authoritative': True,
        'real_connected': True,
        'drive_speed': {'recorder': {
            'available': True, 'pid': 123,
            't_ms': 100_000 + seconds * 1000,
            'checked_ms': 100_010 + seconds * 1000,
            'phase': 'recording', 'elapsed_ms': seconds * 1000,
            'duration_ms': 0, 'has_last': False, 'reason': '正在录制',
        }},
    }


class OrderedChannel:
    """Match _read: publish an answer, then a newer event before waiter resumes."""
    error = None

    def __init__(self, transport, clock, accepted=True):
        self.transport, self.clock = transport, clock
        self.old = recorder_status(12, accepted)
        self.new = recorder_status(13)
        self.requests = []

    def request(self, command):
        self.requests.append(command)
        self.clock[0] = 11.0
        self.transport._input_status(self.old)
        self.clock[0] = 12.0
        self.transport._input_status(self.new)
        self.clock[0] = 13.0
        return self.old


class RecorderOrderTests(unittest.TestCase):
    def setup_transport(self, accepted=True):
        clock = [10.0]
        transport = Transport()
        channel = OrderedChannel(transport, clock, accepted)
        transport.input_channel = channel
        transport._open_input = lambda create=True: True
        notices = []
        transport.subscribe_input_status(lambda status: notices.append((
            status['drive_speed']['recorder']['elapsed_ms'], transport.pad_status_at)))
        return transport, channel, clock, notices

    def assert_newer_status_preserved(self, transport, notices):
        self.assertEqual(transport.pad_status['drive_speed']['recorder']['elapsed_ms'], 13_000)
        self.assertEqual(transport.pad_status['drive_speed']['recorder']['checked_ms'], 113_010)
        self.assertEqual(transport.pad_status_at, 12.0)
        self.assertEqual(notices, [(12_000, 11.0), (13_000, 12.0)])

    def test_call_keeps_newer_cache_and_returns_original_receipt(self):
        for action in ('webpad_state', 'webpad_close'):
            for accepted in (True, False):
                with self.subTest(action=action, accepted=accepted):
                    transport, channel, clock, notices = self.setup_transport(accepted)
                    with patch('controls.time.monotonic', side_effect=lambda: clock[0]):
                        result = transport.call({'action': action, 'owner': 'test', 'frame': {}})
                    self.assertIs(result, channel.old)
                    self.assertEqual(result['drive_speed']['recorder']['elapsed_ms'], 12_000)
                    self.assertIs(result['accepted'], accepted)
                    self.assertIn('control_rtt_ms', result)
                    self.assertEqual(len(channel.requests), 1)
                    self.assert_newer_status_preserved(transport, notices)

    def test_pause_keeps_newer_cache_and_does_not_notify_old_receipt_again(self):
        transport, channel, clock, notices = self.setup_transport()
        with patch('controls.time.monotonic', side_effect=lambda: clock[0]):
            self.assertIsNone(transport.pause_input())
        self.assertEqual(channel.requests, [{'action': 'reset'}])
        self.assert_newer_status_preserved(transport, notices)

    def test_pause_refusal_still_raises_without_replacing_newer_status(self):
        transport, channel, clock, notices = self.setup_transport(False)
        with patch('controls.time.monotonic', side_effect=lambda: clock[0]):
            with self.assertRaises(ControlError):
                transport.pause_input()
        self.assertEqual(channel.requests, [{'action': 'reset'}])
        self.assert_newer_status_preserved(transport, notices)


if __name__ == '__main__':
    unittest.main()

"""Hotspot scheduling is confirmed, credential-safe and independent of IMU state."""
import base64
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import service_control
from controls import ControlError
from service_control import ServiceController, ServiceTransport, validate
from telemetry import Store


COMMAND = {'action': 'enable-hotspot', 'supported': True, 'confirmed': True}
RECEIPT = {'accepted': True, 'queued': True, 'delay_seconds': 5,
           'ssid': 'Microduck-kissqy', 'password': '12345678',
           'portal_url': 'http://10.42.0.1:8088', 'unit': 'microduck-hotspot-reset',
           'message': '切换任务已调度，热点状态尚待手机确认'}


class InlineThread:
    def __init__(self, target, args=(), **_):
        self.target, self.args = target, args

    def start(self):
        self.target(*self.args)


class HotspotServiceTests(unittest.TestCase):
    def controller(self, receipt=RECEIPT, error=None):
        store = Store()
        store.system_log = Mock()
        transport = SimpleNamespace(
            enable_hotspot=Mock(return_value=receipt, side_effect=error),
            channel=SimpleNamespace(disconnect=Mock()),
            call=Mock(side_effect=AssertionError('network action must not send robotd commands')),
        )
        controls = SimpleNamespace(suspend_connections=Mock(), resume_connections=Mock(),
                                   reconnect_after_service=Mock(), pause_input=Mock())
        return ServiceController(store, transport=transport, controls=controls), transport, controls

    def submit(self, controller, command=COMMAND, seq=1):
        with patch('service_control.threading.Thread', InlineThread):
            return controller.handle({'client': 'hotspot-ui44', 'seq': seq,
                                      'command': dict(command)})

    def test_requires_explicit_boolean_confirmation_and_known_fields(self):
        self.assertEqual(validate(dict(COMMAND)), COMMAND)
        for command in [
            {'action': 'enable-hotspot', 'supported': True},
            {**COMMAND, 'confirmed': False}, {**COMMAND, 'confirmed': 1},
            {**COMMAND, 'supported': False}, {**COMMAND, 'supported': 1},
            {**COMMAND, 'argv': ['reboot']},
        ]:
            with self.subTest(command=command), self.assertRaises(ControlError) as caught:
                validate(command)
            self.assertEqual(caught.exception.status, 400)

    def test_no_imu_or_robotd_feedback_required_and_secrets_stay_out_of_job(self):
        controller, transport, controls = self.controller()
        self.assertFalse(controller.store.snapshot().get('service_sample_fresh'))
        answer = self.submit(controller, {**COMMAND, 'sudo_password': 'private-sudo'})
        self.assertTrue(answer['accepted'])
        transport.enable_hotspot.assert_called_once_with(password='private-sudo')
        self.assertEqual(controller.job['status'], 'completed')
        self.assertEqual(controller.job['result'], RECEIPT)
        self.assertNotIn('private-sudo', json.dumps(controller.job))
        self.assertNotIn('private-sudo', json.dumps(list(controller.store.service_commands)))
        self.assertNotIn('private-sudo', str(controller.store.system_log.add.call_args_list))
        self.assertTrue(controller.store.connection_paused.is_set())
        controls.suspend_connections.assert_called_once_with()
        transport.channel.disconnect.assert_called_once_with()
        controls.pause_input.assert_not_called()
        transport.call.assert_not_called()
        controls.resume_connections.assert_not_called()
        controls.reconnect_after_service.assert_not_called()
        self.assertFalse(controller.stopping)
        self.assertFalse(controller.busy)
        self.assertFalse(controller.store.service_operation)

    def test_failed_or_ambiguous_request_never_retries_or_pauses_connection(self):
        for error in (ControlError('R5 组件缺失；未清除 Wi-Fi', 503),
                      TimeoutError('SSH 回执丢失；实际结果未知，未自动重试')):
            with self.subTest(error=error):
                controller, transport, controls = self.controller(error=error)
                self.submit(controller)
                self.assertEqual(controller.job['status'], 'error')
                self.assertIn(str(error), controller.job['error'])
                transport.enable_hotspot.assert_called_once_with(password=None)
                self.assertFalse(controller.store.connection_paused.is_set())
                controls.suspend_connections.assert_not_called()
                transport.channel.disconnect.assert_not_called()
                transport.call.assert_not_called()
                controls.reconnect_after_service.assert_not_called()

    def test_missing_or_nonboolean_queue_confirmation_is_not_success(self):
        for receipt in (None, {}, {'accepted': True}, {'accepted': False, 'queued': True},
                        {'accepted': True, 'queued': 1}, {'accepted': 1, 'queued': True}):
            with self.subTest(receipt=receipt):
                controller, transport, controls = self.controller(receipt=receipt)
                self.submit(controller)
                self.assertEqual(controller.job['status'], 'error')
                self.assertIn('未确认热点切换任务已调度', controller.job['error'])
                self.assertNotIn('result', controller.job)
                self.assertFalse(controller.store.connection_paused.is_set())
                controls.suspend_connections.assert_not_called()
                transport.channel.disconnect.assert_not_called()

    def test_existing_pause_blocks_repeat_reset_until_explicit_reconnect(self):
        controller, transport, controls = self.controller()
        self.submit(controller)
        with self.assertRaises(ControlError):
            self.submit(controller, seq=2)
        transport.enable_hotspot.assert_called_once()
        answer = self.submit(controller, {'action': 'resume-connection'}, seq=3)
        self.assertTrue(answer['accepted'])
        self.assertFalse(controller.store.connection_paused.is_set())
        controls.resume_connections.assert_called_once()
        transport.enable_hotspot.assert_called_once()

    def test_streamed_r5_payload_uses_existing_sudo_stdin_and_single_request(self):
        transport = ServiceTransport.__new__(ServiceTransport)
        transport.log = None
        transport.credential = Mock()
        transport.channel = Mock()
        transport.channel.request.return_value = {
            'returncode': 0, 'stderr': '', 'stdout': json.dumps(RECEIPT)}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            helper = 'print("test helper")\n'
            original = b'#!/bin/bash\n# exact R5 fixture\n'
            (root / 'hotspot_control.py').write_text(helper)
            resource = root / 'resources/wifi-r5/microduck-public-image.sh'
            resource.parent.mkdir(parents=True)
            resource.write_bytes(original)
            with patch.object(service_control, 'ROOT', root):
                result = transport.enable_hotspot(password='private-sudo')
        self.assertEqual(result, RECEIPT)
        transport.channel.request.assert_called_once()
        request = transport.channel.request.call_args.args[0]
        self.assertEqual(request['argv'][:8],
                         ['sudo', '-S', '-p', '', '--', 'python3', '-u', '-c'])
        self.assertEqual(request['argv'][8], helper)
        self.assertEqual(gzip.decompress(base64.b64decode(request['argv'][9])), original)
        self.assertNotIn('private-sudo', repr(request['argv']))
        self.assertEqual(request['input'], 'private-sudo\n')
        self.assertNotIn('progress', request)
        transport.credential.remember.assert_called_once_with('private-sudo')


if __name__ == '__main__':
    unittest.main()

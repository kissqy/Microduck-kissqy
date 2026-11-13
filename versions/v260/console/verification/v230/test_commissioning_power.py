import importlib.util
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from test_support import FW, PC
sys.path.insert(0, str(PC))
from service_control import ServiceController, ServiceTransport, validate
from controls import ControlError
from telemetry import Store

spec = importlib.util.spec_from_file_location('v230_firmware_runtime', FW / 'runtime.py')
runtime = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(FW))
spec.loader.exec_module(runtime)


class CommissioningPowerTests(unittest.TestCase):
    def test_live_commissioning_uses_native_stop_and_poweroff(self):
        events = []
        def rpc(method, *args, **kwargs):
            events.append(method)
            if method == 'robot.busStatus':
                return {'mode': 'commissioning', 'torque_state': 'off'}
            self.assertEqual(args, ({'action': 'shutdown'},))
            return {'power_action': 'poweroff', 'scheduled': True, 'torque': 'off'}
        with patch.object(runtime, 'rpc', side_effect=rpc), \
             patch.object(runtime, 'power') as power:
            result = runtime.commissioning_shutdown()
        self.assertEqual(events, ['robot.busStatus', 'robot.busCommand'])
        power.assert_not_called()
        self.assertIs(result['torque_off_confirmed'], True)
        self.assertEqual(result['shutdown_path'], 'commissioning.systemctl')

    def test_motion_unknown_and_unconfirmed_relax_never_call_os(self):
        for mode in ('motion', None):
            with self.subTest(mode=mode), patch.object(runtime, 'rpc', return_value={'mode': mode}), \
                 patch.object(runtime, 'relax_confirmed') as relax, patch.object(runtime, 'power') as power:
                with self.assertRaises(RuntimeError): runtime.commissioning_shutdown()
                relax.assert_not_called(); power.assert_not_called()
        with patch.object(runtime, 'rpc', side_effect=[{'mode': 'commissioning'}, RuntimeError('torque unconfirmed')]), \
             patch.object(runtime, 'power') as power:
            with self.assertRaisesRegex(RuntimeError, 'torque'): runtime.commissioning_shutdown()
            power.assert_not_called()

    def test_mode_change_before_native_command_never_uses_os_fallback(self):
        with patch.object(runtime, 'rpc', side_effect=[{'mode': 'commissioning'}, RuntimeError('not commissioning')]), \
             patch.object(runtime, 'relax_confirmed'), patch.object(runtime, 'power') as power:
            with self.assertRaises(RuntimeError): runtime.commissioning_shutdown()
            power.assert_not_called()

    def transport(self, mode):
        transport = ServiceTransport.__new__(ServiceTransport)
        transport.log = None
        transport.channel = Mock()
        transport.channel.request.return_value = {'id': 1, 'result': {'mode': mode}}
        transport.call = Mock(return_value={'accepted': True})
        transport.manage = Mock(return_value={'scheduled': True, 'shutdown_path': 'commissioning.systemctl',
                                            'torque_off_confirmed': True})
        return transport

    def test_native_motion_path_preserved(self):
        transport = self.transport('motion')
        result = transport.power('shutdown', password='fixture-password')
        self.assertEqual(result['shutdown_path'], 'robot.shutdown')
        transport.call.assert_called_once_with({'action': 'shutdown'})
        transport.manage.assert_not_called()

    def test_commissioning_uses_existing_privileged_helper(self):
        transport = self.transport('commissioning')
        result = transport.power('shutdown', password='fixture-password')
        transport.manage.assert_called_once_with('power-commissioning', 'shutdown', password='fixture-password')
        transport.call.assert_not_called()
        self.assertIs(result['accepted'], True)
        self.assertIs(result['shutdown_requested'], True)

    def test_unknown_mode_and_rejected_helper_do_not_fall_back(self):
        transport = self.transport('unknown')
        with self.assertRaises(ControlError): transport.power('shutdown')
        transport.call.assert_not_called(); transport.manage.assert_not_called()
        transport = self.transport('commissioning'); transport.manage.return_value = {'scheduled': True}
        with self.assertRaises(ControlError): transport.power('shutdown')
        transport.call.assert_not_called()

    def test_commissioning_mode_query_crosses_the_real_unix_relay(self):
        # Reuse V229's socketpair fixture: this detects relay allow-list errors.
        fixture_spec = importlib.util.spec_from_file_location('v230_native_relay_fixture', PC / 'verification/test_shutdown_ui45.py')
        fixture = importlib.util.module_from_spec(fixture_spec)
        fixture_spec.loader.exec_module(fixture)
        transport = self.transport('commissioning')
        transport.channel = fixture.PairChannel({'id': 1, 'result': {'mode': 'commissioning'}})
        transport.power('shutdown')
        self.assertEqual(transport.channel.wire, [{'jsonrpc': '2.0', 'id': 1,
                                                'method': 'robot.busStatus', 'params': {}}])
        transport.manage.assert_called_once_with('power-commissioning', 'shutdown', password=None)

    def test_controller_accepts_commissioning_receipt_and_pauses_after_acceptance(self):
        class InlineThread:
            def __init__(self, target, args=(), **_): self.target, self.args = target, args
            def start(self): self.target(*self.args)
        receipt = {'accepted': True, 'shutdown_requested': True, 'shutdown_path': 'commissioning.systemctl',
                   'torque_off_confirmed': True, 'scheduled': True}
        transport = SimpleNamespace(power=Mock(return_value=receipt), channel=SimpleNamespace(disconnect=Mock()))
        controls = SimpleNamespace(suspend_connections=Mock())
        store = Store(); store.system_log = Mock()
        controller = ServiceController(store, transport=transport, controls=controls)
        with patch('service_control.threading.Thread', InlineThread):
            controller.handle({'client': 'v230-power', 'seq': 1, 'command': {'action': 'shutdown', 'sudo_password': 'fixture'}})
        self.assertEqual(controller.job['status'], 'completed')
        transport.power.assert_called_once_with('shutdown', password='fixture')
        self.assertTrue(store.connection_paused.is_set())
        controls.suspend_connections.assert_called_once()
        self.assertEqual(validate({'action': 'shutdown', 'sudo_password': 'fixture'})['action'], 'shutdown')


if __name__ == '__main__': unittest.main()

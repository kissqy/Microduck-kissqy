"""Regression coverage for the shipped commissioning shutdown helper."""
import importlib.util
import json
from pathlib import Path
import socket
import sys
import threading
import unittest
from unittest.mock import Mock, call, patch

PC = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PC / 'verification' / 'v230'))
from test_support import FW
sys.path.insert(0, str(FW))
spec = importlib.util.spec_from_file_location('v256_runtime', FW / 'runtime.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)

RECEIPT = {'power_action': 'poweroff', 'scheduled': True,
           'delay_seconds': 3, 'torque': 'off'}
STATUS = {'mode': 'commissioning', 'torque_state': 'unknown',
          'torque_off_pending': 'previous torque readback pending'}


class PairSocket:
    def __init__(self, stream): self.stream = stream
    def __enter__(self): return self
    def __exit__(self, *_): self.stream.close()
    def connect(self, path):
        if path != '/run/robotd.sock': raise AssertionError(path)
    def settimeout(self, value): self.stream.settimeout(value)
    def sendall(self, data): self.stream.sendall(data)
    def makefile(self, mode): return self.stream.makefile(mode)


class CommissioningShutdownRegressionTests(unittest.TestCase):
    def test_previous_torque_timeout_uses_native_shutdown_instead(self):
        # The old motion relax ACK never releases a commissioning movement.
        # Advancing its clock reproduces the user's exact eight-second failure.
        def endpoint(method, params=None, **_):
            if method == 'robot.busStatus': return dict(STATUS)
            if method == 'robot.relax': return {'accepted': True}
            self.assertEqual((method, params), ('robot.busCommand', {'action': 'shutdown'}))
            return dict(RECEIPT)
        with patch.object(runtime, 'rpc', side_effect=endpoint) as rpc, \
             patch.object(runtime.time, 'monotonic', side_effect=[0, .1, 9]), \
             patch.object(runtime.time, 'sleep'), patch.object(runtime, 'power') as power:
            result = runtime.commissioning_shutdown()
        self.assertEqual(rpc.call_args_list, [call('robot.busStatus', timeout=3),
                                             call('robot.busCommand', {'action': 'shutdown'})])
        self.assertEqual(result['shutdown_path'], 'commissioning.systemctl')
        self.assertIs(result['torque_off_confirmed'], True)
        self.assertEqual(result['delay_seconds'], 3)
        power.assert_not_called()

    def test_already_off_still_uses_native_atomic_stop_and_schedule(self):
        status = {'mode': 'commissioning', 'torque_state': 'off'}
        with patch.object(runtime, 'rpc', side_effect=[status, dict(RECEIPT)]) as rpc, \
             patch.object(runtime, 'relax_confirmed') as relax, \
             patch.object(runtime, 'power') as power:
            self.assertTrue(runtime.commissioning_shutdown()['scheduled'])
        self.assertEqual(rpc.call_count, 2)
        relax.assert_not_called(); power.assert_not_called()

    def test_unconfirmed_native_receipts_do_not_become_success(self):
        for invalid in (None, True, {}, {'scheduled': True},
                        {**RECEIPT, 'scheduled': 1},
                        {**RECEIPT, 'scheduled': False},
                        {**RECEIPT, 'torque': 'unknown'},
                        {**RECEIPT, 'power_action': 'reboot'}):
            with self.subTest(receipt=invalid), \
                 patch.object(runtime, 'rpc', side_effect=[dict(STATUS), invalid]), \
                 patch.object(runtime, 'power') as power:
                with self.assertRaises(RuntimeError): runtime.commissioning_shutdown()
                power.assert_not_called()

    def test_motion_or_unknown_mode_never_sends_commissioning_shutdown(self):
        for status in ({'mode': 'motion'}, {}, None):
            with self.subTest(status=status), patch.object(runtime, 'rpc', return_value=status) as rpc:
                with self.assertRaises(RuntimeError): runtime.commissioning_shutdown()
                rpc.assert_called_once_with('robot.busStatus', timeout=3)

    def test_native_torque_failure_or_mode_change_never_falls_back(self):
        for error in ('torque-off not confirmed: ID 22',
                      'raw bus commands require the running robotd commissioning mode'):
            with self.subTest(error=error), \
                 patch.object(runtime, 'rpc', side_effect=[dict(STATUS), RuntimeError(error)]), \
                 patch.object(runtime, 'power') as power:
                with self.assertRaisesRegex(RuntimeError, error): runtime.commissioning_shutdown()
                power.assert_not_called()

    def test_missing_native_ack_is_not_retried_or_reported_as_shutdown(self):
        with patch.object(runtime, 'rpc', side_effect=[dict(STATUS), ConnectionError('closed before ACK')]) as rpc, \
             patch.object(runtime, 'power') as power:
            with self.assertRaisesRegex(ConnectionError, 'before ACK'): runtime.commissioning_shutdown()
        self.assertEqual(rpc.call_count, 2); power.assert_not_called()

    def test_real_unix_wire_uses_the_existing_commissioning_command(self):
        wire, errors, clients, servers, workers = [], [], [], [], []
        for result in (dict(STATUS), dict(RECEIPT)):
            client, server = socket.socketpair()
            clients.append(PairSocket(client)); servers.append(server)
            def endpoint(stream=server, reply=result):
                try:
                    with stream, stream.makefile('rb') as reader:
                        request = json.loads(reader.readline())
                        wire.append(request)
                        stream.sendall((json.dumps({'jsonrpc': '2.0', 'id': request['id'],
                                                   'result': reply}) + '\n').encode())
                except Exception as exc: errors.append(exc)
            worker = threading.Thread(target=endpoint, daemon=True)
            worker.start(); workers.append(worker)
        try:
            with patch.object(runtime.socket, 'socket', side_effect=clients), \
                 patch.object(runtime, 'power') as power:
                result = runtime.commissioning_shutdown()
            power.assert_not_called()
        finally:
            for client in clients: client.stream.close()
            for server in servers: server.close()
            for worker in workers: worker.join(2)
        self.assertFalse(errors)
        self.assertFalse(any(worker.is_alive() for worker in workers))
        self.assertEqual(wire, [
            {'jsonrpc': '2.0', 'id': 1, 'method': 'robot.busStatus', 'params': {}},
            {'jsonrpc': '2.0', 'id': 1, 'method': 'robot.busCommand', 'params': {'action': 'shutdown'}}])
        self.assertTrue(result['torque_off_confirmed'])


if __name__ == '__main__': unittest.main()

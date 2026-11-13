"""Byte tunnels: ownership, startup failure and cancellation without remote code."""
import contextlib
import io
from pathlib import Path
import socket
import sys
import threading
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'console'))
import socket_transport as transport


class Child:
    def __init__(self, lines):
        self.stderr = io.BytesIO(lines)
        self.returncode = None
        self.terminations = 0

    def poll(self): return self.returncode
    def terminate(self): self.terminations += 1; self.returncode = 0
    def kill(self): self.returncode = -9
    def wait(self, timeout=None): return self.returncode


class TunnelTests(unittest.TestCase):
    def setUp(self):
        self.assertFalse(transport._registry)
        self.children = []
        self.sockets = []
        self.reservation = MagicMock()
        self.reservation.__enter__.return_value = self.reservation
        self.reservation.getsockname.return_value = ('127.0.0.1', 53117)

    def tearDown(self):
        for wrapper in self.sockets: wrapper.close()
        for forward in list(transport._registry.values()): forward.close()
        transport._registry.clear()

    def child(self, command, **kwargs):
        self.assertEqual(command[-1], 'radxa@duck')
        self.assertIn('-N', command)
        self.assertIsNone(kwargs.get('shell'))
        child = Child(b'debug1: Local forwarding listening on 127.0.0.1 port 53117.\r\n'
                      b'debug1: channel 0: new port-listener [port listener]\r\n'
                      b'debug1: Entering interactive session.\r\n')
        self.children.append(child)
        return child

    @contextlib.contextmanager
    def forwarded(self, child=None):
        with patch.object(transport.socket, 'socket', return_value=self.reservation), \
             patch.object(transport.subprocess, 'Popen', side_effect=child or self.child) as popen, \
             patch.object(transport.socket, 'create_connection', side_effect=lambda *a, **k: MagicMock()) as connect:
            yield popen, connect

    def open(self, path='/run/robotd/robot.sock', **kwargs):
        wrapper = transport.open_remote_socket('duck', path, **kwargs)
        self.sockets.append(wrapper)
        return wrapper

    def test_forward_command_keeps_auth_and_loopback_only_without_a_remote_command(self):
        command = transport.forward_command('duck', '/run/robotd/robot.sock', 53117)
        self.assertEqual(command[-1], 'radxa@duck')
        self.assertEqual(command[command.index('-L') + 1], '127.0.0.1:53117:/run/robotd/robot.sock')
        self.assertIn('ExitOnForwardFailure=yes', command)
        self.assertIn('StrictHostKeyChecking=accept-new', command)
        self.assertIn('-N', command)
        self.assertFalse(any('python' in part or part in ('sudo','sh','bash','-W') for part in command))
        for path in ('relative', '/run/x\nother', '/run/x:123', '/'+'x'*104):
            with self.assertRaises(ValueError): transport.forward_command('duck', path, 53117)

    def test_endpoint_is_shared_and_last_stream_close_owns_ssh_teardown(self):
        with self.forwarded() as (popen, connect):
            first, second = self.open(), self.open()
            self.assertIs(first.forward, second.forward)
            self.assertEqual((popen.call_count, connect.call_count), (1, 2))
            first.socket.sendall.assert_not_called()
            second.socket.sendall.assert_not_called()
            first.close(); first.close()
            self.assertEqual(self.children[0].terminations, 0)
            self.assertEqual(second.forward.refs, 1)
            second.close()
            self.assertEqual(self.children[0].terminations, 1)
            self.assertFalse(transport._registry)

    def test_a_different_endpoint_is_independent_and_does_not_wake_an_input_socket(self):
        with self.forwarded() as (popen, connect):
            telemetry = self.open()
            self.assertEqual(popen.call_count, 1)
            self.assertTrue(all('/run/microduck-webpad' not in str(call) for call in popen.call_args_list))
            input_stream = self.open('/run/microduck-webpad.sock')
            self.assertEqual(popen.call_count, 2)
            self.assertIsNot(telemetry.forward, input_stream.forward)
            input_stream.close()
            self.assertEqual(self.children[0].terminations, 0)

    def test_a_failed_bind_debug_line_is_not_readiness_and_never_connects_a_foreign_port(self):
        child = Child(b'debug1: Local forwarding listening on 127.0.0.1 port 53117.\n'
                      b'bind: Address already in use\n'
                      b'Could not request local forwarding.\n')
        with self.forwarded(child=lambda *a, **k: child) as (popen, connect):
            with self.assertRaisesRegex(transport.SSHConnectError, 'Address already in use'):
                self.open(timeout=.2)
            connect.assert_not_called()
            self.assertEqual(child.terminations, 1)
            self.assertFalse(transport._registry)

    def test_unrelated_listener_debug_does_not_release_the_requested_endpoint(self):
        child = Child(b'debug1: Local forwarding listening on 127.0.0.1 port 53118.\n'
                      b'debug1: Entering interactive session.\n')
        with self.forwarded(child=lambda *a, **k: child) as (_, connect):
            with self.assertRaises(transport.SSHConnectError): self.open(timeout=.2)
            connect.assert_not_called()

    def test_failure_does_not_retry_or_leave_a_process_and_cancellation_does_not_start_one(self):
        with self.forwarded(child=lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError('ssh'))) as (popen, connect):
            with self.assertRaises(transport.SSHConnectError): self.open(timeout=.2)
            self.assertEqual(popen.call_count, 1); connect.assert_not_called()
            self.assertFalse(transport._registry)
        stopped = threading.Event(); stopped.set()
        with patch.object(transport.subprocess,'Popen') as popen:
            with self.assertRaises(ConnectionAbortedError): self.open(stop=stopped)
            popen.assert_not_called()

    def test_retiring_a_dead_tunnel_never_closes_a_new_generation(self):
        with self.forwarded() as (popen, _):
            old = self.open(); old.process.returncode = 255
            new = self.open()
            self.assertEqual(popen.call_count, 2)
            self.assertIsNot(old.forward, new.forward)
            old.close()
            self.assertIs(transport._registry[('radxa@duck','/run/robotd/robot.sock')], new.forward)
            self.assertEqual(self.children[1].terminations, 0)

    def test_remote_socket_transmits_unmodified_binary_and_close_wakes_a_blocked_reader(self):
        left, right = socket.socketpair()
        wrapper = transport.RemoteSocket(left)
        self.sockets.append(wrapper)
        try:
            binary = bytes(range(256))*3+b'\0\r\n'
            wrapper.sendall(binary)
            self.assertEqual(right.recv(len(binary)),binary)
            right.sendall(binary)
            self.assertEqual(wrapper.recv(7)+wrapper.recv(len(binary)-7),binary)
            reader = wrapper.makefile('rb'); done = threading.Event(); result = []
            def read():
                try: result.append(reader.read(1))
                except OSError as error: result.append(error)
                finally: done.set()
            worker = threading.Thread(target=read,daemon=True);worker.start()
            wrapper.close()
            self.assertTrue(done.wait(1),'close must release the blocked telemetry reader')
            self.assertEqual(result,[b''])
            reader.close();worker.join(1)
        finally: right.close()

    def test_local_mode_opens_the_existing_unix_socket_without_ssh_or_payload(self):
        stream = MagicMock()
        with patch.object(transport.socket,'socket',return_value=stream), \
             patch.object(transport.subprocess,'Popen') as popen:
            wrapper = transport.open_remote_socket(None,'/run/robotd/robot.sock')
            self.sockets.append(wrapper)
            stream.connect.assert_called_once_with('/run/robotd/robot.sock')
            stream.sendall.assert_not_called();popen.assert_not_called()


if __name__ == '__main__': unittest.main()

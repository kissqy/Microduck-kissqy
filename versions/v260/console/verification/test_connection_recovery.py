import sys
from pathlib import Path
import threading
import queue
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import connection as links
from controls import Controller, ControlError
from raw_telemetry import endpoint_error
from ssh_connect import SSHConnectError
from telemetry import Store
from service_control import ServiceController

REAL_THREAD = threading.Thread


class ObservedWorker(REAL_THREAD):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.join_alive = []

    def join(self, timeout=None):
        super().join(timeout)
        self.join_alive.append(self.is_alive())


class DormantWorker:
    def __init__(self, target, args, daemon):
        self.args = args
    def start(self):
        pass
    def join(self, timeout):
        pass


class ConnectionRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.store = Store('service')
        self.controls = Mock()
        self.controls.transport.socket_path = '/run/robotd.sock'
        self.controls.transport.target = None
        self.config = {'ssh_target': 'radxa@192.168.6.151', 'camera_host': '192.168.6.151'}
        self.connection = links.Connection(self.store, self.config, self.controls, None, Mock(), {})
        for name, replacement in [('Transport', Mock()), ('SudoCredential', Mock()),
                                  ('set_credential', Mock()), ('save_target', Mock()),
                                  ('threading.Thread', DormantWorker)]:
            self.addCleanup(patch.stopall)
            patch.object(links.threading, 'Thread', replacement).start() if name == 'threading.Thread' else patch.object(links, name, replacement).start()

    def connect(self):
        self.connection.handle({'action': 'connect', 'target': 'radxa@192.168.6.151'})
        return self.connection.worker.args[2]

    def transport(self, emit, endpoint, connected):
        emit({'channel': 'ssh_transport', 'data': {'endpoint': endpoint, 'connected': connected}})

    def test_robotd_crash_with_live_tof_keeps_ssh_connected_and_motion_blocked(self):
        emit = self.connect()
        self.transport(emit, 'tof', True)
        emit({'channel': 'tof', 'data': {'seq': 7792, 'distance_mm': [10] * 64}})
        problem = endpoint_error('robotd', ConnectionResetError('[WinError 10054] 远程主机强迫关闭了一个现有的连接。'), 'radxa@192.168.6.151')
        for channel in ('state', 'health', 'system', 'capabilities', 'bus', 'calibration'):
            emit({'channel': channel, **problem})
        status = self.connection.status()
        self.assertTrue(status['connected'])
        self.assertIn('robotd 数据连接失败', status['error'])
        self.assertIn('10054', status['error'])
        self.assertNotIn('SSH 连接失败', status['error'])
        transport = Mock()
        controller = Controller(self.store, transport=transport)
        with self.assertRaises(ControlError) as rejected:
            controller.handle({'action': 'webpad_state', 'client': 'test_page', 'seq': 1, 'frame': {}})
        self.assertEqual(str(rejected.exception), '先升级配套 R17 / 0.15.1 服务并切到运动模式')
        transport.call.assert_not_called()
        self.assertFalse(self.store.snapshot()['service_sample_fresh'])

    def test_authenticated_forward_without_any_robot_service_still_allows_maintenance(self):
        emit = self.connect()
        self.transport(emit, 'robotd', True)
        emit({'channel': 'state', **endpoint_error('robotd', ConnectionResetError('Unix socket not available'), self.connection.target)})
        self.transport(emit, 'robotd', False)
        status = self.connection.status()
        self.assertTrue(status['active'])
        self.assertTrue(status['connected'])
        self.assertEqual(self.store.data, {})
        self.assertFalse(self.store.service_operation)

    def test_actual_ssh_authentication_failure_clears_verified_login_and_retains_detail(self):
        emit = self.connect()
        self.transport(emit, 'robotd', True)
        self.transport(emit, 'robotd', False)
        detail = 'radxa@192.168.6.151: Permission denied (publickey,password).'
        emit({'channel': 'state', **endpoint_error('robotd', SSHConnectError(detail), self.connection.target)})
        status = self.connection.status()
        self.assertFalse(status['connected'])
        self.assertIn('SSH 登录失败', status['error'])
        self.assertIn(detail, status['error'])
        emit({'channel': 'state', **endpoint_error('robotd', SSHConnectError('connect to host 192.168.6.151 port 22: Connection timed out'), self.connection.target)})
        self.assertIn('port 22: Connection timed out', self.connection.status()['error'])
        problem = endpoint_error('robotd', TimeoutError('SSH 接口连接超时：/run/robotd.sock'), self.connection.target)
        self.assertEqual(problem['error_source'], 'ssh')
        self.assertIn('SSH 接口连接超时', problem['error'])
        self.transport(emit, 'tof', True)
        emit({'channel': 'state', **endpoint_error('robotd', SSHConnectError(detail), self.connection.target)})
        self.assertTrue(self.connection.status()['connected'])
        self.transport(emit, 'tof', False)
        self.assertFalse(self.connection.status()['connected'])

    def test_old_connection_generation_cannot_restore_a_successful_ssh_status(self):
        old_emit = self.connect()
        self.transport(old_emit, 'tof', True)
        self.assertTrue(self.connection.status()['connected'])
        new_emit = self.connect()
        self.transport(old_emit, 'tof', True)
        old_emit({'channel': 'system', 'data': {'boot_id': 'old'}})
        self.assertFalse(self.connection.status()['connected'])
        self.assertNotIn('system', self.store.data)
        self.transport(new_emit, 'robotd', True)
        self.assertTrue(self.connection.status()['connected'])
        self.transport(old_emit, 'robotd', False)
        old_emit({'channel': 'state', **endpoint_error('robotd', SSHConnectError('Permission denied'), self.connection.target)})
        self.assertTrue(self.connection.status()['connected'])
        self.assertEqual(self.connection.ssh_error, '')


class ConnectionLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.store = Store('service')
        self.controls = Controller(self.store)
        self.service = ServiceController(self.store, controls=self.controls, warm=False)
        self.config = {'ssh_target': 'radxa@192.168.6.151', 'camera_host': '192.168.6.151'}
        self.collectors = []
        self.collector_started = queue.Queue()
        self.cleanup_gate = None

        def collector(target, config, emit, stop, log, paused):
            finished = threading.Event()
            self.collectors.append((stop, finished, emit))
            self.collector_started.put(finished)
            try:
                stop.wait(5)
                # This is the real callback/owner-lock dependency that made
                # the previous join time out during disconnect and shutdown.
                emit({'channel': 'system', 'data': {'hostname': 'retired collector'}})
                if self.cleanup_gate is not None:
                    self.cleanup_gate.wait(3)
            finally:
                finished.set()

        self.connection = links.Connection(self.store, self.config, self.controls, self.service, collector, {})
        self.patches = [patch.object(links, 'save_target'), patch.object(links.threading, 'Thread', ObservedWorker)]
        for item in self.patches: item.start()

    def tearDown(self):
        if self.cleanup_gate is not None: self.cleanup_gate.set()
        self.connection.close(); self.controls.close(); self.service.close()
        for item in reversed(self.patches): item.stop()

    def connect(self):
        self.connection.handle({'action': 'connect', 'target': self.config['ssh_target']})
        self.collector_started.get(timeout=2)
        return self.connection.worker

    def test_close_joins_real_collector_after_releasing_callback_lock(self):
        worker = self.connect()
        self.connection.close()
        self.assertFalse(worker.is_alive())
        self.assertEqual(worker.join_alive, [False], 'collector must finish during the join, not after close releases its lock')
        self.assertTrue(self.collectors[0][1].is_set())
        self.assertNotIn('system', self.store.data, 'the final old-generation callback cannot publish a fresh sample')
        self.assertTrue(self.store.connection_paused.is_set())
        self.assertFalse(self.connection.status()['active'])

    def test_manual_disconnect_retires_worker_and_channel_then_allows_explicit_new_connection(self):
        worker = self.connect(); old_channel = self.service.transport.channel
        result = self.connection.handle({'action': 'disconnect'})
        self.assertFalse(result['active']); self.assertFalse(self.connection.closed)
        self.assertEqual(worker.join_alive, [False]); self.assertFalse(worker.is_alive())
        self.assertTrue(old_channel.closed)
        self.assertTrue(self.controls.transport.suspended)
        self.assertIsNone(self.service.job, 'disconnect must not issue HOME or relax')
        self.connect()
        self.assertFalse(self.service.transport.channel.closed)
        self.assertIsNot(self.service.transport.channel, old_channel)

    def test_reconnect_closes_old_channel_so_a_late_maintenance_request_cannot_respawn_ssh(self):
        worker = self.connect(); old_channel = self.service.transport.channel
        replacement = self.connect()
        self.assertEqual(worker.join_alive, [False]); self.assertFalse(worker.is_alive())
        self.assertIsNot(worker, replacement)
        self.assertTrue(old_channel.closed)
        with patch('service_channel.spawn_process') as spawn:
            with self.assertRaisesRegex(RuntimeError, '服务连接已关闭'):
                old_channel.request({'kind': 'manage', 'argv': ['true']}, timeout=.1)
            old_channel.warm()
        spawn.assert_not_called()
        self.assertFalse(self.service.transport.channel.closed)
        self.assertNotIn('system', self.store.data)

    def test_final_close_is_idempotent_and_rejects_late_connect_without_new_transport(self):
        self.connect(); self.connection.close(); self.connection.close()
        with patch.object(links, 'Transport') as inputs, patch.object(links, 'ServiceTransport') as services:
            with self.assertRaisesRegex(ControlError, '中控已关闭'):
                self.connection.handle({'action': 'connect', 'target': 'other@192.168.6.150'})
            with self.assertRaisesRegex(ControlError, '中控已关闭'):
                self.connection.handle({'action': 'disconnect'})
        inputs.assert_not_called(); services.assert_not_called()
        self.assertIsNone(self.connection.worker)
        self.assertTrue(self.connection.closed)

    def test_close_serializes_a_racing_late_connect_until_retired_collector_finishes(self):
        worker = self.connect(); self.cleanup_gate = threading.Event()
        close_finished = threading.Event(); connect_entered = threading.Event(); failures = []

        def close():
            self.connection.close(); close_finished.set()

        def late_connect():
            connect_entered.set()
            try: self.connection.handle({'action': 'connect', 'target': 'other@192.168.6.150'})
            except ControlError as exc: failures.append(str(exc))

        closer = REAL_THREAD(target=close); closer.start()
        self.assertTrue(self.collectors[0][0].wait(2))
        self.assertTrue(self.connection.closed)
        late = REAL_THREAD(target=late_connect); late.start()
        self.assertTrue(connect_entered.wait(2))
        self.assertFalse(close_finished.is_set(), 'close must be waiting for this collector fixture')
        self.cleanup_gate.set(); closer.join(3); late.join(3)
        self.assertFalse(closer.is_alive()); self.assertFalse(late.is_alive())
        self.assertEqual(failures, ['中控已关闭'])
        self.assertEqual(worker.join_alive, [False])
        self.assertEqual(len(self.collectors), 1, 'a queued late connect must not create another generation')

    def test_service_busy_rejects_connection_change_before_retiring_any_channel(self):
        self.connect(); channel = self.service.transport.channel; stop = self.connection.stop
        self.service.busy = True
        try:
            with self.assertRaisesRegex(ControlError, '当前服务操作还在执行'):
                self.connection.handle({'action': 'connect', 'target': 'other@192.168.6.150'})
            self.assertFalse(channel.closed); self.assertFalse(stop.is_set())
            self.assertTrue(self.connection.status()['active'])
        finally: self.service.busy = False


if __name__ == '__main__':
    unittest.main()

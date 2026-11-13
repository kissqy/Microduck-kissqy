"""Fault injection for bounded recovery and service restoration; no real radio/systemd."""
import copy
import os
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gamepad_repair as gp
from service_control import ServiceController, ServiceTransport, validate
from controls import ControlError

ADDRESS = '53:81:7F:20:AE:AB'
OTHER = '53:81:7F:20:AE:AC'


class Harness:
    def __init__(self, paired=False, connected=False, fault='', virtual=True):
        self.paired, self.connected = paired, connected
        self.hid_connected = connected and fault != 'acl_only'
        self.stale_bond = paired and fault == 'old_pair'
        self.fault, self.virtual = fault, virtual
        self.calls, self.commands = [], []
        self.units = {'btd.service': True, 'bluetooth.service': True, 'robotd.service': False, gp.INPUTS[0]: True, gp.INPUTS[1]: True}
        self.padd_reads = fault not in ('padd_stalled', 'padd_wait')
        self.now = 0
        self.closed = False
        self.known = paired
        self.phone_enabled = True
        self.powered = True

    def clock(self):
        self.now += .01
        return self.now

    def sleep(self, value):
        self.now += value

    def run(self, *args, **kwargs):
        self.calls.append(args)
        if args[:2] == ('bluetoothctl', 'devices'):
            return 'Device ' + ADDRESS + ' ' + gp.NAME if self.known else ''
        if args[:2] == ('bluetoothctl', 'info'):
            if not self.known: return 'Device ' + ADDRESS + ' not available'
            return f'Name: {gp.NAME}\nPaired: {"yes" if self.paired else "no"}\nConnected: {"yes" if self.connected else "no"}'
        if args[:2] == ('bluetoothctl', 'show'):
            return 'Powered: ' + ('yes\nPowerState: on' if self.powered else 'no\nPowerState: off')
        if args[:2] == ('systemctl', 'is-enabled'):
            return 'enabled' if self.phone_enabled else 'disabled'
        if args[0] == 'systemctl' and args[1] in ('start', 'stop', 'enable', 'restart'):
            for unit in args[2:]:
                if unit.endswith('.service'):
                    if self.fault == 'restore' and args[1] == 'start' and unit == 'btd.service':
                        raise gp.RepairError('cannot restore phone')
                    self.units[unit] = args[1] != 'stop'
                    if args[1] == 'restart' and unit == gp.INPUTS[0] and self.fault == 'bridge_stalled': self.virtual = True
                    if args[1] == 'restart' and unit == gp.INPUTS[1]: self.padd_reads = True
        return ''

    def command(self, command, success, timeout=8):
        self.commands.append(command)
        if self.fault == 'power' and command == 'power off':
            raise gp.RepairError('org.bluez.Error.Failed')
        if command == 'power off':
            self.powered = False
            if self.fault == 'power_async': raise gp.RepairError('org.bluez.Error.Failed')
        if command == 'power on': self.powered = True
        if self.fault == 'scan' and command == 'scan on':
            raise gp.RepairError('org.bluez.Error.InProgress')
        if command.startswith('connect') and (self.stale_bond or self.fault == 'profile_failure'):
            raise gp.RepairError('br-connection-create-socket')
        if self.fault == 'connect_timeout' and command.startswith('connect'):
            raise subprocess.TimeoutExpired('connect HID', 20)
        if command.startswith('remove'):
            self.known = self.paired = self.connected = False
            self.hid_connected = self.stale_bond = False
        if command == 'scan on':
            self.known = True
        if command.startswith('pair '):
            if self.fault == 'pair_timeout': raise subprocess.TimeoutExpired('pair', 30)
            self.paired = self.connected = True
        if command.startswith('connect'):
            self.connected = True
            self.hid_connected = self.fault != 'missing_hid'
        return success[0]

    def session(self):
        h = self
        class Session:
            seen = set()
            command = h.command
            def read(self, seconds):
                h.sleep(.01 if h.known else seconds)
                return '[NEW] Device ' + ADDRESS + ' ' + gp.NAME + '\n' if h.known else ''
            def close(self): h.closed = True
        return Session()

    def state(self):
        if self.fault == 'link_drops' and any(c.startswith('connect ') for c in self.commands):
            self.connected = False
        physical = self.connected and self.hid_connected
        virtual = physical and self.virtual and self.units.get(gp.INPUTS[0], False)
        return {'physical': physical, 'virtual': virtual,
                'bridge_active': self.units.get(gp.INPUTS[0], False),
                'padd_active': self.units.get(gp.INPUTS[1], False),
                'padd_open': virtual and self.padd_reads and self.units.get(gp.INPUTS[1], False),
                'bridge_waiting': self.fault == 'startup_wait', 'padd_waiting': self.fault == 'padd_wait'}

    def execute(self, address='', operation='repair'):
        h = self
        class Watch:
            def __enter__(self): return self
            def __exit__(self, *_): pass
            def wait(self, seconds): h.sleep(seconds); return False
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(gp, 'open', lambda *_: open(Path(directory) / 'lock', 'w'), create=True), \
                patch.object(gp, 'run', self.run), patch.object(gp, 'loaded', return_value=True), \
                patch.object(gp, 'active', lambda unit: self.units.get(unit, False)), \
                patch.object(gp, 'BluetoothSession', self.session), patch.object(gp, 'bridge_state', self.state), \
                patch.object(gp, 'InputWatch', Watch), \
                patch.object(gp, 'emit') as emitted, patch.object(gp.time, 'monotonic', self.clock), patch.object(gp.time, 'sleep', self.sleep):
            result = gp.repair(address, operation)
            self.events = emitted.call_args_list
            return result


class RepairTests(unittest.TestCase):
    def test_global_budget_stops_new_commands_but_cleanup_has_a_separate_budget(self):
        with patch.object(gp, 'DEADLINE', 10), patch.object(gp.time, 'monotonic', return_value=11):
            with self.assertRaises(gp.RepairError) as error: gp.time_budget(30)
            self.assertEqual(error.exception.phase, 'timeout')
        self.assertEqual(gp.time_budget(30), 30)
    def test_first_pair_keeps_inactive_phone_inactive_and_never_enables_units(self):
        h = Harness(); h.units['btd.service'] = False; h.phone_enabled = False
        result = h.execute(operation='pair')
        self.assertEqual(result['status'], 'completed', result)
        self.assertFalse(h.units['btd.service'])
        self.assertNotIn('phone_service_restored', result)
        self.assertEqual(h.commands.count('scan on'), 1)
        self.assertTrue(all(result[k] for k in ('bluetooth_connected', 'physical', 'virtual', 'padd_active')))
        self.assertTrue(h.closed)
        self.assertNotIn('restart', [arg for call in h.calls for arg in call])
        self.assertNotIn('enable', [arg for call in h.calls for arg in call])

    def test_working_bond_never_resets_radio_or_deletes_a_device(self):
        h = Harness(paired=True, connected=True)
        self.assertEqual(h.execute()['status'], 'completed')
        self.assertFalse(any(c.startswith(('remove', 'scan', 'power off', 'pair ')) for c in h.commands))
        self.assertFalse(any(c[0] == 'systemctl' and c[1] in ('stop','start','restart','enable') for c in h.calls))
        self.assertEqual(h.commands, [])
        self.assertFalse(h.closed)

    def test_old_socket_failure_preserves_bond_without_automatic_repair(self):
        h = Harness(paired=True, fault='old_pair')
        result = h.execute()
        self.assertEqual(result['phase'], 'connect_failed')
        self.assertFalse(any(c.startswith(('remove','pair ','scan ','power off')) for c in h.commands))
        self.assertTrue(h.paired)

    def test_explicit_repair_removes_only_target_and_rebonds(self):
        h = Harness(paired=True, fault='old_pair')
        self.assertEqual(h.execute(operation='pair')['status'], 'completed')
        self.assertEqual([c for c in h.commands if c.startswith('remove')], ['remove ' + ADDRESS])
        self.assertEqual(h.commands.count('power off'), 1)
        self.assertEqual(h.commands.count('scan on'), 1)
        self.assertLess(h.commands.index('remove ' + ADDRESS), h.commands.index('pair ' + ADDRESS))

    def test_explicit_pair_clears_incomplete_target_record(self):
        h = Harness(); h.known = True
        result = h.execute(operation='pair')
        self.assertEqual(result['status'],'completed',result)
        self.assertEqual([c for c in h.commands if c.startswith('remove ')],['remove '+ADDRESS])

    def test_pair_connected_property_does_not_skip_hid_profile(self):
        h = Harness()
        result = h.execute(operation='pair')
        self.assertEqual(result['status'], 'completed', result)
        self.assertEqual(h.commands.count('connect ' + ADDRESS + ' ' + gp.HID), 1)
        self.assertLess(h.commands.index('pair ' + ADDRESS), h.commands.index('connect ' + ADDRESS + ' ' + gp.HID))
        self.assertTrue(result['physical'])

    def test_connected_without_input_repairs_hid_once_with_existing_bond(self):
        h = Harness(paired=True, connected=True, fault='acl_only')
        result = h.execute()
        self.assertEqual(result['status'], 'completed', result)
        self.assertEqual(h.commands.count('connect ' + ADDRESS + ' ' + gp.HID), 1)
        self.assertFalse(any(c.startswith(('pair ', 'remove ', 'scan ', 'power off')) for c in h.commands))
        self.assertFalse(any(c[0] == 'systemctl' and c[1] in ('stop', 'restart', 'enable') for c in h.calls))

    def test_new_pair_profile_failure_keeps_bond_address_and_exact_error(self):
        h = Harness(fault='profile_failure')
        result = h.execute(operation='pair')
        self.assertEqual(result['phase'], 'connect_failed', result)
        self.assertEqual(result['address'], ADDRESS)
        self.assertTrue(h.paired)
        self.assertIn('br-connection-create-socket', result['message'])
        self.assertFalse(any(c[0] == 'systemctl' and 'robotd.service' in c for c in h.calls))

    def test_disconnected_after_pair_is_bluetooth_failure_without_robotd_blame(self):
        h = Harness(fault='link_drops')
        result = h.execute(operation='pair')
        self.assertEqual(result['phase'], 'connect_failed', result)
        self.assertIn('蓝牙已断开', result['message'])
        self.assertNotIn('robotd 启动未完成', result['message'])
        failed = [c.args for c in h.events if len(c.args) > 2 and c.args[2] == 'failed']
        self.assertEqual([c[0] for c in failed], ['bluetooth', 'physical', 'bridge', 'padd'])
        self.assertIn('蓝牙已断开', failed[0][1])

    def test_connected_but_missing_hid_is_not_bridge_or_main_service_failure(self):
        h = Harness(fault='missing_hid')
        result = h.execute(operation='pair')
        self.assertEqual(result['phase'], 'physical_unready', result)
        self.assertIn('HID 接入未完成', result['message'])
        self.assertNotIn('robotd 启动未完成', result['message'])

    def test_connect_timeout_is_reported_at_bluetooth_layer_and_keeps_bond(self):
        h = Harness(fault='connect_timeout')
        result = h.execute(operation='pair')
        self.assertEqual(result['phase'], 'connect_failed', result)
        self.assertTrue(h.paired)
        self.assertEqual(result['address'], ADDRESS)

    def test_adapter_power_failure_stops_without_scanning_and_restores_services(self):
        h = Harness(fault='power')
        result = h.execute(operation='pair')
        self.assertEqual(result['phase'], 'adapter_failed')
        self.assertFalse(any(c.startswith(('scan', 'pair ')) for c in h.commands))
        self.assertTrue(all(h.units[u] for u in (*gp.INPUTS, 'btd.service')))
        self.assertTrue(h.closed)

    def test_discovery_inprogress_has_no_pair_attempt_or_blind_restart(self):
        h = Harness(fault='scan')
        result = h.execute(operation='pair')
        self.assertEqual(result['phase'], 'scan_busy')
        self.assertFalse(any(c.startswith('pair ') for c in h.commands))
        self.assertTrue(result['phone_service_restored'])
        self.assertLess(h.now, 60)

    def test_power_off_error_with_actual_off_state_continues_once(self):
        h = Harness(fault='power_async')
        result = h.execute(operation='pair')
        self.assertEqual(result['status'], 'completed', result)
        self.assertEqual(h.commands.count('power off'), 1)

    def test_pair_timeout_still_closes_session_and_restores_phone_and_inputs(self):
        h = Harness(paired=True, fault='pair_timeout')
        self.assertEqual(h.execute(operation='pair')['status'], 'error')
        self.assertTrue(h.closed)
        self.assertTrue(all(h.units[u] for u in (*gp.INPUTS, 'btd.service')))

    def test_active_units_without_virtual_xbox_are_not_a_success(self):
        h = Harness(paired=True, connected=True, virtual=False)
        result = h.execute()
        self.assertEqual(result['phase'], 'bridge_unready')
        self.assertFalse(result['virtual'])
        self.assertTrue(result['padd_active'])
        self.assertLess(h.now, 30)

    def test_phone_failure_is_reported_separately_from_confirmed_input(self):
        h = Harness(paired=True, connected=True, fault='restore')
        result = h.execute(operation='pair')
        self.assertEqual(result['status'], 'completed', result)
        self.assertEqual(result['phase'], 'ready')
        self.assertIn('btd', result['message'])
        self.assertTrue(result['warnings'])

    def test_explicitly_disabled_phone_stays_disabled_when_option_is_off(self):
        h = Harness(paired=True, connected=True); h.units['btd.service'] = False; h.phone_enabled = False
        self.assertEqual(h.execute()['status'], 'completed')
        self.assertFalse(h.units['btd.service'])

    def test_exact_device_name_does_not_select_other_modes_or_other_devices(self):
        text = '\n'.join(['Device ' + ADDRESS + ' ' + gp.NAME, 'Device ' + OTHER + ' GameSir-Nova 2 Lite_G',
                          'Device AA:BB:CC:DD:EE:FF Other Controller'])
        self.assertEqual(gp.devices(text), {ADDRESS: gp.NAME})

    def test_recovery_stops_after_unconfirmed_motor_torque(self):
        h = Harness(); h.units['robotd.service'] = True
        with patch.object(gp, 'rpc', side_effect=gp.RepairError('torque unconfirmed')):
            result = h.execute(operation='pair')
        self.assertEqual(result['status'], 'error')
        self.assertEqual(h.commands, [])
        self.assertTrue(all(h.units[u] for u in gp.INPUTS))

    def test_unpaired_repair_requires_explicit_pair_selection(self):
        h = Harness()
        result = h.execute()
        self.assertEqual(result['phase'], 'pair_required')
        self.assertEqual(h.commands, [])
        self.assertFalse(any(c[0] == 'systemctl' and c[1] == 'stop' for c in h.calls))

    def test_normal_reconnect_uses_old_bond_once_without_motion_or_phone_work(self):
        h = Harness(paired=True)
        result = h.execute()
        self.assertEqual(result['status'], 'completed', result)
        self.assertEqual(sum(c.startswith('connect ') for c in h.commands), 1)
        self.assertFalse(any(c[0] == 'systemctl' and c[1] in ('stop','restart','enable') for c in h.calls))

    def test_only_missing_input_service_is_started(self):
        h = Harness(paired=True, connected=True); h.units[gp.INPUTS[0]] = False
        self.assertEqual(h.execute()['status'], 'completed')
        self.assertEqual([c for c in h.calls if c[0] == 'systemctl' and c[1] in ('start','stop','restart','enable')], [('systemctl','start',gp.INPUTS[0])])

    def test_only_stalled_bridge_is_restarted(self):
        h = Harness(paired=True, connected=True, fault='bridge_stalled', virtual=False)
        self.assertEqual(h.execute()['status'], 'completed')
        self.assertEqual([c for c in h.calls if c[0] == 'systemctl' and c[1] == 'restart'], [('systemctl','restart',gp.INPUTS[0])])

    def test_only_stalled_padd_is_restarted(self):
        h = Harness(paired=True, connected=True, fault='padd_stalled')
        self.assertEqual(h.execute()['status'], 'completed')
        self.assertEqual([c for c in h.calls if c[0] == 'systemctl' and c[1] == 'restart'], [('systemctl','restart',gp.INPUTS[1])])

    def test_startup_gate_is_left_running_without_restart(self):
        h = Harness(paired=True, connected=True, fault='startup_wait', virtual=False)
        result = h.execute()
        self.assertEqual(result['status'], 'error')
        self.assertTrue(result['bridge_waiting'])
        self.assertIn('等待主服务启动完成事件', result['message'])
        self.assertFalse(any(c[0] == 'systemctl' and c[1] == 'restart' for c in h.calls))

    def test_stale_startup_report_is_not_mistaken_for_confirmed_torque(self):
        with patch.object(gp, 'active', return_value=True), patch.object(gp, 'emit'), \
                patch.object(gp, 'rpc', side_effect=[{}, {'mode': 'motion', 'phase': 'configuration_error', 'cycle': 0}]):
            gp.stop_motion()
        with patch.object(gp, 'active', return_value=True), patch.object(gp, 'emit'), \
                patch.object(gp, 'rpc', side_effect=gp.RepairError('rejected')):
            with self.assertRaises(gp.RepairError): gp.stop_motion()


class Store:
    service_operation = False
    connection_paused = threading.Event()
    def snapshot(self): return {'bus': {}, 'service_sample_fresh': False}
    def record_service_command(self, job): self.job = copy.deepcopy(job)


class WatchTests(unittest.TestCase):
    def test_real_inotify_observes_late_directory_and_input_open_without_probes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with gp.InputWatch(root) as watch, patch.object(gp, 'bridge_state', side_effect=AssertionError('no state polling')):
                self.assertFalse(watch.wait(.02))
                (root/'input').mkdir()
                self.assertTrue(watch.wait(.2))
                event = root/'input/event9'
                event.touch()
                self.assertTrue(watch.wait(.2))
                self.assertFalse(watch.wait(.02))
                fd = os.open(event, os.O_RDONLY)
                try:self.assertTrue(watch.wait(.2))
                finally:os.close(fd)
                self.assertFalse(watch.wait(.02))
            with self.assertRaises(OSError):os.fstat(watch.fd)

    def test_padd_active_and_virtual_exists_do_not_prove_device_open(self):
        original = Path.read_text
        original_bytes, original_iterdir = Path.read_bytes, Path.iterdir
        block = 'N: Name="'+gp.NAME+'"\n\nN: Name="'+gp.VIRTUAL+'"\nH: Handlers=event9 js0\n'
        def text(path, *args, **kwargs):
            if str(path) == '/proc/bus/input/devices':return block
            return original(path, *args, **kwargs)
        def cmdline(path):
            return b'/opt/robot/padd\0' if str(path) == '/proc/42/cmdline' else original_bytes(path)
        def fds(path):
            return iter([Path('/proc/42/fd/5')]) if str(path) == '/proc/42/fd' else original_iterdir(path)
        with patch.object(Path, 'read_text', text), patch.object(gp, 'active', return_value=True), \
                patch.object(Path, 'read_bytes', cmdline), patch.object(Path, 'iterdir', fds), \
                patch.object(gp, 'run', return_value='42'), patch.object(gp.os, 'readlink', return_value='/tmp/other'):
            state = gp.bridge_state()
            self.assertTrue(state['virtual'] and state['padd_active'])
            self.assertFalse(state['padd_open'])
            self.assertFalse(gp.input_ready(state))
        with patch.object(Path, 'read_text', text), patch.object(gp, 'active', return_value=True), \
                patch.object(Path, 'read_bytes', cmdline), patch.object(Path, 'iterdir', fds), \
                patch.object(gp, 'run', return_value='42'), patch.object(gp.os, 'readlink', return_value='/dev/input/event9'):
            state = gp.bridge_state()
            self.assertTrue(gp.input_ready(state), state)


class InlineThread:
    def __init__(self, target, args=(), **kwargs): self.target, self.args = target, args
    def start(self): self.target(*self.args)


class ControllerTests(unittest.TestCase):
    def test_named_steps_replace_raw_progress_and_phone_failure_is_separate(self):
        from unittest.mock import Mock
        class Transport:
            def repair_gamepad(self, *args, progress=None, **kwargs):
                progress(json.dumps({'pad_repair_progress':{'phase':'bluetooth','status':'success','message':'已连接','evidence':{'bluetooth_connected':True}}}))
                progress(json.dumps({'pad_repair_progress':{'phase':'phone_restore','status':'failed','message':'btd 未恢复'}}))
                return {'status':'completed','phase':'ready','message':'手柄就绪；btd 未恢复','warnings':['btd 未恢复']}
        store = Store();store.system_log = Mock()
        controller = ServiceController(store, transport=Transport())
        job = {'action':'repair-gamepad','status':'running'}
        controller._execute({'action':'repair-gamepad','supported':True,'address':'','operation':'repair'},job,0)
        self.assertEqual(job['status'],'completed')
        self.assertEqual(job['pad_steps']['phone_restore']['status'],'failed')
        self.assertTrue(job['pad_evidence']['bluetooth_connected'])
        rows = store.system_log.add.call_args_list
        self.assertIn(('手柄 / 蓝牙连接','成功 · 已连接'),[r.args for r in rows])
        self.assertIn(('手柄 / 恢复手机连接服务','失败 · btd 未恢复'),[r.args for r in rows])
        self.assertNotIn('pad_repair_progress',str(rows))
    def test_repair_works_without_imu_and_password_never_enters_job(self):
        class Transport:
            def repair_gamepad(self, address, operation, password=None, progress=None):
                self.password = password
                progress(json.dumps({'pad_repair_progress': {'phase': 'pairing', 'message': '配对'}}))
                return {'status': 'completed', 'message': '已确认桥接'}
        transport = Transport(); controller = ServiceController(Store(), transport=transport)
        request = {'action': 'repair-gamepad', 'supported': True, 'address': '', 'operation': 'repair', 'sudo_password': 'secret'}
        with patch('service_control.threading.Thread', InlineThread):
            controller.handle({'client': 'gamepad-test', 'seq': 1, 'command': request})
        self.assertEqual(controller.job['status'], 'completed')
        self.assertEqual(transport.password, 'secret')
        self.assertNotIn('secret', json.dumps(controller.job))
        self.assertFalse(controller.store.service_operation)

    def test_adapter_failure_preserves_phase_and_partial_evidence(self):
        class Transport:
            def repair_gamepad(self, *args, **kwargs):
                return {'status': 'error', 'phase': 'needs_reboot', 'message': '需重启', 'virtual': False}
        controller = ServiceController(Store(), transport=Transport())
        job = {'action': 'repair-gamepad', 'status': 'running'}
        controller._execute({'action': 'repair-gamepad', 'supported': True, 'address': '', 'operation': 'repair'}, job, 0)
        self.assertEqual(job['status'], 'error')
        self.assertEqual(job['phase'], 'needs_reboot')
        self.assertFalse(job['result']['virtual'])

    def test_validates_target_and_support_and_does_not_allow_extra_command_fields(self):
        base = {'action': 'repair-gamepad', 'supported': True, 'address': '', 'operation': 'repair'}
        validate(base)
        for change in ({'supported': False}, {'address': ADDRESS + '; reboot'}, {'operation': 'invalid'}, {'argv': ['reboot']}):
            with self.assertRaises(ControlError): validate({**base, **change})

    def test_ssh_embeds_helper_without_installing_a_new_daemon(self):
        transport = ServiceTransport('', '/unused')
        with patch.object(transport, '_manage', return_value={'status': 'completed'}) as manage:
            transport.repair_gamepad(ADDRESS, 'repair', password='secret', progress=lambda _: None)
        args = manage.call_args.args[0]
        self.assertEqual(args[:3], ['python3', '-u', '-c'])
        self.assertIn('def repair(', args[3])
        self.assertEqual(json.loads(args[4]), {'address': ADDRESS, 'operation': 'repair'})
        self.assertNotIn('secret', repr(args))
        self.assertFalse(manage.call_args.kwargs['record_output'])
        self.assertTrue(callable(manage.call_args.kwargs['output_handler']))


class SessionTests(unittest.TestCase):
    def test_one_live_client_owns_scan_agent_pair_and_connect_until_cleanup(self):
        # Use a real child with terminal-style asynchronous output, not a mocked command method.
        script = '''import sys,time
print("Agent registered",flush=True)
for line in sys.stdin:
 c=line.strip()
 if c=="quit":break
 out={"power on":"Changing power on succeeded", "agent off":"Agent unregistered", "agent NoInputNoOutput":"Agent registered", "default-agent":"Default agent request successful", "scan on":"Discovery started", "scan off":"Discovery stopped"}.get(c)
 if c.startswith("pair "):
  print("[agent] Accept pairing (yes/no):",flush=True);continue
 if c=="yes":out="Pairing successful"
 if c.startswith("connect "):out="Connection successful"
 if c.startswith("connect already "):out="Failed to connect: org.bluez.Error.AlreadyConnected"
 if not out:out="Failed: org.bluez.Error.InProgress"
 sys.stdout.write("\\x1b[0;94m[bluetooth]\\x1b[0m> ");sys.stdout.flush();time.sleep(.01)
 print(out,flush=True)
'''
        popen = subprocess.Popen
        children = []
        def spawn(*args, **kwargs):
            child = popen([sys.executable, '-u', '-c', script], **kwargs)
            children.append(child)
            return child
        with patch.object(gp.subprocess, 'Popen', spawn):
            session = gp.BluetoothSession()
            try:
                for command, success in [('power on', 'Changing power on succeeded'), ('agent off', 'Agent unregistered'),
                        ('agent NoInputNoOutput', 'Agent registered'), ('default-agent', 'Default agent request successful'),
                        ('scan on', 'Discovery started'), ('scan off', 'Discovery stopped'),
                        ('pair ' + ADDRESS, 'Pairing successful'), ('connect ' + ADDRESS + ' ' + gp.HID, 'Connection successful')]:
                    self.assertIn(success, session.command(command, [success], timeout=1))
                with self.assertRaises(gp.RepairError): session.command('invalid', ['success'], timeout=1)
                self.assertIn('AlreadyConnected', session.command('connect already ' + gp.HID,
                              ['Connection successful', 'org.bluez.Error.AlreadyConnected'], timeout=1))
                self.assertIsNone(children[0].poll())
            finally: session.close()
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0].poll(), 0)


if __name__ == '__main__': unittest.main()

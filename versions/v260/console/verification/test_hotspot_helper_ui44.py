"""R5 hotspot scheduling/worker verification with no real network or services.

All filesystem writes are under TemporaryDirectory. The one real Bash worker
test shadows nmcli/systemctl/chown with fixture commands. Its derived library
overrides ONLY legacy_wifi_files, whose original hard-coded absolute probes
would otherwise inspect the host. The original R5 profile functions are used.
"""
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import hotspot_control as helper

ORIGINAL = (ROOT / 'resources/wifi-r5/microduck-public-image.sh').read_bytes()


class Runner:
    def __init__(self):
        self.calls = []
        self.ap = 'yes'
        self.devices = 'wlan0:wifi\neth0:ethernet\n'
        self.dropins = ''
        self.legacy = ''
        self.states = {}
        self.fail_queue = False

    def __call__(self, *args, **_):
        self.calls.append(args)
        if args == ('getent', 'passwd', 'radxa'):
            return 'radxa:x:1000:1000:Radxa:/home/radxa:/bin/bash\n'
        if args == ('nmcli', '-t', '-f', 'DEVICE,TYPE', 'device', 'status'):
            return self.devices
        if args[:3] == ('nmcli', '-g', 'WIFI-PROPERTIES.AP'):
            return self.ap
        if args[:3] == ('systemctl', 'show', '--property=DropInPaths'):
            return self.dropins
        if args[:3] == ('systemctl', 'show', '--property=ActiveState'):
            return self.states.get(args[-1], 'inactive')
        if args[:2] == ('/bin/bash', '-c'):
            return self.legacy if args[2].endswith('\nlegacy_wifi_files\n') else ''
        if args[0] == 'systemd-run':
            if self.fail_queue:
                raise RuntimeError('fixture scheduling failure')
            name = next(arg.removeprefix('--unit=') for arg in args if arg.startswith('--unit='))
            self.states[name + '.timer'] = 'active'
        return ''

    @property
    def queues(self):
        return [call for call in self.calls if call[0] == 'systemd-run']


class HotspotHelperTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix='ui44-hotspot-')
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name)
        self.runner = Runner()
        files = {
            'usr/local/sbin/microduck-public-image': ORIGINAL,
            'usr/local/libexec/microduck-setup-portal.py': helper.r5_portal(ORIGINAL),
            'etc/systemd/system/microduck-setup.service':
                ('[Service]\nExecStart=/usr/bin/python3 ' +
                 str(self.root / 'usr/local/libexec/microduck-setup-portal.py') +
                 ' --serve wlan0\n').encode(),
            'etc/NetworkManager/system-connections/old.nmconnection':
                b'[connection]\ntype=wifi\n[wifi]\nssid=fixture-home\n',
        }
        for name, data in files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        (self.root / 'usr/local/libexec/microduck_wifi_r7.py').write_bytes((ROOT/'resources/wifi-r5/microduck_wifi_r7.py').read_bytes())
        for leaf in ('microduck_wifi_events.py', '90-microduck-hotspot'):
            relative = 'etc/NetworkManager/dispatcher.d' if leaf == '90-microduck-hotspot' else 'usr/local/libexec'
            target = self.root / relative / leaf
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT/'resources/wifi-r5'/leaf).read_bytes())
        self.old = self.root / 'etc/NetworkManager/system-connections/old.nmconnection'
        self.before = self.old.read_bytes()

    def schedule(self, **kwargs):
        return helper.schedule(ORIGINAL, self.runner, self.root,
                               which=kwargs.pop('which', lambda name: '/fixture/' + name),
                               uid=kwargs.pop('uid', lambda: 0), **kwargs)

    def assert_no_reset(self):
        self.assertEqual(self.runner.queues, [])
        self.assertEqual(self.old.read_bytes(), self.before)
        self.assertFalse(any('remove_wifi_profiles\n' == call[-1] for call in self.runner.calls))

    def test_compressed_original_is_bounded_verified_and_exact(self):
        self.assertEqual(hashlib.sha256(ORIGINAL).hexdigest(), helper.R5_SHA256)
        encoded = base64.b64encode(gzip.compress(ORIGINAL, mtime=0)).decode()
        self.assertLess(len(encoded), 120000)
        self.assertEqual(helper.decode_original(encoded), ORIGINAL)
        for bad in ['not base64!', encoded[:-5],
                    base64.b64encode(gzip.compress(b'wrong R5')).decode(),
                    base64.b64encode(gzip.compress(b'x' * (128 * 1024 + 1))).decode(),
                    base64.b64encode(gzip.compress(ORIGINAL) + b'trailing').decode(),
                    'a' * 120001]:
            with self.subTest(bad_length=len(bad)), self.assertRaises((ValueError, OSError)):
                helper.decode_original(bad)

    def test_missing_mismatched_or_unprivileged_components_never_queue(self):
        with self.assertRaisesRegex(RuntimeError, 'sudo'):
            self.schedule(uid=lambda: 1000)
        self.assert_no_reset()
        with self.assertRaisesRegex(RuntimeError, '依赖'):
            self.schedule(which=lambda _: None)
        self.assert_no_reset()
        with self.assertRaisesRegex(RuntimeError, '依赖'):
            self.schedule(which=lambda name: None if name == 'chpasswd' else '/fixture/' + name)
        self.assert_no_reset()
        program = self.root / 'usr/local/sbin/microduck-public-image'
        program.unlink()
        with self.assertRaisesRegex(RuntimeError, '完整安装'):
            self.schedule()
        self.assert_no_reset()
        program.write_bytes(ORIGINAL + b'\n# changed\n')
        with self.assertRaisesRegex(RuntimeError, '不一致'):
            self.schedule()
        self.assert_no_reset()
        program.write_bytes(ORIGINAL)
        portal = self.root / 'usr/local/libexec/microduck-setup-portal.py'
        portal.write_bytes(b'print("other portal")\n')
        with self.assertRaisesRegex(RuntimeError, '不一致'):
            self.schedule()
        self.assert_no_reset()

    def test_radio_unit_legacy_and_other_r5_operations_fail_before_queue(self):
        for field, value in [('ap', 'no'), ('ap', ''), ('devices', 'eth0:ethernet\n'),
                             ('dropins', '/fixture/custom.conf'),
                             ('legacy', '/fixture/old-wpa.conf')]:
            before = getattr(self.runner, field)
            setattr(self.runner, field, value)
            with self.subTest(field=field, value=value), self.assertRaises(RuntimeError):
                self.schedule()
            self.assert_no_reset()
            setattr(self.runner, field, before)
        self.runner.states['microduck-image-seal.timer'] = 'active'
        with self.assertRaisesRegex(RuntimeError, '封存'):
            self.schedule()
        self.assert_no_reset()
        self.runner.states.clear()
        marker = self.root / 'run/microduck-wifi-test-restore'
        marker.parent.mkdir(exist_ok=True)
        marker.write_text('test underway')
        with self.assertRaisesRegex(RuntimeError, '测试'):
            self.schedule()
        self.assert_no_reset()

    def test_queue_uses_one_detached_five_second_worker_without_clearing_wifi(self):
        receipt = self.schedule()
        self.assertIs(receipt['accepted'], True)
        self.assertIs(receipt['queued'], True)
        self.assertEqual(receipt['delay_seconds'], 5)
        self.assertEqual(receipt['ssid'], helper.SSID)
        self.assertEqual(receipt['portal_url'], helper.PORTAL_URL)
        self.assertEqual(len(self.runner.queues), 1)
        queue = self.runner.queues[0]
        self.assertIn('--on-active=5s', queue)
        self.assertIn('--collect', queue)
        self.assertIn('--property=Type=oneshot', queue)
        self.assertEqual(queue[-2], '/bin/bash')
        worker = Path(queue[-1])
        self.assertTrue(worker.is_relative_to(self.root / 'run'))
        self.assertEqual(self.old.read_bytes(), self.before)
        self.assertFalse(any(call[:2] == ('systemctl', 'restart') for call in self.runner.calls))
        prepared = [call[2] for call in self.runner.calls if call[:2] == ('/bin/bash', '-c')]
        self.assertEqual(len(prepared), 2)
        self.assertTrue(prepared[-1].endswith('\nwrite_hotspot_profile\n'))
        self.assertNotIn('remove_wifi_profiles', prepared[-1])
        self.assertNotIn('--seal-now', worker.read_text())
        self.assertNotIn('\nseal\n', worker.read_text())
        self.assertNotIn('ssh', worker.read_text())
        self.assertNotIn('chpasswd', worker.read_text())
        self.assertNotIn('poweroff', worker.read_text())

    def test_active_pending_task_cannot_be_repeated(self):
        self.schedule()
        before = len(self.runner.queues)
        with self.assertRaisesRegex(RuntimeError, '未重复执行'):
            self.schedule()
        self.assertEqual(len(self.runner.queues), before)
        self.assertEqual(self.old.read_bytes(), self.before)

    def test_failed_scheduler_does_not_return_a_queued_receipt(self):
        self.runner.fail_queue = True
        with self.assertRaisesRegex(RuntimeError, 'scheduling failure'):
            self.schedule()
        self.assertEqual(len(self.runner.queues), 1)
        self.assertEqual(self.old.read_bytes(), self.before)

    def test_missing_unit_inactive_is_allowed_but_manager_errors_are_not(self):
        command = ('systemctl', 'show', '--property=ActiveState', '--value', 'missing.timer')
        missing = subprocess.CompletedProcess(command, 1, 'inactive\n', 'not found')
        with patch.object(helper.subprocess, 'run', return_value=missing):
            self.assertEqual(helper.run(*command), 'inactive\n')
        for stdout in ('', 'active\n'):
            failed = subprocess.CompletedProcess(command, 1, stdout, 'private fixture stderr')
            with self.subTest(stdout=stdout), patch.object(helper.subprocess, 'run', return_value=failed), \
                 self.assertRaises(RuntimeError) as error:
                helper.run(*command)
            self.assertNotIn('private fixture stderr', str(error.exception))

    def test_original_function_bodies_and_generated_shell_parse(self):
        functions = helper.r5_functions(ORIGINAL, self.root)
        source = ORIGINAL.decode()
        for name in helper.FUNCTIONS:
            # The function text in the generated library is copied from the
            # frozen original, without hand-translated nmcli commands.
            start = functions.index(name + '(){')
            tail = functions[start:]
            next_start = __import__('re').search(r'^\w+\(\)\{', tail[len(name) + 3:], __import__('re').M)
            end = len(name) + 3 + next_start.start() if next_start else len(tail)
            body = tail[:end].strip()
            self.assertIn(body, source)
        self.assertNotIn('remove_private_history(){', functions)
        self.assertNotIn('seal_now(){', functions)
        self.assertNotIn('case "${1:-help}"', functions)
        for source_text in [functions,
                            helper.worker_script(self.root / 'library.sh', 'wlan0', self.root)]:
            parsed = subprocess.run(['/bin/bash', '-n'], input=source_text, text=True,
                                    capture_output=True, timeout=5)
            self.assertEqual(parsed.returncode, 0, parsed.stderr)

    def test_real_bash_worker_uses_r5_cleanup_and_preserves_unrelated_files(self):
        directory = self.root / 'fixture-bin'
        directory.mkdir()
        state_path = self.root / 'nm-state.json'
        log_path = self.root / 'commands.jsonl'
        profiles = self.root / 'etc/NetworkManager/system-connections'
        home_uuid = '11111111-1111-1111-1111-111111111111'
        ap_uuid = '22222222-2222-2222-2222-222222222222'
        phone_uuid = '33333333-3333-3333-3333-333333333333'
        eth_uuid = '44444444-4444-4444-4444-444444444444'
        rows = {
            home_uuid: {'name': 'Fixture Home', 'type': '802-11-wireless', 'file': 'home.nmconnection'},
            ap_uuid: {'name': helper.SSID, 'type': '802-11-wireless', 'file': 'Microduck-Setup.nmconnection'},
            phone_uuid: {'name': 'Fixture Phone', 'type': 'wifi', 'file': 'phone.nmconnection'},
            eth_uuid: {'name': 'Ethernet', 'type': '802-3-ethernet', 'file': 'wired.nmconnection'},
        }
        for identifier, row in rows.items():
            (profiles / row['file']).write_text(
                '[connection]\nuuid=' + identifier + '\ntype=' + row['type'] + '\n')
        (profiles / 'orphan.nmconnection').write_text('[wifi]\nssid=orphan\n')
        state_path.write_text(json.dumps(rows))
        state_dir = self.root / 'var/lib/microduck-wifi-setup'
        state_dir.mkdir(parents=True)
        for name in ('skip-until-sealed', 'provisioned', 'ap-verified'):
            (state_dir / name).write_text('existing')
        preserved = {}
        for name in ('etc/machine-id', 'etc/ssh/ssh_host_ed25519_key',
                     'home/radxa/.ssh/authorized_keys', 'etc/shadow',
                     'opt/robot/model.onnx', 'etc/robot/calibration.json'):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'unchanged fixture ' + name.encode())
            preserved[path] = path.read_bytes()
        executable = '''#!{python}
import json,os,sys
from pathlib import Path
args=sys.argv[1:];cmd=Path(sys.argv[0]).name
state=Path(os.environ['FIXTURE_STATE']);log=Path(os.environ['FIXTURE_LOG'])
with log.open('a') as stream:stream.write(json.dumps([cmd,*args])+'\\n')
if cmd in ('systemctl','chown'):sys.exit(0)
rows=json.loads(state.read_text())
if args==['-g','WIFI-PROPERTIES.AP','device','show','wlan0']:print('yes')
elif args==['-t','-f','UUID,TYPE','connection','show']:
 for identity,row in rows.items():print(identity+':'+row['type'])
elif args[:5]==['-g','connection.id','connection','show','uuid']:
 print(rows[args[5]]['name'])
elif args[:3]==['connection','delete','uuid']:
 row=rows.pop(args[3]);(Path(os.environ['FIXTURE_PROFILES'])/row['file']).unlink(missing_ok=True)
 state.write_text(json.dumps(rows))
elif args[:2] in (['connection','load'],['connection','reload']):pass
else:
 print('unexpected fixture command',file=sys.stderr);sys.exit(9)
'''.format(python=sys.executable)
        for command in ('nmcli', 'systemctl', 'chown'):
            path = directory / command
            path.write_text(executable)
            path.chmod(0o755)
        library = self.root / 'fixture-library.sh'
        library.write_text(helper.r5_functions(ORIGINAL, self.root) +
                           '\n# Test isolation: no reads of host legacy Wi-Fi paths.\n'
                           'legacy_wifi_files(){ :; }\n')
        worker = self.root / 'fixture-worker.sh'
        worker.write_text(helper.worker_script(library, 'wlan0', self.root))
        env = {**os.environ, 'PATH': str(directory) + os.pathsep + os.environ['PATH'],
               'FIXTURE_STATE': str(state_path), 'FIXTURE_LOG': str(log_path),
               'FIXTURE_PROFILES': str(profiles)}
        result = subprocess.run(['/bin/bash', str(worker)], env=env, text=True,
                                capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        remaining = json.loads(state_path.read_text())
        self.assertEqual(set(remaining), {ap_uuid, eth_uuid})
        self.assertTrue((profiles / 'Microduck-Setup.nmconnection').is_file())
        self.assertTrue((profiles / 'wired.nmconnection').is_file())
        self.assertFalse((profiles / 'orphan.nmconnection').exists())
        self.assertFalse(self.old.exists(), 'R5 recheck removes unlisted Wi-Fi residue')
        self.assertEqual(list(state_dir.iterdir()), [])
        self.assertEqual({path: path.read_bytes() for path in preserved}, preserved)
        calls = [json.loads(line) for line in log_path.read_text().splitlines()]
        restart = calls.index(['systemctl', 'restart', 'microduck-setup.service'])
        first_delete = next(i for i, call in enumerate(calls) if call[:4] ==
                            ['nmcli', 'connection', 'delete', 'uuid'])
        self.assertLess(restart, first_delete, 'R5 AP recovery starts before profile deletion')
        self.assertEqual({call[0] for call in calls}, {'nmcli', 'systemctl', 'chown'})
        self.assertFalse(any(any(word in str(call) for word in ('ssh.service', 'poweroff', 'reboot', 'chpasswd'))
                             for call in calls))


if __name__ == '__main__':
    unittest.main(verbosity=2)

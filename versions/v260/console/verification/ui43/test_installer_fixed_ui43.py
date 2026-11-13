"""Exercise the real installer and status readers without services or hardware.

Run from any directory with Python 3.11+. During development the staged payload
is used; a distributed package falls back to its embedded update archive.
Pass --embedded to exercise that fallback even when a staged tree exists.
"""
import ast
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import shlex
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT.parent / 'ui43_firmware_stage/Microduck-Robotd-FT6-R17'
ARCHIVE = ROOT / 'updates/Microduck-Robotd-FT6-R17.tar.gz'
FORCE_ARCHIVE = '--embedded' in sys.argv
if FORCE_ARCHIVE:
    sys.argv.remove('--embedded')
PAYLOAD_FILES = (
    'gamepad.py', 'pad_settings.py', 'configure.py', 'management_profile.py',
    'management-profile.json', 'drive_settings.py', 'padd.service', 'padd',
)


def payload(directory, force_archive=False):
    if not force_archive and all((STAGE / name).is_file() for name in PAYLOAD_FILES):
        return STAGE
    directory.mkdir(parents=True, exist_ok=True)
    with tarfile.open(ARCHIVE, 'r:gz') as archive:
        for name in PAYLOAD_FILES:
            member = archive.getmember('Microduck-Robotd-FT6-R17/' + name)
            if not member.isfile():
                raise ValueError('Expected a regular payload file: ' + name)
            (directory / name).write_bytes(archive.extractfile(member).read())
    return directory


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def function_bytes(source, name):
    node = next(node for node in ast.parse(source).body
                if isinstance(node, ast.FunctionDef) and node.name == name)
    return ''.join(source.splitlines(keepends=True)[node.lineno - 1:node.end_lineno])


class InstallerFixedSpeedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = tempfile.TemporaryDirectory(prefix='ui43-installer-')
        cls.addClassCleanup(cls.work.cleanup)
        cls.bundle = payload(Path(cls.work.name) / 'payload', force_archive=FORCE_ARCHIVE)
        # Keep production imports isolated from other console verification suites.
        cls.modules = patch.dict(sys.modules)
        cls.modules.start()
        cls.addClassCleanup(cls.modules.stop)
        for name in ('management_profile', 'configure', 'pad_settings'):
            module = load_module(name, cls.bundle / (name + '.py'))
            sys.modules[name] = module
        cls.pad = sys.modules['pad_settings']
        cls.gamepad = load_module('ui43_installer_fixture', cls.bundle / 'gamepad.py')
        cls.drive = load_module('ui43_status_fixture', cls.bundle / 'drive_settings.py')

    def test_upgrade_ignores_old_speeds_and_broken_json_and_preserves_recording(self):
        for previous in ('{"speed":0.1}\n', '{"speed":0.2}\n', '{broken json'):
            with self.subTest(previous=previous), tempfile.TemporaryDirectory() as name:
                root = Path(name)
                base = root / 'opt/robot/feetech-ft5-r5'
                base.mkdir(parents=True)
                (base / 'padd.service').write_bytes((self.bundle / 'padd.service').read_bytes())
                config = root / 'etc/robot/feetech-ft5'
                config.mkdir(parents=True)
                old_speed = config / 'drive-settings.json'
                old_speed.write_text(previous)
                settings = config / 'pad-settings.json'
                original_settings = b'{"mouth_percent":67.0,"head_rad":1.0}\n'
                settings.write_bytes(original_settings)
                last = root / 'var/lib/padd/last.json'
                last.parent.mkdir(parents=True)
                original_clip = b'{"fixture":"last manually saved clip"}\n'
                last.write_bytes(original_clip)
                dropin = root / self.gamepad.PAD_DROPIN
                dropin.parent.mkdir(parents=True)
                old_dropin = ('[Service]\nExecStart=\nExecStart=/old/padd '
                              '--max-linear 0.2 --max-linear-backward 0.2\n')
                dropin.write_text(old_dropin)
                calls = []
                with patch.object(self.gamepad, 'ROOT', root), \
                     patch.object(self.gamepad, 'BASE', base), \
                     patch.object(self.gamepad, 'CONFIG', config / 'robotd.toml'), \
                     patch.object(self.gamepad, 'SETTINGS_PATH', settings), \
                     patch.object(self.gamepad, 'load', lambda: self.pad.load(settings)), \
                     patch.object(self.gamepad, 'save', side_effect=AssertionError('must preserve existing settings')), \
                     patch.object(self.gamepad, 'run', side_effect=lambda *args, **kw: calls.append(args)), \
                     contextlib.redirect_stdout(io.StringIO()):
                    self.gamepad.upgrade_client(deferred=True)
                    first = dropin.read_bytes()
                    self.gamepad.upgrade_client(deferred=True)
                result = dropin.read_text()
                self.assertEqual(dropin.read_bytes(), first)
                self.assertNotEqual(result, old_dropin)
                command = next(line for line in result.splitlines() if line.startswith('ExecStart=/'))
                arguments = shlex.split(command.removeprefix('ExecStart='))
                self.assertNotIn('--max-linear', arguments)
                self.assertNotIn('--max-linear-backward', arguments)
                self.assertNotIn('--max-angular', arguments)
                self.assertEqual(arguments[arguments.index('--max-head') + 1], '1')
                self.assertEqual(arguments[arguments.index('--input-settings') + 1], str(settings))
                self.assertIn('\nStateDirectory=padd\n', result)
                self.assertIn('\nRuntimeDirectory=padd\n', result)
                self.assertIn('\nStateDirectory=padd\n', (root / 'etc/systemd/system/padd.service').read_text())
                self.assertEqual(last.read_bytes(), original_clip)
                self.assertEqual(settings.read_bytes(), original_settings)
                self.assertEqual(old_speed.read_text(), previous)
                self.assertEqual([call[0] for call in calls], ['systemd-sysusers'] * 2,
                                 'deferred installer must not restart services or send robot commands')

    def test_non_deferred_upgrade_restarts_only_the_handpad_service(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            base = root / 'opt/robot/feetech-ft5-r5'
            base.mkdir(parents=True)
            (base / 'padd.service').write_bytes((self.bundle / 'padd.service').read_bytes())
            settings = root / 'pad.json'
            settings.write_text('{"mouth_percent":75,"head_rad":0.5}')
            calls = []
            with patch.object(self.gamepad, 'ROOT', root), \
                 patch.object(self.gamepad, 'BASE', base), \
                 patch.object(self.gamepad, 'SETTINGS_PATH', settings), \
                 patch.object(self.gamepad, 'load', lambda: self.pad.load(settings)), \
                 patch.object(self.gamepad, 'run', side_effect=lambda *args, **kw: calls.append(args)), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.gamepad.upgrade_client()
            self.assertEqual(calls, [
                ('systemd-sysusers', str(base / 'padd-sysusers.conf')),
                ('systemctl', 'daemon-reload'),
                ('systemctl', '--no-reload', 'enable', 'padd.service'),
                ('systemctl', 'restart', 'padd.service'),
            ])

    def test_original_native_defaults_and_binary_are_preserved(self):
        source = (ROOT / 'verification/ui42/native-source/padd/src/main.rs').read_text()
        for name in ('max_linear', 'max_linear_backward'):
            match = re.search(r'#\[arg\(long, default_value_t = ([0-9.]+)\)\]\s*' + name + r': f64', source)
            self.assertIsNotNone(match, name)
            self.assertEqual(float(match.group(1)), .3)
        match = re.search(r'#\[arg\(long, default_value_t = ([0-9.]+)\)\]\s*max_angular: f64', source)
        self.assertEqual(float(match.group(1)), 1.5)
        metadata = json.loads((ROOT / 'verification/ui42/native/native-build.json').read_text())
        self.assertEqual(hashlib.sha256((self.bundle / 'padd').read_bytes()).hexdigest(),
                         metadata['binary_sha256'])

    def test_status_uses_original_defaults_and_refuses_old_explicit_speed(self):
        d = self.drive
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            report = root / 'input-settings.json'
            report.write_text('{"pid":123}')
            recorder = root / 'recorder.json'
            recorder.write_text(json.dumps({'pid':123, 't_ms':9500, 'phase':'idle',
                'elapsed_ms':0, 'duration_ms':6000, 'has_last':True, 'reason':''}))
            proc = root / 'proc'
            (proc / '123').mkdir(parents=True)
            command = proc / '123/cmdline'
            with patch.object(d, 'REPORT', report), patch.object(d, 'RECORDER', recorder), \
                 patch.object(d, 'PROC', proc), patch.object(d.time, 'monotonic_ns', lambda:10_000_000_000):
                for flags in ([], ['--max-linear', '0.3', '--max-linear-backward', '0.3']):
                    command.write_bytes(('\0'.join([str(d.BASE / 'padd'), *flags]) + '\0').encode())
                    before = {path: path.read_bytes() for path in (report, recorder, command)}
                    result = d.status()
                    self.assertEqual(result['speed'], .3)
                    self.assertTrue(result['fixed'])
                    self.assertNotIn('error', result)
                    self.assertTrue(result['recorder']['available'])
                    self.assertEqual(before, {path: path.read_bytes() for path in before})
                command.write_bytes(('\0'.join([str(d.BASE / 'padd'), '--max-linear', '0.2',
                                     '--max-linear-backward', '0.2']) + '\0').encode())
                result = d.status()
                self.assertIsNone(result['speed'])
                self.assertIn('请安装配套更新', result['error'])
                self.assertTrue(result['recorder']['available'], 'speed migration must not hide recorder metadata')

    def test_recorder_status_function_is_byte_identical_to_ui42(self):
        original = (ROOT / 'verification/ui42/installer-source/drive_settings.py').read_text()
        current = (self.bundle / 'drive_settings.py').read_text()
        self.assertEqual(function_bytes(original, 'recorder_status'),
                         function_bytes(current, 'recorder_status'))


if __name__ == '__main__':
    unittest.main(verbosity=2)

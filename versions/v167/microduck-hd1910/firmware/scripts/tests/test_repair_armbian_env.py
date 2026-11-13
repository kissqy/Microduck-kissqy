"""Temporary-file regression tests; no real boot config, sysfs or services used."""
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('repair', SCRIPTS / 'repair-armbian-env.py')
repair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)
LEGACY = (Path(__file__).parent / 'fixtures/armbian-hardware-optimization-26.2.1.sh').read_bytes()
ENV = (b'verbosity=1\nfdtfile=rockchip/rk3566-radxa-zero3.dtb\n'
       b'rootdev=UUID=00000000-0000-0000-0000-000000000000\nrootfstype=ext4\n'
       b'overlays=uart2-m0 npu-enable\n'
       b'usbstoragequirks=0x2537:0x1066:u,0x2537:0x1068:u\n')


def snapshot(path):
    meta = path.stat()
    return (path.read_bytes(), meta.st_ino, meta.st_mtime_ns, meta.st_ctime_ns,
            meta.st_uid, meta.st_gid, meta.st_mode)


class RepairTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.target = self.root / 'armbian-hardware-optimization'
        self.target.write_bytes(LEGACY)
        self.target.chmod(0o755)
        self.env = self.root / 'armbianEnv.txt'
        self.env.write_bytes(ENV)
        self.backups = self.root / 'backups'
        # Unit tests also run on macOS; GNU sync -f is exercised by Linux tests.
        sync = patch.object(repair, 'sync_filesystem')
        self.sync = sync.start()
        self.addCleanup(sync.stop)

    def run_repair(self, apply=True):
        return repair.repair(self.target, self.env, self.backups, apply=apply)

    def test_check_is_read_only(self):
        before = snapshot(self.target), snapshot(self.env)
        self.assertEqual(self.run_repair(False)['status'], 'needs-fix')
        self.assertEqual(before, (snapshot(self.target), snapshot(self.env)))
        self.assertFalse(self.backups.exists())

    def test_backup_apply_idempotence_and_restore(self):
        before = snapshot(self.env)
        result = self.run_repair()
        backup = Path(result['backup'])
        self.assertEqual((backup / self.target.name).read_bytes(), LEGACY)
        self.assertEqual((backup / self.env.name).read_bytes(), ENV)
        self.assertEqual(snapshot(self.env), before)
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o755)
        fixed = snapshot(self.target)
        self.assertEqual(self.run_repair()['status'], 'already-fixed')
        self.assertEqual(snapshot(self.target), fixed)
        self.assertEqual(len(list(self.backups.iterdir())), 1)
        self.assertEqual(repair.restore(backup, self.target)['status'], 'restored')
        self.assertEqual(self.target.read_bytes(), LEGACY)
        self.assertEqual(repair.restore(backup, self.target)['status'], 'already-restored')
        self.assertEqual(snapshot(self.env), before)

    def test_unrelated_board_setup_is_preserved(self):
        original = LEGACY.replace(b'prepare_board() { :; }', b'prepare_board() { echo board-specific; }')
        fixed = repair.patched_script(original)
        self.assertIn(b'prepare_board() { echo board-specific; }', fixed)
        self.assertIn(b'prepare_board &', fixed)
        self.assertIn(b'add_usb_storage_quirks || exit $?', fixed)
        self.assertNotIn(b'add_usb_storage_quirks &', fixed)

    def test_unknown_vendor_function_is_not_overwritten(self):
        self.target.write_bytes(LEGACY.replace(b'sync &', b'sync -f /boot/armbianEnv.txt'))
        before = snapshot(self.target)
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            self.run_repair()
        self.assertEqual(snapshot(self.target), before)
        self.assertFalse(self.backups.exists())

    def test_ambiguous_invocation_is_refused(self):
        for suffix in (b'\nadd_usb_storage_quirks &\n',):
            with self.assertRaisesRegex(ValueError, 'invocation'):
                repair.patched_script(LEGACY + suffix)

    def test_missing_script_is_not_applicable(self):
        self.target.unlink()
        self.assertEqual(self.run_repair()['status'], 'not-applicable')
        self.assertFalse(self.backups.exists())

    def test_empty_config_is_refused(self):
        self.env.write_bytes(b'')
        with self.assertRaisesRegex(ValueError, 'empty'):
            self.run_repair()
        self.assertEqual(self.target.read_bytes(), LEGACY)

    def test_symlink_is_refused(self):
        real = self.root / 'real'
        self.target.rename(real)
        self.target.symlink_to(real)
        with self.assertRaisesRegex(ValueError, 'regular file'):
            self.run_repair()
        self.assertEqual(real.read_bytes(), LEGACY)

    def test_target_replace_failure_leaves_original_and_backup(self):
        replace = repair.os.replace
        def fail(source, target):
            if target == self.target:
                raise OSError('injected rename failure')
            return replace(source, target)
        before = snapshot(self.target)
        with patch.object(repair.os, 'replace', side_effect=fail):
            with self.assertRaisesRegex(OSError, 'injected'):
                self.run_repair()
        self.assertEqual(snapshot(self.target), before)
        backup = next(self.backups.iterdir())
        self.assertEqual((backup / self.target.name).read_bytes(), LEGACY)
        self.assertFalse(list(self.root.glob('.armbian-hardware-optimization.*')))

    def test_backup_sync_failure_does_not_install(self):
        self.sync.side_effect = OSError('backup sync failed')
        before = snapshot(self.target)
        with self.assertRaisesRegex(OSError, 'backup sync'):
            self.run_repair()
        self.assertEqual(snapshot(self.target), before)

    def test_concurrent_vendor_update_is_not_overwritten(self):
        changed = LEGACY + b'\n# vendor changed the script\n'
        def concurrent(path):
            if path == self.backups:
                self.target.write_bytes(changed)
        self.sync.side_effect = concurrent
        with self.assertRaisesRegex(ValueError, 'changed during backup'):
            self.run_repair()
        self.assertEqual(self.target.read_bytes(), changed)

    def test_restore_refuses_later_vendor_update(self):
        backup = Path(self.run_repair()['backup'])
        changed = self.target.read_bytes() + b'\n# vendor update\n'
        self.target.write_bytes(changed)
        with self.assertRaisesRegex(ValueError, 'changed since repair'):
            repair.restore(backup, self.target)
        self.assertEqual(self.target.read_bytes(), changed)

    def test_restore_refuses_corrupted_backup(self):
        backup = Path(self.run_repair()['backup'])
        (backup / self.target.name).write_bytes(b'corrupt')
        before = snapshot(self.target)
        with self.assertRaisesRegex(ValueError, 'does not match'):
            repair.restore(backup, self.target)
        self.assertEqual(snapshot(self.target), before)


@unittest.skipUnless(sys.platform == 'linux', 'requires GNU coreutils; use the documented Linux container')
class BootWriterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.boot = self.root / 'boot'
        self.boot.mkdir()
        self.env = self.boot / 'armbianEnv.txt'
        self.env.write_bytes(ENV)
        self.env.chmod(0o640)
        if os.geteuid() == 0:
            os.chown(self.env, 1016, 1016)
        self.sysfs = self.root / 'sysfs'
        self.sysfs.write_text('unchanged')
        self.trace = self.root / 'trace'
        self.work = self.root / 'work'
        self.work.mkdir()

    def run_writer(self, usb='', fault='', legacy=False):
        source = LEGACY.decode() if legacy else repair.patched_script(LEGACY).decode()
        function = repair.FUNCTION.search(source)[0]
        function = function.replace('/boot/armbianEnv.txt', str(self.env))
        function = function.replace('/sys/module/usb_storage/parameters/quirks', str(self.sysfs))
        function = function.replace('/tmp/armbian-usb-quirks.XXXXXX', str(self.work / 'quirks.XXXXXX'))
        function = function.replace('/tmp/${0##*/}.XXXXXX', str(self.work / 'legacy.XXXXXX'))
        mocks = f'''
lsusb() {{ printf '%s' {shlex.quote(usb)}; }}
sync() {{ printf 'sync %s\\n' "$*" >> {shlex.quote(str(self.trace))}; command sync "$@"; }}
mv() {{ printf 'mv %s\\n' "$*" >> {shlex.quote(str(self.trace))}; command mv "$@"; }}
'''
        faults = {
            'copy': 'cat() { case "$1" in */env) printf partial; return 1;; *) command cat "$@";; esac; }',
            'presync': 'sync() { return 1; }',
            'rename': 'mv() { return 1; }',
            'postsync': 'sync() { if [ "$1" = -f ]; then return 1; fi; command sync "$@"; }',
            'usb': 'lsusb() { return 1; }',
        }
        result = subprocess.run(['bash'], input=mocks + faults.get(fault, '') + '\n' + function + '\nadd_usb_storage_quirks\n',
                                text=True, capture_output=True)
        self.assertFalse(list(self.boot.glob('.armbianEnv.txt.*')))
        self.assertFalse(list(self.work.iterdir()))
        return result

    def test_legacy_rewrites_unchanged_config(self):
        before = snapshot(self.env)
        self.assertEqual(self.run_writer(legacy=True).returncode, 0)
        after = snapshot(self.env)
        self.assertEqual(before[0], after[0])
        self.assertNotEqual(before[1], after[1])

    def test_no_change_does_not_rewrite_or_sync_boot_config(self):
        before = snapshot(self.env)
        for _ in range(2):
            result = self.run_writer()
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(snapshot(self.env), before)
        self.assertFalse(self.trace.exists())
        self.assertEqual(self.sysfs.read_text(), '0x2537:0x1066:u,0x2537:0x1068:u\n')

    def test_changed_config_preserves_boot_parameters_and_metadata(self):
        before = snapshot(self.env)
        usb = 'Bus 001 Device 002: ID 1058:1234 Western Digital\n'
        result = self.run_writer(usb=usb)
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = ENV.replace(b'0x2537:0x1068:u', b'0x2537:0x1068:u,0x1058:0x1234:u')
        self.assertEqual(self.env.read_bytes(), expected)
        self.assertEqual(snapshot(self.env)[4:], before[4:])
        calls = self.trace.read_text().splitlines()
        self.assertEqual(len(calls), 3)
        self.assertTrue(calls[0].startswith('sync -- '))
        self.assertTrue(calls[1].startswith('mv -fT -- '))
        self.assertTrue(calls[2].startswith('sync -f -- '))
        after = snapshot(self.env)
        self.assertEqual(self.run_writer(usb=usb).returncode, 0)
        self.assertEqual(snapshot(self.env), after)
        self.assertEqual(self.trace.read_text().splitlines(), calls)

    def test_missing_quirks_and_newline_cleanup_preserve_all_other_fields(self):
        for content in (ENV[:ENV.index(b'usbstoragequirks=')], b'\n' + ENV.rstrip(b'\n') + b'\n\n'):
            with self.subTest(content=content):
                self.env.write_bytes(content)
                result = self.run_writer()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.env.read_bytes(), ENV)

    def test_failures_before_rename_leave_original_complete(self):
        for fault in ('copy', 'presync', 'rename', 'usb'):
            with self.subTest(fault=fault):
                before = snapshot(self.env)
                result = self.run_writer(usb='Bus 001 Device 002: ID 1058:1234 WD\n', fault=fault)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(snapshot(self.env), before)
                self.assertEqual(self.sysfs.read_text(), 'unchanged')

    def test_failure_after_rename_reports_error_with_complete_new_file(self):
        result = self.run_writer(usb='Bus 001 Device 002: ID 1058:1234 WD\n', fault='postsync')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.env.read_bytes(), ENV.replace(b'0x2537:0x1068:u', b'0x2537:0x1068:u,0x1058:0x1234:u'))

    def test_empty_or_missing_config_is_not_recreated(self):
        self.env.write_bytes(b'')
        self.assertEqual(self.run_writer().returncode, 1)
        self.assertEqual(self.env.read_bytes(), b'')
        self.env.unlink()
        self.assertEqual(self.run_writer().returncode, 0)
        self.assertFalse(self.env.exists())


if __name__ == '__main__':
    unittest.main()

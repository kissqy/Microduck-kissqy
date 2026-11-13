"""V232 rollback and compatibility with the original SGID service restriction."""
import grp
import hashlib
import importlib.util
import os
from pathlib import Path
import pwd
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

PC = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PC))
sys.path.insert(0, str(PC / 'verification/v230'))
from test_support import FW
sys.path.insert(0, str(FW))
import gamepad
import ai_input_lease
import ai_mouth_lease


def install_config(root):
    with patch.object(gamepad, 'ROOT', root), patch.object(gamepad, 'BASE', FW), \
         patch.object(gamepad, 'load', return_value={'mouth_percent':100, 'head_rad':1}), \
         patch.object(gamepad, 'save'), patch.object(gamepad, 'SETTINGS_PATH', root/'settings.json'), \
         patch.object(gamepad, 'run') as runner:
        gamepad.upgrade_client(deferred=True)
    return (root/gamepad.PAD_DROPIN).read_text(), runner


class RuntimeConfigTests(unittest.TestCase):
    def test_upgrade_overwrites_the_owned_v231_prestart_step(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            old = root/gamepad.PAD_DROPIN
            old.parent.mkdir(parents=True)
            old.write_text('[Service]\nExecStartPre=/usr/bin/python3 /opt/robot/feetech-ft5-r5/padd_runtime.py\n')
            text, runner = install_config(root)
        self.assertNotIn('ExecStartPre', text)
        self.assertNotIn('padd_runtime.py', text)
        self.assertFalse((FW/'padd_runtime.py').exists())
        self.assertTrue(all('padd_runtime' not in str(call) for call in runner.call_args_list))
        self.assertIn('ExecStart=/usr/bin/python3 '+str(FW/'startup_gate.py')+' --timeout 60 --exec '+str(FW/'padd'), text)

    def test_manager_declares_all_shared_directories_without_sgid(self):
        with tempfile.TemporaryDirectory() as folder:
            text, _ = install_config(Path(folder))
        self.assertIn('Group=robot\n', text)
        self.assertIn('UMask=0022\n', text)
        self.assertIn('RuntimeDirectory=\nRuntimeDirectory=padd padd/ai-input padd/ai-mouth\n', text)
        self.assertIn('RuntimeDirectoryMode=0770\n', text)
        self.assertNotIn('2770', text)
        original = (FW/'padd.service').read_text()
        self.assertIn('User=padd\n', original)
        self.assertIn('RestrictSUIDSGID=yes\n', original)
        self.assertIn('NoNewPrivileges=yes\n', original)
        self.assertEqual(hashlib.sha256((FW/'padd').read_bytes()).hexdigest(),
                         'fd9fb6b99083d9f1eeee5414910dc861d8f88c805f182e6e4a57d9c7b6834bbd')

    def test_merged_unit_is_accepted_by_systemd_parser(self):
        if not shutil.which('systemd-analyze'): self.skipTest('systemd-analyze unavailable')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            text, _ = install_config(root)
            unit = root/'padd.service'
            shutil.copy2(FW/'padd.service', unit)
            dropin = root/'padd.service.d/zzzz-r17-0151.conf'
            dropin.parent.mkdir()
            dropin.write_text(text)
            result = subprocess.run(['systemd-analyze','verify','--man=no','--generators=no',str(unit)],
                                    text=True,capture_output=True,timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_input_lease_remains_readable_despite_restrictive_ssh_umask(self):
        with tempfile.TemporaryDirectory() as folder:
            lease = ai_input_lease.InputLease(lambda:False, directory=Path(folder), requires_ack=lambda:False)
            old = os.umask(0o077)
            try:
                lease.acquire()
                for path in (lease.path,lease.ack,lease.solo):
                    self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o644)
                lease.ensure_current()
            finally:
                os.umask(old)
                lease.close()

    def test_upgrade_cleanup_removes_the_owned_v231_helper(self):
        import json
        self.assertNotIn('padd_runtime.py',json.loads((FW/'install-files.json').read_text()))
        spec=importlib.util.spec_from_file_location('v232_file_installer',FW/'install-files.py')
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder:
            installed=Path(folder)
            legacy=installed/'padd_runtime.py'
            legacy.write_text('retired V231 helper')
            module.cleanup(FW,installed,previous_owned={'padd_runtime.py'})
            self.assertFalse(legacy.exists())

    def test_real_sgid_filter_rejects_old_mode_but_accepts_current_leases(self):
        if sys.platform != 'linux': self.skipTest('Linux seccomp test')
        code = r'''
import ctypes,errno,grp,json,os,pwd,stat,sys,tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,sys.argv[1])
import ai_input_lease,ai_mouth_lease
try: lib=ctypes.CDLL('libseccomp.so.2',use_errno=True)
except OSError: sys.exit(77)
class Compare(ctypes.Structure):
 _fields_=[('arg',ctypes.c_uint),('op',ctypes.c_uint),('datum_a',ctypes.c_uint64),('datum_b',ctypes.c_uint64)]
lib.seccomp_init.argtypes=[ctypes.c_uint32];lib.seccomp_init.restype=ctypes.c_void_p
lib.seccomp_syscall_resolve_name.argtypes=[ctypes.c_char_p];lib.seccomp_syscall_resolve_name.restype=ctypes.c_int
lib.seccomp_rule_add_array.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_int,ctypes.c_uint,ctypes.POINTER(Compare)]
lib.seccomp_load.argtypes=[ctypes.c_void_p]
lib.seccomp_release.argtypes=[ctypes.c_void_p]
context=lib.seccomp_init(0x7fff0000)
assert context
for name,index in [(b'chmod',1),(b'fchmod',1),(b'fchmodat',2),(b'mkdir',1),(b'mkdirat',2)]:
 number=lib.seccomp_syscall_resolve_name(name)
 if number<0:continue
 for bit in (0o2000,0o4000):
  rule=Compare(index,7,bit,bit)
  assert lib.seccomp_rule_add_array(context,0x00050000|errno.EPERM,number,1,ctypes.byref(rule))==0
assert lib.seccomp_load(context)==0
lib.seccomp_release(context)
with tempfile.TemporaryDirectory() as folder:
 directory=Path(folder)
 fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY)
 try:
  try:os.fchmod(fd,0o2770)
  except PermissionError as error:assert error.errno==errno.EPERM
  else:raise AssertionError('positive control did not reject SGID')
 finally:os.close(fd)
 for module in (ai_input_lease,ai_mouth_lease):
  path=directory/module.__name__
  path.mkdir(mode=0o770)
  os.chmod(path,0o770)
  if module is ai_input_lease:
   lease=module.InputLease(lambda:False,directory=path,requires_ack=lambda:False)
  else:
   lease=module.MouthLease(lambda:True,lambda:False,directory=path,requires_ack=lambda:False)
  account=pwd.getpwuid(os.getuid());shared=grp.getgrgid(os.getgid())
  with patch.object(module,'DIRECTORY',path), patch.object(module.os,'geteuid',return_value=0), \
       patch('pwd.getpwnam',return_value=account), patch('grp.getgrnam',return_value=shared):
   lease._prepare()
  assert stat.S_IMODE(path.stat().st_mode)==0o770
  try:
   lease.acquire()
   assert stat.S_IMODE(lease.path.stat().st_mode)==0o644
  finally:lease.close()
print('Old SGID mode denied; V232 input and mouth lease acquire/cleanup succeeded under the same mode-bit filter')
'''
        result = subprocess.run([sys.executable,'-c',code,str(PC)],text=True,capture_output=True,timeout=10)
        if result.returncode == 77:self.skipTest('libseccomp unavailable')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('Old SGID mode denied',result.stdout)


class InstallerReadbackTests(unittest.TestCase):
    @staticmethod
    def installer():
        spec=importlib.util.spec_from_file_location('v232_system_installer',FW/'system-repair/install-system-repair.py')
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_existing_wrong_component_bytes_and_modes_are_repaired_and_read_back(self):
        installer=self.installer()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            program=root/installer.PROGRAM
            program.parent.mkdir(parents=True)
            program.write_bytes(b'old installed onboarding program')
            program.chmod(0o644)
            home=root/'etc/NetworkManager/system-connections/home.nmconnection'
            home.parent.mkdir(parents=True)
            home.write_bytes(b'private fixture network')
            result=installer.apply(root,live=False)
            self.assertIs(result['readback_verified'],True)
            self.assertEqual(program.stat().st_mode & 0o7777,0o700)
            self.assertEqual(home.read_bytes(),b'private fixture network')
            self.assertEqual(installer.apply(root,live=False)['changed'],[])

    def test_silent_failed_install_cannot_report_success(self):
        installer=self.installer()
        original=installer.repair_module()
        writer=original.atomic_write
        def corrupt(path,data,metadata):
            return writer(path,b'broken portal' if path.name=='microduck-setup-portal.py' else data,metadata)
        with tempfile.TemporaryDirectory() as folder, patch.object(installer,'repair_module',return_value=original), \
             patch.object(original,'atomic_write',side_effect=corrupt):
            with self.assertRaisesRegex(RuntimeError,'读回不一致.*microduck-setup-portal.py'):
                installer.apply(Path(folder),live=False)


if __name__ == '__main__': unittest.main()

import importlib.util
from pathlib import Path
import tempfile
import types
import unittest
import sys
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('gamepad',Path(__file__).with_name('gamepad.py'))
gamepad=importlib.util.module_from_spec(spec);spec.loader.exec_module(gamepad)
COMMAND_RUN=gamepad.run

class GamepadInstallTests(unittest.TestCase):
    def test_non_utf8_command_output_does_not_abort_success_or_hide_failure_exit(self):
        command=[sys.executable,'-c',"import sys;sys.stdout.buffer.write(b'unit\\xff\\n');sys.stderr.buffer.write(b'warning\\xff\\n')"]
        result=COMMAND_RUN(*command)
        self.assertEqual(result.returncode,0);self.assertIn('\ufffd',result.stdout);self.assertIn('\ufffd',result.stderr)
        with self.assertRaises(gamepad.subprocess.CalledProcessError) as error:
            COMMAND_RUN(sys.executable,'-c',"import sys;sys.stdout.buffer.write(b'unit\\xff');sys.exit(7)")
        self.assertEqual(error.exception.returncode,7)

    def test_legacy_utf16_unit_and_dropin_are_replaced_without_reading_systemctl_cat(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);bundle=root/'bundle';bundle.mkdir();system=root/'system';calls=[]
            (bundle/'padd.service').write_bytes(Path(__file__).with_name('padd.service').read_bytes())
            target=system/'etc/systemd/system/padd.service';target.parent.mkdir(parents=True);target.write_bytes('[Service]\n'.encode('utf-16'))
            dropin=system/gamepad.PAD_DROPIN;dropin.parent.mkdir(parents=True);dropin.write_bytes('[Service]\nExecStart=/old/padd\n'.encode('utf-16'))
            def run(*args,**kwargs):
                calls.append(args)
                if args[:2]==('systemctl','cat'):
                    raise UnicodeDecodeError('utf-8',b'\xff',0,1,'invalid start byte')
                return types.SimpleNamespace(returncode=0,stdout='',stderr='')
            with patch.object(gamepad,'ROOT',system),patch.object(gamepad,'BASE',bundle),patch.object(gamepad,'run',run),patch.object(gamepad,'SETTINGS_PATH',root/'settings.json'),patch.object(gamepad,'load',return_value={'mouth_percent':70,'head_rad':2.5}),patch.object(gamepad,'save'):
                gamepad.upgrade_client()
            self.assertEqual(target.read_bytes(),(bundle/'padd.service').read_bytes())
            self.assertIn(str(bundle/'padd'),dropin.read_text(encoding='utf-8'))
            self.assertFalse(dropin.read_bytes().startswith(b'\xff\xfe'))
            self.assertIn(('systemctl','restart','padd.service'),calls)
            self.assertFalse(any(c[:2]==('systemctl','cat') for c in calls))

    def test_missing_padd_and_masked_webpad_are_installed_by_real_input_installers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);bundle=root/'bundle';target_root=root/'system';calls=[]
            for name in gamepad.FILES:
                p=bundle/'gamepad-r7'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('R7:'+name)
            for name in ('padd.service','microduck-webpad.service','microduck-webpad.socket'):
                (bundle/name).write_text('[Service]\nExecStart=/bundle/'+name+'\n')
            mask=root/'mask';mask.write_text('mask sentinel')
            webpad=target_root/'etc/systemd/system/microduck-webpad.service';webpad.parent.mkdir(parents=True);webpad.symlink_to(mask)
            padd=target_root/'etc/systemd/system/padd.service'
            def run(*args,check=True):
                calls.append(args)
                rc=1 if args[:3]==('systemctl','cat','padd.service') and not padd.exists() else 0
                if check and rc:raise gamepad.subprocess.CalledProcessError(rc,args)
                return types.SimpleNamespace(returncode=rc,stdout='',stderr='')
            with patch.object(gamepad,'ROOT',target_root),patch.object(gamepad,'BASE',bundle),patch.object(gamepad,'SETTINGS_PATH',root/'settings.json'),patch.object(gamepad,'run',run),patch.object(gamepad,'save'),patch.object(gamepad,'load',return_value={'mouth_percent':70,'head_rad':2.5}),patch.object(gamepad,'verify_webpad') as verified:
                gamepad.install(bundle)
                gamepad.upgrade_client()
                gamepad.install_webpad()
            self.assertEqual(padd.read_bytes(),(bundle/'padd.service').read_bytes())
            self.assertFalse(webpad.is_symlink());self.assertEqual(webpad.read_bytes(),(bundle/'microduck-webpad.service').read_bytes())
            self.assertEqual(mask.read_text(),'mask sentinel','installer must replace masks without following their target')
            self.assertIn(('systemctl','restart','padd.service'),calls)
            self.assertIn(('systemctl','restart','microduck-webpad.socket'),calls)
            verified.assert_called_once()

    def test_upgrade_webpad_start_does_not_wait_for_socket_readback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);bundle=root/'bundle';bundle.mkdir();(bundle/'microduck-webpad.service').write_text('[Service]\n');(bundle/'microduck-webpad.socket').write_text('[Socket]\n')
            with patch.object(gamepad,'ROOT',root/'system'),patch.object(gamepad,'BASE',bundle),patch.object(gamepad,'run',return_value=types.SimpleNamespace(returncode=0,stdout='',stderr='')),patch.object(gamepad,'verify_webpad',side_effect=AssertionError('no upgrade readiness gate')):
                gamepad.install_webpad(verify=False)
            self.assertTrue((root/'system/etc/systemd/system/microduck-webpad.service').is_file())

    def test_input_binary_replacement_does_not_truncate_existing_inode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'new';target=root/'binary'
            source.write_bytes(b'new executable');target.write_bytes(b'running executable')
            with target.open('rb') as running:
                gamepad.replace_owned_file(source,target,0o755)
                self.assertEqual(running.read(),b'running executable')
            self.assertEqual(target.read_bytes(),source.read_bytes());self.assertEqual(target.stat().st_mode&0o777,0o755)

    def test_complete_input_setup_writes_once_and_does_not_start_until_caller_is_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);bundle=root/'bundle';target=root/'system';calls=[]
            for name in gamepad.FILES:
                path=bundle/'gamepad-r7'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('R7:'+name)
            for name in ('padd.service','microduck-webpad.service','microduck-webpad.socket'):(bundle/name).write_text('[Service]\n')
            def run(*args,**_):calls.append(args);return types.SimpleNamespace(returncode=0,stdout='',stderr='')
            with patch.object(gamepad,'ROOT',target),patch.object(gamepad,'BASE',bundle),patch.object(gamepad,'run',run),patch.object(gamepad,'SETTINGS_PATH',root/'settings'),patch.object(gamepad,'load',return_value={'mouth_percent':60,'head_rad':.5}),patch.object(gamepad,'save'):
                gamepad.prepare_all(bundle)
                self.assertEqual(sum(a[:2]==('modprobe','uinput') for a in calls),1)
                self.assertFalse(any('daemon-reload' in a or 'restart' in a or 'start' in a or 'stop' in a for a in calls))
                self.assertIn(('systemctl','--no-reload','enable','gamesir-xboxd.service','padd.service','microduck-webpad.socket'),calls)
                self.assertTrue((target/'etc/systemd/system/padd.service').exists());self.assertTrue((target/'etc/systemd/system/microduck-webpad.service').exists())
                calls.clear();gamepad.prepare_all(bundle)
                self.assertFalse(any(a[0]=='udevadm' for a in calls),'unchanged input rules need no device trigger')

    def test_firmware_restart_reuses_an_active_listener_without_starting_worker(self):
        with patch.object(gamepad,'webpad_socket_ready',return_value=True),patch.object(gamepad,'run') as run:
            gamepad.ensure_webpad()
        run.assert_not_called()

if __name__=='__main__':unittest.main()

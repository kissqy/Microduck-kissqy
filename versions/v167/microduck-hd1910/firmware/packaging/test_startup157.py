"""Independent service startup and configuration ownership. No hardware writes."""
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock,patch

import configure
import runtime
import gamepad


class StartupTests(unittest.TestCase):
    def test_unit_has_official_restart_without_auxiliary_gates(self):
        for mode in ('motion','commissioning'):
            text=runtime.unit(mode)
            self.assertIn('Restart=always\nRestartSec=2s',text)
            self.assertIn('--port /dev/ttyS2',text)
            for removed in ('uart-service.py','--uart-setup','After=alsa','verify-ready','rebuild-config','updaterd','padd.service'):
                self.assertNotIn(removed,text)
            self.assertEqual('--commissioning' in text,mode=='commissioning')
    def test_explicit_restart_status_queries_once_and_accepts_waiting(self):
        report={'phase':'waiting_for_bus','error':'IMU not ready'}
        with patch.object(runtime,'rpc',return_value=report) as rpc,redirect_stdout(io.StringIO()):
            self.assertEqual(runtime.verify_ready('motion'),report)
        rpc.assert_called_once_with('robot.busStatus',timeout=2)
        with patch.object(runtime,'rpc',side_effect=OSError('IPC starting')) as rpc,redirect_stdout(io.StringIO()):
            self.assertTrue(runtime.verify_ready('motion')['status_pending'])
        self.assertEqual(rpc.call_count,1)
    def test_config_backup_is_made_on_actual_change_and_cannot_be_active_dropin(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'startup.conf';configure.atomic_write(p,'old')
            configure.atomic_write(p,'old');self.assertEqual(list(Path(directory).glob('*.previous')),[])
            configure.atomic_write(p,'new')
            self.assertEqual(p.read_text(),'new');self.assertEqual(p.with_name(p.name+'.previous').read_text(),'old')
            self.assertEqual(list(Path(directory).glob('*.conf')),[p])
    def test_physical_input_install_retires_web_device_without_starting_robot(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);unit=root/'etc/systemd/system/microduck-webpad.service'
            unit.parent.mkdir(parents=True);unit.write_text('old')
            with patch.object(gamepad,'ROOT',root),patch.object(gamepad,'run') as run,redirect_stdout(io.StringIO()):gamepad.retire_webpad()
            self.assertFalse(unit.exists());self.assertFalse(any('robotd.service' in c.args for c in run.call_args_list))
    def test_automatic_recovery_is_disabled_and_manual_installer_does_not_call_updater(self):
        writes=[];calls=[]
        with patch.object(runtime,'atomic',side_effect=lambda p,s,**_:writes.append((p,s))),patch.object(runtime.subprocess,'run',side_effect=lambda args,**_:calls.append(args)),redirect_stdout(io.StringIO()):runtime.disable_automatic_recovery()
        self.assertEqual(len(writes),3);self.assertEqual(len(calls),3)
        self.assertTrue(all('ConditionPathExists=' in text for p,text in writes))
        service=Path(__file__).with_name('service.sh').read_text()
        self.assertNotIn('systemctl start microduck-webpad',service)
        self.assertNotIn('uart-service.py',service)
        self.assertNotIn('ensure-webpad',service)
    def test_restart_and_core_start_are_not_gated_by_models_or_input_setup(self):
        service=Path(__file__).with_name('service.sh').read_text()
        self.assertIn('prepare-all "$install_dir" || echo',service)
        restart=service[service.index('restart_service()'):service.index('on_error()')]
        self.assertNotIn('verify-models',restart)
        self.assertEqual(restart.count('systemctl restart robotd.service'),1)


if __name__=='__main__':unittest.main()

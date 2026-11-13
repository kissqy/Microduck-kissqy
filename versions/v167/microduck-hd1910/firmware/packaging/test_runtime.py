"""Deployment logic tests: no UART, systemd operations or physical movement."""
import importlib.util
import json
from pathlib import Path
import tempfile
import os
import subprocess
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('runtime', Path(__file__).with_name('runtime.py'))
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patches = [patch.object(runtime, k, v) for k,v in {
            'CONFIG': self.root/'robotd.toml', 'MODEL_DIR': self.root/'models',
            'DROPINS':self.root/'dropins', 'SYSTEMD_DIR':self.root/'systemd', 'PROC':self.root/'proc', 'STATE_DIR':self.root/'state'}.items()]
        for p in self.patches:p.start()
        runtime.MODEL_DIR.mkdir();runtime.DROPINS.mkdir()
        runtime.CONFIG.write_text('[bus]\nport="/dev/ttyS2"\n[policy]\nenabled=true\n')

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()

    def test_only_current_startup_profile_is_written_without_scanning_or_retiring(self):
        legacy=runtime.DROPINS/'zzzzzz-unrelated.conf'
        contents='[Service]\nEnvironment=KEEP=1\n'
        legacy.write_text(contents)
        with patch.object(Path,'glob',side_effect=AssertionError('no old-hook scan')):
            result=runtime.configure_startup('commissioning')
        self.assertEqual(result,{'mode':'commissioning','port':'/dev/ttyS2'})
        self.assertEqual(legacy.read_text(),contents)
        self.assertFalse((runtime.STATE_DIR/'retired-startup').exists())
        text=(runtime.DROPINS/runtime.DROPIN_NAME).read_text()
        self.assertIn('--commissioning',text);self.assertNotIn('uart-service.py',text)
        self.assertNotIn('--uart-setup',text)
        self.assertFalse(hasattr(runtime,'retire_legacy_dropins'))
        self.assertFalse(hasattr(runtime,'verify_startup'))
        self.assertFalse(hasattr(runtime,'verify_ready'))

    def test_recovery_policy_runs_once_and_retries_only_a_failed_setting(self):
        first=[]
        def invoke(args,**kwargs):
            first.append(args)
            return subprocess.CompletedProcess(args,1 if 'robot-boot-check.timer' in args else 0,stdout=b'',stderr=b'blocked')
        with patch.object(runtime.subprocess,'run',side_effect=invoke),patch.object(runtime,'run'):
            with redirect_stdout(StringIO()):runtime.disable_automatic_recovery()
        self.assertEqual(len(first),3)
        with patch.object(runtime.subprocess,'run',return_value=subprocess.CompletedProcess([],0)) as invoke,patch.object(runtime,'run'):
            with redirect_stdout(StringIO()):runtime.disable_automatic_recovery()
        invoke.assert_called_once()
        self.assertIn('robot-boot-check.timer',invoke.call_args.args[0])
        with patch.object(runtime.subprocess,'run') as invoke,patch.object(runtime,'run') as run:
            runtime.disable_automatic_recovery()
        invoke.assert_not_called();run.assert_not_called()

    def test_actual_process_cannot_be_replaced_by_effective_unit(self):
        process=runtime.PROC/'123';process.mkdir(parents=True)
        (process/'exe').symlink_to(runtime.BASE/'robotd')
        argv=[str(runtime.BASE/'robotd'),'--socket','/run/robotd.sock','--params',str(runtime.CONFIG),'--port','/dev/ttyS9','--commissioning']
        (process/'cmdline').write_bytes(('\0'.join(argv)+'\0').encode())
        with patch.object(runtime,'run',return_value='123'):
            with self.assertRaisesRegex(ValueError,'实际服务进程'):runtime.verify_running('commissioning','/dev/ttyS2')
            argv[6]='/dev/ttyS2';argv.append('--uart-setup')
            (process/'cmdline').write_bytes(('\0'.join(argv)+'\0').encode())
            with redirect_stdout(StringIO()):runtime.verify_running('commissioning','/dev/ttyS2')

    def test_power_submits_without_bus_readback(self):
        for action,system_action in [('reboot','reboot'),('shutdown','poweroff')]:
            with patch.object(runtime,'run',return_value='') as run,patch.object(runtime,'rpc',side_effect=AssertionError('no robot IPC')) as rpc,patch.object(runtime,'relax_confirmed',side_effect=AssertionError('no torque gate')):
                answer=runtime.power(action)
            self.assertTrue(answer['scheduled']);self.assertEqual(answer['delay_seconds'],0)
            rpc.assert_not_called()
            self.assertEqual(run.call_args.args,('/usr/bin/systemctl','--no-block',system_action))
            self.assertEqual(run.call_count,1)

    def test_power_does_not_touch_missing_input_services_or_robot_socket(self):
        for action in ('shutdown','reboot'):
            def command(*argv,**kwargs):
                if 'stop' in argv or any(arg.endswith('.service') for arg in argv):raise RuntimeError('Unit not loaded')
            with patch.object(runtime,'run',side_effect=command) as run,patch.object(runtime,'rpc',side_effect=RuntimeError('bus unavailable')) as rpc:
                answer=runtime.power(action)
            self.assertTrue(answer['scheduled']);self.assertEqual(run.call_count,1)
            rpc.assert_not_called()
            self.assertEqual(run.call_args.args[0],'/usr/bin/systemctl')

    def test_only_os_submission_failure_is_reported(self):
        def command(*argv,**kwargs):
            raise RuntimeError('systemd unavailable')
        with patch.object(runtime,'run',side_effect=command) as run,patch.object(runtime,'rpc',side_effect=TimeoutError('no robot IPC')):
            with self.assertRaisesRegex(RuntimeError,'systemd unavailable'):runtime.power('shutdown')
        self.assertEqual(run.call_count,1)
        self.assertFalse(any('robotd.service' in call.args for call in run.call_args_list))



    def test_reconnect_stop_request_accepts_missing_old_socket_and_never_sends_motion(self):
        for problem in (FileNotFoundError('removed old socket'),TimeoutError('old bus timeout'),RuntimeError('old bus unavailable')):
            with self.subTest(problem=problem),patch.object(runtime,'rpc',side_effect=problem) as rpc:
                self.assertFalse(runtime.request_relax()['requested'])
                rpc.assert_called_once_with('robot.relax',timeout=2)


if __name__=='__main__':unittest.main()

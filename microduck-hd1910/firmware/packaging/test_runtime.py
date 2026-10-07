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
            'DROPINS':self.root/'dropins', 'RUNTIME_DROPINS':self.root/'runtime-dropins', 'PROC':self.root/'proc', 'STATE_DIR':self.root/'state'}.items()]
        for p in self.patches:p.start()
        runtime.MODEL_DIR.mkdir();runtime.DROPINS.mkdir()
        runtime.CONFIG.write_text('[bus]\nport="/dev/ttyS2"\n[policy]\nenabled=true\n')

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()

    def test_hat_modes_and_retire_old_overrides(self):
        for mode in ('motion','commissioning'):
            text=runtime.unit(mode)
            self.assertEqual('--commissioning' in text, mode=='commissioning')
            self.assertIn('--uart-setup',text)
            self.assertIn('--port /dev/ttyS2',text)
            self.assertIn('uart-service.py prepare',text)
        legacy=runtime.DROPINS/'zzzzz-old-test.conf'
        legacy.write_text('[Service]\nExecStart=\nExecStart=/opt/robot/feetech-ft5-r5/robotd-old-test --port /dev/ttyS9\nEnvironment=KEEP=1\n')
        old_profile=runtime.DROPINS/'zzzz-old-model-r4.conf'
        old_profile.write_text('[Service]\nExecStart=\nExecStart='+str(runtime.BASE/'robotd')+' --params '+str(runtime.CONFIG)+' --port /dev/ttyS2\n')
        runtime.RUNTIME_DROPINS.mkdir()
        temporary=runtime.RUNTIME_DROPINS/'zzzz-session.conf'
        temporary.write_text('[Service]\nExecStart=/opt/robot/feetech-ft5-r5/robotd --port /dev/ttyS9\n')
        runtime.configure_startup('commissioning')
        self.assertEqual(runtime.config()['bus']['port'],'/dev/ttyS2')
        self.assertNotIn('ExecStart=',legacy.read_text())
        self.assertIn('Environment=KEEP=1',legacy.read_text())
        self.assertFalse(temporary.exists())
        self.assertFalse(old_profile.exists())
        self.assertIn('--uart-setup',(runtime.DROPINS/runtime.DROPIN_NAME).read_text())

    def test_other_installation_hook_only_and_late_override_are_retired(self):
        foreign=runtime.DROPINS/'zzzzzz-custom-policy.conf'
        text='[Service]\nExecStartPre=+/usr/bin/python3 \\\n /opt/microduck-0151/deploy/custom-guard.py\nExecStopPost=/opt/microduck-0151/deploy/recover.sh\nEnvironment=KEEP=1 ORT_DYLIB_PATH=/opt/microduck-0151/libort.so\nMemoryMax=200M\n'
        foreign.write_text(text)
        other=runtime.DROPINS/'unrelated.conf';other.write_text('[Service]\nEnvironment=LANG=zh_CN.UTF-8\n')
        runtime.configure_startup('commissioning')
        self.assertNotIn('Exec',foreign.read_text());self.assertNotIn('ORT_DYLIB_PATH',foreign.read_text())
        self.assertIn('KEEP=1',foreign.read_text());self.assertIn('MemoryMax=200M',foreign.read_text())
        self.assertEqual(other.read_text(),'[Service]\nEnvironment=LANG=zh_CN.UTF-8\n')
        self.assertEqual(next((runtime.STATE_DIR/'retired-startup').glob('*.bak')).read_text(),text)

    def test_merged_hooks_must_match_before_restart(self):
        values={'ExecStart':f'{{ path={runtime.BASE}/robotd ; argv[]={runtime.BASE}/robotd --params {runtime.CONFIG} --port /dev/ttyS2 --uart-setup --commissioning ; }}',
                'ExecStartPre':f'{runtime.BASE}/uart-service.py prepare','ExecStartPost':f'{runtime.BASE}/uart-service.py apply',
                'ExecStopPost':'','ExecStop':'','ExecCondition':''}
        with patch.object(runtime,'run',side_effect=lambda *args:values[args[-2]]):
            self.assertTrue(runtime.verify_startup('commissioning')['startup_verified'])
            values['ExecStartPre']+=' /opt/microduck-0151/deploy/custom_policy_guard.py'
            with self.assertRaisesRegex(ValueError,'其他安装目录'):runtime.verify_startup('commissioning')

    def test_ready_requires_bus_feedback_and_no_automatic_motion(self):
        good={'build':runtime.BUILD,'mode':'motion','phase':'control','fresh_sample':True,'homed':False,'policy_enabled':False,'native':{'torque_state_confirmed':False}}
        waiting={**good,'phase':'configuring_uart','fresh_sample':False}
        with patch.object(runtime,'rpc',side_effect=[waiting,good]) as rpc,patch.object(runtime.time,'sleep'):
            self.assertTrue(runtime.verify_ready('motion')['service_ready'])
            self.assertEqual([call.args for call in rpc.call_args_list],[('robot.busStatus',),('robot.busStatus',)])
        with patch.object(runtime,'rpc',return_value={**good,'build':'old'}):
            with self.assertRaisesRegex(ValueError,'版本或模式'):runtime.verify_ready('motion')

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

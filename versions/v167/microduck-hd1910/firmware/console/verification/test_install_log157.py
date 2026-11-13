"""Install outcomes, actual checksum transfer and completion-driven handoff."""
import io,json,os,secrets,shlex,subprocess,tempfile,threading,time,unittest
from pathlib import Path,PureWindowsPath
from unittest.mock import Mock,patch
from install_handoff import InstallHandoff
from service_control import ServiceController,ServiceTransport,ControlError
from staging_upload import StagingUpload
from telemetry import Store
from system_log import SystemLog
from raw_telemetry import raw_loop,Hub
import test_upgrade_units as unit_fakes
import gamepad
from contextlib import redirect_stdout


class UploadTests(unittest.TestCase):
    def transfer(self,corrupt=False):
        path=Path('/tmp/microduck-upgrade-'+secrets.token_hex(6));path.mkdir()
        events=[];data=b'firmware-data'*18000
        def spawn(command,**options):
            args=shlex.split(command[-1])
            if corrupt:args[2]=args[2].replace("h.hexdigest()","'0'*64")
            return subprocess.Popen(args,**options)
        try:
            with patch('staging_upload.ssh_command',return_value=['ssh','duck']),patch('staging_upload.ssh_process_options',return_value={}),patch('staging_upload.spawn_process',side_effect=spawn):
                uploader=StagingUpload('duck')
                if corrupt:
                    with self.assertRaisesRegex(ValueError,'校验不一致'):
                        uploader.upload(str(path/'package.tar.gz'),io.BytesIO(data),len(data),events.append,False)
                else:
                    result=uploader.upload(str(path/'package.tar.gz'),io.BytesIO(data),len(data),events.append,False)
                    self.assertEqual(result['bytes'],len(data));self.assertEqual((path/'package.tar.gz').read_bytes(),data)
            return events
        finally:
            (path/'package.tar.gz').unlink(missing_ok=True);path.rmdir()
    def test_real_receiver_writes_and_fsyncs_then_compares_hash_with_progress(self):
        events=self.transfer()
        values=[e['percent'] for e in events if e['step']=='上传固件']
        self.assertEqual(values,sorted(values));self.assertEqual(values[0],0);self.assertEqual(values[-1],100)
        self.assertEqual(events[-1]['step'],'校验上传');self.assertEqual(events[-1]['status'],'成功')
        self.assertTrue(any(e['step']=='上传固件' and e['status']=='成功' for e in events))
    def test_wrong_remote_hash_reports_verification_failure_never_success(self):
        events=self.transfer(True)
        self.assertEqual(events[-1]['step'],'校验上传');self.assertEqual(events[-1]['status'],'失败')
        self.assertFalse(any(e['status']=='成功' for e in events))
    def test_ssh_spawn_failure_reports_upload_step_failure(self):
        events=[]
        with patch('staging_upload.spawn_process',side_effect=OSError('SSH executable unavailable')):
            with self.assertRaisesRegex(OSError,'SSH executable unavailable'):
                StagingUpload('duck').upload('/tmp/microduck-upgrade-abcdefghijkl/package.tar.gz',io.BytesIO(b'x'),1,events.append,False)
        self.assertEqual(events[-1]['step'],'上传固件');self.assertEqual(events[-1]['status'],'失败')


class Channel:
    def __init__(self,fail='',receipt=True,directory='/tmp/microduck-upgrade-abcdefghijkl'):
        self.calls=[];self.fail=fail;self.receipt=receipt;self.directory=directory
    def request(self,request,timeout,progress=None):
        args=request['argv'];self.calls.append(args)
        if 'mktemp' in args:return {'returncode':0,'stdout':self.directory+'\n','stderr':''}
        if 'tar' in args and self.fail=='tar':
            if progress:progress('tar: damaged archive\n')
            return {'returncode':2,'stdout':'','stderr':'tar: damaged archive'}
        if 'upgrade' in args:
            text='[固件安装 / 检查可执行文件] 开始 · 校验 AArch64 架构\n[固件安装 / 检查可执行文件] 成功 · 完整性通过\n'
            if self.receipt:text+=json.dumps({'upgrade_installed':True,'mode':'motion'})+'\n'
            if progress:
                for line in text.splitlines(True):progress(line)
            return {'returncode':0,'stdout':text,'stderr':''}
        return {'returncode':0,'stdout':'','stderr':''}


class InstallTransportTests(unittest.TestCase):
    def run_install(self,channel,windows=False):
        events=[]
        with tempfile.TemporaryDirectory() as directory:
            archive=Path(directory)/'package.tar.gz';archive.write_bytes(b'fixed-bundle')
            log=SystemLog(directory);transport=ServiceTransport('radxa@duck','/run/robotd.sock',log);transport.channel=channel
            def upload(_self,path,stream,size,progress,record_output):
                self.assertFalse(record_output);progress({'step':'校验上传','status':'成功','detail':'SHA256 一致','percent':100,'bytes':size,'total':size})
            def platform_path(value):
                return PureWindowsPath(value) if windows and str(value)==channel.directory else Path(value)
            try:
                with patch('service_control.bundle_info',return_value={}),patch.object(StagingUpload,'upload',upload),patch('service_control.Path',side_effect=platform_path):
                    try:result=transport.upgrade(archive=archive,progress=events.append)
                    except ControlError as exc:result=exc
                log.flush();return result,events,log.path.read_text()
            finally:log.close()
    def test_success_logs_owned_steps_without_commands_paths_or_receipt_json(self):
        channel=Channel();result,events,log=self.run_install(channel)
        self.assertTrue(result['upgrade_installed']);self.assertIn('解压固件] 成功',log);self.assertIn('清理暂存目录] 成功',log)
        self.assertNotIn('SSH 命令',log);self.assertNotIn('upgrade_installed',log);self.assertNotIn(channel.directory,log)
        self.assertEqual(len(channel.calls),4)
        self.assertNotIn('开始',log)
    def test_windows_pc_still_sends_posix_installer_path_to_linux(self):
        channel=Channel();result,events,log=self.run_install(channel,windows=True)
        self.assertTrue(result['upgrade_installed'])
        call=next(args for args in channel.calls if 'upgrade' in args)
        script=call[call.index('/bin/bash')+1]
        self.assertEqual(script,channel.directory+'/Microduck-Robotd-FT6-R17/service.sh')
        self.assertNotIn('\\',script);self.assertNotIn('开始',log)
    def test_extraction_error_preserves_reason_and_never_runs_installer(self):
        channel=Channel(fail='tar');result,events,log=self.run_install(channel)
        self.assertIsInstance(result,ControlError);self.assertIn('damaged archive',log);self.assertIn('解压固件] 失败',log)
        self.assertFalse(any('upgrade' in a for a in channel.calls));self.assertIn('清理暂存目录] 成功',log)
    def test_exit_zero_without_success_receipt_is_not_install_success(self):
        result,_,log=self.run_install(Channel(receipt=False))
        self.assertIsInstance(result,ControlError);self.assertIn('未返回成功回执',str(result))
    def test_invalid_directory_does_not_claim_success_upload_or_cleanup(self):
        channel=Channel(directory='/etc');result,_,log=self.run_install(channel)
        self.assertIsInstance(result,ControlError);self.assertIn('创建暂存目录] 失败',log)
        self.assertNotIn('创建暂存目录] 成功',log);self.assertEqual(len(channel.calls),1)


class HandoffTests(unittest.TestCase):
    def test_production_collector_does_not_open_during_install_or_retry_failed_completion(self):
        gate=InstallHandoff();gate.begin();stop=threading.Event();attempted=threading.Event()
        failed_attempt=gate.failed_attempt
        def failed():
            result=failed_attempt();attempted.set();return result
        gate.failed_attempt=failed
        class NoWorker:
            def __init__(self,*args,**kwargs):pass
            def start(self):pass
            def join(self,**kwargs):pass
        thread_type=threading.Thread
        opener=Mock(side_effect=OSError('robotd socket unavailable'))
        with patch('socket_transport.open_remote_socket',opener),patch('raw_telemetry.threading.Thread',NoWorker):
            thread=thread_type(target=raw_loop,args=('duck',{'hub':Hub(),'robotd_socket':'robot','tofd_socket':'tof','install_handoff':gate},lambda _:None,stop))
            thread.start()
            try:
                self.assertFalse(attempted.wait(.03));opener.assert_not_called()
                gate.complete(after_install=True);self.assertTrue(attempted.wait(1))
                self.assertTrue(gate.paused);self.assertEqual(opener.call_count,1)
                self.assertTrue(thread.is_alive())
            finally:stop.set();gate.wake();thread.join(1)
            self.assertFalse(thread.is_alive());self.assertEqual(opener.call_count,1)
    def test_completion_wakes_existing_waiter_and_closes_only_owned_streams(self):
        gate=InstallHandoff();peer=Mock();gate.attach(peer);gate.begin();peer.close.assert_called_once()
        stop=threading.Event();started=threading.Event();done=threading.Event()
        def reader():started.set();gate.wait(stop);done.set()
        t=threading.Thread(target=reader);t.start();self.assertTrue(started.wait(1));self.assertFalse(done.wait(.03))
        gate.complete(after_install=True);self.assertTrue(done.wait(1));t.join(1)
        self.assertTrue(gate.failed_attempt());self.assertTrue(gate.paused)
        gate.complete();self.assertFalse(gate.paused)
    def test_failed_install_keeps_data_disconnected_until_manual_reconnect(self):
        store=Store('service');gate=store.install_handoff
        def upgrade(*args,**kwargs):self.assertTrue(gate.paused);raise ControlError('ELF truncated',503)
        service=ServiceController(store,transport=Mock(upgrade=upgrade),warm=False)
        job={'action':'upgrade-service','status':'running'}
        service._execute({'action':'upgrade-service','firmware':'bundled'},job,0)
        self.assertEqual(job['status'],'error');self.assertTrue(gate.paused);self.assertIn('ELF truncated',job['error'])
    def test_success_releases_data_only_after_installer_returns_and_preserves_transfer_progress(self):
        store=Store('service');gate=store.install_handoff
        def upgrade(*args,**kwargs):
            self.assertTrue(gate.paused)
            kwargs['progress']({'step':'上传固件','status':'进行中','detail':'writing','percent':40,'bytes':4,'total':10})
            kwargs['progress']({'step':'完成安装','status':'成功','detail':'installed'})
            return {'upgrade_installed':True}
        service=ServiceController(store,transport=Mock(upgrade=upgrade),warm=False)
        job={'action':'upgrade-service','status':'running'}
        service._execute({'action':'upgrade-service','firmware':'bundled'},job,0)
        self.assertEqual(job['status'],'completed');self.assertFalse(gate.paused);self.assertTrue(gate.recovery_pending)
        self.assertEqual(job['transfer_progress']['percent'],40);self.assertEqual(job['phase'],'完成安装')
    def test_cancel_wakes_blocked_collector_without_a_timed_poll(self):
        gate=InstallHandoff();gate.begin();stop=threading.Event();result=[]
        t=threading.Thread(target=lambda:result.append(gate.wait(stop)));t.start()
        stop.set();gate.wake();t.join(1);self.assertEqual(result,[False])


BODY=r'''bundle_dir="$TEST_ROOT"
install_dir="$TEST_ROOT"
config_dir="$TEST_ROOT/config"
params_path="$config_dir/robotd.toml"
calibration_path="$config_dir/calibration.toml"
service_user=$(id -un); service_group=$(id -gn)
touch "$install_dir/robotd" "$install_dir/service.sh"
cp "$SERVICE_SRC/configure.py" "$bundle_dir/configure.py"
cp "$SERVICE_SRC/management_profile.py" "$bundle_dir/management_profile.py"
cp "$SERVICE_SRC/robotd-profile.toml" "$bundle_dir/robotd-profile.toml"
cp "$SERVICE_SRC/management-profile.json" "$bundle_dir/management-profile.json"
identity() { :; }
request_relax_service() { install_log 提示 '旧服务不可达'; }
python3() {
 case "${1##*/}" in
 elf_integrity.py) [[ ${FAIL_ELF:-0} == 0 ]] || { echo 'robotd: truncated ELF segment' >&2; return 23; } ;;
 rebuild-config.py) printf '[policy]\n' > "$3/robotd.toml"; printf 'motion_enabled = false\n' > "$3/hd1910-calibration.toml" ;;
 configure.py) "$REAL_PYTHON" "$@" ;;
 calibration-config.py) cp "$3" "$5" ;;
 runtime.py) [[ $2 == configure-startup || $2 == disable-automatic-recovery ]] || { echo 'UNEXPECTED-STATUS-POLL' >&2; return 88; } ;;
 voice-setup.py) : ;;
 startup_gate.py) [[ ${FAIL_READY:-0} == 0 ]] || { echo "robotd 第 2/4 步失败：IMU not ready" >&2; return 78; } ;;
 gamepad.py) [[ $2 == prepare-all ]] || return 89 ;;
 *) "$REAL_PYTHON" "$@" ;;
 esac
}
install_bundle upgrade
'''


class InstallerShellTests(unittest.TestCase):
    def run_shell(self,units,body=BODY):return unit_fakes.UpgradeUnitTests().run_script(units,body)
    def test_complete_install_has_start_result_steps_and_no_bus_status_poll(self):
        p,calls,_=self.run_shell({})
        self.assertEqual(p.returncode,0,p.stderr);self.assertIn('完成安装] 成功',p.stdout)
        self.assertIn('停止旧机器人服务] 成功',p.stdout);self.assertIn('安装主服务启动配置] 成功',p.stdout)
        self.assertEqual(calls.count(['restart','robotd.service']),1)
        self.assertFalse(any(c[0]=='show' for c in calls));self.assertNotIn('UNEXPECTED-STATUS-POLL',p.stderr)
        objects=[json.loads(s) for s in p.stdout.splitlines() if s.startswith('{')]
        self.assertEqual(len(objects),2);self.assertTrue(objects[-1]['upgrade_installed']);self.assertTrue(objects[0]['robotd_ready'])
        self.assertNotIn('沿用现有原生音库',p.stdout);self.assertNotIn('单独起身老师',p.stdout)
    def test_failed_robot_stop_aborts_instead_of_claiming_success_or_starting(self):
        p,calls,_=self.run_shell({'robotd.service':{'load':'loaded','active':'active','stop_rc':13}})
        self.assertEqual(p.returncode,13);self.assertIn('Stop failed for robotd',p.stderr)
        self.assertIn('停止旧机器人服务] 失败',p.stderr);self.assertNotIn('停止旧机器人服务] 成功',p.stdout)
        self.assertFalse(any(c[0] in ('start','restart') for c in calls));self.assertNotIn('upgrade_installed',p.stdout)
    def test_input_failure_keeps_main_install_independent_and_returns_honest_receipt(self):
        p,calls,_=self.run_shell({'padd.service':{'load':'loaded','active':'active','stop_rc':13}})
        self.assertEqual(p.returncode,0,p.stderr);self.assertIn('停止旧实体手柄服务] 失败',p.stdout)
        self.assertIn('Stop failed for padd',p.stderr);self.assertIn(['restart','robotd.service'],calls)
        self.assertTrue(json.loads(p.stdout.splitlines()[-1])['input_setup_complete'])
    def test_bad_elf_fails_named_step_before_stopping_services(self):
        p,calls,_=self.run_shell({},'FAIL_ELF=1\n'+BODY)
        self.assertEqual(p.returncode,23);self.assertIn('检查可执行文件] 失败',p.stderr)
        self.assertIn('truncated ELF segment',p.stderr);self.assertFalse(any(c[0]=='stop' for c in calls))


class InputInstallTests(unittest.TestCase):
    def test_no_legacy_webpad_files_means_no_command_and_no_spurious_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=io.StringIO()
            with patch.object(gamepad,'ROOT',Path(tmp)),patch.object(gamepad,'run') as run,redirect_stdout(out):gamepad.retire_webpad()
            run.assert_not_called();self.assertEqual(out.getvalue(),'')
    def test_existing_legacy_unit_is_stopped_and_removed_without_claiming_ssh_connected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);unit=root/'etc/systemd/system/microduck-webpad.service';unit.parent.mkdir(parents=True);unit.write_text('old unit')
            out=io.StringIO()
            with patch.object(gamepad,'ROOT',root),patch.object(gamepad,'run') as run,redirect_stdout(out):gamepad.retire_webpad()
            run.assert_called_once_with('systemctl','--no-reload','disable','--now','microduck-webpad.service')
            self.assertFalse(unit.exists());self.assertIn('清理旧网页虚拟手柄] 成功',out.getvalue());self.assertNotIn('SSH',out.getvalue())


if __name__=='__main__':unittest.main()

"""Startup push events control data/input ordering; no hardware or systemd writes."""
import copy,errno,io,json,os,socket,sys,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from contextlib import redirect_stdout,redirect_stderr
import startup_gate as gate
from install_handoff import InstallHandoff
from raw_telemetry import Hub,raw_loop
from telemetry import Store
from service_control import ServiceController,ServiceTransport,ControlError
from system_log import SystemLog
import gamepad,runtime
import test_install_log157 as install_tests
from test_install_log157 import BODY,Channel

READY={'steps':{str(n):{'status':'success','detail':'ready '+str(n)} for n in range(1,5)}}
WAIT={'steps':{'1':READY['steps']['1'],'2':{'status':'waiting','detail':'waiting for first valid IMU'}}}
def wire(report,first=True):
 return (json.dumps({'id':1,'result':report} if first else {'method':'robot.startup','params':report})+'\n').encode()

class GateTests(unittest.TestCase):
 def test_one_subscription_waits_for_all_four_push_events_without_a_probe(self):
  client,server=socket.socketpair();published=threading.Event();answer=[]
  def emit(report):published.set()
  worker=threading.Thread(target=lambda:answer.append(gate.receive(client,emit,timeout=2)))
  with client,server:
   worker.start();request=server.recv(1000)
   self.assertEqual(json.loads(request)['method'],'robot.startupSubscribe')
   server.sendall(wire(WAIT));self.assertTrue(published.wait(1));self.assertTrue(worker.is_alive())
   server.settimeout(.03)
   with self.assertRaises(socket.timeout):server.recv(1000)
   server.sendall(wire(READY,False));worker.join(1);self.assertFalse(worker.is_alive())
  self.assertEqual(answer,[READY])
 def test_fourth_step_alone_does_not_release_commissioning_with_bad_feedback(self):
  self.assertFalse(gate.ready({'steps':{'4':READY['steps']['4']}}))
  report=copy.deepcopy(READY);report['steps']['2']=WAIT['steps']['2'];self.assertFalse(gate.ready(report))
 def test_explicit_failure_returns_original_reason_and_does_not_restart(self):
  bad=copy.deepcopy(READY);bad['steps']['3']={'status':'failed','detail':'ONNX tensor shape mismatch'}
  client,server=socket.socketpair()
  with client,server:
   server.sendall(wire(bad));seen=[]
   with self.assertRaisesRegex(gate.StartupFailure,'第 3/4.*tensor shape mismatch'):gate.receive(client,seen.append,timeout=1)
  self.assertEqual(seen,[bad])
 def test_timeout_preserves_pending_imu_reason(self):
  client,server=socket.socketpair()
  with client,server:
   server.sendall(wire(WAIT))
   with self.assertRaisesRegex(TimeoutError,'valid IMU.*未停止或重启'):gate.receive(client,timeout=.03)
 def test_eof_is_failure_not_readiness(self):
  peer=Mock();peer.recv.return_value=b''
  with self.assertRaises(EOFError):gate.receive(peer)
  peer.sendall.assert_called_once()
 def test_inotify_waits_for_socket_creation_with_only_event_driven_connect_attempts(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'robotd.sock';waiting=threading.Event();first=Mock();second=Mock();answer=[]
   def absent(_):waiting.set();raise FileNotFoundError(errno.ENOENT,'not yet created')
   first.connect.side_effect=absent
   with patch.object(gate.socket,'socket',side_effect=[first,second]):
    thread=threading.Thread(target=lambda:answer.append(gate.connect_local(path,1)));thread.start()
    self.assertTrue(waiting.wait(1));path.touch();thread.join(1)
   self.assertFalse(thread.is_alive());self.assertEqual(answer,[second]);first.close.assert_called_once();second.connect.assert_called_once_with(str(path))
 def test_socket_bind_and_permission_setup_race_waits_for_attribute_event(self):
  for code in (errno.EACCES,errno.ECONNREFUSED):
   with self.subTest(errno=code),tempfile.TemporaryDirectory() as tmp:
    path=Path(tmp)/'robotd.sock';created=threading.Event();attributes=threading.Event();first=Mock();second=Mock();third=Mock();answer=[]
    def missing(_):created.set();raise FileNotFoundError(errno.ENOENT,'not bound')
    def incomplete(_):attributes.set();raise OSError(code,'bind/permission setup pending')
    first.connect.side_effect=missing;second.connect.side_effect=incomplete
    with patch.object(gate.socket,'socket',side_effect=[first,second,third]):
     thread=threading.Thread(target=lambda:answer.append(gate.connect_local(path,1)));thread.start()
     self.assertTrue(created.wait(1));path.touch()
     self.assertTrue(attributes.wait(1));path.chmod(0o660);thread.join(1)
    self.assertFalse(thread.is_alive());self.assertEqual(answer,[third]);third.connect.assert_called_once()
 def test_boot_waiter_execs_original_binary_once_and_is_replaced(self):
  with patch.object(sys,'argv',['startup_gate.py','--exec','/opt/padd','--socket','/run/robotd.sock']),patch.object(gate,'wait_local',return_value=READY) as wait,patch.object(os,'execv') as execute,redirect_stdout(io.StringIO()):
   self.assertEqual(gate.main(),0)
  wait.assert_called_once();execute.assert_called_once_with('/opt/padd',['/opt/padd','--socket','/run/robotd.sock'])
 def test_boot_failure_prevents_restart_loop_and_never_execs_input(self):
  with patch.object(sys,'argv',['startup_gate.py','--exec','/opt/padd']),patch.object(gate,'wait_local',side_effect=gate.StartupFailure('IMU failure')),patch.object(os,'execv') as execute,redirect_stderr(io.StringIO()) as error:
   self.assertEqual(gate.main(),78)
  execute.assert_not_called();self.assertIn('IMU failure',error.getvalue())

class WorkflowTests(unittest.TestCase):
 def test_install_readiness_releases_data_before_optional_setup_without_losing_startup(self):
  store=Store('service');store.raw_hub=Hub();seen=[]
  def install(*_,progress,**kwargs):
   self.assertTrue(store.install_handoff.paused)
   progress({'startup':WAIT});self.assertTrue(store.install_handoff.paused)
   progress({'robotd_ready':True,'startup':READY})
   self.assertFalse(store.install_handoff.paused);self.assertEqual(store.install_handoff.ready_report,READY)
   seen.append(store.peek()['startup']);progress({'step':'手柄配置','status':'失败','detail':'udev unavailable'})
   return {'upgrade_installed':True,'input_setup_complete':False}
  service=ServiceController(store,transport=Mock(upgrade=install),warm=False);job={'action':'upgrade-service','status':'running'}
  service._execute({'action':'upgrade-service','firmware':'bundled'},job,0)
  self.assertEqual(job['status'],'completed');self.assertEqual(seen,[READY]);self.assertFalse(store.install_handoff.paused)
 def test_data_reset_keeps_same_startup_and_does_not_log_four_steps_twice(self):
  store=Store('service');store.system_log=Mock()
  store.ingest({'channel':'startup','data':WAIT});store.ingest({'channel':'startup','data':READY})
  count=store.system_log.add.call_count;self.assertEqual(count,4)
  epoch=store.robotd_epoch
  store.ingest({'channel':'robotd_stream','data':{'preserve_startup':True}});store.ingest({'channel':'startup','data':READY})
  self.assertEqual(store.system_log.add.call_count,count);self.assertEqual(store.robotd_epoch,epoch)
  self.assertEqual(store.peek()['startup'],READY)
 def test_installer_event_frames_are_consumed_without_logging_raw_json(self):
  class EventsChannel(Channel):
   def request(self,request,timeout,progress=None):
    if 'upgrade' in request['argv'] and progress:
     progress(json.dumps({'robotd_startup':READY})+'\n');progress('{"robotd_ready":true}\n')
    return super().request(request,timeout,progress)
  result,events,log=install_tests.InstallTransportTests().run_install(EventsChannel())
  self.assertTrue(result['upgrade_installed']);self.assertTrue(any(e.get('robotd_ready') for e in events))
  self.assertNotIn('robotd_startup',log);self.assertNotIn('"steps"',log)
 def test_failed_core_start_never_starts_inputs_and_does_not_stop_the_new_robot(self):
  result,calls,state=install_tests.InstallerShellTests().run_shell({},'FAIL_READY=1\n'+BODY)
  self.assertEqual(result.returncode,78);self.assertIn('IMU not ready',result.stderr)
  self.assertEqual(calls.count(['restart','robotd.service']),1);self.assertEqual(calls.count(['stop','robotd.service']),1)
  self.assertFalse(any(c[0] in ('start','restart') and 'padd.service' in c for c in calls))
  self.assertEqual(state['robotd.service']['active'],'active');self.assertNotIn('upgrade_installed',result.stdout)
 def test_config_failure_after_core_is_reported_but_robot_stays_running(self):
  body=BODY.replace('gamepad.py) [[ $2 == prepare-all ]] || return 89 ;;','gamepad.py) echo input-config-failure >&2; return 22 ;;')
  result,calls,state=install_tests.InstallerShellTests().run_shell({},body)
  self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(state['robotd.service']['active'],'active')
  self.assertFalse(json.loads(result.stdout.splitlines()[-1])['input_setup_complete'])
  self.assertIn('安装实体手柄配置] 失败',result.stdout)
 def test_process_query_is_shared_between_simultaneous_callers_and_reset_on_new_instance(self):
  store=Store('service');started=threading.Event();release=threading.Event();transport=Mock()
  def query(*a,**kw):started.set();release.wait(1);return {'process_matches':True,'actual_mode':'motion','actual_port':'/dev/ttyS2'}
  transport.manage.side_effect=query;service=ServiceController(store,transport=transport,warm=False);answers=[]
  threads=[threading.Thread(target=lambda:answers.append(service.connection())) for _ in range(2)]
  for thread in threads:thread.start()
  self.assertTrue(started.wait(1));release.set()
  for thread in threads:thread.join(1)
  self.assertEqual(transport.manage.call_count,1);self.assertEqual(len(answers),2)
  store.ingest({'channel':'robotd_stream','data':{'status':'waiting'}});service.connection()
  self.assertEqual(transport.manage.call_count,2)
 def test_installed_boot_units_wait_without_pulling_in_or_restarting_robotd(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);base=Path(gamepad.__file__).parent
   with patch.object(gamepad,'ROOT',root),patch.object(gamepad,'BASE',base),patch.object(gamepad,'load',return_value={'mouth_percent':100,'head_rad':1.0}),patch.object(gamepad,'save'),patch.object(gamepad,'SETTINGS_PATH',root/'settings.json'),patch.object(gamepad,'run'),redirect_stdout(io.StringIO()):
    gamepad.install(base,deferred=True);gamepad.upgrade_client(deferred=True)
   paths=[root/'etc/systemd/system/gamesir-xboxd.service.d/zzzz-r17-ready.conf',root/gamepad.PAD_DROPIN]
   for path in paths:
    text=path.read_text();self.assertIn('startup_gate.py --timeout 60 --exec',text)
    self.assertIn('RestartPreventExitStatus=78',text);self.assertNotIn('Wants=robotd',text);self.assertNotIn('Requires=robotd',text)
 def test_packaging_and_console_use_identical_event_validation(self):
  root=Path(__file__).resolve().parents[2]
  self.assertEqual((root/'console/startup_gate.py').read_bytes(),(root/'packaging/startup_gate.py').read_bytes())

if __name__=='__main__':unittest.main()

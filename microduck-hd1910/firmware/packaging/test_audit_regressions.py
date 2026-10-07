"""Behavioral regressions for the v121 audit; no hardware or robot commands."""
import gc, importlib.util, io, json, os, socket, subprocess, sys, tempfile, threading, time, tomllib, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from session_sequences import SequenceWindow
from controls import Controller, ControlError
from service_control import ServiceController
from service_channel import ServiceChannel
from configure import dumps
from remote_audio import NativeAudio
import webpad, pad_settings
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('audit_install',ROOT/'packaging/install-files.py')
install=importlib.util.module_from_spec(spec);spec.loader.exec_module(install)
class Store:
 service_operation=False
 def snapshot(self):return {'bus':{'build':'1fa8438-feetech-ft6-control.14','mode':'motion','phase':'control'}}
 def record_service_command(self,job):pass
class AuditRegressions(unittest.TestCase):
 def test_failed_connect_retries_and_many_management_pages_do_not_exhaust_sources(self):
  class Input:
   connected=False;audio_status={}
   def call(self,command):return {'accepted':False,'reason':'socket missing','available':False}
  control=Controller(Store(),transport=Input())
  for n in range(1000):
   with self.assertRaisesRegex(ControlError,'socket missing'):control.handle({'action':'connect','client':f'failed-tab-{n}','seq':1})
  self.assertEqual(len(control.sequences),0)
  service=ServiceController(Store(),transport=SimpleNamespace(forget_sudo_password=lambda:None))
  for n in range(1000):service.handle({'client':f'manage-tab-{n}','seq':1,'command':{'action':'forget-sudo-password'}})
  self.assertLessEqual(len(service.sequences),32)
  with self.assertRaisesRegex(ControlError,'重复'):service.handle({'client':'manage-tab-0','seq':1,'command':{'action':'forget-sudo-password'}})
 def test_replay_window_protects_inflight_entries_and_retains_recent_duplicates(self):
  now=[0.];window=SequenceWindow(limit=2,clock=lambda:now[0]);window.accept('slow',5);window.accept('old',1)
  with window.protect('slow'):
   for n in range(100):window.accept(str(n),1)
   self.assertEqual(window['slow'],5)
   with self.assertRaisesRegex(ValueError,'重复'):window.accept('old',1)
  now[0]=301;window.accept('new',1);self.assertNotIn('slow',window)
 def test_completed_install_survives_delayed_or_failed_input_and_is_not_replayed(self):
  class Firmware:
   def __init__(self):self.count=0
   def upgrade(self,*_,**kwargs):self.count+=1;return {'upgrade_installed':True}
  class Input:
   def __init__(self,succeeds):self.succeeds=succeeds;self.first=0;self.probes=0
   def resume_connections(self):pass
   def reconnect_after_service(self):self.first+=1;raise RuntimeError('socket missing')
   def refresh_after_service(self):
    self.probes+=1
    if self.succeeds:return {'webpad_reconnected':True}
    raise RuntimeError('socket still missing')
  for succeeds in (True,False):
   firmware=Firmware();control=Input(succeeds);store=Store();service=ServiceController(store,transport=firmware,controls=control)
   job={'action':'upgrade-service','status':'running'};service.job=job
   service._execute({'action':'upgrade-service','firmware':'bundled'},job,0)
   self.assertEqual(job['status'],'completed');self.assertFalse(store.service_operation)
   deadline=time.monotonic()+6
   while job['result']['input']['status']=='recovering' and time.monotonic()<deadline:time.sleep(.01)
   self.assertEqual(job['result']['input']['status'],'ready' if succeeds else 'error')
   self.assertEqual(firmware.count,1);self.assertEqual(control.first,1)
 def test_broken_service_reader_is_retired_and_next_request_starts_fresh_without_replay(self):
  # A malformed stdout line previously left a living process with no reader.
  original=subprocess.Popen;procs=[]
  bad="import sys,time;sys.stdin.buffer.readline();print('broken-json',flush=True);time.sleep(60)"
  def spawn(argv,**kw):
   if not procs:argv=[sys.executable,'-u','-c',bad]
   proc=original(argv,**kw);procs.append(proc);return proc
  channel=ServiceChannel(None,'unused')
  try:
   with patch('service_channel.subprocess.Popen',spawn):
    with self.assertRaisesRegex(RuntimeError,'未重发'):channel.request({'kind':'manage','argv':['/bin/true']},2)
    result=channel.request({'kind':'manage','argv':['/bin/echo','fresh']},2)
    self.assertEqual(result['stdout'],'fresh\n');self.assertEqual(len(procs),2)
  finally:channel.close()
  deadline=time.monotonic()+3
  while any(p.poll() is None or not p.stdout.closed or not p.stderr.closed for p in procs) and time.monotonic()<deadline:time.sleep(.01)
  self.assertTrue(all(p.poll() is not None and p.stdout.closed and p.stderr.closed for p in procs))
 def test_many_service_disconnects_do_not_accumulate_processes_or_open_descriptors(self):
  before=len(os.listdir('/proc/self/fd'));channel=ServiceChannel(None,'unused');procs=[]
  try:
   for _ in range(30):
    channel.request({'kind':'manage','argv':['/bin/true']},2);procs.append(channel.proc);channel.disconnect()
  finally:channel.close()
  gc.collect();time.sleep(.1)
  self.assertLessEqual(len(os.listdir('/proc/self/fd')),before+2)
  self.assertTrue(all(p.poll() is not None and p.stdin.closed and p.stdout.closed and p.stderr.closed for p in procs))
 def test_native_audio_constructor_is_nonblocking_and_volume_waits_for_initialization(self):
  with tempfile.TemporaryDirectory() as tmp:
   base=Path(tmp);setup=base/'voice.json';setup.write_text('{"card":"aic3104"}');calls=[]
   def mixer(argv,**_):calls.append(argv);return SimpleNamespace(returncode=0,stdout=': values=500',stderr='')
   audio=NativeAudio(None,setup=setup,config=base/'none',runner=mixer,initialize=False)
   self.assertEqual(calls,[]);self.assertIsNone(audio.status()['volume']);self.assertTrue(audio.status()['initializing'])
   audio.initialize();self.assertEqual(len(calls),2);self.assertFalse(audio.status()['initializing'])
 def test_upgrade_preserves_model_bindings_filters_pad_and_scale_but_reset_is_explicit(self):
  with tempfile.TemporaryDirectory() as tmp:
   base=Path(tmp);source=base/'old';target=base/'new'
   custom={'bus':{'port':'wrong'},'control':{'hz':1},'policy':{'custom_only':True,'walk':'/custom/new/policy.onnx','stand':'/custom/stand/policy.onnx','sitstand':'none','action_scale':.63,'head_lowpass':.44,'legs_lowpass':.66,'r17_inference_scale':.4},'pad':{'dpad_down':'sit_toggle','custom_param':5}}
   source.write_text(dumps(custom));args=[sys.executable,str(ROOT/'packaging/configure.py'),'--source',str(source),'--previous-overrides',str(ROOT/'packaging/robotd-profile.toml'),'--overrides',str(ROOT/'packaging/robotd-profile.toml'),'--output',str(target)]
   subprocess.run(args,check=True,capture_output=True);data=tomllib.loads(target.read_text())
   for k in ('walk','stand','sitstand','action_scale','head_lowpass','legs_lowpass'):self.assertEqual(data['policy'][k],custom['policy'][k])
   self.assertNotIn('r17_inference_scale',data['policy']);self.assertEqual(data['pad']['custom_param'],5);self.assertEqual(data['bus']['port'],'/dev/ttyS2');self.assertEqual(data['control']['hz'],50)
   subprocess.run(args+['--replace-models'],check=True,capture_output=True);data=tomllib.loads(target.read_text())
   self.assertNotEqual(data['policy']['walk'],custom['policy']['walk']);self.assertEqual(data['policy']['stand'],'none');self.assertNotIn('head_lowpass',data['policy']);self.assertNotIn('legs_lowpass',data['policy'])
 def test_preserved_export_metadata_is_not_overwritten_and_explicit_reset_replaces_it(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);bundle=root/'bundle';live=root/'live';names=['models/shared/deployment-contract.json','models/shared/policy.onnx']
   for base in (bundle,live):
    (base/'models/shared').mkdir(parents=True)
    (base/'models/shared/deployment-contract.json').write_text('{"source":"bundle"}' if base==bundle else '{"source":"user"}')
    (base/'models/shared/policy.onnx').write_text('new' if base==bundle else 'existing')
   (bundle/'install-files.json').write_text(json.dumps(names));(bundle/'SHA256SUMS').write_text('')
   (live/'models/imported').mkdir();(live/'models/imported/policy.onnx').write_text('extra')
   install.install(bundle,live)
   self.assertEqual((live/'models/shared/deployment-contract.json').read_text(),'{"source":"user"}');self.assertTrue((live/'models/imported').exists())
   install.install(bundle,live,replace_models=True)
   self.assertEqual((live/'models/shared/deployment-contract.json').read_text(),'{"source":"bundle"}');self.assertFalse((live/'models/imported').exists())
 def test_payload_swap_failure_never_cleans_old_files_or_user_models(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);bundle=root/'bundle';live=root/'live';bundle.mkdir();live.mkdir()
   (bundle/'replacement').write_text('new');(bundle/'install-files.json').write_text('["replacement"]');(bundle/'SHA256SUMS').write_text('')
   (live/'retired').write_text('old');(live/'install-files.json').write_text('["retired"]')
   with patch.object(install.os,'replace',side_effect=OSError('swap failed')):
    with self.assertRaises(OSError):install.install(bundle,live)
   self.assertEqual((live/'retired').read_text(),'old')
 def test_device_hotplug_interrupts_scan_cache_and_real_pad_revokes_web_owner(self):
  now=[0.];physical=[];scans=[]
  class Monitor:
   socket=object();dirty=False
   def changed(self):v=self.dirty;self.dirty=False;return v
  monitor=Monitor();cache=webpad.DeviceCache(scanner=lambda:scans.append(1) or list(physical),monitor=monitor,clock=lambda:now[0])
  class Pad:
   closed=False
   def send(self,*_):pass
   def close(self):self.closed=True
  pad=Pad();bridge=webpad.Bridge(lambda:pad,cache,clock=lambda:now[0],settings_loader=lambda:{})
  bridge.handle({'action':'state','owner':'test-owner','frame':{'buttons':['a']}})
  for _ in range(100):bridge.poll();bridge.status()
  self.assertEqual(len(scans),1)
  physical.append({'name':'Xbox'});monitor.dirty=True;bridge.poll()
  self.assertTrue(pad.closed);self.assertIsNone(bridge.owner);self.assertTrue(bridge.status()['real_connected'])
 def test_settings_cache_observes_atomic_settings_replacement(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);path=root/'settings.json';now=[0.];path.write_text('{"mouth_percent":70,"head_rad":2.5}');reads=[]
   def load():reads.append(1);return json.loads(path.read_text())
   with patch.object(pad_settings,'PATH',path),patch.object(webpad,'load',load):
    cache=webpad.SettingsCache(clock=lambda:now[0])
    for _ in range(100):self.assertEqual(cache()['mouth_percent'],70)
    self.assertEqual(len(reads),1)
    replacement=root/'next';replacement.write_text('{"mouth_percent":30,"head_rad":1.5}');os.replace(replacement,path);now[0]=.11
    self.assertEqual(cache()['mouth_percent'],30);self.assertEqual(len(reads),2)
 def test_missing_kick_adapter_is_reported_before_upload_and_all_slots_remain_visible(self):
  import model_packages
  with tempfile.TemporaryDirectory() as tmp:
   base=Path(tmp);cfg=base/'cfg';cfg.write_text('[policy]\n');listing=model_packages.catalog(base,cfg)
   self.assertEqual(len(listing['slots']),7)
   for slot in ('kick_left','kick_right'):
    info=next(s for s in listing['slots'] if s['slot']==slot);self.assertFalse(info['import_supported']);self.assertIn('合同适配',info['support_message'])
    with self.assertRaisesRegex(ControlError,'合同适配'):ServiceController(Store(),transport=object()).import_model('kick.zip',io.BytesIO(b'never read'),10,slot=slot)
 def test_snapshot_uses_one_coherent_sample_and_records_once(self):
  import console as ui
  import urllib.request
  from http.server import ThreadingHTTPServer
  class SampleStore(Store):
   calls=0
   def snapshot(self):self.calls+=1;return {'at':self.calls,'bus':{}}
  class Panel:
   def status(self,snapshot):return {'at':snapshot['at']}
  store=SampleStore();server=ThreadingHTTPServer(('127.0.0.1',0),ui.handler_for(store,{'bind':'127.0.0.1'},Panel(),Panel()))
  worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
  try:
   with urllib.request.urlopen(f'http://127.0.0.1:{server.server_port}/api/snapshot') as response:data=json.load(response)
   self.assertEqual(store.calls,1);self.assertEqual(data['at'],data['control']['at']);self.assertEqual(data['at'],data['service_control']['at'])
  finally:server.shutdown();server.server_close();worker.join()
 def test_collector_error_reconnects_reap_processes_and_close_pipes(self):
  import console as ui
  original=subprocess.Popen;procs=[];event=threading.Event();errors=[]
  class Stop:
   def is_set(self):return event.is_set()
   def wait(self,timeout):return event.wait(min(.001,timeout))
  def spawn(*args,**kw):
   proc=original([sys.executable,'-u','-c',"import sys,time;sys.stdin.buffer.read();print('{broken',flush=True);time.sleep(60)"],**kw);procs.append(proc);return proc
  def emit(frame):
   if frame.get('channel')=='bus' and frame.get('error'):
    errors.append(frame)
    if len(errors)==30:event.set()
  before=len(os.listdir('/proc/self/fd'))
  with patch.object(ui.subprocess,'Popen',spawn):ui.ssh_loop('unused',{},emit,Stop())
  self.assertEqual(len(procs),30);self.assertTrue(all(p.poll() is not None and p.stdout.closed and p.stderr.closed for p in procs))
  gc.collect();self.assertLessEqual(len(os.listdir('/proc/self/fd')),before+2)
 def test_slow_local_socket_reader_does_not_block_other_input_or_lease_expiry(self):
  # Run the actual selector loop with fake evdev and a small kernel send buffer.
  # AF_UNIX is forbidden here; substitute loopback TCP for socket addressing only.
  # A client that stops reading must not hold up another client or the .6 s lease.
  with tempfile.TemporaryDirectory() as tmp:
   base=Path(tmp);path=base/'input.sock';trace=base/'frames';errors=base/'stderr'
   code=r"""import os,socket,time,sys
from pathlib import Path
import webpad
path,trace=map(Path,sys.argv[1:]);webpad.SOCKET=path
class Tap:
 name=webpad.NAME;generation=1
webpad.PadTap=Tap
class Pad:
 def __init__(self):Tap.generation+=1
 def send(self,axes,buttons):
  with trace.open('a') as f:f.write(str(sorted(buttons))+'\n')
 def close(self):
  with trace.open('a') as f:f.write('closed\\n')
webpad.Xbox=Pad
webpad.SettingsCache=lambda *_:lambda:{'padding':'x'*50000}
class Monitor:
 socket=None
 def changed(self):return False
 def close(self):pass
webpad.InputMonitor=Monitor
webpad.real_gamepads=lambda:[]
webpad.DeviceCache=lambda **_:lambda:[]
webpad.os.chown=lambda *_:None
webpad.grp.getgrnam=lambda _:type('G',(),{'gr_gid':0})()
native=socket.socket
class Peer(native):
 def __init__(self,family=socket.AF_INET,*args,**kwargs):super().__init__(socket.AF_INET if family==socket.AF_UNIX else family,*args,**kwargs)
 def bind(self,address):
  super().bind(('127.0.0.1',0) if isinstance(address,str) else address);path.write_text(str(self.getsockname()[1]))
 def accept(self):
  client,address=super().accept();client.setsockopt(socket.SOL_SOCKET,socket.SO_SNDBUF,1024);return client,address
webpad.socket.socket=Peer
webpad.serve()
"""
   with errors.open('wb') as stderr:
    proc=subprocess.Popen([sys.executable,'-u','-c',code,str(path),str(trace)],stderr=stderr)
    try:
     deadline=time.monotonic()+3
     while not path.exists() and proc.poll() is None and time.monotonic()<deadline:time.sleep(.01)
     self.assertTrue(path.exists(),errors.read_text())
     with socket.socket() as slow,socket.socket() as fast:
      address=('127.0.0.1',int(path.read_text()));slow.connect(address);slow.sendall(b'{"action":"status"}\n');time.sleep(.02)
      fast.settimeout(.4);fast.connect(address);at=time.monotonic()
      fast.sendall(b'{"action":"state","owner":"fast-page","frame":{"buttons":["a"]}}\n')
      with fast.makefile('rb') as reader:answer=json.loads(reader.readline(65537))
      self.assertTrue(answer['accepted']);self.assertLess(time.monotonic()-at,.25)
      deadline=time.monotonic()+1.5
      while time.monotonic()<deadline:
       if trace.exists() and "closed" in trace.read_text():break
       time.sleep(.02)
      self.assertIn("['a']",trace.read_text());self.assertIn('closed',trace.read_text(),'input lease must still expire with a blocked reader')
    finally:proc.terminate();proc.wait(timeout=3)
 def test_action_descriptor_matches_native_supported_task_prefixes(self):
  from management_profile import ACTION_INFO
  native=(ROOT/'duck-control/src/deployment.rs').read_text();task_fn=native[native.index('pub fn task_slot('):native.index('fn read_json(')]
  for row in ACTION_INFO.values():
   if row['import_supported']:
    for prefix in row['task_prefixes']:
     self.assertIn('Mjlab-'+prefix+('-Flat-MicroDuck' if prefix=='VelStand' else '-'),task_fn)
   else:self.assertEqual(row['task_prefixes'],[])
 def test_command_logs_decode_invalid_utf8_but_configuration_stays_strict(self):
  import runtime
  result=runtime.run(sys.executable,'-c',"import sys;sys.stdout.buffer.write(bytes([255]));sys.stderr.buffer.write(bytes([254]))")
  self.assertEqual(result,'\ufffd')
  with self.assertRaisesRegex(RuntimeError,'\ufffd'):runtime.run(sys.executable,'-c',"import sys;sys.stderr.buffer.write(bytes([255]));sys.exit(1)")
 def test_shared_atomic_writer_preserves_mode_and_old_file_on_interrupted_replace(self):
  import configure
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'data';path.write_text('old');path.chmod(0o600)
   with patch.object(configure.os,'replace',side_effect=OSError('interrupted')):
    with self.assertRaises(OSError):configure.atomic_write(path,'new')
   self.assertEqual(path.read_text(),'old');self.assertEqual(path.stat().st_mode & 0o777,0o600)
   configure.atomic_write(path,'confirmed');self.assertEqual(path.read_text(),'confirmed');self.assertEqual(path.stat().st_mode & 0o777,0o600)
 def test_compact_history_retains_all_plotted_values_and_independent_actual_target(self):
  script="""import fs from 'node:fs';
const load=async p=>import('data:text/javascript;base64,'+Buffer.from(fs.readFileSync(p,'utf8')).toString('base64'));
const {historyFrame}=await load(process.argv[1]),{loopHz}=await load(process.argv[2]);
const row={id:31,status:'live',angle_deg:12,target_deg:25,position_raw:1000,goal_position_raw:1100,current_ma:3,current_raw:4,temperature_c:32,velocity_rpm:2,speed_raw:5,error_deg:13};
for(const mode of ['service','live']){
 const s={at:5,mode,channels:{bus:{status:'live'},state:{status:'live'},health:{status:'live'}},bus:{achieved_hz:49,raw:'x'.repeat(10000)},state:{loop:{hz:48},odom:{position:[1,2,3]}},health:{control_loop:{achieved_hz:47},battery:{volts:7},motors:{max_c:32}},imu:{status:'live',gravity:[0,0,-1]},servos:[row],raw_logs:'x'.repeat(10000)};
 const h=historyFrame(s);if(loopHz(h)!==loopHz(s)||JSON.stringify(h.servos)!==JSON.stringify(s.servos)||JSON.stringify(h.state.odom)!==JSON.stringify(s.state.odom)||JSON.stringify(h.imu)!==JSON.stringify(s.imu))throw Error('plotted values changed');
 if(JSON.stringify(h).length>JSON.stringify(s).length/10)throw Error('retained large payload');
 if(h.servos[0].angle_deg===h.servos[0].target_deg)throw Error('curves merged');
}
"""
  subprocess.run(['node','--input-type=module','-e',script,str(ROOT/'console/static/history-frame.js'),str(ROOT/'console/static/metrics.js')],check=True,capture_output=True)
if __name__=='__main__':unittest.main()

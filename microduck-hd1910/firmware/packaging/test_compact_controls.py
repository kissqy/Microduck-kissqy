"""Mode management and native volume regressions; no robot hardware writes."""
import copy,importlib.util,json,sys,tempfile,unittest
from io import StringIO
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'console'))
from controls import Controller,ControlError
from service_control import ServiceController
from release_identity import BUILD

def load_runtime():
 spec=importlib.util.spec_from_file_location('runtime_compact',ROOT/'packaging/runtime.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
class InlineThread:
 def __init__(self,target,args=(),**_):self.target=target;self.args=args
 def start(self):self.target(*self.args)
class Store:
 service_operation=False
 def __init__(self):self.events=[]
 def snapshot(self):return {'bus':{'build':BUILD,'mode':'commissioning'},'service_sample_fresh':False,'calibrated_count':0}
 def record_service_command(self,job):self.events.append(copy.deepcopy(job))
class CompactTests(unittest.TestCase):
 def test_saved_calibration_is_checked_in_helper_instead_of_live_joint_count(self):
  class Transport:
   def switch_mode(self,target,password):self.target=target;return {'mode':target}
  tr=Transport();c=ServiceController(Store(),transport=tr)
  with patch('service_control.threading.Thread',InlineThread):
   r=c.handle({'client':'compact-test','seq':1,'command':{'action':'switch-mode','target':'motion','supported':True}})
  self.assertTrue(r['accepted']);self.assertEqual(tr.target,'motion');self.assertEqual(c.job['status'],'completed')
 def test_invalid_saved_calibration_still_blocks_and_surfaces_helper_error(self):
  class Transport:
   def switch_mode(self,target,password):raise RuntimeError('IMU 安装方向尚未确认')
  c=ServiceController(Store(),transport=Transport())
  with patch('service_control.threading.Thread',InlineThread):c.handle({'client':'compact-test','seq':1,'command':{'action':'switch-mode','target':'motion','supported':True}})
  self.assertEqual(c.job['status'],'error');self.assertIn('IMU',c.job['error'])
 def test_disk_readiness_validates_actual_saved_file_not_display_count(self):
  m=load_runtime()
  with tempfile.TemporaryDirectory() as tmp,patch.object(m,'CONFIG',Path(tmp)/'robotd.toml'):
   self.assertFalse(m.motion_readiness()['motion_ready'])
   cal=Path(tmp)/'hd1910-calibration.toml';cal.write_bytes((ROOT/'packaging/hd1910-calibration.training.toml').read_bytes())
   self.assertTrue(m.motion_readiness()['motion_ready'])
   cal.write_text(cal.read_text().replace('imu_mount_verified = true','imu_mount_verified = false'))
   self.assertFalse(m.motion_readiness()['motion_ready'])
 def test_model_catalog_can_be_read_when_motor_daemon_has_failed(self):
  class Transport:
   def manage(self,action,privileged=False):
    return {'management_revision':'R17'} if action=='connection' else {'models':[{'id':'saved-walk'}]}
  c=ServiceController(Store(),transport=Transport())
  c.store.snapshot=lambda:{'bus':{},'service_sample_fresh':False}
  self.assertEqual(c.models()['models'][0]['id'],'saved-walk')
 def test_model_catalog_still_requires_the_installed_management_helper(self):
  class Transport:
   def manage(self,action,privileged=False):return {'management_revision':'unrelated'}
  c=ServiceController(Store(),transport=Transport());c.store.snapshot=lambda:{'bus':{}}
  with self.assertRaises(ControlError):c.models()
 def test_volume_roundtrip_is_finite_native_audio_and_does_not_open_input(self):
  spec=importlib.util.spec_from_file_location('finite_audio',ROOT/'packaging/audio-control.py');helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
  calls=[]
  class Audio:
   def __init__(self,*_,**kwargs):self.volume=None;calls.append(('create',kwargs))
   def initialize(self):self.volume=50;calls.append(('initialize',))
   def status(self):return {'volume':self.volume}
   def set_volume(self,value):self.volume=value;calls.append(('set',value));return {'accepted':True,'volume':value,'volume_saved':True}
  for argv,volume in [(['audio-control.py','status'],50),(['audio-control.py','set-volume','72'],72)]:
   with self.subTest(action=argv[1]):
    out=StringIO()
    with patch.object(helper,'NativeAudio',Audio),patch.object(sys,'argv',argv),redirect_stdout(out):helper.main()
    result=json.loads(out.getvalue());self.assertTrue(result['accepted']);self.assertEqual(result['audio']['volume'],volume)
  self.assertEqual(calls,[('create',{'initialize':False}),('initialize',),('create',{'initialize':False}),('set',72)])
 def test_volume_is_not_motion_and_rejects_noninteger_values(self):
  class Transport:
   connected=True;audio_status={}
   def call(self,c):self.command=c;return {'accepted':True,'audio':{'volume':c['volume']}}
  tr=Transport();c=Controller(Store(),transport=tr);c.pad={'real_connected':True}
  result=c.handle({'client':'compact-test','seq':1,'action':'set_volume','volume':38});self.assertEqual(result['audio']['volume'],38);self.assertEqual(c.pad,{'real_connected':True})
  for value in (True,1.5,101,-1):
   with self.assertRaises(ControlError):c.handle({'client':'compact-test','seq':2,'action':'set_volume','volume':value})
 def test_failed_native_volume_readback_does_not_report_success(self):
  from remote_audio import NativeAudio
  class Result:
   returncode=0;stdout=': values=900';stderr=''
  with tempfile.TemporaryDirectory() as tmp:
   setup=Path(tmp)/'voice-device.json';setup.write_text('{"card":"aic3104"}')
   audio=NativeAudio(lambda *_:None,setup=setup,config=Path(tmp)/'robotd.toml',runner=lambda *_args,**_kwargs:Result())
   before=audio.volume
   with self.assertRaisesRegex(RuntimeError,'回读不符'):audio.set_volume(20)
   self.assertEqual(audio.volume,before)
 def test_unconfigured_volume_fails_with_configuration_reason(self):
  from remote_audio import NativeAudio
  with tempfile.TemporaryDirectory() as tmp:
   audio=NativeAudio(lambda *_:None,setup=Path(tmp)/'missing.json',config=Path(tmp)/'robotd.toml')
   self.assertIsNone(audio.volume)
   with self.assertRaisesRegex(RuntimeError,'声音通道配置'):audio.set_volume(20)
if __name__=='__main__':unittest.main()

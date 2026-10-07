"""One editable descriptor feeds deployment copies; saved choices own runtime."""
import importlib.util,json,os,shutil,subprocess,sys,tempfile,threading,tomllib,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import controls,voice_preferences
from configure import dumps
ROOT=Path(__file__).resolve().parents[1]

class SettingsSourcesTests(unittest.TestCase):
 def test_changed_descriptor_reaches_both_deployments_and_injected_channel(self):
  # Editing the source must not require chasing defaults through UI/helpers.
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)
   for d in ('config','scripts','packaging','console/static'):(root/d).mkdir(parents=True,exist_ok=True)
   for rel in ('scripts/generate-management-profile.py','packaging/management_profile.py','packaging/release_identity.py','packaging/voice_preferences.py','packaging/robotd-profile.toml'):shutil.copyfile(ROOT/rel,root/rel)
   profile=json.loads((ROOT/'config/r17-management.json').read_text())
   profile['defaults']={'policy':{'action_scale':.62},'pad':{'mouth_percent':72.,'head_rad':1.},'audio':{'volume':23}}
   (root/'config/r17-management.json').write_text(json.dumps(profile))
   subprocess.run([sys.executable,str(root/'scripts/generate-management-profile.py')],check=True,capture_output=True)
   for rel in ('packaging/robotd-profile.toml','config/robotd-selftrained.toml'):
    policy=tomllib.loads((root/rel).read_text())['policy']
    for k,v in profile['defaults']['policy'].items():self.assertEqual(policy[k],v)
   for destination in ('packaging','console'):
    self.assertEqual(json.loads((root/destination/'management-profile.json').read_text())['defaults'],profile['defaults'])
   script="import json,management_profile,voice_preferences;print(json.dumps([management_profile.DEFAULTS,voice_preferences.DEFAULT_VOLUME]))"
   result=subprocess.run([sys.executable,'-c',script],env={**os.environ,'PYTHONPATH':str(root/'console'),'PYTHONDONTWRITEBYTECODE':'1'},capture_output=True,text=True,check=True,cwd=t)
   self.assertEqual(json.loads(result.stdout),[profile['defaults'],23])
   injected={'PROFILE':profile};exec((root/'console/management_profile.py').read_text(),injected)
   self.assertEqual(injected['DEFAULTS'],profile['defaults'])
 def test_audio_readback_uses_installed_helper_once_without_input_bootstrap(self):
  # The actual mixer owns saved volume. PC defaults must not be injected into
  # an input relay or applied during a passive dashboard connection.
  called=threading.Event();calls=[]
  class Maintenance:
   def _manage(self,argv,privileged):
    calls.append((argv,privileged));called.set();return {'accepted':True,'audio':{'volume':23}}
  transport=controls.Transport();transport.attach_service_transport(Maintenance())
  try:
   with patch.object(controls,'open_remote_socket',side_effect=AssertionError('audio/status activated webpad')):
    transport.call({'action':'connect'});self.assertTrue(called.wait(1))
    with transport.audio_lock:pass
    for _ in range(20):transport.call({'action':'connect'});transport.call({'action':'webpad_status'})
    self.assertEqual(transport.audio_status['volume'],23)
    self.assertEqual(calls,[(['python3',transport.AUDIO_HELPER,'status'],False)])
  finally:transport.close()
 def test_audio_defaults_are_not_assigned_by_robotd_restart(self):
  import runtime
  unit=runtime.unit('motion')
  self.assertNotIn('voice-setup.py',unit)
  self.assertNotIn('--init-volume',unit)
  self.assertFalse(hasattr(voice_preferences,'save'))
 def test_ordinary_upgrade_keeps_saved_filters_without_legacy_custom_marker(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);old=root/'old';new=root/'new'
   old.write_text(dumps({'policy':{'action_scale':.63,'head_lowpass':.44,'legs_lowpass':.66}}))
   subprocess.run([sys.executable,str(ROOT/'packaging/configure.py'),'--source',str(old),'--overrides',str(ROOT/'packaging/robotd-profile.toml'),'--output',str(new)],check=True,capture_output=True)
   policy=tomllib.loads(new.read_text())['policy']
   for k,v in {'action_scale':.63,'head_lowpass':.44,'legs_lowpass':.66}.items():self.assertEqual(policy[k],v)
 def test_missing_saved_imu_mount_is_not_replaced_by_official_orientation(self):
  spec=importlib.util.spec_from_file_location('calibration_default_test',ROOT/'packaging/calibration-config.py');helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
  with self.assertRaisesRegex(ValueError,'四元数'):helper.validate({'imu_mount_verified':True})

if __name__=='__main__':unittest.main()

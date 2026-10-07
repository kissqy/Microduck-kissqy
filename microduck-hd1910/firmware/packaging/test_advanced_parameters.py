"""Exercise the temporary extension through the real save and transport paths."""
import json,subprocess,sys,tempfile,tomllib,unittest
from pathlib import Path
from unittest.mock import patch
import runtime,advanced_parameters
from configure import dumps
from service_control import validate
from controls import ControlError
ROOT=Path(__file__).resolve().parents[1]
IDENT='9e3ff8bde021be28a728c02dbd8e7aaf'

class AdvancedParameterTests(unittest.TestCase):
 def test_only_explicit_apply_creates_test_settings_and_scale_stays_native(self):
  with tempfile.TemporaryDirectory() as t:
   config=Path(t)/'robotd.toml'
   original={'policy':{'walk':f'/models/{IDENT}/policy.onnx','action_scale':.7,'head_lowpass':.5,'legs_lowpass':.7,'voltage_adapt':True,'skill':[{'name':'roulade','params':{'action_scale':1.}}]},'pad':{'lb':'stand_test'}}
   config.write_text(dumps(original))
   self.assertIsNone(advanced_parameters.load(config))
   with patch.object(runtime,'CONFIG',config),patch('model_packages.verify_directory'):
    runtime.set_action_scale(IDENT,.63,4,1,700)
   saved=tomllib.loads(config.read_text());expected={**original,'policy':{**original['policy'],'action_scale':.63}}
   self.assertEqual(saved,expected)
   self.assertEqual(config.read_bytes(),config.with_name('robotd.saved.toml').read_bytes())
   self.assertEqual(advanced_parameters.load(config),{'kp':4,'kd':1,'torque_limit':700})
   # Ordinary model/firmware parameter derivation neither activates nor resets the test.
   out=config.with_name('derived.toml')
   subprocess.run([sys.executable,str(ROOT/'packaging/configure.py'),'--source',str(config),'--overrides',str(ROOT/'packaging/robotd-profile.toml'),'--output',str(out)],check=True,capture_output=True)
   self.assertEqual(advanced_parameters.load(out),{'kp':4,'kd':1,'torque_limit':700})
   config.with_name('servo-test-parameters.json').unlink()
   subprocess.run([sys.executable,str(ROOT/'packaging/configure.py'),'--source',str(config),'--overrides',str(ROOT/'packaging/robotd-profile.toml'),'--output',str(out)],check=True,capture_output=True)
   self.assertIsNone(advanced_parameters.load(out))
 def test_invalid_register_values_do_not_change_any_saved_value(self):
  with tempfile.TemporaryDirectory() as t:
   config=Path(t)/'robotd.toml';config.write_text('[policy]\naction_scale=.7\n')
   before=config.read_bytes()
   for kp,kd,torque in [(-1,0,681),(3,256,681),(3,0,1001),(3.5,0,681),(True,0,681)]:
    with patch.object(runtime,'CONFIG',config),self.assertRaises(ValueError):runtime.set_action_scale(IDENT,.63,kp,kd,torque)
    self.assertEqual(config.read_bytes(),before);self.assertIsNone(advanced_parameters.load(config))
 def test_api_requires_all_four_values_in_one_request(self):
  request={'action':'set-action-scale','model':IDENT,'scale':.7,'kp':3,'kd':0,'torque_limit':681,'supported':True}
  self.assertEqual(validate(request),request)
  for key in ('scale','kp','kd','torque_limit'):
   incomplete=request.copy();incomplete.pop(key)
   with self.assertRaises(ControlError):validate(incomplete)
  for key,value in [('kp',-1),('kd',256),('torque_limit',1001),('kp',True)]:
   with self.assertRaises(ControlError):validate({**request,key:value})

if __name__=='__main__':unittest.main()

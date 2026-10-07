import hashlib,tempfile,tomllib,unittest,subprocess,sys
from pathlib import Path
from unittest.mock import patch
import runtime
from configure import dumps
ROOT=Path(__file__).resolve().parents[1]
class ReadbackTests(unittest.TestCase):
 def test_catalog_uses_shipped_default_but_saved_selection_wins(self):
  for policy,expected in (({},.7),({'action_scale':.64},.64)):
   with self.subTest(policy=policy),tempfile.TemporaryDirectory() as t:
    cfg=Path(t)/'robotd.toml';cfg.write_text(dumps({'policy':policy}))
    with patch.object(runtime,'CONFIG',cfg),patch.object(runtime,'detect_port',return_value='/dev/ttyS2'),patch('model_packages.catalog',return_value={'models':[{'slot':'walk'}]}):
     result=runtime.model_list()
    self.assertEqual(result['action_scale'],expected);self.assertEqual(result['models'][0]['action_scale'],expected);self.assertEqual(result['default_action_scale'],.7)
 def test_upgrade_retires_secondary_scale_and_keeps_official_choice(self):
  with tempfile.TemporaryDirectory() as t:
   source=Path(t)/'old.toml';out=Path(t)/'new.toml';data=tomllib.loads((ROOT/'packaging/robotd-profile.toml').read_text())
   data['policy'].update(action_scale=.65,r17_inference_scale=.7,head_lowpass=.5,legs_lowpass=.7,hold_action_scale=.3);source.write_text(dumps(data))
   subprocess.run([sys.executable,str(ROOT/'packaging/configure.py'),'--source',str(source),'--replace-models','--overrides',str(ROOT/'packaging/robotd-profile.toml'),'--output',str(out)],check=True,capture_output=True)
   policy=tomllib.loads(out.read_text())['policy'];self.assertEqual(policy['action_scale'],.65);self.assertNotIn('r17_inference_scale',policy);self.assertNotIn('head_lowpass',policy);self.assertNotIn('legs_lowpass',policy);self.assertNotIn('hold_action_scale',policy)
   # Apply the same upgrade again: the selected official value survives restart/upgrade.
   source.write_bytes(out.read_bytes())
   subprocess.run([sys.executable,str(ROOT/'packaging/configure.py'),'--source',str(source),'--replace-models','--overrides',str(ROOT/'packaging/robotd-profile.toml'),'--output',str(out)],check=True,capture_output=True)
   self.assertEqual(tomllib.loads(out.read_text())['policy'],policy)
 def test_confirmation_requires_actual_hash_and_official_global_readback(self):
  data={'policy':{'walk':str(ROOT/'policies/walk/policy.onnx'),'action_scale':.65,'head_lowpass':.5,'legs_lowpass':.7,'voltage_adapt':False}}
  sha=hashlib.sha256(Path(data['policy']['walk']).read_bytes()).hexdigest();bus={'build':runtime.BUILD,'loaded_models':{'walk':{'sha256':sha}},'action_scale':.65,'head_lowpass':.5,'legs_lowpass':.7,'voltage_adapt':False}
  with patch.object(runtime,'config',return_value=data),patch.object(runtime,'rpc',return_value=bus):self.assertTrue(runtime.verify_loaded_models()['loaded_models_verified'])
  for bad in ({**bus,'action_scale':.9},{**bus,'loaded_models':{'walk':{'sha256':'old-model'}}}):
   with patch.object(runtime,'config',return_value=data),patch.object(runtime,'rpc',return_value=bad),patch.object(runtime.time,'monotonic',side_effect=[0,0,9]),patch.object(runtime.time,'sleep'):
    with self.assertRaises(ValueError):runtime.verify_loaded_models()
 def test_all_four_slots_must_actually_load_including_roulade(self):
  policy={slot:str(ROOT/'policies'/slot/'policy.onnx') for slot in ('walk','sitstand','ground_pick','roulade')}
  loaded={slot:{'sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest()} for slot,path in policy.items()}
  policy['skill']=[{'name':'roulade','params':{'action_scale':1.0}}]
  bus={'model_action_scales':{'roulade':1.0},'build':runtime.BUILD,'loaded_models':loaded,'action_scale':.7,'head_lowpass':.5,'legs_lowpass':.7,'voltage_adapt':True}
  with patch.object(runtime,'config',return_value={'policy':policy}),patch.object(runtime,'rpc',return_value=bus):
   self.assertTrue(runtime.verify_loaded_models()['loaded_models_verified'])
  for bad in ({key:value for key,value in loaded.items() if key!='roulade'},{**loaded,'roulade':{'sha256':'old-model'}}):
   with patch.object(runtime,'config',return_value={'policy':policy}),patch.object(runtime,'rpc',return_value={**bus,'loaded_models':bad}),patch.object(runtime.time,'monotonic',side_effect=[0,0,9]),patch.object(runtime.time,'sleep'):
    with self.assertRaises(ValueError):runtime.verify_loaded_models()

class RollScaleReadback(unittest.TestCase):
 def test_wrong_actual_roulade_coefficient_cannot_complete_upgrade(self):
  p=ROOT/'policies/roulade/policy.onnx';policy={'roulade':str(p),'skill':[{'name':'roulade','params':{'action_scale':1.0}}]}
  bus={'build':runtime.BUILD,'loaded_models':{'roulade':{'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}},'action_scale':.7,'head_lowpass':.5,'legs_lowpass':.7,'voltage_adapt':True,'model_action_scales':{'roulade':.9}}
  with patch.object(runtime,'config',return_value={'policy':policy}),patch.object(runtime,'rpc',return_value=bus),patch.object(runtime.time,'monotonic',side_effect=[0,0,9]),patch.object(runtime.time,'sleep'):
   with self.assertRaises(ValueError):runtime.verify_loaded_models()

if __name__=='__main__':unittest.main()

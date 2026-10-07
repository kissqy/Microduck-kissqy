"""Import the real 11000-round unfiltered teacher without changing operator choices."""
import json,sys,tempfile,tomllib,unittest,zipfile
from pathlib import Path
import model_packages as models
from configure import dumps
ROOT=Path(__file__).resolve().parents[1]
ID='a481d9f211f31d9476ab1a319fe362a2'
class RoughStandTests(unittest.TestCase):
 def test_stored_teacher_does_not_change_binding_tuning_or_calibration(self):
  with tempfile.TemporaryDirectory() as tmp:
   base=Path(tmp);cfg=base/'robotd.toml';cal=base/'calibration.toml'
   policy={'custom_only':True,'walk':'/my/walk/policy.onnx','stand':'none','sitstand':'/my/sit/policy.onnx','action_scale':.63,'voltage_adapt':True,'head_lowpass':.5,'legs_lowpass':.7,'gain':5,'standing_gain_ratio':.8}
   cfg.write_text(dumps({'policy':policy,'pad':{'dpad_down':'sit_toggle'},'audio':{'gain':.37}}));before=cfg.read_bytes()
   cal.write_bytes((ROOT/'packaging/hd1910-calibration.robot.toml').read_bytes());calibration=cal.read_bytes()
   archive=base/'stand.zip'
   with zipfile.ZipFile(archive,'w') as z:
    for name in ('policy.onnx',*models.SOURCE_FILES):
     p=ROOT/'policies/stand'/name
     if p.is_file():z.write(p,name)
   result=models.import_package(archive,archive.name,base,cfg,cal,validator=False,target_slot='stand')
   self.assertEqual(result['id'],ID)
   self.assertEqual(cfg.read_bytes(),before);self.assertEqual(cal.read_bytes(),calibration)
   stored=base/'models'/ID
   self.assertEqual((stored/'policy.onnx').read_bytes(),(ROOT/'policies/stand/policy.onnx').read_bytes())
   contract=models.verify_directory(stored)['contract']
   self.assertTrue(contract['teacher_only']);self.assertEqual(contract['actions']['joint_pos']['scale'],1.0)
   self.assertEqual(contract['hardware_command']['firmware_kp_raw'],5)
   self.assertNotIn('voltage_adapt',contract['required_policy_settings'])
   self.assertFalse(contract['action_filter']['enabled'])
   self.assertEqual(models.verify_directory(stored)['policy_settings'],{'action_scale':1.0,'head_lowpass':1.0,'legs_lowpass':1.0})
   listing=models.catalog(base,cfg);row=next(r for r in listing['models'] if r['id']==ID)
   self.assertFalse(row['active']);self.assertEqual(row['slot'],'stand')
 def test_target_slot_mismatch_does_not_import_as_walk(self):
  with tempfile.TemporaryDirectory() as tmp:
   base=Path(tmp);archive=base/'stand.zip'
   with zipfile.ZipFile(archive,'w') as z:
    for name in ('policy.onnx',*models.SOURCE_FILES):
     p=ROOT/'policies/stand'/name
     if p.is_file():z.write(p,name)
   with self.assertRaises(ValueError):models.import_package(archive,archive.name,base,base/'config',base/'cal',validator=False,target_slot='walk')
   self.assertFalse((base/'models'/ID).exists())
 def test_shipped_profile_keeps_stand_unbound_and_training_records_intact(self):
  policy=tomllib.loads((ROOT/'packaging/robotd-profile.toml').read_text())['policy']
  self.assertEqual(policy['stand'],'none');self.assertIn('1cbf8730eadd75a5704332c9f3c10f60',policy['walk'])
  c=json.loads((ROOT/'policies/stand/deployment-contract.json').read_text())
  self.assertEqual(c['task'],'Mjlab-StandUp-Rough-Backlash-MicroDuck')
  self.assertEqual(c.get('action_ema_old_weight',0.0),0.0)
  self.assertFalse(c['action_filter']['enabled'])
  self.assertEqual(json.loads((ROOT/'policies/stand/training-request.json').read_text())['source_iteration'],11000)
 def test_disabled_filter_rejects_non_passthrough_alpha(self):
  files={n:(ROOT/'policies/stand'/n).read_bytes() for n in ('policy.onnx',*models.SOURCE_FILES) if (ROOT/'policies/stand'/n).is_file()}
  contract=json.loads(files['deployment-contract.json'])
  contract['action_filter']['head_alpha']=.5
  contract['required_policy_settings']['head_lowpass']=.5
  files['deployment-contract.json']=json.dumps(contract).encode()
  with self.assertRaisesRegex(ValueError,'滤波系数'):models.validate_export(files)
if __name__=='__main__':unittest.main()

class TestBindingUpgradeTests(unittest.TestCase):
 def test_existing_bindings_and_models_survive_test_skill_install_and_reboot(self):
  import subprocess
  for lb in ('','operator_skill'):
   with self.subTest(lb=lb),tempfile.TemporaryDirectory() as tmp:
    base=Path(tmp);old=base/'old';previous=base/'previous';out=base/'out'
    shipped_walk=tomllib.loads((ROOT/'packaging/robotd-profile.toml').read_text())['policy']['walk']
    previous.write_text(dumps({'policy':{'action_scale':.7,'walk':shipped_walk,'skill':[{'name':'roulade'}]},'pad':{'lb':''}}))
    policy={'custom_only':True,'walk':'/my/walk','stand':'none','sitstand':'/my/sit','action_scale':.63,'skill':[{'name':'roulade','duration':1.7},{'name':'operator_skill','duration':3}]}
    old.write_text(dumps({'policy':policy,'pad':{'a':'ground_pick','x':'roulade','lb':lb,'dpad_down':'sit_toggle'}}))
    args=[sys.executable,str(ROOT/'packaging/configure.py'),'--source',str(old),'--previous-overrides',str(previous),'--overrides',str(ROOT/'packaging/robotd-profile.toml'),'--output',str(out)]
    subprocess.run(args,check=True,capture_output=True)
    got=tomllib.loads(out.read_text());self.assertEqual(got['pad']['lb'],'stand_test')
    for k in ('walk','stand','sitstand','action_scale'):self.assertEqual(got['policy'][k],policy[k])
    self.assertEqual(got['policy']['skill'][:2],policy['skill'])
    skill=got['policy']['skill'][2];self.assertEqual(skill['name'],'stand_test');self.assertEqual(skill['duration'],6)
    self.assertEqual(skill['params']['action_scale'],1.0);self.assertIn(ID,skill['path'])
    # Once installed, an operator's disabled key and changed timing survive upgrades.
    got['pad']['lb']='';got['policy']['skill'][2]['duration']=2.5
    old.write_text(dumps(got));previous.write_bytes((ROOT/'packaging/robotd-profile.toml').read_bytes())
    subprocess.run(args,check=True,capture_output=True)
    again=tomllib.loads(out.read_text());self.assertEqual(again['pad']['lb'],'');self.assertEqual(again['policy']['skill'][2]['duration'],2.5)

class RecoveryScaleUpgradeTests(unittest.TestCase):
 def test_installed_recovery_scales_become_one_without_changing_gait_or_other_skills(self):
  import subprocess
  with tempfile.TemporaryDirectory() as tmp:
   base=Path(tmp);old=base/'old.toml';previous=base/'previous.toml';out=base/'new.toml'
   previous.write_bytes((ROOT/'packaging/robotd-profile.toml').read_bytes().replace(ID.encode(),b'd11f8430712c35cb2416ce3948e9f8b7').replace(b'standing_action_scale = 1.0\n',b'').replace(b'[policy.skill.params]\naction_scale = 1.0\n\n[pad]',b'\n[pad]'))
   data={'policy':{'custom_only':True,'walk':'/custom/walk.onnx','stand':'none','standing_action_scale':.7,'action_scale':.63,'skill':[{'name':'stand_test','path':'/custom/stand.onnx','duration':2.5,'params':{'action_scale':.7,'gain_ratio':.8}},{'name':'operator_skill','duration':3,'params':{'action_scale':.54}}]},'pad':{'lb':'stand_test','rb':'operator_skill'}}
   old.write_text(dumps(data))
   subprocess.run([sys.executable,str(ROOT/'packaging/configure.py'),'--source',str(old),'--previous-overrides',str(previous),'--overrides',str(ROOT/'packaging/robotd-profile.toml'),'--output',str(out)],check=True,capture_output=True)
   got=tomllib.loads(out.read_text());self.assertEqual(got['policy']['standing_action_scale'],1.0)
   self.assertEqual(got['policy']['action_scale'],.63);self.assertEqual(got['policy']['walk'],'/custom/walk.onnx');self.assertEqual(got['policy']['stand'],'none')
   skill=next(s for s in got['policy']['skill'] if s['name']=='stand_test')
   self.assertEqual(skill,{**data['policy']['skill'][0],'path':f'/opt/robot/feetech-ft5-r5/models/{ID}/policy.onnx','params':{'action_scale':1.0,'gain_ratio':.8}})
   self.assertEqual(next(s for s in got['policy']['skill'] if s['name']=='operator_skill'),data['policy']['skill'][1])
   self.assertEqual(got['pad']['lb'],'stand_test');self.assertEqual(got['pad']['rb'],'operator_skill')

class MissingRecoveryUpgradeTests(unittest.TestCase):
 def test_explicit_replacement_reinstalls_missing_skill_and_lb_only_once(self):
  import subprocess
  with tempfile.TemporaryDirectory() as tmp:
   base=Path(tmp);old=base/'old.toml';previous=base/'previous.toml';out=base/'new.toml'
   previous.write_bytes((ROOT/'packaging/robotd-profile.toml').read_bytes().replace(ID.encode(),b'd11f8430712c35cb2416ce3948e9f8b7'))
   policy={'custom_only':True,'walk':'/custom/walk.onnx','action_scale':.63,'head_lowpass':.5,'legs_lowpass':.7,'voltage_adapt':True,'skill':[{'name':'operator_skill','duration':3}]}
   old.write_text(dumps({'policy':policy,'pad':{'lb':'operator_skill','rb':'operator_skill'}}))
   args=[sys.executable,str(ROOT/'packaging/configure.py'),'--source',str(old),'--previous-overrides',str(previous),'--overrides',str(ROOT/'packaging/robotd-profile.toml'),'--output',str(out)]
   subprocess.run(args,check=True,capture_output=True)
   got=tomllib.loads(out.read_text());self.assertEqual(got['pad']['lb'],'stand_test');self.assertEqual(got['pad']['rb'],'operator_skill')
   self.assertEqual(got['policy']['walk'],policy['walk']);self.assertEqual(got['policy']['action_scale'],.63)
   for k in ('head_lowpass','legs_lowpass','voltage_adapt'):self.assertEqual(got['policy'][k],policy[k])
   skill=next(s for s in got['policy']['skill'] if s['name']=='stand_test');self.assertIn(ID,skill['path']);self.assertEqual(skill['params']['action_scale'],1.)
   got['pad']['lb']='operator_skill';old.write_text(dumps(got));previous.write_bytes((ROOT/'packaging/robotd-profile.toml').read_bytes())
   subprocess.run(args,check=True,capture_output=True)
   self.assertEqual(tomllib.loads(out.read_text())['pad']['lb'],'operator_skill')

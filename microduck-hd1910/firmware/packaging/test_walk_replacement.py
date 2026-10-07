"""Ship one joint Walk plus four other models and keep the operator's saved tuning."""
import json,subprocess,sys,tempfile,tomllib,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
from configure import dumps
import model_packages as models
NEW='1cbf8730eadd75a5704332c9f3c10f60'
TEACHER='9e3ff8bde021be28a728c02dbd8e7aaf'
OLD='ff30787a148229005d12bef353d57120'
SIT='1c94934c6421ec72ed48079cea749668'
PICK='2b69fa681ed06f7ded9e2a2d12ba5c67'
class WalkReplacementTests(unittest.TestCase):
 def test_default_change_migrates_once_and_preserves_operator_choices(self):
  profile=ROOT/'packaging/robotd-profile.toml'
  for previous_default,saved,expected in ((.9,.9,.7),(.9,.63,.63),(.7,.9,.9)):
   with self.subTest(previous_default=previous_default,saved=saved),tempfile.TemporaryDirectory() as t:
    old=Path(t)/'old.toml';previous=Path(t)/'previous.toml';out=Path(t)/'robotd.toml'
    policy={'custom_only':True,'walk':'/custom/walk/policy.onnx','action_scale':saved,'head_lowpass':.44,'legs_lowpass':.66}
    old.write_text(dumps({'policy':policy}));previous.write_text(dumps({'policy':{'action_scale':previous_default,'walk':tomllib.loads(profile.read_text())['policy']['walk']}}))
    result=subprocess.run([sys.executable,str(ROOT/'packaging/configure.py'),'--source',str(old),'--previous-overrides',str(previous),'--overrides',str(profile),'--output',str(out)],check=True,capture_output=True,text=True)
    got=tomllib.loads(out.read_text())['policy'];self.assertEqual(got['action_scale'],expected)
    for name in ('walk','head_lowpass','legs_lowpass'):self.assertEqual(got[name],policy[name])
    self.assertEqual('默认值已更新' in result.stdout,saved!=expected)
 def test_upgrade_moves_saved_walking_scale_and_disables_deleted_skills(self):
  profile=ROOT/'packaging/robotd-profile.toml'
  for previous in (OLD,'e6173f3d950167a125c3c9bee5ccfcc1','0b8f04476cab068f6db14b4b08856212'):
   for new_choice in (None,0.8):
    with tempfile.TemporaryDirectory() as t:
     old=Path(t)/'old.toml';out=Path(t)/'robotd.toml';data=tomllib.loads(profile.read_text());p=data['policy']
     p['walk']=f'/opt/robot/feetech-ft5-r5/models/{previous}/policy.onnx';p['stand']='/old/getup.onnx';p['ground_pick']='/old/pick.onnx';p['hold_action_scale']=0.2
     p['action_scales']={previous:0.6,SIT:0.9,'28dab340fcd51440dd7362aa1010b0f4':0.7,'12b8e58479ebd6bf2606f4ef43048cea':0.5}
     if new_choice is not None:p['action_scales'][NEW]=new_choice
     old.write_text(dumps(data))
     subprocess.run([sys.executable,str(ROOT/'packaging/configure.py'),'--source',str(old),'--replace-models','--overrides',str(profile),'--output',str(out)],check=True,capture_output=True)
     got=tomllib.loads(out.read_text())['policy'];self.assertIn(NEW,got['walk']);self.assertEqual(got['stand'],'none');self.assertIn(PICK,got['ground_pick'])
     self.assertEqual(got['action_scale'],0.7);self.assertNotIn('head_lowpass',got);self.assertNotIn('legs_lowpass',got);self.assertNotIn('action_scales',got);self.assertNotIn('hold_action_scale',got)
 def test_legacy_fallback_scale_migrates_without_an_action_map(self):
  profile=ROOT/'packaging/robotd-profile.toml'
  with tempfile.TemporaryDirectory() as t:
   old=Path(t)/'old.toml';out=Path(t)/'new.toml'
   old.write_text(dumps({'policy':{'walk':f'/opt/robot/feetech-ft5-r5/models/{OLD}/policy.onnx','walk_action_scale':0.5}}))
   subprocess.run([sys.executable,str(ROOT/'packaging/configure.py'),'--source',str(old),'--replace-models','--overrides',str(profile),'--output',str(out)],check=True,capture_output=True)
   self.assertEqual(tomllib.loads(out.read_text())['policy']['action_scale'],0.7)
 def test_legacy_teacher_fixture_sitstand_and_pick_keep_original_training_mapping(self):
  for slot,ident,iteration in [('walk',TEACHER,13999),('sitstand',SIT,10000),('ground_pick',PICK,4999)]:
   directory=ROOT/'test-data/walk-teacher14000' if slot=='walk' else ROOT/'policies'/slot
   info=models.verify_directory(directory);self.assertEqual(info['id'],ident);self.assertEqual(info['slot'],slot);self.assertEqual(info['contract']['actions']['joint_pos']['scale'],.7 if slot=='walk' else 1.0)
   req=json.loads((directory/'training-request.json').read_text());self.assertEqual(req['source_iteration'],iteration)
  # Independent LB recovery remains a skill; it must not enable the Stand slot.
  self.assertEqual(tomllib.loads((ROOT/'packaging/robotd-profile.toml').read_text())['policy']['stand'],'none')
 def test_new_joint_walk_is_the_release_default_with_separate_runtime_and_training_settings(self):
  info=models.verify_directory(ROOT/'policies/walk')
  self.assertEqual(info['id'],NEW);self.assertEqual(info['slot'],'walk')
  self.assertEqual(info['contract']['actions']['joint_pos']['scale'],1.0)
  self.assertEqual(info['policy_settings'],{'action_scale':1.0,'head_lowpass':1.0,'legs_lowpass':1.0})
  self.assertEqual(info['execution_profile'],{'schema':'microduck-runtime-execution/v1','model_sha256':info['sha256'],
                   'mode':'uniform','action_scale':.9,'head_lowpass':.5,'legs_lowpass':.7})
  self.assertEqual(json.loads((ROOT/'policies/walk/training-request.json').read_text())['source_iteration'],9599)
  self.assertIn('/'+NEW+'/',tomllib.loads((ROOT/'packaging/robotd-profile.toml').read_text())['policy']['walk'])
  shipped=[models.verify_directory(p) for p in (ROOT/'policies').iterdir() if (p/'policy.onnx').is_file()]
  self.assertEqual(len(shipped),5)
  self.assertEqual([p['id'] for p in shipped if p['slot']=='walk'],[NEW])
  self.assertNotIn(TEACHER,[p['id'] for p in shipped])
 def test_ground_pick_official_phase_and_binding_survive_reinstall(self):
  info=models.verify_directory(ROOT/'policies/ground_pick')
  self.assertEqual(info['contract']['task_adapter'],'hd1910-official0151')
  self.assertEqual(info['contract']['commands']['twist']['period'],4.0)
  self.assertEqual(info['home'],models.verify_directory(ROOT/'policies/walk')['home'])
  for path in ('packaging/robotd-profile.toml','config/robotd-selftrained.toml'):
   data=tomllib.loads((ROOT/path).read_text());self.assertEqual(data['pad']['a'],'ground_pick');self.assertEqual(data['pad']['dpad_down'],'sit_toggle')
   self.assertEqual(data['policy']['ground_pick_period'],4.0);self.assertEqual(data['policy']['ground_pick_action_scale'],1.0)
if __name__=='__main__':unittest.main()

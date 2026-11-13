"""Legacy teacher metadata remains a validation fixture outside the release catalog."""
import hashlib,json,shutil,subprocess,sys,tempfile,tomllib,unittest,zipfile
from pathlib import Path
from configure import dumps
import model_packages as models
ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'test-data/walk-teacher14000'
ID='9e3ff8bde021be28a728c02dbd8e7aaf'

class TeacherImportTests(unittest.TestCase):
 def test_release_replaces_requested_slots_once_and_keeps_other_operator_choices(self):
  profile=ROOT/'packaging/robotd-profile.toml';defaults=tomllib.loads(profile.read_text())
  for saved_scale in (.31,.7,.9):
   with self.subTest(scale=saved_scale),tempfile.TemporaryDirectory() as t:
    b=Path(t);old=b/'old';previous=b/'previous';out=b/'out'
    policy={'custom_only':True,'walk':'/old/walk/policy.onnx','sitstand':'/my/sit/policy.onnx','stand':'none','ground_pick':'/my/pick/policy.onnx','roulade':'/my/roll/policy.onnx','action_scale':saved_scale,'head_lowpass':.41,'legs_lowpass':.69,'voltage_adapt':True}
    old.write_text(dumps({'policy':policy,'pad':{'mouth_open_max':.6},'audio':{'gain':.4}}))
    previous.write_text(dumps({'policy':{'walk':'/old/walk/policy.onnx','action_scale':saved_scale}}))
    args=[sys.executable,str(ROOT/'packaging/configure.py'),'--source',str(old),'--previous-overrides',str(previous),'--overrides',str(profile),'--output',str(out)]
    subprocess.run(args,check=True,capture_output=True)
    got=tomllib.loads(out.read_text());self.assertEqual(got['policy']['walk'],defaults['policy']['walk'])
    for k,v in policy.items():
     self.assertEqual(got['policy'][k],defaults['policy'][k] if k in ('walk','ground_pick','roulade') else v)
    self.assertEqual(got['pad']['mouth_open_max'],.6);self.assertEqual(got['audio']['gain'],.4)
    # Once installed, manually selected models/settings survive another upgrade.
    previous.write_text(profile.read_text());old.write_text(dumps({'policy':policy}))
    subprocess.run(args,check=True,capture_output=True)
    for k,v in policy.items():self.assertEqual(tomllib.loads(out.read_text())['policy'][k],v)
 def test_teacher_metadata_is_preserved_without_training_simulation_at_runtime(self):
  info=models.verify_directory(FIXTURE);c=info['contract']
  self.assertEqual(info['id'],ID);self.assertEqual(c['trained_action_scale'],.7)
  self.assertEqual(c['action_filter']['previous_action_observation'],'raw_policy_output')
  self.assertEqual(c['gear_backlash']['joint_count'],14)
  self.assertEqual(c['gear_backlash']['encoder_position'],'motor + passive backlash')
  self.assertEqual(json.loads((FIXTURE/'training-request.json').read_text())['source_iteration'],13999)


 def test_upgrade_preserves_runtime_settings_without_custom_marker(self):
  for custom in (False,True):
   for voltage in (False,True):
    with self.subTest(custom=custom,voltage=voltage),tempfile.TemporaryDirectory() as t:
     b=Path(t);old=b/'old';out=b/'out';previous=b/'robotd-profile.toml'
     previous.write_bytes((ROOT/'packaging/robotd-profile.toml').read_bytes())
     profile=json.loads((ROOT/'config/r17-management.json').read_text())
     (b/'management-profile.json').write_text(json.dumps(profile))
     saved={'custom_only':custom,'walk':'/old/walk/policy.onnx','voltage_adapt':voltage,'gain':1.11,'standing_gain_ratio':.82,'ground_pick_gain_ratio':.73,'roulade_gain_ratio':.94}
     old.write_text(dumps({'policy':saved}))
     subprocess.run([sys.executable,str(ROOT/'packaging/configure.py'),'--source',str(old),'--previous-overrides',str(previous),'--overrides',str(ROOT/'packaging/robotd-profile.toml'),'--output',str(out)],check=True,capture_output=True)
     got=tomllib.loads(out.read_text())['policy']
     for n,v in saved.items():
      if n not in ('custom_only','walk'):self.assertEqual(got[n],v)

if __name__=='__main__':unittest.main()

"""Legacy teacher import remains supported as a regression fixture, outside the release catalog."""
import hashlib,json,shutil,subprocess,sys,tempfile,tomllib,unittest,zipfile
from pathlib import Path
from configure import dumps
import model_packages as models
ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'test-data/walk-teacher14000'
ID='9e3ff8bde021be28a728c02dbd8e7aaf'

class TeacherImportTests(unittest.TestCase):
 def test_original_export_import_keeps_saved_parameters_and_calibration(self):
  with tempfile.TemporaryDirectory() as t:
   b=Path(t);cfg=b/'robotd.toml';cal=b/'calibration.toml'
   cal.write_bytes((ROOT/'packaging/hd1910-calibration.robot.toml').read_bytes());cal_before=cal.read_bytes()
   policy={'custom_only':True,'walk':'none','sitstand':'none','action_scale':.63,'head_lowpass':.42,'legs_lowpass':.68,'voltage_adapt':True}
   cfg.write_text(dumps({'policy':policy,'pad':{'dpad_down':'sit_toggle'}}))
   archive=b/'teacher.zip'
   with zipfile.ZipFile(archive,'w') as z:
    for name in ('policy.onnx',*models.SOURCE_FILES):
     if (FIXTURE/name).exists():z.write(FIXTURE/name,name)
   info=models.import_package(archive,archive.name,b,cfg,cal,validator=False,target_slot='walk')
   models.assign_model(info['id'],'walk',b,cfg,cal)
   self.assertEqual(info['id'],ID)
   saved=tomllib.loads(cfg.read_text())['policy']
   for name,value in policy.items():
    if name!='walk':self.assertEqual(saved[name],value)
   self.assertEqual(cal.read_bytes(),cal_before)
   self.assertEqual(cfg.read_bytes(),cfg.with_name('robotd.saved.toml').read_bytes())
   self.assertEqual((b/'models'/ID/'policy.onnx').read_bytes(),(FIXTURE/'policy.onnx').read_bytes())
   self.assertEqual(models.catalog(b,cfg)['configured_model'],ID)
 def test_release_replaces_walk_once_and_keeps_all_operator_choices(self):
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
     if k!='walk':self.assertEqual(got['policy'][k],v)
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

 def test_same_weights_corrected_contract_replaces_bad_export_and_inherits_runtime(self):
  # A weight hash alone cannot detect an exporter-only contract correction.
  for voltage in (False,True):
   with self.subTest(voltage=voltage),tempfile.TemporaryDirectory() as t:
    b=Path(t);cfg=b/'robotd.toml';cal=b/'calibration.toml';cal.write_bytes((ROOT/'packaging/hd1910-calibration.robot.toml').read_bytes())
    policy={'custom_only':True,'walk':'none','action_scale':.63,'head_lowpass':.42,'legs_lowpass':.68,'voltage_adapt':voltage,'gain':1.13,'standing_gain_ratio':.81,'ground_pick_gain_ratio':.72,'roulade_gain_ratio':.93}
    cfg.write_text(dumps({'policy':policy}));original=cfg.read_bytes();calibration=cal.read_bytes()
    files={n:(FIXTURE/n).read_bytes() for n in ('policy.onnx',*models.SOURCE_FILES)}
    broken=json.loads(files['deployment-contract.json']);broken.pop('export_contract_revision');broken['required_policy_settings']['voltage_adapt']=False
    for label,contract in (('old',json.dumps(broken).encode()),('corrected',files['deployment-contract.json'])):
     archive=b/(label+'.zip')
     with zipfile.ZipFile(archive,'w') as z:
      for n,data in files.items():z.writestr(n,contract if n=='deployment-contract.json' else data)
     info=models.import_package(archive,archive.name,b,cfg,cal,validator=False,target_slot='walk')
     self.assertEqual(info['id'],ID)
    self.assertTrue(info['duplicate']);directory=b/'models'/ID
    self.assertEqual(cfg.read_bytes(),original);self.assertEqual(cal.read_bytes(),calibration)
    for n,data in files.items():self.assertEqual((directory/n).read_bytes(),data,n)
    contract=models.verify_directory(directory)['contract']
    self.assertEqual(contract['export_contract_revision'],2);self.assertNotIn('voltage_adapt',contract['required_policy_settings'])
    models.assign_model(ID,'walk',b,cfg,cal)
    for n,v in policy.items():
     if n!='walk':self.assertEqual(tomllib.loads(cfg.read_text())['policy'][n],v)

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

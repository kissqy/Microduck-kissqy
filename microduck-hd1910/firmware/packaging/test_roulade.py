"""Original roll import, safe metadata, persisted bindings, real load readback."""
import copy,hashlib,json,shutil,tempfile,tomllib,unittest
from pathlib import Path
import model_packages as models
from configure import dumps
ROOT=Path(__file__).resolve().parents[1]
ROLL='8fdaf12c7478a8314a63647a466bfa34'
class RouladeTests(unittest.TestCase):
 def test_original_model_contract_and_manifest_skill(self):
  info=models.verify_directory(ROOT/'policies/roulade')
  self.assertEqual(info['id'],ROLL);self.assertEqual(info['slot'],'roulade');self.assertEqual(info['contract']['task'],'Mjlab-Roulade-Flat-MicroDuck')
  self.assertEqual(info['contract']['task_adapter'],'hd1910-official0151');self.assertEqual(info['skill']['params']['action_scale'],1.0);self.assertEqual(info['skill']['duration'],1.0);self.assertTrue(info['skill']['chain'])
  for rel in ('packaging/robotd-profile.toml','config/robotd-selftrained.toml'):
   config=tomllib.loads((ROOT/rel).read_text());self.assertIn(ROLL,config['policy']['roulade']);self.assertEqual(config['pad']['x'],'roulade');self.assertEqual(config['policy']['skill'][0],info['skill'])
   self.assertEqual(config['policy']['action_scale'],.7);self.assertNotIn('head_lowpass',config['policy']);self.assertNotIn('legs_lowpass',config['policy']);self.assertFalse(config['safety']['limp_fall'])
 def test_selection_persists_skill_and_binding_without_overwriting_global_settings_or_calibration(self):
  with tempfile.TemporaryDirectory() as temp:
   base=Path(temp);directory=base/'models'/ROLL;directory.parent.mkdir();shutil.copytree(ROOT/'policies/roulade',directory)
   cfg=base/'robotd.toml';cal=base/'calibration.toml';cal.write_bytes((ROOT/'packaging/hd1910-calibration.robot.toml').read_bytes());cal_before=cal.read_bytes()
   original={'policy':{'action_scale':.65,'r17_inference_scale':.7,'head_lowpass':.5,'legs_lowpass':.7,'voltage_adapt':True,'skill':[{'name':'another','duration':2.0}]},'pad':{'a':'ground_pick','dpad_down':'sit_toggle','x':''}}
   cfg.write_text(dumps(original));models.assign_model(ROLL,'roulade',base,cfg,cal)
   selected=tomllib.loads(cfg.read_text());self.assertEqual(selected['policy']['action_scale'],.65);self.assertEqual(selected['policy']['head_lowpass'],.5);self.assertEqual(selected['policy']['legs_lowpass'],.7);self.assertTrue(selected['policy']['voltage_adapt']);self.assertNotIn('r17_inference_scale',selected['policy']);self.assertEqual(selected['pad']['x'],'roulade');self.assertEqual(selected['pad']['dpad_down'],'sit_toggle');self.assertEqual(len(selected['policy']['skill']),2)
   self.assertEqual(cal.read_bytes(),cal_before);self.assertEqual(cfg.read_bytes(),cfg.with_name('robotd.saved.toml').read_bytes())
   models.assign_model(ROLL,'roulade',base,cfg,cal);self.assertEqual(tomllib.loads(cfg.read_text()),selected)
 def test_unsupported_skill_window_is_rejected_before_install(self):
  files={name:(ROOT/'policies/roulade'/name).read_bytes() for name in models.EXPORT_FILES}
  for bad in ({'duration_s':0},{'chain':'true'},{'action_scale':float('nan')},{'kind':'perpetual'},{'command':{'encoding':'phase'}}):
   manifest=json.loads(files['manifest.json']);manifest.update(bad);changed={**files,'manifest.json':json.dumps(manifest).encode()}
   with self.assertRaises(ValueError):models.validate_export(changed)
if __name__=='__main__':unittest.main()

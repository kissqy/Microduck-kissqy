"""Original roll import, safe metadata, persisted bindings, real load readback."""
import copy,hashlib,json,shutil,tempfile,tomllib,unittest
from pathlib import Path
import model_packages as models
from configure import dumps
ROOT=Path(__file__).resolve().parents[1]
ROLL='59e15d7b04d0c40e9b11b8a70bdecae6'
class RouladeTests(unittest.TestCase):
 def test_original_model_contract_and_manifest_skill(self):
  info=models.verify_directory(ROOT/'policies/roulade')
  self.assertEqual(info['id'],ROLL);self.assertEqual(info['slot'],'roulade');self.assertEqual(info['contract']['task'],'Mjlab-Roulade-Flat-MicroDuck')
  self.assertEqual(info['contract']['task_adapter'],'hd1910-official0151');self.assertEqual(info['skill']['params']['action_scale'],1.0);self.assertEqual(info['skill']['duration'],1.0);self.assertTrue(info['skill']['chain'])
  for rel in ('packaging/robotd-profile.toml','config/robotd-selftrained.toml'):
   config=tomllib.loads((ROOT/rel).read_text());self.assertIn(ROLL,config['policy']['roulade']);self.assertEqual(config['pad']['x'],'roulade');self.assertEqual(config['policy']['skill'][0],info['skill'])
   self.assertEqual(config['policy']['action_scale'],.7);self.assertNotIn('head_lowpass',config['policy']);self.assertNotIn('legs_lowpass',config['policy']);self.assertFalse(config['safety']['limp_fall'])
 def test_unsupported_skill_window_is_rejected_before_install(self):
  files={name:(ROOT/'policies/roulade'/name).read_bytes() for name in models.EXPORT_FILES}
  for bad in ({'duration_s':0},{'chain':'true'},{'action_scale':float('nan')},{'kind':'perpetual'},{'command':{'encoding':'phase'}}):
   manifest=json.loads(files['manifest.json']);manifest.update(bad);changed={**files,'manifest.json':json.dumps(manifest).encode()}
   with self.assertRaises(ValueError):models.validate_export(changed)
if __name__=='__main__':unittest.main()

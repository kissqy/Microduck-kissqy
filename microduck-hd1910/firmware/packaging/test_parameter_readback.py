"""Applying numeric settings and listing installed models must not reparse training YAML."""
import json,shutil,tempfile,time,tomllib,unittest
from pathlib import Path
from unittest.mock import patch
import runtime,model_packages as models
from configure import dumps
ROOT=Path(__file__).resolve().parents[1]

class ParameterReadbackTests(unittest.TestCase):
 def installed(self,base):
  policy={'action_scale':.7,'stand':'none','head_lowpass':.5,'legs_lowpass':.7}
  for slot in ('walk','sitstand','ground_pick','roulade','stand'):
   src=ROOT/'policies'/slot
   ident=json.loads((src/'manifest.json').read_text())['onnx_sha256'][:32]
   dest=base/'models'/ident;shutil.copytree(src,dest)
   policy['stand_test' if slot=='stand' else slot]=str(dest/'policy.onnx')
  cfg=base/'robotd.toml';cfg.write_text(dumps({'policy':policy,'pad':{'lb':'stand_test'}}))
  return cfg,Path(policy['walk']).parent.name
 def test_actual_apply_then_list_returns_changed_values_without_model_derivation(self):
  with tempfile.TemporaryDirectory() as t:
   base=Path(t);cfg,ident=self.installed(base)
   weights={p:p.read_bytes() for p in (base/'models').glob('*/policy.onnx')}
   original_read_bytes=Path.read_bytes
   def read_bytes(path):
    if path.name=='policy.onnx' or path.suffix=='.yaml':raise AssertionError('parameter read reparsed model/training data')
    return original_read_bytes(path)
   with patch.object(runtime,'BASE',base),patch.object(runtime,'CONFIG',cfg),patch.object(runtime,'detect_port',return_value='/dev/ttyS2'),patch.object(Path,'read_bytes',read_bytes),patch.object(models,'verify_directory',side_effect=AssertionError('numeric apply revalidates models')):
    before=runtime.model_list();self.assertIsNone(before['servo_parameters'])
    runtime.set_action_scale(ident,.63,3,50,681)
    after=runtime.model_list()
    self.assertEqual(after['servo_parameters'],{'kp':3,'kd':50,'torque_limit':681})
    self.assertEqual(after['action_scale'],.63)
    self.assertEqual(after['configured_model'],ident)
    self.assertEqual(len(after['models']),5);self.assertTrue(all(r['available'] for r in after['models']))
    self.assertEqual([r['id'] for r in after['models'] if r['slot']=='walk'],[ident])
    self.assertEqual(ident,'1cbf8730eadd75a5704332c9f3c10f60')
    self.assertNotIn('9e3ff8bde021be28a728c02dbd8e7aaf',[r['id'] for r in after['models']])
    runtime.set_action_scale(ident,.7,3,0,681)
    again=runtime.model_list();self.assertEqual(again['servo_parameters']['kd'],0)
   self.assertEqual(cfg.read_bytes(),cfg.with_name('robotd.saved.toml').read_bytes())
   self.assertEqual(tomllib.loads(cfg.read_text())['policy']['head_lowpass'],.5)
   self.assertEqual(tomllib.loads(cfg.read_text())['policy']['legs_lowpass'],.7)
   self.assertTrue(all(p.read_bytes()==v for p,v in weights.items()))
   self.assertEqual(cfg.with_name('servo-test-parameters.json').stat().st_mode&0o777,0o644)
 def test_listing_is_read_only_and_missing_metadata_or_weights_are_reported(self):
  with tempfile.TemporaryDirectory() as t:
   base=Path(t);cfg,ident=self.installed(base)
   before={p:p.read_bytes() for p in base.rglob('*') if p.is_file()}
   models.catalog(base,cfg)
   self.assertEqual(before,{p:p.read_bytes() for p in base.rglob('*') if p.is_file()})
   (base/'models'/ident/'policy.onnx').unlink()
   row=next(r for r in models.catalog(base,cfg)['models'] if r['id']==ident)
   self.assertFalse(row['available']);self.assertIn('模型文件不存在',row['error'])
   (base/'models'/ident/'manifest.json').write_text('{invalid')
   self.assertFalse(next(r for r in models.catalog(base,cfg)['models'] if r['id']==ident)['available'])
if __name__=='__main__':unittest.main()

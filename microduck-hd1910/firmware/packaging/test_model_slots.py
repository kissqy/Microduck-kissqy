"""Official slot imports must replace only the chosen, contract-compatible action."""
import io,json,shutil,tempfile,time,tomllib,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
import model_packages as models,runtime
from configure import dumps
from service_control import ServiceController,ControlError,validate
ROOT=Path(__file__).resolve().parents[1]
class SlotTests(unittest.TestCase):
 def test_lb_binding_is_explicit_and_separate_from_automatic_stand(self):
  with tempfile.TemporaryDirectory() as t:
   b=Path(t);cfg=b/'robotd.toml';ident=json.loads((ROOT/'policies/stand/model-info.json').read_text())['id'];directory=b/'models'/ident
   shutil.copytree(ROOT/'policies/stand',directory)
   cfg.write_text(dumps({'policy':{'stand':'none','skill':[{'name':'stand_test','path':str(directory/'policy.onnx'),'params':{'action_scale':1.0}}]},'pad':{'lb':'stand_test'}}))
   data=models.catalog(b,cfg);model=data['manual_recovery']['model']
   self.assertEqual(model['id'],ident);self.assertIn('11000',model['name']);self.assertTrue(model['available'])
   self.assertFalse(model['active']);self.assertEqual(model['skill_bindings'],[{'name':'stand_test','buttons':['lb'],'action_scale':1.0}])
   self.assertIsNone(next(row for row in data['slots'] if row['slot']=='stand')['model'])
   (directory/'deployment-contract.json').write_bytes(b'')
   data=models.catalog(b,cfg);model=data['manual_recovery']['model']
   self.assertEqual(model['id'],ident);self.assertFalse(model['available']);self.assertIn('Expecting value',model['error'])
   self.assertEqual(model['skill_bindings'][0]['buttons'],['lb'])

 def package(self,base,slot):
  path=base/(slot+'.zip')
  with zipfile.ZipFile(path,'w') as z:
   for name in (*models.EXPORT_FILES,*models.PARAM_FILES):
    src=ROOT/'policies'/slot/name
    if src.exists():z.write(src,name)
  return path
 def test_all_seven_official_actions_including_empty_are_explicit(self):
  with tempfile.TemporaryDirectory() as t:
   b=Path(t);(b/'models').mkdir();cfg=b/'robotd.toml';cfg.write_text('[policy]\n')
   data=models.catalog(b,cfg)
   self.assertEqual([r['slot'] for r in data['slots']],list(models.SLOTS))
   self.assertTrue(all(r['model'] is None and ' / ' in r['label'] for r in data['slots']))
 def test_real_exports_import_and_replace_only_the_selected_slot(self):
  with tempfile.TemporaryDirectory() as t:
   b=Path(t);cfg=b/'robotd.toml';cal=b/'calibration.toml';cal.write_bytes((ROOT/'packaging/hd1910-calibration.robot.toml').read_bytes());original_cal=cal.read_bytes()
   initial={'policy':{'action_scale':.65,'head_lowpass':1.,'legs_lowpass':1.,'walk':'none','sitstand':'none','stand':'none','ground_pick':'none','roulade':'none'},'pad':{'dpad_down':'sit_toggle','a':'ground_pick'}}
   cfg.write_text(dumps(initial))
   for slot in ('walk','sitstand','ground_pick','roulade'):
    archive=self.package(b,slot);before=tomllib.loads(cfg.read_text())
    result=models.import_package(archive,archive.name,b,cfg,cal,validator=False,target_slot=slot)
    models.assign_model(result['id'],slot,b,cfg,cal)
    after=tomllib.loads(cfg.read_text());self.assertEqual(after['policy'][slot],str(b/'models'/result['id']/'policy.onnx'))
    for key,value in before['policy'].items():
     if key not in (slot,'skill'):self.assertEqual(after['policy'][key],value)
    self.assertEqual(cfg.read_bytes(),cfg.with_name('robotd.saved.toml').read_bytes());self.assertEqual(cal.read_bytes(),original_cal)
    listing=models.catalog(b,cfg);self.assertEqual(next(r for r in listing['slots'] if r['slot']==slot)['model']['id'],result['id'])
    # Reimporting the same ZIP remains an explicit successful replacement.
    repeated=models.import_package(archive,archive.name,b,cfg,cal,validator=False,target_slot=slot);self.assertTrue(repeated['duplicate'])
 def test_wrong_action_is_rejected_before_install_or_binding(self):
  with tempfile.TemporaryDirectory() as t:
   b=Path(t);cfg=b/'robotd.toml';cfg.write_text('[policy]\naction_scale=0.65\n');raw=cfg.read_bytes();archive=self.package(b,'walk')
   with self.assertRaisesRegex(ValueError,'不一致'):models.import_package(archive,archive.name,b,cfg,b/'none',validator=False,target_slot='sitstand')
   self.assertFalse((b/'models').exists());self.assertEqual(cfg.read_bytes(),raw)
   info=models.verify_directory(ROOT/'policies/walk');shutil.copytree(ROOT/'policies/walk',b/'models'/info['id'])
   with self.assertRaisesRegex(ValueError,'不一致'):models.assign_model(info['id'],'roulade',b,cfg,b/'none')
   self.assertEqual(cfg.read_bytes(),raw)
 def test_actual_slot_hash_is_required_for_assignment_readback(self):
  with tempfile.TemporaryDirectory() as t:
   b=Path(t);cfg=b/'robotd.toml';info=models.verify_directory(ROOT/'policies/walk');shutil.copytree(ROOT/'policies/walk',b/'models'/info['id'])
   cfg.write_text(dumps({'policy':{}}));models.assign_model(info['id'],'walk',b,cfg,b/'none')
   bus={'build':runtime.BUILD,'mode':'motion','loaded_models':{'walk':{'sha256':info['sha256']}}}
   with patch.object(runtime,'BASE',b),patch.object(runtime,'CONFIG',cfg):
    with patch.object(runtime,'rpc',return_value=bus):self.assertTrue(runtime.model_assignment(info['id'],'walk')['model_assignment']['running_verified'])
    with patch.object(runtime,'rpc',return_value={**bus,'loaded_models':{'walk':{'sha256':'old'}}}):
     with self.assertRaisesRegex(ValueError,'哈希'):runtime.model_assignment(info['id'],'walk')
    with patch.object(runtime,'rpc',return_value={**bus,'mode':'commissioning'}):self.assertFalse(runtime.model_assignment(info['id'],'walk')['model_assignment']['running_verified'])
 def test_import_waits_for_assignment_and_input_confirmation(self):
  class Store:
   service_operation=False
   def snapshot(self):return {'bus':{'build':runtime.BUILD}}
   def record_service_command(self,job):pass
  class Input:
   def reconnect_after_service(self):return {'webpad_reconnected':True}
  for matched in (True,False):
   class Transport:
    def import_model(self,name,stream,size,password,slot):return {'model_assignment':{'slot':slot if matched else 'roulade','saved_verified':True,'running_verified':True,'mode':'motion'}}
   store=Store();service=ServiceController(store,transport=Transport(),controls=Input())
   if matched:
    response=service.import_model('new.zip',io.BytesIO(b'x'),1,slot='walk')
    self.assertEqual(response['operation']['status'],'completed')
    deadline=time.monotonic()+2
    while service.job['result']['input'].get('status')!='ready' and time.monotonic()<deadline:time.sleep(.01)
    self.assertTrue(service.job['result']['input']['webpad_reconnected'])
   else:
    with self.assertRaises(ControlError):service.import_model('new.zip',io.BytesIO(b'x'),1,slot='walk')
   self.assertEqual(service.job['status'],'completed' if matched else 'error');self.assertFalse(store.service_operation)
 def test_retired_selection_api_and_invalid_slot_cannot_dispatch(self):
  with self.assertRaises(ControlError):validate({'action':'select-model','model':'a'*32,'supported':True})
  with self.assertRaises(ControlError):ServiceController(object(),transport=object()).import_model('a.zip',io.BytesIO(b'x'),1,slot='walk; shutdown')
if __name__=='__main__':unittest.main()

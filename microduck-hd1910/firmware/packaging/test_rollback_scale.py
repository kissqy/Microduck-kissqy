"""Rollback staging and scale persistence; no hardware or real systemd."""
import importlib.util,json,subprocess,sys,tempfile,tomllib,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
CURRENT_WALK='1cbf8730eadd75a5704332c9f3c10f60'
sys.path.insert(0,str(ROOT/'console'))
import runtime
from configure import dumps
from service_control import validate,ControlError,ServiceController

def load(name):
    spec=importlib.util.spec_from_file_location(name.replace('-','_'),ROOT/'packaging'/name)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

class RollbackScaleTests(unittest.TestCase):
    def test_scale_is_persisted_without_changing_model_or_calibration(self):
        with tempfile.TemporaryDirectory() as t:
            config=Path(t)/'robotd.toml';cal=Path(t)/'calibration.toml'
            data=tomllib.loads((ROOT/'packaging/robotd-profile.toml').read_text());data['policy']['r17_inference_scale']=0.7;config.write_text(dumps(data));cal.write_bytes(b'current mounted calibration')
            old_models={k:data['policy'][k] for k in ('walk','stand','sitstand','ground_pick')}
            with patch.object(runtime,'CONFIG',config),patch('model_packages.verify_directory',return_value={}):
                result=runtime.set_action_scale(CURRENT_WALK,'0.6',3,0,681)
                self.assertEqual(result['action_scale'],0.6);self.assertNotIn('r17_inference_scale',result)
                self.assertEqual(tomllib.loads(config.read_text())['policy']['action_scale'],0.6)
                result=runtime.set_action_scale('1c94934c6421ec72ed48079cea749668','0.9',3,0,681)
                self.assertEqual(result['sitstand_base_action_scale'],1.0)
                runtime.set_action_scale(CURRENT_WALK,'0.65',3,0,681)
                self.assertEqual(tomllib.loads(config.read_text())['policy']['action_scale'],0.65)
                for value in ('nan','inf','0','1.1','0.651'):
                    before=config.read_bytes()
                    with self.assertRaises(ValueError):runtime.set_action_scale(CURRENT_WALK,value,3,0,681)
                    self.assertEqual(config.read_bytes(),before)
            result=tomllib.loads(config.read_text());self.assertNotIn('r17_inference_scale',result['policy']);self.assertEqual(result['policy']['action_scale'],0.65)
            self.assertNotIn('head_lowpass',result['policy']);self.assertNotIn('legs_lowpass',result['policy'])
            self.assertEqual({k:result['policy'][k] for k in old_models},old_models)
            self.assertEqual(config.read_bytes(),config.with_name('robotd.saved.toml').read_bytes());self.assertEqual(cal.read_bytes(),b'current mounted calibration')
    def test_console_validates_and_dispatches_scaling(self):
        self.assertEqual(validate({'action':'set-action-scale','model':'9e3ff8bde021be28a728c02dbd8e7aaf','scale':0.7,'supported':True,'kp':3,'kd':0,'torque_limit':681})['scale'],0.7)
        self.assertEqual(validate({'action':'set-action-scale','model':'9e3ff8bde021be28a728c02dbd8e7aaf','scale':0.65,'supported':True,'kp':3,'kd':0,'torque_limit':681})['scale'],0.65)
        for value in (True,float('nan'),0,1.1,0.651):
            with self.assertRaises(ControlError):validate({'action':'set-action-scale','model':'9e3ff8bde021be28a728c02dbd8e7aaf','scale':value,'supported':True,'kp':3,'kd':0,'torque_limit':681})
        class Store:
            service_operation=True
            def record_service_command(self,job):pass
        class Transport:
            def __init__(self):self.calls=[]
            def manage(self,*args,**kwargs):self.calls.append((args,kwargs));return {'action_scale':0.7}
        transport=Transport();c=ServiceController(Store(),transport=transport);job={'action':'set-action-scale','status':'running'}
        c._execute({'action':'set-action-scale','model':'9e3ff8bde021be28a728c02dbd8e7aaf','scale':0.7,'supported':True,'kp':3,'kd':0,'torque_limit':681},job,0)
        self.assertEqual(job['status'],'completed');self.assertEqual(transport.calls[0][0],('action-scale','9e3ff8bde021be28a728c02dbd8e7aaf','0.7','3','0','681'))
        self.assertFalse(c.store.service_operation)
    def test_current_reassembled_calibration_is_kept_including_saved_copy(self):
        with tempfile.TemporaryDirectory() as t:
            original=Path(t)/'mounted.toml';active=Path(t)/'calibration.toml'
            data=tomllib.loads((ROOT/'packaging/hd1910-calibration.training.toml').read_text())
            next(j for j in data['joints'] if j['id']==33)['zero_raw']=1599
            original.write_text(dumps(data));raw=original.read_bytes()
            subprocess.run([sys.executable,str(ROOT/'packaging/calibration-config.py'),'copy',str(original),'--output',str(active)],check=True,capture_output=True)
            self.assertEqual(active.read_bytes(),raw);self.assertEqual(active.with_name('calibration.saved.toml').read_bytes(),raw)
            recovery=load('rebuild-config.py');self.assertEqual(recovery.source_data(active,'calibration',ROOT/'packaging'),data)
    def test_replacement_rebinds_all_old_model_slots_and_scale(self):
        with tempfile.TemporaryDirectory() as t:
            old=Path(t)/'old.toml';new=Path(t)/'new.toml'
            old.write_text('[policy]\nwalk="/new/model.onnx"\nstand="none"\nsitstand="none"\nground_pick="none"\n')
            subprocess.run([sys.executable,str(ROOT/'packaging/configure.py'),'--source',str(old),'--replace-models','--overrides',str(ROOT/'packaging/robotd-profile.toml'),'--output',str(new)],check=True,capture_output=True)
            p=tomllib.loads(new.read_text())['policy'];self.assertEqual(p['action_scale'],0.7)
            for slot,ident in {'walk':CURRENT_WALK,'sitstand':'1c94934c6421ec72ed48079cea749668'}.items():self.assertIn('/'+ident+'/',p[slot])

            self.assertEqual(p['stand'],'none')
            self.assertIn('2b69fa681ed06f7ded9e2a2d12ba5c67',p['ground_pick'])
            # Exercise the installer merge from a previously shipped bad binding:
            # the model slot is sitstand, but the daemon's built-in action is sit_toggle.
            old.write_text(old.read_text()+'[pad]\ndpad_down="sitstand"\n')
            subprocess.run([sys.executable,str(ROOT/'packaging/configure.py'),'--source',str(old),'--replace-models','--overrides',str(ROOT/'packaging/robotd-profile.toml'),'--output',str(new)],check=True,capture_output=True)
            self.assertEqual(tomllib.loads(new.read_text())['pad']['dpad_down'],'sit_toggle')
            reference=tomllib.loads((ROOT/'config/robotd-selftrained.toml').read_text())
            self.assertEqual(reference['pad']['dpad_down'],'sit_toggle')

    def test_cleanup_removes_retired_models_and_preserves_current_and_unrelated_models(self):
        with tempfile.TemporaryDirectory() as t:
            bundle=Path(t)/'bundle';installed=Path(t)/'installed';bundle.mkdir();installed.mkdir()
            profile=json.loads((ROOT/'config/r17-management.json').read_text())
            retired=profile['retired_model_ids']
            self.assertIn('9e3ff8bde021be28a728c02dbd8e7aaf',retired)
            keep=(CURRENT_WALK,'1c94934c6421ec72ed48079cea749668')
            unrelated=('alpha_walking','12345678901234567890123456789012')
            names=(*retired,*keep,*unrelated)
            (bundle/'management-profile.json').write_text(json.dumps(profile))
            (bundle/'install-files.json').write_text(json.dumps(['models/'+n+'/policy.onnx' for n in keep]))
            for name in names:
                d=installed/'models'/name;d.mkdir(parents=True);(d/'policy.onnx').write_bytes(b'weight')
            load('install-files.py').cleanup(bundle,installed,replace_models=False)
            for name in retired:self.assertFalse((installed/'models'/name).exists())
            for name in (*keep,*unrelated):self.assertTrue((installed/'models'/name/'policy.onnx').exists())

if __name__=='__main__':unittest.main()

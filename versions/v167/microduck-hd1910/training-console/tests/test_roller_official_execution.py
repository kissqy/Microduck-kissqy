"""Frozen upstream 0.15.1 train/inference split for six roller families."""
import copy
import json
import tempfile
import tomllib
import unittest
from pathlib import Path
from training.deployment import deployment_contract, manifest_for, write_sidecars
from training.official_spec import TASKS, ROLLER_ROLES

ROOT=Path(__file__).resolve().parents[1]

class RollerOfficialExecutionTests(unittest.TestCase):
    def test_six_roles_ten_variants_keep_training_scale_one(self):
        configs={}
        for task, spec in TASKS.items():
            if spec['role'] not in ROLLER_ROLES:continue
            actual=json.loads((ROOT/'data/task-configs'/(task+'.json')).read_text())['inspection']
            assert actual['full']['env']['actions']['joint_pos']['scale']==1.0
            self.assertFalse('head_alpha' in actual['full']['env']['actions']['joint_pos'])
            self.assertFalse('legs_alpha' in actual['full']['env']['actions']['joint_pos'])
            configs[task]=(spec,actual)
        self.assertEqual(len(configs),10)
        self.assertEqual(set(x['role'] for x,_ in configs.values()),set(ROLLER_ROLES))

    def test_only_published_two_have_official_inference_presets(self):
        for task, spec in TASKS.items():
            if spec['role'] not in ROLLER_ROLES:continue
            actual=json.loads((ROOT/'data/task-configs'/(task+'.json')).read_text())['inspection']
            c=deployment_contract({'task':task,'source_training_snapshot':actual},actual)
            expected=.8 if spec['role'] in ('roller','crouch') else 1.0
            key='ground_pick_action_scale' if spec['role'] in ('crouch','spin') else 'action_scale'
            if spec['role'] == 'roller_stand':key=None
            if key:self.assertEqual(c['required_policy_settings'][key],expected,task)
            self.assertEqual(c['runtime_action_scale'],expected,task)
            self.assertEqual(c['trained_action_scale'],1.,task)
            self.assertEqual(manifest_for({'task':task},c,'f'*64)['action_scale'],expected,task)
            if spec['role'] in ('roller','crouch'):
                self.assertEqual(c['required_policy_settings']['head_lowpass'],.5)
                self.assertEqual(c['required_policy_settings']['legs_lowpass'],.7)
                self.assertFalse(c['action_filter']['enabled'])
                self.assertIsNotNone(c['runtime_execution_preset'])
            else:
                self.assertIsNone(c['runtime_execution_preset'])
                self.assertEqual(c['required_policy_settings']['head_lowpass'],1.0)
                self.assertEqual(c['required_policy_settings']['legs_lowpass'],1.0)

    def test_actual_deployment_sidecar_separates_train_and_inference(self):
        for role in ('roller','crouch'):
            task=next(t for t,s in TASKS.items() if s['role']==role and not s['backlash'])
            actual=json.loads((ROOT/'data/task-configs'/(task+'.json')).read_text())['inspection']
            contract=deployment_contract({'task':task,'source_training_snapshot':actual},actual)
            with tempfile.TemporaryDirectory() as tmp:
                onnx=Path(tmp)/'policy.onnx'; onnx.write_bytes(b'fake-graph-sidecar-only')
                write_sidecars(onnx,{'task':task},contract)
                man=json.loads(onnx.with_suffix('.manifest.json').read_text())
                old=json.loads(onnx.with_suffix('.training.json').read_text())
                policy=tomllib.loads(onnx.with_suffix('.deployment.toml').read_text())['policy']
                self.assertEqual(old['full']['env']['actions']['joint_pos']['scale'],1.0)
                self.assertEqual(man['trained_action_scale'],1.0)
                self.assertEqual(man['action_scale'],0.8)
                self.assertEqual(policy['action_scale' if role=='roller' else 'ground_pick_action_scale'],0.8)
                self.assertEqual(policy['head_lowpass'],0.5)
                self.assertEqual(policy['legs_lowpass'],0.7)
                self.assertEqual(man['mode'],'roller')

    def test_legacy_non_one_scale_retained(self):
        for role in ('roller','crouch'):
            task=next(t for t,s in TASKS.items() if s['role']==role and not s['backlash'])
            data=json.loads((ROOT/'data/task-configs'/(task+'.json')).read_text())['inspection']
            data['full']['env']['actions']['joint_pos']['scale']=.7
            c=deployment_contract({'task':task,'source_training_snapshot':data},copy.deepcopy(data))
            self.assertEqual(c['runtime_action_scale'],.7)
            self.assertIsNone(c['runtime_execution_preset'])
            self.assertEqual(c['required_policy_settings']['head_lowpass'],1.0)
            self.assertEqual(c['required_policy_settings']['legs_lowpass'],1.0)

if __name__=='__main__': unittest.main()

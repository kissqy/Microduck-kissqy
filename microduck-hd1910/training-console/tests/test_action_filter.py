"""Filter provenance, legacy compatibility and deployment regression tests."""
import ast
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import training_console as tc
from training import action_filter as af
from training.deployment import deployment_contract, write_sidecars
from training.official_spec import WALK, STAND, JOINT, TASKS, new_training_action_scale, contract, compare_contracts

ROOT = Path(__file__).resolve().parents[1]
TRIAL = {'enabled': True, 'head_alpha': .5, 'legs_alpha': .7, 'version': 1}


def inspection(task=WALK, filtered=False):
    result = json.loads((ROOT/'data/task-configs'/(task+'.json')).read_text())['inspection']
    if filtered:
        result['full']['env']['actions']['joint_pos'].update(head_alpha=.5, legs_alpha=.7, filter_version=1)
    return result


class ActionFilterContractTests(unittest.TestCase):
    def test_legacy_missing_settings_do_not_acquire_new_filter(self):
        self.assertFalse(af.validate()['enabled'])
        c = deployment_contract({'task': WALK, 'action_filter': TRIAL}, inspection())
        self.assertFalse(c['action_filter']['enabled'])
        self.assertEqual(c['required_policy_settings']['head_lowpass'], 1)

    def test_validation_rejects_nonfinite_zero_and_unsupported_values(self):
        for value in (0, -.5, 1.1, float('nan'), float('inf'), True, '0.5'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                af.validate({**TRIAL, 'head_alpha': value})
        with self.assertRaises(ValueError): af.validate({**TRIAL, 'version': 2})
        with self.assertRaises(ValueError): af.validate({'enabled': 'yes'})

    def test_request_validation_keeps_new_filter_and_legacy_passthrough(self):
        self.assertEqual(tc.validate_parameters({'task': WALK, 'action_filter': TRIAL}, {'tasks': [WALK]})['action_filter'], TRIAL)
        self.assertFalse(tc.validate_parameters({'task': WALK}, {'tasks': [WALK]})['action_filter']['enabled'])
        self.assertIn('action_filter', tc.PARAMETER_KEYS)

    def test_selected_scale_reaches_new_training_request(self):
        self.assertEqual(tc.validate_parameters({'task': WALK}, {'tasks': [WALK]})['training_action_scale'], .9)
        for scale in (.7, .9, 1.0):
            with self.subTest(scale=scale), tempfile.TemporaryDirectory() as d:
                manager=tc.BaseTrainingManager(Path(d))
                manager.environment={'ready':True,'revision':'fixture-revision','tasks':[WALK],'configs':{}}
                with patch.object(tc.BaseTrainingManager,'_run'):
                    job=manager.jobs[manager.launch('train',{'task':WALK,'training_action_scale':scale,'action_filter':TRIAL})['job_id']]
                    self.assertEqual(job['request']['training_action_scale'],scale)
                manager.close()
        for scale in (0, True, '0.9', float('nan'), float('inf'), 2.1):
            with self.subTest(scale=scale), self.assertRaises(ValueError):
                tc.validate_parameters({'task':WALK,'training_action_scale':scale},{'tasks':[WALK]})

    def test_resolved_filter_controls_export_not_mutable_request(self):
        c = deployment_contract({'task': WALK, 'action_filter': af.validate()}, inspection(filtered=True))
        self.assertEqual(c['required_policy_settings']['action_scale'], 1)
        self.assertEqual(c['required_policy_settings']['head_lowpass'], .5)
        self.assertEqual(c['required_policy_settings']['legs_lowpass'], .7)
        self.assertNotIn('voltage_adapt', c['required_policy_settings'])
        self.assertEqual(c['previous_action_observation'], 'raw_policy_output_before_scaling_and_filtering')
        self.assertEqual(c['action_filter']['reset'], 'first_target_passthrough_per_environment')
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'policy.onnx'; p.write_bytes(b'test-not-a-real-onnx')
            write_sidecars(p, {'task': WALK}, c)
            profile = p.with_suffix('.deployment.toml').read_text()
            self.assertIn('head_lowpass = 0.5', profile)
            self.assertIn('legs_lowpass = 0.7', profile)
            manifest = json.loads(p.with_suffix('.manifest.json').read_text())
            self.assertEqual(manifest['action_filter'], c['action_filter'])

    def test_task_scales_and_profiles_do_not_change_unrelated_runtime_branches(self):
        keys={'walk':'action_scale','stand':'action_scale','joint':'action_scale',
              'ground_pick':'ground_pick_action_scale','roulade':'roulade_action_scale',
              'kick_right':'standing_action_scale','kick_left':'standing_action_scale',
              'roller':'action_scale','crouch':'ground_pick_action_scale','sitstand':None}
        for task,info in TASKS.items():
            resolved=inspection(task,True)
            expected=new_training_action_scale(task)
            resolved['full']['env']['actions']['joint_pos']['scale']=expected
            c=deployment_contract({'task':task},resolved)
            required=c['required_policy_settings']
            key=keys[info['role']]
            for other in ('action_scale','standing_action_scale','ground_pick_action_scale','roulade_action_scale'):
                if other==key:self.assertEqual(required[other],expected)
                else:self.assertNotIn(other,required)
            self.assertEqual(c['trained_action_scale'],expected)
            from training.deployment import manifest_for
            self.assertEqual(manifest_for({'task':task},c,'fixture')['action_scale'],expected)

    def test_joint_teachers_must_match_filter_semantics(self):
        target = contract(inspection(JOINT, True))
        for task in (WALK, STAND):
            compare_contracts(contract(inspection(task, True)), target)
            with self.assertRaisesRegex(ValueError, '动作滤波不同'):
                compare_contracts(contract(inspection(task)), target)
        compare_contracts(contract(inspection(WALK)), contract(inspection(JOINT)))

    def test_play_export_and_resume_use_saved_filter_even_when_page_differs(self):
        for source_filter in (TRIAL, af.validate()):
            for op in ('play', 'export', 'train'):
                with self.subTest(source_filter=source_filter, op=op), tempfile.TemporaryDirectory() as d:
                    manager=tc.BaseTrainingManager(Path(d))
                    manager.environment={'ready':True,'revision':'fixture-revision','tasks':[WALK],'configs':{}}
                    with patch.object(tc.BaseTrainingManager,'_run'):
                        source=manager.jobs[manager.launch('train',{'task':WALK,'action_filter':source_filter})['job_id']]
                        source['request']['training_action_scale']=1.0  # Saved R1.5.7 or earlier model.
                        source.update(status='completed',revision='fixture-revision',checkpoints=[{'path':'/fixture/model_1000.pt','iteration':1000}])
                        source['effective_config']={'action_filter':source_filter,'training_action_scale':1.0}
                        page_filter=af.validate() if source_filter['enabled'] else TRIAL
                        job=manager.jobs[manager.launch(op,{'task':WALK,'source_job':source['id'],
                                      'checkpoint':'/fixture/model_1000.pt','action_filter':page_filter})['job_id']]
                        self.assertEqual(job['request']['policy_parameters']['action_filter'],source_filter)
                        self.assertEqual(job['request']['policy_parameters']['training_action_scale'],1.0)
                        if op=='train':
                            self.assertEqual(job['request']['action_filter'],source_filter)
                            self.assertEqual(job['request']['training_action_scale'],1.0)
                    manager.close()

    def test_remote_and_durable_worker_bundles_contain_filter_implementation(self):
        from training.durable_manager import monitor_payload
        req = {'op': 'train', 'task': WALK, 'action_filter': TRIAL}
        payload = monitor_payload({'id': 'fixture', 'request': req}, create=True).decode()
        first_line=payload.splitlines()[0]
        request=ast.literal_eval(first_line.split(" = ",1)[1])
        bundle_line=request["source"].splitlines()[1]
        bundle=ast.literal_eval(bundle_line.split(" = ",1)[1])
        self.assertIn("filtered_actions.py", bundle)
        self.assertIn('once_per_policy_step', payload)
        self.assertIn('first_target_passthrough_per_environment', payload)


if __name__ == '__main__': unittest.main()

"""Recovery evaluation launch guards and model-bound configuration, no trainer."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import training_console as tc
from training.official_spec import ENGINE, REVISION, TASKS, STAND, WALK


class RecoveryLaunchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.worker = patch.object(tc.BaseTrainingManager, '_run')
        self.worker.start()
        self.addCleanup(self.worker.stop)
        self.manager = tc.TrainingManager(Path(self.tmp.name))
        self.addCleanup(self.manager.close)
        self.manager.computer_verified = True
        self.manager.environment = {'ready': True, 'revision': REVISION,
                                    'engine': ENGINE, 'tasks': list(TASKS), 'configs': {}}

    def model(self, task=STAND):
        value = {'task': task, 'training_action_scale': 1.0, 'training_firmware_p': 5,
                 'action_filter': {'enabled': True, 'head_alpha': 1.0, 'legs_alpha': 1.0}}
        job = self.manager.jobs[self.manager.launch('train', value)['job_id']]
        job.update(status='completed', revision=REVISION, checkpoints=[{'path': '/fixture/model_11000.pt',
                                                     'iteration': 11000}])
        job['effective_config'] = {'resolved': json.loads(
            (tc.ROOT/'data/task-configs'/(task+'.json')).read_text())['inspection']}
        return job, {'source_job': job['id'], 'checkpoint': '/fixture/model_11000.pt'}

    def test_pt_check_binds_source_task_and_mapping_and_disables_pushes(self):
        source, selection = self.model()
        original = copy.deepcopy(source)
        job = self.manager.jobs[self.manager.launch('play', {
            **selection, 'task': WALK, 'recovery_evaluation': True, 'eval_pushes': True})['job_id']]
        request = job['request']
        self.assertEqual(request['task'], STAND)
        self.assertTrue(request['recovery_evaluation'])
        self.assertFalse(request['eval_pushes'])
        self.assertEqual(request['policy_parameters']['training_action_scale'], 1.0)
        self.assertEqual(request['policy_parameters']['training_firmware_p'], 5)
        self.assertEqual(request['policy_parameters']['action_filter']['legs_alpha'], 1.0)
        self.assertEqual(source, original)

    def test_onnx_check_uses_export_bound_source_and_sha(self):
        source, selection = self.model()
        exported = self.manager.jobs[self.manager.launch('export', selection)['job_id']]
        exported.update(status='completed', revision=REVISION, artifact='/fixture/policy.onnx', artifact_sha256='a'*64)
        request = self.manager.jobs[self.manager.launch('onnx', {
            'export_job': exported['id'], 'recovery_evaluation': True})['job_id']]['request']
        self.assertEqual(request['task'], STAND)
        self.assertEqual(request['onnx_sha256'], 'a'*64)
        self.assertEqual(request['source_job'], source['id'])
        self.assertTrue(request['recovery_evaluation'])

    def test_walking_model_cannot_enter_check_by_spoofing_task(self):
        _, selection = self.model(WALK)
        before = set(self.manager.jobs)
        with self.assertRaisesRegex(ValueError, '需要选择倒地起身'):
            self.manager.launch('play', {**selection, 'task': STAND, 'recovery_evaluation': True})
        self.assertEqual(set(self.manager.jobs), before)

    def test_invalid_flags_never_enqueue_a_viewer(self):
        _, selection = self.model()
        before = set(self.manager.jobs)
        for value in (1, 'true', None, [], {}):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, '参数无效'):
                self.manager.launch('play', {**selection, 'recovery_evaluation': value})
        self.assertEqual(set(self.manager.jobs), before)

    def test_flag_does_not_start_training_or_apply_to_preview_export(self):
        _, selection = self.model()
        before = set(self.manager.jobs)
        for op, value in (('train', {'task': STAND}), ('preview', {'task': STAND}),
                          ('export', selection)):
            with self.subTest(op=op), self.assertRaisesRegex(ValueError, '仅用于'):
                self.manager.launch(op, {**value, 'recovery_evaluation': True})
        self.assertEqual(set(self.manager.jobs), before)

    def test_normal_play_remains_normal_and_training_has_no_eval_flag(self):
        source, selection = self.model()
        request = self.manager.jobs[self.manager.launch('play', selection)['job_id']]['request']
        self.assertFalse(request['recovery_evaluation'])
        self.assertNotIn('recovery_evaluation', source['request'])


if __name__ == '__main__':
    unittest.main()

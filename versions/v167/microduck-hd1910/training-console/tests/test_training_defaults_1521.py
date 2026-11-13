"""New job defaults, removed EMA controls and immutable historical requests."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import training_console as tc
from training.official_spec import CATALOG, TASKS, WALK, new_training_action_scale


class TrainingDefaultsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        guard = patch.object(tc.BaseTrainingManager, '_run')
        guard.start()
        self.addCleanup(guard.stop)
        self.manager = tc.TrainingManager(Path(self.temp.name))
        self.manager.computer_verified = True
        self.addCleanup(self.manager.close)

    def test_all_catalog_defaults_and_real_queue_snapshot(self):
        self.assertEqual(len(CATALOG['profiles']), 14)
        self.assertEqual(len(TASKS), 35)
        for task in TASKS:
            self.assertEqual(new_training_action_scale(task), 1.0)
        eid = self.manager.queue_add({'task': WALK, 'client_id': 'new-default'})['entry_id']
        entry = next(e for e in self.manager.training_queue['entries'] if e['id'] == eid)
        request = entry['request']
        self.assertEqual(request['training_firmware_p'], 5)
        self.assertEqual(request['training_action_scale'], 1.0)
        self.assertEqual(request['action_filter'], {'enabled': False, 'head_alpha': 1.0, 'legs_alpha': 1.0, 'version': 1})
        self.assertFalse(self.manager.jobs)
        self.manager.queue_command({'action': 'start'})
        self.manager.queue_tick()
        launched = self.manager.jobs[entry['job_id']]['request']
        for key in ('training_firmware_p', 'training_action_scale', 'action_filter'):
            self.assertEqual(launched[key], request[key])

    def test_stale_ui_cannot_reenable_new_training_filter(self):
        enabled = {'enabled': True, 'head_alpha': .5, 'legs_alpha': .7, 'version': 1}
        with self.assertRaisesRegex(ValueError, '已取消头腿滤波'):
            self.manager.queue_add({'task': WALK, 'client_id': 'stale-ui', 'action_filter': enabled})
        for op in ('train', 'preview', 'preflight'):
            with self.subTest(op=op), self.assertRaisesRegex(ValueError, '已取消头腿滤波'):
                self.manager.launch(op, {'task': WALK, 'action_filter': enabled})
        self.assertFalse(self.manager.jobs)

    def test_user_scale_and_p_edits_still_work(self):
        eid = self.manager.queue_add({'task': WALK, 'client_id': 'edited',
                                     'training_firmware_p': 7, 'training_action_scale': .6})['entry_id']
        entry = next(e for e in self.manager.training_queue['entries'] if e['id'] == eid)
        self.assertEqual(entry['request']['training_firmware_p'], 7)
        self.assertEqual(entry['request']['training_action_scale'], .6)

    def test_resume_and_export_preserve_old_p_scale_and_filter(self):
        job = self.manager.jobs[self.manager.launch('train', {'task': WALK})['job_id']]
        old = {'training_action_scale': .7, 'training_firmware_p': 3,
               'action_filter': {'enabled': True, 'head_alpha': .5, 'legs_alpha': .7, 'version': 1}}
        job['request'].update(copy.deepcopy(old))
        job.update(status='completed', revision=job['request']['expected_revision'],
                   checkpoints=[{'path': '/fixture/model_1000.pt', 'iteration': 1000}])
        before = copy.deepcopy(job['request'])
        pick = {'task': WALK, 'source_job': job['id'], 'checkpoint': '/fixture/model_1000.pt',
                'training_action_scale': 1., 'training_firmware_p': 5}
        for op in ('export', 'play', 'train'):
            result = self.manager.jobs[self.manager.launch(op, pick)['job_id']]
            actual = result['request'] if op == 'train' else result['request']['policy_parameters']
            for key, value in old.items():
                self.assertEqual(actual[key], value)
            result['status'] = 'completed'
        self.assertEqual(job['request'], before)


if __name__ == '__main__':
    unittest.main()

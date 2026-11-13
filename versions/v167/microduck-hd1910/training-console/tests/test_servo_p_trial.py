"""Writable P values and immutable train/play/export gain provenance."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

import training_console as tc
from training.deployment import deployment_contract
from training.official_spec import WALK
from training.recipe import validate_training_firmware_p
from training.runtime_adapter import apply_recipe


def inspection(p):
    data = json.loads((tc.ROOT/'data/task-configs'/(WALK+'.json')).read_text())['inspection']
    data['full']['env']['scene']['entities']['robot']['articulation']['actuators'][0]['kp_fw'] = float(p)
    actuator = data['model']['actuators'][0]
    actuator['kp_fw'] = float(p)
    actuator['runtime_properties']['kp_fw'] = float(p)
    actuator['runtime_properties']['duty_slope_per_rad'] *= p / 5
    return data


class ServoPTrialTests(unittest.TestCase):
    def test_fractional_gain_is_not_presented_as_writable(self):
        for value in (2.69, 0, 33, True, '3', float('nan'), float('inf')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_training_firmware_p(value)
        for value in (1, 3, 3.0, 5, 32):
            self.assertEqual(validate_training_firmware_p(value), int(value))

    def test_actual_training_config_and_saved_policy_gain(self):
        for op, page, saved, expected in (
                ('train', 3, None, 3), ('preview', 3, None, 3),
                ('play', 5, 3, 3), ('export', 3, 5, 5),
                ('onnx', 3, 5, 5), ('play', 3, None, 5)):
            with self.subTest(op=op, saved=saved):
                actuator = NS(kp_fw=5.0)
                cfg = NS(scene=NS(entities={'robot': NS(articulation=NS(actuators=[actuator]))}),
                         actions={'joint_pos': NS(scale=1.0, use_default_offset=True)})
                req = {'op': op, 'task': WALK, 'training_firmware_p': page,
                       'policy_parameters': {'training_firmware_p': saved}}
                apply_recipe(cfg, NS(save_interval=1), req)
                self.assertEqual(actuator.kp_fw, expected)

    def test_export_archives_actual_p_and_does_not_relabel_old_models(self):
        for p in (3, 5):
            data = inspection(p)
            original = copy.deepcopy(data)
            c = deployment_contract({'task': WALK, 'training_firmware_p': 32,
                                     'source_training_snapshot': data}, copy.deepcopy(data))
            self.assertEqual(c['hardware_command']['firmware_kp_raw'], p)
            self.assertEqual(c['training_physics']['actuators'][0]['kp_fw'], p)
            self.assertEqual(data, original)
        with self.assertRaisesRegex(ValueError, '导出配置与原训练读回不一致'):
            deployment_contract({'task': WALK, 'source_training_snapshot': inspection(3)}, inspection(5))

    def test_queue_freezes_p_and_export_uses_the_source(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(tc.BaseTrainingManager, '_run'):
            manager = tc.TrainingManager(Path(directory))
            manager.computer_verified = True
            try:
                queued = manager.queue_add({'task': WALK, 'client_id': 'p3-trial',
                                            'training_firmware_p': 3})
                entry = next(e for e in manager.training_queue['entries'] if e['id'] == queued['entry_id'])
                self.assertEqual(entry['request']['training_firmware_p'], 3)
                manager.queue_command({'action': 'start'})
                manager.queue_tick()
                job = manager.jobs[entry['job_id']]
                self.assertEqual(job['request']['training_firmware_p'], 3)
                job['status'] = 'completed'
                job['revision'] = job['request']['expected_revision']
                job['checkpoints'] = [{'path': '/saved/model_1000.pt', 'iteration': 1000}]
                job['effective_config'] = {'training_firmware_p': 3, 'resolved': inspection(3)}
                exported = manager.jobs[manager.launch('export', {
                    'source_job': job['id'], 'checkpoint': '/saved/model_1000.pt',
                    'training_firmware_p': 5})['job_id']]
                self.assertEqual(exported['request']['policy_parameters']['training_firmware_p'], 3)
                self.assertEqual(exported['request']['source_training_snapshot']['model']['actuators'][0]['kp_fw'], 3)
            finally:
                manager.close()


if __name__ == '__main__':
    unittest.main()

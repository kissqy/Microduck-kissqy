"""Export provenance and sidecars: no hidden deployment knob overrides."""
import copy
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import training_console as tc
from studio import computer_id
from training.deployment import deployment_contract, manifest_for, write_sidecars
from training.model_package import model_package
from training.official_spec import ENGINE, REVISION, TASKS, WALK, JOINT

ROOT = Path(__file__).resolve().parents[1]


def inspection(task=WALK):
    return json.loads((ROOT/'data/task-configs'/(task+'.json')).read_text())['inspection']


class ExportContractTests(unittest.TestCase):
    def test_all_tasks_archive_enabled_physics_without_overriding_runtime_only_knobs(self):
        for task in TASKS:
            with self.subTest(task=task):
                data = inspection(task)
                c = deployment_contract({'task': task, 'source_training_snapshot': data}, data)
                for key in ('voltage_adapt', 'gain', 'standing_gain_ratio',
                            'ground_pick_gain_ratio', 'roulade_gain_ratio'):
                    self.assertNotIn(key, c['required_policy_settings'])
                physics = c['training_physics']
                self.assertEqual(physics['actuators'], data['model']['actuators'])
                self.assertEqual(physics['gear_backlash']['enabled'], TASKS[task]['backlash'])
                self.assertEqual(physics['randomization_events']['randomize_joint_friction']['params']['scale_range'], [.9, 1.1])
                self.assertEqual(physics['actuators'][0]['vin_range'], [7.4, 8.0])
                self.assertEqual(physics['actuators'][0]['vin_drop_gain_range'], [0.0, .2])
                self.assertEqual(c['training_snapshot']['provenance'], 'training_run_readback')

    def test_original_bc_events_and_curricula_survive_export_only_differences(self):
        source = inspection(JOINT)
        source['full']['agent']['algorithm']['bc_cfg'] = {'anchor_checkpoint_path': '/saved/walk.pt'}
        source['full']['env']['events']['topple_push']['params']['saved_marker'] = 'train-time'
        rebuilt = copy.deepcopy(source)
        rebuilt['full']['agent']['algorithm']['bc_cfg'] = None
        rebuilt['full']['env']['events'].pop('topple_push')
        rebuilt['full']['env']['curriculum'] = {}
        c = deployment_contract({'task': JOINT, 'source_training_snapshot': source}, rebuilt)
        self.assertEqual(c['training_snapshot']['full'], source['full'])
        self.assertIn('topple_push', c['training_physics']['randomization_events'])
        self.assertEqual(c['training_physics']['curricula'], source['full']['env']['curriculum'])
        self.assertEqual(source['full']['agent']['algorithm']['bc_cfg'], {'anchor_checkpoint_path': '/saved/walk.pt'})

    def test_conflicting_export_mapping_is_not_silently_relabelled(self):
        source = inspection()
        source['full']['env']['actions']['joint_pos'].update(scale=.7, head_alpha=.5, legs_alpha=.7, filter_version=1)
        rebuilt = copy.deepcopy(source)
        rebuilt['full']['env']['actions']['joint_pos']['scale'] = 1.0
        with self.assertRaisesRegex(ValueError, '导出配置与原训练读回不一致'):
            deployment_contract({'task': WALK, 'source_training_snapshot': source}, rebuilt)

    def test_sidecars_manifest_and_repacked_archive_share_one_training_receipt(self):
        for scale, enabled in ((.7, True), (.9, True), (1.0, False)):
            with self.subTest(scale=scale), tempfile.TemporaryDirectory() as directory:
                data = inspection()
                data['full']['env']['actions']['joint_pos']['scale'] = scale
                if enabled:
                    data['full']['env']['actions']['joint_pos'].update(head_alpha=.5, legs_alpha=.7, filter_version=1)
                # Conflicting page settings must not change the saved model.
                req = {'task': WALK, 'engine': ENGINE, 'training_action_scale': 1.0,
                       'action_filter': {'enabled': False}, 'source_training_snapshot': data}
                c = deployment_contract(req, copy.deepcopy(data))
                p = Path(directory)/'policy.onnx'; p.write_bytes(b'opaque-existing-policy')
                cp = Path(directory)/'model_14000.pt'; cp.write_bytes(b'opaque-existing-checkpoint')
                req['checkpoint'] = str(cp)
                write_sidecars(p, req, c)
                p.with_suffix('.contract.json').write_text(json.dumps(c))
                model_bytes = p.read_bytes()
                packed = model_package({'artifact': str(p), 'checkpoint': str(cp),
                                        'sha256': hashlib.sha256(model_bytes).hexdigest(), 'training_request': req})
                with zipfile.ZipFile(io.BytesIO(packed)) as z:
                    self.assertEqual(z.read('policy.onnx'), model_bytes)
                    manifest = json.loads(z.read('manifest.json'))
                    saved = json.loads(z.read('training-config.json'))
                    profile = z.read('deployment-profile.toml').decode()
                    self.assertEqual(manifest['required_policy_settings'], c['required_policy_settings'])
                    self.assertEqual(manifest['training_snapshot_sha256'], saved['sha256'])
                    self.assertEqual(saved['full'], data['full'])
                    self.assertEqual(manifest['action_scale'], scale)
                    self.assertEqual(manifest['action_filter']['enabled'], enabled)
                    self.assertIn('head_lowpass = ' + str(.5 if enabled else 1.0), profile)
                    assignments = {line.split('=', 1)[0].strip() for line in profile.splitlines()
                                   if '=' in line and not line.lstrip().startswith('#')}
                    self.assertNotIn('voltage_adapt', assignments)
                    self.assertNotIn('standing_gain_ratio', assignments)
                p.with_suffix('.training.json').unlink()
                with self.assertRaisesRegex(ValueError, '训练配置快照'):
                    model_package({'artifact': str(p), 'checkpoint': str(cp),
                                   'sha256': hashlib.sha256(model_bytes).hexdigest(), 'training_request': req})

    def test_normalization_and_missing_history_are_reported_honestly(self):
        for enabled in (True, False):
            data = inspection()
            data['full']['agent']['actor']['obs_normalization'] = enabled
            c = deployment_contract({'task': WALK}, data)
            self.assertEqual(c['normalization'], 'embedded_in_onnx_once' if enabled else 'not_used_in_training')
            self.assertEqual(c['training_snapshot']['provenance'], 'reconstructed_from_saved_recipe')
            self.assertEqual(manifest_for({'task': WALK}, c, 'a'*64)['normalization'], c['normalization'])

    def test_manager_export_binds_original_readback_instead_of_page(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'computer.json').write_text(json.dumps({'id': computer_id(), 'verified': True}))
            manager = tc.TrainingManager(root)
            try:
                with patch.object(tc.BaseTrainingManager, '_run'):
                    job = manager.jobs[manager.launch('train', {'task': WALK, 'training_action_scale': .7})['job_id']]
                    job['revision'] = REVISION
                    data = inspection()
                    data['full']['env']['actions']['joint_pos']['scale'] = .7
                    job['effective_config'] = {'resolved': data, 'training_action_scale': .7}
                    job['checkpoints'] = [{'path': '/saved/model_14000.pt', 'iteration': 14000}]
                    export = manager.jobs[manager.launch('export', {
                        'source_job': job['id'], 'checkpoint': '/saved/model_14000.pt',
                        'training_action_scale': 1.0})['job_id']]
                    snap = export['request']['source_training_snapshot']
                    self.assertEqual(snap['full']['env']['actions']['joint_pos']['scale'], .7)
                    data['full']['env']['actions']['joint_pos']['scale'] = 1.0
                    self.assertEqual(snap['full']['env']['actions']['joint_pos']['scale'], .7)
                    export['status'] = 'completed'
                    job['effective_config']['resolved'] = {'rows': []}
                    old_export = manager.jobs[manager.launch('export', {
                        'source_job': job['id'], 'checkpoint': '/saved/model_14000.pt'})['job_id']]
                    self.assertNotIn('source_training_snapshot', old_export['request'])
                    self.assertFalse(any(j['op'] in ('probe', 'preflight', 'describe', 'setup') for j in manager.jobs.values()))
            finally:
                manager.close()


if __name__ == '__main__':
    unittest.main()

"""Frozen 0.15.1 routes: command meaning, timing and installed-runtime boundaries."""
import copy
import json
import tempfile
import tomllib
import unittest
from pathlib import Path

from training.deployment import deployment_contract, manifest_for, write_sidecars
from training.official_spec import TASKS, ROLLER_ROLES, RUNTIME_REVISION


ROOT = Path(__file__).resolve().parents[1]


def inspection(task):
    return json.loads((ROOT / 'data/task-configs' / (task + '.json')).read_text())['inspection']


def by_role(role):
    return next(task for task, info in TASKS.items() if info['role'] == role and not info['backlash'])


def exported(role, resolved=None):
    task = by_role(role)
    request = {'task': task}
    contract = deployment_contract(request, resolved or inspection(task))
    return contract, manifest_for(request, contract, 'a' * 64)


class ExtendedDeploymentTests(unittest.TestCase):
    def test_all_registered_readbacks_export_without_claiming_deployment(self):
        for task in TASKS:
            with self.subTest(task=task):
                source = inspection(task)
                before = copy.deepcopy(source)
                contract = deployment_contract({'task': task}, source)
                manifest = manifest_for({'task': task}, contract, 'a' * 64)
                self.assertEqual(source, before)
                compat = manifest['runtime_compatibility']
                self.assertEqual(compat['native_runtime']['revision'], RUNTIME_REVISION)
                self.assertFalse(compat['automatic_deployment'])
                self.assertFalse(compat['official_finished_weights'])
                self.assertFalse(compat['r148_importer']['direct_import_verified'])
                self.assertEqual((manifest['obs_len'], manifest['action_len']), (61, 14))

    def test_roller_hardware_mode_and_importer_gate_are_explicit(self):
        for role in ROLLER_ROLES:
            with self.subTest(role=role):
                contract, manifest = exported(role)
                self.assertEqual(contract['robot_mode'], 'roller')
                self.assertEqual(manifest['mode'], 'roller')
                self.assertTrue(contract['runtime_compatibility']['requires_passive_roller_hardware'])
                self.assertFalse(contract['runtime_compatibility']['r148_importer']['task_allowlisted'])

    def test_phase_route_uses_actual_period_not_episode_or_stale_docstring(self):
        for role, period in (('ground_pick', 4.0), ('crouch', 5.0), ('spin', 4.0)):
            with self.subTest(role=role):
                contract, manifest = exported(role)
                self.assertEqual(contract['slot'], 'ground_pick')
                self.assertEqual(manifest['kind'], 'episodic')
                self.assertEqual(manifest['command']['encoding'], 'phase')
                self.assertEqual(manifest['command']['period_s'], period)
                self.assertEqual(manifest['command']['start_phase'], 0)
                self.assertAlmostEqual(manifest['duration_s'], period * .7)
                self.assertFalse(manifest['chain'])
                self.assertIsNone(contract['required_skill_settings'])
                source = inspection(by_role(role))
                source['full']['env']['commands']['twist']['period'] = 6.5
                changed, changed_manifest = exported(role, source)
                self.assertEqual(changed['required_policy_settings']['ground_pick_period'], 6.5)
                self.assertAlmostEqual(changed_manifest['duration_s'], 4.55)
        _, ground_pick = exported('ground_pick')
        self.assertTrue(ground_pick['command']['training_randomize_phase'])

    def test_invalid_phase_encoder_or_period_is_rejected(self):
        for key, value in (('period', 0), ('period', -1), ('period', float('inf')),
                           ('period', True), ('class_type', {'callable': 'other.Phase'})):
            with self.subTest(key=key, value=value):
                source = inspection(by_role('spin'))
                source['full']['env']['commands']['twist'][key] = value
                with self.assertRaises(ValueError):
                    exported('spin', source)

    def test_roller_stand_is_not_automatic_stand_or_fabricated_six_second_skill(self):
        contract, manifest = exported('roller_stand')
        self.assertIsNone(contract['slot'])
        self.assertNotIn('slot', manifest)
        self.assertIsNone(manifest['duration_s'])
        self.assertIsNone(contract['required_skill_settings'])
        self.assertNotIn('action_scale', contract['required_policy_settings'])
        self.assertEqual(manifest['entry_pose'], 'fallen')
        self.assertEqual(contract['runtime_compatibility']['native_runtime']['route'], 'manual_skill')
        self.assertEqual(contract['runtime_compatibility']['native_runtime']['support'], 'manual_configuration_required')

    def test_swizzle_and_slope_cannot_claim_general_velocity_control(self):
        contract, manifest = exported('swizzle')
        self.assertEqual(contract['slot'], 'walk')
        self.assertIn('heading error', manifest['command']['twist'])
        self.assertIn('not yaw velocity', manifest['command']['twist'])
        self.assertIn('HOME', manifest['command']['head'])
        self.assertEqual(manifest['command']['body'], 'zeros')
        self.assertEqual(contract['runtime_compatibility']['native_runtime']['support'], 'restricted_command_protocol')
        self.assertIn('直行子集', ''.join(contract['runtime_compatibility']['native_runtime']['limitations']))
        contract, manifest = exported('slope')
        self.assertEqual(TASKS[by_role('slope')]['terrain'], 'Slope')
        self.assertEqual([manifest['command'][key] for key in ('twist', 'head', 'body')], ['zeros'] * 3)
        self.assertIsNone(manifest['duration_s'])

    def test_incompatible_head_or_body_observation_is_rejected(self):
        for role, name in (('spin', 'head_command'), ('slope', 'body_command'), ('swizzle', 'head_command')):
            source = inspection(by_role(role))
            source['full']['env']['observations']['actor']['terms'][name]['func'] = {'callable': 'custom.changed'}
            with self.subTest(role=role), self.assertRaises(ValueError):
                exported(role, source)

    def test_builtin_skill_scales_use_native_skill_overrides(self):
        for role, duration in (('roulade', 1), ('kick_left', .5), ('kick_right', .5)):
            with self.subTest(role=role):
                source = inspection(by_role(role))
                source['full']['env']['actions']['joint_pos']['scale'] = .83
                contract, manifest = exported(role, source)
                self.assertEqual(contract['required_skill_settings']['params'], {'action_scale': .83})
                self.assertNotIn('roulade_action_scale', contract['required_policy_settings'])
                self.assertNotIn('standing_action_scale', contract['required_policy_settings'])
                self.assertEqual(manifest['duration_s'], duration)
                self.assertEqual(manifest['chain'], role == 'roulade')
                with tempfile.TemporaryDirectory() as folder:
                    path = Path(folder) / 'policy.onnx'
                    path.write_bytes(b'test-graph-placeholder')
                    write_sidecars(path, {'task': by_role(role)}, contract)
                    policy = tomllib.loads(path.with_suffix('.deployment.toml').read_text())['policy']
                    self.assertEqual(policy['skill'], [contract['required_skill_settings']])
                    self.assertEqual(policy['head_lowpass'], 1)
                    self.assertEqual(policy['legs_lowpass'], 1)
                    self.assertNotIn('gain', policy)

    def test_stand_teacher_and_left_training_identity_preserved(self):
        contract, manifest = exported('stand')
        self.assertTrue(contract['teacher_only'])
        self.assertNotIn('slot', manifest)
        self.assertEqual(manifest['name'], 'standup-teacher')
        contract, manifest = exported('kick_left')
        self.assertIn('BallKickLeft', manifest['task'])
        self.assertEqual(manifest['name'], 'kick_left')
        self.assertFalse(contract['runtime_compatibility']['r148_importer']['task_allowlisted'])

    def test_sitstand_ramp_is_read_from_training_snapshot(self):
        source = inspection(by_role('sitstand'))
        source['full']['env']['commands']['twist']['ramp_s'] = 3.25
        _, manifest = exported('sitstand', source)
        self.assertEqual(manifest['ramp_s'], 3.25)
        self.assertEqual(manifest['unwind_s'], 1)


if __name__ == '__main__':
    unittest.main()

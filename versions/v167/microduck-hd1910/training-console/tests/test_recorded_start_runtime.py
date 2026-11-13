"""Portable pose reconstruction and first-action gate tests; no physics claims."""
import copy
import hashlib
import math
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from training import recorded_start as recorded
from training import recovery_evaluation as recovery
from training import limit_comparison as comparison
from training.official_spec import RUNTIME_JOINTS


def pose():
    return {'schema': recorded.SCHEMA, 'frame_index': 184, 'active_frame_index': 185,
            'frame_at_s': 13.1567, 'state_t_ns': 123456789, 'gap_s': .139430098,
            'joint_names': list(RUNTIME_JOINTS), 'joint_pos_rad': [i*.01-.1 for i in range(14)],
            'joint_vel_rad_s': [.01]*14, 'gravity_b': [-.8, .6, 0.], 'gyro_rad_s': [.02, 0., 0.],
            'source': 'last_inactive_before_first_standup_enable'}


class Tensor:
    def __init__(self, value): self.value = np.asarray(value)
    def detach(self): return self
    def cpu(self): return self
    def to(self, **kwargs): return self
    def tolist(self): return self.value.tolist()
    def __len__(self): return len(self.value)
    def __getitem__(self, key): return Tensor(self.value[key])
    def __setitem__(self, key, value):
        if isinstance(key, tuple): key = tuple(k.value if isinstance(k, Tensor) else k for k in key)
        elif isinstance(key, Tensor): key = key.value
        self.value[key] = value.value if isinstance(value, Tensor) else value


def fake_env():
    active = list(reversed(RUNTIME_JOINTS))
    # Intentionally shuffled active/passive order and qpos addresses: no slicing
    # or assumption that actuator joint IDs equal MuJoCo qpos addresses is valid.
    names = active + ['passive_' + n + '_backlash' for n in active]
    addresses = list(range(7, 35))[::-1]
    qpos = np.zeros((1, 35)); qpos[0, :7] = [1., 2., .05, math.sqrt(.5), 0., -math.sqrt(.5), 0.]
    qpos[0, 7:] = np.arange(28)*.0007
    robot = SimpleNamespace(joint_names=names, data=SimpleNamespace(
        indexing=SimpleNamespace(joint_q_adr=Tensor(addresses)), encoder_bias=Tensor([np.arange(28)*.0003]),
        projected_gravity_b=Tensor([[-.8, .6, 0.]])))
    return SimpleNamespace(num_envs=1, device='cpu', scene={'robot': robot},
                           sim=SimpleNamespace(data=SimpleNamespace(qpos=Tensor(qpos), qvel=Tensor(np.ones((1, 34))))))


class RecordedPoseMathTests(unittest.TestCase):
    def test_gravity_orientation_and_sampled_yaw_convention(self):
        gravities = ([-1., 0., 0.], [0., 0., -1.], [0., 0., 1.], [-.8, .6, 0.], [0., .6, -.8])
        for yaw in (-2.3, 0., 1.4):
            yaw_q = [math.cos(yaw/2), 0., 0., math.sin(yaw/2)]
            source = recorded.multiply_quaternions(yaw_q, [math.sqrt(.5), 0., -math.sqrt(.5), 0.])
            for gravity in gravities:
                with self.subTest(yaw=yaw, gravity=gravity):
                    q = recorded.quaternion_for_gravity(gravity, source)
                    self.assertAlmostEqual(sum(v*v for v in q), 1.)
                    for actual, wanted in zip(recorded.gravity_from_quaternion(q), gravity):
                        self.assertAlmostEqual(actual, wanted)
            self.assertTrue(np.allclose(recorded.quaternion_for_gravity([-1., 0., 0.], source), source))

    def test_degenerate_and_nonfinite_orientation_rejected(self):
        for gravity in ([0., 0., 0.], [float('nan'), 0., 0.]):
            with self.assertRaises(ValueError): recorded.quaternion_for_gravity(gravity, [1., 0., 0., 0.])
        with self.assertRaises(ValueError): recorded.quaternion_for_gravity([-1., 0., 0.], [0., 1., 0., 0.])

    def test_named_motor_inverse_preserves_sampled_backlash_bias_and_readback(self):
        env = fake_env(); p = pose(); before = env.sim.data.qpos.value.copy()
        recorded.apply_pose(env, Tensor([0]), p, backlash_expected=True)
        result = recorded.verify_pose(env, p, backlash_expected=True)
        self.assertTrue(result['passed'])
        self.assertLess(result['errors']['encoder_max_abs_deg'], 1e-12)
        self.assertLess(result['errors']['gravity_l2'], 1e-12)
        self.assertEqual(env.sim.data.qpos.value[0, :2].tolist(), [1., 2.])
        self.assertTrue(np.all(env.sim.data.qvel.value == 0.))
        robot = env.scene['robot']
        for name, adr in zip(robot.joint_names, robot.data.indexing.joint_q_adr.tolist()):
            if name.startswith('passive_'): self.assertEqual(before[0, adr], env.sim.data.qpos.value[0, adr])
        self.assertEqual(result['requested']['source_joint_vel_rad_s'], [.01]*14)
        self.assertEqual(result['conventions']['velocity'], 'zero_all_qvel')

    def test_partial_backlash_or_unknown_joint_rejected(self):
        p = pose(); names = p['joint_names']
        for model_names in (names + ['passive_' + names[0] + '_backlash'], ['unknown'] + names[1:]):
            with self.assertRaises(ValueError): recorded.joint_layout(names, model_names, list(range(len(model_names))), backlash_expected=True)

    def test_first_action_tolerances_and_raw_gravity_norm_are_enforced(self):
        p = pose(); q = recorded.quaternion_for_gravity(p['gravity_b'], [math.sqrt(.5), 0., -math.sqrt(.5), 0.])
        encoder = list(p['joint_pos_rad']); encoder[3] += math.radians(.11)
        self.assertFalse(recorded.compare_readback(p, encoder, p['gravity_b'], q, [0.]*34)['passed'])
        self.assertFalse(recorded.compare_readback(p, p['joint_pos_rad'], [-.802, .6, 0.], q, [0.]*34)['passed'])
        self.assertFalse(recorded.compare_readback(p, p['joint_pos_rad'], p['gravity_b'], q, [.001]*34)['passed'])
        encoder[3] = p['joint_pos_rad'][3] + math.radians(.09)
        self.assertTrue(recorded.compare_readback(p, encoder, p['gravity_b'], q, [0.]*34)['passed'])
        stretched = copy.deepcopy(p); stretched['gravity_b'] = [v*1.002 for v in p['gravity_b']]
        self.assertFalse(recorded.compare_readback(stretched, stretched['joint_pos_rad'], p['gravity_b'], q, [0.]*34)['passed'])

    def test_nonfinite_feedback_and_multiworld_reset_are_rejected(self):
        p = pose(); encoder = list(p['joint_pos_rad']); encoder[0] = float('nan')
        invalid = recorded.compare_readback(p, encoder, p['gravity_b'], [1.,0.,0.,0.], [0.]*34)
        self.assertFalse(invalid['passed'])
        self.assertIn('非有限', invalid['reason'])
        self.assertEqual(invalid['requested']['joint_names'], p['joint_names'])
        env = fake_env(); env.num_envs = 2
        with self.assertRaises(ValueError): recorded.apply_pose(env, Tensor([0]), p, backlash_expected=True)

    def test_stale_entity_gravity_fails_even_when_raw_qpos_is_correct(self):
        env = fake_env(); p = pose(); recorded.apply_pose(env, Tensor([0]), p, backlash_expected=True)
        env.scene['robot'].data.projected_gravity_b = Tensor([[-1., 0., 0.]])
        check = recorded.verify_pose(env, p, backlash_expected=True)
        self.assertFalse(check['passed'])
        self.assertLess(check['errors']['encoder_max_abs_deg'], 1e-12)
        self.assertGreater(check['errors']['gravity_data_vs_qpos_l2'], .1)
        self.assertTrue(np.allclose(check['measured']['gravity_from_qpos_b'], p['gravity_b']))


class RecordedResetIntegrationTests(unittest.TestCase):
    def test_source_then_pose_then_placement_without_stepping_or_rng_calls(self):
        env = fake_env(); events = []; p = pose()
        torch = ModuleType('torch'); torch.long = 'long'
        def source(env, ids, **params):
            events.append('source')
            self.assertEqual(params['face_up_prob'], 1.)
        def placement(env, ids):
            events.append('placement')
            self.assertTrue(recorded.verify_pose(env, p, backlash_expected=True)['passed'])
            env.sim.data.qpos[0, 2] = .123
        with patch.dict(sys.modules, {'torch': torch}), patch.object(recovery, 'place_on_plane', placement):
            recovery.reset_ground_pose(env, Tensor([0]), source, {}, recorded_pose=p, recorded_backlash=True)
        self.assertEqual(events, ['source', 'placement'])
        self.assertEqual(env.sim.data.qpos.value[0, 2], .123)
        self.assertEqual(env._studio_recovery_reset_serial, 1)

    def test_standard_reset_never_applies_recorded_pose(self):
        env = fake_env(); torch = ModuleType('torch'); torch.long = 'long'
        with patch.dict(sys.modules, {'torch': torch}), patch.object(recovery, 'place_on_plane'), \
             patch.object(recorded, 'apply_pose', side_effect=AssertionError('standard must stay unchanged')):
            recovery.reset_ground_pose(env, Tensor([0]), lambda *args, **kwargs: None, {})
        self.assertFalse(hasattr(env, '_studio_recorded_start_application'))

    def test_prepare_config_propagates_recorded_pose_only_for_opt_in(self):
        event_module = ModuleType('mjlab.managers.event_manager')
        event_module.EventTermCfg = lambda **kwargs: SimpleNamespace(**kwargs)
        request = {'engine': 'official_0151', 'op': 'onnx', 'task': 'Mjlab-StandUp-Rough-Backlash-MicroDuck',
                   'recovery_evaluation': True, 'target_limit_start_mode': 'recorded',
                   'target_limit_comparison': {'recorded_start': pose()}}
        cfg = SimpleNamespace(events={}, curriculum={}, scene=SimpleNamespace(terrain=SimpleNamespace()))
        with patch.dict(sys.modules, {'mjlab.managers.event_manager': event_module}):
            recovery.prepare_config(cfg, request)
        params = cfg.events[recovery.STARTUP_EVENT].params
        self.assertEqual(params['recorded_pose'], pose())
        self.assertTrue(params['recorded_backlash'])
        request.pop('target_limit_start_mode')
        cfg.events.clear()
        with patch.dict(sys.modules, {'mjlab.managers.event_manager': event_module}): recovery.prepare_config(cfg, request)
        self.assertNotIn('recorded_pose', cfg.events[recovery.STARTUP_EVENT].params)


class RecordedComparisonGateTests(unittest.TestCase):
    def test_good_readback_allows_first_action_after_existing_fairness_check(self):
        env = fake_env(); p = pose(); recorded.apply_pose(env, Tensor([0]), p, backlash_expected=True)
        env.reward_manager = SimpleNamespace(get_term_cfg=lambda _: SimpleNamespace(params={'target_height': .115}))
        env.step_dt = .02; env.reset_terminated = [False]; env.reset_time_outs = [True]
        env.cfg = SimpleNamespace(auto_reset=True)
        actions, closed, checks = [], [], []
        wrapped = SimpleNamespace(unwrapped=env, close=lambda: closed.append(True),
                                  step=lambda action: ({}, None, [True], {}))
        mapping = {'scale': 1., 'filter': {'head_alpha': 1., 'legs_alpha': 1.}}
        profile = {'recorded_start': p, 'runtime': {'effective_action_scale_min': 1., 'effective_action_scale_max': 1.}}
        req = {'target_limit_start_mode': 'recorded', 'task': 'Mjlab-StandUp-Rough-Backlash-MicroDuck'}
        fingerprint = {'components': {'rng': 'same'}}
        def capture(*args, **kwargs):
            checks.append('fairness')
            return fingerprint
        def policy(obs):
            self.assertEqual(checks, ['fairness'])
            actions.append(True)
            return [0.]*14
        with patch.object(comparison, '_build_group', return_value=(wrapped, policy, {}, mapping)), \
             patch.object(comparison, 'startup_fingerprint', capture):
            result = comparison._run_group(req, profile, 'B', lambda *args, **kwargs: None, fingerprint)
        self.assertTrue(result['recorded_start_check']['passed'])
        self.assertTrue(result['initial_state_comparison']['passed'])
        self.assertEqual(result['steps'], 1)
        self.assertEqual(actions, [True])
        self.assertEqual(closed, [True])

    def test_bad_readback_stops_before_policy_or_fingerprint(self):
        env = fake_env(); p = pose(); recorded.apply_pose(env, Tensor([0]), p, backlash_expected=True)
        env.sim.data.qpos.value[0, 34] += .1
        env.reward_manager = SimpleNamespace(get_term_cfg=lambda _: SimpleNamespace(params={'target_height': .115}))
        closed = []; wrapped = SimpleNamespace(unwrapped=env, close=lambda: closed.append(True))
        mapping = {'scale': 1., 'filter': {'head_alpha': 1., 'legs_alpha': 1.}}
        profile = {'recorded_start': p, 'runtime': {'effective_action_scale_min': 1., 'effective_action_scale_max': 1.}}
        req = {'target_limit_start_mode': 'recorded', 'task': 'Mjlab-StandUp-Rough-Backlash-MicroDuck'}
        def forbidden(*args): raise AssertionError('Mismatch must not reach policy or startup comparison')
        with patch.object(comparison, '_build_group', return_value=(wrapped, forbidden, {}, mapping)), \
             patch.object(comparison, 'startup_fingerprint', forbidden):
            result = comparison._run_group(req, profile, 'B', lambda *args, **kwargs: None)
        self.assertEqual((result['status'], result['steps']), ('invalid', 0))
        self.assertFalse(result['recorded_start_check']['passed'])
        self.assertEqual(result['recorded_start_check']['source']['frame_index'], 184)
        self.assertEqual(closed, [True])

    def test_two_groups_share_exact_recorded_input_and_scope_metadata(self):
        from training import target_limit_profile
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'model.onnx'; path.write_bytes(b'fixture')
            request = {'op': 'onnx', 'engine': 'official_0151', 'task': 'Mjlab-StandUp-Rough-Backlash-MicroDuck',
                       'onnx_path': str(path), 'onnx_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                       'target_limit_start_mode': 'recorded', 'target_limit_comparison': {}}
            profile = {'seed': 3, 'recorded_start': pose()}; inputs = []
            def evaluate(req, profile, label, emit, expected=None, **kwargs):
                inputs.append((label, copy.deepcopy(profile['recorded_start']), req['target_limit_start_mode']))
                return {'label': label, 'status': 'passed', 'elapsed_s': 1.,
                        'initial_fingerprint': {'components': {'rng': 'same'}}}
            with patch.object(target_limit_profile, 'validate_profile', return_value=profile), \
                 patch.object(comparison, '_configure_backends'), patch.object(comparison, '_run_group', evaluate):
                result = comparison.run(request, lambda *args, **kwargs: None)
        self.assertEqual([row[0] for row in inputs], ['A', 'B'])
        self.assertEqual(inputs[0][1:], inputs[1][1:])
        self.assertTrue(result['valid'])
        self.assertEqual(result['start_mode'], 'recorded')
        self.assertIn('not_trajectory_replay', result['start_pose'])


if __name__ == '__main__': unittest.main()

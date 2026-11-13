"""Pinned RollerStandUp uses raw wheel indices in three 14-servo rewards."""
import copy
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import PropertyMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
UPSTREAM = os.environ.get('MICRODUCK_OFFICIAL_SOURCE')
TASK = 'Mjlab-RollerStandUp-Flat-MicroDuck'
REWARDS = ('pose_stand_legs', 'pose_stand_l1', 'standing_composite')


@unittest.skipUnless(UPSTREAM, 'Pinned official source not supplied')
class RollerStandupAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(Path(UPSTREAM)/'src'))
        import torch
        torch.set_num_threads(2)
        from mjlab_microduck.tasks.microduck_roller_standup_env_cfg import make_microduck_roller_standup_env_cfg
        cls.factory = staticmethod(make_microduck_roller_standup_env_cfg)

    def repair(self, cfg, op='train'):
        from training.official_adapter import _repair_roller_standup_servo_indices
        req = {'task': TASK, 'op': op}
        with patch('training.event_protocol.emit'):
            _repair_roller_standup_servo_indices(cfg, req)
        return req

    def test_all_three_leg_rewards_preserve_joint_intent_and_reset_contract(self):
        from training.recipe import plain
        cfg = self.factory()
        old = {name: copy.deepcopy(cfg.rewards[name].params) for name in REWARDS}
        events = plain(cfg.events)
        weights = {name: term.weight for name, term in cfg.rewards.items()}
        req = self.repair(cfg)
        expected = list(range(5)) + list(range(9, 14))
        for name in REWARDS:
            self.assertEqual(old[name]['joint_indices'], list(range(5)) + list(range(11, 16)))
            self.assertEqual(cfg.rewards[name].params['joint_indices'], expected)
            self.assertIsNone(cfg.rewards[name].params['target_overrides'])
        self.assertEqual(plain(cfg.events), events)
        self.assertEqual({name: term.weight for name, term in cfg.rewards.items()}, weights)
        self.assertEqual(len(req['_adapter_corrections'][0]['changes']), 3)
        before = plain(cfg.rewards)
        self.repair(cfg)
        self.assertEqual(plain(cfg.rewards), before)

    def test_three_reward_target_vectors_map_legs_and_neck_by_name(self):
        import torch
        from mjlab_microduck.tasks import mdp
        for reward_name in REWARDS:
            for raw_selected in (list(range(5)) + list(range(11, 16)), list(range(7, 11))):
                with self.subTest(reward=reward_name, selected=raw_selected):
                    cfg = self.factory()
                    term = cfg.rewards[reward_name]
                    term.params['joint_indices'] = raw_selected
                    term.params['target_overrides'] = {index: (index + 1) / 100 for index in raw_selected}
                    self.repair(cfg)
                    receipt = cfg._studio_adapter_corrections[0]
                    raw_names, servo_names = receipt['source_joint_names'], receipt['servo_joint_names']
                    expected_ids = [servo_names.index(raw_names[index]) for index in raw_selected]
                    expected = torch.zeros(2, 14)
                    for raw_index in raw_selected:
                        expected[:, servo_names.index(raw_names[raw_index])] = (raw_index + 1) / 100
                    params = cfg.rewards[reward_name].params
                    self.assertEqual(params['joint_indices'], expected_ids)
                    actual_target = torch.zeros(2, 14)
                    for index, value in params['target_overrides'].items():
                        actual_target[:, index] = value
                    torch.testing.assert_close(actual_target, expected)
                    data = types.SimpleNamespace(
                        root_link_pos_w=torch.tensor([[0., 0., .138], [0., 0., .138]]),
                        root_link_quat_w=torch.tensor([[1., 0., 0., 0.], [1., 0., 0., 0.]]))
                    class Scene(dict):
                        terrain = types.SimpleNamespace(env_origins=torch.zeros(2, 3))
                    env = types.SimpleNamespace(scene=Scene(robot=types.SimpleNamespace(data=data)))
                    with patch.object(mdp, '_servo_joint_pos', return_value=expected), \
                         patch.object(mdp, '_servo_default_joint_pos', return_value=torch.zeros(2, 14)):
                        value = term.func(env, **params)
                    target = torch.zeros(2) if reward_name == 'pose_stand_l1' else torch.ones(2)
                    torch.testing.assert_close(value, target)

    def test_unknown_or_passive_reward_target_fails_before_partial_mutation(self):
        from training.recipe import plain
        cfg = self.factory()
        cfg.rewards['pose_stand_l1'].params['target_overrides'] = {5: .2}
        before = plain(cfg.rewards)
        with self.assertRaisesRegex(ValueError, '被动轮'):
            self.repair(cfg)
        self.assertEqual(plain(cfg.rewards), before)

    def test_adapter_has_same_mapping_for_describe_train_and_export(self):
        from training.official_adapter import adapt_robot
        from training.recipe import plain
        snapshots = []
        for op in ('describe', 'train', 'export'):
            cfg = self.factory()
            req = {'task': TASK, 'op': op}
            with patch('training.event_protocol.emit'):
                adapt_robot(cfg, None, req)
            snapshots.append(plain(cfg.rewards))
            self.assertIn('_adapter_corrections', req)
        self.assertEqual(snapshots[0], snapshots[1])
        self.assertEqual(snapshots[1], snapshots[2])

    def test_corrected_hd1910_two_world_reset_and_ten_steps(self):
        import torch
        from mjlab.envs import ManagerBasedRlEnv
        from training.official_adapter import adapt_robot
        cfg = self.factory()
        with patch('training.event_protocol.emit'):
            adapt_robot(cfg, None, {'task': TASK, 'op': 'train'})
        cfg.scene.num_envs = 2
        cfg.seed = 31
        env = ManagerBasedRlEnv(cfg, device='cpu')
        try:
            obs, _ = env.reset()
            self.assertEqual(tuple(obs['actor'].shape), (2, 61))
            for _ in range(10):
                obs, reward, *_ = env.step(torch.zeros(2, 14))
                self.assertEqual(tuple(obs['actor'].shape), (2, 61))
                self.assertTrue(bool(torch.isfinite(obs['actor']).all()))
                self.assertTrue(bool(torch.isfinite(reward).all()))
            data = self.readback(env)
            self.assertEqual(data['foot_or_wheel_contact']['geom_count'], 4)
            self.assertEqual(data['foot_or_wheel_contact']['coefficients']['shape'], [2, 4, 3])
            self.assertEqual(data['foot_or_wheel_contact']['sliding']['min'], 1.0)
            self.assertEqual(data['foot_or_wheel_contact']['sliding']['max'], 1.0)
            self.assertEqual(data['wheel_bearings']['actual_frictionloss_nm']['shape'], [2, 4])
            self.assertAlmostEqual(data['wheel_bearings']['actual_frictionloss_nm']['min'], .05)
            self.assertAlmostEqual(data['wheel_bearings']['actual_frictionloss_nm']['max'], .05)
            self.assertIsNone(data['configured_events']['foot_friction'])
            print('ROLLER_STANDUP_HD1910_TWO_WORLDS_TEN_STEPS_61x14_FINITE', flush=True)
        finally:
            env.close()

    def readback(self, env):
        import torch
        from training.official_adapter import report_friction_state
        robot = env.scene['robot']
        before = (robot.data.joint_pos.clone(), robot.data.joint_vel.clone(),
                  robot.actuators[0].friction_scale.clone(), env.common_step_counter)
        frames = []
        report_friction_state(env, lambda kind, **body: frames.append({'kind': kind, **body}))
        data = next(frame['data'] for frame in frames if frame['kind'] == 'friction_readback')
        for field in ('foot_or_wheel_contact', 'terrain_contact', 'wheel_bearings'):
            self.assertTrue(data[field]['available'], data[field])
        motor = data['motor'][0]
        self.assertTrue(motor['available'], motor)
        self.assertEqual(motor['friction_scale']['shape'], [2, 1])
        self.assertEqual(motor['actual_dof_frictionloss_nm']['shape'], [2, 14])
        self.assertEqual(motor['configured_scale_range'], [.9, 1.1])
        self.assertGreaterEqual(motor['friction_scale']['min'], .9)
        self.assertLessEqual(motor['friction_scale']['max'], 1.1)
        torch.testing.assert_close(robot.data.joint_pos, before[0])
        torch.testing.assert_close(robot.data.joint_vel, before[1])
        torch.testing.assert_close(robot.actuators[0].friction_scale, before[2])
        self.assertEqual(env.common_step_counter, before[3])
        print('FRICTION_READBACK', data, flush=True)
        return data

    def test_walking_contact_readback_is_post_randomization_and_has_no_wheels(self):
        import torch
        from mjlab.envs import ManagerBasedRlEnv
        from mjlab_microduck.tasks.microduck_velocity_env_cfg import make_microduck_velocity_env_cfg
        from training.official_adapter import adapt_robot
        cfg = make_microduck_velocity_env_cfg()
        adapt_robot(cfg, None, {'task': 'Mjlab-Velocity-Flat-MicroDuck', 'op': 'train'})
        cfg.scene.num_envs = 2
        cfg.seed = 31
        env = ManagerBasedRlEnv(cfg, device='cpu')
        try:
            env.reset()
            env.step(torch.zeros(2, 14))
            data = self.readback(env)
            contact = data['foot_or_wheel_contact']
            self.assertEqual(contact['geom_count'], 2)
            self.assertEqual(contact['coefficients']['shape'], [2, 2, 3])
            self.assertGreaterEqual(contact['sliding']['min'], .7)
            self.assertLessEqual(contact['sliding']['max'], 1.3)
            self.assertNotEqual(contact['sliding']['min'], contact['sliding']['max'])
            self.assertEqual(data['configured_events']['foot_friction']['params']['ranges'], [.7, 1.3])
            self.assertEqual(data['wheel_bearings']['joint_names'], [])
            self.assertIsNone(data['wheel_bearings']['actual_frictionloss_nm'])
        finally:
            env.close()

    def test_rough_terrain_limits_details_but_preserves_all_geom_extrema(self):
        import json
        import torch
        from mjlab.envs import ManagerBasedRlEnv
        from mjlab_microduck.tasks.microduck_velocity_env_cfg import make_microduck_velocity_env_cfg, MicroduckRlCfg
        from training.runtime_adapter import apply_recipe
        from studio import fresh_recipe
        cfg = make_microduck_velocity_env_cfg(rough=True)
        apply_recipe(cfg, copy.deepcopy(MicroduckRlCfg),
                     {'task': 'Mjlab-Velocity-Rough-MicroDuck', 'op': 'train',
                      'engine': 'official_0151', 'studio_recipe': fresh_recipe(),
                      'training_firmware_p': 5, 'training_action_scale': 1,
                      'action_filter': {'enabled': False, 'head_alpha': 1, 'legs_alpha': 1}})
        cfg.scene.num_envs = 2
        cfg.seed = 31
        env = ManagerBasedRlEnv(cfg, device='cpu')
        try:
            env.reset()
            obs, reward, *_ = env.step(torch.linspace(-.05, .05, 14).repeat(2, 1))
            self.assertEqual(tuple(obs['actor'].shape), (2, 61))
            self.assertTrue(bool(torch.isfinite(reward).all()))
            actual = self.readback(env)
            terrain = actual['terrain_contact']
            count = len(env.scene.terrain.indexing.geom_ids)
            self.assertGreater(count, 32)
            self.assertEqual(terrain['total_count'], count)
            self.assertEqual(terrain['sample_count'], 32)
            self.assertTrue(terrain['truncated'])
            self.assertEqual(len(terrain['geoms']), 32)
            self.assertEqual(terrain['coefficients']['shape'], [2, count, 3])
            self.assertEqual(len(terrain['coefficients']['per_item_min']), 32)
            self.assertFalse(actual['foot_or_wheel_contact']['truncated'])
            fixture = os.environ.get('MICRODUCK_READBACK_FIXTURE_OUT')
            if fixture:
                Path(fixture).write_text(json.dumps(actual, ensure_ascii=False, indent=2)+'\n')

            # Feed a COPY of the live fields to the reader. Put extrema beyond
            # the detail cap, without modifying physics or advancing the env.
            model = env.sim.model
            copied = model.geom_friction[:].clone()
            last = int(env.scene.terrain.indexing.geom_ids[-1])
            copied[0, last, 0] = .123
            copied[1, last, 0] = 1.987
            proxy = types.SimpleNamespace(geom_friction=copied,
                                          dof_frictionloss=model.dof_frictionloss)
            with patch.object(type(env.sim), 'model', new_callable=PropertyMock, return_value=proxy):
                synthetic = self.readback(env)['terrain_contact']
            self.assertAlmostEqual(synthetic['sliding']['min'], .123, places=6)
            self.assertAlmostEqual(synthetic['sliding']['max'], 1.987, places=6)
            self.assertEqual(len(synthetic['sliding']['per_item_min']), 32)
            self.assertTrue(all(value == 1.0 for value in synthetic['sliding']['per_item_min']))
            print('ROUGH_READBACK_32_DETAILS_ALL_GEOM_EXTREMA_NO_STATE_CHANGE', flush=True)
        finally:
            env.close()


if __name__ == '__main__':
    unittest.main()

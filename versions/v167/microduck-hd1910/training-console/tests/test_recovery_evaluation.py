"""Regressions for missing ONNX back starts and reset-as-success mistakes.

Real manager/physics tests use MICRODUCK_OFFICIAL_SOURCE and the pinned CPU
dependencies. No user checkpoint or training process is opened by these tests.
"""
import copy
import json
import math
import os
import sys
import unittest
from pathlib import Path

from training.recovery_evaluation import TrialRecorder


class RecoveryResultsTests(unittest.TestCase):
    def test_reset_pose_cannot_create_success(self):
        trial = TrialRecorder(.115)
        trial.start('back_flat')
        for _ in range(49):
            self.assertFalse(trial.observe(.02, height=.115, gravity_z=-1))
        self.assertTrue(trial.observe(.02, height=.115, gravity_z=-1, timed_out=True))
        self.assertEqual(trial.current['result'], 'failed')
        self.assertEqual(trial.counts['back_flat'], {'passed': 0, 'failed': 1, 'cancelled': 0})

    def test_height_and_tilt_must_hold_together_for_a_full_second(self):
        trial = TrialRecorder(.115)
        trial.start('face_down')
        for _ in range(70):
            self.assertFalse(trial.observe(.02, height=.060, gravity_z=-1))
        for _ in range(70):
            self.assertFalse(trial.observe(.02, height=.115, gravity_z=-.5))
        for _ in range(30):
            self.assertFalse(trial.observe(.02, height=.115, gravity_z=-1))
        self.assertFalse(trial.observe(.02, height=.060, gravity_z=-1))
        for _ in range(49):
            self.assertFalse(trial.observe(.02, height=.115, gravity_z=-1))
        self.assertTrue(trial.observe(.02, height=.115, gravity_z=-1))
        self.assertEqual(trial.counts['face_down']['passed'], 1)
        # Continuing a completed episode never increments the numerator again.
        for _ in range(100):
            trial.observe(.02, height=.115, gravity_z=-1)
        self.assertEqual(trial.counts['face_down']['passed'], 1)

    def test_mixed_observation_and_cancelled_trials_do_not_inflate_success(self):
        trial = TrialRecorder(.115)
        trial.start('mixed')
        for _ in range(100):
            self.assertFalse(trial.observe(.02, height=.115, gravity_z=-1))
        self.assertFalse(trial.observe(.02, height=.115, gravity_z=-1, timed_out=True))
        self.assertFalse(trial.history)
        trial.start('back_flat')
        trial.start('left_side')
        self.assertEqual(trial.counts['back_flat'], {'passed': 0, 'failed': 0, 'cancelled': 1})
        trial.observe(.02, height=.115, gravity_z=float('nan'))
        self.assertEqual(trial.current['hold_s'], 0)


UPSTREAM = os.environ.get('MICRODUCK_OFFICIAL_SOURCE')


@unittest.skipUnless(UPSTREAM, 'Pinned official source/dependencies not supplied')
class RecoveryUpstreamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(Path(UPSTREAM) / 'src'))
        import mjlab.tasks, mjlab_microduck.tasks
        import torch
        torch.set_num_threads(2)

    def configuration(self, op='onnx', specialist=True, rough=False):
        from mjlab.tasks.registry import load_env_cfg, load_rl_cfg
        from training.runtime_adapter import apply_recipe, configure_evaluation_events
        from training.recovery_evaluation import prepare_config
        from studio import fresh_recipe
        task = 'Mjlab-StandUp-' + ('Rough' if rough else 'Flat') + '-Backlash-MicroDuck'
        req = {'op': op, 'engine': 'official_0151', 'task': task,
               'recovery_evaluation': specialist, 'studio_recipe': fresh_recipe(),
               'policy_parameters': {'training_action_scale': 1.0,
                                     'action_filter': {'enabled': True, 'head_alpha': .5, 'legs_alpha': .7}}}
        cfg, agent = load_env_cfg(task, play=op in ('play', 'onnx')), load_rl_cfg(task)
        apply_recipe(cfg, agent, req)
        configure_evaluation_events(cfg, req)
        cfg.scene.num_envs = 1
        prepare_config(cfg, req)
        return cfg, req

    def test_ordinary_viewer_preserves_rough_terrain_and_train_export_preview_are_untouched(self):
        from mjlab.tasks.registry import load_env_cfg
        from training.recovery_evaluation import prepare_config, STARTUP_EVENT
        from training.recipe import plain
        cfg, _ = self.configuration(specialist=False, rough=True)
        self.assertEqual(cfg.scene.terrain.terrain_type, 'generator')
        self.assertIsNotNone(cfg.scene.terrain.terrain_generator)
        self.assertIn(STARTUP_EVENT, cfg.events)
        for op in ('train', 'preflight', 'preview', 'export', 'describe'):
            cfg = load_env_cfg('Mjlab-StandUp-Flat-MicroDuck')
            before = copy.deepcopy(plain(cfg))
            prepare_config(cfg, {'op': op, 'engine': 'official_0151',
                                 'task': 'Mjlab-StandUp-Flat-MicroDuck', 'recovery_evaluation': True})
            self.assertEqual(plain(cfg), before)

    def test_pt_and_onnx_prepare_the_same_evaluation(self):
        from training.recipe import plain
        pt, _ = self.configuration(op='play', rough=True)
        onnx, _ = self.configuration(op='onnx', rough=True)
        self.assertEqual(plain(pt), plain(onnx))
        self.assertEqual(pt.scene.terrain.terrain_type, 'plane')
        self.assertIsNone(pt.scene.terrain.terrain_generator)

    def test_real_reset_manager_has_mature_mix_exact_body_axes_and_clean_histories(self):
        import torch
        import mujoco
        from mjlab.envs import ManagerBasedRlEnv
        from training.recovery_evaluation import GROUND_EVENT, geom_lowest_z, GROUND_CLEARANCE_M

        cfg, _ = self.configuration()
        env = ManagerBasedRlEnv(cfg, device='cpu')
        try:
            self.assertEqual(env._studio_recovery_evaluation['final_mix'],
                             {'standing_prob': .15, 'sitting_prob': .20,
                              'face_down_prob': .30, 'face_up_prob': .35})
            self.assertFalse(env.curriculum_manager.active_terms)
            term = env.event_manager.get_term_cfg(GROUND_EVENT)
            self.assertIsNot(term, env.cfg.events[GROUND_EVENT])
            # Opposite checkpoint counters cannot send ONNX back to stage zero.
            for counter in (0, 11000 * 24):
                env.common_step_counter = counter
                env.curriculum_manager.compute()
                self.assertEqual(term.params['source_params']['face_up_prob'], .35)
            # Ground-frame gravity proves the axis/sign, independent of random yaw.
            expected = {'back_flat': [-1., 0., 0.], 'left_side': [0., 1., 0.],
                        'right_side': [0., -1., 0.], 'face_down': [1., 0., 0.]}
            for pose, gravity in expected.items():
                term.params['pose'] = pose
                env.reset()
                actual = env.scene['robot'].data.projected_gravity_b[0]
                torch.testing.assert_close(actual, torch.tensor(gravity), rtol=0, atol=2e-6)
                self.assertTrue(bool((env.sim.data.qvel == 0).all()))
                for name in ('twist', 'head_pose', 'body_pose'):
                    self.assertTrue(bool((env.command_manager.get_term(name).command == 0).all()))
                scratch = env._studio_recovery_kinematics
                scratch.qpos[:] = env.sim.data.qpos[0].detach().cpu().numpy()
                mujoco.mj_kinematics(env.sim.mj_model, scratch)
                model = env.sim.mj_model
                floor = next(i for i in range(model.ngeom) if model.geom_type[i] == mujoco.mjtGeom.mjGEOM_PLANE)
                body_geoms = [i for i in env.scene['robot'].data.indexing.geom_ids.tolist() if
                              ((int(model.geom_contype[i]) & int(model.geom_conaffinity[floor])) or
                               (int(model.geom_conaffinity[i]) & int(model.geom_contype[floor])))]
                self.assertAlmostEqual(min(geom_lowest_z(model, scratch, i) for i in body_geoms)
                                       - float(scratch.geom_xpos[floor, 2]), GROUND_CLEARANCE_M, places=6)
            env.step(torch.full((1, 14), .2))
            term.params['pose'] = 'back_flat'
            env.reset()
            self.assertTrue(bool((env.action_manager.action == 0).all()))
            joint_term = env.action_manager.get_term('joint_pos')
            self.assertTrue(bool(joint_term._filter_first.all()))
            self.assertTrue(bool((joint_term._previous_filtered == 0).all()))
            for name in ('_prev_leg_actions', '_prev_neck_actions'):
                if hasattr(env, name):
                    self.assertTrue(bool((getattr(env, name) == 0).all()))
            print('RECOVERY_REAL_MANAGER_AXES_GROUNDING_AND_HISTORY_OK', flush=True)
        finally:
            env.close()

    def test_real_specialist_viewer_starts_repositions_and_reports_trials(self):
        import io
        import torch
        from unittest.mock import patch
        from mjlab.envs import ManagerBasedRlEnv
        from mjlab.rl import RslRlVecEnvWrapper
        from training.runtime_adapter import viewer_class
        cfg, req = self.configuration(op='play')
        env = RslRlVecEnvWrapper(ManagerBasedRlEnv(cfg, device='cpu'))

        class ZeroPolicy:
            def __call__(self, observations):
                return torch.zeros((1, 14))

        try:
            with patch('training.runtime_adapter.sys.stdin', io.StringIO()), \
                 patch('training.runtime_adapter.emit') as report:
                viewer = viewer_class(req)(env, ZeroPolicy())
                try:
                    viewer.setup()
                    self.assertEqual(viewer._recovery.current['pose'], 'back_flat')
                    self.assertIsNotNone(viewer._recovery_status)
                    self.assertTrue(viewer._execute_step(), viewer._last_error)
                    # Even an enabled native Viser joystick must not put a
                    # command into the next cached actor observation.
                    twist = env.unwrapped.command_manager.get_term('twist')
                    twist._joystick_enabled.value = True
                    twist._joystick_sliders[0].max = 1.0
                    twist._joystick_sliders[0].min = -1.0
                    twist._joystick_sliders[0].value = .3
                    self.assertTrue(viewer._execute_step(), viewer._last_error)
                    self.assertTrue(bool((env.get_observations()['actor'][:, -13:] == 0).all()))
                    viewer._recovery.mode = 'left_side'
                    viewer.reset_environment()
                    self.assertEqual(viewer._recovery.counts['back_flat']['cancelled'], 1)
                    torch.testing.assert_close(env.unwrapped.scene['robot'].data.projected_gravity_b[0],
                                               torch.tensor([0., 1., 0.]), rtol=0, atol=2e-6)
                    viewer.telemetry()
                    receipts = [call.kwargs['data'] for call in report.call_args_list if call.args[0] == 'sim_state']
                    self.assertEqual(receipts[-1]['recovery_evaluation']['pose'], 'left_side')
                    self.assertFalse(receipts[-1]['recovery_evaluation']['contact_verified'])
                    viewer._pose_snapshot_requests.put(True)
                    viewer._drain_pose_snapshots()
                    records = [json.loads(call.kwargs['line'].split(' ', 1)[1])
                               for call in report.call_args_list if call.args[0] == 'log'
                               and call.kwargs['line'].startswith('MICRODUCK_POSE_RECORD ')]
                    self.assertEqual(records[-1]['trial']['pose'], 'left_side')
                    self.assertTrue(records[-1]['contacts']['available'], records[-1]['contacts'])
                    self.assertTrue(records[-1]['finite_qpos_qvel'])
                finally:
                    viewer.close()
                viewer.close()
                print('RECOVERY_REAL_VISER_START_REPOSITION_REPORT_CLOSE_OK', flush=True)
        finally:
            env.close()

    def test_real_ordinary_viewer_pose_record_preserves_rough_commands_and_state(self):
        import io
        import torch
        from unittest.mock import patch
        from mjlab.envs import ManagerBasedRlEnv
        from mjlab.rl import RslRlVecEnvWrapper
        from training.runtime_adapter import viewer_class
        cfg, req = self.configuration(op='onnx', specialist=False, rough=True)
        env = RslRlVecEnvWrapper(ManagerBasedRlEnv(cfg, device='cpu'))
        try:
            with patch('training.runtime_adapter.sys.stdin', io.StringIO()), \
                 patch('training.runtime_adapter.emit') as report:
                viewer = viewer_class(req)(env, lambda _: torch.zeros((1, 14)))
                try:
                    viewer.setup()
                    self.assertIsNone(viewer._recovery)
                    self.assertIsNotNone(viewer._pose_snapshot_status)
                    raw = env.unwrapped
                    raw.command_manager.get_term('twist').command[0, :3] = torch.tensor([.23, -.11, .31])
                    before_qpos, before_qvel = raw.sim.data.qpos.clone(), raw.sim.data.qvel.clone()
                    before_step = raw.episode_length_buf.clone()
                    viewer._pose_snapshot_requests.put(True)
                    viewer._drain_pose_snapshots()
                    records = [json.loads(call.kwargs['line'].split(' ', 1)[1])
                               for call in report.call_args_list if call.args[0] == 'log'
                               and call.kwargs['line'].startswith('MICRODUCK_POSE_RECORD ')]
                    self.assertEqual(len(records), 1, report.call_args_list)
                    snapshot = records[0]
                    self.assertEqual(snapshot['terrain']['type'], 'generator')
                    self.assertIsNone(snapshot['trial'])
                    self.assertTrue(snapshot['contacts']['available'], snapshot['contacts'])
                    self.assertEqual(len(snapshot['joint_names']), len(snapshot['joint_pos']))
                    self.assertEqual(len(snapshot['joint_ids']), len(snapshot['joint_pos']))
                    torch.testing.assert_close(torch.tensor(snapshot['commands']['twist'][:3]), torch.tensor([.23, -.11, .31]))
                    torch.testing.assert_close(raw.sim.data.qpos.clone(), before_qpos)
                    torch.testing.assert_close(raw.sim.data.qvel.clone(), before_qvel)
                    torch.testing.assert_close(raw.episode_length_buf, before_step)
                    for position, address in zip(snapshot['joint_pos'], snapshot['joint_qpos_addresses']):
                        self.assertAlmostEqual(position, snapshot['qpos'][address])
                    print('RECOVERY_REAL_ORDINARY_ROUGH_NONZERO_COMMAND_POSE_RECORD_OK', flush=True)
                finally:
                    viewer.close()
        finally:
            env.close()


if __name__ == '__main__':
    unittest.main()

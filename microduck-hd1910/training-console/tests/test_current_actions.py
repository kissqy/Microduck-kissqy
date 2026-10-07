"""Deployed action coverage, historical physics, and real HD1910 gear play."""
import copy
import json
import math
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
from training.official_spec import TASKS, CATALOG, DEFAULT_TASK, contract, compare_contracts
from training.deployment import deployment_contract, manifest_for


def reference(task):
    return json.loads((ROOT/'data/task-configs'/(task+'.json')).read_text())['inspection']


class CurrentActionTests(unittest.TestCase):
    def test_removed_new_recipe_keeps_historical_play_and_sitstand_mapping(self):
        import training_console as tc
        with tempfile.TemporaryDirectory() as directory, patch.object(tc.BaseTrainingManager, '_run'):
            manager = tc.TrainingManager(Path(directory))
            manager.computer_verified = True
            try:
                sit = 'Mjlab-SitStand-Flat-MicroDuck'
                old = 'Mjlab-SitStand-Rough-MicroDuck'
                with self.assertRaisesRegex(ValueError, '固定动作系数1.0'):
                    manager.launch('train', {'task':sit,'training_action_scale':.9})
                with self.assertRaisesRegex(ValueError, '旧配方'):
                    manager.launch('train', {'task':old})
                job = manager.jobs[manager.launch('train', {'task':sit})['job_id']]
                self.assertEqual(job['request']['training_action_scale'], 1)
                # A genuine saved run from the old catalog keeps its original ID.
                job['request']['task'] = old
                job['revision'] = job['request']['baseline_pin']['revision']
                job['status'] = 'completed'
                job['checkpoints'] = [{'path':'/fixture/model_1000.pt','iteration':1000}]
                pick = {'source_job':job['id'],'checkpoint':'/fixture/model_1000.pt'}
                played = manager.jobs[manager.launch('play', pick)['job_id']]
                self.assertEqual(played['request']['task'], old)
                played['status'] = 'completed'
                exported = manager.jobs[manager.launch('export', pick)['job_id']]
                self.assertEqual(exported['request']['task'], old)
                self.assertFalse(any(j['op'] in ('probe','preflight','setup') for j in manager.jobs.values()))
            finally:
                manager.close()

    def test_current_set_and_no_duplicate_action_entries(self):
        roles = [p['role'] for p in CATALOG['profiles']]
        self.assertEqual(len(roles), len(set(roles)))
        self.assertEqual(set(roles), {'joint','sitstand','ground_pick','kick_left','kick_right',
                                     'roulade','walk','stand','roller','crouch'})
        self.assertEqual(DEFAULT_TASK, 'Mjlab-VelStand-Rough-Backlash-MicroDuck')
        for profile in CATALOG['profiles']:
            self.assertIn(profile['default_task'], profile['variants'])
            self.assertTrue(all(TASKS[t]['enabled'] for t in profile['variants']))
        self.assertFalse(any(any(x in t for x in ('Swizzle','Slope','Spin','RollerStandUp')) for t in TASKS))
        for t in ('Mjlab-SitStand-Rough-MicroDuck','Mjlab-GroundPick-Rough-MicroDuck'):
            self.assertFalse(TASKS[t]['enabled'])
            self.assertEqual(reference(t)['task'], t)  # original history is not relabelled

    def test_exact_gear_play_and_teacher_matching(self):
        joint = reference(DEFAULT_TASK)
        self.assertEqual(joint['model']['gear_backlash']['joint_count'], 14)
        for lo, hi in joint['model']['gear_backlash']['ranges_rad'].values():
            self.assertAlmostEqual(lo, -math.pi/180)
            self.assertAlmostEqual(hi, math.pi/180)
        for family in ('Velocity','StandUp'):
            task = f'Mjlab-{family}-Rough-Backlash-MicroDuck'
            compare_contracts(contract(reference(task)), contract(joint))
            plain = reference(f'Mjlab-{family}-Rough-MicroDuck')
            # Official gear-play twins retain the same output-encoder policy
            # interface. Existing plain teachers may teach a backlash student;
            # their original physics must remain in the migration receipt.
            compare_contracts(contract(plain), contract(joint))
            self.assertFalse(plain['model']['gear_backlash']['enabled'])

    def test_left_right_and_roller_deployment_are_distinct(self):
        for task, info in TASKS.items():
            ins = reference(task)
            c = deployment_contract({'task': task}, ins)
            m = manifest_for({'task': task}, c, 'a'*64)
            self.assertEqual(m['action_len'], 14)
            self.assertEqual(c['gear_backlash']['enabled'], info['backlash'])
            if info['role'] in ('kick_left','kick_right'):
                self.assertEqual(m['name'], info['role'])
                self.assertEqual(m['duration_s'], .5)
            if info['role'] in ('roller','crouch'):
                self.assertEqual(m['mode'], 'roller')
            if info['role'] == 'crouch':
                self.assertEqual(m['command']['period_s'], 5)
                self.assertEqual(m['duration_s'], 3.5)


UPSTREAM = os.environ.get('MICRODUCK_OFFICIAL_SOURCE')


@unittest.skipUnless(UPSTREAM, 'Pinned official source not supplied')
class RealGearPlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(Path(UPSTREAM)/'src'))
        import mjlab.tasks, mjlab_microduck.tasks
        from training.official_adapter import register_tasks
        register_tasks()
        import torch
        torch.set_num_threads(2)

    def cfg(self, task):
        from mjlab.tasks.registry import load_env_cfg, load_rl_cfg
        from training.runtime_adapter import apply_recipe
        from studio import fresh_recipe
        cfg, agent = load_env_cfg(task), load_rl_cfg(task)
        apply_recipe(cfg, agent, {'engine':'official_0151','task':task,'op':'train',
                                 'studio_recipe':fresh_recipe(), 'training_action_scale':.9,
                                 'action_filter':{'enabled':True,'head_alpha':.5,'legs_alpha':.7}})
        cfg.scene.num_envs = 2
        return cfg, agent

    def test_real_feedback_position_velocity_partial_reset_and_friction(self):
        import torch
        from mjlab.envs import ManagerBasedRlEnv
        from training.hd1910_actuator import Hd1910BacklashActuator
        from mjlab_microduck.actuator.friction_dr_bam import FrictionDRBamActuator
        from mjlab_microduck.actuator.friction_dr_bam import BacklashEncoderBamActuatorCfg
        from training.official_adapter import adapt_robot
        from mjlab_microduck.tasks import mdp
        cfg, _ = self.cfg('Mjlab-Velocity-Flat-Backlash-MicroDuck')
        self.assertIsInstance(cfg.scene.entities['robot'].articulation.actuators[0], BacklashEncoderBamActuatorCfg)
        adapt_robot(cfg, None, {'op':'train','task':'Mjlab-Velocity-Flat-Backlash-MicroDuck'})
        self.assertIsInstance(cfg.scene.entities['robot'].articulation.actuators[0], BacklashEncoderBamActuatorCfg)
        env = ManagerBasedRlEnv(cfg, device='cpu')
        try:
            env.reset()
            robot = env.scene['robot']; act = robot.actuators[0]
            self.assertIsInstance(act, Hd1910BacklashActuator)
            self.assertIsInstance(act, FrictionDRBamActuator)
            self.assertEqual(int(act._backlash_mask.sum()), 14)
            motor_ids = act.target_ids
            passive_ids = act._backlash_joint_ids
            robot.write_joint_state_to_sim(torch.full((2,14), .10), torch.full((2,14), .20), joint_ids=motor_ids)
            robot.write_joint_state_to_sim(torch.full((2,14), .01), torch.full((2,14), .03), joint_ids=passive_ids)
            command = act.get_command(robot.data)
            torch.testing.assert_close(command.pos, torch.full((2,14), .11))
            torch.testing.assert_close(command.vel, torch.full((2,14), .20))
            asset = env.observation_manager.get_term_cfg('actor', 'joint_vel').params['asset_cfg']
            # Actor observes output-side velocity; BAM back-EMF uses motor-side velocity.
            torch.testing.assert_close(mdp.joint_vel_rel_backlash(env, asset_cfg=asset), torch.full((2,14), .23))
            act._bam_model.actuator.q_target_smooth.fill_(9)
            act._goal_reset_pending.zero_(); act.reset(torch.tensor([0]))
            act.compute(command)
            self.assertFalse(bool(act._goal_reset_pending.any()))
            self.assertLess(float(act._bam_model.actuator.q_target_smooth[0].max()), 1)
            self.assertGreater(float(act._bam_model.actuator.q_target_smooth[1].min()), 1)
            env.reset()
            for _ in range(3):
                obs, reward, *_ = env.step(torch.zeros(2,14))
                self.assertEqual(obs['actor'].shape, (2,61))
                self.assertTrue(torch.isfinite(reward).all())
            self.assertGreaterEqual(float(act.friction_scale.min()), .9)
            self.assertLessEqual(float(act.friction_scale.max()), 1.1)
            print('REAL_HD1910_BACKLASH_POSITION_VELOCITY_RESET_FRICTION_AND_61x14_OK', flush=True)
        finally:
            env.close()

    def test_left_factory_and_roll_crouch_real_envs(self):
        import torch
        from mjlab.envs import ManagerBasedRlEnv
        from mjlab.tasks.registry import load_env_cfg
        from training.recipe import plain
        left = load_env_cfg('Mjlab-BallKickLeft-Flat-MicroDuck')
        right = load_env_cfg('Mjlab-BallKick-Flat-MicroDuck')
        self.assertNotEqual(plain(left.events), plain(right.events))
        for task in ('Mjlab-BallKickLeft-Flat-Backlash-MicroDuck', 'Mjlab-RollerCrouch-Flat-Backlash-MicroDuck'):
            cfg, _ = self.cfg(task)
            env = ManagerBasedRlEnv(cfg, device='cpu')
            try:
                env.reset()
                obs, reward, *_ = env.step(torch.zeros(2,14))
                self.assertEqual(obs['actor'].shape, (2,61))
                self.assertTrue(torch.isfinite(reward).all())
            finally:
                env.close()

    def test_backlash_ppo_checkpoint_and_official_onnx_export(self):
        import numpy as np
        import torch
        import onnxruntime as ort
        from dataclasses import asdict
        from mjlab.envs import ManagerBasedRlEnv
        from mjlab.rl import MjlabOnPolicyRunner, RslRlVecEnvWrapper
        from training.runtime_adapter import export
        from studio import fresh_recipe
        task = 'Mjlab-Velocity-Flat-Backlash-MicroDuck'
        cfg, agent = self.cfg(task)
        agent.upload_model = False; agent.logger = 'tensorboard'
        env = RslRlVecEnvWrapper(ManagerBasedRlEnv(cfg, device='cpu'), clip_actions=agent.clip_actions)
        try:
            with tempfile.TemporaryDirectory() as d:
                runner = MjlabOnPolicyRunner(env, asdict(agent), d, 'cpu')
                runner.learn(num_learning_iterations=1, init_at_random_ep_len=False)
                cp = Path(d)/'model_1000.pt'; runner.save(str(cp))
                req = {'engine':'official_0151','op':'export','task':task,'checkpoint':str(cp),
                       'studio_recipe':fresh_recipe(), 'export_path':str(Path(d)/'policy.onnx'),
                       'policy_parameters':{'training_action_scale':.9,
                                            'action_filter':{'enabled':True,'head_alpha':.5,'legs_alpha':.7}}}
                export(req)
                obs = env.get_observations()
                with torch.no_grad(): expected = runner.get_inference_policy(device='cpu')(obs).numpy()
                session = ort.InferenceSession(req['export_path'], providers=['CPUExecutionProvider'])
                actual = session.run(None, {'obs':obs['actor'][:1].numpy()})[0]
                np.testing.assert_allclose(actual, expected[:1], rtol=1e-4, atol=1e-5)
                self.assertEqual(session.get_inputs()[0].shape, [1,61])
                self.assertEqual(session.get_outputs()[0].shape, [1,14])
                deployed = json.loads(Path(req['export_path']).with_suffix('.contract.json').read_text())
                self.assertEqual(deployed['gear_backlash']['joint_count'], 14)
                self.assertEqual(deployed['required_policy_settings']['action_scale'], .9)
                self.assertEqual(deployed['required_policy_settings']['head_lowpass'], .5)
                self.assertEqual(deployed['required_policy_settings']['legs_lowpass'], .7)
                print('REAL_BACKLASH_CPU_PPO_PT_ONNX_61x14_RAW_OUTPUT_AND_DEPLOYMENT_OK', flush=True)
        finally:
            env.close()


if __name__ == '__main__':
    unittest.main()

"""Real CPU mjlab tests. Enable with MICRODUCK_OFFICIAL_SOURCE=<pinned checkout>."""
import copy
import os
import sys
import unittest
from pathlib import Path

UPSTREAM = os.environ.get('MICRODUCK_OFFICIAL_SOURCE')
TRIAL = {'enabled': True, 'head_alpha': .5, 'legs_alpha': .7, 'version': 1}


@unittest.skipUnless(UPSTREAM, 'Pinned official source not supplied')
class UpstreamActionFilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(Path(UPSTREAM)/'src'))
        import mjlab.tasks, mjlab_microduck.tasks
        from training.official_adapter import register_tasks
        register_tasks()
        import torch
        torch.set_num_threads(2)

    def cfg(self, task, enabled=True):
        from mjlab.tasks.registry import load_env_cfg, load_rl_cfg
        from training.runtime_adapter import apply_recipe
        from studio import fresh_recipe
        from training.official_spec import ENGINE
        cfg, agent = load_env_cfg(task), load_rl_cfg(task)
        apply_recipe(cfg, agent, {'engine': ENGINE, 'op': 'train', 'task': task,
                                  'studio_recipe': fresh_recipe(),
                                  'action_filter': {**TRIAL, 'enabled': enabled}})
        return cfg, agent

    def test_all_tasks_only_action_term_changes_and_explanations_are_complete(self):
        from dataclasses import asdict
        from training.official_spec import TASKS, contract, compare_contracts, WALK, STAND, JOINT, new_training_action_scale
        from training.recipe import inspect_configs, plain
        from training.action_filter import from_action
        from training.deployment import deployment_contract
        inspections = {}
        for task in TASKS:
            cfg, agent = self.cfg(task); base, base_agent = self.cfg(task, False)
            a, b = plain(cfg), plain(base)
            del a['actions']; del b['actions']
            self.assertEqual(a, b)
            self.assertEqual(asdict(agent), asdict(base_agent))
            self.assertEqual(cfg.actions['joint_pos'].scale, new_training_action_scale(task))
            self.assertEqual(from_action(cfg.actions['joint_pos']), TRIAL)
            ins = inspect_configs(task, cfg, agent); inspections[task] = ins
            from training.explanations import annotate_rows
            rows=annotate_rows(ins['rows'])
            self.assertFalse(any(r['help'].get('documentation_missing') for r in rows))
            self.assertEqual(deployment_contract({'task': task}, ins)['required_policy_settings']['head_lowpass'], .5)
        for task in (WALK, STAND):
            compare_contracts(contract(inspections[task]), contract(inspections[JOINT]))
        print('ALL_CURRENT_TASKS_FILTER_AND_EXPORTED_SETTINGS_OK', flush=True)

    def test_selected_scale_controls_actual_targets_and_deployment(self):
        import torch
        from mjlab.envs import ManagerBasedRlEnv
        from mjlab.tasks.registry import load_env_cfg, load_rl_cfg
        from training.runtime_adapter import apply_recipe
        from training.official_spec import ENGINE, WALK
        from training.recipe import inspect_configs
        from training.deployment import deployment_contract
        from studio import fresh_recipe
        for scale in (.7, .9, 1.0):
            cfg,agent=load_env_cfg(WALK),load_rl_cfg(WALK)
            req={'engine':ENGINE,'op':'train','task':WALK,'studio_recipe':fresh_recipe(),
                 'training_action_scale':scale,'action_filter':TRIAL}
            apply_recipe(cfg,agent,req)
            self.assertEqual(cfg.actions['joint_pos'].scale,scale)
            c=deployment_contract(req,inspect_configs(WALK,cfg,agent))
            self.assertEqual(c['trained_action_scale'],scale)
            self.assertEqual(c['required_policy_settings']['action_scale'],scale)
            cfg.scene.num_envs=2
            env=ManagerBasedRlEnv(cfg,device='cpu')
            try:
                env.reset()
                term=env.action_manager.get_term('joint_pos')
                raw=torch.full((2,14),.2)
                env.action_manager.process_action(raw)
                torch.testing.assert_close(term._processed_actions,term.offset+scale*raw)
                torch.testing.assert_close(env.action_manager.action,raw)
            finally:env.close()
        print('SELECTED_07_09_10_REACH_REAL_TARGETS_AND_DEPLOYMENT_OK',flush=True)

    def test_actual_action_manager_recursion_raw_observations_partial_reset_and_decimation(self):
        import torch
        from mjlab.envs import ManagerBasedRlEnv
        from training.official_spec import WALK
        from training.action_filter import HEAD_JOINTS, LEG_JOINTS
        cfg, _ = self.cfg(WALK); cfg.scene.num_envs = 2
        env = ManagerBasedRlEnv(cfg, device='cpu')
        try:
            env.reset()
            manager = env.action_manager; term = manager.get_term('joint_pos')
            self.assertEqual(set(term.target_names), set(HEAD_JOINTS+LEG_JOINTS))
            alpha = torch.tensor([.5 if n in HEAD_JOINTS else .7 for n in term.target_names])
            home = term.offset.clone()
            first = torch.full((2, 14), .2)
            manager.process_action(first)
            torch.testing.assert_close(term._processed_actions, home+.9*first)
            torch.testing.assert_close(manager.action, first)
            second = torch.full((2, 14), -.4)
            manager.process_action(second)
            expected = alpha*(home+.9*second)+(1-alpha)*(home+.9*first)
            torch.testing.assert_close(term._processed_actions, expected)
            torch.testing.assert_close(manager.action, second)
            torch.testing.assert_close(manager.prev_action, first)
            torch.testing.assert_close(term.raw_action, second)
            # Physics repeats may only apply the cached target, never re-filter.
            for _ in range(cfg.decimation): manager.apply_action()
            torch.testing.assert_close(term._processed_actions, expected)
            torch.testing.assert_close(term._entity.data.joint_pos_target[:, term.target_ids], expected-term._entity.data.encoder_bias[:, term.target_ids])
            manager.reset(torch.tensor([0]))
            third = torch.full((2, 14), .6)
            manager.process_action(third)
            torch.testing.assert_close(term._processed_actions[0], (home+.9*third)[0])
            torch.testing.assert_close(term._processed_actions[1], (alpha*(home+.9*third)+(1-alpha)*expected)[1])
            manager.reset()
            env.step(first)
            before = term._processed_actions.clone()
            env.step(second)
            torch.testing.assert_close(term._processed_actions, alpha*(home+.9*second)+(1-alpha)*before)
            obs = env.observation_manager.compute()['actor']
            self.assertTrue(torch.isfinite(obs).all())
            torch.testing.assert_close(manager.action, second)
            print('REAL_MANAGER_50HZ_EMA_RAW_ACTIONS_PARTIAL_RESET_AND_PHYSICS_STEPS_OK', flush=True)
        finally: env.close()


    def test_replay_and_export_configs_read_saved_filter_not_page(self):
        from mjlab.tasks.registry import load_env_cfg, load_rl_cfg
        from training.runtime_adapter import apply_recipe
        from training.action_filter import from_action
        from training.official_spec import ENGINE, WALK
        from studio import fresh_recipe
        for op in ('play','onnx','export'):
            for saved in (TRIAL, None):
                with self.subTest(op=op,saved=saved):
                    cfg,agent=load_env_cfg(WALK,play=True),load_rl_cfg(WALK)
                    req={'engine':ENGINE,'op':op,'task':WALK,'studio_recipe':fresh_recipe(),
                         'action_filter':{'enabled':True,'head_alpha':.2,'legs_alpha':.3},
                         'policy_parameters':{'training_action_scale':1.0,'action_filter':saved}}
                    apply_recipe(cfg,agent,req)
                    actual=from_action(cfg.actions['joint_pos'])
                    self.assertEqual(actual['enabled'],saved is not None)
                    if saved is not None:self.assertEqual(actual,TRIAL)

    def test_real_ppo_checkpoint_official_export_and_raw_onnx_policy_match(self):
        import json
        import tempfile
        from dataclasses import asdict
        from unittest.mock import patch
        import numpy as np
        import torch
        import onnx
        import onnxruntime as ort
        from mjlab.envs import ManagerBasedRlEnv
        from mjlab.rl import MjlabOnPolicyRunner, RslRlVecEnvWrapper
        import mjlab_microduck.export as official
        from training.runtime_adapter import export
        from training.official_spec import ENGINE, WALK
        from studio import fresh_recipe
        cfg, agent = self.cfg(WALK); cfg.scene.num_envs=2
        agent.upload_model=False; agent.logger='tensorboard'
        env=RslRlVecEnvWrapper(ManagerBasedRlEnv(cfg,device='cpu'),clip_actions=agent.clip_actions)
        try:
            with tempfile.TemporaryDirectory() as d:
                runner=MjlabOnPolicyRunner(env,asdict(agent),d,'cpu')
                runner.learn(num_learning_iterations=1,init_at_random_ep_len=False)
                cp=Path(d)/'model_1000.pt'; runner.save(str(cp))
                req={'op':'export','engine':ENGINE,'task':WALK,'checkpoint':str(cp),
                     'studio_recipe':fresh_recipe(),'policy_parameters':{'training_action_scale':.9,'action_filter':TRIAL},
                     'export_path':str(Path(d)/'policy.onnx')}
                with patch.object(official,'load_env_cfg',official.load_env_cfg), patch.object(official,'load_rl_cfg',official.load_rl_cfg):
                    export(req)
                policy=runner.get_inference_policy(device='cpu')
                obs=env.get_observations()
                with torch.no_grad():raw=policy(obs).detach().numpy()
                session=ort.InferenceSession(req['export_path'],providers=['CPUExecutionProvider'])
                actual=session.run(None,{'obs':obs['actor'][:1].detach().numpy()})[0]
                np.testing.assert_allclose(actual,raw[:1],rtol=1e-4,atol=1e-5)
                model=onnx.load(req['export_path'])
                metadata={v.key:v.value for v in model.metadata_props}
                self.assertTrue(json.loads(metadata['microduck.action_filter'])['enabled'])
                contract=json.loads(Path(req['export_path']).with_suffix('.contract.json').read_text())
                self.assertEqual(contract['required_policy_settings']['head_lowpass'],.5)
                self.assertEqual(contract['required_policy_settings']['legs_lowpass'],.7)
                self.assertEqual(contract['required_policy_settings']['action_scale'],.9)
                self.assertEqual(session.get_inputs()[0].shape,[1,61])
                self.assertEqual(session.get_outputs()[0].shape,[1,14])
                print('REAL_CPU_PPO_PT_OFFICIAL_ONNX_RAW_OUTPUT_AND_FILTER_PROFILE_OK',flush=True)
        finally:env.close()


if __name__ == '__main__': unittest.main()

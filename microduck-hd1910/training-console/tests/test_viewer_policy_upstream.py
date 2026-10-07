"""Opt-in real CPU physics + Viser startup, with ordinary PT and ONNX policies.

MICRODUCK_VIEWER_INTEGRATION=1 and MICRODUCK_OFFICIAL_SOURCE enable this test.
It binds loopback only, uses generated test weights and never touches a robot.
"""
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

UPSTREAM = os.environ.get('MICRODUCK_OFFICIAL_SOURCE')


@unittest.skipUnless(UPSTREAM and os.environ.get('MICRODUCK_VIEWER_INTEGRATION') == '1',
                     'Opt-in pinned CPU physics and loopback Viser integration')
class RealViewerPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(Path(UPSTREAM) / 'src'))
        import mjlab.tasks, mjlab_microduck.tasks
        import torch
        torch.set_num_threads(2)

    def configuration(self, op, recorded_scale=1.0):
        from mjlab.tasks.registry import load_env_cfg, load_rl_cfg
        from training.runtime_adapter import apply_recipe, configure_evaluation_events
        from training.official_spec import ENGINE, WALK
        from studio import fresh_recipe
        req = {'engine': ENGINE, 'op': op, 'task': WALK,
               'studio_recipe': fresh_recipe(), 'training_action_scale': .7,
               'policy_parameters': {'training_action_scale': recorded_scale},
               'inference_scale': .7}  # An old page cannot add a second multiplier.
        cfg, agent = load_env_cfg(WALK, play=op != 'train'), load_rl_cfg(WALK)
        apply_recipe(cfg, agent, req)
        configure_evaluation_events(cfg, req)
        cfg.scene.num_envs = 1
        return req, cfg, agent

    def test_new_training_uses_one_and_replay_retains_recorded_mapping(self):
        for op, recorded, expected in (('train', .7, .9), ('play', .7, .7),
                                        ('onnx', 1., 1.), ('export', .7, .7)):
            with self.subTest(op=op):
                _, cfg, _ = self.configuration(op, recorded)
                self.assertEqual(cfg.actions['joint_pos'].scale, expected)

    def run_viewer(self, op):
        import numpy as np
        import torch
        from mjlab.envs import ManagerBasedRlEnv
        from mjlab.rl import RslRlVecEnvWrapper
        from rsl_rl.models import MLPModel
        from training.runtime_adapter import viewer_class
        from training.sim_protocol import OnnxPolicy
        req, cfg, agent = self.configuration(op)
        env = RslRlVecEnvWrapper(ManagerBasedRlEnv(cfg, device='cpu'),
                                clip_actions=agent.clip_actions)
        self.addCleanup(env.close)
        obs = env.get_observations()
        with tempfile.TemporaryDirectory() as directory:
            if op == 'play':
                original = MLPModel(obs, agent.obs_groups, 'actor', env.num_actions,
                                    hidden_dims=(16,), obs_normalization=True).eval()
                checkpoint = Path(directory) / 'test_actor.pt'
                torch.save(original.state_dict(), checkpoint)
                policy = MLPModel(obs, agent.obs_groups, 'actor', env.num_actions,
                                  hidden_dims=(16,), obs_normalization=True).eval()
                policy.load_state_dict(torch.load(checkpoint, weights_only=True))
                req['checkpoint'] = str(checkpoint)
            else:
                import onnx
                from onnx import TensorProto, helper, numpy_helper
                groups = agent.obs_groups['actor']
                width = sum(obs[k].shape[-1] for k in groups)
                path = Path(directory) / 'test_policy.onnx'
                output = np.full((1, env.num_actions), .2, dtype=np.float32)
                graph = helper.make_graph(
                    [helper.make_node('Constant', [], ['actions'],
                                      value=numpy_helper.from_array(output))],
                    'viewer-policy-test',
                    [helper.make_tensor_value_info('obs', TensorProto.FLOAT, [1, width])],
                    [helper.make_tensor_value_info('actions', TensorProto.FLOAT, [1, env.num_actions])])
                model = helper.make_model(graph, opset_imports=[helper.make_opsetid('', 17)])
                model.ir_version = 9
                onnx.save(model, path)
                policy = OnnxPolicy(path, width, env.num_actions, groups, env.device)
                req['onnx_path'] = str(path)
            self.assertFalse(hasattr(policy, 'scale'))
            with torch.no_grad():
                before = policy(obs).clone()
            self.assertTrue(bool(before.abs().sum() > 0))
            with patch('training.runtime_adapter.sys.stdin', io.StringIO()), \
                 patch('training.runtime_adapter.emit') as emit:
                viewer = viewer_class(req)(env, policy)
                try:
                    self.assertIs(viewer.policy, policy)
                    viewer.setup()
                    self.assertTrue(any(call.args[0] == 'viewer_ready' for call in emit.call_args_list))
                    with torch.no_grad():
                        torch.testing.assert_close(viewer.policy(obs), before, rtol=0, atol=0)
                    for _ in range(2):
                        self.assertTrue(viewer._execute_step(), viewer._last_error)
                    viewer.telemetry()
                    self.assertTrue(any(call.args[0] == 'sim_state' for call in emit.call_args_list))
                finally:
                    viewer.close()
                viewer.close()  # Repeated shutdown is safe.
            print('REAL_VIEWER_START_STEP_CLOSE_OK', op, type(policy).__name__, flush=True)

    def test_pt_mlp_without_scale_starts_steps_and_closes(self):
        self.run_viewer('play')

    def test_onnx_without_scale_starts_steps_and_closes(self):
        self.run_viewer('onnx')


if __name__ == '__main__':
    unittest.main()

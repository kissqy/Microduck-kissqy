"""Actual pinned factories and CPU physics for restored rough action variants."""
import os
import sys
import unittest
from pathlib import Path

UPSTREAM = os.environ.get('MICRODUCK_OFFICIAL_SOURCE')


@unittest.skipUnless(UPSTREAM, 'Pinned official source not supplied')
class AddedActionPhysicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(Path(UPSTREAM) / 'src'))
        import torch
        import mjlab.tasks, mjlab_microduck.tasks
        from training.official_adapter import register_tasks
        torch.set_num_threads(2)
        register_tasks()

    def test_catalog_names_and_budgets_are_real_registered_factories(self):
        from mjlab.tasks.registry import list_tasks, load_rl_cfg
        from training.official_spec import TASKS
        for task, info in TASKS.items():
            with self.subTest(task=task):
                self.assertIn(task, list_tasks())
                self.assertEqual(info['iterations'], load_rl_cfg(task).max_iterations)

    def test_restored_rough_sitstand_and_pick_compile_reset_step(self):
        import torch
        from mjlab.envs import ManagerBasedRlEnv
        from mjlab.tasks.registry import load_env_cfg, load_rl_cfg
        from studio import fresh_recipe
        from training.runtime_adapter import apply_recipe
        from training.action_filter import from_action
        for family in ('SitStand', 'GroundPick'):
            for backlash in ('', '-Backlash'):
                task = f'Mjlab-{family}-Rough{backlash}-MicroDuck'
                with self.subTest(task=task):
                    cfg, agent = load_env_cfg(task), load_rl_cfg(task)
                    apply_recipe(cfg, agent, {'engine': 'official_0151', 'op': 'train', 'task': task,
                                              'studio_recipe': fresh_recipe(), 'training_firmware_p': 5,
                                              'training_action_scale': 1.0})
                    cfg.scene.num_envs = 2
                    self.assertEqual(cfg.scene.terrain.terrain_type, 'generator')
                    self.assertFalse(from_action(cfg.actions['joint_pos'])['enabled'])
                    env = ManagerBasedRlEnv(cfg, device='cpu')
                    try:
                        env.reset()
                        robot = env.scene['robot']
                        names = robot.joint_names
                        self.assertEqual(sum(n.startswith('passive_') and n.endswith('_backlash') for n in names), 14 if backlash else 0)
                        act = robot.actuators[0]
                        self.assertTrue(torch.all(act._bam_model.actuator.kp == 5.).item())
                        self.assertEqual(tuple(act.friction_scale.shape), (2, 1))
                        self.assertGreaterEqual(float(act.friction_scale.min()), .9)
                        self.assertLessEqual(float(act.friction_scale.max()), 1.1)
                        for _ in range(3):
                            observations, reward, *_ = env.step(torch.zeros(2, 14))
                            self.assertEqual(tuple(observations['actor'].shape), (2, 61))
                            self.assertTrue(torch.isfinite(observations['actor']).all())
                            self.assertTrue(torch.isfinite(reward).all())
                        term = env.action_manager.get_term('joint_pos')
                        raw = torch.full((2, 14), .1)
                        env.action_manager.process_action(raw)
                        torch.testing.assert_close(term._processed_actions, term.offset + raw)
                        print('CPU_NEW_ROUGH_OK', task, flush=True)
                    finally:
                        env.close()


if __name__ == '__main__':
    unittest.main()

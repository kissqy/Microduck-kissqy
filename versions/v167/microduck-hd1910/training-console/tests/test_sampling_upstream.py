"""Optional CPU integration against the pinned official checkout and dependencies.

Set MICRODUCK_OFFICIAL_SOURCE to that checkout; make its locked BAM available.
No GPU long run or policy-quality claim is made by these tests.
"""
import copy
import os
import sys
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

UPSTREAM = os.environ.get('MICRODUCK_OFFICIAL_SOURCE')


@unittest.skipUnless(UPSTREAM, 'Pinned official source not supplied')
class UpstreamSamplingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0,str(Path(UPSTREAM)/'src'))
        import mjlab.tasks, mjlab_microduck.tasks
        from training.official_adapter import register_tasks
        register_tasks()
        import torch
        torch.set_num_threads(2)

    def cfg(self, task):
        from mjlab.tasks.registry import load_env_cfg, load_rl_cfg
        from training.runtime_adapter import apply_recipe
        from training.official_spec import ENGINE
        from studio import fresh_recipe
        cfg,agent=load_env_cfg(task),load_rl_cfg(task)
        apply_recipe(cfg,agent,{'engine':ENGINE,'op':'describe','task':task,'studio_recipe':fresh_recipe()})
        return cfg,agent

    def test_all_official_configs_and_snapshot_explanations(self):
        from training.official_spec import TASKS
        from training.sample_alignment import align_curricula
        from training.recipe import inspect_configs
        for task in TASKS:
            cfg,agent=self.cfg(task);cfg.scene.num_envs=2048
            before=asdict(cfg)
            receipt=align_curricula(cfg,agent)
            after=asdict(cfg)
            self.assertEqual({k:v for k,v in before.items() if k!='curriculum'},
                             {k:v for k,v in after.items() if k!='curriculum'})
            self.assertEqual(receipt['factor'],2)
            inspection=inspect_configs(task,cfg,agent)
            self.assertTrue(inspection['rows'])
            print('ACTUAL_CONFIG_ALIGNED',task,len(receipt['stages']),flush=True)

    def test_real_joint_manager_uses_scaled_boundaries(self):
        import torch
        from mjlab.envs import ManagerBasedRlEnv
        from training.official_spec import JOINT
        from training.sample_alignment import align_curricula
        cfg,agent=self.cfg(JOINT);cfg.scene.num_envs=2048
        align_curricula(cfg,agent)
        # Keep the 2048 schedule, instantiate just two worlds to test its real
        # managers at chosen counter values without allocating a GPU batch.
        cfg.scene.num_envs=2
        env=ManagerBasedRlEnv(cfg,device='cpu')
        try:
            env.reset()
            for step,prone,crouch in ((0,0,0),(7199,0,0),(7200,0,.2),
                                      (33599,0,.2),(33600,.15,.2),(47999,.15,.2),
                                      (48000,.3,.2),(67200,.45,.2)):
                env.common_step_counter=step
                env.curriculum_manager.compute()
                params=env.event_manager.get_term_cfg('random_prone_init').params
                self.assertEqual(params['prone_prob'],prone)
                self.assertEqual(params['crouch_prob'],crouch)
            env.common_step_counter=0
            for _ in range(3):
                result=env.step(torch.zeros((2,14)))
                self.assertTrue(torch.isfinite(result[1]).all())
            print('REAL_JOINT_MANAGER_2048_BOUNDARIES_AND_CPU_STEPS_OK',flush=True)
        finally:env.close()

    def test_real_pt_save_resume_preserves_weights_and_sample_clock(self):
        import torch
        from mjlab.envs import ManagerBasedRlEnv
        from mjlab.rl import MjlabOnPolicyRunner,RslRlVecEnvWrapper
        from training.official_spec import WALK
        from training import sample_alignment as align
        official=NS(load_runner_cls=lambda task:None,MjlabOnPolicyRunner=MjlabOnPolicyRunner)
        restore=align.install(official,{},Mock());envs=[]
        try:
            with tempfile.TemporaryDirectory() as d:
                runners=[]
                for n in (2,1):
                    cfg,agent=self.cfg(WALK);cfg.scene.num_envs=n;agent.upload_model=False
                    align.align_curricula(cfg,agent)
                    env=ManagerBasedRlEnv(cfg,device='cpu');envs.append(env)
                    runners.append(official.MjlabOnPolicyRunner(RslRlVecEnvWrapper(env,clip_actions=agent.clip_actions),asdict(agent),None,'cpu'))
                first,second=runners;first.current_learning_iteration=119
                envs[0].common_step_counter=120*24
                cp=str(Path(d)/'fixture.pt');first.save(cp,{'kept':True})
                saved=torch.load(cp,map_location='cpu',weights_only=True)
                self.assertEqual(saved['infos'][align.CLOCK_KEY]['sample_count'],120*24*2)
                second.load(cp,map_location='cpu')
                self.assertEqual(second.current_learning_iteration,119)
                self.assertEqual(envs[1].common_step_counter,120*24*2)
                self.assertEqual(align.sample_count(envs[0]),align.sample_count(envs[1]))
                for key,value in first.alg.actor.state_dict().items():
                    self.assertTrue(torch.equal(value,second.alg.actor.state_dict()[key]))
                print('REAL_PT_SAVE_RESUME_WEIGHTS_AND_SAMPLE_CLOCK_OK',flush=True)
        finally:
            for env in envs:env.close()
            restore()


if __name__=='__main__':unittest.main()

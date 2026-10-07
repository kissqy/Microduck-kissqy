"""Official Python API contract and real subprocess transport, without a GPU.

The configuration fixture follows mjlab 1.3.0 TrainConfig.from_task(task) and
launch_training(task, cfg). GPU execution is replaced, never reported as tested.
"""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace as NS
from unittest.mock import Mock, patch

from training import runtime_adapter as adapter, worker

TASK='Mjlab-Velocity-Flat-MicroDuck'


def config():
    robot=NS(spec=NS(compile=lambda:NS(nu=14)))
    terms={name:NS(history_length=0) for name in ['base_ang_vel','projected_gravity','joint_pos','joint_vel','actions','command','head_command','body_command']}
    return NS(env=NS(scene=NS(num_envs=4096,entities={'robot':NS(build=lambda:robot,articulation=NS(actuators=[NS(kp_fw=5.0)]))}),
                     sim=NS(mujoco=NS(timestep=.005)),decimation=4,
                     observations={'actor':NS(terms=terms,history_length=0)},actions={'joint_pos':NS(scale=1.,use_default_offset=True)},
                     curriculum={},rewards={},events={'push_robot':object()}),
              agent=NS(actor=NS(hidden_dims=(128,128),activation='elu'),critic=NS(hidden_dims=(128,128),activation='elu'),
                       algorithm=NS(learning_rate=.001,gamma=.99,entropy_coef=.01,clip_param=.2),seed=0,
                       max_iterations=50000,save_interval=250,run_name='',logger='wandb',
                       resume=False,load_run='',load_checkpoint=''))


class TrainingApiTests(unittest.TestCase):
    def setUp(self):
        self.req={'op':'train','task':TASK,'num_envs':64,'iterations':5,'save_interval':5,'run_name':'console_test',
                  'seed':42,'learning_rate':.0003,'pushes':'off','reward_weights':{}}
        self.cfg=config();self.api=ModuleType('mjlab.scripts.train')
        self.api.TrainConfig=NS(from_task=Mock(return_value=self.cfg));self.api.launch_training=Mock()
        self.api.load_runner_cls=lambda task:None;self.api.MjlabOnPolicyRunner=type('FixtureRunner',(),{})
        self.modules=patch.dict(sys.modules,{'mjlab.scripts.train':self.api});self.modules.start()
        self.addCleanup(self.modules.stop)

    def test_official_entry_receives_environment_count_iterations_and_resume(self):
        req={**self.req,'checkpoint':'/tmp/run.with.dots/model_100.pt'}
        with patch.object(adapter,'inspect_configs',return_value={}),patch.object(adapter,'emit') as emit:
            adapter.train(req)
        self.api.launch_training.assert_called_once_with(TASK,self.cfg)
        self.assertEqual(self.cfg.env.scene.num_envs,64)
        self.assertEqual(self.cfg.agent.max_iterations,5);self.assertEqual(self.cfg.agent.save_interval,1000)
        self.assertEqual(self.cfg.agent.logger,'tensorboard');self.assertEqual(self.cfg.agent.seed,42)
        self.assertEqual(self.cfg.agent.algorithm.learning_rate,.0003);self.assertNotIn('push_robot',self.cfg.env.events)
        self.assertTrue(self.cfg.agent.resume)
        self.assertTrue(re.fullmatch(self.cfg.agent.load_run,'run.with.dots'))
        self.assertFalse(re.fullmatch(self.cfg.agent.load_run,'runXwithXdots'))
        self.assertEqual(self.cfg.agent.load_checkpoint,r'^model_100\.pt$')
        event=next(c.kwargs['data'] for c in emit.call_args_list if c.args==('effective_config',))
        self.assertEqual(event['num_envs'],64);self.assertEqual(event['iterations'],5)

    def test_preflight_uses_same_configuration_without_starting_training(self):
        req={k:v for k,v in self.req.items() if k!='run_name'}
        with patch.object(adapter,'inspect_configs',return_value={}),patch.object(adapter,'emit') as emit:
            adapter.preflight(req)
        self.assertEqual(self.cfg.env.scene.num_envs,64);self.assertEqual(self.cfg.agent.max_iterations,5)
        self.api.launch_training.assert_not_called()
        self.assertEqual(emit.call_args.kwargs['data']['checks']['action_count'],14)

    def test_missing_real_field_is_reported_before_training(self):
        del self.cfg.env.scene.num_envs
        with patch.object(adapter,'emit'),self.assertRaisesRegex(RuntimeError,'env.scene.num_envs'):
            adapter.train(self.req)
        self.api.launch_training.assert_not_called();self.assertFalse(hasattr(self.cfg.env.scene,'num_envs'))


@unittest.skipUnless(sys.platform=='linux','Linux training subprocess transport')
class TrainingTransportTests(unittest.TestCase):
    def test_launch_uses_adapter_without_cli_help_and_retains_logs_and_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);runner=root/'runner.py'
            runner.write_text("import os,sys\nassert sys.argv[1]=='python','Unexpected legacy CLI/help probe'\nos.execv(sys.executable,[sys.executable]+sys.argv[2:])\n")
            (root/'runtime_adapter.py').write_text(
                "import json,sys\nr=json.load(open(sys.argv[1]))\n"
                "assert r['num_envs']==64 and r['iterations']==5\n"
                "print('MICRODUCK_ADAPTER '+json.dumps({'kind':'log','line':'CONFIG_RECEIVED_64_ENVS_5_ITERATIONS'}))\n"
                "print('SIMULATED_TRAINER_OUTPUT',flush=True)\n"
                "if r.get('fixture_fail'): raise RuntimeError('SIMULATED_TRAINER_FAILURE')\n")
            request={'op':'train','task':TASK,'num_envs':64,'iterations':5,'run_name':'console_fixture','save_interval':5}
            for fail in (False,True):
                events=[];worker.STOP.clear()
                with self.subTest(failure=fail),patch.object(worker,'prepare',return_value=(root,[sys.executable,str(runner)],'a'*40)),\
                     patch.object(worker,'monitor_gpu'),patch.object(worker,'emit',side_effect=lambda kind,**data:events.append((kind,data))):
                    if fail:
                        with self.assertRaisesRegex(RuntimeError,'SIMULATED_TRAINER_FAILURE'):
                            worker.run_prepared({**request,'fixture_fail':True},root)
                    else: worker.run_prepared(request,root)
                logs='\n'.join(d['line'] for kind,d in events if kind=='log')
                self.assertIn('CONFIG_RECEIVED_64_ENVS_5_ITERATIONS',logs);self.assertIn('SIMULATED_TRAINER_OUTPUT',logs)
                self.assertEqual(any(kind=='complete' for kind,_ in events),not fail)


if __name__=='__main__':unittest.main()

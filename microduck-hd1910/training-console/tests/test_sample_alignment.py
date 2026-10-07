"""Sampling equivalence and resume invariants; no claimed policy equivalence."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import training_console as tc
from training import sample_alignment as align
from training.official_spec import TASKS, WALK

ROOT = Path(__file__).resolve().parents[1]


def loaded(task):
    data = json.loads((ROOT/'data/task-configs'/(task+'.json')).read_text())
    return data.get('full', data.get('inspection', {}).get('full'))


def config(full, n):
    terms = {}
    for name, term in full['env']['curriculum'].items():
        if term is None:
            terms[name] = None
        else:
            terms[name] = NS(params=copy.deepcopy(term['params']),
                             func=NS(__name__=term['func']['callable'].split('.')[-1]))
    return NS(scene=NS(num_envs=n), curriculum=terms), NS(num_steps_per_env=full['agent']['num_steps_per_env'])


class SamplingTests(unittest.TestCase):
    def test_all_twelve_tasks_keep_values_and_change_only_time_thresholds(self):
        total = 0
        for task in TASKS:
            full = loaded(task)
            for n in (1024, 2048, 4096, 8192, 3000):
                env, agent = config(full, n)
                before = copy.deepcopy(env)
                receipt = align.align_curricula(env, agent)
                self.assertGreater(len(receipt['stages']), 0, task)
                for entry in receipt['stages']:
                    total += 1
                    term, key, index = entry['term'], entry['key'], entry['index']
                    source = before.curriculum[term].params[key][index]
                    actual = env.curriculum[term].params[key][index]
                    self.assertEqual({k:v for k,v in actual.items() if k!='step'},
                                     {k:v for k,v in source.items() if k!='step'})
                    # The first active step crosses the same sample threshold;
                    # the immediately preceding step must not cross it.
                    first = actual['step'] + int(entry['strict'])
                    target = source['step'] * 4096
                    if entry['strict']:
                        self.assertGreater(first*n, target)
                        self.assertLessEqual((first-1)*n, target)
                    else:
                        self.assertGreaterEqual(first*n, target)
                        self.assertLess((first-1)*n, target)
                for name in receipt['untimed_terms']:
                    self.assertEqual(env.curriculum[name].params, before.curriculum[name].params)
                self.assertEqual(receipt, align.align_curricula(env, agent), 'must not scale twice')
        self.assertGreater(total, 500)

    def test_joint_intervals_and_4096_identity(self):
        full = loaded('Mjlab-VelStand-Flat-MicroDuck')
        for n, starts in ((4096,[0,150,700,1000,1400]),(2048,[0,300,1400,2000,2800]),
                          (1024,[0,600,2800,4000,5600])):
            env, agent = config(full,n);align.align_curricula(env,agent)
            stages=env.curriculum['prone_init_prob'].params['param_stages']
            self.assertEqual([s['step']//24 for s in stages],starts)
            self.assertEqual(stages[2]['params']['prone_prob'],.15)
            self.assertEqual(stages[3]['step']//24-1,999*4096//n+(4096//n-1))

    def test_official_defaults_are_not_mutated_or_compounded(self):
        full = loaded(WALK);env,agent=config(full,2048)
        shared=env.curriculum['action_rate_weight'].params
        old=copy.deepcopy(shared);align.align_curricula(env,agent)
        self.assertEqual(shared,old)
        env.scene.num_envs=4096;align.align_curricula(env,agent)
        self.assertEqual(env.curriculum['action_rate_weight'].params,old)
        self.assertEqual(align.budget_iterations(50000,1024),200000)


class ClockTests(unittest.TestCase):
    def run_clock(self, saved, n, request=None):
        class Runner:
            def save(self,path,infos=None):
                return {'iter':self.current_learning_iteration,
                        'infos':{**(infos or {}),'env_state':{'common_step_counter':self.env.unwrapped.common_step_counter}}}
            def load(self,path):
                self.current_learning_iteration=saved['iter']
                self.env.unwrapped.common_step_counter=saved['infos']['env_state']['common_step_counter']
                return copy.deepcopy(saved['infos'])
        original=lambda task:Runner
        official=NS(load_runner_cls=original,MjlabOnPolicyRunner=Runner)
        restore=align.install(official,request or {},Mock())
        runner=official.MjlabOnPolicyRunner();runner.env=NS(unwrapped=NS(num_envs=n,common_step_counter=0))
        runner.load('fixture.pt');restore()
        self.assertIs(official.load_runner_cls,original)
        self.assertIs(official.MjlabOnPolicyRunner,Runner)
        return runner

    def test_resume_changes_count_without_resetting_progress_or_ppo_iteration(self):
        old={'iter':700,'infos':{'env_state':{'common_step_counter':16800},
                              align.CLOCK_KEY:{'version':1,'sample_count':16800*4096}}}
        runner=self.run_clock(old,2048)
        self.assertEqual(runner.current_learning_iteration,700)
        self.assertEqual(runner.env.unwrapped.common_step_counter,33600)
        self.assertEqual(align.progress(runner.env.unwrapped)['reference_iterations'],700)
        runner.env.unwrapped.common_step_counter+=24
        saved=runner.save('unused',infos={'unrelated':'preserved'})
        self.assertEqual(saved['infos']['unrelated'],'preserved')
        again=self.run_clock(saved,4096)
        self.assertEqual(align.progress(again.env.unwrapped)['reference_iterations'],700.5)

    def test_remainder_survives_nondivisor_counts(self):
        samples=700*24*4096
        old={'iter':700,'infos':{'env_state':{'common_step_counter':16800},
                              align.CLOCK_KEY:{'version':1,'sample_count':samples}}}
        runner=self.run_clock(old,3000)
        self.assertEqual(align.sample_count(runner.env.unwrapped),samples)
        again=self.run_clock(runner.save('unused'),2048)
        self.assertEqual(align.sample_count(again.env.unwrapped),samples)

    def test_legacy_checkpoint_and_teacher_warm_start(self):
        old={'iter':1000,'infos':{'env_state':{'common_step_counter':24000}}}
        resumed=self.run_clock(old,2048,{'resume_sample_source':{'num_envs':4096}})
        self.assertEqual(resumed.env.unwrapped.common_step_counter,48000)
        teacher=self.run_clock(old,2048,{'joint':{'mode':'warm_start'}})
        self.assertEqual(align.sample_count(teacher.env.unwrapped),0)


class BackendTests(unittest.TestCase):
    def test_default_budget_scaled_once_manual_budget_is_actual(self):
        with tempfile.TemporaryDirectory() as d,patch.object(tc.BaseTrainingManager,'_run'):
            manager=tc.TrainingManager(Path(d));manager.computer_verified=True
            try:
                for n,provided,expected in ((2048,None,100000),(1024,None,200000),(2048,1234,1234)):
                    value={'task':WALK,'num_envs':n}
                    if provided is not None:value['iterations']=provided
                    job=manager.jobs[manager.launch('train',value)['job_id']]
                    self.assertEqual(job['request']['iterations'],expected)
                    self.assertEqual(job['request']['sample_alignment_version'],1)
                    self.assertEqual(job['request']['save_interval'],1000)
                    job['status']='completed'
            finally:manager.close()


if __name__=='__main__':unittest.main()

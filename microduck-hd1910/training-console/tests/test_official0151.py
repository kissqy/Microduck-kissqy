"""Official 0.15.1 migration, task semantics and deployment regression checks."""
import copy
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import training_console as tc
from studio import ROOT, PINS, fresh_recipe, computer_id, task_profile
from training.official_spec import ENGINE, REVISION, TASKS, WALK, STAND, JOINT, JOINT_TASKS, contract, compare_contracts
from training.deployment import deployment_contract, manifest_for, write_sidecars
from training.model_package import model_package


def reference(task):
    return json.loads((ROOT/'data/task-configs'/(task+'.json')).read_text())


class CatalogAndContractTests(unittest.TestCase):
    def test_one_source_current_profiles_and_native_physical_variants(self):
        self.assertEqual(list(PINS), [ENGINE])
        self.assertEqual(len(TASKS), 27)
        catalog=json.loads((ROOT/'data/tasks.json').read_text())
        self.assertEqual({x['id'] for x in catalog['tasks']}, set(TASKS))
        for task, info in TASKS.items():
            with self.subTest(task=task):
                self.assertEqual(info['upstream_task'], task.replace('BallKickLeft','BallKick'))
                self.assertEqual(info['source_revision'], REVISION)
                d=reference(task); c=d['inspection']
                self.assertFalse(any(r['help'].get('documentation_missing') for r in c['rows']))
                self.assertEqual(c['full']['agent']['max_iterations'], info['iterations'])
                self.assertEqual(c['full']['env']['actions']['joint_pos']['scale'], 1.0)
                self.assertAlmostEqual(c['model']['total_mass_kg'], .81958644 if info['hardware']=='rollers' else .820, places=9)
                self.assertEqual(c['full']['env']['events']['randomize_joint_friction']['params']['scale_range'], [.9,1.1])

    def test_teacher_contracts_match_and_physics_change_is_detected(self):
        target=contract(reference(JOINT)['inspection'])
        for task in (WALK, STAND, WALK.replace('Flat','Rough'), STAND.replace('Flat','Rough')):
            source=contract(reference(task)['inspection'])
            compare_contracts(source, target)
            source['bodies'][0]['mass_kg'] += .01
            with self.assertRaisesRegex(ValueError, 'bodies'):compare_contracts(source, target)

    def test_slots_phase_posture_and_teacher_are_not_conflated(self):
        for task, info in TASKS.items():
            c=deployment_contract({'task':task},reference(task)['inspection'])
            m=manifest_for({'task':task},c,'a'*64)
            self.assertEqual((m['schema_version'],m['model_api'],m['obs_len'],m['action_len']), (2,1,61,14))
            self.assertEqual(c['required_policy_settings']['head_lowpass'],1)
            self.assertEqual(c['required_policy_settings']['legs_lowpass'],1)
            self.assertNotIn('voltage_adapt', c['required_policy_settings'])
            if info['role']=='stand':
                self.assertTrue(m['teacher_only']);self.assertNotIn('slot',m)
            elif info['role']=='ground_pick':
                self.assertEqual(m['command']['encoding'],'phase');self.assertEqual(m['command']['period_s'],4)
                self.assertEqual(m['command']['end_phase'],.7)
            elif info['role']=='sitstand':
                self.assertEqual(m['kind'],'scripted');self.assertEqual(m['command']['encoding'],'posture_flag')
            elif info['role']=='roulade':
                self.assertEqual(m['duration_s'],1);self.assertTrue(m['chain'])
            elif info['role']=='kick_right':self.assertEqual(m['duration_s'],.5)

    def test_nonmatching_observation_history_or_frequency_not_labelled_compatible(self):
        data=reference(WALK)['inspection'];req={'task':WALK}
        data['full']['env']['observations']['actor']['history_length']=2
        with self.assertRaises(ValueError):deployment_contract(req,data)
        data=reference(WALK)['inspection'];data['full']['env']['decimation']=2
        with self.assertRaises(ValueError):deployment_contract(req,data)

    def test_repacked_export_preserves_manifest_and_deployment_profile(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'policy.onnx';p.write_bytes(b'unit-test-model-bytes')
            cp=Path(d)/'model_1000.pt';cp.write_bytes(b'unit-test-checkpoint-bytes')
            req={'task':WALK,'checkpoint':str(cp),'engine':ENGINE}
            write_sidecars(p,req,deployment_contract(req,reference(WALK)['inspection']))
            data=model_package({'artifact':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
                                'checkpoint':str(cp),'training_request':req})
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                self.assertEqual(json.loads(z.read('manifest.json'))['target_firmware'],'0.15.1')
                self.assertIn(b'head_lowpass = 1.0',z.read('deployment-profile.toml'))
                self.assertIn('使用说明.md',z.namelist())
            p.with_suffix('.manifest.json').unlink()
            with self.assertRaisesRegex(ValueError,'manifest'):
                model_package({'artifact':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
                               'checkpoint':str(cp),'training_request':req})


class MigrationAndLaunchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.patch=patch.object(tc.BaseTrainingManager,'_run');self.worker=self.patch.start()
        self.managers=[]
    def tearDown(self):
        for m in self.managers:m.close()
        self.patch.stop();self.tmp.cleanup()
    def manager(self):
        m=tc.TrainingManager(self.root);self.managers.append(m);return m
    def verified(self):
        (self.root/'computer.json').write_text(json.dumps({'id':computer_id(),'verified':True}))

    def test_migration_keeps_current_calibration_robot_and_machine_receipt(self):
        old=fresh_recipe();old['baseline']='hd1910';old['training_action_scale']=.7
        old['calibration']['data']['joints'][0]['zero_raw']=2222
        old['robot']['bodies']={'trunk_base':{'mass':.25}}
        old['overrides']=[{'path':['agent','gamma'],'value':.7}]
        (self.root/'recipe.json').write_text(json.dumps(old));self.verified()
        m=self.manager()
        self.assertTrue(m.computer_verified)
        self.assertEqual(m.recipe['calibration'],old['calibration'])
        self.assertEqual(m.recipe['robot'],old['robot'])
        self.assertEqual(m.recipe['baseline'],ENGINE)
        self.assertEqual(m.recipe['training_action_scale'],.9)
        self.assertEqual(m.recipe['overrides'],[])
        self.assertEqual(json.loads((self.root/'recipe-before-official0151.json').read_text()),old)
        self.assertEqual(m.launch('probe',{}),{'cached':True})

    def test_switching_tasks_launches_train_directly_with_source_pin_and_no_preflight(self):
        self.verified();m=self.manager()
        for task in TASKS:
            if task in JOINT_TASKS or not TASKS[task]['enabled']:continue
            j=m.jobs[m.launch('train',{'task':task})['job_id']]
            self.assertEqual(j['request']['engine'],ENGINE)
            self.assertEqual(j['request']['baseline_pin']['revision'],REVISION)
            self.assertEqual(j['request']['num_envs'],4096)
            self.assertEqual(j['request']['iterations'],TASKS[task]['iterations'])
            self.assertEqual(j['request']['save_interval'],1000)
            self.assertEqual(j['request']['training_action_scale'], .9 if TASKS[task]['role'] in ('walk','stand','joint') else 1)
            self.assertTrue(m.snapshot()['jobs'][0]['target_compatible'])
            j['status']='completed'
        self.assertFalse(any(j['op'] in ('probe','preflight') for j in m.jobs.values()))

    def test_current_calibration_import_does_not_invalidate_running_job_or_machine_cache(self):
        self.verified();m=self.manager()
        job=m.jobs[m.launch('train',{'task':WALK})['job_id']]
        before=copy.deepcopy(job['request']);data=copy.deepcopy(m.recipe['calibration']['data'])
        data['joints'][0]['zero_raw']+=1
        m.import_calibration({'name':'current.json','text':json.dumps(data)})
        self.assertEqual(job['request'],before);self.assertTrue(m.computer_verified)
        self.assertTrue(m.recipe['calibration']['sync']['simulation_unchanged'])

    def test_reward_edit_uses_bundled_schema_without_remote_describe(self):
        self.verified();m=self.manager()
        reward=next(x for x in reference(WALK)['rewards'] if x['editable'])
        job=m.jobs[m.launch('train',{'task':WALK,'reward_weights':{reward['name']:1.25}})['job_id']]
        self.assertEqual(job['request']['reward_weights'],{reward['name']:1.25})
        self.assertEqual([j['op'] for j in m.jobs.values()],['train'])

    def test_unsupported_legacy_engines_are_preserved_and_not_implicitly_converted(self):
        self.verified();m=self.manager()
        job=m.jobs[m.launch('train',{'task':WALK})['job_id']];job['status']='completed'
        job['request']['engine']='hd1910';job['checkpoints']=[{'path':'/fixture/model_5000.pt','iteration':5000}]
        self.assertFalse(m.snapshot()['jobs'][0]['target_compatible'])
        with self.assertRaisesRegex(ValueError,'不属于已支持'):
            m.launch('play',{'source_job':job['id'],'checkpoint':'/fixture/model_5000.pt'})
        self.assertIn(job['id'],m.jobs)

    def test_install_reuses_machine_verification_and_legacy_managed_paths_route_once(self):
        self.verified();m=self.manager()
        job=m.jobs[m.launch('setup',{})['job_id']]
        self.assertTrue(job['request']['machine_verified'])
        for name in ('luwu','hd1910/software/training','velstand_v2'):
            p={**m.profile,'repo':'/home/radxa/microduck-training-studio/engines/'+name}
            self.assertEqual(task_profile(p)['repo'],'/home/radxa/microduck-training-studio/engines/official_0151')


@unittest.skipUnless(importlib.util.find_spec('mjlab_microduck'), 'Optional: frozen official source and locked training dependencies')
class RealOfficialSourceTests(unittest.TestCase):
    def test_twelve_real_configs_preserve_rewards_curricula_commands_and_contact_geometry(self):
        import mjlab.tasks, mjlab_microduck.tasks
        from training.official_adapter import register_tasks
        register_tasks()
        from mjlab.tasks.registry import load_env_cfg,load_rl_cfg
        from training.runtime_adapter import apply_recipe
        from training.recipe import plain
        from training.hd1910_actuator import Hd1910Actuator
        from mjlab_microduck.actuator.friction_dr_bam import FrictionDRBamActuator
        from mjlab_microduck.publish.manifest import validate_manifest
        self.assertTrue(issubclass(Hd1910Actuator,FrictionDRBamActuator))
        for task in TASKS:
            with self.subTest(task=task):
                cfg=load_env_cfg(task);agent=load_rl_cfg(task)
                before={k:plain(getattr(cfg,k)) for k in ('rewards','curriculum','commands','terminations','events','actions')}
                original_spec=cfg.scene.entities['robot'].spec_fn().compile()
                req={'engine':ENGINE,'task':task,'op':'describe','studio_recipe':fresh_recipe()}
                apply_recipe(cfg,agent,req)
                self.assertEqual(before,{k:plain(getattr(cfg,k)) for k in before})
                model=cfg.scene.entities['robot'].build().spec.compile()
                self.assertEqual(model.nu,14)
                self.assertAlmostEqual(float(model.body_mass.sum()), .81958644 if TASKS[task]['hardware']=='rollers' else .820, places=7)
                self.assertEqual(model.ngeom,original_spec.ngeom)
                validate_manifest(manifest_for(req,deployment_contract(req,reference(task)['inspection']),'a'*64))


if __name__=='__main__':unittest.main()

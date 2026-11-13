"""Existing V2 weights must remain usable across the single-engine migration."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import training_console as tc
from studio import ROOT, fresh_recipe
from training.official_spec import (ENGINE, PIN, REVISION, LEGACY_V2_REVISION, WALK, STAND, JOINT,
    current_request, legacy_v2_request, model_task, contract, compare_contracts)
from training.deployment import deployment_contract, manifest_for
from training.worker import model_roots, run_prepared


def reference(task):
    return json.loads((ROOT/'data/task-configs'/(task+'.json')).read_text())['inspection']


def old_job(manager, task, adapter=None):
    job=manager.jobs[manager.launch('train',{'task':WALK if task==JOINT else task})['job_id']]
    job['status']='completed';job['revision']=LEGACY_V2_REVISION
    job['profile']={**manager.profile,'repo':'~/microduck-training-studio/engines/velstand_v2'}
    req=job['request'];req.update(engine='velstand_v2',task=task+'-V2-HD1910',
        baseline_pin={'revision':LEGACY_V2_REVISION},training_adapter_revision=adapter)
    req['studio_recipe']['baseline']='hd1910'
    req['studio_recipe']['task_overrides']={req['task']:[]}
    job['effective_config']={'training_action_scale':1.,'resolved':reference(task)}
    job['effective_config']['resolved']['model']['actuators'][0]['target_names_expr']=['^(?!passive_).*']
    job['checkpoints']=[{'path':str(Path.home())+'/microduck-training-studio/engines/velstand_v2/logs/rsl_rl/'+job['id']+'/model_5000.pt','iteration':5000}]
    return job


def selected(job):return {'source_job':job['id'],'checkpoint':job['checkpoints'][0]['path']}


class LegacyModelTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.worker=patch.object(tc.BaseTrainingManager,'_run');self.worker.start()
        self.manager=tc.TrainingManager(Path(self.tmp.name));self.manager.computer_verified=True
    def tearDown(self):
        self.manager.close();self.worker.stop();self.tmp.cleanup()

    def test_v2_walk_stand_joint_visible_without_reenabling_legacy_training_engines(self):
        m=self.manager
        for task in (WALK,STAND,JOINT):
            job=old_job(m,task)
            row=next(j for j in m.snapshot()['jobs'] if j['id']==job['id'])
            self.assertTrue(row['target_compatible']);self.assertFalse(row['resume_compatible'])
            self.assertEqual(row['resolved_task'],task)
            self.assertIn('固定摩擦',row['compatibility_label'])
        self.assertEqual(m.environment['engine'],ENGINE)
        req=copy.deepcopy(job['request']);req['baseline_pin']['revision']='unknown'
        self.assertIsNone(model_task(req))
        req['engine']='hd1910';self.assertIsNone(model_task(req))

    def test_play_and_export_route_code_to_current_source_but_preserve_old_weight_identity(self):
        m=self.manager;old=old_job(m,WALK);before=copy.deepcopy(old)
        m.recipe['calibration']['data']['joints'][0]['zero_raw']+=1
        for op in ('play','export'):
            job=m.jobs[m.launch(op,{**selected(old),'inference_scale':.7})['job_id']];req=job['request']
            self.assertEqual(req['task'],WALK);self.assertEqual(req['expected_revision'],REVISION)
            self.assertEqual(job['profile']['repo'],PIN['repo'])
            self.assertEqual(req['model_source']['repo'],old['profile']['repo'])
            self.assertEqual(req['model_source']['origin']['baseline_pin']['revision'],LEGACY_V2_REVISION)
            self.assertEqual(req['model_source']['origin']['friction_randomization'],'fixed')
            self.assertEqual(req['studio_recipe']['baseline'],ENGINE)
            self.assertEqual(req['policy_parameters']['training_action_scale'],1.)
            self.assertNotIn('inference_scale',req)
            self.assertEqual(req['training_calibration'],old['request']['studio_recipe']['calibration'])
            self.assertEqual(req['studio_recipe']['calibration'],m.recipe['calibration'])
            job['status']='completed'
        self.assertEqual(old,before)
        self.assertFalse(any(j['op'] in ('probe','preflight','setup') for j in m.jobs.values()))

    def test_custom_legacy_checkout_is_never_used_as_execution_source(self):
        m=self.manager;old=old_job(m,WALK);old['profile']['repo']='~/custom-old-source'
        job=m.jobs[m.launch('play',selected(old))['job_id']]
        self.assertEqual(job['profile']['repo'],PIN['repo'])
        self.assertEqual(job['request']['model_source']['repo'],'~/custom-old-source')

    def test_original_onnx_and_reexport_both_retain_v2_provenance(self):
        m=self.manager;old=old_job(m,WALK)
        exported=copy.deepcopy(old);exported.update(id='1'*16,op='export',artifact=old['checkpoints'][0]['path']+'.onnx',artifact_sha256='a'*64)
        exported['request'].update(source_job=old['id'],policy_parameters={'training_action_scale':1.})
        m.jobs[exported['id']]=exported
        viewed=m.jobs[m.launch('onnx',{'export_job':exported['id'],'inference_scale':.7})['job_id']]
        self.assertEqual(viewed['request']['task'],WALK)
        self.assertEqual(viewed['request']['model_source']['repo'],old['profile']['repo'])
        self.assertNotIn('inference_scale',viewed['request'])
        self.assertEqual(viewed['request']['policy_parameters']['training_action_scale'],1.)
        viewed['status']='completed'
        new_export=m.jobs[m.launch('export',selected(old))['job_id']]
        new_export.update(status='completed',revision=REVISION,artifact='/current/logs/rsl_rl/export.onnx',artifact_sha256='b'*64)
        viewed=m.jobs[m.launch('onnx',{'export_job':new_export['id'],'inference_scale':.7})['job_id']]
        self.assertEqual(viewed['request']['model_source'],new_export['request']['model_source'])
        self.assertNotIn('inference_scale',viewed['request'])
        self.assertEqual(viewed['request']['policy_parameters']['training_action_scale'],1.)
        c=deployment_contract(new_export['request'],reference(WALK))
        manifest=manifest_for(new_export['request'],c,'b'*64)
        self.assertEqual(manifest['training']['commit'],LEGACY_V2_REVISION)
        self.assertEqual(manifest['training']['task_id'],WALK+'-V2-HD1910')
        self.assertEqual(manifest['export_source_revision'],REVISION)
        self.assertEqual(c['model_origin']['friction_randomization'],'fixed')

    def test_joint_warm_start_accepts_old_teachers_and_records_their_original_paths(self):
        m=self.manager;walk=old_job(m,WALK);stand=old_job(m,STAND)
        before=[copy.deepcopy(x) for x in (walk,stand)]
        job=m.jobs[m.launch('train',{'task':JOINT,'walk_teacher':selected(walk),'stand_teacher':selected(stand)})['job_id']]
        self.assertTrue(current_request(job['request']))
        for role,source in [('walk',walk),('stand',stand)]:
            spec=job['request']['joint'][role]
            self.assertEqual(spec['checkpoint'],selected(source)['checkpoint'])
            self.assertEqual(spec['repo'],source['profile']['repo'])
            self.assertTrue(legacy_v2_request(spec['origin']))
            compare_contracts(spec['contract'],contract(reference(JOINT)))
        self.assertNotIn('model_source',job['request']) # New student must keep DR.
        self.assertEqual([walk,stand],before)
        self.assertFalse(any(j['op'] in ('probe','preflight','setup') for j in m.jobs.values()))

    def test_wrong_teacher_role_and_changed_robot_are_not_silently_reinterpreted(self):
        m=self.manager;walk=old_job(m,WALK);stand=old_job(m,STAND)
        with self.assertRaisesRegex(ValueError,'走路'):
            m.launch('train',{'task':JOINT,'walk_teacher':selected(stand),'stand_teacher':selected(stand)})
        m.recipe['robot']['bodies']={'trunk_base':{'mass':.3}}
        with self.assertRaisesRegex(ValueError,'物理配置'):
            m.launch('train',{'task':JOINT,'walk_teacher':selected(walk),'stand_teacher':selected(stand)})

    def test_repaired_v2_models_are_not_mislabeled_fixed_friction(self):
        old=old_job(self.manager,WALK,adapter='R1.4.23-friction-dr-base')
        req=self.manager.jobs[self.manager.launch('play',selected(old))['job_id']]['request']
        self.assertEqual(req['model_source']['origin']['friction_randomization'],'official')


class ContractAndPathTests(unittest.TestCase):
    def test_equivalent_selector_is_accepted_but_physical_and_action_differences_are_not(self):
        target=contract(reference(JOINT));old=copy.deepcopy(target)
        old['actuators'][0]['target_names_expr']=['^(?!passive_).*']
        compare_contracts(old,target)
        changes=[('actions',lambda c:c['actions']['joint_pos'].update(scale=.7)),
                 ('actuators',lambda c:c['actuators'][0].update(kp_fw=8)),
                 ('actuators',lambda c:c['actuators'][0].update(target_names_expr=['left_.*'])),
                 ('bodies',lambda c:c['bodies'][0].update(mass_kg=.9)),
                 ('joints',lambda c:c['joints'].reverse()),
                 ('observations',lambda c:c['observations'].reverse())]
        for field,mutate in changes:
            changed=copy.deepcopy(old);mutate(changed)
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,field):compare_contracts(changed,target)

    def test_external_checkpoint_root_is_limited_to_known_v2_evaluation(self):
        req={'op':'play','task':WALK,'model_source':{'repo':'/old',
             'origin':{'engine':'velstand_v2','task':WALK+'-V2-HD1910','baseline_pin':{'revision':LEGACY_V2_REVISION}}}}
        self.assertEqual(model_roots(req,Path('/new')),[Path('/new/logs/rsl_rl'),Path('/old/logs/rsl_rl')])
        req['op']='train'
        with self.assertRaises(ValueError):model_roots(req,Path('/new'))
        req['op']='play';req['model_source']['origin']['baseline_pin']['revision']='unknown'
        with self.assertRaises(ValueError):model_roots(req,Path('/new'))

    def test_worker_can_read_old_pt_and_onnx_without_running_old_source(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);old=root/'old';new=root/'new';scratch=root/'adapter';scratch.mkdir()
            cp=old/'logs/rsl_rl/fixture/model_5000.pt';cp.parent.mkdir(parents=True);cp.write_bytes(b'fixture')
            req={'repo':str(new),'op':'play','task':WALK,'checkpoint':str(cp),
                 'model_source':{'repo':str(old),'origin':{'engine':'velstand_v2','task':WALK+'-V2-HD1910',
                 'baseline_pin':{'revision':LEGACY_V2_REVISION},'friction_randomization':'fixed'}}}
            with patch('training.worker.prepare',return_value=(new,['uv','run'],REVISION)),patch('training.worker.monitor_gpu'),patch('training.worker.emit'),patch('training.worker.execute') as execute:
                run_prepared(req,scratch)
                self.assertEqual(execute.call_args.args[1],new)
                self.assertEqual(json.loads((scratch/'request.json').read_text())['checkpoint'],str(cp))
                artifact=cp.with_suffix('.onnx');artifact.write_bytes(b'onnx-fixture')
                req.update(op='onnx',onnx_path=str(artifact));req.pop('checkpoint')
                run_prepared(req,scratch)
                self.assertEqual(execute.call_args.args[1],new)
                req.update(op='play',checkpoint=str(root/'unrecorded.pt'));Path(req['checkpoint']).write_bytes(b'fixture')
                with self.assertRaisesRegex(RuntimeError,'来源训练仓库'):run_prepared(req,scratch)


if __name__=='__main__':unittest.main()

"""Evaluation-only target mapping: HTTP wiring and immutable model identity.

The worker is mocked. These checks do not execute GPU physics or the robot.
"""
import copy
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

import training_console as tc
from training.official_spec import ENGINE, REVISION, TASKS, STAND, WALK
from training.remote_ssh import RELEASE
from training.target_limit_profile import SCHEMA, POLICY_IDS


def fixture_profile(task=STAND, sha='a'*64):
    return {'schema':SCHEMA, 'model_sha256':sha, 'task':task, 'seed':42,
            'joints':[{'name':name, 'id':sid, 'zero_raw':2048, 'direction':1,
                       'min_rad':-0.9, 'max_rad':0.9} for name,sid in POLICY_IDS.items()],
            'recording':{'created_at':1.0, 'source_name':'fixture.json',
                         'source_sha256':'b'*64, 'frame_count':2, 'active_frames':2,
                         'build':'synthetic-fixture'},
            'runtime':{'base_action_scale':1.0, 'effective_action_scale_min':0.96,
                       'effective_action_scale_max':0.97, 'head_alpha':1.0,
                       'legs_alpha':1.0, 'voltage_adapt':True}}


class TargetLimitApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher=patch.object(tc.BaseTrainingManager, '_run')
        patcher.start();self.addCleanup(patcher.stop)
        self.manager=tc.TrainingManager(Path(self.tmp.name))
        self.addCleanup(self.manager.close)
        self.manager.computer_verified=True
        self.manager.environment={'ready':True, 'revision':REVISION, 'engine':ENGINE,
                                  'tasks':list(TASKS), 'configs':{}}

    def export(self, task=STAND):
        source=self.manager.jobs[self.manager.launch('train', {
            'task':task, 'training_action_scale':1.0, 'training_firmware_p':5})['job_id']]
        # This fixture represents a saved pre-R1.5.21 model, not a new EMA recipe.
        historical_filter={'enabled':True, 'head_alpha':1.0, 'legs_alpha':1.0, 'version':1}
        source['request']['action_filter']=copy.deepcopy(historical_filter)
        source.update(status='completed', revision=REVISION,
                      checkpoints=[{'path':'/fixture/model_11000.pt', 'iteration':11000}])
        source['effective_config']={'resolved':json.loads(
            (tc.ROOT/'data/task-configs'/(task+'.json')).read_text())['inspection']}
        source['effective_config']['action_filter']=copy.deepcopy(historical_filter)
        source['effective_config']['resolved']['full']['env']['actions']['joint_pos'].update(
            head_alpha=1.0, legs_alpha=1.0, filter_version=1)
        selected={'source_job':source['id'], 'checkpoint':'/fixture/model_11000.pt'}
        exported=self.manager.jobs[self.manager.launch('export', selected)['job_id']]
        exported.update(status='completed', revision=REVISION,
                        artifact='/fixture/model_11000.onnx', artifact_sha256='a'*64)
        return source,exported,selected

    def server(self):
        server=tc.ThreadingHTTPServer(('127.0.0.1',0),tc.handler_for(self.manager,'fixture-token'))
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        def close():
            server.shutdown();server.server_close();thread.join(timeout=2)
        self.addCleanup(close)
        return 'http://127.0.0.1:'+str(server.server_port)

    def post(self, url, value, token='fixture-token'):
        request=urllib.request.Request(url, data=json.dumps(value).encode(),
            headers={'Content-Type':'application/json','X-Training-Token':token})
        with urllib.request.urlopen(request,timeout=3) as response:
            return json.load(response)

    def test_selected_export_identity_is_bound_and_recipe_is_untouched(self):
        source,exported,_=self.export()
        source_before=copy.deepcopy(source);export_before=copy.deepcopy(exported)
        recipe_before=copy.deepcopy(self.manager.recipe);profile=fixture_profile()
        job=self.manager.jobs[self.manager.launch('onnx', {
            'export_job':exported['id'], 'task':WALK, 'eval_pushes':True,
            'recovery_evaluation':False, 'target_limit_comparison':profile})['job_id']]
        request=job['request']
        self.assertEqual(request['task'],STAND)
        self.assertEqual(request['onnx_sha256'],'a'*64)
        self.assertEqual(request['source_iteration'],11000)
        self.assertTrue(request['recovery_evaluation'])
        self.assertFalse(request['eval_pushes'])
        self.assertEqual(request['policy_parameters']['training_action_scale'],1.0)
        self.assertTrue(request['policy_parameters']['action_filter']['enabled'])
        self.assertEqual(request['target_limit_comparison']['runtime']['effective_action_scale_min'],0.96)
        self.assertEqual(source,source_before);self.assertEqual(exported,export_before)
        self.assertEqual(self.manager.recipe,recipe_before)
        profile['joints'][0]['min_rad']=-0.5
        self.assertEqual(request['target_limit_comparison']['joints'][0]['min_rad'],-0.9)
        self.assertNotIn('target_limit_comparison',request['studio_recipe'])

    def test_wrong_model_and_invalid_profile_do_not_create_jobs(self):
        _,exported,_=self.export()
        before=set(self.manager.jobs)
        values=[fixture_profile(sha='c'*64), fixture_profile(task=WALK), None, False, {}, []]
        for value in values:
            with self.subTest(profile=value),self.assertRaises(ValueError):
                self.manager.launch('onnx',{'export_job':exported['id'],
                    'target_limit_comparison':value})
        self.assertEqual(set(self.manager.jobs),before)

    def test_mapping_cannot_leak_into_training_or_other_operations(self):
        _,_,selected=self.export()
        before=set(self.manager.jobs);recipe=copy.deepcopy(self.manager.recipe)
        for op in ('train','preflight','preview','play','export','setup','probe','describe'):
            with self.subTest(op=op),self.assertRaisesRegex(ValueError,'仅用于'):
                self.manager.launch(op,{'task':STAND,**selected,'target_limit_comparison':fixture_profile()})
        self.assertEqual(set(self.manager.jobs),before)
        self.assertEqual(self.manager.recipe,recipe)
        with self.assertRaisesRegex(ValueError,'不能加入训练队列'):
            self.manager.queue_add({'task':STAND,'client_id':'fixture-ab',
                'target_limit_comparison':fixture_profile()})
        self.assertEqual(self.manager.training_queue['entries'],[])

    def test_ordinary_onnx_keeps_its_original_path(self):
        _,exported,_=self.export()
        job=self.manager.jobs[self.manager.launch('onnx',{'export_job':exported['id']})['job_id']]
        self.assertNotIn('target_limit_comparison',job['request'])
        self.assertFalse(job['request']['recovery_evaluation'])
        self.manager._event(job,{'kind':'limit_comparison_result','data':{'valid':True}})
        self.assertNotIn('limit_comparison_result',job)

    def test_http_profile_launch_progress_result_download_and_auth(self):
        _,exported,_=self.export();base=self.server();profile=fixture_profile()
        # The dedicated parser has its own numerical/recording tests; this
        # checks its HTTP transport and the exact normalized result handoff.
        with patch('training.target_limit_profile.from_recording',return_value=profile) as parser:
            response=self.post(base+'/api/target-limit-profile',{'name':'fixture.json','text':'{}'})
            parser.assert_called_once_with({'name':'fixture.json','text':'{}'})
        jid=self.post(base+'/api/onnx',{'export_job':exported['id'],
                      'target_limit_comparison':response['profile']})['job_id']
        job=self.manager.jobs[jid]
        endpoint=base+'/api/target-limit-comparison?job='+jid
        with self.assertRaises(urllib.error.HTTPError) as absent:
            urllib.request.urlopen(endpoint,timeout=3)
        self.assertEqual(absent.exception.code,409)
        self.manager._event(job,{'kind':'limit_comparison_state','data':{'group':'A','step':5}})
        self.assertEqual(job['limit_comparison_state']['step'],5)
        difference={'component':'live_physics','field':'body_mass','gating':True,
                    'passed':False,'exact':False,'reason':'outside_tolerance',
                    'shape_a':[1,2],'shape_b':[1,2],'dtype_a':'float32','dtype_b':'float32',
                    'max_abs_diff':0.01,'max_rel_diff':0.05,'atol':1e-10,'rtol':2e-6}
        comparison={'method':'fresh_env_same_seed_numeric_physics_exact_histories_v2',
                    'passed':False,'exact':False,'fields':[difference],'differences':[difference]}
        result={'schema':'microduck-target-limit-ab-v1','valid':False,
                'initial_state_equal':False,'initial_state_exact':False,
                'initial_state_method':comparison['method'],
                'initial_state_comparison':comparison,'initial_state_differences':[difference],
                'error':'fixture mismatch',
                'groups':[{'label':'A','status':'passed','steps':72,'elapsed_s':1.44,
                           'max_roll_deg':106.404,'joint21_clamp_steps':0,
                           'trace':[{'joint21_actual_rad':-0.4},{'joint21_actual_rad':-0.3}]},
                          {'label':'B','status':'invalid','steps':0,'elapsed_s':0,
                           'max_roll_deg':0,'joint21_clamp_steps':0,'trace':[],
                           'initial_state_comparison':comparison}]}
        self.manager._event(job,{'kind':'limit_comparison_result','data':result})
        with urllib.request.urlopen(endpoint,timeout=3) as downloaded:
            self.assertEqual(json.load(downloaded),result)
        saved=json.loads((Path(self.tmp.name)/'runs'/jid/'run.json').read_text())
        self.assertEqual(saved['limit_comparison_result'],result)
        with urllib.request.urlopen(base+'/api/state?selected='+jid,timeout=3) as state:
            compact=next(j for j in json.load(state)['jobs'] if j['id']==jid)['limit_comparison_result']
        self.assertNotIn('trace',compact['groups'][0])
        self.assertEqual(compact['groups'][0]['trace_ranges_rad']['joint21_actual_rad'],[-0.4,-0.3])
        self.assertEqual(compact['initial_state_differences'],[difference])
        self.assertEqual(compact['initial_state_comparison'],comparison)
        self.assertEqual(compact['groups'][1]['initial_state_comparison'],comparison)
        self.assertEqual(job['limit_comparison_result'],result)
        log=tc.event_log_text({'kind':'limit_comparison_result','data':result})
        self.assertIn('B组：未运行（初态核对未通过）',log)
        self.assertIn('live_physics.body_mass',log)
        self.assertIn('最大绝对差=0.01',log)
        self.assertNotIn('B组：invalid；最大翻身角=0',log)
        with self.assertRaises(urllib.error.HTTPError) as rejected:
            self.post(base+'/api/target-limit-profile',{'name':'fixture.json','text':'{}'},token='wrong')
        self.assertEqual(rejected.exception.code,403)
        with urllib.request.urlopen(base+'/api/config',timeout=3) as cfg:
            self.assertEqual(json.load(cfg)['release'],RELEASE)


if __name__=='__main__':
    unittest.main()

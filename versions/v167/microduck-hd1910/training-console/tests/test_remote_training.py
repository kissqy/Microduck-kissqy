"""Remote API routing, portable models and deployment lifecycle without a GPU."""
import base64
import copy
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
from unittest.mock import Mock, patch
from http.server import ThreadingHTTPServer

import training_console as console
from training.model_import import import_model
from training.remote_ssh import RemoteTraining, RELEASE, validate_connection, ssh_argv
from training.official_spec import PIN, contract, compare_contracts

ROOT = Path(console.__file__).parent
TASK = 'Mjlab-StandUp-Rough-Backlash-MicroDuck'


def package(scale=.7, p=5):
    from training.action_filter import validate
    resolved = json.loads((ROOT/'data/task-configs'/(TASK+'.json')).read_text())['inspection']
    resolved = copy.deepcopy(resolved)
    action = resolved['full']['env']['actions']['joint_pos']
    action.update(scale=scale,head_alpha=.5,legs_alpha=.7,filter_version=1)
    for actuator in resolved['model']['actuators']:
        actuator['kp_fw']=p
    request = {'engine':'official_0151','task':TASK,'baseline_pin':PIN,'studio_recipe':__import__('studio').fresh_recipe(),
               'training_action_scale':scale,'training_firmware_p':p,'action_filter':validate({'enabled':True,'head_alpha':.5,'legs_alpha':.7}),
               'iterations':7000,'num_envs':4096}
    deployment = {'task':TASK,'input_dim':61,'output_dim':14,'model':resolved['model'],
                  'actions':resolved['full']['env']['actions'],'observations':resolved['full']['env']['observations']['actor'],'control_hz':50.0}
    manifest={'task':TASK,'action_scale':scale,'training':{'checkpoint':7000}}
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w') as archive:
        archive.writestr('checkpoint.pt',b'portable PT fixture, never executed')
        for name, value in [('deployment-contract.json',deployment),('manifest.json',manifest),('training-request.json',request)]:
            archive.writestr(name,json.dumps(value))
    return output.getvalue(),request,resolved


class RemoteTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.manager=console.TrainingManager(directory=Path(self.temp.name))
        self.remote=RemoteTraining(self.manager.directory,ROOT,self.manager,console.save_json)
        self.manager.remote=self.remote
    def tearDown(self):
        self.remote.close();self.manager.close();self.temp.cleanup()
    def test_input_validation_and_safe_ssh_arguments(self):
        for update in [{'host':'-oProxyCommand=x'},{'host':'a;echo x'},{'user':'root@host'},{'port':True},{'workspace':'/'}]:
            with self.assertRaises(ValueError):validate_connection({'host':'example.org',**update})
        valid=validate_connection({'host':'example.org','workspace':"~/training space/quote's"})
        with patch('training.remote_ssh.shutil.which',return_value='/usr/bin/ssh'):
            argv=ssh_argv(valid)
        self.assertIn('StrictHostKeyChecking=yes',argv)
        self.assertIn('BatchMode=yes',argv)
        self.assertNotIn('shell',argv)
    def test_restart_preserves_target_without_starting_or_falling_back(self):
        self.remote.connection=validate_connection({'host':'example.org'})
        self.remote.target='ssh';self.remote.persist()
        restored=RemoteTraining(self.manager.directory,ROOT,self.manager,console.save_json)
        self.assertEqual(restored.target,'ssh')
        with self.assertRaises(ValueError):restored.proxy('/api/train',{})
        self.assertEqual(self.manager.jobs,{})
    def test_failed_connection_stays_remote_and_retains_local_configuration(self):
        self.remote.connection=validate_connection({'host':'example.org'})
        original=copy.deepcopy(self.manager.recipe)
        with patch('training.remote_ssh.ssh_argv',return_value=['ssh']),patch('training.remote_ssh.subprocess.run',return_value=Mock(returncode=255,stderr=b'Permission denied',stdout=b'')):
            self.remote.target='ssh';self.remote.operation='connect';self.remote._connect('connect')
        self.assertEqual(self.remote.status,'failed');self.assertEqual(self.remote.target,'ssh')
        self.assertEqual(self.manager.recipe,original);self.assertEqual(self.manager.jobs,{})
    def test_close_and_disconnect_only_close_local_tunnels(self):
        process=Mock();process.poll.return_value=None
        log=io.BytesIO()
        self.remote.tunnels[40000]={'process':process,'local_port':40100,'error':log}
        self.remote.disconnect()
        process.terminate.assert_called_once();self.assertTrue(log.closed)
        self.assertEqual(self.manager.jobs,{})
    def test_viewers_get_separate_loopback_tunnels(self):
        self.remote.forward=Mock(side_effect=lambda port:port+100)
        value={'jobs':[{'viewer_url':'http://127.0.0.1:8093','training_view_url':'http://127.0.0.1:8094'}]}
        self.remote.rewrite_viewers(value)
        self.assertEqual(value['jobs'][0]['viewer_url'],'http://127.0.0.1:8193')
        self.assertEqual(value['jobs'][0]['training_view_url'],'http://127.0.0.1:8194')
    def test_model_transport_keeps_physical_contract_and_iteration(self):
        packed,request,resolved=package()
        value={'name':'teacher.zip','data':base64.b64encode(packed).decode()}
        result=import_model(self.manager,value,ROOT)
        source=self.manager.jobs[result['job_id']]
        self.assertEqual(source['request']['training_action_scale'],.7)
        self.assertEqual(source['request']['training_firmware_p'],5)
        self.assertEqual(source['request']['action_filter'],request['action_filter'])
        self.assertEqual(source['request']['baseline_pin'],request['baseline_pin'])
        self.assertEqual(source['checkpoints'][0]['iteration'],7000)
        actual=contract(self.manager.source_inspection(source),source['request'])
        compare_contracts(actual,contract(resolved,request))
        self.assertNotIn('full',self.manager.source_inspection(source),'legacy package must not fabricate full PPO readback')
        again=import_model(self.manager,value,ROOT)
        self.assertTrue(again['reused']);self.assertEqual(again['job_id'],result['job_id'])
    def test_model_mismatches_and_size_are_rejected(self):
        packed,_,_=package(); output=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(packed)) as original,zipfile.ZipFile(output,'w') as bad:
            for name in original.namelist():
                data=original.read(name)
                if name=='manifest.json':
                    value=json.loads(data);value['action_scale']=1.0;data=json.dumps(value)
                bad.writestr(name,data)
        with self.assertRaisesRegex(ValueError,'动作系数'):
            import_model(self.manager,{'data':base64.b64encode(output.getvalue()).decode()},ROOT)
        self.assertFalse(self.manager.jobs)
    def test_legacy_export_envelope_reads_saved_parameters_and_actual_p(self):
        packed,request,_=package();output=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(packed)) as original,zipfile.ZipFile(output,'w') as rebuilt:
            for name in original.namelist():
                data=original.read(name)
                if name=='training-request.json':
                    value=json.loads(data);value['op']='export'
                    value['policy_parameters']={k:value.pop(k) for k in ('training_action_scale','action_filter')}
                    value.pop('training_firmware_p');value.pop('num_envs')
                    data=json.dumps(value)
                rebuilt.writestr(name,data)
        result=import_model(self.manager,{'name':'legacy-export.zip','data':base64.b64encode(output.getvalue()).decode()},ROOT)
        self.assertEqual(result['training_action_scale'],.7)
        self.assertEqual(result['training_firmware_p'],5)
        self.assertFalse(result['resume_supported'])
        job=self.manager.jobs[result['job_id']]
        self.assertFalse(next(j for j in self.manager.snapshot()['jobs'] if j['id']==job['id'])['resume_compatible'])
        with self.assertRaisesRegex(ValueError,'并行数'):
            self.manager.queue_add({'client_id':'legacy-resume','source_job':job['id'],'checkpoint':job['checkpoints'][0]['path'],'task':TASK})

    def test_deploy_starts_remote_environment_preparation(self):
        self.remote.connection=validate_connection({'host':'example.org'})
        info={'port':41000,'release':RELEASE,'workspace':'/home/ubuntu/test'}
        cfg={'release':RELEASE,'remote_workspace':info['workspace'],'token':'remote-token'}
        response=Mock();response.__enter__=Mock(return_value=io.BytesIO(json.dumps(cfg).encode()));response.__exit__=Mock()
        self.remote.forward=Mock(return_value=42000)
        self.remote.proxy=Mock(side_effect=[(b'{"environment":{"ready":false},"jobs":[]}',200,'application/json'),(b'{"job_id":"setup"}',200,'application/json')])
        result=Mock(returncode=0,stdout=('MICRODUCK_SSH_RESULT '+json.dumps(info)).encode(),stderr=b'')
        with patch('training.remote_ssh.ssh_argv',return_value=['ssh']),patch('training.remote_ssh.subprocess.run',return_value=result),patch('training.remote_ssh.urllib.request.urlopen',return_value=response),patch.object(self.manager,'launch') as local_launch:
            self.remote.target='ssh';self.remote.operation='deploy';self.remote._connect('deploy')
            self.assertEqual(self.remote.status,'connected')
            self.remote.proxy.assert_any_call('/api/setup',{'mode':'local','distro':'Ubuntu','repo':PIN['repo']})
            local_launch.assert_not_called()

    def test_wsl_deploy_only_inspects_existing_engine(self):
        self.remote.connection=validate_connection({'host':'127.0.0.1','identity':'test key','known_hosts':'trusted key','wsl_distro':'Ubuntu'})
        info={'port':41000,'release':RELEASE,'workspace':'/home/ubuntu/test'}
        cfg={'release':RELEASE,'remote_workspace':info['workspace'],'token':'remote-token'}
        response=Mock();response.__enter__=Mock(return_value=io.BytesIO(json.dumps(cfg).encode()));response.__exit__=Mock()
        self.remote.forward=Mock(return_value=42000)
        self.remote.proxy=Mock(side_effect=[(b'{"environment":{"ready":false},"jobs":[]}',200,'application/json'),(b'{"job_id":"probe"}',200,'application/json')])
        result=Mock(returncode=0,stdout=('MICRODUCK_SSH_RESULT '+json.dumps(info)).encode(),stderr=b'')
        with patch('training.remote_ssh.ssh_argv',return_value=['ssh']),patch('training.remote_ssh.subprocess.run',return_value=result),patch('training.remote_ssh.urllib.request.urlopen',return_value=response),patch.object(self.manager,'launch') as local_launch:
            self.remote.target='ssh';self.remote.operation='wsl_test';self.remote._connect('deploy')
        self.assertEqual(self.remote.status,'connected')
        self.remote.proxy.assert_any_call('/api/probe',{'mode':'local','distro':'Ubuntu','repo':PIN['repo']})
        self.assertFalse(any(call.args[0]=='/api/setup' for call in self.remote.proxy.call_args_list))
        local_launch.assert_not_called()

    def test_server_proxy_keeps_browser_token_local_and_remote_payload_exact(self):
        self.remote.target='ssh';self.remote.proxy=Mock(return_value=(b'{"job_id":"remote"}',200,'application/json'))
        server=ThreadingHTTPServer(('127.0.0.1',0),console.handler_for(self.manager,'local-token'))
        server.daemon_threads=True
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        url='http://127.0.0.1:%d'%server.server_port
        try:
            config=json.load(urllib.request.urlopen(url+'/api/config'))
            self.assertEqual(config['token'],'local-token');self.assertEqual(config['release'],RELEASE)
            payload={'training_action_scale':.7,'training_firmware_p':5,'action_filter':{'enabled':True,'head_alpha':.5,'legs_alpha':.7}}
            request=urllib.request.Request(url+'/api/train',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','X-Training-Token':'local-token'})
            self.assertEqual(json.load(urllib.request.urlopen(request))['job_id'],'remote')
            self.remote.proxy.assert_called_once_with('/api/train',payload)
            request.headers['X-training-token']='wrong'
            with self.assertRaises(urllib.error.HTTPError) as caught:urllib.request.urlopen(request)
            self.assertEqual(caught.exception.code,403)
            self.remote.proxy.assert_called_once()
            for path in ['/remote.js','/remote.css']:
                self.assertEqual(urllib.request.urlopen(url+path).status,200)
        finally:server.shutdown();server.server_close();thread.join()


if __name__=='__main__':unittest.main()

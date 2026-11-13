"""Built-in deployment, finite kick RPC and retirement of manual/import paths."""
import copy
import importlib.util
import io
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import tomllib
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'console'))
import console
import controls
import model_packages as models
import runtime
import service_rpc
from configure import dumps
from management_profile import PROFILE
from service_control import ControlError,ServiceController,ServiceTransport,validate

KICK='67ad09d82f4865d222a7ae06f250cf9f'
WALK='1cbf8730eadd75a5704332c9f3c10f60'
COMMAND={'action':'run-skill','name':'kick_right','supported':True}

def fixture(row):
    return ROOT/'packaging/models'/row['id']

class Store:
    service_operation=False
    def __init__(self,snapshot=None):
        self.data=snapshot or {'service_sample_fresh':True,'service_compatible':True,
            'bus':{'build':runtime.BUILD,'mode':'motion','phase':'control','homed':True,
                   'policy_enabled':True,'native':{'imu_ready':True,'torque_state_confirmed':True}},
            'capabilities':{'skills':['kick_right']}}
        self.records=[]
    def snapshot(self):return self.data
    def record_service_command(self,job):self.records.append(copy.deepcopy(job))

class ImmediateThread:
    def __init__(self,target,args=(),**_):self.target=target;self.args=args
    def start(self):self.target(*self.args)

class BuiltinControls154Tests(unittest.TestCase):
    def test_scale_api_accepts_only_scale_and_dispatches_no_servo_registers(self):
        command={'action':'set-action-scale','model':WALK,'scale':.63,'supported':True}
        self.assertEqual(validate(command),command)
        for key,value in [('kp',3),('kd',0),('torque_limit',681)]:
            with self.subTest(key=key),self.assertRaises(ControlError):validate({**command,key:value})
        transport=SimpleNamespace(manage=Mock(return_value={'action_scale':.63}))
        controller=ServiceController(Store(),transport=transport)
        job={'action':'set-action-scale','status':'running'}
        controller._execute(command,job,0)
        transport.manage.assert_called_once_with('action-scale',WALK,'0.63',password=None)
        self.assertEqual(job['status'],'completed')

    def test_stale_servo_override_is_not_read_or_rewritten_by_scale(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);config=base/'robotd.toml';legacy=base/'servo-test-parameters.json'
            legacy.write_bytes(b'{ corrupt obsolete values')
            config.write_text(dumps({'policy':{'walk':f'/missing/{WALK}/policy.onnx','action_scale':.7,
                'head_lowpass':.41,'legs_lowpass':.69},'pad':{'rb':'kick_right'}}))
            with patch.object(runtime,'CONFIG',config):result=runtime.set_action_scale(WALK,.63)
            self.assertEqual(result['action_scale'],.63);self.assertNotIn('servo_parameters',result)
            self.assertEqual(legacy.read_bytes(),b'{ corrupt obsolete values')
            data=tomllib.loads(config.read_text());self.assertEqual(data['policy']['head_lowpass'],.41)
            self.assertEqual(data['policy']['legs_lowpass'],.69)
            self.assertEqual(config.read_bytes(),config.with_name('robotd.saved.toml').read_bytes())
            with self.assertRaises(TypeError):runtime.set_action_scale(WALK,.7,3,0,681)

    def test_catalog_only_exposes_builtins_and_never_reads_onnx_or_training_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);config=base/'robotd.toml';policy={}
            for row in PROFILE['builtin_models']:
                directory=base/'models'/row['id'];shutil.copytree(fixture(row),directory)
                policy[row['slot']]=str(directory/'policy.onnx')
            imported=base/'models'/('f'*32);shutil.copytree(ROOT/'policies/walk',imported)
            config.write_text(dumps({'policy':policy}))
            before={p:p.read_bytes() for p in base.rglob('*') if p.is_file()}
            original=Path.read_bytes
            def small_metadata(path):
                if path.name=='policy.onnx' or path.suffix=='.yaml':raise AssertionError('catalog parsed training/weights')
                return original(path)
            with patch.object(Path,'read_bytes',small_metadata):listing=models.catalog(base,config)
            self.assertEqual({r['id'] for r in listing['models']},{r['id'] for r in PROFILE['builtin_models']})
            self.assertEqual(len(listing['models']),6)
            self.assertTrue(all(r['available'] and r['builtin'] and not r['deletable'] for r in listing['models']))
            self.assertNotIn('manual_recovery',listing)
            self.assertEqual(before,{p:p.read_bytes() for p in base.rglob('*') if p.is_file()})

    def test_original_five_builtin_models_and_right_kick_contract_validate(self):
        for row in PROFILE['builtin_models']:
            with self.subTest(slot=row['slot']):
                info=models.verify_directory(fixture(row));self.assertEqual(info['id'],row['id'])
                self.assertEqual(info['slot'],row['slot'])
        info=models.verify_directory(ROOT/'packaging/models'/KICK)
        self.assertEqual(info['skill']['duration'],.5)
        self.assertFalse(info['skill']['chain']);self.assertEqual(info['skill']['params']['action_scale'],1.)

    def test_model_import_upload_is_unavailable_without_reading_body(self):
        handler=console.handler_for(Store(),{'bind':'127.0.0.1'},service_controller=object())
        request=object.__new__(handler);request.path='/api/service/models/upload';request.reply=Mock()
        request.rfile=SimpleNamespace(read=Mock(side_effect=AssertionError('obsolete upload body read')))
        request.do_POST();self.assertEqual(request.reply.call_args.args[1],405)
        self.assertFalse(hasattr(ServiceTransport,'import_model'))
        self.assertFalse(hasattr(ServiceController,'import_model'))
        for function in ('import_package','assign_model','delete_model'):
            self.assertFalse(hasattr(models,function))

    def test_runtime_import_and_assignment_commands_are_retired(self):
        for action in ('import-model','assign-model','delete-model','model-assignment','validate-advanced'):
            with self.subTest(action=action),patch.object(sys,'argv',['runtime.py',action]),self.assertRaisesRegex(ValueError,'不支持'):
                runtime.main()

    def test_install_cleanup_removes_retired_feature_modules(self):
        spec=importlib.util.spec_from_file_location('builtin_install',ROOT/'packaging/install-files.py')
        installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);bundle=base/'bundle';live=base/'live';bundle.mkdir();live.mkdir()
            (bundle/'install-files.json').write_text('[]');(bundle/'management-profile.json').write_text(json.dumps(PROFILE))
            for name in ('advanced_parameters.py','model_preflight.py'):(live/name).write_text('obsolete')
            installer.cleanup(bundle,live)
            for name in ('advanced_parameters.py','model_preflight.py'):
                self.assertFalse((live/name).exists());self.assertFalse((ROOT/'packaging'/name).exists())
        # The actual installer clears the old persistent override on upgrades.
        self.assertIn('rm -f -- "$config_dir/servo-test-parameters.json"',(ROOT/'packaging/service.sh').read_text())

    def test_kick_api_and_ipc_relay_do_not_expose_arbitrary_skills(self):
        self.assertEqual(validate(COMMAND),COMMAND)
        for name,supported in [('stand_test',True),('kick_left',True),('kick_right',False)]:
            with self.subTest(name=name,supported=supported),self.assertRaises(ControlError):validate({**COMMAND,'name':name,'supported':supported})
        with patch.object(service_rpc.socket,'socket',side_effect=AssertionError('unauthorized RPC connected')):
            with self.assertRaisesRegex(ValueError,'right kick'):service_rpc.execute({'method':'robot.do','params':{'skill':'stand_test'}})

    def test_kick_success_uses_one_original_robot_do_rpc_without_home_start_or_pause(self):
        calls=[]
        channel=SimpleNamespace(request=lambda request,**_:calls.append(request) or {'id':1,'result':{'accepted':True}})
        transport=ServiceTransport(None,"/run/robotd.sock");transport.channel=channel
        store=Store();controller=ServiceController(store,transport=transport)
        with patch('service_control.threading.Thread',ImmediateThread):
            result=controller.handle({'client':'kick-page-154','seq':1,'command':COMMAND})
        self.assertTrue(result['accepted']);self.assertEqual(controller.job['status'],'completed')
        self.assertEqual([(c['method'],c['params']) for c in calls],[('robot.do',{'skill':'kick_right'})])
        self.assertFalse(store.service_operation);self.assertTrue(all(not r.get('input') for r in store.records))

    def test_kick_relay_uses_existing_unix_json_rpc_protocol(self):
        received=[];errors=[]
        with tempfile.TemporaryDirectory() as tmp:
            path=str(Path(tmp)/'robotd.sock')
            original_socket=socket.socket
            with original_socket(socket.AF_INET,socket.SOCK_STREAM) as listener:
                # This executor rejects AF_UNIX. Substitute only the OS endpoint;
                # the production relay still selects the sole robotd Unix socket.
                listener.bind(('127.0.0.1',0));listener.listen(1);listener.settimeout(2)
                def serve():
                    try:
                        with listener.accept()[0] as peer,peer.makefile('rb') as reader:
                            peer.settimeout(2);received.append(json.loads(reader.readline()))
                            peer.sendall(b'{"jsonrpc":"2.0","id":1,"result":{"accepted":true}}\n')
                    except Exception as exc:errors.append(exc)
                worker=threading.Thread(target=serve);worker.start()
                test=self
                class Endpoint:
                    def __init__(self):self.peer=original_socket(socket.AF_INET,socket.SOCK_STREAM)
                    def __enter__(self):return self
                    def __exit__(self,*_):self.peer.close()
                    def __getattr__(self,name):return getattr(self.peer,name)
                    def connect(self,endpoint):
                        test.assertEqual(endpoint,path);self.peer.connect(listener.getsockname())
                def open_socket(family,kind):
                    self.assertEqual((family,kind),(socket.AF_UNIX,socket.SOCK_STREAM));return Endpoint()
                with patch.object(sys,'argv',['service_rpc.py',path]),patch.object(service_rpc,'socket',SimpleNamespace(AF_UNIX=socket.AF_UNIX,SOCK_STREAM=socket.SOCK_STREAM,socket=open_socket)):
                    result=service_rpc.execute({'method':'robot.do','params':{'skill':'kick_right'}})
                worker.join(2);self.assertFalse(worker.is_alive())
            self.assertEqual(errors,[]);self.assertTrue(result['result']['accepted'])
            self.assertEqual(received,[{'jsonrpc':'2.0','id':1,'method':'robot.do','params':{'skill':'kick_right'}}])

    def test_kick_unready_states_reject_without_job_or_rpc(self):
        cases=[('fresh',lambda s:s.update(service_sample_fresh=False),'新鲜'),
               ('mode',lambda s:s['bus'].update(mode='commissioning'),'运动模式'),
               ('phase',lambda s:s['bus'].update(phase='ready'),'运动模式'),
               ('imu',lambda s:s['bus']['native'].update(imu_ready=False),'IMU'),
               ('torque',lambda s:s['bus']['native'].update(torque_state_confirmed=False),'上力'),
               ('relax',lambda s:s['bus'].update(torque_off_pending=True),'上力'),
               ('home',lambda s:s['bus'].update(homed=False),'HOME'),
               ('policy',lambda s:s['bus'].update(policy_enabled=False),'Start'),
               ('model',lambda s:s['capabilities'].update(skills=[]),'尚未加载')]
        for name,change,message in cases:
            with self.subTest(name=name):
                store=Store();change(store.data);transport=SimpleNamespace(call=Mock())
                controller=ServiceController(store,transport=transport)
                with self.assertRaisesRegex(ControlError,message):controller.handle({'client':'kick-page-154','seq':1,'command':COMMAND})
                self.assertIsNone(controller.job);self.assertFalse(controller.busy);transport.call.assert_not_called()

    def test_native_kick_refusal_is_not_queued_retried_or_recovered(self):
        calls=[]
        transport=ServiceTransport(None,"/run/robotd.sock")
        transport.channel=SimpleNamespace(request=lambda request,**_:calls.append(request) or {'id':1,'result':{'accepted':False,'reason':'policy driving'}})
        controller=ServiceController(Store(),transport=transport)
        with patch('service_control.threading.Thread',ImmediateThread):controller.handle({'client':'kick-page-154','seq':1,'command':COMMAND})
        self.assertEqual(controller.job['status'],'error');self.assertEqual(controller.job['error'],'policy driving')
        self.assertEqual(len(calls),1);self.assertFalse(controller.store.service_operation)

    def test_webpad_frames_remain_available_during_kick_but_not_maintenance(self):
        for action,allowed in [('run-skill',True),('upgrade-service',False)]:
            with self.subTest(action=action):
                store=Store();store.data['service_control']={'busy':True,'job':{'action':action}}
                transport=SimpleNamespace(call=Mock(return_value={'accepted':True}),connected=True)
                controller=controls.Controller(store,transport=transport)
                payload={'action':'webpad_state','client':'kick-page-154','seq':1,'frame':{'buttons':[]}}
                if allowed:self.assertTrue(controller.handle(payload)['accepted']);transport.call.assert_called_once()
                else:
                    with self.assertRaisesRegex(ControlError,'等待服务操作'):controller.handle(payload)
                    transport.call.assert_not_called()

    def configure(self,saved,previous):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);source=base/'saved.toml';prior=base/'previous.toml';out=base/'new.toml';cal=base/'calibration.toml'
            source.write_text(dumps(saved));prior.write_text(dumps(previous));cal.write_bytes(b'mounted calibration')
            subprocess.run([sys.executable,str(ROOT/'packaging/configure.py'),'--source',str(source),
                '--previous-overrides',str(prior),'--overrides',str(ROOT/'packaging/robotd-profile.toml'),
                '--output',str(out)],check=True,capture_output=True)
            self.assertEqual(cal.read_bytes(),b'mounted calibration')
            return tomllib.loads(out.read_text())

    def test_first_kick_migration_retires_standalone_recovery_and_preserves_joint_tuning(self):
        defaults=tomllib.loads((ROOT/'packaging/robotd-profile.toml').read_text());previous=copy.deepcopy(defaults)
        previous['policy']['kick_right']='none';previous['policy']['skill']=[s for s in previous['policy']['skill'] if s['name']!='kick_right']
        saved=copy.deepcopy(previous);saved['policy'].update(custom_only=True,action_scale=.63,head_lowpass=.41,legs_lowpass=.69)
        saved['policy']['skill'] += [{'name':'stand_test','path':'/old/teacher.onnx','duration':6},{'name':'operator_skill','duration':3}]
        saved['pad'].update(lb='stand_test',rb='')
        result=self.configure(saved,previous)
        self.assertEqual(result['policy']['walk'],saved['policy']['walk']);self.assertEqual(result['policy']['action_scale'],.63)
        self.assertEqual(result['policy']['head_lowpass'],.41);self.assertEqual(result['policy']['legs_lowpass'],.69)
        self.assertEqual(result['policy']['stand'],'none');self.assertNotIn('stand_test',[s['name'] for s in result['policy']['skill']])
        self.assertEqual(result['pad']['lb'],'kick_left');self.assertEqual(result['pad']['rb'],'kick_right')
        self.assertEqual(result['policy']['kick_right'],defaults['policy']['kick_right'])
        kick=next(s for s in result['policy']['skill'] if s['name']=='kick_right')
        self.assertEqual(kick,next(s for s in defaults['policy']['skill'] if s['name']=='kick_right'))
        self.assertIn({'name':'operator_skill','duration':3},result['policy']['skill'])

    def test_repeat_install_preserves_kick_scale_timing_and_other_custom_pad_bindings(self):
        defaults=tomllib.loads((ROOT/'packaging/robotd-profile.toml').read_text());saved=copy.deepcopy(defaults)
        saved['policy']['custom_only']=True;saved['pad'].update(lb='operator_skill',rb='other_skill')
        kick=next(s for s in saved['policy']['skill'] if s['name']=='kick_right');kick['duration']=.8;kick['params']['action_scale']=.7
        self.assertEqual(self.configure(saved,defaults),saved)

if __name__=='__main__':unittest.main()

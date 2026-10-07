"""Power acknowledgement controls local connection lifecycle; no robot movement."""
import copy,io,json,shlex,subprocess,sys,tempfile,threading,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'console'))
import console
from controls import Controller,ControlError
from service_control import ServiceController,ServiceTransport
from telemetry import Store

class MemoryStore:
    service_operation=False
    def __init__(self):self.connection_paused=threading.Event();self.boot='before';self.commands=[]
    def snapshot(self):return {'system':{'boot_id':self.boot},'bus':{},'service_sample_fresh':False}
    def record_service_command(self,row):self.commands.append(copy.deepcopy(row))
class Input:
    connected=False;audio_status={};pad_status={}
    def __init__(self):self.suspended=False;self.calls=[]
    def suspend(self):self.suspended=True
    def resume(self):self.suspended=False
    def call(self,row):self.calls.append(row);return {'accepted':True}
class PowerTransport:
    def __init__(self):self.disconnected=False;self.channel=SimpleNamespace(disconnect=lambda:setattr(self,'disconnected',True))
    def power(self,action,password=None):return {'scheduled':True,'power_action':action}

class PowerConnectionTests(unittest.TestCase):
    def test_power_sends_one_os_command_without_installed_firmware_gate(self):
        transport=ServiceTransport('', '/unused')
        with patch.object(transport,'_manage',return_value={'scheduled':True}) as manage,patch.object(transport,'manage',side_effect=AssertionError('no installed helper dependency')):
            self.assertTrue(transport.power('shutdown')['scheduled'])
        command=manage.call_args.args[0]
        self.assertEqual(command,['/usr/bin/systemctl','--no-block','poweroff'])
        self.assertEqual(manage.call_count,1)

    def test_power_has_no_collection_pause_or_upgrade_readiness_gate(self):
        for action in ('shutdown','reboot'):
            store=MemoryStore();store.connection_paused.set();transport=PowerTransport();service=ServiceController(store,transport=transport)
            service.busy=True;service.stopping=True;service.job={'action':'upgrade-service','status':'running'}
            answer=service.handle({'client':'power-test','seq':1,'command':{'action':action}})
            self.assertTrue(answer['accepted']);deadline=time.monotonic()+2
            while service.job['status']=='running' and time.monotonic()<deadline:time.sleep(.01)
            self.assertEqual(service.job['status'],'completed',service.job)
            self.assertEqual(store.connection_paused.is_set(),action=='shutdown')

    def test_acknowledged_shutdown_blocks_all_input_and_probes_until_explicit_resume(self):
        store=MemoryStore();input=Input();controls=Controller(store,transport=input);transport=PowerTransport()
        service=ServiceController(store,transport=transport,controls=controls)
        job={'action':'shutdown','status':'running'};service._execute({'action':'shutdown'},job,0)
        self.assertEqual(job['status'],'completed');self.assertTrue(store.connection_paused.is_set())
        self.assertTrue(input.suspended);self.assertTrue(transport.disconnected)
        service.power_boot_id='before';service.job=job;store.boot='unexpected-new-boot'
        self.assertTrue(service.status()['stopping'],'intentional shutdown requires explicit resume')
        with self.assertRaises(ControlError):controls.handle({'client':'power-test','seq':1,'action':'connect'})
        with self.assertRaises(ControlError):service.connection()
        with self.assertRaises(ControlError):service.models()
        controls.release_owner('power-test');self.assertEqual(input.calls,[])
        result=service.handle({'client':'power-test','seq':2,'command':{'action':'resume-connection'}})
        self.assertTrue(result['accepted']);self.assertFalse(store.connection_paused.is_set());self.assertFalse(input.suspended)
        self.assertFalse(service.stopping);self.assertEqual(input.calls,[],'resume must not issue HOME or enable')
    def test_failed_shutdown_does_not_report_off_or_suspend_connections(self):
        store=MemoryStore();transport=PowerTransport()
        transport.power=lambda *_args,**_kwargs:(_ for _ in ()).throw(RuntimeError('systemd unavailable'))
        service=ServiceController(store,transport=transport);job={'action':'shutdown','status':'running'}
        service._execute({'action':'shutdown'},job,0)
        self.assertEqual(job['status'],'error');self.assertFalse(store.connection_paused.is_set());self.assertFalse(transport.disconnected)
    def test_reboot_retains_reconnect_and_unblocks_on_new_boot(self):
        store=MemoryStore();transport=PowerTransport();service=ServiceController(store,transport=transport)
        service.power_boot_id=store.boot;job={'action':'reboot','status':'running'};service.job=job
        service._execute({'action':'reboot'},job,0)
        self.assertFalse(store.connection_paused.is_set());self.assertFalse(transport.disconnected);self.assertTrue(service.stopping)
        store.boot='after';self.assertFalse(service.status()['stopping']);self.assertTrue(job['result']['reconnected'])
    def test_collector_pause_prevents_process_creation_and_resume_starts_only_one(self):
        # Exercise the real observer loop using a harmless local process in place
        # of SSH. It must stop retrying, then resume collection without any action.
        stop=threading.Event();paused=threading.Event();paused.set();seen=threading.Event();spawned=[];errors=[]
        real_popen=subprocess.Popen
        simulator="import sys,json,time;sys.stdin.read();print(json.dumps({'channel':'collector','data':{}}),flush=True);time.sleep(10)"
        def spawn(*args,**kwargs):
            child=real_popen(*args,**kwargs);spawned.append(child);return child
        log=SimpleNamespace(add=lambda source,message:errors.append((source,message)))
        with patch.object(console,'ssh_command',return_value=[sys.executable,'-u','-c',simulator]),patch.object(console.subprocess,'Popen',side_effect=spawn):
            worker=threading.Thread(target=console.ssh_loop,args=('ignored',{},lambda _:seen.set(),stop,log,paused));worker.start()
            try:
                self.assertFalse(seen.wait(.25));self.assertEqual(spawned,[])
                paused.clear();self.assertTrue(seen.wait(3));self.assertEqual(len(spawned),1)
                paused.set();stop.wait(.7);self.assertEqual(len(spawned),1);self.assertIsNotNone(spawned[0].poll())
                self.assertFalse(any(source=='采集 SSH / 错误' for source,_ in errors))
            finally:
                stop.set();worker.join(3)
                for child in spawned:
                    if child.poll() is None:child.kill();child.wait()
                self.assertFalse(worker.is_alive())
    def test_upgrade_cleanup_is_privileged_and_preserves_original_install_error(self):
        directory='/tmp/microduck-upgrade-AbCd1234EfGh';transport=ServiceTransport('radxa@127.0.0.1','/unused');calls=[]
        def manage(command,password=None,**_):
            calls.append((command,password))
            if command[0]=='mktemp':return {'message':directory}
            if command[0]=='/bin/bash':raise ControlError('actual install error')
            return {'message':'removed'}
        from staging_upload import StagingUpload
        with tempfile.TemporaryDirectory() as temporary:
            archive=Path(temporary)/'package';archive.write_bytes(b'archive')
            replies=iter([SimpleNamespace(returncode=0,stdout=(directory+'\n').encode()),SimpleNamespace(returncode=0,stderr=b'')])
            with patch('service_control.bundle_info',return_value={}),patch.object(transport,'_ssh_run',side_effect=AssertionError('must reuse management SSH')),patch.object(StagingUpload,'upload'),patch.object(transport,'_manage',side_effect=manage):
                with self.assertRaisesRegex(ControlError,'actual install error'):transport.upgrade(password='secret',archive=archive)
        self.assertEqual(calls[-1],(['/bin/rm','-rf','--',directory],'secret'))
    def test_installation_disables_bytecode_cache_for_python_children(self):
        # Execute the actual shell setup prefix and import a fresh module. This
        # reproduces cache creation without needing privileged filesystem writes.
        prefix=(ROOT/'packaging/service.sh').read_text().split('bundle_dir=',1)[0]
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'module.py').write_text('value=1\n')
            command=prefix+'\ncd '+shlex.quote(temporary)+'\n'+shlex.quote(sys.executable)+' -c "import module"\n'
            subprocess.run(['bash','-c',command],check=True,capture_output=True)
            self.assertFalse((root/'__pycache__').exists())

if __name__=='__main__':unittest.main()

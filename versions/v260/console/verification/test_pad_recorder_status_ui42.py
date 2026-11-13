"""Physical recorder status stays display-only on the existing input SSH session."""
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import remote_input

def drive_module():
    stage=ROOT.parent/'ui43_firmware_stage/Microduck-Robotd-FT6-R17/drive_settings.py'
    if stage.exists():source=stage.read_text()
    else:
        with tarfile.open(ROOT/'updates/Microduck-Robotd-FT6-R17.tar.gz') as archive:
            source=archive.extractfile('Microduck-Robotd-FT6-R17/drive_settings.py').read().decode()
    module=types.ModuleType('recorder_drive_fixture')
    exec(compile(source,str(stage),'exec'),module.__dict__)
    return module

class RecorderReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.drive=drive_module();d=self.drive
        d.PATH=self.root/'drive.json';d.REPORT=self.root/'input-settings.json'
        d.RECORDER=self.root/'recorder.json';d.PROC=self.root/'proc'
        self.now=10_000
        clock=patch.object(d.time,'monotonic_ns',lambda:self.now*1_000_000);clock.start();self.addCleanup(clock.stop)
        d.REPORT.write_text(json.dumps({'pid':123}))
        proc=d.PROC/'123';proc.mkdir(parents=True)
        (proc/'cmdline').write_bytes(('\0'.join([str(d.BASE/'padd'),'--max-linear','0.3','--max-linear-backward','0.3'])+'\0').encode())
        self.data={'pid':123,'t_ms':9500,'phase':'playing','elapsed_ms':1200,'duration_ms':6000,'has_last':True,'reason':''}
        self.write()
    def write(self):self.drive.RECORDER.write_text(json.dumps(self.data))
    def test_verified_pid_and_clock_keep_existing_speed_result(self):
        before=self.drive.REPORT.read_bytes();result=self.drive.status()
        self.assertEqual(result['speed'],.3);self.assertNotIn('error',result)
        self.assertTrue(result['recorder']['available'])
        self.assertEqual(result['recorder']['phase'],'playing')
        self.assertEqual(result['recorder']['checked_ms'],self.now)
        self.assertEqual(self.drive.REPORT.read_bytes(),before,'display reads never write input settings')
    def test_stale_future_or_wrong_pid_report_never_becomes_saved(self):
        for change in [{'pid':456},{'pid':True},{'t_ms':6999},{'t_ms':10001}]:
            with self.subTest(change=change):
                self.drive.RECORDER.write_text(json.dumps({**self.data,**change}))
                value=self.drive.status();self.assertEqual(value['speed'],.3)
                self.assertFalse(value['recorder']['available'])
                self.assertNotIn('has_last',value['recorder'])
        self.data['t_ms']=7000;self.write()
        self.assertTrue(self.drive.status()['recorder']['available'],'three-second boundary is inclusive')
    def test_current_process_must_be_padd(self):
        (self.drive.PROC/'123/cmdline').write_bytes(b'python3\0')
        self.assertFalse(self.drive.status()['recorder']['available'])
        (self.drive.PROC/'123/cmdline').unlink()
        self.assertFalse(self.drive.status()['recorder']['available'])
    def test_bad_report_is_bounded_and_does_not_break_speed_controls(self):
        for change in [{'phase':'saved'},{'phase':[]},{'elapsed_ms':True},{'duration_ms':-1},{'elapsed_ms':1.5},{'has_last':'yes'},{'reason':[]}]:
            with self.subTest(change=change):
                self.drive.RECORDER.write_text(json.dumps({**self.data,**change}))
                value=self.drive.status();self.assertEqual(value['speed'],.3)
                self.assertFalse(value['recorder']['available'])
        self.drive.RECORDER.write_bytes(b' '*16385)
        self.assertFalse(self.drive.status()['recorder']['available'])
        self.drive.RECORDER.write_text('{broken')
        self.assertFalse(self.drive.status()['recorder']['available'])
    def test_old_firmware_missing_report_is_a_support_hint(self):
        self.drive.RECORDER.unlink();value=self.drive.status()
        self.assertEqual(value['speed'],.3);self.assertFalse(value['recorder']['available'])
        self.assertEqual(value['recorder']['reason'],'安装配套更新后支持录放')
    def test_idle_without_last_is_not_a_saved_recording(self):
        self.data.update(phase='idle',elapsed_ms=0,duration_ms=0,has_last=False);self.write()
        value=self.drive.status()['recorder'];self.assertTrue(value['available']);self.assertFalse(value['has_last'])

class Native:
    def __init__(self):self.calls=[]
    def request(self,*args):self.calls.append(('request',args));raise AssertionError('status refresh must not call robotd')
    def notify(self,*args):self.calls.append(('notify',args))
    def close(self):pass

class IdleWakeTests(unittest.TestCase):
    def test_one_hz_timeout_never_extends_input_lease(self):
        now=[0.];robot=Native()
        with patch.object(remote_input,'drive_reader',return_value=lambda:{'supported':True,'speed':.2}):
            control=remote_input.Input(robot,lambda:now[0])
        self.assertIsNone(remote_input.status_wait_timeout(control,1))
        control.real=[{'name':'physical'}]
        self.assertEqual(remote_input.status_wait_timeout(control,1),1)
        control.deadline=.25
        self.assertEqual(remote_input.status_wait_timeout(control,1),.25)
        self.assertEqual(control.deadline,.25)
        control.real=[]
        self.assertEqual(remote_input.status_wait_timeout(control,1),.25)
        now[0]=.3
        self.assertEqual(remote_input.status_wait_timeout(control,1),0)
        self.assertEqual(robot.calls,[],'computing display timeout cannot emit any action')
    def test_real_pad_status_refreshes_but_disconnected_idle_sleeps(self):
        now=[0.];robot=Native();reads=[];outputs=[]
        def read_drive():
            reads.append(now[0]);return {'supported':True,'speed':.2,'recorder':{'phase':'recording','elapsed_ms':int(now[0]*1000)}}
        with patch.object(remote_input,'drive_reader',return_value=read_drive):control=remote_input.Input(robot,lambda:now[0])
        class Peer:
            def __init__(self):self.pending=[]
            def recv(self,_):
                if self.pending:return self.pending.pop(0)
                raise BlockingIOError()
            def close(self):pass
        peer=Peer()
        class Selector:
            def __init__(self):self.timeouts=[]
            def register(self,*args):pass
            def select(self,timeout):
                self.timeouts.append(timeout)
                if len(self.timeouts)==1:
                    now[0]+=timeout;return []
                if len(self.timeouts)==2:
                    now[0]+=timeout;peer.pending.append(b'SUBSYSTEM=input\0ACTION=remove\0')
                    return [(types.SimpleNamespace(data='hotplug'),None)]
                return [(types.SimpleNamespace(data='input'),None)]
            def close(self):pass
        selector=Selector();stdin=types.SimpleNamespace(buffer=object(),fileno=lambda:0)
        def capture(value,**_):outputs.append(json.loads(value))
        with patch.object(remote_input,'Input',return_value=control),patch.object(remote_input,'Robot',return_value=robot),\
             patch.object(remote_input,'monitor',return_value=peer),patch.object(remote_input,'devices',side_effect=[[{'name':'physical'}],[]]) as devices,\
             patch.object(remote_input.selectors,'DefaultSelector',return_value=selector),patch.object(remote_input.sys,'stdin',stdin),\
             patch.object(remote_input.os,'read',return_value=b''),patch('builtins.print',side_effect=capture):
            remote_input.run('/run/robotd.sock')
        self.assertEqual(selector.timeouts,[1,1,None])
        self.assertEqual(devices.call_count,2,'only initial read and kernel hotplug may discover devices')
        self.assertEqual(reads,[0,1,2])
        self.assertEqual(outputs[1]['payload']['drive_speed']['recorder']['elapsed_ms'],1000)
        self.assertEqual(robot.calls,[],'periodic display status never requests or notifies robotd')
        self.assertIsNone(control.owner);self.assertIsNone(control.deadline)

if __name__=='__main__':unittest.main()

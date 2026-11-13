"""Bounded action input pauses, tested without hardware or native motor IPC."""
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
import ai_input_lease as leases
from ai_action_gate import ActionDenied
from ai_remote import RemoteAI,worker_bundle
from ai_runtime import AIHub
from ai_zero import GateRelay
import service_rpc
from verification.test_ai_v200 import FakeRobot

TOKEN='a'*32


class LeaseFilesTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.directory=Path(self.temp.name)

    def write(self,suffix,value):
        (self.directory/(TOKEN+'.'+suffix)).write_text(str(value)+'\n')

    def test_worker_and_standalone_rpc_share_the_same_fail_closed_file_rules(self):
        now=time.monotonic_ns()//1_000_000
        cases=[('current',now+700,now+700,None,False,True),
               ('renewal_pending',now+700,now+500,None,False,True),
               ('missing_ack',now+700,None,None,False,False),
               ('expired_ack',now+700,now-1,None,False,False),
               ('expired_lease',now-1,now+500,None,False,False),
               ('future_lease',now+3000,now+500,None,False,False),
               ('ack_ahead',now+500,now+700,None,False,False),
               ('manual_cancel',now+700,now+700,'manual-select',False,False),
               ('empty_cancel',now+700,now+700,'',False,False),
               ('solo_then_padd_starts',now+700,now+700,None,True,False)]
        for label,expiry,ack,cancel,solo,valid in cases:
            with self.subTest(case=label):
                for path in self.directory.iterdir():path.unlink()
                self.write('lease',expiry)
                if ack is not None:self.write('ack',ack)
                if cancel is not None:self.write('cancel',cancel)
                if solo:self.write('solo',expiry)
                validators=(lambda:leases.validate_input_token(TOKEN,directory=self.directory,requires_ack=lambda:True),
                            lambda:service_rpc.validate_ai_input_token(TOKEN,directory=self.directory))
                with patch('service_rpc._input_padd_running',return_value=True):
                    for validate in validators:
                        if valid:self.assertEqual(validate(),expiry)
                        else:
                            with self.assertRaises(ValueError):validate()
        for token in (None,'../'+TOKEN,'A'*32,'a'*31):
            with self.subTest(token=token):
                with self.assertRaises(ValueError):leases.validate_input_token(token,directory=self.directory)
                with self.assertRaises(ValueError):service_rpc.validate_ai_input_token(token,directory=self.directory)

    def test_initial_ack_must_be_exact_but_live_previous_renewal_ack_is_valid(self):
        now=time.monotonic_ns()//1_000_000
        self.write('lease',now+700);self.write('ack',now+500)
        leases.validate_input_token(TOKEN,directory=self.directory)
        with self.assertRaisesRegex(ValueError,'尚未确认'):
            leases.validate_input_token(TOKEN,directory=self.directory,exact=True)

    def test_running_old_padd_never_gets_self_ack_and_native_cancel_reason_survives(self):
        lease=leases.InputLease(lambda:False,directory=self.directory,requires_ack=lambda:True)
        self.addCleanup(lease.close)
        lease._prepare();lease._refresh()
        self.assertFalse(lease.ack.exists());self.assertFalse(lease.solo.exists())
        lease.path.with_suffix('.cancel').write_text('imu-head\n')
        with self.assertRaisesRegex(ValueError,'关闭实体手柄 IMU'):
            lease.acquire()
        self.assertFalse(list(self.directory.iterdir()))

    def test_no_padd_acquire_renews_and_cleanup_invalidates_late_ack(self):
        running=[False]
        lease=leases.InputLease(lambda:False,directory=self.directory,requires_ack=lambda:running[0])
        self.addCleanup(lease.close);lease.acquire();lease.ensure_current()
        self.assertTrue(lease.solo.exists())
        running[0]=True
        with self.assertRaisesRegex(ValueError,'服务已启动'):lease.ensure_current()
        lease.close()
        lease.ack.write_text(str(time.monotonic_ns()//1_000_000+700))
        with self.assertRaises(ValueError):lease.ensure_current()
        with self.assertRaises(ValueError):leases.validate_input_token(lease.token,directory=self.directory)

    def test_native_exact_ack_precedes_acquire_and_cancel_stops_renewal(self):
        lease=leases.InputLease(lambda:False,directory=self.directory,requires_ack=lambda:True)
        self.addCleanup(lease.close)
        acknowledged=threading.Event()
        def padd():
            deadline=time.monotonic()+1
            while time.monotonic()<deadline:
                try:value=lease.path.read_text()
                except FileNotFoundError:time.sleep(.005);continue
                lease.ack.write_text(value);acknowledged.set();return
        thread=threading.Thread(target=padd);thread.start()
        try:lease.acquire()
        finally:thread.join(1)
        self.assertTrue(acknowledged.is_set());lease.ensure_current()
        lease.path.with_suffix('.cancel').write_text('manual-select\n')
        with self.assertRaisesRegex(ValueError,'Select'):lease.ensure_current()
        with self.assertRaisesRegex(ValueError,'Select'):lease._refresh()
        lease.close();self.assertFalse(list(self.directory.iterdir()))


class StandaloneRPCTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.directory=Path(self.temp.name)
        expiry=time.monotonic_ns()//1_000_000+700
        for suffix in ('lease','ack'):(self.directory/(TOKEN+'.'+suffix)).write_text(str(expiry))
        self.patch=patch('service_rpc.AI_INPUT_DIRECTORY',self.directory);self.patch.start();self.addCleanup(self.patch.stop)
        self.sent=[];self.on_connect=lambda:None
        outer=self
        class Socket:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def settimeout(self,value):pass
            def connect(self,path):outer.on_connect()
            def sendall(self,data):outer.sent.append(json.loads(data))
            def makefile(self,*args):return io.BytesIO(b'{"jsonrpc":"2.0","id":1,"result":{"accepted":true}}\n')
        self.socket_patch=patch('service_rpc.socket.socket',return_value=Socket());self.socket_patch.start();self.addCleanup(self.socket_patch.stop)

    def call(self,method='robot.move'):
        with patch.object(sys,'argv',['service_rpc.py','/tmp/fixture.sock']):
            return service_rpc.execute({'method':method,'params':{'vx':.1},'ai_input_token':TOKEN})

    def test_token_is_rechecked_after_connect_and_never_enters_robotd_params(self):
        self.assertTrue(self.call()['result']['accepted'])
        self.assertEqual(self.sent,[{'jsonrpc':'2.0','id':1,'method':'robot.move','params':{'vx':.1}}])
        self.sent.clear()
        self.on_connect=lambda:(self.directory/(TOKEN+'.cancel')).write_text('manual-select')
        with self.assertRaisesRegex(ValueError,'取消'):self.call()
        self.assertFalse(self.sent)

    def test_lease_cannot_enable_or_initialize_robot(self):
        for method in ('robot.enable','robot.init','robot.relax','robot.busCommand'):
            with self.subTest(method=method),self.assertRaisesRegex(ValueError,'不能上力'):
                self.call(method)
        self.assertFalse(self.sent)


class RelayOrderingTests(unittest.TestCase):
    def fixture(self,deny=False,cancel_result=False):
        self.order=[];self.current=True
        outer=self
        class Lease:
            token=TOKEN
            def __init__(self,cancelled):self.cancelled=cancelled
            def acquire(self):
                outer.order.append('ack')
                if deny:raise ValueError('not-neutral')
            def ensure_current(self):
                if not outer.current:raise ValueError('manual-select')
            def close(self):outer.order.append('release')
        hub=SimpleNamespace(stop=threading.Event(),muted=True,provider=None,vision=SimpleNamespace(ready=False))
        relay=GateRelay(hub,[]);relay.lease_factory=Lease
        def log(kind,**fields):
            self.order.append(kind)
            if kind=='action_request':
                self.assertEqual(fields['ai_input_token'],TOKEN)
                self.current=not cancel_result
                relay.feedback(fields['request_id'],{'accepted':True,'status':'completed'})
        hub.log=log
        return relay

    def test_ack_then_request_then_result_validation_then_release(self):
        relay=self.fixture()
        self.assertEqual(relay.execute('perform_skill',{'skill':'roulade'})['status'],'completed')
        self.assertEqual(self.order,['ack','action_request','action_cancelled','release'])
        relay=self.fixture(deny=True)
        self.assertFalse(relay.execute('head_pose',{})['accepted'])
        self.assertNotIn('action_request',self.order)
        relay=self.fixture(cancel_result=True)
        result=relay.execute('perform_skill',{'skill':'roulade'})
        self.assertFalse(result['accepted']);self.assertIn('manual-select',result['reason'])
        self.assertEqual(self.order[-1],'release')


class ActionContextTests(unittest.TestCase):
    def setUp(self):
        self.robot=FakeRobot();self.gate=self.robot.gate;self.gate.set_skills(self.robot.skills)

    def test_action_token_is_thread_local_and_never_inherited_by_pcm_mouth(self):
        calls=[]
        source=self.gate.rpc
        self.gate.rpc=lambda method,args:(calls.append((method,self.gate.input_token())) or source(method,args))
        with self.gate.input_lease_context(TOKEN,lambda:False):
            self.gate.execute('mouth_pose',{'open':.4})
            thread=threading.Thread(target=lambda:self.gate.follow_speech_mouth(.6));thread.start();thread.join(1)
            self.assertEqual(self.gate.input_token(),TOKEN)
        self.assertIsNone(self.gate.input_token())
        self.assertEqual(calls,[('robot.mouth',TOKEN),('robot.mouth',None)])

    def test_cancelled_walk_and_body_do_not_issue_a_tokenless_cleanup_or_mask_error(self):
        for name,args in (('walk_short',{'vx':.1,'vy':0,'vyaw':0,'seconds':.2}),
                          ('body_pose',{'z':0,'pitch':.1,'roll':0,'seconds':.2})):
            with self.subTest(name=name):
                self.setUp();cancelled=threading.Event()
                def sleep(seconds):
                    cancelled.set();raise ActionDenied('original manual interruption')
                self.gate.sleep=sleep
                with self.gate.input_lease_context(TOKEN,cancelled.is_set):
                    with self.assertRaisesRegex(ActionDenied,'original manual interruption'):
                        self.gate.execute(name,args)
                self.assertEqual(len(self.robot.calls),1)
                self.assertIsNone(self.gate.input_token())

    def test_sit_confirms_only_fresh_mode_entry_and_rise_keeps_finite_completion(self):
        result=self.gate.execute('perform_skill',{'skill':'sit_toggle'})
        self.assertEqual(result['status'],'sit_mode_entered_not_completion')
        self.assertGreater(result['mode_entered_t_ns'],50_000_000_000)
        self.assertNotIn('model_completed_t_ns',result)
        result=self.gate.execute('perform_skill',{'skill':'sit_toggle'})
        self.assertEqual(result['status'],'completed')
        self.assertGreater(result['model_completed_t_ns'],result['model_started_t_ns'])

    def test_rpc_attaches_internal_token_without_altering_robotd_parameters(self):
        payloads=[]
        hub=AIHub(SimpleNamespace(peek=lambda:{}),connection=SimpleNamespace(active=True))
        self.addCleanup(hub.close);hub.service_controller=object()
        hub._get_ai_channel=lambda:SimpleNamespace(request=lambda req,**kw:payloads.append(req) or {'id':1,'result':{'accepted':True}})
        with hub.gate.input_lease_context(TOKEN,lambda:False):hub.rpc('robot.move',{'vx':.1})
        hub.rpc('robot.mouth',{'open':.2})
        self.assertEqual(payloads[0]['ai_input_token'],TOKEN)
        self.assertEqual(payloads[0]['params'],{'vx':.1})
        self.assertNotIn('ai_input_token',payloads[1])

    def test_remote_cancelled_before_send_rejects_late_action_thread(self):
        replies=[];finished=threading.Event();execute_started=threading.Event();allow=threading.Event()
        original=self.gate.execute
        def delayed(*args):execute_started.set();allow.wait(1);return original(*args)
        self.gate.execute=delayed
        def request(payload,**kwargs):replies.append(payload);finished.set();return {'accepted':True}
        remote=RemoteAI(SimpleNamespace(gate=self.gate,log=lambda *a,**kw:None),SimpleNamespace(request=request),threading.Event())
        remote._event({'kind':'action_request','request_id':'b'*32,'name':'walk_short',
                       'arguments':{'vx':.1,'vy':0,'vyaw':0,'seconds':.2},'ai_input_token':TOKEN})
        self.assertTrue(execute_started.wait(1))
        remote._event({'kind':'action_cancelled','ai_input_token':TOKEN});allow.set()
        self.assertTrue(finished.wait(1));self.assertFalse(replies[0]['message']['result']['accepted'])
        self.assertFalse(self.robot.calls)
        # A delayed event has no active capability once the Zero lease is gone.
        remote.stop_event.set();finished.clear()
        remote._event({'kind':'action_request','request_id':'c'*32,'name':'head_pose',
                       'arguments':{},'ai_input_token':TOKEN})
        self.assertTrue(finished.wait(1));self.assertFalse(replies[-1]['message']['result']['accepted'])
        self.assertFalse(self.robot.calls)

    def test_worker_bundle_contains_input_helper(self):
        import base64,zipfile
        encoded,_=worker_bundle()
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(encoded))) as bundle:
            self.assertIn('ai_input_lease.py',bundle.namelist())


if __name__=='__main__':unittest.main()

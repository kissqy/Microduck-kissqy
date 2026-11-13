"""Model entry/exit is the capture barrier; it never adds head or posture moves."""
import contextlib
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from ai_action_gate import ActionDenied,ActionGate
from ai_conversation import Conversation
from ai_doubao import DoubaoNative
from ai_runtime import AIHub
from ai_remote import RemoteAI
from ai_vision import VisualService,validate_vision
from ai_zero import ZeroHub
from verification import test_ai_v200 as base
from verification import test_ai_vision_ui13 as camera


def image_info():
    return camera.PNG,{'captured_at_ms':round(time.time()*1000),'captured_t_ns':time.monotonic_ns(),
                       'read_ms':1,'image_ms':0,'capture_ms':1,'capture_backend':'fixture'}


class ModelCompletionTests(unittest.TestCase):
    def setUp(self):
        self.robot=base.FakeRobot();self.gate=self.robot.gate;self.gate.set_skills(self.robot.skills)

    def test_model_tool_waits_for_reported_entry_and_exit_before_returning_completed(self):
        result=self.gate.execute('perform_skill',{'skill':'roulade'})
        self.assertEqual(result['status'],'completed');self.assertEqual(result['completion_source'],'robot.state.policy')
        self.assertGreater(result['model_completed_t_ns'],result['model_started_t_ns'])
        self.assertGreaterEqual(self.robot.clock()-50,.25)
        self.assertEqual(self.robot.calls,[('robot.do',{'skill':'roulade'})])

    def test_duration_is_a_timeout_not_proof_of_completion(self):
        self.gate.model_timeouts['roulade']=3
        original=self.robot.rpc
        def rpc(method,args):
            receipt=original(method,args);self.robot.model_until=52.5;return receipt
        self.gate.rpc=rpc
        result=self.gate.execute('perform_skill',{'skill':'roulade'})
        self.assertEqual(result['status'],'completed');self.assertGreaterEqual(self.robot.clock(),52.5)

    def test_accepted_without_observed_model_start_is_not_completed(self):
        self.gate.rpc=lambda *args:{'accepted':True}
        with self.assertRaisesRegex(ActionDenied,'未观测到模型动作开始'):
            self.gate.execute('perform_skill',{'skill':'roulade'})

    def test_another_model_or_stale_feedback_cannot_finish_this_action(self):
        source=self.robot.state
        self.gate.monitor=lambda:{**source(),'policy':'kick_left' if self.robot.clock()>50.15 else source()['policy']}
        with self.assertRaisesRegex(ActionDenied,'其他模型'):
            self.gate.execute('perform_skill',{'skill':'roulade'})
        self.setUp();source=self.robot.state
        self.gate.monitor=lambda:{**source(),'state_fresh':self.robot.clock()<50.15}
        with self.assertRaisesRegex(ActionDenied,'新鲜的模型'):
            self.gate.execute('perform_skill',{'skill':'roulade'})

    def test_photo_waits_for_model_exit_without_any_motion_rpc(self):
        self.robot.active_model='roulade';self.robot.model_until=50.3
        result=self.gate.wait_capture_model()
        self.assertEqual(result['status'],'model_idle');self.assertGreaterEqual(self.robot.clock(),50.3)
        self.assertFalse(self.robot.calls,'the barrier must not home, turn the head or add a posture check')

    def test_photo_stale_missing_and_cancelled_state_fail_without_motion(self):
        for change in ({'state_fresh':False},{'state_t_ns':None},{'connected':False}):
            with self.subTest(change=change):
                source=self.robot.state;self.gate.monitor=lambda:{**source(),**change}
                with self.assertRaises(ActionDenied):self.gate.wait_capture_model()
        self.gate.cancelled=lambda:True
        with self.assertRaises(ActionDenied):self.gate.wait_capture_model()
        self.assertFalse(self.robot.calls)

    def test_existing_telemetry_monitor_never_polls_robot_policies(self):
        snap={'service_sample_fresh':True,'service_sample_age_ms':0,'bus':{},
              'state':{'policy':'walk','t_ns':123},'channels':{'state':{'status':'live','age_ms':0}}}
        hub=AIHub(SimpleNamespace(peek=lambda:snap),connection=SimpleNamespace(active=True))
        self.addCleanup(hub.close)
        hub.rpc=lambda *args:(_ for _ in ()).throw(AssertionError('no extra native query'))
        self.assertEqual(hub.gate.wait_capture_model()['model_completed_t_ns'],123)


class CaptureOrderingTests(unittest.TestCase):
    def test_motion_then_new_frame_and_no_parallel_motion_during_frame_capture(self):
        stop=threading.Event();hub=ZeroHub({'api_key':'fixture','tools':[],'vision':validate_vision(camera.VISION_KEY)},stop)
        self.addCleanup(hub.vision.close)
        model_started=threading.Event();finish_model=threading.Event();frame_started=threading.Event();finish_frame=threading.Event()
        order=[];results={};events=[]
        active=[False];ended=[False]
        def model_state():
            if active[0] and finish_model.is_set() and not ended[0]:ended[0]=True;order.append('model_end')
            return {'connected':True,'fresh':True,'motion_ready':True,'state_fresh':True,
                    'state_t_ns':time.monotonic_ns(),'policy':'roulade' if active[0] and not ended[0] else 'walk'}
        def model_rpc(method,args):
            self.assertEqual((method,args),('robot.do',{'skill':'roulade'}))
            active[0]=True;order.append('model_start');model_started.set();return {'accepted':True}
        pc_gate=ActionGate(model_rpc,model_state,lambda *a,**kw:None)
        pc_gate.set_skills({'skills':[{'name':'roulade','duration':3}],'built_in':[]})
        def log(kind,**fields):
            events.append({'kind':kind,**fields})
            if kind!='action_request':return
            if fields['name']=='perform_skill':
                reply=pc_gate.execute(fields['name'],fields['arguments'])
            elif fields['name']=='wait_capture_model':
                reply=pc_gate.wait_capture_model();order.append('model_confirmed')
            else:reply={'accepted':True,'available':False}
            hub.gate.feedback(fields['request_id'],reply)
        hub.log=log;hub.vision.log=log
        def capture(*args):
            order.append('frame');frame_started.set();finish_frame.wait(2);return image_info()
        motion=threading.Thread(target=lambda:results.update(motion=hub.gate.execute('perform_skill',{'skill':'roulade'})))
        photo=threading.Thread(target=lambda:results.update(photo=hub.vision.inspect({'question':'前面是什么？'})))
        with patch('ai_vision.capture_image',side_effect=capture),patch('ai_vision.understand_png',return_value='这是三轮车。'):
            try:
                motion.start();self.assertTrue(model_started.wait(1));photo.start()
                self.assertFalse(frame_started.wait(.1),'never take a photo while the model is running')
                finish_model.set();self.assertTrue(frame_started.wait(1))
                denied=hub.gate.execute('head_pose',{'head_yaw':1})
                self.assertFalse(denied['accepted'],'a later AI motion cannot sneak between confirmation and capture')
                finish_frame.set();motion.join(1);photo.join(2)
            finally:finish_model.set();finish_frame.set();stop.set();motion.join(1);photo.join(1)
        self.assertEqual(order,['model_start','model_end','model_confirmed','frame'])
        self.assertEqual(results['motion']['completion_source'],'robot.state.policy')
        self.assertTrue(results['photo']['accepted'])
        self.assertGreater(results['photo']['capture_requested_t_ns'],results['photo']['model_completed_t_ns'])
        self.assertEqual(results['photo']['frame_freshness'],'mediad_next_frame_requested_after_model_idle')
        self.assertFalse(any(e.get('name') in ('home','enable','head_pose') for e in events if e['kind']=='action_request'))

    def test_unconfirmed_model_never_captures_or_sends_an_image_to_vision(self):
        @contextlib.contextmanager
        def guard():raise ValueError('模型未结束');yield
        service=VisualService(validate_vision(camera.VISION_KEY),threading.Event(),lambda *a,**kw:None,capture_guard=guard)
        self.addCleanup(service.close)
        with patch('ai_vision.capture_image') as capture,patch('ai_vision.understand_png') as vision:
            result=service.inspect({'question':'是什么？'})
        self.assertFalse(result['accepted']);capture.assert_not_called();vision.assert_not_called()

    def test_plain_acceptance_is_not_a_model_completion_receipt(self):
        for reply in ({'accepted':True,'status':'pending'},{'accepted':True,'status':'model_idle'}):
            with self.subTest(reply=reply):
                hub=ZeroHub({'api_key':'fixture','tools':[],'vision':validate_vision(camera.VISION_KEY)},threading.Event())
                def log(kind,**fields):
                    if kind=='action_request':hub.gate.feedback(fields['request_id'],reply)
                hub.log=log;hub.vision.log=log
                try:
                    with patch('ai_vision.capture_image') as capture:
                        result=hub.vision.inspect({'question':'前面是什么？'})
                    self.assertFalse(result['accepted']);capture.assert_not_called()
                finally:hub.vision.close()

    def test_manual_photo_uses_the_same_model_barrier_and_keeps_the_original_pixels(self):
        order=[];stop=threading.Event()
        @contextlib.contextmanager
        def guard():order.append('model_done');yield {'model_completed_t_ns':1}
        service=VisualService(validate_vision(camera.VISION_KEY),stop,lambda *a,**kw:None,capture_guard=guard)
        hub=SimpleNamespace(vision=service,gate=SimpleNamespace(speaking_enabled=False),muted=False,log=lambda *a,**kw:None)
        provider=DoubaoNative(hub,'fixture','voice',None,None,stop);provider._send=lambda _:True
        self.addCleanup(service.close)
        def capture(*args):order.append('new_frame');return image_info()
        def understand(pixels,*args,**kwargs):self.assertEqual(pixels,camera.PNG);order.append('vision');return '三轮车。'
        with patch('ai_vision.capture_image',side_effect=capture),patch('ai_vision.understand_png',side_effect=understand):
            provider.inspect_scene('前面是什么？')
            with provider.tool_lock:threads=list(provider.tool_threads)
            for thread in threads:thread.join(2)
        self.assertEqual(order,['model_done','new_frame','vision'])

    def test_photo_question_stays_attached_to_the_input_that_requested_it(self):
        c=Conversation();count=0
        def event(kind,**fields):
            nonlocal count;count+=1
            return c.record({'kind':kind,'id':count,'at':'2026-10-24T16:00:00',**fields})
        first=event('transcript',text='看看前面',final=True,item_id='u1')['messages'][0]['id']
        event('vision_state',phase='waiting_motion',request_id='a'*32,question='前面是什么？')
        event('transcript',text='还有呢',final=True,item_id='u2')
        capture=event('vision_state',phase='capturing',request_id='a'*32,question='前面是什么？')
        self.assertEqual(capture['messages'][0]['parent_id'],first)

    def test_remote_internal_barrier_uses_existing_control_reply_and_no_robot_command(self):
        robot=base.FakeRobot();replies=[];received=threading.Event()
        def request(payload,**kwargs):replies.append(payload);received.set();return {'accepted':True}
        hub=SimpleNamespace(gate=robot.gate,log=lambda *a,**kw:None)
        remote=RemoteAI(hub,SimpleNamespace(request=request),threading.Event())
        remote._event({'kind':'action_request','name':'wait_capture_model','arguments':{},'request_id':'a'*32})
        self.assertTrue(received.wait(1))
        self.assertEqual(replies[0]['kind'],'ai_control')
        self.assertEqual(replies[0]['message']['result']['status'],'model_idle')
        self.assertFalse(robot.calls)


if __name__=='__main__':unittest.main()

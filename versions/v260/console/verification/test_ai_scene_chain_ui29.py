"""Head intent cleanup and explicit motion-to-fresh-scene continuation.

These exercise program ordering with fake robot/camera/cloud data, not the
live model's ability to select a tool or the robot's measured head position.
"""
import json
import threading
import time
import unittest
from unittest.mock import patch

from ai_action_gate import ActionDenied
from ai_doubao import DoubaoNative
from ai_zero import ZeroHub
from verification.test_ai_v200 import FakeRobot
from verification import test_ai_vision_ui13 as camera


class StandHeadTests(unittest.TestCase):
    def setUp(self):
        self.robot=FakeRobot();self.gate=self.robot.gate
        self.gate.set_skills(self.robot.skills)

    def test_seated_look_up_is_cleared_on_all_axes_before_rise(self):
        self.gate.execute('sit_down')
        self.gate.execute('head_pose',{'neck_pitch':.3,'head_pitch':-1.,'head_yaw':.4,'head_roll':.1})
        self.robot.calls.clear()
        result=self.gate.execute('stand_up')
        self.assertEqual(self.robot.calls,[('robot.head',{k:0. for k in self.gate.HEAD_KEYS}),
                                           ('robot.do',{'skill':'sit_toggle'})])
        self.assertEqual(result['status'],'completed')
        self.assertTrue(result['head_neutral_intent_sent'])
        self.assertGreater(result['model_completed_t_ns'],result['model_started_t_ns'])

    def test_already_standing_restores_head_without_toggling_to_sit(self):
        result=self.gate.execute('stand_up')
        self.assertEqual(result['status'],'already_target')
        self.assertEqual(self.robot.calls,[('robot.head',{k:0. for k in self.gate.HEAD_KEYS})])
        self.assertFalse(self.robot.sitting)

    def test_rejected_head_reset_does_not_start_rise(self):
        self.robot.sitting=True
        self.gate.rpc=lambda method,args:{'accepted':False}
        with self.assertRaises(ActionDenied):self.gate.execute('stand_up')
        self.assertFalse(self.robot.calls)
        self.assertTrue(self.robot.sitting)

    def test_missing_posture_or_readiness_never_sends_reset_or_rise(self):
        source=self.robot.state
        for change in ({'sitting':None},{'fresh':False},{'webpad_active':True}):
            with self.subTest(change=change):
                self.gate.state=lambda:{**source(),**change}
                with self.assertRaises(ActionDenied):self.gate.execute('stand_up')
        self.assertFalse(self.robot.calls)


class SceneChainTests(unittest.TestCase):
    def fixture(self,enabled=True):
        self.robot=FakeRobot();self.robot.gate.set_skills(self.robot.skills)
        self.events=[];self.order=[];self.sent=[];self.before_action=None
        self.hub=ZeroHub({'api_key':'fixture','tools':self.robot.gate.tool_definitions(),
                          'vision':{'api_key':camera.VISION_KEY,'enabled':enabled}},threading.Event())
        self.addCleanup(self.hub.vision.close)
        def robot_log(kind,**fields):
            if kind=='model_progress' and fields.get('phase')=='completed':self.order.append('model_completed')
        self.robot.gate.log=robot_log
        def log(kind,**fields):
            self.events.append({'kind':kind,**fields})
            if kind!='action_request':return
            name=fields['name']
            if self.before_action:self.before_action(name)
            try:
                if name=='wait_capture_model':
                    result=self.robot.gate.wait_capture_model();self.order.append('model_idle')
                elif name=='read_distance':result={'available':False,'reason':'fixture'}
                else:result=self.robot.gate.execute(name,fields['arguments'])
            except ActionDenied as exc:result={'accepted':False,'reason':str(exc)}
            self.hub.gate.feedback(fields['request_id'],result)
        self.hub.log=log;self.hub.vision.log=log
        self.provider=DoubaoNative(self.hub,'fixture','fixture-voice',None,None,self.hub.stop)
        self.hub.provider=self.provider
        self.provider._send=lambda payload:self.sent.append(payload) or True
        self.args={'skill':'roulade','question':'现在前方主要是什么物体？'}

    def capture(self,*args):
        self.order.append('fresh_frame')
        return camera.PNG,{'captured_at_ms':round(time.time()*1000),'captured_t_ns':time.monotonic_ns(),
                           'read_ms':1,'image_ms':0,'capture_ms':1,'capture_backend':'fixture'}

    def understand(self,pixels,*args,**kwargs):
        self.assertEqual(pixels,camera.PNG);self.order.append('vision')
        return '本次画面是蓝色儿童三轮车。'



    def test_plain_skill_does_not_implicitly_trigger_a_camera(self):
        self.fixture()
        with patch('ai_vision.capture_image') as capture:
            result=self.hub.gate.execute('perform_skill',{'skill':'roulade'})
        self.assertEqual(result['status'],'completed');capture.assert_not_called()








if __name__=='__main__':unittest.main()

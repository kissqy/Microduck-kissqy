"""Offline behavior checks for named expressions, measured ranges, photos and TOF."""
import copy
import json
import math
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from ai_action_gate import ActionDenied
from ai_conversation import Conversation
from ai_runtime import AIHub
from ai_tof import distance_snapshot
from ai_vision import VisualService, validate_vision
from verification.test_ai_v200 import FakeRobot
from verification.test_ai_vision_ui13 import PNG


class HeadAndExpressionTests(unittest.TestCase):
    def setUp(self):
        self.robot=FakeRobot();self.gate=self.robot.gate
        self.gate.set_skills(self.robot.skills)

    def test_turn_and_raise_are_not_capped_at_twenty_degrees(self):
        self.gate.execute('head_pose',{'head_yaw':1.4,'head_pitch':-1.0,'neck_pitch':-.8,'head_roll':.4})
        self.assertEqual(self.robot.calls[-1],('robot.head',{
            'neck_pitch':-.8,'head_pitch':-1.,'head_yaw':1.4,'head_roll':.4}))
        tool=next(row for row in self.gate.tool_definitions() if row['name']=='head_pose')
        spans=tool['parameters']['properties']
        self.assertEqual(spans['head_yaw']['maximum'],2.5)
        self.assertAlmostEqual(spans['head_roll']['maximum'],math.radians(25))
        self.assertAlmostEqual(spans['neck_pitch']['maximum'],math.radians(60))
        self.assertIn('正数向鸭子自身左侧',spans['head_yaw']['description'])

    def test_saved_amplitude_and_each_axis_range_are_both_enforced(self):
        original=self.gate.state
        self.gate.state=lambda:{**original(),'head_rad':.5}
        self.assertEqual(self.gate.head_ranges()['head_yaw'],(-.5,.5))
        with self.assertRaises(ActionDenied):self.gate.execute('head_pose',{'head_yaw':.6})
        with self.assertRaises(ActionDenied):self.gate.execute('head_pose',{'head_roll':.5})
        self.assertFalse(self.robot.calls)
        self.gate.execute('head_pose',{'head_yaw':-.5})
        self.assertEqual(self.robot.calls[-1][1]['head_yaw'],-.5)

    def test_no_invented_head_range_when_native_metadata_is_missing(self):
        report=copy.deepcopy(self.robot.skills);report.pop('head_limits')
        self.gate.set_skills(report)
        self.assertNotIn('head_pose',[row['name'] for row in self.gate.tool_definitions()])
        with self.assertRaises(ActionDenied):self.gate.execute('head_pose',{'head_yaw':1})
        self.assertFalse(self.robot.calls)

    def expression(self):
        report=copy.deepcopy(self.robot.skills)
        report['expressions']=[{'name':'excited','label':'兴奋','meaning':'惊喜、兴奋',
            'seconds':2.,'skill':'emotion_silent_excited','silent':True}]
        self.gate.set_skills(report)
        self.phase='pending';self.sequence=31;self.complete_on_poll=True
        def rpc(method,args):
            self.robot.calls.append((method,args))
            if args['skill']=='emotion_silent_excited':
                return {'accepted':True,'request_id':self.sequence,'seconds':2.}
            if args['skill']=='emotion_status':
                phase=self.phase
                if self.complete_on_poll:self.phase='completed'
                return {'request_id':self.sequence,'phase':phase}
            return {'accepted':True}
        self.gate.rpc=rpc

    def test_exact_native_expression_waits_for_completion_and_does_not_drive_joints(self):
        self.expression()
        result=self.gate.execute('express_emotion',{'emotion':'excited'})
        self.assertEqual(result['status'],'completed')
        self.assertEqual(result['request_id'],31)
        self.assertEqual(self.robot.calls[0],('robot.do',{'skill':'emotion_silent_excited'}))
        self.assertTrue(all(method=='robot.do' for method,_ in self.robot.calls))
        tools=self.gate.tool_definitions()
        self.assertNotIn('excited',self.gate.skills)
        self.assertEqual(next(t for t in tools if t['name']=='express_emotion')['parameters']['properties']['emotion']['enum'],['excited'])

    def test_manual_takeover_cancels_only_the_requested_generation(self):
        self.expression();self.complete_on_poll=False
        def sleep(seconds):
            self.robot.clock.sleep(seconds);self.robot.webpad=True
        self.gate.sleep=sleep
        with self.assertRaisesRegex(ActionDenied,'网页手柄'):
            self.gate.execute('express_emotion',{'emotion':'excited'})
        self.assertIn(('robot.do',{'skill':'emotion_cancel_31'}),self.robot.calls)
        self.assertFalse(any(method in ('robot.enable','robot.init') for method,_ in self.robot.calls))

    def test_busy_native_refusal_is_never_reported_as_completed(self):
        self.expression()
        self.gate.rpc=lambda *_:{'accepted':False,'reason':'其他动作未结束'}
        with self.assertRaisesRegex(ActionDenied,'其他动作未结束'):
            self.gate.execute('express_emotion',{'emotion':'excited'})


class SessionRefreshTests(unittest.TestCase):
    def test_refresh_keeps_native_audio_and_current_function_ranges(self):
        from ai_doubao import DoubaoNative, MODEL
        from ai_persona import DEFAULT_PERSONA
        robot=FakeRobot();robot.gate.set_skills(robot.skills);robot.gate.speaking_enabled=True
        hub=SimpleNamespace(gate=robot.gate,persona=DEFAULT_PERSONA)
        provider=DoubaoNative(hub,'fixture-key','fixture-voice',None,None,threading.Event())
        initial=provider._session('create')['session']
        update=provider._session('update')
        self.assertEqual(update['type'],'session.update')
        self.assertEqual(update['session']['model'],MODEL)
        self.assertEqual(update['session']['audio'],initial['audio'])
        self.assertEqual(update['session']['tools'],initial['tools'])
        self.assertIn('最多20字',update['session']['instructions'])


class ToFTests(unittest.TestCase):
    def frame(self):
        return {'channels':{'tof':{'status':'live','age_ms':20}},'tof':{
            'seq':8,'t_ns':1_020_000_000,'rows':8,'cols':8,
            'distance_mm':[800]*64,'status':[5]*64}}

    def test_real_grid_in_metres_and_same_zero_clock_are_returned(self):
        data=self.frame();data['tof']['distance_mm'][27]=400
        data['tof']['distance_mm'][28]=600
        result=distance_snapshot(data,1_000_000_000)
        self.assertTrue(result['available'])
        self.assertAlmostEqual(result['center_m'],.7)
        self.assertEqual(result['nearest_m'],.4)
        self.assertEqual(result['capture_delta_ms'],20.)
        self.assertEqual(len(result['grid_m']),8)
        self.assertIn('不一定属于',result['note'])
        self.assertNotIn('object_distance',result)

    def test_stale_invalid_unsynchronised_and_missing_frames_are_not_distances(self):
        variants=[]
        for state in ('stale','error','waiting'):
            data=self.frame();data['channels']['tof']['status']=state;variants.append(data)
        data=self.frame();data['channels']['tof']['age_ms']=1001;variants.append(data)
        data=self.frame();data['tof']['t_ns']=0;variants.append(data)
        data=self.frame();data['tof']['t_ns']=5_000_000_000;variants.append(data)
        data=self.frame();data['tof']['status']=[255]*64;variants.append(data)
        data=self.frame();data['tof']['distance_mm']=[-1]*64;variants.append(data)
        for data in variants:
            with self.subTest(data=data):self.assertFalse(distance_snapshot(data,1_000_000_000)['available'])

    def test_status_five_and_nine_only_and_no_fallback_from_center_to_background(self):
        data=self.frame();data['tof']['status']=[4]*64
        data['tof']['status'][0]=9
        result=distance_snapshot(data)
        self.assertTrue(result['available']);self.assertEqual(result['valid_zones'],1)
        self.assertIsNone(result['center_m']);self.assertEqual(result['center_valid_zones'],0)

    def test_visual_model_and_voice_tool_receive_the_same_tof_context(self):
        distance=distance_snapshot(self.frame(),1_000_000_000)
        events=[]
        service=VisualService(validate_vision('fixture-vision-key'),threading.Event(),
            lambda kind,**fields:events.append({'kind':kind,**fields}),distance=lambda _:distance)
        try:
            with patch('ai_vision.capture_png',return_value=PNG),patch('ai_vision.understand_png',return_value='一个杯子。') as cloud:
                result=service.inspect({'question':'我手上是什么？'})
                self.assertTrue(service.wait_preview())
            self.assertEqual(cloud.call_args.kwargs['distance'],distance)
            self.assertEqual(result['distance'],distance)
            self.assertEqual(cloud.call_args.args[0],PNG)
        finally:service.close()


class ConversationPhotoTests(unittest.TestCase):
    def test_late_preview_updates_its_own_question_after_a_new_capture(self):
        conversation=Conversation();conversation.begin();counter=0
        def event(kind,**fields):
            nonlocal counter
            counter+=1
            return conversation.record({'id':counter,'kind':kind,'at':'2026-10-24T14:20:00',**fields})
        event('transcript',item_id='q1',text='我手上是什么？',final=True)
        event('vision_state',phase='capturing',request_id='a'*32,question='手上物品是什么？',source='voice')
        event('transcript',item_id='q2',text='那这个呢？',final=True)
        event('vision_state',phase='capturing',request_id='b'*32,question='这个是什么？',source='voice')
        event('vision_result',capture_id='a'*32,question='手上物品是什么？',observation='杯子。')
        event('vision_preview',capture_id='a'*32,width=2,height=1)
        event('vision_result',capture_id='b'*32,question='这个是什么？',observation='玩具。')
        event('vision_preview',capture_id='b'*32,width=2,height=1)
        messages=conversation.snapshot()['messages']
        photos=[m for m in messages if m['type']=='vision']
        self.assertEqual(len(photos),2)
        self.assertEqual([m['parent_id'] for m in photos],[1,3])
        self.assertEqual([m['text'] for m in photos],['杯子。','玩具。'])
        self.assertTrue(all(m['image_available'] for m in photos))
        self.assertNotIn('base64',json.dumps(messages))

    def test_later_capture_retains_previous_bytes_without_replacing_current_preview(self):
        hub=AIHub(SimpleNamespace(peek=lambda:{}),connection=SimpleNamespace(active=False))
        meta=lambda value:{'capture_id':value*32,'width':2,'height':1,'captured_at_ms':1}
        try:
            hub.log('vision_state',phase='capturing',request_id='a'*32,question='一个？')
            self.assertTrue(hub.update_vision_frame(meta('a'),PNG))
            hub.log('vision_state',phase='capturing',request_id='b'*32,question='两个？')
            self.assertFalse(hub.update_vision_frame(meta('a'),PNG))
            self.assertIsNone(hub.vision_frame)
            self.assertTrue(hub.update_vision_frame(meta('b'),PNG))
            self.assertEqual(hub.get_vision_frame('a'*32),PNG)
            self.assertEqual(hub.get_vision_frame('b'*32),PNG)
            self.assertEqual(hub.vision_frame[0],'b'*32)
            for index in range(25):hub.update_vision_frame({**meta('c'),'capture_id':format(index,'032x')},PNG)
            self.assertEqual(len(hub.vision_frames),24)
            self.assertIsNone(hub.get_vision_frame('a'*32))
        finally:hub.close()


if __name__=='__main__':unittest.main()

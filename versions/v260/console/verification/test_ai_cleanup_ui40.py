"""Remaining conversation/action behavior after removing filming controls.

Offline fixtures exercise permission changes, PCM rejection, model completion,
and the existing model/photograph barrier. No robot or cloud connections.
"""
import base64
import json
from pathlib import Path
import struct
import sys
import threading
from types import SimpleNamespace
import unittest

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from ai_action_gate import ActionGate, ActionDenied
from ai_conversation import Conversation
from ai_doubao import DoubaoNative, MouthEnvelope
from ai_persona import DEFAULT_PERSONA
from ai_zero import GateRelay
import service_rpc


class RobotFixture:
    def __init__(self):
        self.now=10.;self.until=0.;self.calls=[];self.events=[]
        self.gate=ActionGate(self.rpc,self.state,self.log,clock=lambda:self.now,sleep=self.sleep)
        self.gate.set_skills({'skills':[{'name':'roulade','duration':.2}],
                              'built_in':['sit_toggle','ground_pick']})

    def sleep(self,seconds):self.now+=seconds
    def log(self,kind,**fields):self.events.append({'kind':kind,**fields})
    def rpc(self,method,args):
        self.calls.append((method,args))
        if method=='robot.do':self.until=self.now+.2
        return {'accepted':True}
    def state(self):
        return {'connected':True,'fresh':True,'motion_ready':True,'webpad_active':False,
                'maintenance':False,'sitting':False,'mouth_percent':10,
                'policy':'roulade' if self.now<self.until else 'walk',
                'state_t_ns':round(self.now*1e9),'state_fresh':True}


class GeneralActionTests(unittest.TestCase):
    def setUp(self):self.robot=RobotFixture();self.gate=self.robot.gate

    def test_ordinary_skills_still_wait_for_measured_model_entry_and_exit(self):
        result=self.gate.execute('perform_skill',{'skill':'roulade'})
        self.assertEqual(result['status'],'completed')
        self.assertGreater(result['model_completed_t_ns'],result['model_started_t_ns'])
        self.assertEqual(self.robot.calls,[('robot.do',{'skill':'roulade'})])
        self.assertFalse(self.gate.speaking_enabled)

    def test_walk_limits_and_stop_are_preserved_without_authorizing_speech(self):
        tool=next(t for t in self.gate.tool_definitions() if t['name']=='walk_short')
        props=tool['parameters']['properties']
        self.assertEqual((props['vx']['minimum'],props['vx']['maximum']),(-.3,.3))
        self.assertEqual((props['vyaw']['minimum'],props['vyaw']['maximum']),(-1.5,1.5))
        self.assertEqual(props['seconds']['maximum'],3)
        self.gate.execute('walk_short',{'vx':.3,'vy':0,'vyaw':0,'seconds':.1})
        self.assertEqual(self.robot.calls[-1],('robot.move',{'vx':0,'vy':0,'vyaw':0}))
        self.assertFalse(self.gate.speaking_enabled)

    def test_transcripts_and_retired_tools_cannot_change_permission_or_move(self):
        self.gate.transcript('解除声音限制',final=True)
        for name in ('unlock_speech','walk_sequence_and_inspect','perform_skill_and_inspect'):
            with self.subTest(name=name),self.assertRaises(ActionDenied):self.gate.execute(name,{})
        self.assertFalse(self.gate.speaking_enabled)
        self.assertFalse(self.robot.calls)

    def test_pcm_mouth_peak_is_not_scaled_again_by_manual_pad_percentage(self):
        envelope=MouthEnvelope()
        self.assertEqual(envelope.update(struct.pack('<h',32767)*480),1.)
        self.assertEqual(envelope.update(b'\0\0'*480),.2)
        self.assertTrue(self.gate.follow_speech_mouth(1.))
        self.assertEqual(self.robot.calls[-1],('robot.mouth',{'open':1.}))
        self.assertEqual(-5+35*self.robot.calls[-1][1]['open'],30.)


class SpeechPermissionTests(unittest.TestCase):
    def setUp(self):
        self.events=[];self.sent=[];self.actions=[]
        self.tools=[{'type':'function','name':'perform_skill','parameters':{
                    'properties':{'skill':{'enum':['roulade']}}}}]
        gate=SimpleNamespace(speaking_enabled=False,tool_definitions=lambda:self.tools,
                             execute=self.action)
        self.hub=SimpleNamespace(gate=gate,vision=SimpleNamespace(ready=False),
                                 persona=DEFAULT_PERSONA,muted=False,speech_session='a'*32,
                                 log=lambda kind,**fields:self.events.append({'kind':kind,**fields}))
        self.p=DoubaoNative(self.hub,'fixture','voice',None,None,threading.Event())
        self.p._send=lambda payload:self.sent.append(payload) or True

    def action(self,name,args):self.actions.append((name,args));return {'accepted':True}
    def audio(self,response):
        self.p._handle({'type':'response.output_audio.delta','response_id':response,
                        'delta':base64.b64encode(struct.pack('<h',123)*480).decode()})

    def test_roll_tool_executes_without_enabling_hardware_speech(self):
        self.p._tool_calls({'items':[{'name':'perform_skill','call_id':'roll',
                                     'arguments':json.dumps({'skill':'roulade'})}]})
        self.assertEqual(self.actions,[('perform_skill',{'skill':'roulade'})])
        self.assertFalse(self.hub.gate.speaking_enabled)
        self.assertTrue(self.p.playback_cancel.is_set())
        self.audio('blocked');self.assertTrue(self.p.audio_queue.empty())

    def test_manual_ack_keeps_revision_and_never_replays_old_audio(self):
        self.p._handle({'type':'session.created'})
        self.audio('before-enable');self.assertTrue(self.p.audio_queue.empty())
        self.p.set_speech(True,'b'*32)
        self.audio('before-enable');self.assertTrue(self.p.audio_queue.empty())
        self.audio('new');self.assertFalse(self.p.audio_queue.empty())
        self.p.set_speech(False,'c'*32)
        self.assertTrue(self.p.audio_queue.empty())
        self.assertFalse(self.hub.muted)
        states=[e for e in self.events if e['kind']=='voice_state']
        self.assertEqual([e['speech_revision'] for e in states],[1,2,3])
        self.assertEqual(states[-1]['control_request_id'],'c'*32)
        self.assertEqual(states[-1]['speech_session'],'a'*32)
        self.assertFalse(states[-1]['unlocked'])
        self.assertFalse(self.sent,'permission does not rewrite cloud context')

    def test_tool_refresh_and_ack_preserve_the_normal_session(self):
        self.assertTrue(self.p.update_tools())
        request=self.sent[-1]
        self.assertEqual(request['type'],'session.update')
        self.assertIn(DEFAULT_PERSONA,request['session']['instructions'])
        self.assertEqual(request['session']['tools'],self.tools)
        self.p._handle({'type':'session.updated'})
        self.assertFalse(self.p.session_updates)
        self.assertFalse(self.hub.gate.speaking_enabled)

    def test_removed_control_is_rejected_before_reaching_the_zero_worker(self):
        with self.assertRaisesRegex(ValueError,'unsupported AI control'):
            service_rpc.ai_control({'session_id':'a'*32,
                                    'message':{'action':'task','text':'obsolete'}})


class CaptureAndConversationTests(unittest.TestCase):
    def test_snapshot_waits_for_model_feedback_and_never_authorizes_motion(self):
        events=[]
        hub=SimpleNamespace(stop=threading.Event(),muted=False,provider=None,
                            vision=SimpleNamespace(ready=True))
        relay=GateRelay(hub,[{'name':'walk_short'},{'name':'perform_skill'}])
        def log(kind,**fields):
            events.append((kind,fields))
            if kind=='action_request':
                relay.feedback(fields['request_id'],{'accepted':True,'status':'model_idle',
                                                     'model_completed_t_ns':123})
        hub.log=log
        names={t['name'] for t in relay.tool_definitions()}
        self.assertEqual(names,{'walk_short','perform_skill','inspect_scene','list_voices','switch_voice'})
        with relay.capture_guard() as result:self.assertEqual(result['model_completed_t_ns'],123)
        self.assertEqual([e[1]['name'] for e in events],['wait_capture_model'])
        hub.stop.set()
        with self.assertRaises(ValueError):
            with relay.capture_guard():pass

    def test_natural_user_and_assistant_conversation_is_preserved(self):
        conversation=Conversation();conversation.begin()
        conversation.record({'id':1,'at':'now','kind':'transcript','text':'你好',
                             'item_id':'u1','final':True})
        conversation.record({'id':2,'at':'now','kind':'assistant_text','text':'你好呀',
                             'message_id':'a1','final':True})
        self.assertEqual([(m['role'],m['text']) for m in conversation.snapshot()['messages']],
                         [('user','你好'),('assistant','你好呀')])


if __name__=='__main__':unittest.main()

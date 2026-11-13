"""HAT playback permission is independent of model instructions and action tools."""
import base64
import json
import struct
import threading
import unittest

from ai_doubao import DoubaoNative
from ai_zero import ZeroHub
from verification.test_ai_hat import Hub


class ModelContextAndHatPermissionTests(unittest.TestCase):
    def provider(self, hub):
        p=DoubaoNative(hub,'fixture','fixture-voice',None,None,threading.Event())
        self.sent=[]
        p._send=lambda payload:self.sent.append(payload) or True
        return p

    def test_native_model_payload_and_tools_do_not_depend_on_either_audio_flag(self):
        hub=Hub();p=self.provider(hub)
        reference=None
        for enabled in (False,True):
            for muted in (False,True):
                hub.gate.speaking_enabled=enabled
                hub.muted=muted
                payload=p._session()
                if reference is None:reference=payload
                self.assertEqual(payload,reference)
                self.assertNotIn('unlock_speech',[tool['name'] for tool in payload['session']['tools']])
        self.assertFalse(hub.robot.calls,'building normal context must never execute an action')

    def test_zero_relay_keeps_the_same_model_tools_while_hat_permission_changes(self):
        normal=Hub()
        hub=ZeroHub({'api_key':'fixture','tools':normal.gate.tool_definitions(),
                     'voice_enabled':False},threading.Event())
        self.addCleanup(hub.vision.close)
        p=self.provider(hub);hub.provider=p
        before=p._session()
        for enabled in (True,False,True):
            p.set_speech(enabled,('a' if enabled else 'b')*32)
            self.assertEqual(p._session(),before)
            self.assertEqual(hub.gate.speaking_enabled,enabled)
            self.assertEqual(p.playback_cancel.is_set(),not enabled)
        self.assertFalse(self.sent,'checkbox changes must not edit the model session')

    def test_final_asr_does_not_open_hat_or_dispatch_motion(self):
        hub=Hub();events=hub.events
        p=self.provider(hub);before=p._session()
        p._handle({'type':'conversation.item.input_audio_transcription.delta',
                   'item_id':'human','delta':'你不解释解释吗'})
        self.assertFalse(hub.gate.speaking_enabled)
        p._handle({'type':'response.output_text.done','item_id':'model',
                   'text':'你不解释解释吗'})
        self.assertFalse(hub.gate.speaking_enabled)
        p._handle({'type':'conversation.item.input_audio_transcription.completed',
                   'item_id':'human','transcript':'你不解释解释吗？'})
        self.assertFalse(hub.gate.speaking_enabled)
        self.assertTrue(p.playback_cancel.is_set())
        self.assertEqual(p._session(),before)
        self.assertFalse(self.sent)
        self.assertFalse(any(e['kind']=='voice_state' for e in events))
        self.assertFalse(hub.robot.calls,'the playback phrase does not script or force an action')

    def test_closed_hat_still_receives_model_text_and_local_replay_audio(self):
        hub=Hub();p=self.provider(hub)
        p._handle({'type':'response.output_text.done','response_id':'answer','text':'听懂了。'})
        pcm=struct.pack('<h',123)*6000
        p._handle({'type':'response.output_audio.delta','response_id':'answer',
                   'delta':base64.b64encode(pcm).decode()})
        p._handle({'type':'response.output_audio.done','response_id':'answer'})
        self.assertTrue(p.audio_queue.empty(),'closed HAT must never receive this model audio')
        text=next(e for e in hub.events if e['kind']=='assistant_text')
        self.assertEqual(text['text'],'听懂了。')
        replay=[e for e in hub.events if e['kind']=='assistant_audio_replay' and e['phase']=='chunk']
        self.assertEqual(b''.join(base64.b64decode(e['data']) for e in replay),pcm)

    def test_model_roll_tool_keeps_hat_closed_without_model_update(self):
        hub=Hub();p=self.provider(hub)
        before=p._session()
        text='你不自己解释一下吗？'
        p._handle({'type':'conversation.item.input_audio_transcription.delta','item_id':'human','delta':text})
        p._handle({'type':'response.output_text.done','item_id':'assistant','text':text})
        self.assertFalse(hub.gate.speaking_enabled)
        p._handle({'type':'conversation.item.input_audio_transcription.completed','item_id':'human','transcript':text})
        self.assertFalse(hub.gate.speaking_enabled);self.assertFalse(hub.robot.calls)
        old_rpc=hub.gate.rpc
        def rpc(method,args):
            if method=='robot.do':self.assertFalse(hub.gate.speaking_enabled,'motion must not authorize speech')
            return old_rpc(method,args)
        hub.gate.rpc=rpc
        p._tool_calls({'items':[{'name':'perform_skill','call_id':'chosen-roll','arguments':'{"skill":"roulade"}'}]})
        self.assertFalse(hub.gate.speaking_enabled);self.assertTrue(p.playback_cancel.is_set())
        self.assertEqual(p._session(),before)
        self.assertEqual([e['type'] for e in self.sent],['conversation.item.create'])
        self.assertEqual(hub.robot.calls,[('robot.do',{'skill':'roulade'})])
        self.assertFalse(any(e['kind']=='voice_state' for e in hub.events))

    def test_other_or_invalid_tools_do_not_open_hat(self):
        hub=Hub();p=self.provider(hub)
        for name,args in (('perform_skill',{'skill':'uninstalled'}),
                          ('perform_skill',{'skill':'roulade','home':True}),
                          ('head_pose',{'skill':'roulade'})):
            with self.subTest(name=name,args=args):
                p._tool_calls({'items':[{'name':name,'call_id':'invalid',
                                         'arguments':json.dumps(args)}]})
                self.assertFalse(hub.gate.speaking_enabled)
                result=json.loads(self.sent[-1]['items'][0]['content'][0]['text'])
                self.assertFalse(result['accepted'])
        self.assertFalse(hub.robot.calls)

    def test_existing_walk_pure_yaw_keeps_translation_zero_and_stops(self):
        hub=Hub()
        tool=next(t for t in hub.gate.tool_definitions() if t['name']=='walk_short')
        bounds=tool['parameters']['properties']['vyaw']
        self.assertEqual((bounds['minimum'],bounds['maximum']),(-1.5,1.5))
        self.assertEqual(tool['parameters']['properties']['seconds']['maximum'],3)
        before=hub.robot.clock()
        result=hub.gate.execute('walk_short',{'vx':0,'vy':0,'vyaw':-1.5,'seconds':3})
        self.assertEqual(result['status'],'stop_intent_sent')
        self.assertEqual(result['seconds'],3)
        self.assertAlmostEqual(hub.robot.clock()-before,3)
        self.assertGreater(len(hub.robot.calls),1)
        for method,args in hub.robot.calls[:-1]:
            self.assertEqual((method,args),('robot.move',{'vx':0.,'vy':0.,'vyaw':-1.5}))
        self.assertEqual(hub.robot.calls[-1],('robot.move',{'vx':0,'vy':0,'vyaw':0}))
        for yaw in (-1.5001,1.5001):
            with self.subTest(yaw=yaw),self.assertRaises(ValueError):
                hub.gate.execute('walk_short',{'vx':0,'vy':0,'vyaw':yaw,'seconds':1})
        with self.assertRaises(ValueError):
            hub.gate.execute('walk_short',{'vx':0,'vy':0,'vyaw':-1.5,'seconds':3.01})

    def test_model_tool_nod_executes_without_local_transcript_trigger_or_speech_permission(self):
        hub=Hub();p=self.provider(hub)
        report={**hub.robot.skills,'expressions':[{'name':'yes','label':'点头','meaning':'肯定',
                    'seconds':1.,'skill':'emotion_yes','silent_skill':'emotion_silent_yes','silent':False}]}
        hub.gate.set_skills(report)
        calls=[]
        def rpc(method,args):
            calls.append((method,args))
            return ({'request_id':18,'phase':'completed'} if args.get('skill')=='emotion_status'
                    else {'accepted':True,'request_id':18})
        hub.gate.rpc=rpc
        p._handle({'type':'conversation.item.input_audio_transcription.completed',
                   'item_id':'human','transcript':'你能听懂我讲话吗？'})
        self.assertFalse(calls,'ASR alone must not pick or execute a gesture')
        p._tool_calls({'items':[{'name':'express_emotion','call_id':'model-selected-nod',
                                'arguments':json.dumps({'emotion':'yes'})}]})
        self.assertEqual(calls[0],('robot.do',{'skill':'emotion_yes'}))
        result=json.loads(self.sent[-1]['items'][0]['content'][0]['text'])
        self.assertEqual(result['status'],'completed')
        self.assertFalse(result['silent'],'official expression WAV is separate from model PCM')
        self.assertFalse(hub.gate.speaking_enabled)


if __name__=='__main__':unittest.main()

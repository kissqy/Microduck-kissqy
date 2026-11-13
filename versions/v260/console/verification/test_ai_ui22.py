"""Original expression audio, PCM ownership and manual unload behavior regressions."""
import base64
import copy
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from ai_action_gate import ActionDenied
from ai_doubao import DoubaoNative
from ai_zero import ZeroHub
from verification import test_ai_ui21 as ui21


class OfficialSoundGateTests(unittest.TestCase):
    def fixture(self):
        old=ui21.HeadAndExpressionTests();old.setUp();old.expression()
        row=copy.deepcopy(old.gate.expressions['excited'])
        row.update(skill='emotion_excited',silent=False,silent_skill='emotion_silent_excited')
        report=copy.deepcopy(old.robot.skills);report['expressions']=[row]
        old.gate.set_skills(report)
        def rpc(method,args):
            old.robot.calls.append((method,args))
            if args['skill'].startswith('emotion_cancel_'):return {'accepted':True}
            if args['skill']=='emotion_status':return {'request_id':31,'phase':'completed'}
            return {'accepted':True,'request_id':31}
        old.gate.rpc=rpc
        return old

    def test_default_expression_requests_official_sound_not_the_silent_alias(self):
        f=self.fixture();result=f.gate.execute('express_emotion',{'emotion':'excited'})
        self.assertEqual(f.robot.calls[0],('robot.do',{'skill':'emotion_excited'}))
        self.assertFalse(result['silent']);self.assertEqual(result['status'],'completed')

    def test_muted_expression_uses_the_explicit_silent_route(self):
        f=self.fixture();state=f.gate.state;f.gate.state=lambda:{**state(),'audio_muted':True}
        result=f.gate.execute('express_emotion',{'emotion':'excited'})
        self.assertEqual(f.robot.calls[0],('robot.do',{'skill':'emotion_silent_excited'}))
        self.assertTrue(result['silent'])

    def test_muting_an_active_clip_cancels_that_generation(self):
        f=self.fixture();state=f.gate.state;muted=[False]
        f.gate.state=lambda:{**state(),'audio_muted':muted[0]}
        def rpc(method,args):
            f.robot.calls.append((method,args))
            if args['skill']=='emotion_status':muted[0]=True;return {'request_id':31,'phase':'playing'}
            return {'accepted':True,'request_id':31}
        f.gate.rpc=rpc
        with self.assertRaisesRegex(ActionDenied,'已静音'):
            f.gate.execute('express_emotion',{'emotion':'excited'})
        self.assertIn(('robot.do',{'skill':'emotion_cancel_31'}),f.robot.calls)


class ExpressionPCMTests(unittest.TestCase):
    def test_yield_closes_pcm_before_native_request_blocks_echo_then_resumes_voice(self):
        stop=threading.Event();hub=ZeroHub({'api_key':'fixture','tools':[],'voice_enabled':True},stop)
        provider=DoubaoNative(hub,'fixture','voice',None,None,stop);hub.provider=provider
        opened=threading.Event();played=threading.Event();after=threading.Event();events=[];sent=[]
        provider._send=sent.append
        class Speaker:
            def __init__(self,*_):pass
            def __enter__(self):return self
            def __exit__(self,*_):self.close()
            def close(self):opened.clear()
            def finish(self):self.close();return True
            def write(self,pcm):
                opened.set();played.set()
                if pcm==b'after':after.set()
                return True
        def log(kind,**fields):
            events.append((kind,fields))
            if kind=='action_request':
                self.assertFalse(opened.is_set(),'release HAT PCM before native WAV starts')
                self.assertTrue(provider.expression_audio_ready.is_set())
                self.assertTrue(provider._input_state()[1],'official WAV must gate echo too')
                provider._handle({'type':'response.output_audio.delta','delta':base64.b64encode(b'\0'*640).decode()})
                self.assertTrue(provider.audio_queue.empty(),'no competing PCM during the native clip')
                hub.gate.feedback(fields['request_id'],{'accepted':True,'status':'completed'})
        hub.log=log
        worker=threading.Thread(target=provider._speaker,daemon=True)
        with patch('ai_doubao.NativeSpeaker',Speaker):
            worker.start()
            try:
                provider.audio_queue.put(b'before');self.assertTrue(played.wait(1))
                result=hub.gate.execute('express_emotion',{'emotion':'excited'})
                self.assertEqual(result['status'],'completed')
                self.assertFalse(provider.expression_audio.is_set())
                self.assertTrue(provider._input_state()[1],'retain the existing short echo tail')
                provider.audio_queue.put(b'after');self.assertTrue(after.wait(1))
            finally:stop.set();worker.join(1);hub.vision.close()
        self.assertFalse(worker.is_alive())

    def test_failed_audio_handoff_never_requests_robot_motion(self):
        stop=threading.Event();hub=ZeroHub({'api_key':'fixture','tools':[],'voice_enabled':True},stop)
        calls=[];hub.log=lambda kind,**fields:calls.append(kind)
        hub.provider=SimpleNamespace(begin_expression_audio=lambda:False)
        try:
            result=hub.gate.execute('express_emotion',{'emotion':'excited'})
            self.assertFalse(result['accepted']);self.assertNotIn('action_request',calls)
        finally:hub.vision.close()


if __name__=='__main__':unittest.main()

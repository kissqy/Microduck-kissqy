"""Startup and the live speech checkbox use Zero-confirmed playback permission."""
import base64
import hashlib
import http.client
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile
from http.server import ThreadingHTTPServer

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from ai_action_gate import ActionDenied
from ai_doubao import DoubaoNative
from ai_preferences import AIPreferences
from ai_remote import RemoteAI,worker_bundle
from ai_runtime import AIHub
from ai_zero import ZeroHub
from console import handler_for
from service_channel import ServiceChannel
from telemetry import Store
import service_rpc


class ZeroSpeechTests(unittest.TestCase):
    def setUp(self):
        self.stop=threading.Event();self.events=[]
        self.hub=ZeroHub({'api_key':'fixture','tools':[],'voice_enabled':False,
                         'speech_session':'a'*32},self.stop)
        self.hub.log=lambda kind,**fields:self.events.append({'kind':kind,**fields})
        self.p=DoubaoNative(self.hub,'fixture','voice',None,None,self.stop)
        self.p._send=lambda _:True;self.hub.provider=self.p;self.addCleanup(self.hub.vision.close)

    def audio(self,response):
        self.p._handle({'type':'response.output_audio.delta','response_id':response,
                        'delta':base64.b64encode(struct.pack('<h',123)*480).decode()})

    def test_startup_blocks_and_reports_actual_zero_state(self):
        self.p._handle({'type':'session.created'})
        self.assertFalse(self.hub.gate.speaking_enabled)
        self.assertTrue(self.p.playback_cancel.is_set());self.assertFalse(self.hub.muted)
        self.audio('startup');self.assertTrue(self.p.audio_queue.empty())
        state=next(e for e in self.events if e['kind']=='voice_state')
        self.assertFalse(state['unlocked']);self.assertEqual(state['source'],'startup')
        self.assertEqual(state['speech_session'],'a'*32);self.assertEqual(state['speech_revision'],1)


    def test_manual_off_closes_only_provider_pcm_and_old_tail_never_replays(self):
        self.p.set_speech(True,'b'*32);self.audio('old');self.assertFalse(self.p.audio_queue.empty())
        self.p.set_speech(False,'c'*32)
        self.assertTrue(self.p.audio_queue.empty());self.assertTrue(self.p.playback_cancel.is_set())
        self.assertFalse(self.hub.muted,'official WAV must remain audible')
        self.p.set_speech(True,'d'*32);self.audio('old');self.assertTrue(self.p.audio_queue.empty())
        self.audio('new');self.assertFalse(self.p.audio_queue.empty())
        revisions=[e['speech_revision'] for e in self.events if e['kind']=='voice_state']
        self.assertEqual(revisions,[1,2,3])

    def test_model_roll_request_cannot_enable_speech(self):
        self.p._handle({'type':'conversation.item.input_audio_transcription.completed',
                        'item_id':'real-input','transcript':'那你展示一下'})
        self.assertFalse(self.hub.gate.speaking_enabled)
        self.hub.gate.tools=[{'name':'perform_skill','parameters':{'properties':{'skill':{'enum':['roulade']}}}}]
        with patch.object(self.hub.gate,'execute',return_value={'accepted':False,'reason':'fixture not ready'}):
            self.p._tool_calls({'items':[{'name':'perform_skill','call_id':'roll-without-task','arguments':'{"skill":"roulade"}'}]})
        self.assertFalse(self.hub.gate.speaking_enabled);self.assertTrue(self.p.playback_cancel.is_set())
        self.assertFalse(any(e['kind']=='voice_state' for e in self.events))

    def test_manual_playback_permission_does_not_update_cloud_context(self):
        sent=[]
        self.p._send=lambda message:sent.append(message) or False
        self.p.set_speech(True,'b'*32)
        self.p.set_speech(False,'c'*32)
        self.assertFalse(self.hub.gate.speaking_enabled);self.assertTrue(self.p.playback_cancel.is_set())
        ack=next(e for e in self.events if e.get('control_request_id')=='c'*32)
        self.assertFalse(ack['unlocked']);self.assertFalse(self.stop.is_set())
        self.assertFalse(sent,'the playback checkbox is independent of cloud context updates')

    def test_speech_off_does_not_hide_the_configured_vision_tool(self):
        self.hub.vision=SimpleNamespace(ready=True)
        session=self.p._session()['session']
        self.assertIn('inspect_scene',[t['name'] for t in session['tools']])
        self.assertFalse(self.hub.gate.speaking_enabled)


class SpeechHubTests(unittest.TestCase):
    def setUp(self):
        self.hub=AIHub(Store('service'));self.addCleanup(self.hub.close);self.calls=[]
        self.hub.provider_ready=True;self.hub.speech_session='a'*32
        self.hub.provider=SimpleNamespace(set_speech=lambda *args:self.calls.append(args),close=lambda:None)

    def ack(self,enabled,revision,**extra):
        self.hub.log('voice_state',source='speech_control',speech_session='a'*32,speech_revision=revision,
                     unlocked=enabled,**extra)

    def test_checkbox_waits_for_zero_ack_and_ignores_old_state_or_old_session(self):
        status=self.hub.set_speech({'enabled':True});request_id=status['speech']['request_id']
        self.assertFalse(status['voice_unlocked']);self.assertEqual(status['speech']['phase'],'pending')
        self.assertEqual(self.calls,[(True,request_id)])
        self.ack(True,2,control_request_id=request_id)
        self.assertTrue(self.hub.status()['voice_unlocked']);self.assertEqual(self.hub.status()['speech']['phase'],'applied')
        self.ack(False,1)
        self.hub.log('voice_state',source='speech_control',speech_session='z'*32,speech_revision=99,unlocked=False)
        self.assertTrue(self.hub.status()['voice_unlocked'])

    def test_timeout_failure_and_duplicate_click_do_not_claim_a_successful_change(self):
        self.hub.set_speech({'enabled':True})
        with self.assertRaises(ActionDenied):self.hub.set_speech({'enabled':False})
        self.hub.speech_sent_at-=9
        self.assertEqual(self.hub.status()['speech']['phase'],'error');self.assertFalse(self.hub.gate.speaking_enabled)
        self.hub.provider.set_speech=lambda *args:(_ for _ in ()).throw(OSError('fixture disconnected'))
        with self.assertRaises(ActionDenied):self.hub.set_speech({'enabled':True})
        self.assertFalse(self.hub.gate.speaking_enabled)
        for args in ({'enabled':1},{'enabled':False,'muted':False},{},None):
            with self.assertRaises(ActionDenied):self.hub.set_speech(args)

    def test_current_manual_ack_applies_and_stopped_session_rejects_late_ack(self):
        pending=self.hub.set_speech({'enabled':True})
        self.ack(True,3,control_request_id=pending['speech']['request_id'])
        self.assertTrue(self.hub.status()['voice_unlocked']);self.assertTrue(self.hub.status()['speech']['enabled'])
        self.hub.stop();self.ack(True,4);self.assertFalse(self.hub.gate.speaking_enabled)

    def test_authenticated_http_and_service_control_validate_the_new_switch(self):
        cfg={'bind':'127.0.0.1','mode':'service','service_enabled':False,'control_token':'fixture'}
        server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(self.hub.store,cfg,ai_hub=self.hub))
        server.daemon_threads=True;worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        try:
            for token,wanted in [('wrong',403),('fixture',200)]:
                client=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=2)
                client.request('POST','/api/ai/speech',json.dumps({'enabled':True}),headers={
                    'Content-Type':'application/json','X-Control-Token':token,
                    'Origin':'http://127.0.0.1:'+str(server.server_port)})
                response=client.getresponse();body=response.read();self.assertEqual(response.status,wanted,body)
                if wanted==200:self.assertFalse(json.loads(body)['voice_unlocked'])
                client.close()
            for enabled,request_id in [(1,'a'*32),(True,'bad')]:
                with self.assertRaises(ValueError):service_rpc.ai_control({'message':{'action':'speech','enabled':enabled,'request_id':request_id}})
        finally:server.shutdown();server.server_close();worker.join(1)


FAKE_CLOUD='''from _ai_vendor.websocket._speech_fixture import DoubaoNative as Real
import base64,struct,uuid
class DoubaoNative(Real):
 def _send(self,payload):
  if payload.get('type')=='session.update':self._handle({'type':'session.updated'})
  return True
 def run(self):
  self._session()
  self._handle({'type':'session.created'})
  self.stop_event.wait(20)
 def inspect_scene(self,question):
  if question=='fixture_roll_request':
   self._handle({'type':'response.function_call_arguments.done','items':[{'name':'perform_skill','call_id':uuid.uuid4().hex,'arguments':'{"skill":"roulade"}'}]})
   return
  rid=uuid.uuid4().hex
  self._handle({'type':'response.output_text.done','response_id':rid,'item_id':rid,'text':'已经帮你摇过头啦。'})
  self._handle({'type':'response.output_audio.delta','response_id':rid,'delta':base64.b64encode(struct.pack('<h',123)*480).decode()})
  self._handle({'type':'response.output_audio.done','response_id':rid})
  self._handle({'type':'response.done','response_id':rid})
  self.hub.log('fixture_probe',enabled=self.hub.gate.speaking_enabled,pcm_queued=any(isinstance(x,bytes) and x for x in self.audio_queue.queue))
'''


class RealPipeStartupTests(unittest.TestCase):
    def bundle(self):
        encoded,_=worker_bundle();out=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(encoded))) as original,zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
            for name in original.namelist():z.writestr(name,FAKE_CLOUD if name=='ai_doubao.py' else original.read(name))
            z.writestr('_ai_vendor/websocket/_speech_fixture.py',original.read('ai_doubao.py'))
        raw=out.getvalue();return base64.b64encode(raw).decode(),hashlib.sha256(raw).hexdigest()

    def until(self,predicate):
        deadline=time.monotonic()+4
        while not predicate() and time.monotonic()<deadline:threading.Event().wait(.01)
        self.assertTrue(predicate())

    def test_pc_start_to_real_zero_worker_manual_switch_and_no_model_roll_unlock(self):
        channel=ServiceChannel(None,'/tmp/fixture-unused.sock');self.addCleanup(channel.close)
        with tempfile.TemporaryDirectory() as directory:
            hub=AIHub(Store('service'),preferences=AIPreferences(Path(directory)/'voice.json'));self.addCleanup(hub.close)
            hub.api_key='fixture-native-key';hub.connection=SimpleNamespace(active=True)
            hub.service_controller=SimpleNamespace(transport=SimpleNamespace(channel=channel))
            hub.load_skills=lambda:hub.gate.set_skills({'skills':[{'name':'flamingo'},{'name':'roulade'}],'built_in':[]})
            with patch('ai_remote.worker_bundle',return_value=self.bundle()):
                hub.start();self.until(lambda:hub.provider_ready and hub.speech_revision>=1)
                self.assertFalse(hub.status()['voice_unlocked'])
                def probe(number):
                    hub.provider.inspect_scene('probe')
                    self.until(lambda:len([e for e in hub.events if e['kind']=='fixture_probe'])>=number)
                    return [e for e in hub.events if e['kind']=='fixture_probe'][-1]
                self.assertFalse(probe(1)['pcm_queued'])
                hub.set_speech({'enabled':True});self.until(lambda:hub.gate.speaking_enabled and hub.speech['phase']=='applied')
                self.assertTrue(probe(2)['pcm_queued'])
                hub.set_speech({'enabled':False});self.until(lambda:not hub.gate.speaking_enabled and hub.speech['phase']=='applied')
                self.assertFalse(probe(3)['pcm_queued'])
                self.assertFalse(hub.gate.speaking_enabled)
                hub.provider.inspect_scene('fixture_roll_request')
                self.until(lambda:any(e['kind']=='tool_feedback' and e.get('name')=='perform_skill' for e in hub.events))
                self.assertFalse(hub.gate.speaking_enabled)
                self.assertFalse(hub.status()['speech']['enabled']);self.assertFalse(hub.muted)
                self.assertNotIn('assistant_audio_replay',hub.trace_file.read_text())
                hub.stop();self.until(lambda:not hub.worker.is_alive())


if __name__=='__main__':unittest.main()

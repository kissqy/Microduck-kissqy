"""Native dialogue regressions, updated in UI10 to use provider turn detection."""
import base64
import json
import math
from pathlib import Path
import queue
import struct
import sys
import threading
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from ai_doubao import DoubaoNative
from ai_pcm import PcmDecoder,detect_pcm_dtype
from ai_runtime import AIHub
from telemetry import Store
from verification.test_ai_hat import Hub
from _ai_vendor import websocket
from ai_persona import DEFAULT_PERSONA


class TurnTests(unittest.TestCase):
    def setUp(self):
        self.hub=Hub();self.hub.gate.speaking_enabled=True
        self.p=DoubaoNative(self.hub,'fixture','fixture',None,None,threading.Event())
        self.now=[0.0];self.p.clock=lambda:self.now[0]
        self.sent=[];self.p._send=self.sent.append

    def delta(self,text):
        self.p._handle({'type':'conversation.item.input_audio_transcription.delta','item_id':'u1','delta':text})

    def test_persona_has_no_speech_ban_and_keeps_m6_audio_contract(self):
        s=self.p._session()
        self.assertIn(DEFAULT_PERSONA,s['session']['instructions'])
        self.assertNotIn('严禁',s['session']['instructions'])
        self.assertNotIn('unlock_speech',[t['name'] for t in s['session']['tools']])
        self.assertEqual(s['session']['audio'],{'input':{'format':{'type':'pcm','rate':16000}},
            'output':{'format':{'type':'pcm','rate':24000},'voice':'fixture','speed':0,'loudness':0}})
        self.assertEqual(s['extension'],{'asr':{},'tts':{},'dialog':{}})

    def test_interim_asr_never_forces_commit_after_a_local_pause(self):
        for text in ('你','你好','你好你好','你好。你好。'):
            self.delta(text);self.now[0]+=.1
        for elapsed in (1.7,1.81,10,60,120):
            self.now[0]=elapsed;self.p._poll_input()
        self.assertFalse(self.sent,'ASR pauses must never send a local forced commit')
        self.assertFalse(any(e['kind']=='transcript' and e['final'] for e in self.hub.events),'do not invent final ASR')
        self.p._handle({'type':'conversation.item.input_audio_transcription.completed','item_id':'u1','transcript':'你好。'})
        self.assertTrue(self.hub.events[-1]['final'])

    def test_manual_debug_commit_still_sends_once_and_warns_without_retries(self):
        self.delta('你好')
        self.now[0]=2
        self.assertTrue(self.p.commit_input())
        self.assertFalse(self.p.commit_input())
        self.assertEqual([x['type'] for x in self.sent],['input_audio_buffer.commit'])
        self.assertEqual(next(e for e in self.hub.events if e['kind']=='input_turn_commit')['reason'],'manual')
        for _ in range(3):self.now[0]+=10;self.p._poll_input()
        self.assertEqual(len(self.sent),1,'never loop or retry a manual commit')
        self.assertEqual(len([e for e in self.hub.events if e['kind']=='input_turn_wait']),1)

    def test_continuing_speech_and_server_final_do_not_force_early_commit(self):
        self.delta('我想');self.now[0]=1.3;self.delta('我想让你点头')
        self.now[0]=2;self.p._poll_input();self.assertFalse(self.sent)
        self.p._handle({'type':'conversation.item.input_audio_transcription.completed','item_id':'u1','transcript':'我想让你点头。'})
        self.now[0]=4;self.p._poll_input();self.assertFalse(self.sent)

    def test_mute_blocks_audio_while_doubao_text_still_arrives(self):
        self.p.set_muted(True)
        self.p._handle({'type':'response.output_text.done','item_id':'a1','text':'你好，我在。'})
        self.p._handle({'type':'response.output_audio.delta','delta':base64.b64encode(struct.pack('<h',123)*480).decode()})
        self.assertTrue(self.p.audio_queue.empty())
        text=next(e for e in self.hub.events if e['kind']=='assistant_text')
        self.assertEqual(text['text'],'你好，我在。');self.assertFalse(text['blocked'])
        self.p.set_muted(False)
        pcm=struct.pack('<h',123)*480
        self.p._handle({'type':'response.output_audio.delta','delta':base64.b64encode(pcm).decode()})
        self.assertEqual(self.p.audio_queue.get_nowait(),pcm)
        self.assertFalse(self.p.stop_event.is_set())


class AudioTests(unittest.TestCase):
    def test_m6_float32_and_int16_survive_arbitrary_network_boundaries(self):
        floats=[.25*math.sin(i/10) for i in range(2048)]
        raw=struct.pack('<2048f',*floats)
        self.assertEqual(detect_pcm_dtype(raw),'float32')
        decoder=PcmDecoder();out=[]
        for start in range(0,len(raw),307):out.append(decoder.feed(raw[start:start+307]))
        out.append(decoder.feed(b'',final=True))
        values=struct.unpack('<2048h',b''.join(out))
        self.assertTrue(all(abs(actual-round(expected*32767))<=1 for actual,expected in zip(values,floats)))
        pcm=struct.pack('<2048h',*[round(v*30000) for v in floats]);d=PcmDecoder()
        self.assertEqual(d.feed(pcm),pcm);self.assertEqual(d.dtype,'int16')


class ConversationTests(unittest.TestCase):
    def test_history_keeps_multiple_turns_and_replaces_only_the_live_bubble(self):
        hub=AIHub(Store('service'))
        try:
            hub.log('transcript',item_id='u1',text='你',final=False)
            hub.log('transcript',item_id='u1',text='你好',final=False)
            hub.log('transcript',item_id='u1',text='你好。',final=True)
            hub.log('assistant_text',message_id='a1',text='你好。',final=True,blocked=False)
            hub.log('transcript',item_id='u2',text='点个头',final=True)
            hub.log('tool_feedback',name='head_expression',call_id='call2',arguments={'gesture':'nod'},result={'accepted':True,'status':'head_intents_sent'})
            snapshot=hub.status()['conversation']
            self.assertEqual([m['role'] for m in snapshot['messages']],['user','assistant','user','assistant'])
            self.assertEqual(snapshot['messages'][0]['text'],'你好。')
            self.assertEqual(snapshot['messages'][-1]['type'],'action')
            self.assertEqual(snapshot['messages'][-1]['arguments'],{'gesture':'nod'})
            self.assertEqual(snapshot['phase'],'ready')
            hub.log('provider_stop',message='ended')
            self.assertEqual(len(hub.status()['conversation']['messages']),4)
            self.assertEqual(hub.status()['conversation']['phase'],'stopped')
            self.assertIn('conversation_update',hub.events[-1])
            self.assertNotIn('conversation_update',hub.trace_file.read_text(),'download retains original compact provider events')
        finally:hub.close()

    def test_start_defaults_to_speech_disabled_and_global_audio_does_not_authorize_it(self):
        hub=AIHub(Store('service'));hub.api_key='fixture-key-1234'
        hub.load_skills=lambda:hub.gate.set_skills({'skills':[{'name':'flamingo'}],'built_in':[]})
        class Provider:
            def __init__(self,owner,channel,stop):self.stop=stop;self.mutes=[]
            def run(self):self.stop.wait(2)
            def close(self):self.stop.set()
            def set_muted(self,value):self.mutes.append(value)
        hub.service_controller=type('Service',(),{'transport':type('Transport',(),{'channel':None})()})()
        hub._get_ai_channel=lambda:None
        try:
            with patch('ai_remote.RemoteAI',Provider):
                status=hub.start()
                self.assertFalse(status['voice_unlocked']);self.assertFalse(status['muted'])
                provider=hub.provider
                status=hub.set_audio({'muted':True})
                self.assertFalse(status['voice_unlocked']);self.assertTrue(status['muted'])
                self.assertEqual(provider.mutes,[True])
        finally:hub.close()


class FullProviderTests(unittest.TestCase):
    def test_session_ack_then_continuous_input_provider_final_tool_text_and_audio(self):
        hub=Hub();hub.gate.speaking_enabled=True;hub.muted=False
        stop=threading.Event();provider=DoubaoNative(hub,'fixture','fixture',None,None,stop)
        played=[];finished=threading.Event();sent=[]
        pcm=struct.pack('<h',321)*480
        class Socket:
            def __init__(self):self.events=queue.Queue();self.pending=False;self.audio_packets=0
            def settimeout(self,_):pass
            def send(self,raw):
                event=json.loads(raw);sent.append(event);kind=event['type']
                if kind=='session.create':
                    for e in ({'type':'session.created','session':{'id':'fixture'}},
                              {'type':'conversation.item.input_audio_transcription.started'},
                              {'type':'conversation.item.input_audio_transcription.delta','item_id':'u1','delta':'点个头'}):self.events.put(e)
                elif kind=='input_audio_buffer.append':
                    self.audio_packets+=1
                    if self.audio_packets<3 or self.pending:return
                    self.pending=True
                    self.events.put({'type':'conversation.item.input_audio_transcription.completed','item_id':'u1','transcript':'点个头。'})
                    self.events.put({'type':'response.function_call_arguments.done','items':[{'name':'head_expression','arguments':'{"gesture":"nod"}','call_id':'call1'}]})
                elif kind=='conversation.item.create':
                    for e in ({'type':'response.output_text.delta','item_id':'a1','delta':'好的。'},
                              {'type':'response.output_text.done','item_id':'a1','text':'好的。'},
                              {'type':'response.output_audio.delta','delta':base64.b64encode(pcm).decode()},
                              {'type':'response.output_audio.done'},{'type':'response.done'}):self.events.put(e)
            def recv(self):
                if finished.is_set():stop.set();return '{}'
                try:return json.dumps(self.events.get(timeout=.01))
                except queue.Empty:raise websocket.WebSocketTimeoutException()
            def close(self,**_):pass
        class Mic:
            def __init__(self,*_):pass
            def __enter__(self):
                if not hub.provider_ready:raise AssertionError('capture opened before session.created')
                return self
            def __exit__(self,*_):pass
            def read(self):stop.wait(.005);return b'\0'*640 if not stop.is_set() else b''
        class Speaker:
            def __init__(self,*_):pass
            def __enter__(self):return self
            def __exit__(self,*_):pass
            def write(self,data):played.append(data)
            def finish(self):
                if played:finished.set()
            def close(self):pass
        socket=Socket();timer=threading.Timer(3,stop.set);timer.start()
        try:
            with patch.object(websocket,'create_connection',return_value=socket),patch('ai_doubao.NativeMicrophone',Mic),patch('ai_doubao.NativeSpeaker',Speaker):provider.run()
        finally:timer.cancel();provider.close()
        self.assertTrue(finished.is_set(),'must reach HAT playback, not stop at the ASR stage')
        self.assertEqual(b''.join(played),pcm)
        self.assertEqual(sum(e['type']=='input_audio_buffer.commit' for e in sent),0)
        self.assertTrue(any(e['type']=='input_audio_buffer.append' for e in sent))
        self.assertTrue(any(e['kind']=='assistant_text' and e['text']=='好的。' for e in hub.events))
        self.assertTrue(any(e['kind']=='tool_feedback' and e['result']['accepted'] for e in hub.events))
        self.assertTrue(any(method=='robot.head' for method,_ in hub.robot.calls))


if __name__=='__main__':unittest.main()

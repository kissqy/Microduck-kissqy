"""Returned voice is live-only transit, keyed to its real assistant text."""
import base64
import http.client
import json
import math
from pathlib import Path
import struct
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from ai_conversation import Conversation
from ai_doubao import DoubaoNative
from ai_remote import RemoteAI
from ai_runtime import AIHub
from console import handler_for
from telemetry import Store
from verification.test_ai_hat import Hub


class ProviderReplyAudioTests(unittest.TestCase):
    def fixture(self):
        hub=Hub();p=DoubaoNative(hub,'fixture','voice',None,None,threading.Event())
        p._send=lambda _:True
        return hub,p

    def test_blocked_hat_voice_still_relays_exact_returned_audio_with_the_text_id(self):
        hub,p=self.fixture();p.set_speech(False,'a'*32)
        p._handle({'type':'response.output_text.done','item_id':'text-first','text':'我听懂了。'})
        pcm=struct.pack('<h',234)*19000
        for start in range(0,len(pcm),1170):
            p._handle({'type':'response.output_audio.delta','response_id':'voice-response',
                        'delta':base64.b64encode(pcm[start:start+1170]).decode()})
        p._handle({'type':'response.output_audio.done','response_id':'voice-response'})
        text=next(e for e in hub.events if e['kind']=='assistant_text')
        audio=[e for e in hub.events if e['kind']=='assistant_audio_replay']
        chunks=[e for e in audio if e['phase']=='chunk']
        self.assertTrue(text['blocked']);self.assertTrue(p.audio_queue.empty())
        self.assertEqual({e['audio_id'] for e in audio},{text['audio_id']})
        self.assertEqual(b''.join(base64.b64decode(e['data']) for e in chunks),pcm)
        self.assertEqual([e['sequence'] for e in chunks],list(range(len(chunks))))
        self.assertEqual(audio[-1]['phase'],'end');self.assertEqual(audio[-1]['sequence'],len(chunks))
        self.assertTrue(all(len(e['data'])<=16000 for e in chunks));self.assertFalse(p.replay_states)
        c=Conversation();text.update(id=1,at='2026-10-24T12:00:00')
        message=c.record(text)['messages'][0];self.assertEqual(message['audio_id'],audio[0]['audio_id'])

    def test_audio_before_text_is_still_one_reply_and_next_turn_gets_another_id(self):
        hub,p=self.fixture();pcm=base64.b64encode(struct.pack('<h',234)*480).decode()
        p._handle({'type':'response.output_audio.delta','response_id':'r1','delta':pcm})
        p._handle({'type':'response.output_audio.done','response_id':'r1'})
        p._handle({'type':'response.output_audio_transcript.done','item_id':'text-r1','transcript':'第一句'})
        p._handle({'type':'response.done','response_id':'r1'})
        p._handle({'type':'response.output_text.done','response_id':'r2','item_id':'text-r2','text':'第二句'})
        p._handle({'type':'response.output_audio.delta','response_id':'r2','delta':pcm})
        p._handle({'type':'response.output_audio.done','response_id':'r2'})
        texts=[e for e in hub.events if e['kind']=='assistant_text']
        clips=[e for e in hub.events if e['kind']=='assistant_audio_replay' and e['phase']=='end']
        self.assertEqual([e['audio_id'] for e in texts],[e['audio_id'] for e in clips])
        self.assertNotEqual(clips[0]['audio_id'],clips[1]['audio_id'])

    def test_native_float_pcm_is_converted_once_for_browser_replay_without_tts(self):
        hub,p=self.fixture();values=[.25*math.sin(i/10) for i in range(2048)]
        raw=struct.pack('<2048f',*values)
        for start in range(0,len(raw),307):
            p._handle({'type':'response.output_audio.delta','response_id':'float-r1',
                       'delta':base64.b64encode(raw[start:start+307]).decode()})
        p._handle({'type':'response.output_audio.done','response_id':'float-r1'})
        data=b''.join(base64.b64decode(e['data']) for e in hub.events
                     if e['kind']=='assistant_audio_replay' and e['phase']=='chunk')
        transmitted=struct.unpack('<2048f',raw)
        self.assertEqual(data,struct.pack('<2048h',*[round(v*32767) for v in transmitted]))

    def test_unidentified_pcm_cannot_accumulate_an_unbounded_zero_buffer(self):
        hub,p=self.fixture()
        p._handle({'type':'response.output_audio.delta','response_id':'silent',
                   'delta':base64.b64encode(bytes(262144+640)).decode()})
        self.assertFalse(p.replay_states)
        self.assertEqual([e for e in hub.events if e['kind']=='assistant_audio_replay'][-1]['phase'],'error')


class LiveOnlyRelayTests(unittest.TestCase):
    def setUp(self):
        self.hub=AIHub(Store('service'));self.addCleanup(self.hub.close)
        self.event={'kind':'assistant_audio_replay','audio_id':'a'*32,'sequence':0,'phase':'chunk',
                    'rate':24000,'data':base64.b64encode(b'\x01\x02'*100).decode()}

    def test_audio_has_no_history_no_trace_and_disappears_with_each_stream(self):
        before=self.hub.trace_file.read_bytes();count=self.hub.counter
        self.hub.relay_audio(self.event)
        first=self.hub.stream(0);self.assertEqual(next(first)['kind'],'ai_ready')
        self.assertFalse(next(iter(self.hub.audio_listeners.values())),'opening a page cannot retrieve old audio')
        second=self.hub.stream(0);next(second)
        self.hub.relay_audio(self.event)
        self.assertEqual(next(first)['data'],self.event['data']);self.assertEqual(next(second)['data'],self.event['data'])
        self.assertEqual(self.hub.counter,count);self.assertEqual(self.hub.trace_file.read_bytes(),before)
        self.assertNotIn(self.event['data'],json.dumps(self.hub.status()))
        self.assertNotIn(self.event['data'],json.dumps(self.hub.tail()))
        first.close();self.assertEqual(len(self.hub.audio_listeners),1)
        second.close();self.assertFalse(self.hub.audio_listeners)
        self.hub.log('assistant_audio_replay',**{k:v for k,v in self.event.items() if k!='kind'})
        self.assertEqual(self.hub.trace_file.read_bytes(),before)

    def test_transit_is_bounded_and_invalid_payloads_are_not_queued(self):
        stream=self.hub.stream(0);next(stream);self.addCleanup(stream.close)
        for seq in range(100):self.hub.relay_audio({**self.event,'sequence':seq})
        live=next(iter(self.hub.audio_listeners.values()));self.assertEqual(len(live),24)
        self.assertEqual(live[0]['sequence'],76,'a slow page must detect a gap and discard the incomplete clip')
        for invalid in ({'audio_id':'../path'},{'sequence':True},{'data':'x'*16385},{'phase':'other'}):
            self.assertFalse(self.hub.relay_audio({**self.event,**invalid}))
        self.assertEqual(len(live),24)

    def test_remote_audio_bypasses_all_ordinary_log_paths(self):
        stream=self.hub.stream(0);next(stream);self.addCleanup(stream.close)
        remote=RemoteAI(self.hub,None,threading.Event());before=self.hub.trace_file.read_bytes()
        remote._event(self.event)
        self.assertEqual(next(stream)['audio_id'],'a'*32)
        self.assertEqual(self.hub.trace_file.read_bytes(),before)

    def test_real_sse_uses_noncacheable_audio_events_without_a_replay_cursor(self):
        cfg={'bind':'127.0.0.1','mode':'service','service_enabled':False,'control_token':'fixture'}
        server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(self.hub.store,cfg,ai_hub=self.hub))
        server.daemon_threads=True;worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        client=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=2)
        try:
            client.request('GET','/api/ai/stream?after=0');response=client.getresponse()
            self.assertEqual(response.status,200);self.assertEqual(response.getheader('Cache-Control'),'no-store')
            self.assertEqual(response.readline().strip(),b'id: 1');response.readline();response.readline()
            self.hub.relay_audio(self.event)
            self.assertEqual(response.readline().strip(),b'event: audio')
            payload=json.loads(response.readline().decode().removeprefix('data: '))
            self.assertNotIn('id',payload);self.assertEqual(payload['data'],self.event['data'])
        finally:
            client.close();self.hub.closed=True
            with self.hub.cv:self.hub.cv.notify_all()
            server.shutdown();server.server_close();worker.join(1)


if __name__=='__main__':unittest.main()

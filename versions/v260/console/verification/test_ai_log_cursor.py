"""Regression using the actual UUID from the user's UI4 dialogue log."""
import http.client
import json
from pathlib import Path
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from ai_runtime import AIHub
from console import handler_for
from telemetry import Store

UUID='46fdcf91-4a05-47b3-84ea-20042d82cdbb'


class LogCursorTests(unittest.TestCase):
    def setUp(self):self.hub=AIHub(Store('service'))
    def tearDown(self):self.hub.close()
    def test_provider_uuid_cannot_replace_log_cursor(self):
        event=self.hub.log('provider_session',event='session.created',id=UUID)
        self.hub.log('asr_started')
        self.assertEqual(event['id'],2);self.assertEqual(event['source_id'],UUID)
        self.assertEqual([e['id'] for e in self.hub.tail(0)['events']],[1,2,3])

    def test_replay_and_resume_continue_after_uuid_event(self):
        stream=self.hub.stream(0);self.assertEqual(next(stream)['id'],1)
        self.hub.log('provider_session',id=UUID,at='untrusted timestamp')
        self.hub.log('asr_started')
        event=next(stream)
        self.assertEqual(event['id'],2);self.assertNotEqual(event['at'],'untrusted timestamp')
        self.assertEqual(event['source_at'],'untrusted timestamp')
        self.assertEqual(next(stream)['id'],3);stream.close()
        resumed=self.hub.stream(2);self.assertEqual(next(resumed)['kind'],'asr_started');resumed.close()

    def test_session_event_has_separate_provider_identifier(self):
        from ai_doubao import DoubaoNative
        provider=DoubaoNative(self.hub,'fixture','fixture',None,None,threading.Event())
        provider._handle({'type':'session.created','session':{'id':UUID}})
        event=self.hub.tail(1)['events'][0]
        self.assertEqual(event['id'],2);self.assertEqual(event['session_id'],UUID)
        self.assertTrue(self.hub.provider_ready)

    def test_real_http_reconnect_recovers_old_uuid_header(self):
        self.hub.log('provider_session',id=UUID);self.hub.log('asr_started')
        config={'bind':'127.0.0.1','mode':'service','service_enabled':False,'control_token':'fixture'}
        server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(self.hub.store,config,ai_hub=self.hub))
        server.daemon_threads=True
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            for header,expected in [(UUID,2),('2',3)]:
                client=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=2)
                try:
                    client.request('GET','/api/ai/stream?after=1',headers={'Last-Event-ID':header})
                    response=client.getresponse();self.assertEqual(response.status,200)
                    self.assertEqual(response.readline().decode().strip(),f'id: {expected}')
                    self.assertEqual(json.loads(response.readline().decode().removeprefix('data: '))['id'],expected)
                finally:client.close()
        finally:
            self.hub.closed=True
            with self.hub.cv:self.hub.cv.notify_all()
            server.shutdown();server.server_close();thread.join(2)

    def test_level_updates_are_live_but_not_written_as_conversation(self):
        before=self.hub.trace_file.read_bytes()
        self.hub.log('mic_level',rms=.1,peak=.2,dbfs=-20,minimum=-.2,maximum=.2)
        self.assertEqual(self.hub.trace_file.read_bytes(),before)
        self.assertEqual(self.hub.status()['mic_level']['dbfs'],-20)
        self.assertEqual(self.hub.tail(1)['events'][0]['kind'],'mic_level')


if __name__=='__main__':unittest.main()

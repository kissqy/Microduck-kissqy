import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from ai_voices import catalog
from ai_preferences import AIPreferences
from ai_runtime import AIHub
from ai_doubao import DoubaoNative
from ai_zero import GateRelay
from telemetry import Store

ROWS=[{'name':'小鸭','id':'voice_a'},{'name':'讲故事','id':'voice_b'}]


class VoiceTests(unittest.TestCase):
    def provider(self):
        events=[]
        hub=SimpleNamespace(voices=ROWS.copy(),voice_id='voice_a',provider_ready=True,
                            speech_session='session-fixture',muted=False,
                            gate=SimpleNamespace(speaking_enabled=False,tool_definitions=lambda:[]),
                            log=lambda kind,**data:events.append({'kind':kind,**data}))
        provider=DoubaoNative(hub,'fixture-key','voice_a',None,None,threading.Event())
        provider._send=Mock(return_value=True)
        self.addCleanup(provider.close)
        return provider,hub,events

    def test_catalog_rejects_duplicates_and_removing_active(self):
        for rows in ([],ROWS+ROWS,[{'name':'小鸭','id':'other'},ROWS[0]]):
            with self.assertRaises(ValueError):catalog(rows)
        with self.assertRaises(ValueError):catalog([ROWS[1]],'voice_a',strict=True)

    def test_legacy_settings_and_voice_catalog_survive_restart_without_key_leaks(self):
        with tempfile.TemporaryDirectory() as folder:
            prefs=AIPreferences(Path(folder)/'voice.json')
            prefs.save('fixture-key-12345','voice_a')
            hub=AIHub(Store('service'),preferences=prefs)
            try:
                self.assertEqual(hub.voices,[{'name':'当前音色','id':'voice_a'}])
                hub.set_voices({'voices':ROWS})
                hub.set_voice({'voice_id':'voice_b'})
                self.assertEqual(prefs.load()['voice_id'],'voice_b')
                self.assertEqual(prefs.load()['voices'],ROWS)
                self.assertNotIn('fixture-key-12345',json.dumps(hub.status()))
            finally:hub.close()

    def test_cloud_ack_commits_voice_after_prior_tool_update_and_preserves_speech_lock(self):
        p,hub,events=self.provider()
        p.update_tools()
        request=p.request_voice('voice_b','a'*32)
        payload=p._send.call_args.args[0]
        self.assertEqual(payload['type'],'session.update')
        self.assertEqual(payload['session']['audio']['output']['voice'],'voice_b')
        self.assertEqual(p.voice_id,'voice_a')
        p._handle({'type':'session.updated'})
        self.assertEqual(p.voice_id,'voice_a')
        p._handle({'type':'session.updated'})
        self.assertEqual(p.voice_id,'voice_b')
        self.assertTrue(request['done'].is_set())
        self.assertEqual(request['result']['status'],'confirmed')
        self.assertFalse(hub.gate.speaking_enabled)
        self.assertTrue(p.playback_cancel.is_set())
        self.assertEqual(events[-2]['phase'],'confirmed')

    def test_unknown_voice_and_concurrent_switch_do_not_send_updates(self):
        p,_,_=self.provider()
        with self.assertRaises(ValueError):p.request_voice('not-added')
        p._send.assert_not_called()
        p.request_voice('voice_b')
        with self.assertRaises(ValueError):p.request_voice('voice_a')
        self.assertEqual(p._send.call_count,1)

    def test_failed_send_leaves_original_voice_and_no_pending_request(self):
        p,_,_=self.provider();p._send.return_value=False
        with self.assertRaises(ValueError):p.request_voice('voice_b')
        self.assertEqual(p.voice_id,'voice_a')
        self.assertIsNone(p.pending_voice)

    def test_timeout_is_not_reported_as_success_and_blocks_another_switch(self):
        p,_,_=self.provider();request=p.request_voice('voice_b')
        request['timer'].cancel();request['timer'].function()
        self.assertFalse(request['result']['accepted'])
        self.assertEqual(p.voice_id,'voice_a')
        with self.assertRaises(ValueError):p.request_voice('voice_a')

    def test_ai_switch_tool_uses_catalog_and_no_motor_lease(self):
        p,hub,_=self.provider();hub.stop=p.stop_event;hub.vision=SimpleNamespace(ready=False)
        relay=GateRelay(hub,[]);hub.gate=relay;hub.provider=p;relay.lease_factory=Mock()
        seen=threading.Event();p._send=Mock(side_effect=lambda _:seen.set() or True)
        result=[];worker=threading.Thread(target=lambda:result.append(relay.execute('switch_voice',{'voice_id':'voice_b'})))
        worker.start();self.assertTrue(seen.wait(1));p._handle({'type':'session.updated'});worker.join(1)
        self.assertFalse(worker.is_alive());self.assertTrue(result[0]['accepted'])
        relay.lease_factory.assert_not_called()
        definition=next(t for t in relay.tool_definitions() if t['name']=='switch_voice')
        self.assertEqual(definition['parameters']['properties']['voice_id']['enum'],['voice_a','voice_b'])

    def test_manual_running_switch_saves_only_after_current_session_confirmation(self):
        with tempfile.TemporaryDirectory() as folder:
            prefs=AIPreferences(Path(folder)/'voice.json');prefs.save('fixture-key-12345','voice_a',voices=ROWS)
            hub=AIHub(Store('service'),preferences=prefs)
            try:
                hub.worker=Mock();hub.worker.is_alive.return_value=True
                hub.provider=Mock();hub.provider_ready=True;hub.speech_session='live'
                hub.set_voice({'voice_id':'voice_b'})
                self.assertEqual(hub.voice_id,'voice_a');self.assertEqual(prefs.load()['voice_id'],'voice_a')
                event={'phase':'confirmed','voice_id':'voice_b','request_id':'a'*32,'voice_session':'old','voice_revision':1}
                hub.on_voice_selection(event);self.assertEqual(hub.voice_id,'voice_a')
                event['voice_session']='live';hub.on_voice_selection(event)
                self.assertEqual(hub.voice_id,'voice_b');self.assertEqual(prefs.load()['voice_id'],'voice_b')
                hub.on_voice_selection({**event,'voice_id':'voice_a','voice_revision':0})
                self.assertEqual(hub.voice_id,'voice_b')
            finally:hub.worker=None;hub.close()


if __name__=='__main__':unittest.main()

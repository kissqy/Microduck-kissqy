"""Local voice settings survive restarts without leaking credentials to the UI."""
import base64
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from ai_preferences import AIPreferences
from ai_runtime import AIHub
from ai_action_gate import ActionDenied
from telemetry import Store
from ai_persona import DEFAULT_PERSONA, LEGACY_STYLE_DEFAULT


class PreferencesTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.path=Path(self.directory.name)/'settings'/'ai-voice.json'
        self.hubs=[]

    def tearDown(self):
        for hub in self.hubs:hub.close()
        self.directory.cleanup()

    def hub(self):
        hub=AIHub(Store('service'),preferences=AIPreferences(self.path))
        self.hubs.append(hub)
        return hub

    def test_restart_restores_key_and_voice_but_status_and_logs_never_return_key(self):
        first=self.hub()
        key='fixture-local-key-987654321'
        status=first.configure({'api_key':key,'voice_id':'fixture_voice_a','persona':'你是一只爱讲冷笑话的小鸭。','muted':False})
        self.assertTrue(status['credentials_present'])
        self.assertTrue(status['configuration_saved'])
        self.assertNotIn(key,json.dumps(status))
        self.assertNotIn(key,first.trace_file.read_text())
        second=self.hub()
        self.assertEqual(second.api_key,key)
        self.assertEqual(second.voice_id,'fixture_voice_a')
        second.configure({'voice_id':'fixture_voice_b'})
        third=self.hub()
        self.assertEqual(third.api_key,key,'an empty browser key field must keep the existing credential')
        self.assertEqual(third.voice_id,'fixture_voice_b')
        self.assertEqual(third.persona,'你是一只爱讲冷笑话的小鸭。')
        third.log('fixture_echo',message='untrusted reply: '+key)
        self.assertNotIn(key,json.dumps(third.tail()))
        self.assertNotIn(key,third.trace_file.read_text())
        if sys.platform!='win32':
            self.assertEqual(stat.S_IMODE(self.path.stat().st_mode),0o600)

    def test_invalid_input_and_failed_atomic_save_keep_last_working_configuration(self):
        hub=self.hub()
        hub.configure({'api_key':'fixture-first-1234','voice_id':'voice_a'})
        before=self.path.read_bytes()
        with self.assertRaises(ActionDenied):
            hub.configure({'api_key':'fixture-new-1234','voice_id':'bad voice','muted':True})
        self.assertEqual(hub.api_key,'fixture-first-1234')
        self.assertFalse(hub.muted)
        self.assertEqual(self.path.read_bytes(),before)
        with patch('ai_preferences.os.replace',side_effect=OSError('fixture denied')):
            with self.assertRaisesRegex(ActionDenied,'无法保存'):
                hub.configure({'api_key':'fixture-new-1234','voice_id':'voice_b','muted':True})
        self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(hub.api_key,'fixture-first-1234')
        self.assertEqual(hub.voice_id,'voice_a')
        self.assertFalse(hub.muted)
        self.assertEqual(list(self.path.parent.glob('*.tmp')),[])

    def test_windows_calls_existing_user_protection_and_never_falls_back_to_plaintext(self):
        key='fixture-windows-key-1234'
        def protect(data,decrypt=False):
            return bytes(x^0xa7 for x in data)
        settings=AIPreferences(self.path)
        with patch('ai_preferences.sys.platform','win32'),patch('sudo_credential._windows_protect',side_effect=protect) as crypt:
            settings.save(key,'voice_a')
            saved=self.path.read_text()
            self.assertNotIn(key,saved)
            self.assertEqual(json.loads(saved)['key_storage'],'windows-dpapi')
            self.assertEqual(settings.load(),{'api_key':key,'voice_id':'voice_a','persona':DEFAULT_PERSONA})
            self.assertEqual(crypt.call_count,2)
            self.assertEqual(crypt.call_args.kwargs,{'decrypt':True})
        before=self.path.read_bytes()
        with patch('ai_preferences.sys.platform','win32'),patch('sudo_credential._windows_protect',side_effect=OSError('fixture failure')):
            with self.assertRaises(OSError):settings.save('fixture-new-key-1234','voice_b')
        self.assertEqual(self.path.read_bytes(),before)

    def test_bad_saved_file_keeps_console_usable_and_can_be_replaced(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text('{broken configuration',encoding='utf-8')
        hub=self.hub()
        status=hub.status()
        self.assertFalse(status['credentials_present'])
        self.assertFalse(status['configuration_saved'])
        self.assertIn('重新填写',status['configuration_error'])
        hub.configure({'api_key':'fixture-recovered-1234','voice_id':'voice_ok'})
        self.assertEqual(hub.status()['configuration_error'],'')
        self.assertEqual(self.hub().api_key,'fixture-recovered-1234')

    def test_older_saved_voice_settings_gain_persona_without_losing_key(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text(json.dumps({'schema':1,'key_storage':'local-user','api_key':'fixture-legacy-key','voice_id':'legacy_voice'}))
        hub=self.hub()
        self.assertEqual(hub.persona,DEFAULT_PERSONA)
        self.assertEqual(hub.api_key,'fixture-legacy-key')
        hub.configure({'persona':'你很安静，回答只用一句话。'})
        restored=self.hub()
        self.assertEqual(restored.persona,'你很安静，回答只用一句话。')
        self.assertEqual(restored.api_key,'fixture-legacy-key')
        self.assertEqual(restored.voice_id,'legacy_voice')
        before=self.path.read_bytes()
        with self.assertRaises(ActionDenied):hub.configure({'persona':' '})
        self.assertEqual(self.path.read_bytes(),before)

    def test_ui11_factory_style_upgrades_to_role_rules_and_reaches_provider(self):
        import threading
        from ai_doubao import DoubaoNative
        self.path.parent.mkdir(parents=True)
        self.path.write_text(json.dumps({'schema':1,'key_storage':'local-user','api_key':'fixture-legacy-key','voice_id':'legacy_voice','persona':LEGACY_STYLE_DEFAULT}))
        hub=self.hub()
        self.assertEqual(hub.status()['persona'],DEFAULT_PERSONA)
        self.assertEqual(hub.api_key,'fixture-legacy-key')
        self.assertEqual(hub.voice_id,'legacy_voice')
        hub.gate.speaking_enabled=True
        provider=DoubaoNative(hub,hub.api_key,hub.voice_id,None,None,threading.Event())
        instructions=provider._session()['session']['instructions']
        self.assertTrue(instructions.startswith(DEFAULT_PERSONA))
        self.assertIn('语音与动作助手',instructions)
        self.assertIn('最多20字',instructions)
        self.assertNotIn('傲娇',instructions)
        hub.configure({})
        self.assertEqual(json.loads(self.path.read_text())['persona'],DEFAULT_PERSONA)


if __name__=='__main__':unittest.main()

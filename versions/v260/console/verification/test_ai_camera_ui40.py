"""Optional continuous camera: guarded release, legacy migration, on-demand vision."""
import json
from pathlib import Path
import struct
import sys
import tempfile
import threading
import tomllib
import unittest
from unittest.mock import Mock, patch
import zlib

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
import ai_camera_setup as camera
import ai_vision as vision
from ai_preferences import AIPreferences, DEFAULT_VOICE
from ai_persona import DEFAULT_PERSONA
from service_control import ServiceTransport


def png():
    def chunk(kind,data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    return (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',2,1,8,2,0,0,0))
            +chunk(b'IDAT',zlib.compress(b'\0'+bytes([20,30,40])*2))+chunk(b'IEND',b''))


class CameraQualityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'robotd.toml';self.active=self.path;self.calls=[]
        self.fail_restart=None

    def command(self,*args):
        self.calls.append(args)
        if args[0]=='show':
            return '{ argv[]=/usr/bin/mediad --config '+str(self.active)+' ; ignore_errors=no ; }'
        if self.fail_restart:
            failure=self.fail_restart;self.fail_restart=None;raise failure
        return ''

    def test_apply_release_retains_independent_other_keys_and_comments(self):
        self.path.write_text('# robot\n[media] # keep\nquality="1080p30" # chosen\nbitrate=2000000\n[control]\nhz=50\n')
        applied=camera.prepare(self.command)
        self.assertTrue(applied['changed']);self.assertEqual(applied['target_fps'],15)
        self.path.write_text(self.path.read_text().replace('bitrate=2000000','bitrate=3000000')+'[custom]\nvalue="new"\n')
        result=camera.restore(applied['restore'],self.command)
        restored=self.path.read_text();parsed=tomllib.loads(restored)
        self.assertTrue(result['restored']);self.assertEqual(parsed['media']['quality'],'1080p30')
        self.assertEqual(parsed['media']['bitrate'],3000000);self.assertEqual(parsed['control'],{'hz':50})
        self.assertEqual(parsed['custom'],{'value':'new'})
        self.assertIn('# robot',restored);self.assertIn('# keep',restored);self.assertIn('# chosen',restored)
        self.assertTrue(all(args[1]=='mediad.service' for args in self.calls))

    def test_absent_quality_and_absent_media_restore_their_original_semantics(self):
        for original in ('[media]\nsource="camera"\n','[control]\nhz=50\n'):
            with self.subTest(original=original):
                self.path.write_text(original);receipt=camera.prepare(self.command)
                self.assertTrue(camera.restore(receipt['restore'],self.command)['restored'])
                self.assertEqual(tomllib.loads(self.path.read_text()),tomllib.loads(original))

    def test_new_config_file_is_removed_only_when_it_has_no_other_data(self):
        receipt=camera.prepare(self.command)
        self.assertTrue(self.path.exists())
        camera.restore(receipt['restore'],self.command)
        self.assertFalse(self.path.exists())
        receipt=camera.prepare(self.command)
        self.path.write_text(self.path.read_text()+'[custom]\nkeep=true\n')
        camera.restore(receipt['restore'],self.command)
        self.assertEqual(tomllib.loads(self.path.read_text()),{'custom':{'keep':True}})

    def test_existing_15fps_has_no_restore_token_or_restart_and_never_guesses_30fps(self):
        original='[media]\nquality="720p15"\n';self.path.write_text(original)
        receipt=camera.prepare(self.command)
        self.assertFalse(receipt['changed']);self.assertIsNone(receipt['restore'])
        self.assertEqual(self.path.read_text(),original);self.assertEqual(len(self.calls),1)

    def test_independent_quality_change_blocks_restore(self):
        self.path.write_text('[media]\nquality="720p30"\n');receipt=camera.prepare(self.command)
        self.path.write_text(self.path.read_text().replace('720p15','360p30'));before=self.path.read_bytes()
        result=camera.restore(receipt['restore'],self.command)
        self.assertFalse(result['restored']);self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(sum(args[0]=='restart' for args in self.calls),1)

    def test_active_config_path_change_blocks_restore(self):
        self.path.write_text('[media]\nquality="720p30"\n');receipt=camera.prepare(self.command)
        self.active=Path(self.tmp.name)/'different.toml'
        result=camera.restore(receipt['restore'],self.command)
        self.assertFalse(result['restored']);self.assertIn('720p15',self.path.read_text())
        self.assertFalse(self.active.exists())

    def test_restore_restart_failure_rolls_back_and_keeps_receipt_retryable(self):
        self.path.write_text('[media]\nquality="720p30"\n');receipt=camera.prepare(self.command)
        self.fail_restart=RuntimeError('fixture restart failed')
        with self.assertRaisesRegex(RuntimeError,'restart failed'):camera.restore(receipt['restore'],self.command)
        self.assertEqual(tomllib.loads(self.path.read_text())['media']['quality'],'720p15')
        self.assertTrue(camera.restore(receipt['restore'],self.command)['restored'])

    def test_malformed_restore_is_rejected_before_service_or_file_access(self):
        for token in (None,{}, {'config_path':'/tmp/other'}):
            with self.subTest(token=token),self.assertRaises(ValueError):camera.restore(token,self.command)
        self.assertEqual(self.calls,[])

    def test_transport_sends_only_guarded_restore_to_the_existing_helper(self):
        transport=object.__new__(ServiceTransport);transport._manage=Mock(return_value={'accepted':True})
        token={'fixture':'private snapshot'}
        self.assertEqual(transport.restore_ai_camera(token),{'accepted':True})
        command=transport._manage.call_args.args[0]
        self.assertEqual(command[:3],['python3','-u','-c'])
        self.assertEqual(json.loads(command[-1]),{'action':'restore','restore':token})
        self.assertFalse(transport._manage.call_args.kwargs['record_output'])


class CameraPreferenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'ai-voice.json';self.prefs=AIPreferences(self.path)

    def legacy(self):
        data={'schema':1,'key_storage':'local-user','api_key':'fixture-voice-key',
              'voice_id':DEFAULT_VOICE,'persona':'我是原来的小鸭。',
              'vision':{'api_key':'fixture-vision-key','model':vision.DEFAULT_VISION_MODEL,'enabled':True}}
        self.path.write_text(json.dumps(data));return data

    def test_legacy_enabled_is_migrated_off_once_without_losing_keys_or_persona(self):
        before=self.legacy();loaded=self.prefs.load();raw=json.loads(self.path.read_text())
        self.assertFalse(loaded['vision']['enabled']);self.assertFalse(raw['vision']['enabled'])
        self.assertEqual(raw['vision']['camera_mode_revision'],1)
        self.assertEqual(loaded['api_key'],before['api_key']);self.assertEqual(loaded['persona'],before['persona'])
        self.assertEqual(raw['vision']['api_key'],before['vision']['api_key'])
        self.prefs.save(loaded['api_key'],loaded['voice_id'],loaded['persona'],vision={**loaded['vision'],'enabled':True})
        self.assertTrue(self.prefs.load()['vision']['enabled'],'new user choice must survive restarting')

    def test_unwritable_legacy_migration_still_returns_credentials_with_camera_off(self):
        self.legacy()
        with patch('ai_preferences.os.replace',side_effect=PermissionError('fixture denied')):
            loaded=self.prefs.load()
        self.assertEqual(loaded['api_key'],'fixture-voice-key');self.assertEqual(loaded['vision']['api_key'],'fixture-vision-key')
        self.assertFalse(loaded['vision']['enabled']);self.assertIn('密钥',loaded['vision_configuration_error'])
        self.assertEqual(list(self.path.parent.glob('*.tmp')),[])

    def test_windows_migration_preserves_ciphertext(self):
        def crypt(data,decrypt=False):return bytes(x^0xa7 for x in data)
        with patch('ai_preferences.sys.platform','win32'),patch('sudo_credential._windows_protect',side_effect=crypt):
            self.prefs.save('fixture-voice-key',DEFAULT_VOICE,vision=vision.validate_vision('fixture-vision-key',enabled=True))
            raw=json.loads(self.path.read_text());raw['vision'].pop('camera_mode_revision');self.path.write_text(json.dumps(raw))
            loaded=self.prefs.load();migrated=json.loads(self.path.read_text())
            self.assertFalse(loaded['vision']['enabled'])
            self.assertEqual(migrated['api_key'],raw['api_key']);self.assertEqual(migrated['vision']['api_key'],raw['vision']['api_key'])
            self.assertNotIn('fixture-vision-key',self.path.read_text())


class OnDemandVisionTests(unittest.TestCase):
    def test_default_off_retains_recognition_with_one_original_photo(self):
        self.assertFalse(vision.validate_vision()['enabled'])
        stop=threading.Event();data=png()
        service=vision.VisualService(vision.validate_vision('fixture-vision-key'),stop,lambda *args,**fields:None)
        try:
            self.assertTrue(service.ready)
            with patch('ai_vision.capture_png',return_value=data) as capture,patch('ai_vision.understand_png',return_value='物品。') as cloud:
                result=service.inspect({'question':'眼前是什么？'})
            self.assertTrue(result['accepted']);self.assertEqual(capture.call_count,1)
            self.assertEqual(cloud.call_count,1);self.assertEqual(cloud.call_args.args[0],data)
        finally:service.close()

    def test_missing_key_never_captures_or_uploads_even_when_continuous_is_on(self):
        service=vision.VisualService(vision.validate_vision(enabled=True),threading.Event(),lambda *args,**fields:None)
        try:
            with patch('ai_vision.capture_png') as capture,patch('ai_vision.understand_png') as cloud:
                self.assertFalse(service.inspect({'question':'眼前是什么？'})['accepted'])
            capture.assert_not_called();cloud.assert_not_called()
        finally:service.close()


if __name__=='__main__':unittest.main()

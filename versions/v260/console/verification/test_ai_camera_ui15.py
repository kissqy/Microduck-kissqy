"""Media-only quality transactions, original photos and optional camera startup."""
import base64
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zlib

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
import ai_camera_setup as setup
import ai_vision as vision
from ai_preferences import AIPreferences
from ai_runtime import AIHub
from telemetry import Store


class CameraConfigTests(unittest.TestCase):
    def test_only_quality_changes_and_unrelated_sections_and_comments_survive(self):
        text='# robot\n[control]\nfrequency = 50\n[media] # camera\nquality = "720p30" # kept\nbitrate = 2000000\n[custom]\nvalue = "user"\n'
        changed=setup.quality_text(text)
        self.assertEqual(changed,text.replace('720p30','720p15'))
        self.assertEqual(setup.quality_text(changed),changed)

    def test_unset_quality_or_section_uses_official_rung_without_losing_keys(self):
        for text in ('# untouched\n[control]\nfrequency=50\n','[media]\nsource="camera"\n'):
            with self.subTest(text=text):
                value=setup.quality_text(text)
                self.assertIn('quality = "720p15"',value)
                self.assertTrue(value.startswith(text.rstrip()) if '[media]' not in text else 'source="camera"' in value)

    def test_unsupported_config_layout_or_wrapper_fails_before_changes(self):
        with self.assertRaises(ValueError):setup.quality_text('media.quality = "720p30"\n')
        with self.assertRaises(ValueError):setup.config_path('{ argv[]=/bin/sh -c mediad ; ignore_errors=no ; }')
        with self.assertRaises(ValueError):setup.config_path('{ argv[]=/usr/bin/mediad --config relative ; ignore_errors=no ; }')

    def exercise(self,quality='720p30',fail=False,concurrent=False):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'robotd.toml';original=f'[media]\nquality="{quality}"\n[control]\nfrequency=50\n'
            path.write_text(original);calls=[]
            def command(*args):
                calls.append(args)
                if args[0]=='show':return '{ argv[]=/usr/bin/mediad --config '+str(path)+' ; ignore_errors=no ; }'
                if fail and len(calls)==2:
                    if concurrent:path.write_text('# independent change\n'+path.read_text())
                    raise RuntimeError('fixture mediad restart failure')
                return ''
            if fail:
                with self.assertRaisesRegex(RuntimeError,'restart failure'):setup.prepare(command)
                if concurrent:self.assertTrue(path.read_text().startswith('# independent change'))
                else:self.assertEqual(path.read_text(),original)
            else:
                result=setup.prepare(command)
                self.assertEqual(result['target_fps'],15)
                self.assertEqual(result['changed'],quality!='720p15')
                self.assertIn('720p15',path.read_text())
            self.assertTrue(all(args[1]=='mediad.service' for args in calls))
            return calls

    def test_transaction_only_restarts_mediad_and_keeps_720p_geometry(self):
        self.assertEqual(len(self.exercise()),2)

    def test_existing_15fps_setting_does_not_restart_the_camera_on_every_ai_start(self):
        self.assertEqual(len(self.exercise('720p15')),1)

    def test_failed_restart_restores_exact_previous_config(self):
        self.assertEqual(len(self.exercise(fail=True)),3)

    def test_failed_restart_does_not_overwrite_an_independent_edit(self):
        self.assertEqual(len(self.exercise(fail=True,concurrent=True)),2)


def fixture_png():
    # An original RGB PNG, built independently of the retired image filters.
    rows=[bytes([0,0,0,32,32,32,64,64,64,255,255,255]),
          bytes([16,16,16,64,64,64,128,128,128,240,240,240])]
    raw=b''.join(b'\0'+row for row in rows)
    def chunk(kind,data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    header=struct.pack('>IIBBBBB',4,2,8,2,0,0,0)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',header)+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b''),rows


class PhotoTests(unittest.TestCase):
    def test_preview_and_vision_receive_the_identical_original_photo(self):
        original,_=fixture_png();events=[];stop=threading.Event();sent=[]
        service=vision.VisualService(vision.validate_vision('fixture-vision-key'),stop,lambda kind,**fields:events.append({'kind':kind,**fields}))
        def observe(data,*args):sent.append(data);return '逆光中的物品。'
        with patch('ai_vision.capture_png',return_value=original),patch('ai_vision.understand_png',side_effect=observe):
            self.assertTrue(service.inspect({'question':'眼前是什么？'})['accepted'])
        self.assertTrue(service.wait_preview());service.close()
        assembler=vision.FrameAssembler();preview=None
        for event in events:
            if event['kind'].startswith('vision_frame_'):preview=assembler.feed(event) or preview
        self.assertEqual(sent[0],original)
        self.assertEqual(preview[1],sent[0])
        self.assertEqual(preview[0]['sha256'],hashlib.sha256(sent[0]).hexdigest())
        self.assertFalse(next(e for e in events if e['kind']=='vision_image')['lift_applied'])

    def test_legacy_enhancement_setting_cannot_restart_image_processing(self):
        original,_=fixture_png()
        for enabled in (False,True):
            with self.subTest(enabled=enabled):
                events=[];stop=threading.Event()
                service=vision.VisualService(vision.validate_vision('fixture-vision-key',backlight=enabled),stop,lambda kind,**fields:events.append({'kind':kind,**fields}))
                with patch('ai_vision.capture_png',return_value=original),patch('ai_vision.understand_png',return_value='物品。') as observe:
                    self.assertTrue(service.inspect({'question':'看看'})['accepted'])
                self.assertEqual(observe.call_args.args[0],original);self.assertFalse(stop.is_set())
                service.close()
                event=next(e for e in events if e['kind']=='vision_image')
                self.assertFalse(event['lift_applied']);self.assertFalse(event['image_warning'])

    def test_legacy_saved_model_and_key_survive_with_enhancement_retired(self):
        with tempfile.TemporaryDirectory() as directory:
            prefs=AIPreferences(Path(directory)/'prefs.json')
            legacy={'api_key':'fixture-vision-key','model':'ep-user-working','enabled':True}
            prefs.save('fixture-voice-key','fixture_voice',vision=legacy)
            saved=prefs.load();self.assertEqual(saved['vision']['model'],'ep-user-working')
            self.assertFalse(saved['vision']['backlight'])
            self.assertEqual(saved['vision']['api_key'],'fixture-vision-key')
            saved['vision']['backlight']=True
            prefs.save(saved['api_key'],saved['voice_id'],saved['persona'],vision=saved['vision'])
            self.assertFalse(prefs.load()['vision']['backlight'])


class RuntimeTests(unittest.TestCase):
    def test_default_off_does_not_prepare_camera_or_change_quality_on_ai_start(self):
        with tempfile.TemporaryDirectory() as directory:
            calls=[];ran=[]
            transport=SimpleNamespace(prepare_ai_camera=lambda:calls.append('prepare'))
            hub=AIHub(Store('service'),service_controller=SimpleNamespace(transport=transport),preferences=AIPreferences(Path(directory)/'prefs.json'))
            hub.vision_settings=vision.validate_vision('fixture-vision-key')
            hub._get_ai_channel=lambda:None
            hub.provider=SimpleNamespace(run=lambda:ran.append(True))
            try:
                hub._run()
                self.assertEqual(ran,[True]);self.assertEqual(calls,[])
                self.assertFalse(hub.vision_settings['enabled'])
                self.assertTrue(hub.status()['vision']['credentials_present'])
            finally:hub.close()

    def test_explicit_on_prepares_without_vision_key_then_restores_only_its_token(self):
        with tempfile.TemporaryDirectory() as directory:
            calls=[];ran=[];token={'fixture':'private restore receipt'}
            def prepare():calls.append('prepare');return {'accepted':True,'restore':token}
            def restore(received):calls.append(('restore',received));return {'accepted':True,'restored':True}
            transport=SimpleNamespace(prepare_ai_camera=prepare,restore_ai_camera=restore)
            hub=AIHub(Store('service'),service_controller=SimpleNamespace(transport=transport),preferences=AIPreferences(Path(directory)/'prefs.json'))
            hub.vision_settings=vision.validate_vision(enabled=True)
            hub._get_ai_channel=lambda:None
            hub.provider=SimpleNamespace(run=lambda:ran.append(True))
            try:
                hub._run()
                self.assertEqual(ran,[True]);self.assertEqual(calls,['prepare',('restore',token)])
                self.assertIsNone(hub.camera_restore)
                self.assertTrue(hub.vision_settings['enabled'],'stopping a session preserves the user preference')
                self.assertNotIn('private restore receipt',json.dumps(hub.status()))
            finally:hub.close()

    def test_camera_setup_failure_does_not_stop_native_voice_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            transport=SimpleNamespace(prepare_ai_camera=lambda:(_ for _ in ()).throw(RuntimeError('fixture camera denied')))
            hub=AIHub(Store('service'),service_controller=SimpleNamespace(transport=transport),preferences=AIPreferences(Path(directory)/'prefs.json'))
            ran=[];hub.vision_settings=vision.validate_vision('fixture-vision-key',enabled=True)
            hub._get_ai_channel=lambda:None
            hub.provider=SimpleNamespace(run=lambda:ran.append(True))
            try:
                hub._run();self.assertEqual(ran,[True])
                self.assertEqual(hub.status()['camera_profile']['phase'],'warning')
                self.assertIn('fixture camera denied',hub.status()['camera_profile']['warning'])
            finally:hub.close()


if __name__=='__main__':unittest.main()

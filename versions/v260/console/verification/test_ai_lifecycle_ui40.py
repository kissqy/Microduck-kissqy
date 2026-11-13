import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ai_mouth_lease import MouthLease
from ai_hat_audio import NativeSpeaker,_ALSA
from ai_runtime import AIHub
from ai_preferences import AIPreferences
from telemetry import Store


class MouthPauseTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.directory=Path(self.tmp.name)

    def test_real_ack_required_before_audio_when_padd_is_running(self):
        lease=MouthLease(lambda:True,lambda:False,directory=self.directory,requires_ack=lambda:True)
        self.addCleanup(lease.close)
        entered=threading.Event();finished=threading.Event();errors=[]
        def acquire():
            entered.set()
            try:lease.acquire();finished.set()
            except Exception as e:errors.append(e)
        worker=threading.Thread(target=acquire);worker.start();entered.wait(1)
        deadline=time.monotonic()+.3
        while not lease.path.exists() and time.monotonic()<deadline:time.sleep(.005)
        self.assertFalse(finished.is_set())
        lease.ack.write_text('0\n')
        self.assertFalse(finished.wait(.02),'stale ACK must not authorize PCM')
        lease.ack.write_text(lease.path.read_text())
        worker.join(1);self.assertFalse(errors);self.assertTrue(finished.is_set())

    def test_no_padd_does_not_block_audio_and_close_only_removes_own_files(self):
        other=self.directory/('f'*32+'.lease');other.write_text('123\n')
        lease=MouthLease(lambda:True,lambda:False,directory=self.directory,requires_ack=lambda:False)
        lease.acquire();expiry=int(lease.path.read_text())
        self.assertGreater(expiry,time.monotonic_ns()//1_000_000)
        lease.close();self.assertFalse(lease.path.exists());self.assertTrue(other.exists())

    def test_cancel_before_start_leaves_no_pause_and_missing_ack_is_bounded(self):
        lease=MouthLease(lambda:True,lambda:True,directory=self.directory,requires_ack=lambda:True)
        with self.assertRaisesRegex(RuntimeError,'取消'):lease.acquire()
        self.assertFalse(lease.path.exists())
        lease=MouthLease(lambda:True,lambda:False,directory=self.directory,requires_ack=lambda:True)
        started=time.monotonic()
        with self.assertRaisesRegex(RuntimeError,'确认让出嘴巴'):lease.acquire()
        self.assertLess(time.monotonic()-started,1.5);self.assertFalse(lease.path.exists())

    def test_speaker_releases_after_real_drain_and_on_drain_failure(self):
        for fail in (False,True):
            speaker=NativeSpeaker(device='plughw:fixture');events=[]
            speaker._mouth_lease=Mock(close=lambda:events.append('release'))
            def close(*a,**k):
                self.assertTrue(speaker._mouth_draining);events.append('drain')
                if fail:raise RuntimeError('playback error')
                return True
            with patch.object(_ALSA,'close',side_effect=close):
                if fail:
                    with self.assertRaises(RuntimeError):speaker.finish()
                else:self.assertTrue(speaker.finish())
            self.assertEqual(events,['drain','release'])
            self.assertIsNone(speaker._mouth_lease)


class Transport:
    def __init__(self):self.calls=[];self.channel=None;self.failure=None
    def prepare_ai_camera(self):
        self.calls.append('prepare')
        if self.failure:raise self.failure
        return {'accepted':True,'restore':{'private_path':'/etc/robot/custom.toml'},'target_fps':15}
    def restore_ai_camera(self,snapshot):
        self.calls.append(('restore',snapshot))
        return {'accepted':True,'restored':True}


class HubLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.transport=Transport()
        self.hub=AIHub(Store('service'),service_controller=Mock(transport=self.transport),
                       preferences=AIPreferences(Path(self.tmp.name)/'ai.json'))
        self.addCleanup(self.hub.close)
        self.hub.api_key='fixture-voice-key-123456'
        self.hub._get_ai_channel=lambda:'fixture_channel'

    def test_default_on_demand_does_not_touch_camera_and_key_allows_photo(self):
        self.assertFalse(self.hub.vision_settings['enabled'])
        self.hub.vision_settings['api_key']='fixture-vision-key-123456'
        self.hub.provider=Mock();self.hub.provider_ready=True
        self.hub.inspect_scene({'question':'眼前是什么？'})
        self.hub.provider.inspect_scene.assert_called_once_with('眼前是什么？')
        self.assertEqual(self.transport.calls,[])

    def test_live_toggle_without_key_uses_only_camera_rpc_and_keeps_snapshot_private(self):
        self.hub.worker=Mock();self.hub.worker.is_alive.return_value=True
        self.hub.provider=Mock();provider=self.hub.provider
        result=self.hub.set_camera_mode({'enabled':True})
        self.assertTrue(result['vision']['enabled']);self.assertEqual(result['camera_profile']['phase'],'ready')
        self.assertNotIn('private_path',json.dumps(result))
        result=self.hub.set_camera_mode({'enabled':False})
        self.assertFalse(result['vision']['enabled']);self.assertEqual(result['camera_profile']['phase'],'idle')
        self.assertEqual(self.transport.calls[0],'prepare');self.assertEqual(self.transport.calls[1][0],'restore')
        self.assertIs(provider,self.hub.provider);provider.close.assert_not_called()
        self.assertIsNone(self.hub.camera_restore)

    def test_failed_camera_setup_does_not_enable_or_clear_warning_on_stop(self):
        self.transport.failure=RuntimeError('camera failed')
        with self.assertRaisesRegex(RuntimeError,'camera failed'):self.hub._apply_camera_mode(True)
        self.assertFalse(self.hub.vision_settings['enabled'])
        self.hub._finish_camera_mode()
        self.assertEqual(self.hub.camera_profile['phase'],'warning')

    def test_manual_speech_ack_uses_session_revision_without_task_state(self):
        self.hub.speech_session='a'*32
        self.hub.log('voice_state',source='speech_control',speech_session='a'*32,speech_revision=1,unlocked=True)
        self.assertTrue(self.hub.gate.speaking_enabled)
        self.hub.log('voice_state',source='speech_control',speech_session='a'*32,speech_revision=0,unlocked=False)
        self.assertTrue(self.hub.gate.speaking_enabled)
        self.hub.log('voice_state',source='speech_control',speech_session='b'*32,speech_revision=2,unlocked=False)
        self.assertTrue(self.hub.gate.speaking_enabled)
        self.assertNotIn('task',self.hub.status())


if __name__=='__main__':unittest.main()

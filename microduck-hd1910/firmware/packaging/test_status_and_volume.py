"""Status changes cross the warm channel once; saved volume wins over reboot defaults."""
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import controls
from controls import Transport
from remote_audio import NativeAudio
from system_log import SystemLog
import voice_preferences
import webpad

ROOT = Path(__file__).resolve().parents[1]


class StatusAndVolumeTests(unittest.TestCase):
    def test_physical_display_uses_native_system_without_a_webpad_status_request(self):
        from controls import Controller
        class Store:
            def snapshot(self):return {}
        tr=Transport();controller=Controller(Store(),transport=tr)
        tr.pad_status={'real_connected':True,'real_devices':[{'name':'newly attached'}]};tr.pad_status_at=95
        with patch.object(controls.time,'monotonic',return_value=100),patch.object(controls,'open_remote_socket',side_effect=AssertionError('status opened input')):
            old={'system':{'real_gamepads':[]},'channels':{'system':{'age_ms':6000}}}
            self.assertTrue(controller.status(old)['webpad']['real_connected'],'older display sample must not overrule rejection')
            fresh={'system':{'real_gamepads':[],'pad_settings':{'mouth_percent':60,'head_rad':.5}},'channels':{'system':{'age_ms':1000}}}
            state=controller.status(fresh)
            self.assertFalse(state['webpad']['real_connected']);self.assertEqual(state['webpad']['settings'],fresh['system']['pad_settings'])
            fresh['system']['real_gamepads']=[{'name':'Xbox','event':'event3'}]
            self.assertTrue(controller.status(fresh)['webpad']['real_connected'])

    def test_successful_status_and_held_input_do_not_fill_system_log_but_rejections_do(self):
        from io import BytesIO
        with tempfile.TemporaryDirectory() as directory:
            log=SystemLog(directory);tr=Transport(system_log=log)
            class Peer:
                def sendall(self,data):pass
                def close(self):pass
            tr.peer=Peer();tr.reader=BytesIO((b'{"accepted":true,"owner":"test-page"}\n'*40)+b'{"accepted":false,"reason":"physical takeover"}\n')
            try:
                with patch.object(controls.select,'select',return_value=([],[],[])):
                    for _ in range(40):
                        tr.call({'action':'webpad_status'})
                        tr.call({'action':'webpad_state','owner':'test-page','frame':{'axes':{'lx':.5}}})
                    self.assertEqual(log.tail()['entries'],[])
                    self.assertFalse(tr.call({'action':'webpad_state','owner':'test-page','frame':{}})['accepted'])
                    self.assertIn('physical takeover',log.tail()['entries'][0]['text'])
            finally:tr.close();log.close()

    def test_system_volume_saved_only_after_confirmed_readback_and_reboot_restored_by_alsa(self):
        for value in (0,17):
            with self.subTest(volume=value),tempfile.TemporaryDirectory() as directory:
                base=Path(directory);setup=base/'voice-device.json';setup.write_text('{"card":"aic3104"}')
                current=[voice_preferences.raw(50)];muted=[False];saved=[];commands=[];fail=[False]
                def runner(argv,**_):
                    commands.append(argv)
                    if 'store' in argv:
                        if fail[0]:return SimpleNamespace(returncode=1,stdout='',stderr='state file permission denied')
                        saved[:]=[current[0],muted[0]];return SimpleNamespace(returncode=0,stdout='',stderr='')
                    if 'name=Line Playback Switch' in argv:
                        if 'cset' in argv:muted[0]=argv[-1]=='off,off'
                        return SimpleNamespace(returncode=0,stdout=': values='+('off,off' if muted[0] else 'on,on'),stderr='')
                    if 'cset' in argv:current[0]=int(argv[-1])
                    return SimpleNamespace(returncode=0,stdout=f': values={current[0]},{current[0]}',stderr='')
                audio=NativeAudio(None,setup=setup,config=base/'none',runner=runner)
                self.assertTrue(audio.set_volume(value)['volume_saved'])
                self.assertIn(['sudo','-n','/usr/sbin/alsactl','store','aic3104'],commands)
                # Simulate system ALSA restore after the board's boot defaults.
                current[0]=127;muted[0]=False;current[0],muted[0]=saved
                reconnected=NativeAudio(None,setup=setup,config=base/'none',runner=runner)
                self.assertEqual(reconnected.status()['volume'],value)
                self.assertEqual(list(base.glob('**/*volume*.json')),[])
                prior=list(saved);fail[0]=True
                with self.assertRaisesRegex(RuntimeError,'保存失败'):audio.set_volume(25)
                self.assertFalse(audio.status()['volume_saved']);self.assertEqual(saved,prior)

    def test_idle_neutral_pad_stays_attached_without_a_lease_or_repeated_input(self):
        class Device:
            def __init__(self): self.frames=[];self.closed=False
            def send(self, *frame): self.frames.append(frame)
            def close(self): self.closed=True
        devices=[]
        def create():
            device=Device();devices.append(device);return device
        now=[0.0];physical=[]
        bridge=webpad.Bridge(create, lambda: physical, lambda: now[0])
        bridge.handle({'action':'state','owner':'test-page','frame':{'buttons':['start']}})
        bridge.handle({'action':'state','owner':'test-page','frame':{'buttons':[]}})
        now[0]=2;bridge.poll()
        self.assertIsNone(bridge.owner)
        self.assertFalse(bridge.status()['web_active'])
        self.assertFalse(devices[0].closed)
        for _ in range(30):bridge.poll()
        self.assertEqual(len(devices[0].frames),2)
        bridge.handle({'action':'state','owner':'next-page','frame':{'buttons':['y']}})
        self.assertEqual(len(devices),1)
        physical.append({'name':'Xbox'});bridge.poll()
        self.assertTrue(devices[0].closed)


if __name__ == '__main__':
    unittest.main()

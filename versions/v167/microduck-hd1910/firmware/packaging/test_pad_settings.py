"""Remember input limits without sending actions or rewriting calibration."""
import json,unittest,tempfile
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch
import pad_settings,webpad,gamepad
from service_control import validate,ControlError
class Device:
 def __init__(self):self.frames=[]
 def send(self,*frame):self.frames.append(frame)
 def close(self):pass
class SettingsTests(unittest.TestCase):
 def test_settings_save_and_restart_load_preserve_choices(self):
  with tempfile.TemporaryDirectory() as t:
   path=Path(t)/'settings.json';self.assertEqual(pad_settings.load(path),pad_settings.DEFAULT)
   pad_settings.save(60,.5,path);self.assertEqual(pad_settings.load(path),{'mouth_percent':60.,'head_rad':.5})
 def test_settings_reject_nonfinite_and_unavailable_choices(self):
  for mouth,head in ((-1,2.5),(101,2.5),(float('nan'),1),(True,1),(40,.6),(40,True)):
   with self.assertRaises(ValueError):pad_settings.validate(mouth,head)
 def test_web_bridge_keeps_raw_triggers_so_sound_edges_are_not_scaled(self):
  with patch.object(webpad,'load',return_value={'mouth_percent':60.,'head_rad':.5}):
   device=Device();bridge=webpad.Bridge(lambda:device,lambda:[])
   bridge.handle({'action':'state','owner':'test-page','frame':{'axes':{'rt':1,'lt':.5,'lx':.8},'buttons':['y']}})
   axes,buttons=device.frames[-1];self.assertEqual(axes['rt'],1);self.assertEqual(axes['lt'],.5);self.assertEqual(axes['lx'],.8);self.assertEqual(buttons,{'y'})
   bridge.handle({'action':'state','owner':'test-page','frame':{'axes':{},'buttons':[]}})
   self.assertEqual(device.frames[-1][0]['rt'],0);self.assertEqual(device.frames[-1][0]['lt'],0)
 def test_physical_controller_does_not_use_web_mouth_scale(self):
  with patch.object(webpad,'load',return_value={'mouth_percent':20.,'head_rad':1.}):
   bridge=webpad.Bridge(Device,lambda:[{'name':'real Xbox'}])
   self.assertFalse(bridge.handle({'action':'state','owner':'test-page','frame':{'axes':{'rt':1}}})['accepted']);self.assertIsNone(bridge.pad)
 def test_management_request_passes_choices_with_saved_password(self):
  request={'action':'set-pad-settings','mouth_percent':60.,'head_rad':.5,'supported':True,'sudo_password':'test-password'}
  self.assertEqual(validate(request),request)
  with self.assertRaises(ControlError):validate({**request,'head_rad':1.5})
 def test_official_head_cli_uses_saved_setting_without_rust_mapping_patch(self):
  with tempfile.TemporaryDirectory() as t,patch.object(gamepad,'ROOT',Path(t)),patch.object(gamepad,'BASE',Path(__file__).parent),patch.object(gamepad,'run',return_value=SimpleNamespace(returncode=0,stdout='')), patch.object(gamepad,'load',return_value={'mouth_percent':60.,'head_rad':.5}),patch.object(gamepad,'SETTINGS_PATH',Path(t)/'pad-settings.json'),patch.object(gamepad,'save'):
   gamepad.upgrade_client();drop=(Path(t)/gamepad.PAD_DROPIN).read_text()
   self.assertIn('--max-head 0.5 --input-settings',drop);self.assertIn('--socket /run/robotd.sock',drop)
   self.assertNotIn('padd.sock',drop)
if __name__=='__main__':unittest.main()

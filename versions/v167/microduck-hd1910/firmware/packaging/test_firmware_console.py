"""Firmware uploads and live logs must remain safe during failed-service recovery."""
import io
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'console'))
import firmware_packages as fw
from controls import ControlError
from service_channel import ServiceChannel
from service_control import ServiceTransport,ServiceController,validate

class FirmwareTests(unittest.TestCase):
 def setUp(self):
  self.directory=tempfile.TemporaryDirectory();self.root=Path(self.directory.name)
  archive=self.root/'updates'/fw.ARCHIVE_NAME;archive.parent.mkdir();archive.write_bytes(b'known approved firmware bytes')
  self.digest=hashlib.sha256(archive.read_bytes()).hexdigest()
  (self.root/'BUILD_MANIFEST.json').write_text(json.dumps({'service_build':fw.BUILD,'console_version':fw.CONSOLE_VERSION,'service_package_sha256':self.digest,'models':{}}))
  self.patch=patch.object(fw,'ROOT',self.root);self.patch.start()
 def tearDown(self):self.patch.stop();self.directory.cleanup()
 def zip_bytes(self,data):
  stream=io.BytesIO()
  with zipfile.ZipFile(stream,'w') as z:z.writestr('firmware/updates/'+fw.ARCHIVE_NAME,data)
  return stream.getvalue()
 def test_matching_local_zip_checked_before_any_remote_operation(self):
  data=self.zip_bytes(b'known approved firmware bytes')
  package=fw.PreparedFirmware('firmware.zip',io.BytesIO(data),len(data),'browser1234')
  try:
   self.assertEqual(package.info['sha256'],self.digest);self.assertEqual(package.owner,'browser1234')
   self.assertEqual(package.path.read_bytes(),b'known approved firmware bytes')
  finally:package.close()
 def test_old_or_unknown_firmware_and_truncated_zip_are_rejected(self):
  data=self.zip_bytes(b'old firmware')
  with self.assertRaisesRegex(ControlError,'不匹配'):fw.PreparedFirmware('bad.zip',io.BytesIO(data),len(data),'browser1234')
  with self.assertRaisesRegex(ControlError,'上传未完成'):fw.PreparedFirmware('bad.zip',io.BytesIO(b'a'),100,'browser1234')
  with self.assertRaisesRegex(ControlError,'无法读取'):fw.PreparedFirmware('bad.zip',io.BytesIO(b'bad'),3,'browser1234')
 def test_bundle_manifest_mismatch_and_tamper_are_refused(self):
  (self.root/'updates'/fw.ARCHIVE_NAME).write_bytes(b'tampered')
  with self.assertRaisesRegex(ControlError,'SHA256'):fw.bundle_info()
 def test_firmware_command_cannot_carry_executable_paths(self):
  for token in ('/tmp/arbitrary.sh','file.zip','../x'):
   with self.assertRaises(ControlError):validate({'action':'upgrade-service','supported':True,'firmware':token})
  self.assertEqual(validate({'action':'upgrade-service','supported':True,'firmware':'bundled'})['firmware'],'bundled')
 def test_progress_received_before_management_finishes(self):
  channel=ServiceChannel('','/unused.sock');event=threading.Event();result=[]
  script="import time;print('first stage',flush=True);time.sleep(.25);print('second stage',flush=True)"
  def run():
   result.append(channel.request({'kind':'manage','argv':[sys.executable,'-u','-c',script],'input':'','progress':True,'timeout':5},timeout=10,progress=lambda line:event.set()))
  thread=threading.Thread(target=run);thread.start()
  try:
   self.assertTrue(event.wait(8));thread.join(10);self.assertFalse(thread.is_alive())
   self.assertEqual(result[0]['returncode'],0);self.assertIn('second stage',result[0]['stdout'])
  finally:channel.close()
 def test_sudo_password_never_enters_progress_or_final_error(self):
  class Channel:
   def request(self,request,timeout,progress=None):
    progress('sudo secret123 rejected\n');return {'returncode':1,'stdout':'secret123 rejected','stderr':''}
  transport=ServiceTransport('', '/unused.sock');transport.channel=Channel();lines=[]
  with self.assertRaises(ControlError) as error:transport._manage(['true'],password='secret123',progress=lines.append)
  self.assertNotIn('secret123',''.join(lines)+str(error.exception));self.assertIn('[已隐藏]',''.join(lines))
 def test_upgrade_works_without_fresh_robot_feedback_and_preserves_logs(self):
  class Store:
   service_operation=False
   def snapshot(self):return {'bus':{},'service_sample_fresh':False}
   def record_service_command(self,job):pass
  class Transport:
   def upgrade(self,password=None,archive=None,progress=None):
    progress('UART 配置完成\n实际模型哈希已核对\n');return {'message':'verified'}
  controller=ServiceController(Store(),transport=Transport());job={'action':'upgrade-service','status':'running'}
  controller._execute({'action':'upgrade-service','supported':True,'firmware':'bundled'},job,0)
  self.assertEqual(job['status'],'completed');self.assertIn('UART 配置完成',job['log']);self.assertFalse(controller.store.service_operation)

class DirectUpgradeTests(unittest.TestCase):
 def test_input_reconnect_error_does_not_turn_installed_firmware_into_failed_upgrade(self):
  class Store:
   service_operation=False
   def snapshot(self):return {'bus':{},'service_sample_fresh':False}
   def record_service_command(self,job):pass
  class Transport:
   def upgrade(self,*args,**kwargs):return {'message':'installed'}
  class Controls:
   def resume_connections(self):pass
   def reconnect_after_service(self):raise OSError('input socket not created yet')
  controller=ServiceController(Store(),transport=Transport(),controls=Controls());job={'action':'upgrade-service','status':'running'}
  controller._execute({'action':'upgrade-service','supported':True,'firmware':'bundled'},job,0)
  self.assertEqual(job['status'],'completed');self.assertFalse(job['result']['input']['webpad_reconnected'])

if __name__=='__main__':unittest.main()

"""Exercise a real Linux executable holder, interrupted staging and local data."""
import errno,hashlib,importlib.util,json,shutil,subprocess,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('atomic_install',Path(__file__).with_name('install-files.py'))
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)
class AtomicInstallTests(unittest.TestCase):
 def joint_profile_bundle(self,root):
  bundle=self.bundle(root);live=root/'live'
  ident='1cbf8730eadd75a5704332c9f3c10f60'
  relative=f'models/{ident}/deployment-execution.json'
  new=bundle/'models'/ident;old=live/'models'/ident
  new.mkdir(parents=True);old.mkdir(parents=True)
  original={'policy.onnx':b'original weights','deployment-contract.json':b'{"export_contract_revision":2}','training-request.json':b'original training'}
  for name,data in original.items():
   (new/name).write_bytes(data);(old/name).write_bytes(data)
  profile=(Path(__file__).resolve().parents[1]/'policies/walk/deployment-execution.json').read_bytes()
  (bundle/relative).write_bytes(profile)
  request={'slot':'walk','id':ident,'export_contract_revision':2,'execution_profile_sha256':hashlib.sha256(profile).hexdigest()}
  (bundle/'management-profile.json').write_text(json.dumps({'requested_model_replacement':request}))
  (bundle/'install-files.json').write_text(json.dumps(['padd','management-profile.json',relative,*[f'models/{ident}/{n}' for n in original]]))
  (live/'calibration.toml').write_bytes(b'operator calibration')
  return bundle,live,old,relative,profile,original

 def test_joint_execution_profile_reaches_preimported_model_once(self):
  with tempfile.TemporaryDirectory() as tmp:
   bundle,live,old,relative,profile,original=self.joint_profile_bundle(Path(tmp))
   copied=[];copy=installer.shutil.copy2
   def observed(source,target):copied.append(Path(source));return copy(source,target)
   with patch.object(installer.shutil,'copy2',side_effect=observed):installer.install(bundle,live)
   self.assertEqual((live/relative).read_bytes(),profile)
   self.assertEqual([p.name for p in copied if 'models' in p.parts],['deployment-execution.json'])
   for name,data in original.items():self.assertEqual((old/name).read_bytes(),data)
   self.assertEqual((live/'calibration.toml').read_bytes(),b'operator calibration')
   # Removing the override for a raw-training comparison remains an operator
   # choice after this release's one-time request has been installed.
   (live/relative).unlink();copied.clear()
   with patch.object(installer.shutil,'copy2',side_effect=observed):installer.install(bundle,live)
   self.assertFalse((live/relative).exists())
   self.assertFalse(any('models' in p.parts for p in copied))

 def test_execution_request_marker_follows_its_file_after_interruption(self):
  with tempfile.TemporaryDirectory() as tmp:
   bundle,live,old,relative,profile,original=self.joint_profile_bundle(Path(tmp))
   replace=installer.os.replace
   def interrupted(source,target):
    if Path(target)==live/relative:raise OSError('interrupted deployment profile write')
    return replace(source,target)
   with patch.object(installer.os,'replace',side_effect=interrupted):
    with self.assertRaises(OSError):installer.install(bundle,live)
   self.assertFalse((live/'management-profile.json').exists())
   installer.install(bundle,live)
   self.assertEqual((live/relative).read_bytes(),profile)
   for name,data in original.items():self.assertEqual((old/name).read_bytes(),data)

 def test_invalid_execution_digest_does_not_replace_installed_payload(self):
  with tempfile.TemporaryDirectory() as tmp:
   bundle,live,old,relative,profile,original=self.joint_profile_bundle(Path(tmp))
   (live/'padd').write_bytes(b'previous executable')
   (bundle/relative).write_bytes(profile+b' ')
   with self.assertRaisesRegex(ValueError,'SHA256'):installer.install(bundle,live)
   self.assertEqual((live/'padd').read_bytes(),b'previous executable')
   self.assertFalse((live/'management-profile.json').exists())

 def test_broken_shipped_contract_is_restored_on_repeat_upgrade(self):
  for broken in (b'',b'{"task":',b'null'):
   with self.subTest(broken=broken),tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);bundle=self.bundle(root);live=root/'live'
    ident='a481d9f211f31d9476ab1a319fe362a2'
    new=bundle/'models'/ident;old=live/'models'/ident
    new.mkdir(parents=True);old.mkdir(parents=True)
    (new/'deployment-contract.json').write_text('{"task":"StandUp"}')
    (new/'policy.onnx').write_bytes(b'original weights');(old/'policy.onnx').write_bytes(b'original weights')
    (old/'deployment-contract.json').write_bytes(broken)
    unknown=live/'models'/'user';unknown.mkdir();(unknown/'deployment-contract.json').write_bytes(b'operator model')
    (live/'calibration.toml').write_bytes(b'mounted calibration')
    (bundle/'install-files.json').write_text(json.dumps(['padd',f'models/{ident}/policy.onnx',f'models/{ident}/deployment-contract.json']))
    installer.install(bundle,live)
    self.assertEqual((old/'deployment-contract.json').read_bytes(),(new/'deployment-contract.json').read_bytes())
    self.assertEqual((old/'policy.onnx').read_bytes(),b'original weights')
    self.assertEqual((unknown/'deployment-contract.json').read_bytes(),b'operator model')
    self.assertEqual((live/'calibration.toml').read_bytes(),b'mounted calibration')
    with patch.object(installer.shutil,'copy2',wraps=installer.shutil.copy2) as copy:
     installer.install(bundle,live)
     self.assertFalse(any('models' in Path(call.args[0]).parts for call in copy.call_args_list))

 def test_ordinary_upgrade_removes_only_explicitly_retired_models(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);bundle=self.bundle(root);live=root/'live';models=live/'models';models.mkdir(parents=True)
   retired=['d11f8430712c35cb2416ce3948e9f8b7','388461feb3f4cd24071197ffc30d63e2','5c019c3d3d2c490947f21974f3947506','9e3ff8bde021be28a728c02dbd8e7aaf']
   for ident in [*retired,'1cbf8730eadd75a5704332c9f3c10f60','a481d9f211f31d9476ab1a319fe362a2','user-import']:
    (models/ident).mkdir();(models/ident/'policy.onnx').write_bytes(b'weights')
   (bundle/'management-profile.json').write_text(json.dumps({'retired_model_ids':retired}))
   (bundle/'install-files.json').write_text('["padd","management-profile.json"]')
   installer.install(bundle,live)
   self.assertEqual({p.name for p in models.iterdir()},{'1cbf8730eadd75a5704332c9f3c10f60','a481d9f211f31d9476ab1a319fe362a2','user-import'})

 def test_corrected_same_id_contract_updates_once_and_keeps_other_models(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);bundle=self.bundle(root);installed=root/'installed'
   ident='9e3ff8bde021be28a728c02dbd8e7aaf'
   (bundle/'management-profile.json').write_text(json.dumps({'requested_model_replacement':{'id':ident,'export_contract_revision':2}}))
   new=bundle/'models'/ident;old=installed/'models'/ident
   new.mkdir(parents=True);old.mkdir(parents=True)
   for directory,revision in ((new,2),(old,1)):
    (directory/'policy.onnx').write_bytes(b'unchanged weights')
    (directory/'deployment-contract.json').write_text(json.dumps({'export_contract_revision':revision}))
    (directory/'export-data.zip').write_bytes(b'corrected' if revision==2 else b'broken')
   other=installed/'models'/'other';other.mkdir();(other/'deployment-contract.json').write_bytes(b'operator model')
   (installed/'calibration.toml').write_bytes(b'local calibration')
   names=['padd','management-profile.json']+[str(p.relative_to(bundle)) for p in new.iterdir()]
   (bundle/'install-files.json').write_text(json.dumps(names))
   installer.install(bundle,installed)
   self.assertEqual(json.loads((old/'deployment-contract.json').read_text())['export_contract_revision'],2)
   self.assertEqual((old/'export-data.zip').read_bytes(),b'corrected')
   self.assertEqual((old/'policy.onnx').read_bytes(),b'unchanged weights')
   self.assertEqual((other/'deployment-contract.json').read_bytes(),b'operator model')
   self.assertEqual((installed/'calibration.toml').read_bytes(),b'local calibration')
   # A newer operator import must survive repeating the same release install.
   (old/'deployment-contract.json').write_text('{"export_contract_revision":3}')
   (old/'export-data.zip').write_bytes(b'operator revision 3')
   installer.install(bundle,installed)
   self.assertEqual((old/'export-data.zip').read_bytes(),b'operator revision 3')
   installer.install(bundle,installed,replace_models=True)
   self.assertEqual((old/'export-data.zip').read_bytes(),b'corrected');self.assertFalse(other.exists())

 def test_preserved_models_are_never_copied_to_temporary_stage(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);bundle=self.bundle(root);live=root/'live';new=bundle/'models/user';old=live/'models/user'
   new.mkdir(parents=True);old.mkdir(parents=True)
   for directory in (new,old):
    (directory/'deployment-contract.json').write_text('{}');(directory/'policy.onnx').write_bytes(b'model')
   names=['padd','models/user/policy.onnx','models/user/deployment-contract.json']
   (bundle/'install-files.json').write_text(json.dumps(names));copied=[];copy=installer.shutil.copy2
   def observed(source,target):
    copied.append(Path(source));return copy(source,target)
   with patch.object(installer.shutil,'copy2',side_effect=observed):installer.install(bundle,live)
   self.assertFalse(any('models' in p.parts for p in copied))
 def test_cleanup_keeps_ownership_metadata_until_it_can_be_replaced(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);bundle=self.bundle(root);installed=root/'installed';installed.mkdir()
   metadata=installed/'install-files.json';metadata.write_text('["padd","install-files.json","SHA256SUMS"]')
   hashes=installed/'SHA256SUMS';hashes.write_text('previous installed checksums')
   installer.cleanup(bundle,installed)
   self.assertEqual(metadata.read_text(),'["padd","install-files.json","SHA256SUMS"]')
   self.assertEqual(hashes.read_text(),'previous installed checksums')

 def bundle(self,root):
  bundle=root/'bundle';bundle.mkdir();shutil.copy2('/bin/sleep',bundle/'padd')
  (bundle/'install-files.json').write_text('["padd"]');(bundle/'SHA256SUMS').write_text('')
  return bundle
 def test_running_executable_is_replaced_and_generated_data_is_preserved(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);bundle=self.bundle(root);installed=root/'installed';installed.mkdir()
   shutil.copy2(bundle/'padd',installed/'padd');(installed/'voice-device.json').write_text('local voice')
   (installed/'models'/'retired').mkdir(parents=True)
   holder=subprocess.Popen([str(installed/'padd'),'60'])
   try:
    # The managed test environment may deny /proc/PID/exe. Opening without
    # truncation observes the kernel's executable write exclusion directly.
    for _ in range(1000):
     try:
      with (installed/'padd').open('r+b'):pass
     except OSError as error:
      if error.errno==errno.ETXTBSY:break
      raise
     if holder.poll() is not None:self.fail('native executable exited')
     time.sleep(.001)
    else:self.fail('native executable did not acquire its inode')
    old_inode=(installed/'padd').stat().st_ino
    with self.assertRaises(OSError) as busy:shutil.copy2(bundle/'padd',installed/'padd')
    self.assertEqual(busy.exception.errno,errno.ETXTBSY)
    installer.install(bundle,installed)
    self.assertNotEqual(old_inode,(installed/'padd').stat().st_ino)
    self.assertIsNone(holder.poll());subprocess.run([str(installed/'padd'),'0'],check=True)
    self.assertEqual((installed/'voice-device.json').read_text(),'local voice')
    self.assertTrue((installed/'models'/'retired').exists())
    self.assertFalse(list(installed.glob('.r17-stage-*')))
   finally:holder.terminate();holder.wait()
 def test_staging_failure_does_not_replace_installed_files(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);bundle=self.bundle(root);installed=root/'installed';installed.mkdir();(installed/'padd').write_bytes(b'old')
   with patch.object(installer.shutil,'copy2',side_effect=OSError('disk full')):
    with self.assertRaises(OSError):installer.install(bundle,installed)
   self.assertEqual((installed/'padd').read_bytes(),b'old');self.assertFalse(list(installed.glob('.r17-stage-*')))
 def test_linked_destination_is_rejected_without_touching_external_file(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);bundle=self.bundle(root);installed=root/'installed';installed.mkdir();external=root/'external';external.write_bytes(b'untouched');(installed/'padd').symlink_to(external)
   with self.assertRaises(ValueError):installer.install(bundle,installed)
   self.assertEqual(external.read_bytes(),b'untouched')
if __name__=='__main__':unittest.main()

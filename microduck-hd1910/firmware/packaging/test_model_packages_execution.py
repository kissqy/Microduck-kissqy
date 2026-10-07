"""Preserve real joint training data while validating its separate runtime experiment."""
import copy
import json
import tempfile
import tomllib
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import model_packages as models
from configure import dumps

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'policies/walk'
ID='1cbf8730eadd75a5704332c9f3c10f60'


class JointExecutionImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original={name:(FIXTURE/name).read_bytes()
                      for name in ('policy.onnx',*models.SOURCE_FILES)
                      if (FIXTURE/name).is_file()}
        cls.execution=(FIXTURE/models.EXECUTION_FILE).read_bytes()
        cls.profile=json.loads(cls.execution)
        cls.info=models.validate_export(cls.original)

    def archive(self,base,execution=None,name='joint.zip'):
        path=base/name
        with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            for key,value in self.original.items():archive.writestr(key,value)
            if execution is not None:archive.writestr(models.EXECUTION_FILE,execution)
        return path

    def environment(self,base):
        config=base/'robotd.toml'
        config.write_text(dumps({'policy':{'walk':'none','stand':'none','action_scale':.63,
                                          'head_lowpass':.44,'legs_lowpass':.66,'voltage_adapt':True,
                                          'skill':[{'name':'stand_test','path':'/kept/lb.onnx','duration':2.5}]},
                                 'pad':{'lb':'stand_test'},'audio':{'gain':.37}}))
        calibration=base/'calibration.toml'
        calibration.write_bytes((ROOT/'packaging/hd1910-calibration.robot.toml').read_bytes())
        return config,calibration

    def install(self,archive,base,config,calibration):
        return models.import_package(archive,archive.name,base,config,calibration,
                                     validator=False,target_slot='walk')

    def test_original_joint_zip_keeps_training_settings_without_creating_an_experiment(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);config,calibration=self.environment(base)
            result=self.install(self.archive(base),base,config,calibration)
            self.assertEqual(result['id'],ID)
            directory=base/'models'/ID
            info=models.verify_directory(directory)
            self.assertEqual(info['slot'],'walk')
            self.assertEqual(info['policy_settings'],{'action_scale':1.0,'head_lowpass':1.0,'legs_lowpass':1.0})
            self.assertNotIn('execution_profile',info)
            self.assertNotIn('execution_profile',models.describe_directory(directory))
            self.assertFalse((directory/models.EXECUTION_FILE).exists())
            for name,data in self.original.items():self.assertEqual((directory/name).read_bytes(),data,name)

    def test_import_and_binding_preserve_model_calibration_tuning_lb_and_training_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);config,calibration=self.environment(base)
            saved=tomllib.loads(config.read_text());calibration_bytes=calibration.read_bytes()
            result=self.install(self.archive(base,self.execution),base,config,calibration)
            self.assertEqual(result['execution_profile'],self.profile)
            directory=base/'models'/ID
            self.assertEqual((directory/models.EXECUTION_FILE).read_bytes(),self.execution)
            self.assertEqual(models.verify_directory(directory)['policy_settings'],
                             {'action_scale':1.0,'head_lowpass':1.0,'legs_lowpass':1.0})
            with zipfile.ZipFile(directory/models.EXPORT_DATA) as archive:
                self.assertNotIn(models.EXECUTION_FILE,archive.namelist())
                for name in models.SOURCE_FILES:
                    if name in self.original:self.assertEqual(archive.read(name),self.original[name],name)
            models.assign_model(ID,'walk',base,config,calibration)
            expected=copy.deepcopy(saved);expected['policy']['walk']=str(directory/'policy.onnx')
            self.assertEqual(tomllib.loads(config.read_text()),expected)
            self.assertEqual(config.read_bytes(),config.with_name('robotd.saved.toml').read_bytes())
            self.assertEqual(calibration.read_bytes(),calibration_bytes)
            for name,data in self.original.items():self.assertEqual((directory/name).read_bytes(),data,name)
            row=next(row for row in models.catalog(base,config)['models'] if row['id']==ID)
            self.assertTrue(row['active']);self.assertTrue(row['available'])
            self.assertEqual(row['execution_profile'],self.profile)

    def test_mismatched_model_hash_is_rejected_before_installation(self):
        bad=copy.deepcopy(self.profile);bad['model_sha256']='f'*64
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);config,calibration=self.environment(base);before=config.read_bytes()
            archive=self.archive(base,json.dumps(bad).encode())
            with self.assertRaisesRegex(ValueError,'SHA256'):
                self.install(archive,base,config,calibration)
            self.assertFalse((base/'models').exists());self.assertEqual(config.read_bytes(),before)

    def test_execution_profile_cannot_attach_to_another_task_or_slot(self):
        for task,slot in [(models.ROUGH_TASK,'walk'),(models.ROUGH_STAND_TASK,'stand'),
                          (models.ROUGH_JOINT_TASK,'stand')]:
            with self.subTest(task=task,slot=slot),self.assertRaisesRegex(ValueError,'联合 Walk'):
                models.execution_profile(self.execution,{**self.info,'task':task,'slot':slot})
        for task in ('Mjlab-VelStand-Rough-MicroDuck','Mjlab-VelStand-Rough-Backlash-MicroDuck-Other'):
            with self.subTest(task=task),self.assertRaises(ValueError):models.slot_for(task)

    def test_execution_profile_requires_the_original_unfiltered_scale_one_contract(self):
        for part,key,value in [('actions','scale',.7),('action_filter','enabled',True),
                               ('action_filter','head_alpha',.5),('action_filter','legs_alpha',.7)]:
            info=copy.deepcopy(self.info)
            target=info['contract'][part]['joint_pos'] if part=='actions' else info['contract'][part]
            target[key]=value
            with self.subTest(part=part,key=key),self.assertRaisesRegex(ValueError,'无缩放和滤波'):
                models.execution_profile(self.execution,info)
        info=copy.deepcopy(self.info);info['contract']['action_ema_old_weight']=.2
        with self.assertRaisesRegex(ValueError,'无缩放和滤波'):models.execution_profile(self.execution,info)

    def test_profile_rejects_nonfinite_boolean_and_out_of_range_values(self):
        for key in ('action_scale','head_lowpass','legs_lowpass'):
            for value in (True,False,None,'1',float('nan'),float('inf'),float('-inf'),-1,0,100,10**1000):
                bad=copy.deepcopy(self.profile);bad[key]=value
                with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                    models.execution_profile(json.dumps(bad).encode(),self.info)
        for key,value in [('action_scale',.099999),('action_scale',2.000001),
                          ('head_lowpass',1.000001),('legs_lowpass',1.000001)]:
            bad=copy.deepcopy(self.profile);bad[key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                models.execution_profile(json.dumps(bad).encode(),self.info)

    def test_profile_accepts_bounded_uniform_tuning_including_boundary_values(self):
        for scale,head,legs in ((.1,1.0,1.0),(2.0,.000001,.000001),(.8,.6,.75)):
            value={**self.profile,'action_scale':scale,'head_lowpass':head,'legs_lowpass':legs}
            with self.subTest(scale=scale,head=head,legs=legs):
                self.assertEqual(models.execution_profile(json.dumps(value).encode(),self.info),value)

    def test_profile_requires_exact_uniform_schema_and_rejects_posture_switch_fields(self):
        malformed=[b'[]',b'null',b'{']
        for key in self.profile:
            bad=copy.deepcopy(self.profile);bad.pop(key);malformed.append(json.dumps(bad).encode())
        for key in ('walking','recovery','switch','experimental','unreviewed'):
            bad=copy.deepcopy(self.profile);bad[key]={};malformed.append(json.dumps(bad).encode())
        for key,value in [('mode','joint_walk_recovery'),('mode','other'),('schema','other')]:
            bad=copy.deepcopy(self.profile);bad[key]=value;malformed.append(json.dumps(bad).encode())
        malformed.append(self.execution.rstrip().removesuffix(b'}')+b',"mode":"uniform"}')
        for data in malformed:
            with self.subTest(data=data[:90]),self.assertRaises(ValueError):
                models.execution_profile(data,self.info)

    def test_reimporting_original_training_zip_preserves_the_installed_execution_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);config,calibration=self.environment(base)
            self.install(self.archive(base,self.execution),base,config,calibration)
            directory=base/'models'/ID;before=config.read_bytes()
            result=self.install(self.archive(base,None,'original.zip'),base,config,calibration)
            self.assertTrue(result['duplicate']);self.assertEqual(result['execution_profile'],self.profile)
            models.restore_export_data(directory)
            self.assertEqual((directory/models.EXECUTION_FILE).read_bytes(),self.execution)
            self.assertEqual(models.verify_directory(directory)['execution_profile'],self.profile)
            self.assertEqual(config.read_bytes(),before)

    def test_explicit_valid_sidecar_can_replace_the_same_model_deployment_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);config,calibration=self.environment(base)
            self.install(self.archive(base),base,config,calibration)
            directory=base/'models'/ID
            self.assertFalse((directory/models.EXECUTION_FILE).exists())
            self.install(self.archive(base,self.execution,'configured.zip'),base,config,calibration)
            self.assertEqual((directory/models.EXECUTION_FILE).read_bytes(),self.execution)
            (directory/models.EXECUTION_FILE).write_text('{"schema":"broken"}')
            new_profile={**self.profile,'action_scale':.83,'head_lowpass':.48,'legs_lowpass':.72}
            corrected=json.dumps(new_profile,separators=(',',':')).encode()
            self.install(self.archive(base,corrected,'corrected.zip'),base,config,calibration)
            self.assertEqual((directory/models.EXECUTION_FILE).read_bytes(),corrected)
            self.assertEqual(models.verify_directory(directory)['execution_profile'],new_profile)
            self.install(self.archive(base,None,'original-again.zip'),base,config,calibration)
            self.assertEqual((directory/models.EXECUTION_FILE).read_bytes(),corrected)

    def test_bad_reimport_does_not_modify_a_working_installation(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);config,calibration=self.environment(base)
            self.install(self.archive(base,self.execution),base,config,calibration)
            directory=base/'models'/ID
            before={str(p.relative_to(directory)):p.read_bytes() for p in directory.rglob('*') if p.is_file()}
            bad=copy.deepcopy(self.profile);bad['head_lowpass']=0
            with self.assertRaises(ValueError):
                self.install(self.archive(base,json.dumps(bad).encode(),'bad.zip'),base,config,calibration)
            after={str(p.relative_to(directory)):p.read_bytes() for p in directory.rglob('*') if p.is_file()}
            self.assertEqual(after,before)

    def test_broken_installed_sidecar_is_reported_and_not_silently_dropped_on_reimport(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);config,calibration=self.environment(base)
            self.install(self.archive(base,self.execution),base,config,calibration)
            directory=base/'models'/ID
            bad=copy.deepcopy(self.profile);bad['model_sha256']='0'*64
            raw=json.dumps(bad).encode();(directory/models.EXECUTION_FILE).write_bytes(raw)
            with self.assertRaisesRegex(ValueError,'SHA256'):models.verify_directory(directory)
            row=next(row for row in models.catalog(base,config)['models'] if row['id']==ID)
            self.assertFalse(row['available']);self.assertIn('SHA256',row['error'])
            with self.assertRaisesRegex(ValueError,'SHA256'):
                self.install(self.archive(base,None,'original.zip'),base,config,calibration)
            self.assertEqual((directory/models.EXECUTION_FILE).read_bytes(),raw)

    def test_catalog_reads_small_metadata_without_hashing_or_revalidating_the_onnx(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);config,calibration=self.environment(base)
            self.install(self.archive(base,self.execution),base,config,calibration)
            original=Path.read_bytes
            def small_reads(path):
                if path.name=='policy.onnx':raise AssertionError('catalog rereads model weights')
                return original(path)
            with patch.object(Path,'read_bytes',small_reads),patch.object(models,'validate_export',side_effect=AssertionError('catalog revalidates export')):
                row=next(row for row in models.catalog(base,config)['models'] if row['id']==ID)
            self.assertTrue(row['available']);self.assertEqual(row['execution_profile'],self.profile)


if __name__=='__main__':unittest.main()

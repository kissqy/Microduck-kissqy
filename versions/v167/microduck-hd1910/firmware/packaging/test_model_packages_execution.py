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


class JointExecutionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original={name:(FIXTURE/name).read_bytes()
                      for name in ('policy.onnx',*models.SOURCE_FILES)
                      if (FIXTURE/name).is_file()}
        cls.execution=(FIXTURE/models.EXECUTION_FILE).read_bytes()
        cls.profile=json.loads(cls.execution)
        cls.info=models.validate_export(cls.original)







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







if __name__=='__main__':unittest.main()

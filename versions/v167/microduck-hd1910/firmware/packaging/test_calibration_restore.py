"""Calibration installation and runtime consistency, without a physical robot."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import tomllib
import unittest
from unittest.mock import patch
import math
import runtime
from configure import dumps
from service_control import validate,ControlError
from service_data import adapt_service

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('restore100',ROOT/'rebuild-config.py')
restore=importlib.util.module_from_spec(spec);spec.loader.exec_module(restore)

class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        self.path=self.base/'hd1910-calibration.toml'
        self.seed=tomllib.loads((ROOT/'hd1910-calibration.robot.toml').read_text())
        for name in ('hd1910-calibration.template.toml','hd1910-calibration.robot.toml'):
            (self.base/name).write_bytes((ROOT/name).read_bytes())
    def tearDown(self):self.temp.cleanup()
    def write(self,data):self.path.write_text(dumps(data))
    def test_snapshot_is_exact_current_walk_model_robot_record_not_old_training_zero(self):
        contract=json.loads((ROOT.parent/'policies/walk/deployment-contract.json').read_text())
        self.assertEqual(self.seed,contract['hardware_calibration']['data'])
        self.assertEqual(self.seed['joints'][8]['zero_raw'],1599)
        self.assertEqual(self.seed['joints'][6]['zero_raw'],1742)
    def test_empty_install_and_confirmed_placeholder_imu_restore_known_assembled_values(self):
        for present in (False,True):
            if present:
                template=tomllib.loads((ROOT/'hd1910-calibration.template.toml').read_text())
                template['imu_mount_verified']=True;self.write(template)
            result=restore.prepare_calibration(self.path,self.base)
            self.assertEqual(result,self.seed)
    def test_local_calibration_and_later_mouth_or_imu_edits_survive_reinstall(self):
        data=copy.deepcopy(self.seed);data['joints'][8]['zero_raw']=1620
        data['joints'][9]['max_rad']=math.radians(12)
        data['imu_mount_quat']=[1.,0.,0.,0.];data['motion_enabled']=True
        self.write(data);self.assertEqual(restore.prepare_calibration(self.path,self.base),data)
    def test_partial_local_and_saved_rows_win_before_known_snapshot(self):
        data=copy.deepcopy(self.seed);data['joints'][8]['zero_raw']=1650
        data['joints'][0]['calibrated']=False
        saved=copy.deepcopy(self.seed);saved['joints'][0]['zero_raw']=2050
        restore.saved_path(self.path).write_text(dumps(saved));self.write(data)
        result=restore.prepare_calibration(self.path,self.base)
        self.assertEqual(result['joints'][8]['zero_raw'],1650)
        self.assertEqual(result['joints'][0]['zero_raw'],2050)
    def test_ordinary_recovery_never_reapplies_seed_after_edit(self):
        data=copy.deepcopy(self.seed);data['joints'][8]['zero_raw']=1640
        data['imu_mount_quat']=[1.,0.,0.,0.];self.write(data)
        self.assertEqual(restore.source_data(self.path,'calibration',self.base),data)
    def test_install_preserves_local_unconfirmed_imu_without_upgrade_gate(self):
        data=copy.deepcopy(self.seed);data['imu_mount_verified']=False;data['units_verified']=False
        self.write(data)
        result=restore.prepare_calibration(self.path,self.base)
        self.assertFalse(result['units_verified'])
        self.assertEqual(result['joints'],data['joints'])

    def test_runtime_checks_real_file_path_zero_limits_and_imu(self):
        self.write(self.seed)
        report={'calibration_path':str(self.path),'calibration':self.seed}
        cfg={'bus':{'feetech_calibration':str(self.path)}}
        with patch.object(runtime,'CONFIG',self.base/'robotd.toml'),patch.object(runtime,'config',return_value=cfg),patch.object(runtime,'rpc',return_value=report):
            self.assertTrue(runtime.verify_calibration()['calibration_verified'])
            for mutation in ('path','zero','imu'):
                bad=copy.deepcopy(report)
                if mutation=='path':bad['calibration_path']='/wrong.toml'
                elif mutation=='zero':bad['calibration']['joints'][8]['zero_raw']=568
                else:bad['calibration']['imu_mount_quat']=[1,0,0,0]
                with patch.object(runtime,'rpc',return_value=bad),self.assertRaises(ValueError):runtime.verify_calibration()
    def test_saved_count_does_not_require_a_live_raw_sample(self):
        result={'channels':{'bus':{'status':'live','age_ms':0},'state':{'status':'live'}},'servos':[{'id':r['id'],'name':r['name'],'index':i} for i,r in enumerate(self.seed['joints'])],'imu':{}}
        adapt_service(result,{'mode':'commissioning','build':runtime.BUILD,'phase':'ready'}, {'calibration':self.seed},0)
        self.assertEqual(result['saved_calibrated_count'],15)
        self.assertEqual(result['calibrated_count'],0)
        self.assertFalse(result['pose_calibrated'])

if __name__=='__main__':unittest.main()

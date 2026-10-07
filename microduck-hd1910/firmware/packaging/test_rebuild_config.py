"""Whole configuration recovery, with no UART or real systemd operations."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from configure import atomic_write, dumps

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('rebuild_config',Path(__file__).with_name('rebuild-config.py'))
recovery=importlib.util.module_from_spec(spec);spec.loader.exec_module(recovery)

class RecoveryTests(unittest.TestCase):
    def test_retired_model_references_migrate_without_changing_operator_parameters(self):
        base='/opt/robot/feetech-ft5-r5/models/'
        for old_lb in ('d11f8430712c35cb2416ce3948e9f8b7','388461feb3f4cd24071197ffc30d63e2'):
            with self.subTest(old_lb=old_lb):
                data=tomllib.loads((ROOT/'packaging/robotd-profile.toml').read_text())
                data['policy'].update(custom_only=True,action_scale=.63,head_lowpass=.5,legs_lowpass=.7,walk=base+'5c019c3d3d2c490947f21974f3947506/policy.onnx',stand=base+old_lb+'/policy.onnx')
                skill=next(s for s in data['policy']['skill'] if s['name']=='stand_test')
                skill['path']=base+old_lb+'/policy.onnx';skill['duration_s']=9.0
                source=self.base/'old.toml';source.write_text(dumps(data));output=self.base/'new.toml'
                subprocess.run([sys.executable,str(ROOT/'packaging/configure.py'),'--source',str(source),'--previous-overrides',str(ROOT/'packaging/robotd-profile.toml'),'--overrides',str(ROOT/'packaging/robotd-profile.toml'),'--output',str(output)],check=True,capture_output=True,text=True)
                result=tomllib.loads(output.read_text());policy=result['policy']
                self.assertEqual(policy['stand'],'none');self.assertIn('1cbf8730eadd75a5704332c9f3c10f60',policy['walk'])
                self.assertEqual(policy['action_scale'],.63);self.assertEqual(policy['head_lowpass'],.5);self.assertEqual(policy['legs_lowpass'],.7)
                skill=next(s for s in policy['skill'] if s['name']=='stand_test')
                self.assertIn('a481d9f211f31d9476ab1a319fe362a2',skill['path']);self.assertEqual(skill['duration_s'],9.0);self.assertEqual(skill['params']['action_scale'],1.0)
                self.assertEqual(result['pad'],data['pad']);self.assertEqual(self.cal.read_bytes(),self.raw_cal)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        self.params=self.base/'robotd.toml';self.cal=self.base/'calibration.toml';self.state=self.base/'uart-state.json'
        policy={}
        self.weights={}
        for slot in ('walk','sitstand'):
            directory=self.base/'models'/slot
            shutil.copytree(ROOT/'policies'/slot,directory)
            policy[slot]=str(directory/'policy.onnx');self.weights[directory]=(directory/'policy.onnx').read_bytes()
        self.params.write_text(dumps({'bus':{'port':'/dev/ttyS2','protocol':'feetech','feetech_calibration':str(self.cal)},'control':{'hz':50},'policy':policy}))
        shutil.copyfile(self.params,self.base/'robotd-profile.toml')
        self.raw_cal=Path(__file__).with_name('hd1910-calibration.training.toml').read_bytes()
        (self.base/'hd1910-calibration.training.toml').write_bytes(self.raw_cal);self.cal.write_bytes(self.raw_cal);shutil.copyfile(ROOT/'packaging/hd1910-calibration.template.toml',self.base/'hd1910-calibration.template.toml');recovery.record(self.params,self.cal)
    def tearDown(self):self.temp.cleanup()
    def test_saved_installation_sources_keep_latest_settings_without_rebuilding_models(self):
        data=tomllib.loads(self.cal.read_text());data['joints'][0]['zero_raw']+=7
        self.cal.write_text(dumps(data));recovery.record(self.params,self.cal)
        self.cal.write_bytes(b'');self.params.write_bytes(b'')
        self.assertEqual(recovery.source_data(self.cal,'calibration',self.base),data)
        self.assertEqual(recovery.source_data(self.params,'params',self.base)['policy']['walk'],str(self.base/'models/walk/policy.onnx'))
        for directory,weight in self.weights.items():self.assertEqual((directory/'policy.onnx').read_bytes(),weight)

    def test_atomic_replacement_does_not_truncate_a_symlink_source(self):
        source=self.base/'source.toml';source.write_bytes(self.raw_cal)
        link=self.base/'link.toml';link.symlink_to(source)
        atomic_write(link,source.read_bytes())
        self.assertFalse(link.is_symlink());self.assertEqual(source.read_bytes(),self.raw_cal);self.assertEqual(link.read_bytes(),self.raw_cal)
    def test_service_restart_attempts_once_and_preserves_first_failure(self):
        script=Path(__file__).with_name('service.sh').read_text()
        start=script.index('restart_service() {');end=script.index('\n\non_error()',start)
        function=script[start:end]
        for outcomes,expected in [([0],0),([7,0],7),([1,1],1)]:
            counter=self.base/'count';counter.unlink(missing_ok=True)
            systemctl=self.base/'systemctl'
            systemctl.write_text('#!/usr/bin/env python3\nimport sys\nfrom pathlib import Path\np=Path('+repr(str(counter))+')\nif sys.argv[1]=="restart":\n n=int(p.read_text()) if p.exists() else 0\n p.write_text(str(n+1))\n sys.exit('+repr(outcomes)+'[n])\n')
            systemctl.chmod(0o755)
            journal=self.base/'journalctl';journal.write_text('#!/bin/sh\necho actual-startup-error\n');journal.chmod(0o755)
            result=subprocess.run(['bash','-c',function+'\nrestart_service'],env={**os.environ,'PATH':str(self.base)+':'+os.environ['PATH']},capture_output=True,text=True)
            self.assertEqual(result.returncode,expected);self.assertEqual(int(counter.read_text()),1)

if __name__=='__main__':unittest.main()

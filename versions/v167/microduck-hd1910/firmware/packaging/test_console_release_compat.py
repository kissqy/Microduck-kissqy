"""Check the shipped daemon is recognized by Home and both console version tables."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import shutil
from unittest.mock import patch
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'console'))
import service_data
from management_profile import supports_feature,PROFILE
from service_control import ServiceController,home_feedback
from controls import ControlError
from telemetry import IDS,NAMES

def snapshot():
    return {'mode':'service','service_compatible':True,'capabilities':{'walk':True},
            'health':{'healthy':True},'state':{'joints':[0.0]*15,'t':0},
            'channels':{name:{'status':'live'} for name in ('state','bus','health','capabilities')},
            'service_sample_fresh':True,'calibrated_count':15,
            'bus':{'policy_enabled':False,'build':service_data.BUILD,'mode':'motion','phase':'control','fresh_sample':True,
                   'policy_enabled':False,'homed':True,
                   'native':{'torque_state_confirmed':True,'all_joints_fresh':True,'imu_mount_verified':True}},
            'imu':{'status':'live','gravity':[0,0,-1]},
            'servos':[{'id':ident,'status':'live','calibrated':True,'angle_deg':17.234,'target_deg':17.234} for ident in IDS]}

class ConsoleReleaseTests(unittest.TestCase):
    def test_signed_positions_remain_live_and_angles_are_not_wrapped(self):
        for commissioning in (False, True):
            for position in (-32767, -1670, -1, 0, 4095, 4096, 32767):
                with self.subTest(commissioning=commissioning, position=position):
                    servos=[dict(id=ident,name=name,index=i) for i,(ident,name) in enumerate(zip(IDS,NAMES))]
                    mapping=[dict(id=ident,name=name,zero_raw=1977,direction=-1,calibrated=True,min_rad=-1.5,max_rad=1.5) for ident,name in zip(IDS,NAMES)]
                    angle=-(position-1977)*360/4096
                    samples=[dict(id=ident,joint=name,position_raw=position,position_rad=service_data.math.radians(angle),calibrated=True) for ident,name in zip(IDS,NAMES)]
                    data=dict(channels={'bus':{'status':'live'},'state':{'status':'live'}},state={'targets':[0]*15},servos=servos,imu={})
                    report=dict(mode='commissioning' if commissioning else 'motion',phase='control',updated_at_us=100000,
                                last_sample={'at_us':100000,'servos':samples},native={'sample_age_ms':0,'joints':samples})
                    service_data.adapt_service(data,report,{'calibration':{'joints':mapping}},0)
                    for row in data['servos']:
                        self.assertEqual(row['status'],'live')
                        self.assertEqual(row['position_raw'],position)
                        self.assertAlmostEqual(row['angle_deg'],angle)

    def test_current_daemon_can_request_home_before_arrival(self):
        build=json.loads((ROOT/'BUILD.json').read_text())['build']
        self.assertEqual(service_data.BUILD,build)
        for feature in ('supported','motion','management','coast'):self.assertTrue(supports_feature({'build':build},feature))
        data=snapshot();data['bus']['homed']=False;data['bus']['native']['torque_state_confirmed']=False
        ServiceController._validate_home(data)
        self.assertEqual(home_feedback(data)['phase'],'torque_off')

    def test_javascript_and_python_capabilities_match_for_new_and_legacy_reports(self):
        reports=[{'build':f'{prefix}-feetech-ft6-control.{n}'} for prefix in ('590b986','1fa8438','future') for n in (3,7,9,13,14,18,22,99)]
        reports += [{'build':'unknown','management_capabilities':{'webpad':True}}, {'build':service_data.BUILD,'management_capabilities':{'webpad':False}}]
        script="""import fs from 'node:fs';
const m=await import('data:text/javascript;base64,'+Buffer.from(fs.readFileSync(process.argv[1],'utf8')).toString('base64'));
const [reports,features]=JSON.parse(process.argv[2]);
process.stdout.write(JSON.stringify(reports.map(r=>features.map(f=>m.supportsFeature(r,f)))));"""
        features=PROFILE['features']
        result=subprocess.run(['node','--input-type=module','-e',script,str(ROOT/'console/static/service-builds.js'),json.dumps([reports,features])],capture_output=True,text=True,check=True)
        self.assertEqual(json.loads(result.stdout),[[supports_feature(r,f) for f in features] for r in reports])

    def test_home_arrival_uses_measured_current_targets_and_keeps_error_checks(self):
        data=snapshot();self.assertTrue(home_feedback(data)['ready'])
        data['servos'][0]['angle_deg']+=6
        result=home_feedback(data);self.assertEqual(result['phase'],'target_error');self.assertEqual(result['unreached_ids'],[IDS[0]])
        data=snapshot();data['service_sample_fresh']=False;self.assertEqual(home_feedback(data)['phase'],'waiting_feedback')

    def test_home_request_ramp_arrival_unlocks_walk_and_frontend(self):
        class Store:
            def __init__(self,frames):self.frames=frames;self.events=[];self.service_operation=False
            def snapshot(self):
                if len(self.frames)>1:return self.frames.pop(0)
                return self.frames[0]
            def record_service_command(self,job):self.events.append(copy.deepcopy(job))
        class Transport:
            def __init__(self):self.calls=[]
            def call(self,command):self.calls.append(command);return {'accepted':True}
        off=snapshot();off['bus'].update(homed=False,cycle=1);off['bus']['native']['torque_state_confirmed']=False
        ramp=copy.deepcopy(off);ramp['bus']['cycle']=2;ramp['state']['t']=2;ramp['bus']['native']['torque_state_confirmed']=True
        frames=[copy.deepcopy(off),copy.deepcopy(off),ramp]
        for cycle in (3,3,4,5):
            data=snapshot();data['bus']['cycle']=cycle;data['state']['t']=cycle;frames.append(data)
        store=Store(frames);transport=Transport();controller=ServiceController(store,transport=transport)
        job={'action':'init','status':'running'}
        with patch('service_control.time.sleep',return_value=None):
            result=controller._run_home({'action':'init'},job,0)
        self.assertEqual(transport.calls,[{'action':'init'}])
        self.assertTrue(result['homed']);self.assertEqual(result['confirmed_samples'],3)
        self.assertEqual(result['confirmed_ids'],list(IDS));self.assertEqual(len(store.frames),1)
        ready=store.snapshot()
        self.assertTrue(home_feedback(ready)['ready'])
        self.assertFalse(home_feedback(off)['ready'])

    def test_native_telemetry_adapts_new_build_and_actual_targets(self):
        data=snapshot();data['servos']=[dict(id=ident,index=index,name=name) for index,(ident,name) in enumerate(zip(IDS,NAMES))]
        targets=[index/100 for index in range(15)];data['state']['targets']=targets
        report=copy.deepcopy(data['bus'])
        report['native'].update(sample_age_ms=10,joints=[dict(id=ident,joint=name,position_raw=2048,position_rad=target,calibrated=True) for ident,name,target in zip(IDS,NAMES,targets)])
        service_data.adapt_service(data,report,{},10)
        self.assertTrue(data['service_compatible']);self.assertTrue(data['service_sample_fresh'])
        self.assertTrue(home_feedback(data)['ready'])
        report['native']['joints'][0]['feedback_fresh']=False
        service_data.adapt_service(data,report,{},10)
        self.assertEqual(data['servos'][0]['status'],'stale')
        self.assertTrue(all(row['status']=='live' for row in data['servos'][1:]))
        report['native']['joints'][0]['feedback_fresh']=True
        data['bus']['native']['sample_age_ms']=600
        service_data.adapt_service(data,report,{},10)
        self.assertFalse(data['service_sample_fresh']);self.assertFalse(home_feedback(data)['ready'])

    def test_invalid_imu_and_restarted_daemon_do_not_confirm_home(self):
        data=snapshot();data['imu']['gravity']=[0,0,1]
        with self.assertRaises(ControlError):ServiceController._validate_home(data)
        origin=snapshot();origin['system']={'boot_id':'before'}
        class Store:
            def snapshot(self):
                value=snapshot();value['system']={'boot_id':'after'};return value
        controller=ServiceController(Store(),transport=object())
        with self.assertRaises(ControlError):controller._home_snapshot(0,origin)

if __name__=='__main__':unittest.main()

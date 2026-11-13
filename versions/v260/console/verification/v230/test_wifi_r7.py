import ast
import configparser
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
import uuid

from test_support import FW, PC
sys.path.insert(0,str(FW/'system-repair'))
from microduck_wifi_r7 import WifiStartup,AP_ATTEMPTS

HOME_UUID='12345678-1111-2222-3333-000000000001'
AP_UUID='12345678-1111-2222-3333-000000000002'

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

class Clock:
    def __init__(self):self.now=0
    def monotonic(self):return self.now
    def sleep(self,seconds):self.now+=seconds

class Network:
    def __init__(self,clock,profile):
        self.clock=clock;self.profile=profile;self.calls=[];self.saved=[];self.cached=False
        self.mode='none';self.radio=True;self.unmanaged=False;self.fail_load=False
        self.fail_uuid=False;self.fail_ap=0;self.false_success=False;self.no_ip=False
        self.timeout_list=False;self.home_cost=0;self.home_success=False
    def result(self,out='',err='',code=0):return types.SimpleNamespace(stdout=out,stderr=err,returncode=code)
    def run(self,*argv,wait=30,**kwargs):
        self.calls.append((argv,wait))
        if argv[0]!='nmcli':raise AssertionError(argv)
        if argv[1:]==('radio','wifi','on'):self.radio=True;return self.result()
        if argv[-2:]==('device','status'):
            state='unavailable' if not self.radio else 'unmanaged' if self.unmanaged else 'disconnected'
            return self.result('wlan0:wifi:'+state+'\n')
        if 'WIFI-PROPERTIES.AP' in argv:return self.result('yes\n')
        if 'GENERAL.STATE,GENERAL.CONNECTION,IP4.ADDRESS' in argv:
            name='Microduck-kissqy' if self.mode=='ap' else 'Home' if self.mode=='home' else '--'
            state=100 if self.mode in ('ap','home') else 30
            ip='10.42.0.1/24' if self.mode=='ap' else '192.168.6.151/24' if self.mode=='home' else ''
            return self.result('GENERAL.STATE:%d (state)\nGENERAL.CONNECTION:%s\n%s'%(state,name,'' if self.no_ip or not ip else 'IP4.ADDRESS[1]:'+ip+'\n'))
        if 'GENERAL.CONNECTION' in argv:
            return self.result('Microduck-kissqy' if self.mode=='ap' else 'Home' if self.mode=='home' else '--')
        if 'IP4.ADDRESS' in argv:return self.result('192.168.6.151/24' if self.mode=='home' else '')
        if argv[1:3]==('connection','load'):
            if self.fail_load:return self.result(err='load failed',code=1)
            self.cached=True;return self.result()
        if 'connection.uuid' in argv:
            return self.result('' if self.fail_uuid else AP_UUID if self.profile.exists() and 'uuid='+AP_UUID in self.profile.read_text() else self._profile_uuid())
        if 'connection.id' in argv:return self.result('Home' if argv[-1]==HOME_UUID else 'Microduck-kissqy')
        if argv[-2:]==('connection','show'):
            if self.timeout_list:raise subprocess.TimeoutExpired(argv,wait)
            rows=[(i,'802-11-wireless','Home') for i in self.saved]
            if self.cached:rows.append((self._profile_uuid(),'802-11-wireless','Microduck-kissqy'))
            if 'UUID,TYPE,NAME' in argv:return self.result('\n'.join(':'.join(row) for row in rows))
            if 'UUID,TYPE' in argv:return self.result('\n'.join(':'.join(row[:2]) for row in rows))
        if 'connection' in argv and 'up' in argv:
            start=argv.index('up')+1
            identity=argv[start+1] if argv[start]=='uuid' else argv[start]
            is_ap=identity=='Microduck-kissqy' or identity==self._profile_uuid()
            if not is_ap:
                cost=self.home_cost
                if cost>wait:self.clock.sleep(wait);raise subprocess.TimeoutExpired(argv,wait)
                self.clock.sleep(cost)
                if self.home_success:self.mode='home';return self.result()
                return self.result(err='old Wi-Fi unavailable',code=1)
            if not self.cached:return self.result(err='unknown connection',code=10)
            if self.fail_ap:
                self.fail_ap-=1;return self.result(err='activation failed',code=1)
            if not self.false_success:self.mode='ap'
            return self.result()
        raise AssertionError('unexpected command: '+repr(argv))
    def _profile_uuid(self):
        if not self.profile.is_file():return AP_UUID
        c=configparser.ConfigParser();c.read(self.profile)
        return c.get('connection','uuid',fallback=AP_UUID)
    def ap_ups(self):
        return [c for c,_ in self.calls if 'up' in c and ('Microduck-kissqy' in c or self._profile_uuid() in c)]

def profile(path,psk='owner-password'):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text('[connection]\nid=Microduck-kissqy\nuuid='+AP_UUID+'\ntype=wifi\nautoconnect=false\n\n[wifi]\nmode=ap\nssid=Owner-SSID\n\n[wifi-security]\nkey-mgmt=wpa-psk\npsk='+psk+'\n\n[ipv4]\nmethod=shared\naddress1=10.42.0.1/24\n')
    path.chmod(0o600)

class R7Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.path=self.root/'etc/NetworkManager/system-connections/Microduck-Setup.nmconnection'
        self.clock=Clock();self.nm=Network(self.clock,self.path)
        self.env={'time':self.clock,'run':self.nm.run,'INTERFACE':'auto','AP_NAME':'Microduck-kissqy','SETUP_IP':'10.42.0.1'}
        self.start=WifiStartup(self.env,self.path)
    def tearDown(self):self.temp.cleanup()
    def test_disk_profile_not_cached_is_loaded(self):
        profile(self.path);before=self.path.read_bytes();self.start.activate_hotspot()
        self.assertEqual(self.nm.mode,'ap');self.assertEqual(self.path.read_bytes(),before)
        args=[c for c,_ in self.nm.calls]
        self.assertLess(next(i for i,c in enumerate(args) if c[1:3]==('connection','load')),next(i for i,c in enumerate(args) if 'up' in c))
    def test_missing_profile_created(self):
        self.start.activate_hotspot();self.assertIn('psk=12345678',self.path.read_text())
        self.assertEqual(self.path.stat().st_mode&0o777,0o600)
    def test_owner_password_and_ssid_preserved(self):
        profile(self.path,'owner-secret-keep');before=self.path.read_bytes();self.start.activate_hotspot()
        self.assertEqual(self.path.read_bytes(),before)
    def test_three_ap_failures_then_stop(self):
        profile(self.path);self.nm.fail_ap=9
        self.assertRaises(RuntimeError,self.start.activate_hotspot)
        self.assertEqual(len(self.nm.ap_ups()),3)
    def test_second_attempt_can_recover(self):
        profile(self.path);self.nm.fail_ap=1;self.start.activate_hotspot()
        self.assertEqual(len(self.nm.ap_ups()),2)
    def test_success_command_wrong_state_does_not_pass(self):
        profile(self.path);self.nm.false_success=True
        self.assertRaises(RuntimeError,self.start.activate_hotspot)
        self.assertEqual(len(self.nm.ap_ups()),3)
    def test_success_command_without_ip_does_not_pass(self):
        profile(self.path);self.nm.no_ip=True
        self.assertRaises(RuntimeError,self.start.activate_hotspot)
        self.assertEqual(len(self.nm.ap_ups()),3)
    def test_loading_failure_does_not_activate_stale_connection(self):
        profile(self.path);self.nm.fail_load=True
        self.assertRaises(RuntimeError,self.start.activate_hotspot)
        self.assertEqual(len(self.nm.ap_ups()),0)
    def test_loading_uuid_not_confirmed_does_not_activate(self):
        profile(self.path);self.nm.fail_uuid=True
        self.assertRaises(RuntimeError,self.start.activate_hotspot)
        self.assertEqual(len(self.nm.ap_ups()),0)
    def test_already_active_does_not_reactivate(self):
        profile(self.path);self.nm.mode='ap';self.nm.cached=True;self.start.activate_hotspot()
        self.assertEqual(len(self.nm.ap_ups()),0)
    def test_invalid_profile_not_overwritten(self):
        self.path.parent.mkdir(parents=True);self.path.write_text('not a valid profile');before=self.path.read_bytes()
        self.assertRaises(RuntimeError,self.start.activate_hotspot);self.assertEqual(self.path.read_bytes(),before)
    def test_symlink_profile_rejected(self):
        self.path.parent.mkdir(parents=True);target=self.root/'other';target.write_text('keep')
        self.path.symlink_to(target);self.assertRaises(RuntimeError,self.start.activate_hotspot)
        self.assertEqual(target.read_text(),'keep')
    def test_readiness_wait_stops(self):
        self.nm.unmanaged=True;self.assertRaises(RuntimeError,self.start.activate_hotspot)
        self.assertLessEqual(self.clock.now,60);self.assertEqual(len(self.nm.ap_ups()),0)
    def test_delayed_wireless_enumeration_waits_before_activation(self):
        profile(self.path); original=self.nm.run
        def run(*args,**kwargs):
            if args[-2:]==('device','status') and self.clock.now<3:return self.nm.result('')
            return original(*args,**kwargs)
        self.env['run']=run;self.start.activate_hotspot()
        self.assertGreaterEqual(self.clock.now,3)
        self.assertEqual(self.nm.mode,'ap')
    def test_disabled_software_radio_enabled_once(self):
        profile(self.path);self.nm.radio=False;self.start.activate_hotspot()
        self.assertEqual(sum(c[1:]==('radio','wifi','on') for c,_ in self.nm.calls),1)
    def test_radio_request_error_does_not_hide_ready_interface(self):
        profile(self.path);original=self.nm.run
        def run(*args,**kwargs):
            if args[1:]==('radio','wifi','on'):return self.nm.result(err='radio request failed',code=1)
            return original(*args,**kwargs)
        self.env['run']=run;self.start.activate_hotspot();self.assertEqual(self.nm.mode,'ap')
    def test_radio_request_error_still_bounds_unavailable_interface(self):
        self.nm.radio=False;original=self.nm.run
        def run(*args,**kwargs):
            if args[1:]==('radio','wifi','on'):return self.nm.result(err='radio request failed',code=1)
            return original(*args,**kwargs)
        self.env['run']=run;self.assertRaises(RuntimeError,self.start.activate_hotspot)
        self.assertLessEqual(self.clock.now,60);self.assertEqual(len(self.nm.ap_ups()),0)
    def test_no_saved_profiles_does_not_wait(self):
        self.assertFalse(self.start.wait_for_saved_wifi());self.assertEqual(self.clock.now,0)
    def test_saved_profile_timeout_reaches_ap(self):
        profile(self.path);self.nm.timeout_list=True
        self.assertFalse(self.start.wait_for_saved_wifi());self.nm.timeout_list=False;self.start.activate_hotspot()
        self.assertEqual(self.nm.mode,'ap')
    def test_old_networks_have_total_wait_budget(self):
        self.nm.saved=[HOME_UUID,str(uuid.uuid4()),str(uuid.uuid4()),str(uuid.uuid4())];self.nm.home_cost=18
        self.assertFalse(self.start.wait_for_saved_wifi());self.assertLessEqual(self.clock.now,60)
        names_queries=[c for c,_ in self.nm.calls if 'connection.id' in c]
        self.assertEqual(names_queries,[])
    def test_working_home_is_preserved(self):
        self.nm.mode='home';self.assertTrue(self.start.wait_for_saved_wifi());self.assertEqual(len(self.nm.ap_ups()),0)
    def test_existing_bad_mode_only_permissions_fixed(self):
        profile(self.path);before=self.path.read_bytes();self.path.chmod(0o644);self.start.activate_hotspot()
        self.assertEqual(self.path.read_bytes(),before);self.assertEqual(self.path.stat().st_mode&0o777,0o600)
    def test_no_robot_or_driver_restart_calls(self):
        profile(self.path);self.start.activate_hotspot()
        self.assertTrue(all(c[0]=='nmcli' for c,_ in self.nm.calls))
        self.assertFalse(any('delete' in c or 'down' in c for c,_ in self.nm.calls))

if __name__=='__main__':unittest.main()

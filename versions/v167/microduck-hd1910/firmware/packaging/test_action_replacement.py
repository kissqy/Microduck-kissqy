"""Ordinary upgrades replace the requested actions once without resetting the robot."""
import copy
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest

from configure import dumps

ROOT=Path(__file__).resolve().parents[1]
PROFILE=ROOT/'packaging/robotd-profile.toml'
OLD={'roulade':'8fdaf12c7478a8314a63647a466bfa34',
     'ground_pick':'2b69fa681ed06f7ded9e2a2d12ba5c67'}


class ActionReplacementTests(unittest.TestCase):
    def setUp(self):
        self.defaults=tomllib.loads(PROFILE.read_text())
        self.previous=copy.deepcopy(self.defaults)
        for slot,ident in OLD.items():
            self.previous['policy'][slot]=f'/opt/robot/feetech-ft5-r5/models/{ident}/policy.onnx'

    def configure(self,saved,previous):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);source=base/'saved.toml';prior=base/'previous.toml';out=base/'new.toml'
            source.write_text(dumps(saved));prior.write_text(dumps(previous))
            subprocess.run([sys.executable,str(ROOT/'packaging/configure.py'),
                '--source',str(source),'--previous-overrides',str(prior),
                '--overrides',str(PROFILE),'--output',str(out)],
                check=True,capture_output=True,text=True)
            return tomllib.loads(out.read_text())

    def test_first_replacement_updates_both_paths_and_action_scales_only(self):
        saved=copy.deepcopy(self.previous);policy=saved['policy']
        policy.update(action_scale=.63,head_lowpass=.41,legs_lowpass=.69,
                      voltage_adapt=True,ground_pick_action_scale=.6,ground_pick_gain_ratio=.8)
        roll=next(s for s in policy['skill'] if s['name']=='roulade')
        roll.update(path=policy['roulade'],duration=1.4)
        roll['params'].update(action_scale=.5,gain_ratio=.9)
        result=self.configure(saved,self.previous)
        expected=copy.deepcopy(saved)
        for slot in OLD:expected['policy'][slot]=self.defaults['policy'][slot]
        expected['policy']['ground_pick_action_scale']=1.0
        roll=next(s for s in expected['policy']['skill'] if s['name']=='roulade')
        roll['path']=self.defaults['policy']['roulade'];roll['params']['action_scale']=1.0
        self.assertEqual(result,expected)

    def test_reinstall_preserves_later_operator_bindings_scales_and_timing(self):
        saved=self.configure(self.previous,self.previous)
        saved['policy'].update(roulade='/custom/roll/policy.onnx',
            ground_pick='/custom/pick/policy.onnx',ground_pick_action_scale=.8,ground_pick_period=6.0)
        roll=next(s for s in saved['policy']['skill'] if s['name']=='roulade')
        roll.update(path='/custom/roll/policy.onnx',duration=1.8)
        roll['params']['action_scale']=.9
        self.assertEqual(self.configure(saved,self.defaults),saved)

    def test_interrupted_install_with_new_defaults_and_old_saved_paths_retries_scales(self):
        saved=copy.deepcopy(self.previous)
        saved['policy'].update(action_scale=.63,head_lowpass=.41,legs_lowpass=.69,ground_pick_action_scale=.6)
        roll=next(s for s in saved['policy']['skill'] if s['name']=='roulade')
        roll['path']=saved['policy']['roulade'];roll['params']['action_scale']=.5
        complete=self.configure(saved,self.previous)
        self.assertEqual(self.configure(saved,self.defaults),complete)

    def test_retired_explicit_skill_path_repairs_when_default_has_no_path(self):
        # A saved named roulade path used to raise KeyError during retirement,
        # because the supplied skill resolves its path through policy.roulade.
        saved=copy.deepcopy(self.defaults)
        roll=next(s for s in saved['policy']['skill'] if s['name']=='roulade')
        roll['path']=self.previous['policy']['roulade'];roll['duration']=1.6
        result=self.configure(saved,self.defaults)
        actual=next(s for s in result['policy']['skill'] if s['name']=='roulade')
        self.assertEqual(actual,{**roll,'path':self.defaults['policy']['roulade']})
        self.assertEqual(result['pad'],saved['pad'])

    def test_retired_unknown_skill_and_its_button_are_removed(self):
        saved=copy.deepcopy(self.defaults)
        saved['policy']['skill'].append({'name':'retired-alias','path':self.previous['policy']['roulade'],'duration':1.0})
        saved['pad']['rb']='retired-alias'
        result=self.configure(saved,self.defaults)
        self.assertNotIn('retired-alias',[s['name'] for s in result['policy']['skill']])
        self.assertEqual(result['pad']['rb'],'')
        self.assertEqual(result['policy'],self.defaults['policy'])


if __name__=='__main__':unittest.main()

"""Release retirement integration: migration, on-disk cleanup and old-daemon AI."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest

PC=Path(__file__).resolve().parents[1]
FW=PC.parents[1]/'firmware/Microduck-Robotd-FT6-R17'
sys.path.insert(0,str(PC));sys.path.append(str(FW))
from ai_action_gate import ActionGate,ActionDenied
from configure import dumps
from verification.test_ai_v200 import FakeRobot

MODEL='95d40b584e8c10c9d52dc63cae1c6c97'
PREVIOUS='77ef1f470960bc7eea1fdf5817ff205a'

class ReleaseRetirement(unittest.TestCase):
    def migrate(self,data,previous=None,reset=False):
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp);source=work/'source.toml';out=work/'output.toml'
            source.write_text(dumps(data))
            command=[sys.executable,'-B',str(FW/'configure.py'),'--source',str(source),
                     '--overrides',str(FW/'robotd-profile.toml'),'--output',str(out)]
            if previous is not None:
                path=work/'robotd-profile.toml';path.write_text(dumps(previous))
                command+=['--previous-overrides',str(path)]
            if reset:command+=['--replace-models']
            result=subprocess.run(command,capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(tomllib.loads(source.read_text()),data)
            return tomllib.loads(out.read_text())

    def source(self):
        data=tomllib.loads((FW/'robotd-profile.toml').read_text())
        data['policy']['action_scale']=.83
        data['policy']['custom_setting']=123
        data['policy']['flamingo']='/legacy/other/policy.onnx'
        data['policy']['skill'] += [
            {'name':'flamingo','path':'/operator/custom-one-leg/policy.onnx','duration':6.},
            {'name':'old_one_leg','path':f'/opt/robot/feetech-ft5-r5/models/{PREVIOUS}/policy.onnx','duration':6.},
            {'name':'left_balance','path':f'/opt/robot/feetech-ft5-r5/models/{MODEL}/policy.onnx','duration':6.},
            {'name':'operator_skill','path':'/operator/keep/policy.onnx','duration':2.}]
        data['pad'].update(dpad_up='flamingo',rb='left_balance',x='old_one_leg',lb='operator_skill',mouth_percent=61.)
        return data

    def assert_retired(self,data):
        self.assertNotIn('flamingo',data['policy'])
        self.assertTrue({'flamingo','old_one_leg','left_balance'}.isdisjoint(s['name'] for s in data['policy']['skill']))
        self.assertTrue({'flamingo','old_one_leg','left_balance'}.isdisjoint(v for v in data['pad'].values() if isinstance(v,str)))

    def test_upgrade_removes_saved_skill_aliases_and_only_their_buttons(self):
        data=self.source();new=self.migrate(data,previous=tomllib.loads((FW/'robotd-profile.toml').read_text()))
        self.assert_retired(new)
        self.assertEqual(new['policy']['action_scale'],.83)
        self.assertEqual(new['policy']['custom_setting'],123)
        self.assertIn('operator_skill',[s['name'] for s in new['policy']['skill']])
        self.assertEqual(new['pad']['lb'],'operator_skill')
        self.assertEqual(new['pad']['mouth_percent'],61.)
        self.assertEqual(new['bus'],data['bus'])
        self.assertEqual(new['control'],data['control'])
        self.assertEqual(new['safety'],data['safety'])
        self.assertEqual(new['pad']['dpad_up'],'')
        self.assertEqual(new['pad']['rb'],'kick_right')
        self.assertEqual(new['pad']['x'],'roulade')

    def test_fresh_old_without_skill_and_explicit_reset(self):
        current=tomllib.loads((FW/'robotd-profile.toml').read_text())
        self.assert_retired(self.migrate({}))
        self.assert_retired(self.migrate(self.source(),reset=True))
        self.assertEqual(self.migrate(current)['policy']['skill'],current['policy']['skill'])

    def test_reinstallation_is_idempotent(self):
        previous=tomllib.loads((FW/'robotd-profile.toml').read_text())
        first=self.migrate(self.source(),previous)
        self.assertEqual(self.migrate(first,previous),first)

    def test_orphaned_pad_binding_is_removed_without_a_skill_entry(self):
        data=tomllib.loads((FW/'robotd-profile.toml').read_text())
        data['pad']['rb']='flamingo'
        self.assertEqual(self.migrate(data)['pad']['rb'],'kick_right')

    def test_real_file_installer_removes_retired_model_preserves_user_model(self):
        spec=importlib.util.spec_from_file_location('v260_installer',FW/'install-files.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/'installed';old=dest/'models'/MODEL;old.mkdir(parents=True)
            (old/'policy.onnx').write_bytes(b'retired model')
            user=dest/'models'/'operator-model';user.mkdir()
            (user/'policy.onnx').write_bytes(b'user weights must survive')
            (user/'deployment-contract.json').write_text('{}')
            (dest/'install-files.json').write_text(json.dumps([f'models/{MODEL}/policy.onnx']))
            module.install(FW,dest)
            self.assertFalse(old.exists())
            self.assertEqual((user/'policy.onnx').read_bytes(),b'user weights must survive')
            self.assertEqual(json.loads((dest/'management-profile.json').read_text())['retired_skill_names'],['flamingo'])

    def test_old_daemon_skill_is_not_exposed_or_executed_by_ai(self):
        robot=FakeRobot();gate=robot.gate
        report=copy.deepcopy(robot.skills);report['skills'] += [{'name':'flamingo','duration':6.}]
        gate.set_skills(report)
        self.assertNotIn('flamingo',gate.skills)
        enum=next(d for d in gate.tool_definitions() if d['name']=='perform_skill')['parameters']['properties']['skill']['enum']
        self.assertNotIn('flamingo',enum)
        before=list(robot.calls)
        with self.assertRaises(ActionDenied):gate.execute('perform_skill',{'skill':'flamingo'})
        self.assertNotIn(('robot.do',{'skill':'flamingo'}),robot.calls[len(before):])
        self.assertIn('play_dead',enum)

    def test_removed_model_task_cannot_be_imported(self):
        import model_packages
        with self.assertRaises(ValueError):model_packages.slot_for('Mjlab-FlamingoCycleGentle-Flat-MicroDuck')
        self.assertEqual(model_packages.slot_for('Mjlab-PlayDead-Flat-MicroDuck'),'play_dead')

if __name__=='__main__':unittest.main()

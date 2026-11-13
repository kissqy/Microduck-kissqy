"""Current manual roller recovery deployment and preservation checks."""
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'packaging'))
import model_packages
from configure import dumps

with zipfile.ZipFile(ROOT/'base/Microduck-Console-R17-V162.zip') as archive:
    prefix = archive.namelist()[0].split('/')[0]+'/'
    BASE_CONSOLE = {name[len(prefix):]:archive.read(name) for name in archive.namelist() if name.startswith(prefix) and not name.endswith('/')}
with tarfile.open(fileobj=io.BytesIO(BASE_CONSOLE['updates/Microduck-Robotd-FT6-R17.tar.gz']), mode='r:gz') as archive:
    BASE_FIRMWARE = {row.name.split('/',1)[1]:archive.extractfile(row).read() for row in archive if row.isfile()}

def stand_skill(config):
    skills = [s for s in config['policy']['skill'] if s['name']=='roller_stand']
    assert len(skills)==1
    return skills[0]

class ManualRollerTests(unittest.TestCase):
    def configure(self, old=None, previous=None):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            args = [sys.executable, str(ROOT/'packaging/configure.py'), '--overrides', str(ROOT/'packaging/robotd-profile.toml'), '--output', str(temp/'result.toml')]
            if old is not None:
                (temp/'saved.toml').write_text(dumps(old)); args += ['--source', str(temp/'saved.toml')]
            if previous is not None:
                (temp/'previous.toml').write_bytes(previous); args += ['--previous-overrides', str(temp/'previous.toml')]
            subprocess.run(args, check=True, capture_output=True, text=True)
            return tomllib.loads((temp/'result.toml').read_text())

    def test_fresh_install_has_one_finite_zero_command_skill(self):
        config = self.configure()
        skill = stand_skill(config)
        self.assertEqual(skill['path'], '/opt/robot/feetech-ft5-r5/roller/standup/policy.onnx')
        self.assertEqual((skill['duration'],skill['chain'],skill['unwind_s']), (5.0,False,0.0))
        self.assertEqual(skill['command'], [0,0,0]); self.assertEqual(skill['unwind'], [0,0,0])
        self.assertEqual(skill['params']['action_scale'], 1.0)
        self.assertEqual(config['pad']['lb'], 'kick_left')

    def test_upgrade_preserves_saved_parameters_and_adds_new_skill(self):
        old = tomllib.loads(BASE_FIRMWARE['robotd-profile.toml'].decode())
        old['policy'].update(action_scale=.63, gain_ratio=.74, head_lowpass=.32, legs_lowpass=.61)
        old['pad']['x'] = 'roulade'
        config = self.configure(old, BASE_FIRMWARE['robotd-profile.toml'])
        stand_skill(config)
        for key in ('action_scale','gain_ratio','head_lowpass','legs_lowpass'):
            self.assertEqual(config['policy'][key], old['policy'][key])
        self.assertEqual(config['pad'], old['pad'])
        self.assertNotIn('stand_test', [s['name'] for s in config['policy']['skill']])

    def test_custom_only_upgrade_keeps_user_skills_and_reinstall_is_idempotent(self):
        old = tomllib.loads(BASE_FIRMWARE['robotd-profile.toml'].decode())
        custom = {'name':'operator_skill','path':'/opt/robot/operator.onnx','duration':1.2,'chain':False,'params':{'action_scale':.64}}
        old['policy']['custom_only'] = True
        old['policy']['skill'].append(custom)
        config = self.configure(old, BASE_FIRMWARE['robotd-profile.toml'])
        self.assertIn(custom, config['policy']['skill']); stand_skill(config)
        again = self.configure(config, (ROOT/'packaging/robotd-profile.toml').read_bytes())
        self.assertEqual(again, config)

    def test_original_export_bytes_and_all_coefficients_are_preserved(self):
        for name, raw in BASE_FIRMWARE.items():
            if name.startswith(('models/','roller/')):
                self.assertEqual((ROOT/'packaging'/name).read_bytes(), raw, name)
        catalog = model_packages.catalog(ROOT/'packaging', ROOT/'packaging/robotd-profile.toml')
        rollers = {r['id']:r for r in catalog['roller_models']}
        self.assertEqual(set(rollers), {'swizzle','crouch','spin','standup'})
        for name,row in rollers.items():
            self.assertTrue(row['available'])
            self.assertEqual((row['action_scale'],row['head_lowpass'],row['legs_lowpass']), (.8,.5,.7) if name=='crouch' else (1.,1.,1.))
        self.assertEqual(rollers['standup']['trigger'], 'L3')
        self.assertEqual(rollers['standup']['test_duration_s'], 5.0)
        original = json.loads((ROOT/'packaging/roller/standup/deployment-contract.json').read_text())
        self.assertIsNone(original['slot']); self.assertIsNone(original['required_skill_settings'])

    def test_native_service_configuration_and_ssh_paths_are_preserved(self):
        for name in ('configure.py','service.sh','management-profile.json','install-files.json','robot-calibration-source.json','hd1910-calibration.robot.toml','hd1910-calibration.training.toml'):
            self.assertEqual((ROOT/'packaging'/name).read_bytes(), BASE_FIRMWARE[name], name)
        for name in ('start.cmd','controls.py','remote_input.py','static/control.js','static/webpad-controls.js','firmware_packages.py'):
            self.assertEqual((ROOT/'console'/name).read_bytes(), BASE_CONSOLE[name], name)

    def test_web_l3_remains_display_only(self):
        class Buttons(HTMLParser):
            l3 = []
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag=='button' and attrs.get('data-button')=='ls': self.l3.append(attrs)
        parser = Buttons(); html = (ROOT/'console/static/index.html').read_text(); parser.feed(html)
        # The native layout has a decorative L3 node, and web input stays disabled.
        self.assertIn('data-unavailable="true"', html)
        self.assertIn('仅实体手柄：滑轮模式且 IMU 确认倒地时，按 L3 测试起身 5 秒', html)
        self.assertEqual(len(parser.l3), 1)
        for button in parser.l3: self.assertEqual(button.get('data-unavailable'), 'true')
        self.assertNotIn('当前未绑定按键', html)

if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ManualRollerTests)
    log = io.StringIO()
    result = unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    target = ROOT/'verification/v163'; target.mkdir(parents=True,exist_ok=True)
    (target/'python-tests.log').write_text(log.getvalue())
    (target/'python-tests.json').write_text(json.dumps({'passed':result.testsRun-len(result.failures)-len(result.errors), 'failed':len(result.failures)+len(result.errors), 'hardware_tested':False, 'scope':'manual L3 config; upgrade/reinstall and custom settings; original exports and coefficients; unchanged service, SSH and web input'},ensure_ascii=False,indent=2)+'\n')
    print(log.getvalue(),end='')
    sys.exit(0 if result.wasSuccessful() else 1)

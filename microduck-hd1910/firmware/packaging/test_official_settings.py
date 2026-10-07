"""Retired R17 settings must disappear from both startup copies and imports."""
import copy, hashlib, importlib.util, json, subprocess, sys, tempfile, tomllib, unittest
from pathlib import Path
from unittest.mock import patch
import configure, model_packages, runtime

ROOT = Path(__file__).resolve().parents[1]
PROFILE = json.loads((ROOT/'config/r17-management.json').read_text())
RETIRED = {'head_lowpass', 'legs_lowpass', 'voltage_adapt'}
SAVE_BLOCK = (ROOT/'packaging/service.sh').read_text().split("<<'PYPARAMS'\n", 1)[1].split('\nPYPARAMS', 1)[0]
spec = importlib.util.spec_from_file_location('settings_recovery', ROOT/'packaging/rebuild-config.py')
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


class OfficialSettingsTests(unittest.TestCase):
    def derive(self, base, previous):
        subprocess.run([sys.executable, str(ROOT/'packaging/configure.py'),
                        '--source', str(base/'source.toml'), '--previous-overrides', str(previous),
                        '--overrides', str(ROOT/'packaging/robotd-profile.toml'),
                        '--output', str(base/'new.toml')], check=True, capture_output=True)
        return tomllib.loads((base/'new.toml').read_text())

    def fixture(self, base, profile):
        previous = base/'robotd-profile.toml'
        previous.write_bytes((ROOT/'packaging/robotd-profile.toml').read_bytes())
        (base/'management-profile.json').write_text(json.dumps(profile))
        policy = {'custom_only': True, 'walk': str(ROOT/'policies/walk/policy.onnx'),
                  'sitstand': 'none', 'stand': 'none', 'ground_pick': 'none', 'roulade': 'none',
                  'action_scale': .63, 'head_lowpass': 1.0, 'legs_lowpass': 1.0,
                  'voltage_adapt': False, 'gain': 5, 'standing_gain_ratio': .82}
        (base/'source.toml').write_text(configure.dumps({'policy': policy, 'audio': {'gain': .4}}))
        return policy, previous

    def test_legacy_overrides_removed_and_both_startup_copies_recover_without_them(self):
        for version, voltage in (('1.0.126', False), ('1.0.127', True), ('1.0.128', True)):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as t:
                base = Path(t)
                old = copy.deepcopy(PROFILE)
                old['defaults']['policy'].update(head_lowpass=.5, legs_lowpass=.7, voltage_adapt=voltage)
                saved, previous = self.fixture(base, old)
                got = self.derive(base, previous)
                self.assertTrue(RETIRED.isdisjoint(got['policy']))
                for key, value in saved.items():
                    if key not in RETIRED:
                        self.assertEqual(got['policy'][key], value)
                self.assertEqual(got['audio']['gain'], .4)
                (base/'management-profile.json').write_text(json.dumps(PROFILE))
                with patch.object(sys, 'argv', ['save', str(base/'new.toml'), str(base/'robotd.toml'), str(base)]):
                    exec(compile(SAVE_BLOCK, 'service.sh:PYPARAMS', 'exec'), {})
                self.assertEqual((base/'robotd.toml').read_bytes(), (base/'robotd.saved.toml').read_bytes())
                (base/'robotd.toml').unlink()
                recovered = recovery.source_data(base/'robotd.toml', 'params', base)
                self.assertTrue(RETIRED.isdisjoint(recovered['policy']))
                self.assertEqual(recovered['policy']['action_scale'], .63)
                self.assertEqual(json.loads((base/'management-profile.json').read_text()), PROFILE)

    def test_current_descriptor_does_not_override_explicit_native_configuration(self):
        with tempfile.TemporaryDirectory() as t:
            base = Path(t)
            saved, previous = self.fixture(base, PROFILE)
            got = self.derive(base, previous)
            self.assertEqual(got['policy'], {**tomllib.loads(previous.read_text())['policy'], **saved})

    def test_repeated_upgrade_leaves_native_fields_absent(self):
        with tempfile.TemporaryDirectory() as t:
            base = Path(t)
            _, previous = self.fixture(base, PROFILE)
            data = tomllib.loads((base/'source.toml').read_text())
            for key in RETIRED:
                data['policy'].pop(key)
            (base/'source.toml').write_text(configure.dumps(data))
            for _ in range(2):
                got = self.derive(base, previous)
                self.assertTrue(RETIRED.isdisjoint(got['policy']))
                self.assertEqual(got['policy']['action_scale'], .63)
                (base/'source.toml').write_bytes((base/'new.toml').read_bytes())

    def test_fresh_profile_and_descriptor_leave_native_settings_unset(self):
        self.assertEqual(PROFILE['defaults']['policy'], {'action_scale': .7})
        for path in ('packaging/robotd-profile.toml', 'config/robotd-selftrained.toml'):
            self.assertTrue(RETIRED.isdisjoint(tomllib.loads((ROOT/path).read_text())['policy']))
        self.assertNotIn('requested_policy_restore', PROFILE)
        self.assertNotIn('applied_policy_restore', PROFILE)

    def test_model_binding_does_not_materialize_filter_or_voltage_parameters(self):
        with tempfile.TemporaryDirectory() as t:
            base = Path(t)
            cfg = base/'robotd.toml'
            cal = base/'calibration.toml'
            cal.write_bytes((ROOT/'packaging/hd1910-calibration.robot.toml').read_bytes())
            cfg.write_text(configure.dumps({'policy': {'custom_only': True, 'action_scale': .63}}))
            info = model_packages.verify_directory(ROOT/'policies/walk')
            with patch.object(model_packages, 'verify_directory', return_value=info):
                model_packages.assign_model(info['id'], 'walk', base, cfg, cal)
            got = tomllib.loads(cfg.read_text())['policy']
            self.assertTrue(RETIRED.isdisjoint(got))
            self.assertEqual(got['action_scale'], .63)
            self.assertEqual(cfg.read_bytes(), cfg.with_name('robotd.saved.toml').read_bytes())

    def test_native_voltage_or_filter_readback_is_not_an_r17_acceptance_gate(self):
        path = ROOT/'policies/walk/policy.onnx'
        data = {'policy': {'walk': str(path), 'action_scale': .63}}
        bus = {'build': runtime.BUILD, 'loaded_models': {'walk': {'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}},
               'action_scale': .63, 'head_lowpass': .5, 'legs_lowpass': .7, 'voltage_adapt': True}
        with patch.object(runtime, 'config', return_value=data), patch.object(runtime, 'rpc', return_value=bus):
            self.assertTrue(runtime.verify_loaded_models()['loaded_models_verified'])
            bus.update(head_lowpass=1.0, legs_lowpass=1.0, voltage_adapt=False)
            result = runtime.verify_loaded_models()
            self.assertEqual(result['head_lowpass'], 1.0)
            self.assertTrue(result['loaded_models_verified'])


if __name__ == '__main__':
    unittest.main()

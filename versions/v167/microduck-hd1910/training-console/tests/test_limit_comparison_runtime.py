"""Portable numerical and orchestration checks; these are not physics rollouts."""
import copy
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace, ModuleType
from dataclasses import dataclass
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from training import limit_comparison as comparison
from training import target_limit_actions as mapping
from training import runtime_adapter
from training.target_limit_profile import POLICY_IDS, SCHEMA


def profile(sha='a' * 64):
    rows = [{'name': name, 'id': servo, 'min_rad': math.radians(-22),
             'max_rad': math.radians(22), 'zero_raw': 2176 if servo == 21 else 2048,
             'direction': -1 if servo == 21 else 1}
            for name, servo in POLICY_IDS.items()]
    return {'schema': SCHEMA, 'model_sha256': sha,
            'task': 'Mjlab-StandUp-Rough-Backlash-MicroDuck', 'joints': rows,
            'seed': 20261007,
            'recording': {'created_at': 1.0, 'source_name': 'real.json',
                          'source_sha256': 'b' * 64, 'frame_count': 10,
                          'active_frames': 10, 'build': 'test'},
            'runtime': {'base_action_scale': 1.0, 'effective_action_scale_min': .96,
                        'effective_action_scale_max': .97, 'head_alpha': 1.0,
                        'legs_alpha': 1.0, 'voltage_adapt': True}}


def fingerprint(value='same'):
    return {'sha256': value, 'components': {'integrator': value, 'actuators': value,
                                         'action_history': value, 'rng': value}}


def group(label, state='same'):
    return {'label': label, 'status': 'passed', 'steps': 60, 'elapsed_s': 1.2,
            'max_roll_deg': 100.0, 'reached_side': True, 'joint21_clamp_steps': 0,
            'clamp_joint_steps': 0, 'stand': {'result': 'passed'}, 'trace': [],
            'initial_fingerprint': fingerprint(state), 'error': None,
            'initial_state_mismatches': []}


class TargetMappingTests(unittest.TestCase):
    def test_action_hook_preserves_raw_and_unclipped_ema_history(self):
        # Run the actual new action subclass against a tiny documented base
        # action contract. This is a pipeline unit test, not a mjlab rollout.
        class Tensor:
            def __init__(self, values): self.values = copy.deepcopy(values)
            @property
            def shape(self): return (len(self.values), len(self.values[0]))
            device = 'cpu'
            dtype = 'float32'
            def __getitem__(self, index): return Tensor(self.values[index])
            def __setitem__(self, index, value): self.values[index] = copy.deepcopy(value.values)
            def detach(self): return self
            def cpu(self): return self
            def tolist(self): return copy.deepcopy(self.values)
        @dataclass(kw_only=True)
        class BaseCfg:
            head_alpha: float = .5
            legs_alpha: float = .5
        class Base:
            def __init__(self, cfg, env):
                self.cfg = cfg
                self.target_names = list(POLICY_IDS)
                self._processed_actions = Tensor([[0.] * 14])
                self.previous_filtered = None
                self.raw_actions = None
            def process_actions(self, actions):
                self.raw_actions = actions.tolist()
                target = actions.tolist()[0]
                if self.previous_filtered is not None:
                    target = [.5 * value + .5 * old for value, old in zip(target, self.previous_filtered)]
                self.previous_filtered = target[:]
                self._processed_actions = Tensor([target])
            def reset(self, ids=None): self.previous_filtered = None
        filtered = ModuleType('training.filtered_actions')
        filtered.FilteredJointPositionAction = Base
        filtered.FilteredJointPositionActionCfg = BaseCfg
        torch = ModuleType('torch')
        torch.as_tensor = lambda values, **kwargs: Tensor(values)
        old = mapping._ACTION_CLASSES
        mapping._ACTION_CLASSES = None
        try:
            with patch.dict(sys.modules, {'torch': torch, 'training.filtered_actions': filtered}):
                cfg_class, action_class = mapping._action_classes()
                p = profile()
                index = list(POLICY_IDS).index('left_hip_roll')
                raw = [0.] * 14
                raw[index] = math.radians(-50)
                a = action_class(cfg_class(limit_profile=p, limit_enabled=False), None)
                b = action_class(cfg_class(limit_profile=p, limit_enabled=True), None)
                a.process_actions(Tensor([raw]))
                b.process_actions(Tensor([raw]))
                self.assertEqual(a.raw_actions, b.raw_actions)
                self.assertEqual(a.previous_filtered, b.previous_filtered)
                self.assertEqual(a._processed_actions.values[0][index], raw[index])
                self.assertAlmostEqual(math.degrees(b._processed_actions.values[0][index]), -21.97265625)
                b.process_actions(Tensor([[0.] * 14]))
                self.assertAlmostEqual(math.degrees(b.previous_filtered[index]), -25)
                self.assertAlmostEqual(math.degrees(b._processed_actions.values[0][index]), -21.97265625)
        finally:
            mapping._ACTION_CLASSES = old

    def test_real_id21_calibration_encoder_roundtrip_and_no_a_change(self):
        joint = next(row for row in profile()['joints'] if row['id'] == 21)
        target = math.radians(-50)
        original = mapping.map_target(target, joint, enabled=False)
        limited = mapping.map_target(target, joint, enabled=True)
        self.assertEqual(original['target_applied_rad'], target)
        self.assertFalse(original['calibration_clipped'])
        self.assertTrue(original['would_calibration_clip'])
        self.assertEqual(limited['encoder_raw'], 2426)
        self.assertAlmostEqual(math.degrees(limited['target_applied_rad']), -21.97265625)
        self.assertTrue(limited['calibration_clipped'])

    def test_pi_is_clipped_not_wrapped_and_stages_remain_visible(self):
        joint = profile()['joints'][0]
        result = mapping.map_target(4 * math.pi, joint, enabled=True)
        self.assertEqual(result['safety_target_rad'], math.pi)
        self.assertTrue(result['safety_clipped'])
        self.assertTrue(result['calibration_clipped'])
        self.assertGreater(result['target_applied_rad'], 0)

    def test_rust_round_ties_and_no_encoder_wrap(self):
        self.assertEqual([mapping.round_away(x) for x in (.5, 1.5, 2.5, -.5, -2.5)],
                         [1, 2, 3, -1, -3])
        joint = dict(profile()['joints'][0], zero_raw=4095, max_rad=1.)
        with self.assertRaisesRegex(ValueError, '0..4095'):
            mapping.map_target(.5, joint, enabled=True)

    def test_roundtrip_may_exceed_endpoint_without_second_clip(self):
        endpoint = 10.6 * math.tau / 4096
        joint = dict(profile()['joints'][0], max_rad=endpoint)
        result = mapping.map_target(1., joint, enabled=True)
        self.assertEqual(result['encoder_raw'], 2059)
        self.assertGreater(result['target_applied_rad'], endpoint)
        self.assertLessEqual(result['target_applied_rad'] - endpoint, math.pi / 4096)

    def test_names_resolve_independent_of_profile_row_order(self):
        p = profile()
        names = list(reversed(POLICY_IDS))
        p['joints'] = list(reversed(p['joints']))
        result = mapping.map_targets([math.radians(-50)] * 14, names, p, enabled=True)
        index = names.index('left_hip_roll')
        self.assertEqual(result[index]['encoder_raw'], 2426)
        with self.assertRaises(ValueError):
            mapping.map_targets([0.] * 14, ['left_hip_roll'] * 14, p, enabled=True)

    def test_encoder_actuals_sum_named_backlash_and_bias(self):
        names = list(POLICY_IDS)
        all_names = list(reversed(names)) + ['passive_' + name + '_backlash' for name in names]
        motor, output, encoder, bias = comparison.actual_joint_positions(
            names, all_names, [.1] * 14 + [.02] * 14, [.003] * 28,
            backlash_expected=True)
        for index in range(14):
            self.assertAlmostEqual(motor[index], .1)
            self.assertAlmostEqual(output[index], .12)
            self.assertAlmostEqual(encoder[index], .123)
            self.assertAlmostEqual(bias[index], .003)
        with self.assertRaisesRegex(ValueError, '配对不完整'):
            comparison.actual_joint_positions(names, all_names[:-1], [.1] * 27,
                                               [.003] * 27, backlash_expected=True)

    def test_vertical_pose_is_not_false_side_crossing(self):
        self.assertEqual(comparison.roll_degrees([0., 0., -1.]), (0., False))
        self.assertEqual(comparison.roll_degrees([-1., 0., 0.]), (0., False))
        angle, reached = comparison.roll_degrees([.5, math.sqrt(.75), 0.])
        self.assertAlmostEqual(angle, 120)
        self.assertTrue(reached)
        self.assertFalse(comparison.roll_degrees([.01, 0., -.99995])[1])


class ComparisonOrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'policy.onnx'
        self.path.write_bytes(b'fixture policy bytes; mocked inference')
        digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.req = {'op': 'onnx', 'engine': 'official_0151',
                    'task': 'Mjlab-StandUp-Rough-Backlash-MicroDuck',
                    'onnx_path': str(self.path), 'onnx_sha256': digest,
                    'target_limit_comparison': profile(digest)}
        self.events = []

    def tearDown(self):
        self.temp.cleanup()

    def emit(self, name, **payload):
        self.events.append((name, payload))

    def test_automatic_a_then_b_with_same_profile_and_exact_fingerprint(self):
        calls = []
        def evaluate(req, p, label, emit, expected=None, **kwargs):
            calls.append((label, p['seed'], expected))
            return group(label)
        with patch.object(comparison, '_configure_backends'), patch.object(comparison, '_run_group', evaluate):
            result = comparison.run(self.req, self.emit)
        self.assertEqual([call[0] for call in calls], ['A', 'B'])
        self.assertEqual(calls[0][1], calls[1][1])
        self.assertIsNone(calls[0][2])
        self.assertEqual(calls[1][2], fingerprint())
        self.assertTrue(result['valid'])
        self.assertTrue(result['initial_state_equal'])
        self.assertFalse(result['mechanical_limits_changed'])
        self.assertFalse(result['voltage_compensation_enabled'])
        self.assertEqual([x[0] for x in self.events].count('limit_comparison_result'), 1)

    def test_physics_history_difference_invalidates_comparison(self):
        def evaluate(req, p, label, emit, expected=None, **kwargs):
            return group(label, 'same' if label == 'A' else 'different')
        with patch.object(comparison, '_configure_backends'), patch.object(comparison, '_run_group', evaluate):
            result = comparison.run(self.req, self.emit)
        self.assertFalse(result['valid'])
        self.assertFalse(result['initial_state_equal'])
        self.assertIn('actuators', result['initial_state_mismatches'])

    def test_b_initialization_error_is_preserved_as_unrun_group(self):
        def evaluate(req, p, label, emit, expected=None, **kwargs):
            if label == 'B':
                raise RuntimeError('B initialization fixture')
            return group(label)
        with patch.object(comparison, '_configure_backends'), patch.object(comparison, '_run_group', evaluate):
            result = comparison.run(self.req, self.emit)
        self.assertFalse(result['valid'])
        self.assertEqual(result['error'], 'B initialization fixture')
        self.assertEqual([item['label'] for item in result['groups']], ['A', 'B'])
        b = result['groups'][1]
        self.assertEqual((b['status'], b['steps'], b['elapsed_s']), ('error', 0, 0.))
        self.assertEqual(b['trace'], [])
        self.assertEqual(b['error'], result['error'])

    def test_model_replacement_between_a_and_b_rejected(self):
        calls = []
        def evaluate(req, p, label, emit, expected=None, **kwargs):
            calls.append(label)
            self.path.write_bytes(b'replaced')
            return group(label)
        with patch.object(comparison, '_configure_backends'), patch.object(comparison, '_run_group', evaluate):
            result = comparison.run(self.req, self.emit)
        self.assertEqual(calls, ['A'])
        self.assertFalse(result['valid'])
        self.assertIn('ONNX', result['error'])

    def test_runtime_rechecks_actual_bytes_and_non_onnx_is_rejected(self):
        self.path.write_bytes(b'changed before run')
        with self.assertRaisesRegex(ValueError, 'ONNX'):
            comparison.run(self.req, self.emit)
        for op in ('train', 'export', 'play', 'preview', 'describe'):
            with self.assertRaisesRegex(ValueError, 'ONNX'):
                runtime_adapter.main({'op': op, 'target_limit_comparison': None})

    def test_none_profile_never_falls_back_to_ordinary_viewer(self):
        request = dict(self.req, target_limit_comparison=None)
        with patch.object(comparison, 'run', return_value='checked') as run:
            self.assertEqual(runtime_adapter.onnx(request), 'checked')
            run.assert_called_once()

    def test_mismatched_start_stops_before_policy_action_and_closes_env(self):
        p = self.req['target_limit_comparison']
        raw = SimpleNamespace(reward_manager=SimpleNamespace(get_term_cfg=lambda _: SimpleNamespace(params={'target_height': .115})))
        closed = []
        env = SimpleNamespace(unwrapped=raw, close=lambda: closed.append(True))
        action = {'scale': 1., 'filter': {'head_alpha': 1., 'legs_alpha': 1.}}
        def forbidden(*args):
            raise AssertionError('B must not take an action with unequal initial state')
        with patch.object(comparison, '_build_group', return_value=(env, forbidden, {}, action)), \
             patch.object(comparison, 'startup_fingerprint', return_value=fingerprint('other')):
            result = comparison._run_group(self.req, p, 'B', self.emit, fingerprint())
        self.assertEqual(result['status'], 'invalid')
        self.assertEqual(result['steps'], 0)
        self.assertEqual(result['trace'], [])
        self.assertEqual(closed, [True])

    def test_unexpected_auto_reset_pose_cannot_be_recorded_as_success(self):
        p = self.req['target_limit_comparison']
        raw = SimpleNamespace(reward_manager=SimpleNamespace(get_term_cfg=lambda _: SimpleNamespace(params={'target_height': .115})),
                              step_dt=.02, reset_terminated=[False], reset_time_outs=[True],
                              cfg=SimpleNamespace(auto_reset=True))
        closed = []
        env = SimpleNamespace(unwrapped=raw, close=lambda: closed.append(True),
                              step=lambda action: ({}, None, [True], {}))
        action = {'scale': 1., 'filter': {'head_alpha': 1., 'legs_alpha': 1.}}
        with patch.object(comparison, '_build_group', return_value=(env, lambda obs: [0.] * 14, {}, action)), \
             patch.object(comparison, 'startup_fingerprint', return_value=fingerprint()), \
             patch.object(comparison, '_trace_frame', side_effect=AssertionError('post-reset pose must not be read')):
            result = comparison._run_group(self.req, p, 'A', self.emit)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['steps'], 1)
        self.assertEqual(result['trace'], [])
        self.assertEqual(closed, [True])


def numeric_field(values, *, shape=None, dtype='float32', kind='f'):
    return {'values': list(values), 'shape': [len(values)] if shape is None else shape,
            'dtype': dtype, 'kind': kind, 'source_type': 'test.numeric_array',
            'sha256': hashlib.sha256(repr(values).encode()).hexdigest()}


def numeric_fixture():
    return {
        'integrator': {'state.qpos': numeric_field([.04, 0., 1.]),
                       'state.qvel': numeric_field([0., 0., 0.]),
                       'state.qacc': numeric_field([9.8, 0., 0.]),
                       'state.qacc_warmstart': numeric_field([0., 0., 0.])},
        'live_physics': {'state.body_mass': numeric_field([.02, .82]),
                         'state.body_inertia': numeric_field([1e-5, 2e-5, 3e-5]),
                         'state.jnt_range': numeric_field([-.384, .384])},
    }


def numeric_fingerprint(values):
    return {'components': {**{name: hashlib.sha256(repr(fields).encode()).hexdigest()
                              for name, fields in values.items()},
                           'actuators': 'unchanged', 'rng': 'unchanged'}, 'sha256': 'diagnostic'}


class NumericStateComparisonTests(unittest.TestCase):
    def compare(self, a, b):
        return comparison.compare_initial_states(numeric_fingerprint(a), numeric_fingerprint(b), a, b)

    def test_signed_zero_and_small_roundoff_pass_with_explicit_numbers(self):
        a, b = numeric_fixture(), numeric_fixture()
        b['integrator']['state.qvel'] = numeric_field([-0., 1e-9, 0.])
        b['integrator']['state.qpos'] = numeric_field([.04000001, 0., 1.])
        b['live_physics']['state.body_mass'] = numeric_field([.02000001, .82])
        result = self.compare(a, b)
        self.assertTrue(result['passed'])
        self.assertFalse(result['exact'])
        qpos = next(row for row in result['fields'] if row['field'] == 'qpos')
        self.assertAlmostEqual(qpos['max_abs_diff'], 1e-8)
        self.assertEqual((qpos['atol'], qpos['rtol']), (1e-7, 1e-6))
        self.assertEqual(qpos['reason'], 'within_tolerance')

    def test_real_pose_mass_and_joint_range_changes_are_rejected(self):
        for component, field, changed in (
            ('integrator', 'state.qpos', [.045, 0., 1.]),
            ('live_physics', 'state.body_mass', [.021, .82]),
            ('live_physics', 'state.jnt_range', [-.4, .4]),
        ):
            with self.subTest(field=field):
                a, b = numeric_fixture(), numeric_fixture()
                b[component][field] = numeric_field(changed)
                result = self.compare(a, b)
                self.assertFalse(result['passed'])
                self.assertEqual(result['differences'][0]['field'], field.removeprefix('state.'))

    def test_one_percent_of_tiny_inertia_is_not_swallowed_by_atol(self):
        a, b = numeric_fixture(), numeric_fixture()
        b['live_physics']['state.body_inertia'] = numeric_field([1.01e-5, 2e-5, 3e-5])
        result = self.compare(a, b)
        self.assertFalse(result['passed'])
        item = result['differences'][0]
        self.assertEqual(item['field'], 'body_inertia')
        self.assertEqual((item['atol'], item['rtol']), (1e-10, 2e-6))

    def test_qacc_is_diagnostic_but_exact_warmstart_name_remains_a_gate(self):
        a, b = numeric_fixture(), numeric_fixture()
        b['integrator']['state.qacc'] = numeric_field([12., 0., 0.])
        check = self.compare(a, b)
        self.assertTrue(check['passed'])
        diagnostic = next(row for row in check['fields'] if row['field'] == 'qacc')
        self.assertFalse(diagnostic['gating'])
        self.assertFalse(diagnostic['passed'])
        b['integrator']['state.qacc_warmstart'] = numeric_field([1e-4, 0., 0.])
        check = self.compare(a, b)
        self.assertFalse(check['passed'])
        self.assertEqual(check['differences'][0]['field'], 'qacc_warmstart')

    def test_nan_including_qacc_shape_dtype_and_integer_change_are_rejected(self):
        for field, descriptor in (
            ('state.qpos', numeric_field([float('nan'), 0., 1.])),
            ('state.qacc', numeric_field([float('nan'), 0., 0.])),
            ('state.qpos', numeric_field([.04, 0., 1.], shape=[1, 3])),
            ('state.qpos', numeric_field([.04, 0., 1.], dtype='float64')),
        ):
            with self.subTest(field=field, descriptor=descriptor):
                a, b = numeric_fixture(), numeric_fixture()
                b['integrator'][field] = descriptor
                self.assertFalse(self.compare(a, b)['passed'])
        a = numeric_field([1], dtype='int64', kind='i')
        b = numeric_field([2], dtype='int64', kind='i')
        row = comparison.compare_numeric_field('integrator', 'state.counter', a, b)
        self.assertFalse(row['passed'])
        self.assertEqual((row['atol'], row['rtol']), (0., 0.))

    def test_old_digest_only_records_do_not_gain_unproven_tolerance(self):
        a, b = fingerprint('a'), fingerprint('b')
        result = comparison.compare_initial_states(a, b)
        self.assertFalse(result['passed'])
        self.assertIn('missing_numeric_snapshot', [row['reason'] for row in result['differences']])
        self.assertTrue(comparison.compare_initial_states(a, a)['passed'])

    def test_scalar_fields_are_captured_and_changes_cannot_hide_in_digest(self):
        import numpy as np
        torch = ModuleType('torch')
        torch.Tensor = type('Tensor', (), {})
        torch.Generator = type('Generator', (), {})
        with patch.dict(sys.modules, {'torch': torch}):
            a = comparison._numeric_tree({'time': 0., 'counter': 1, 'enabled': True,
                                         'mass': np.float32(.02), 'flag': np.bool_(True)}, capture_values=True)
            b = comparison._numeric_tree({'time': .01, 'counter': 2, 'enabled': False,
                                         'mass': np.float32(.021), 'flag': np.bool_(False)}, capture_values=True)
        comparison._require_numeric_coverage('integrator', ['time', 'counter', 'enabled', 'mass', 'flag'], a['numeric_values'])
        for field in a['numeric_values']:
            with self.subTest(field=field):
                self.assertEqual(a['numeric_values'][field]['shape'], [])
                row = comparison.compare_numeric_field('integrator', field,
                      a['numeric_values'][field], b['numeric_values'][field])
                self.assertFalse(row['passed'])
                self.assertIsNotNone(row['example_difference']['flat_index'])
        self.assertEqual(a['numeric_values']['state.mass']['dtype'], 'float32')
        self.assertEqual(a['numeric_values']['state.enabled']['kind'], 'b')

    def test_opaque_or_metadata_only_required_state_cannot_claim_coverage(self):
        import numpy  # Import outside patch.dict so module caching is preserved.
        torch = ModuleType('torch')
        torch.Tensor = type('Tensor', (), {})
        torch.Generator = type('Generator', (), {})
        with patch.dict(sys.modules, {'torch': torch}):
            tree = comparison._numeric_tree({'qpos': SimpleNamespace(ptr=123),
                                            'qvel': object(), 'ctrl': [0.]}, capture_values=True)
        self.assertIn('state.qpos.ptr', tree['numeric_values'])
        with self.assertRaisesRegex(ValueError, r'integrator.qpos.*integrator.qvel.*integrator.ctrl'):
            comparison._require_numeric_coverage('integrator', ['qpos', 'qvel', 'ctrl'], tree['numeric_values'])

    def test_nonfinite_a_preflight_stops_before_first_action(self):
        values = numeric_fixture()
        values['integrator']['state.qacc'] = numeric_field([float('nan'), 0., 0.])
        raw = SimpleNamespace(reward_manager=SimpleNamespace(get_term_cfg=lambda _: SimpleNamespace(params={'target_height': .115})))
        closed = []
        env = SimpleNamespace(unwrapped=raw, close=lambda: closed.append(True))
        def forbidden(obs):
            raise AssertionError('Nonfinite A initial state must not take an action')
        def capture(env, obs, policy, *, numeric_snapshots):
            numeric_snapshots.update(values)
            return numeric_fingerprint(values)
        action = {'scale': 1., 'filter': {'head_alpha': 1., 'legs_alpha': 1.}}
        with patch.object(comparison, '_build_group', return_value=(env, forbidden, {}, action)), \
             patch.object(comparison, 'startup_fingerprint', capture):
            result = comparison._run_group({}, profile(), 'A', lambda *args, **kwargs: None)
        self.assertEqual((result['status'], result['steps']), ('invalid', 0))
        self.assertIn('A组未运行', result['error'])
        self.assertEqual(result['initial_state_differences'][0]['reason'], 'nonfinite_value')
        self.assertEqual(closed, [True])

    def test_torcharray_pointer_and_stream_excluded_and_snapshot_frozen(self):
        import numpy as np
        class Tensor:
            def __init__(self, values): self.array = np.array(values, dtype=np.float32)
            def detach(self): return self
            def cpu(self): return self
            def contiguous(self): return self
            def numpy(self): return self.array
        class TorchArray:
            def __init__(self, values, pointer):
                self._tensor = Tensor(values)
                self._wp_array = SimpleNamespace(ptr=pointer, capacity=999, device='cuda:0')
                self._torch_stream = pointer + 1000
                self._is_cuda = True
        torch = ModuleType('torch')
        torch.Tensor = Tensor
        torch.Generator = type('Generator', (), {})
        a, b = TorchArray([.04, 0., 1.], 111), TorchArray([.04, 0., 1.], 999)
        with patch.dict(sys.modules, {'torch': torch}):
            aa = comparison._numeric_tree({'qpos': a}, capture_values=True)
            bb = comparison._numeric_tree({'qpos': b}, capture_values=True)
            self.assertEqual(aa['sha256'], bb['sha256'])
            self.assertEqual(set(aa['fields']), {'state.qpos'})
            self.assertIn('TorchArray', aa['fields']['state.qpos']['source_type'])
            saved = copy.deepcopy(aa['numeric_values'])
            a._tensor.array[0] = 10.0  # Simulate subsequent A rollout mutation.
            self.assertEqual(aa['numeric_values'], saved)
            changed = comparison._numeric_tree({'qpos': a}, capture_values=True)
            row = comparison.compare_numeric_field('integrator', 'state.qpos',
                  aa['numeric_values']['state.qpos'], changed['numeric_values']['state.qpos'])
            self.assertFalse(row['passed'])
            invalid = TorchArray([0.], 111)
            invalid._tensor = None
            with self.assertRaisesRegex(ValueError, 'GPU指针'):
                comparison._numeric_tree(invalid, capture_values=True)
        # Public comparison records contain metadata/numbers, never arrays.
        json.dumps(comparison.compare_initial_states(
            {'components': {'integrator': aa['sha256']}},
            {'components': {'integrator': bb['sha256']}},
            {'integrator': aa['numeric_values']}, {'integrator': bb['numeric_values']}), allow_nan=False)

    def test_within_tolerance_group_b_runs_and_public_result_is_serializable(self):
        p = profile()
        a, b = numeric_fixture(), numeric_fixture()
        b['integrator']['state.qpos'] = numeric_field([.04000001, 0., 1.])
        raw = SimpleNamespace(reward_manager=SimpleNamespace(get_term_cfg=lambda _: SimpleNamespace(params={'target_height': .115})),
                              step_dt=.02, reset_terminated=[False], reset_time_outs=[True],
                              cfg=SimpleNamespace(auto_reset=True))
        actions = []
        closed = []
        env = SimpleNamespace(unwrapped=raw, close=lambda: closed.append(True),
                              step=lambda action: ({}, None, [True], {}))
        def policy(obs):
            actions.append(True)
            return [0.] * 14
        def capture(env, obs, policy, *, numeric_snapshots):
            numeric_snapshots.update(b)
            return numeric_fingerprint(b)
        action_mapping = {'scale': 1., 'filter': {'head_alpha': 1., 'legs_alpha': 1.}}
        with patch.object(comparison, '_build_group', return_value=(env, policy, {}, action_mapping)), \
             patch.object(comparison, 'startup_fingerprint', capture):
            result = comparison._run_group({}, p, 'B', lambda *args, **kwargs: None,
                                           numeric_fingerprint(a), expected_numeric=a)
        self.assertEqual(actions, [True])
        self.assertEqual(result['steps'], 1)
        self.assertEqual(result['status'], 'failed')  # The trial ran and timed out.
        self.assertTrue(result['initial_state_comparison']['passed'])
        self.assertFalse(result['initial_state_exact'])
        self.assertEqual(closed, [True])
        self.assertNotIn('values', json.dumps(result))
        json.dumps(result, allow_nan=False)


if __name__ == '__main__':
    unittest.main(verbosity=2)

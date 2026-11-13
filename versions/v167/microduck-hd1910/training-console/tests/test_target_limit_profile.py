"""Synthetic fixtures only: no robot recordings or user calibration data."""
import copy
import hashlib
import json
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from training import target_limit_profile as profile


TASK = 'Mjlab-StandUp-Rough-Backlash-MicroDuck'
OTHER_STAND_TASK = 'Mjlab-StandUp-Flat-MicroDuck'
MODEL_SHA = 'a' * 64


def make_recording():
    joints = [
        {'name': name, 'id': ident, 'zero_raw': 2048,
         'direction': 1 if i % 2 else -1, 'min_rad': -0.6,
         'max_rad': 0.6, 'calibrated': True}
        for i, (name, ident) in enumerate(profile.POLICY_IDS.items())
    ]
    joints.insert(4, {'name': 'mouth', 'id': 34, 'zero_raw': 2048,
                      'direction': 1, 'min_rad': -0.2, 'max_rad': 0.3,
                      'calibrated': True})
    frame = {
        'bus': {
            'policy_enabled': True,
            'active_model': {'sha256': MODEL_SHA, 'task': TASK},
            'active_action_scale': 0.96,
            'model_action_scales': {'stand_test': 1},
            'active_target_filters': {'head_lowpass': 1, 'legs_lowpass': 1},
            'voltage_adapt': True, 'build': 'synthetic-test-build',
        },
        'calibration': {'calibration': {'joints': joints}},
    }
    return {'schema': 'microduck-console-recording/v1',
            'created_at': 1700000000.0, 'frames': [frame, copy.deepcopy(frame)]}


def parse(recording):
    return profile.from_recording({'name': 'synthetic.json',
                                   'text': json.dumps(recording)})


def joint_rows(recording, frame=0):
    return recording['frames'][frame]['calibration']['calibration']['joints']


def make_recorded_start_recording():
    recording = make_recording()
    previous = copy.deepcopy(recording['frames'][0])
    previous.update(at=1000.0, connection_paused=False,
                    channels={key: {'status': 'live', 'seq': 1, 'age_ms': 40}
                              for key in ('state', 'bus')})
    rows = previous['calibration']['calibration']['joints']
    pos = [(i - 7) * .03 for i in range(15)]
    previous['state'] = {'policy': 'held', 't_ns': 1_000_000_000,
                         'joints': pos, 'velocities': [0.0] * 15,
                         'safety': {'gravity': [-1.0, 0.0, 0.0]},
                         'imu': {'gyro': [0.0, 0.0, .004]}}
    previous['servos'] = [{'name': row['name'], 'id': row['id'], 'index': i,
                           'angle_deg': math.degrees(pos[i]), 'status': 'live',
                           'sample_age_ms': 5} for i, row in enumerate(rows)]
    previous['bus'].update(policy_enabled=False, active_model=None,
                           loaded_models={'stand_test': {'sha256': MODEL_SHA, 'task': TASK}},
                           fresh_sample=True, all_joints_fresh=True,
                           native={'all_joints_fresh': True, 'held_joint_ids': [],
                                   'stale_joint_ids': [], 'sample_age_ms': 5,
                                   'imu_ready': True, 'imu_mount_verified': True,
                                   'joints': [{'feedback_fresh': True, 'sample_age_ms': 5} for _ in range(15)]})
    for i, frame in enumerate(recording['frames']):
        frame.update(at=1000.1 + .1 * i,
                     state={'policy': 'stand_test', 't_ns': 1_100_000_000 + i * 100_000_000})
    recording['frames'].insert(0, previous)
    return recording


class TargetLimitProfileTests(unittest.TestCase):
    def test_recorded_start_is_last_inactive_before_first_enable_with_named_mapping(self):
        recording = make_recorded_start_recording()
        # Servo enumeration and state-vector order are deliberately different.
        recording['frames'][0]['servos'].reverse()
        before = copy.deepcopy(recording)
        result = parse(recording)
        start = result['recorded_start']
        self.assertNotIn('recorded_start_unavailable_reason', result)
        self.assertEqual((start['frame_index'], start['active_frame_index']), (0, 1))
        self.assertEqual(start['source'], 'last_inactive_before_first_standup_enable')
        self.assertEqual(start['schema'], 'microduck-recorded-start-v1')
        self.assertAlmostEqual(start['gap_s'], .1)
        self.assertEqual(start['joint_names'], list(profile.RUNTIME_JOINTS))
        by_name = {row['name']: row for row in before['frames'][0]['servos']}
        self.assertEqual(start['joint_pos_rad'], [before['frames'][0]['state']['joints'][by_name[name]['index']] for name in profile.RUNTIME_JOINTS])
        self.assertEqual(start['joint_vel_rad_s'], [0.0] * 14)
        self.assertEqual(recording, before, 'parser does not mutate the uploaded recording')
        self.assertEqual(profile.validate_profile(result), result)

    def test_active_only_recording_stays_valid_for_standard_comparison(self):
        result = parse(make_recording())
        self.assertNotIn('recorded_start', result)
        self.assertIn('没有首次启用前', result['recorded_start_unavailable_reason'])
        self.assertEqual(profile.validate_profile(result), result)
        legacy = copy.deepcopy(result)
        del legacy['recorded_start_unavailable_reason']
        self.assertEqual(profile.validate_profile(legacy), legacy)

    def test_unavailable_start_never_falls_back_to_a_later_activation(self):
        recording = make_recorded_start_recording()
        later = copy.deepcopy(recording['frames'][0])
        later['at'], later['state']['t_ns'] = 1001.0, 2_000_000_000
        active = copy.deepcopy(recording['frames'][1])
        active['at'], active['state']['t_ns'] = 1001.1, 2_100_000_000
        recording['frames'].extend([later, active])
        recording['frames'][0]['channels']['state']['age_ms'] = 201
        result = parse(recording)
        self.assertNotIn('recorded_start', result)
        self.assertIn('过旧', result['recorded_start_unavailable_reason'])

    def test_recorded_start_availability_guards_preserve_standard_mode(self):
        mutations = {
            'moving joint': lambda f: f['state']['velocities'].__setitem__(0, .251),
            'moving body': lambda f: f['state']['imu'].__setitem__('gyro', [.2, .2, 0]),
            'bad gravity': lambda f: f['state']['safety'].__setitem__('gravity', [-.5, 0, 0]),
            'not held': lambda f: f['state'].__setitem__('policy', 'homing'),
            'paused': lambda f: f.__setitem__('connection_paused', True),
            'channel skew': lambda f: f['channels']['bus'].__setitem__('seq', 2),
            'stale channel': lambda f: f['channels']['state'].__setitem__('age_ms', 201),
            'stale native': lambda f: f['bus']['native'].__setitem__('sample_age_ms', 101),
            'stale joint': lambda f: f['bus']['native']['joints'][0].__setitem__('feedback_fresh', False),
            'held joint': lambda f: f['bus']['native'].__setitem__('held_joint_ids', [21]),
            'bad IMU': lambda f: f['bus']['native'].__setitem__('imu_mount_verified', False),
            'wrong model': lambda f: f['bus']['loaded_models']['stand_test'].__setitem__('sha256', 'b' * 64),
            'wrong calibration': lambda f: f['calibration']['calibration']['joints'][0].__setitem__('zero_raw', 2049),
            'bad name': lambda f: f['servos'][0].__setitem__('name', 'other'),
            'duplicate index': lambda f: f['servos'][0].__setitem__('index', 1),
            'wrong feedback mapping': lambda f: f['servos'][0].__setitem__('angle_deg', 0),
            'state gap': lambda f: f['state'].__setitem__('t_ns', 700_000_000),
            'wall gap': lambda f: f.__setitem__('at', 999.5),
            'invalid timestamp': lambda f: f['state'].__setitem__('t_ns', True),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                recording = make_recorded_start_recording()
                mutate(recording['frames'][0])
                result = parse(recording)
                self.assertNotIn('recorded_start', result)
                self.assertTrue(result['recorded_start_unavailable_reason'])
                self.assertEqual(result['model_sha256'], MODEL_SHA)

    def test_validate_recorded_start_rejects_tampered_optional_fields(self):
        result = parse(make_recorded_start_recording())
        for key, value in [('schema', 'other'), ('source', 'second_enable'),
                           ('frame_index', -1), ('active_frame_index', 0),
                           ('active_frame_index', 2), ('state_t_ns', True),
                           ('state_t_ns', 10**100), ('gap_s', .31), ('gap_s', -1),
                           ('joint_names', list(profile.RUNTIME_JOINTS)[:-1]),
                           ('joint_pos_rad', [float('nan')] * 14),
                           ('joint_pos_rad', [4.0] * 14),
                           ('joint_vel_rad_s', [.3] * 14),
                           ('gyro_rad_s', [True, 0, 0]), ('gravity_b', [0, 0, 0])]:
            bad = copy.deepcopy(result)
            bad['recorded_start'][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                profile.validate_profile(bad)
        bad = copy.deepcopy(result)
        bad['recorded_start_unavailable_reason'] = 'contradictory'
        with self.assertRaises(ValueError):
            profile.validate_profile(bad)
        for reason in ('', None, 'x' * 241):
            bad = parse(make_recording())
            bad['recorded_start_unavailable_reason'] = reason
            with self.subTest(reason=reason), self.assertRaises(ValueError):
                profile.validate_profile(bad)

    def test_validate_recorded_start_normalizes_named_vector_order(self):
        result = parse(make_recorded_start_recording())
        permuted = copy.deepcopy(result)
        for key in ('joint_names', 'joint_pos_rad', 'joint_vel_rad_s'):
            permuted['recorded_start'][key].reverse()
        self.assertEqual(profile.validate_profile(permuted), result)

    def test_named_mapping_excludes_mouth_and_keeps_source_unchanged(self):
        recording = make_recording()
        joint_rows(recording).reverse()
        second = joint_rows(recording, 1)
        second[:] = second[7:] + second[:7]
        recording['frames'][1]['bus']['active_action_scale'] = 0.97
        before = copy.deepcopy(recording)
        text = json.dumps(recording)
        result = profile.from_recording({'name': r'C:\samples\synthetic.json', 'text': text})
        self.assertEqual([r['name'] for r in result['joints']], list(profile.RUNTIME_JOINTS))
        self.assertEqual(len(result['joints']), 14)
        self.assertNotIn('mouth', [r['name'] for r in result['joints']])
        self.assertEqual(recording, before)
        self.assertEqual(result['recording']['source_name'], 'synthetic.json')
        self.assertEqual(result['recording']['source_sha256'], hashlib.sha256(text.encode()).hexdigest())
        self.assertEqual(result['runtime']['effective_action_scale_min'], 0.96)
        self.assertEqual(result['runtime']['effective_action_scale_max'], 0.97)
        self.assertEqual(profile.validate_profile(result, MODEL_SHA, TASK), result)

    def test_rejects_missing_duplicate_unknown_and_extra_joint_rows(self):
        for case in ('missing', 'duplicate', 'unknown_instead_of_mouth', 'extra', 'wrong_id', 'not_object'):
            with self.subTest(case=case):
                recording = make_recording()
                rows = joint_rows(recording)
                if case == 'missing':
                    rows.pop()
                elif case == 'duplicate':
                    rows[-1] = copy.deepcopy(rows[0])
                elif case == 'unknown_instead_of_mouth':
                    next(r for r in rows if r['name'] == 'mouth')['name'] = 'unknown'
                elif case == 'extra':
                    rows.append(copy.deepcopy(rows[0]))
                elif case == 'wrong_id':
                    rows[0]['id'] = 34
                else:
                    rows[0] = None
                with self.assertRaises(ValueError):
                    parse(recording)
        result = parse(make_recording())
        for length in (13, 15):
            bad = copy.deepcopy(result)
            bad['joints'] = (bad['joints'] + [bad['joints'][0]])[:length]
            with self.subTest(profile_rows=length), self.assertRaises(ValueError):
                profile.validate_profile(bad)

    def test_requires_matching_model_hash_and_standup_task(self):
        result = parse(make_recording())
        for expected in ({'expected_sha': 'b' * 64}, {'expected_task': OTHER_STAND_TASK}):
            with self.subTest(expected=expected), self.assertRaises(ValueError):
                profile.validate_profile(result, **expected)
        for key, value in (('model_sha256', 'short'), ('model_sha256', 'g' * 64),
                           ('task', 'Mjlab-Velocity-Flat-MicroDuck'), ('task', [])):
            bad = copy.deepcopy(result)
            bad[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                profile.validate_profile(bad)

    def test_rejects_model_calibration_or_fixed_runtime_change(self):
        for case in ('sha', 'task', 'zero', 'direction', 'limit', 'base_scale', 'filter', 'voltage_adapt'):
            with self.subTest(case=case):
                recording = make_recording()
                bus = recording['frames'][1]['bus']
                joint = joint_rows(recording, 1)[0]
                if case == 'sha':
                    bus['active_model']['sha256'] = 'b' * 64
                elif case == 'task':
                    bus['active_model']['task'] = OTHER_STAND_TASK
                elif case == 'zero':
                    joint['zero_raw'] += 1
                elif case == 'direction':
                    joint['direction'] *= -1
                elif case == 'limit':
                    joint['min_rad'] = -0.5
                elif case == 'base_scale':
                    bus['model_action_scales']['stand_test'] = 0.9
                elif case == 'filter':
                    bus['active_target_filters']['head_lowpass'] = 0.5
                else:
                    bus['voltage_adapt'] = False
                with self.assertRaises(ValueError):
                    parse(recording)

    def test_rejects_nonfinite_and_overflow_numbers(self):
        for value in (float('nan'), float('inf'), -float('inf'), 10 ** 400):
            recording = make_recording()
            recording['frames'][0]['bus']['active_action_scale'] = value
            with self.subTest(value=str(value)[:30]), self.assertRaises(ValueError):
                parse(recording)
        # Exponent overflow does not use json.loads' parse_constant callback.
        text = json.dumps(make_recording())[:-1] + ', "unused": 1e999}'
        with self.assertRaises(ValueError):
            profile.from_recording({'name': 'synthetic.json', 'text': text})
        result = parse(make_recording())
        result['joints'][0]['min_rad'] = float('nan')
        with self.assertRaises(ValueError):
            profile.validate_profile(result)

    def test_raw_boundaries_use_rust_rounding_and_never_wrap(self):
        tick = math.tau / 4096
        for zero, lo, hi in ((0, -0.5 * tick, 0.1),
                             (4095, -0.1, 0.5 * tick),
                             (0, -0.6, 0.6)):
            recording = make_recording()
            for frame in range(2):
                joint_rows(recording, frame)[0].update(
                    zero_raw=zero, direction=1, min_rad=lo, max_rad=hi)
            with self.subTest(zero=zero, lo=lo, hi=hi), self.assertRaises(ValueError):
                parse(recording)
        # A raw value just inside half a count rounds to a valid endpoint.
        for zero, lo, hi in ((0, -0.49 * tick, 0.1), (4095, -0.1, 0.49 * tick)):
            recording = make_recording()
            for frame in range(2):
                joint_rows(recording, frame)[0].update(
                    zero_raw=zero, direction=1, min_rad=lo, max_rad=hi)
            self.assertEqual(parse(recording)['joints'][0]['zero_raw'], zero)

    def test_rejects_invalid_numeric_types_and_malformed_active_fields(self):
        for key, value in (('name', []), ('id', True), ('zero_raw', 2048.0),
                           ('direction', True), ('direction', 0), ('min_rad', True),
                           ('max_rad', -0.7), ('max_rad', math.pi + 0.01),
                           ('calibrated', False)):
            recording = make_recording()
            joint_rows(recording)[0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                parse(recording)
        for key, value in (('active_model', {'task': []}), ('active_target_filters', []),
                           ('model_action_scales', []), ('policy_enabled', 'true')):
            recording = make_recording()
            recording['frames'][0]['bus'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                parse(recording)

    def test_frame_counts_and_active_frame_requirement(self):
        for count in (0, 1501):
            recording = make_recording()
            recording['frames'] = recording['frames'][:1] * count
            with self.subTest(count=count), self.assertRaises(ValueError):
                parse(recording)
        recording = make_recording()
        for frame in recording['frames']:
            frame['bus']['policy_enabled'] = False
        with self.assertRaises(ValueError):
            parse(recording)
        result = parse(make_recording())
        self.assertEqual(result['recording']['frame_count'], 2)
        self.assertEqual(result['recording']['active_frames'], 2)
        for key, value in (('active_frames', 3), ('frame_count', 1501), ('frame_count', True)):
            bad = copy.deepcopy(result)
            bad['recording'][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                profile.validate_profile(bad)


if __name__ == '__main__':
    unittest.main()

"""Recorded-start request isolation. Uses mocked workers, no actuation."""
import copy
import unittest

from tests import test_target_limit_api as api_fixture

fixture_profile = api_fixture.fixture_profile
from training.limit_comparison_request import validate_request
from training.official_spec import STAND
from training.target_limit_profile import POLICY_IDS


def profile_with_start():
    profile = fixture_profile()
    profile['recorded_start'] = {
        'schema': 'microduck-recorded-start-v1',
        'frame_index': 0, 'active_frame_index': 1,
        'frame_at_s': 1.0, 'state_t_ns': 1000000000, 'gap_s': 0.1,
        'joint_names': list(POLICY_IDS), 'joint_pos_rad': [0.0]*14,
        'joint_vel_rad_s': [0.0]*14, 'gravity_b': [-1.0, 0.0, 0.0],
        'gyro_rad_s': [0.0]*3,
        'source': 'last_inactive_before_first_standup_enable',
    }
    return profile


class RecordedStartApiTests(unittest.TestCase):
    setUp = api_fixture.TargetLimitApiTests.setUp
    export = api_fixture.TargetLimitApiTests.export

    def test_recorded_start_is_bound_without_editing_recipe_or_source(self):
        source, exported, _ = self.export()
        original = copy.deepcopy((source, exported, self.manager.recipe))
        profile = profile_with_start()
        jid = self.manager.launch('onnx', {'export_job': exported['id'],
            'target_limit_comparison': profile, 'target_limit_start_mode': 'recorded'})['job_id']
        req = self.manager.jobs[jid]['request']
        self.assertEqual(req['target_limit_start_mode'], 'recorded')
        self.assertEqual(req['target_limit_comparison']['recorded_start'], profile['recorded_start'])
        self.assertEqual((source, exported, self.manager.recipe), original)
        self.assertNotIn('recorded_start', req['studio_recipe'])
        profile['recorded_start']['joint_pos_rad'][0] = 0.4
        self.assertEqual(req['target_limit_comparison']['recorded_start']['joint_pos_rad'][0], 0.0)

    def test_missing_pose_and_bad_modes_do_not_create_jobs(self):
        _, exported, _ = self.export()
        before = set(self.manager.jobs)
        for mode in ('recorded', None, True, [], {}, '', 'replay', 1):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                self.manager.launch('onnx', {'export_job': exported['id'],
                    'target_limit_comparison': fixture_profile(), 'target_limit_start_mode': mode})
        self.assertEqual(before, set(self.manager.jobs))

    def test_mode_alone_cannot_leak_to_ordinary_onnx_or_cached_probe(self):
        _, exported, selected = self.export()
        before = set(self.manager.jobs)
        for mode in ('standard', 'recorded'):
            for op in ('train', 'preflight', 'preview', 'play', 'onnx', 'export', 'setup', 'probe', 'describe'):
                with self.subTest(op=op, mode=mode), self.assertRaises(ValueError):
                    self.manager.launch(op, {**selected, 'task': STAND,
                        'export_job': exported['id'], 'target_limit_start_mode': mode})
            with self.assertRaisesRegex(ValueError, '不能加入训练队列'):
                self.manager.queue_add({'task': STAND, 'client_id': 'start-'+mode,
                                       'target_limit_start_mode': mode})
        self.assertEqual(before, set(self.manager.jobs))
        self.assertEqual(self.manager.training_queue['entries'], [])

    def test_standard_mode_remains_available_without_pre_enable_pose(self):
        _, exported, _ = self.export()
        jid = self.manager.launch('onnx', {'export_job': exported['id'],
            'target_limit_comparison': fixture_profile()})['job_id']
        req = self.manager.jobs[jid]['request']
        self.assertEqual(req['target_limit_start_mode'], 'standard')
        self.assertNotIn('recorded_start', req['target_limit_comparison'])


class RecordedStartWorkerGuardTests(unittest.TestCase):
    def test_failed_pose_readback_is_not_logged_as_motor_failure(self):
        import training_console
        line=training_console.event_log_text({'kind':'limit_comparison_result','data':{
            'start_mode':'recorded','valid':False,'groups':[{'label':'A','steps':0,'status':'invalid',
                'recorded_start_check':{'passed':False,'errors':{'encoder_max_abs_deg':2.0,
                    'gravity_l2':0.002,'gravity_data_vs_qpos_l2':0.002}}}]}})
        self.assertIn('真机起点对照结果',line)
        self.assertIn('关节最大误差=2°',line)
        self.assertIn('A组：未运行（真机起点回读未通过）',line)
        self.assertNotIn('最大翻身角=0',line)

    def test_rejects_non_onnx_before_loading_simulator(self):
        from training import runtime_adapter
        for op in ('train', 'preflight', 'preview', 'play', 'export', 'describe'):
            with self.subTest(op=op), self.assertRaisesRegex(ValueError, '仅用于'):
                runtime_adapter.main({'op': op, 'target_limit_start_mode': 'recorded'})

    def test_direct_onnx_rejects_detached_mode_before_loading_simulator(self):
        from training import runtime_adapter
        with self.assertRaisesRegex(ValueError, '一起提交'):
            runtime_adapter.onnx({'op': 'onnx', 'target_limit_start_mode': 'recorded'})

    def test_guard_preserves_missing_pose_reason(self):
        profile = {'recorded_start_unavailable_reason': '启用前样本过期。'}
        with self.assertRaisesRegex(ValueError, '启用前样本过期'):
            validate_request({'op': 'onnx', 'target_limit_comparison': profile,
                              'target_limit_start_mode': 'recorded'}, profile=profile)


if __name__ == '__main__':
    unittest.main()

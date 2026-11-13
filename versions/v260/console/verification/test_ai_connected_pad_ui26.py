"""Connected physical handpads coexist with AI; real robot readiness still applies."""
import threading
from types import SimpleNamespace
import unittest

from ai_action_gate import ActionDenied
from ai_remote import RemoteAI
from ai_runtime import AIHub
from verification.test_ai_v200 import FakeRobot


class ConnectedHandpadTests(unittest.TestCase):
    def setUp(self):
        self.robot = FakeRobot()
        self.pad = {'real_connected': True}
        self.snap = {
            'service_sample_fresh': True, 'service_sample_age_ms': 10,
            'bus': {'mode': 'motion', 'phase': 'control', 'homed': True,
                    'policy_enabled': True, 'sitting': False, 'torque_off_pending': False,
                    'native': {'torque_state_confirmed': True, 'imu_ready': True}},
            'channels': {'state': {'status': 'live', 'age_ms': 0}},
        }
        self.connection = SimpleNamespace(active=True)
        def snapshot():
            state = self.robot.state()
            return {**self.snap, 'state': {'policy': state['policy'], 't_ns': state['state_t_ns']}}
        self.hub = AIHub(SimpleNamespace(peek=snapshot), connection=self.connection,
                         controller=SimpleNamespace(status=lambda _: {'webpad': self.pad}))
        self.gate = self.hub.gate
        self.gate.rpc = self.rpc
        self.gate.clock = self.robot.clock
        self.gate.sleep = self.robot.clock.sleep
        report = {**self.robot.skills, 'expressions': [
            {'name': 'laugh', 'label': '大笑', 'meaning': '开心大笑', 'seconds': 1.,
             'skill': 'emotion_laugh', 'silent_skill': 'emotion_silent_laugh', 'silent': False}]}
        self.gate.set_skills(report)
        self.polls = 0
        self.complete_after_polls = 2

    def tearDown(self):
        self.hub.close()

    def rpc(self, method, args):
        if method == 'robot.do' and args['skill'].startswith('emotion_'):
            self.robot.calls.append((method, args))
            if args['skill'] == 'emotion_status':
                self.polls += 1
                completed = self.complete_after_polls is not None and self.polls >= self.complete_after_polls
                return {'request_id': 42, 'phase': 'completed' if completed else 'playing'}
            return {'accepted': True, 'request_id': 42}
        return self.robot.rpc(method, args)

    def test_connected_handpad_allows_audible_laugh_and_actual_completion(self):
        result = self.gate.execute('express_emotion', {'emotion': 'laugh'})
        self.assertEqual(result['status'], 'completed')
        self.assertFalse(result['silent'])
        self.assertEqual(self.robot.calls[0], ('robot.do', {'skill': 'emotion_laugh'}))
        self.assertEqual(self.polls, 2)
        self.assertFalse(any('cancel' in args.get('skill', '') for _, args in self.robot.calls))

    def test_connecting_handpad_during_expression_does_not_cancel_it(self):
        self.pad['real_connected'] = False
        def sleep(seconds):
            self.robot.clock.sleep(seconds)
            self.pad['real_connected'] = True
        self.gate.sleep = sleep
        self.assertEqual(self.gate.execute('express_emotion', {'emotion': 'laugh'})['status'], 'completed')
        self.assertTrue(self.pad['real_connected'])

    def test_legacy_gamepad_flag_cannot_block_head_walk_or_model_tools(self):
        state, monitor = self.gate.state, self.gate.monitor
        self.gate.state = lambda: {**state(), 'gamepad': True}
        self.gate.monitor = lambda: {**monitor(), 'gamepad': True}
        self.gate.execute('head_pose', {'head_yaw': 1.})
        self.assertEqual(self.robot.calls[-1][0], 'robot.head')
        self.gate.execute('walk_short', {'vx': .1, 'vy': 0, 'vyaw': 0, 'seconds': .1})
        self.assertEqual(self.robot.calls[-1], ('robot.move', {'vx': 0, 'vy': 0, 'vyaw': 0}))
        result = self.gate.execute('perform_skill', {'skill': 'roulade'})
        self.assertEqual(result['status'], 'completed')
        self.assertGreater(result['model_completed_t_ns'], result['model_started_t_ns'])

    def test_connected_handpad_does_not_bypass_home_hold_torque_or_maintenance(self):
        cases = [(self.snap, 'service_sample_fresh', False, '实时反馈'),
                 (self.snap['bus'], 'homed', False, 'HOME'),
                 (self.snap['bus'], 'policy_enabled', False, '策略未启用'),
                 (self.snap['bus']['native'], 'torque_state_confirmed', False, '力矩未使能'),
                 (self.snap['bus'], 'torque_off_pending', True, '等待卸力'),
                 (self.snap, 'service_operation', True, '维护')]
        for obj, key, value, reason in cases:
            previous = obj.get(key)
            obj[key] = value
            try:
                with self.subTest(reason=reason), self.assertRaisesRegex(ActionDenied, reason):
                    self.gate.execute('express_emotion', {'emotion': 'laugh'})
            finally:
                obj[key] = previous
        self.connection.active = False
        with self.assertRaisesRegex(ActionDenied, '未连接'):
            self.gate.execute('head_pose', {})
        self.assertFalse(self.robot.calls)

    def test_unload_during_expression_still_cancels_without_enabling_torque(self):
        self.complete_after_polls = None
        def sleep(seconds):
            self.robot.clock.sleep(seconds)
            self.snap['bus']['torque_off_pending'] = True
        self.gate.sleep = sleep
        with self.assertRaisesRegex(ActionDenied, '等待卸力'):
            self.gate.execute('express_emotion', {'emotion': 'laugh'})
        self.assertIn(('robot.do', {'skill': 'emotion_cancel_42'}), self.robot.calls)
        self.assertFalse(any(method in ('robot.enable', 'robot.init') for method, _ in self.robot.calls))

    def test_zero_action_relay_returns_completed_with_handpad_connected(self):
        remote = RemoteAI(self.hub, SimpleNamespace(), threading.Event())
        received = []
        done = threading.Event()
        def control(message):
            received.append(message)
            done.set()
            return {'accepted': True}
        remote._control = control
        remote._event({'kind': 'action_request', 'request_id': 'laugh-from-doubao',
                       'name': 'express_emotion', 'arguments': {'emotion': 'laugh'},
                       'ai_input_token': 'a'*32})
        self.assertTrue(done.wait(2))
        self.assertEqual(received[0]['request_id'], 'laugh-from-doubao')
        self.assertEqual(received[0]['result']['status'], 'completed')
        self.assertTrue(received[0]['result']['accepted'])


if __name__ == '__main__':
    unittest.main()

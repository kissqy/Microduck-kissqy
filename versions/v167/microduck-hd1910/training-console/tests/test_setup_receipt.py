"""Run real setup finalization with protocol output, without package installs/GPU."""
import copy
import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

import training_console as tc
from training.official_spec import REVISION, TASKS, WALK


class SetupReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.manager = tc.TrainingManager(Path(self.temp.name))
        self.addCleanup(self.manager.close)

    def complete_setup(self, ready=True, failed=False, exit_code=0, emit_result=True, op='setup'):
        with patch.object(tc.BaseTrainingManager, '_run'):
            job = self.manager.jobs[self.manager.launch(op, {**self.manager.profile})['job_id']]
        receipt = {'ready': ready, 'revision': REVISION, 'tasks': list(TASKS),
                   'gpu': {'cuda': ready, 'gpus': [{'name': 'fixture GPU'}] if ready else []},
                   'message': '环境就绪' if ready else 'CUDA不可用', 'configs': {}}
        events = []
        if emit_result:
            events.append({'kind': 'environment', 'data': receipt})
        events.append({'kind': 'failed' if failed else 'complete', 'message': '安装失败' if failed else '安装完成'})
        output = ''.join(tc.PREFIX + json.dumps(e) + '\n' for e in events).encode()
        process = Mock(stdout=io.BytesIO(output), stdin=io.BytesIO())
        process.wait.return_value = exit_code
        with patch.object(self.manager.sessions, 'start', return_value=process):
            tc.BaseTrainingManager._run(self.manager, job)
        return job

    def test_setup_preserves_ready_and_cache_across_restart(self):
        job = self.complete_setup()
        self.assertEqual(job['status'], 'completed')
        self.assertTrue(self.manager.environment['ready'])
        self.assertTrue(self.manager.computer_verified)
        cached = json.loads((self.manager.directory / 'environments.json').read_text())
        self.assertTrue(cached[self.manager.environment_key(self.manager.profile)]['ready'])
        self.manager.close()
        restored = tc.TrainingManager(self.manager.directory)
        self.addCleanup(restored.close)
        self.assertTrue(restored.computer_verified)
        self.assertTrue(restored.environment['ready'])

    def test_waiting_queue_dispatches_after_setup_without_probe_or_reinstall(self):
        eid = self.manager.queue_add({'task': WALK, 'num_envs': 2048, 'iterations': 2000,
                                      'client_id': 'after-setup'})['entry_id']
        self.manager.queue_command({'action': 'start'})
        self.complete_setup()
        with patch.object(tc.BaseTrainingManager, '_run'):
            self.manager.queue_tick()
        entry = next(e for e in self.manager.training_queue['entries'] if e['id'] == eid)
        self.assertEqual(entry['status'], 'running', entry.get('message'))
        self.assertEqual([j['op'] for j in self.manager.jobs.values()], ['setup', 'train'])

    def test_unavailable_cuda_is_never_cached_as_success(self):
        self.complete_setup(ready=False)
        self.assertFalse(self.manager.environment['ready'])
        self.assertFalse(self.manager.computer_verified)
        self.assertIn('CUDA', self.manager.environment['message'])

    def test_failure_after_ready_event_is_not_accepted(self):
        for failed, code in [(True, 1), (False, 1)]:
            with self.subTest(failed=failed, code=code):
                self.complete_setup(failed=failed, exit_code=code)
                self.assertFalse(self.manager.environment['ready'])
                self.assertFalse(self.manager.computer_verified)

    def test_complete_without_environment_receipt_does_not_verify_gpu(self):
        self.complete_setup(emit_result=False)
        self.assertFalse(self.manager.environment['ready'])
        self.assertFalse(self.manager.computer_verified)

    def test_probe_recovers_legacy_completed_setup_without_downloads(self):
        self.complete_setup(emit_result=False)
        job = self.complete_setup(op='probe')
        self.assertEqual(job['op'], 'probe')
        self.assertTrue(self.manager.environment['ready'])
        self.assertTrue(self.manager.computer_verified)


if __name__ == '__main__':
    unittest.main()

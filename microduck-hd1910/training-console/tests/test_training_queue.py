"""Scheduling boundaries, immutable recipes, and crash recovery without a GPU."""
import copy
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import training_console as tc
from training.official_spec import WALK, STAND, JOINT
from training.worker import command_failure


class TrainingQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.guard = patch.object(tc.BaseTrainingManager, '_run')
        self.guard.start()
        self.addCleanup(self.guard.stop)
        self.manager = tc.TrainingManager(Path(self.temp.name))
        self.manager.computer_verified = True
        self.addCleanup(lambda: self.manager.close())

    def add(self, task=WALK, **extra):
        value = {'task': task, 'num_envs': 2048, 'iterations': 2000,
                 'training_action_scale': 1., 'client_id': str(time.time_ns()), **extra}
        eid = self.manager.queue_add(value)['entry_id']
        return next(e for e in self.manager.training_queue['entries'] if e['id'] == eid)

    def start(self):
        self.manager.queue_command({'action': 'start'})
        self.manager.queue_tick()

    def finish(self, entry, status='completed', code=0):
        job = self.manager.jobs[entry['job_id']]
        job.update(status=status, ended=time.time(), worker_exit_code=code,
                   revision=job['request']['expected_revision'], message='fixture '+status)
        job['checkpoints'] = [{'path':'/fixture/'+job['id']+'/model_1000.pt', 'iteration':1000},
                              {'path':'/fixture/'+job['id']+'/model_1999.pt', 'iteration':1999}]
        reference = json.loads((tc.ROOT/'data/task-configs'/(job['request']['task']+'.json')).read_text())
        job['effective_config'] = {'resolved': reference['inspection']}
        self.manager.persist(job)
        return job

    def test_snapshot_and_add_are_not_launch_or_checks(self):
        key = 'same-http-retry'
        a = self.add(client_id=key, label='first', training_action_scale=.7)
        self.add(client_id=key, label='different payload retry')
        self.assertEqual(len(self.manager.training_queue['entries']), 1)
        self.assertEqual(len(self.manager.jobs), 0)
        self.manager.recipe['robot']['body_mass_profile'] = {'fixture': 'changed'}
        current = copy.deepcopy(self.manager.recipe)
        self.start()
        job = self.manager.jobs[a['job_id']]
        self.assertEqual(job['request']['studio_recipe'], a['recipe'])
        self.assertEqual(self.manager.recipe, current)
        self.assertEqual(job['request']['training_action_scale'], .7)
        self.assertEqual(job['request']['num_envs'], 2048)
        self.assertEqual(job['request']['queue_entry_id'], a['id'])
        self.assertFalse(any(j['op'] in ('setup','preflight','probe','describe') for j in self.manager.jobs.values()))

    def test_next_waits_for_owner_exit_not_complete_event(self):
        a, b = self.add(), self.add(STAND)
        self.start()
        job = self.manager.jobs[a['job_id']]
        job['status'] = 'completed'
        self.manager.queue_tick()
        self.assertNotIn('job_id', b)
        self.finish(a)
        job['_monitor_thread'] = True
        self.manager.queue_tick()
        self.assertNotIn('job_id', b)
        job.pop('_monitor_thread')
        self.manager.processes[job['id']] = object()
        self.manager.queue_tick()
        self.assertNotIn('job_id', b)
        self.manager.processes.clear()
        self.manager.queue_tick()
        self.assertEqual(a['status'], 'completed')
        self.assertIn('job_id', b)
        self.finish(b)
        self.manager.queue_tick()
        self.assertFalse(self.manager.training_queue['enabled'])
        self.assertEqual([e['status'] for e in self.manager.training_queue['entries']], ['completed','completed'])

    def test_pause_does_not_stop_current_and_resume_continues(self):
        a, b = self.add(), self.add(STAND)
        self.start()
        with patch.object(self.manager, 'stop') as stop:
            self.manager.queue_command({'action':'pause'})
            self.finish(a)
            self.manager.queue_tick()
            stop.assert_not_called()
        self.assertNotIn('job_id', b)
        self.start()
        self.assertIn('job_id', b)

    def test_stop_persists_barrier_before_stopping_only_training(self):
        a, b = self.add(), self.add(STAND)
        self.start()
        self.manager.jobs['viewer'] = {'id': 'viewer', 'op': 'play', 'status': 'running'}
        original_stop = self.manager.stop
        def checked_stop(jid):
            self.assertFalse(self.manager.training_queue['enabled'])
            saved = json.loads((self.manager.directory/'training-queue.json').read_text())
            self.assertFalse(saved['enabled'])
            self.assertEqual(jid, a['job_id'])
            original_stop(jid)
        with patch.object(self.manager, 'stop', side_effect=checked_stop) as stop:
            self.manager.queue_command({'action': 'stop'})
            self.manager.queue_command({'action': 'stop'})
            self.manager.queue_tick()
            stop.assert_called_once_with(a['job_id'])
        self.assertEqual(a['status'], 'stopping')
        self.assertEqual(self.manager.jobs['viewer']['status'], 'running')
        self.assertNotIn('job_id', b)
        self.finish(a, 'stopped', 1)
        self.manager.queue_tick()
        self.assertNotIn('job_id', b)
        self.start()
        self.assertIn('job_id', b)
        self.assertEqual(len([j for j in self.manager.jobs.values() if j['op'] == 'train']), 2)

    def test_stop_after_complete_event_does_not_dispatch_next(self):
        a, b = self.add(), self.add(STAND)
        self.start()
        self.manager.jobs[a['job_id']]['status'] = 'completed'
        with patch.object(self.manager, 'stop') as stop:
            self.manager.queue_command({'action': 'stop'})
            stop.assert_not_called()
        self.finish(a)
        self.manager.queue_tick()
        self.assertNotIn('job_id', b)
        self.assertEqual(a['status'], 'completed')
        self.assertFalse(self.manager.training_queue['enabled'])

    def test_stop_waiting_queue_survives_restart_without_launch(self):
        a = self.add()
        self.manager.queue_command({'action': 'start'})
        with patch.object(self.manager, 'stop') as stop:
            self.manager.queue_command({'action': 'stop'})
            stop.assert_not_called()
        self.manager.close()
        restored = tc.TrainingManager(self.manager.directory)
        self.addCleanup(restored.close)
        restored.queue_tick()
        self.assertFalse(restored.training_queue['enabled'])
        self.assertEqual(restored.training_queue['entries'][0]['id'], a['id'])
        self.assertEqual(restored.training_queue['entries'][0]['status'], 'waiting')
        self.assertEqual(restored.jobs, {})

    def test_failure_pauses_or_skips_and_stop_always_pauses(self):
        a, b = self.add(), self.add(STAND)
        self.start()
        self.finish(a, 'failed', 1)
        self.manager.queue_tick()
        self.assertFalse(self.manager.training_queue['enabled'])
        self.assertNotIn('job_id', b)
        self.manager.queue_command({'action':'retry','entry_id':a['id']})
        self.start()
        self.assertEqual(self.manager.jobs[a['job_id']]['request']['queue_attempt'], 2)
        self.manager.queue_command({'action':'policy','failure_policy':'continue'})
        self.finish(a, 'failed', 1)
        self.manager.queue_tick()
        self.assertIn('job_id', b)
        self.finish(b, 'stopped', 0)
        self.manager.queue_tick()
        self.assertFalse(self.manager.training_queue['enabled'])

    def test_persisted_launch_link_recovers_without_duplicate(self):
        a, b = self.add(), self.add(STAND)
        self.start()
        a.pop('job_id')  # crash between persisted run and queue link write
        self.manager._queue_save()
        self.manager.close()
        self.manager = tc.TrainingManager(Path(self.temp.name))
        self.manager.computer_verified = True
        self.manager.queue_tick()
        self.assertEqual(len(self.manager.jobs), 1)
        a, b = self.manager.training_queue['entries']
        self.assertIn('job_id', a)
        self.finish(a)
        self.manager.queue_tick()
        self.assertEqual(len(self.manager.jobs), 2)
        self.assertIn('job_id', b)
        self.assertEqual(self.manager.queue_snapshot()['entries'][0]['progress']['percent'], 100)

    def test_missing_launch_recovers_once_and_closed_never_starts(self):
        a = self.add()
        a['status'] = 'starting'
        self.manager.training_queue['enabled'] = True
        self.manager._queue_save()
        self.manager.queue_tick()
        self.assertEqual(len(self.manager.jobs), 1)
        self.manager.queue_tick()
        self.assertEqual(len(self.manager.jobs), 1)
        self.manager.close()
        self.manager.queue_tick()
        self.assertEqual(len(self.manager.jobs), 1)

    def test_complete_event_without_owner_exit_is_reconnected(self):
        a = self.add()
        self.start()
        job = self.manager.jobs[a['job_id']]
        job['status'] = 'completed'
        job.pop('ended', None)
        self.manager.persist(job)
        self.manager.close()
        self.manager = tc.TrainingManager(Path(self.temp.name))
        with patch('training.durable_manager.threading.Thread') as thread:
            self.manager.reconnect_training()
            thread.assert_called_once()
            thread.return_value.start.assert_called_once()
        self.manager.queue_tick()
        self.assertEqual(len(self.manager.jobs), 1)
        self.assertTrue(self.manager.jobs[job['id']]['_monitor_thread'])
        self.manager.jobs[job['id']].pop('_monitor_thread')

    def test_teachers_latest_pt_and_order_and_deletion(self):
        a, b = self.add(WALK), self.add(STAND)
        c = self.add(JOINT, walk_teacher={'queue_entry':a['id']}, stand_teacher={'queue_entry':b['id']})
        with self.assertRaisesRegex(ValueError, '老师后面'):
            self.manager.queue_command({'action':'move','entry_id':c['id'],'direction':-1})
        with self.assertRaisesRegex(ValueError, '引用此老师'):
            self.manager.queue_command({'action':'remove','entry_id':a['id']})
        self.start()
        self.finish(a)
        self.manager.queue_tick()
        self.finish(b)
        self.manager.queue_tick()
        job = self.manager.jobs[c['job_id']]
        self.assertEqual(job['request']['joint']['walk']['checkpoint'], '/fixture/'+a['job_id']+'/model_1999.pt')
        self.assertEqual(job['request']['joint']['stand']['checkpoint'], '/fixture/'+b['job_id']+'/model_1999.pt')
        with self.assertRaisesRegex(ValueError, '队列正在引用'):
            self.manager.delete_model({'source_job':a['job_id'], 'checkpoint':'/fixture/'+a['job_id']+'/model_1999.pt'})
        self.manager.queue_command({'action':'clear'})
        self.assertEqual(len(self.manager.training_queue['entries']), 3, 'referenced teachers stay until consumer ends')

    def test_invalid_future_teacher_and_no_saved_pt_fail_clearly(self):
        a = self.add(WALK)
        with self.assertRaisesRegex(ValueError, '老师类型'):
            self.add(JOINT, walk_teacher={'queue_entry':a['id']}, stand_teacher={'queue_entry':a['id']})
        b = self.add(STAND)
        c = self.add(JOINT, walk_teacher={'queue_entry':a['id']}, stand_teacher={'queue_entry':b['id']})
        self.start()
        self.finish(a)['checkpoints'] = []
        self.manager.queue_tick()
        self.finish(b)
        self.manager.queue_tick()
        self.assertEqual(c['status'], 'failed')
        self.assertIn('没有保存PT', c['message'])
        self.assertFalse(self.manager.training_queue['enabled'])

    def test_reorder_remove_and_manual_train_guard(self):
        a, b = self.add(), self.add(STAND)
        self.manager.queue_command({'action':'move','entry_id':b['id'],'direction':-1})
        self.assertEqual(self.manager.training_queue['entries'][0]['id'], b['id'])
        self.manager.queue_command({'action':'remove','entry_id':a['id']})
        self.start()
        with self.assertRaisesRegex(ValueError, '队列正在执行'):
            self.manager.launch('train', {'task':WALK})

    def test_existing_manual_training_is_waited_for_and_never_stopped(self):
        jid=self.manager.launch('train', {'task':WALK})['job_id']
        a=self.add(STAND)
        with patch.object(self.manager,'stop') as stop:
            self.start()
            self.assertNotIn('job_id',a)
            job=self.manager.jobs[jid]
            job.update(status='completed',ended=time.time(),worker_exit_code=0)
            self.manager.queue_tick()
            self.assertIn('job_id',a)
            stop.assert_not_called()

    def test_early_pt_pruning_keeps_pending_queue_resume_source(self):
        jid=self.manager.launch('train', {'task':WALK})['job_id']
        job=self.manager.jobs[jid]
        job.update(status='completed',ended=time.time(),worker_exit_code=0)
        job['checkpoints']=[{'path':'/fixture/model_500.pt','iteration':500}]
        self.add(source_job=jid,checkpoint='/fixture/model_500.pt')
        self.assertEqual(self.manager.prune_early_models(),[])

    def test_cuda_600_message_does_not_guess_oom_or_hide_trace(self):
        trace = 'RuntimeError: Graph creation error: Warp CUDA error 600: device not ready'
        message = command_failure(1, [trace])
        self.assertIn('不能单独证明显存不足', message)
        self.assertIn(trace, message)
        self.assertIn('官方命令执行失败', command_failure(1, ['out of memory']))


if __name__ == '__main__':
    unittest.main()

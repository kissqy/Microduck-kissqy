"""Viewer replacement and training isolation. Real POSIX processes, no GPU."""
import io
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import training_console as tc
from training.session import SessionPool

PROFILE={'mode':'local','distro':'Ubuntu','repo':'/tmp'}
ENV={'ready':True,'revision':'a'*40,'tasks':[tc.DEFAULT_TASK]}

def until(predicate, seconds=5):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        if predicate():return
        time.sleep(.02)
    raise AssertionError('timed out waiting for lifecycle receipt')

class ReplacementTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.m=tc.BaseTrainingManager(Path(self.tmp.name));self.m.environment=ENV
        self.patch=patch.object(self.m,'_run');self.patch.start();self.addCleanup(self.patch.stop)
        self.train=self.m.launch('train',{})['job_id'];self.m.jobs[self.train]['status']='running'
        self.old=self.m.launch('preview',{})['job_id'];self.m.jobs[self.old]['status']='running'

    def test_valid_replacement_only_stops_viewer_and_invalid_preserves_it(self):
        with self.assertRaises(ValueError):self.m.launch('play',{'source_job':'bad','checkpoint':'bad'})
        self.assertEqual(self.m.jobs[self.old]['status'],'running')
        new=self.m.launch('preview',{})['job_id']
        self.assertEqual(self.m.jobs[new]['wait_for_viewers'],[self.old])
        self.assertEqual(self.m.jobs[self.old]['status'],'stopping')
        self.assertEqual(self.m.jobs[self.train]['status'],'running')
        with self.assertRaisesRegex(ValueError,'正在切换'):self.m.launch('preview',{})
        self.assertEqual(len(self.m.jobs),3)

    def test_replacement_waits_for_exit_not_terminal_event(self):
        new=self.m.launch('preview',{})['job_id'];job=self.m.jobs[new]
        self.m.jobs[self.old]['status']='stopped' # Receipt before pipe cleanup is insufficient.
        proc=SimpleNamespace(stdin=io.BytesIO(),stdout=io.BytesIO(b'MICRODUCK_TRAINING {"kind":"complete"}\n'),wait=lambda:0)
        with patch.object(self.m.sessions,'start',return_value=proc) as start:
            t=threading.Thread(target=tc.BaseTrainingManager._run,args=(self.m,job));t.start()
            time.sleep(.1);start.assert_not_called()
            self.m.jobs[self.old]['ended']=time.time();t.join(3)
            self.assertFalse(t.is_alive());start.assert_called_once()
            self.assertEqual(start.call_args.kwargs['channel'],'viewer')
        self.assertEqual(job['status'],'completed');self.assertEqual(self.m.jobs[self.train]['status'],'running')

    def test_cancel_pending_switch_does_not_start_or_stop_training(self):
        new=self.m.launch('preview',{})['job_id'];self.m.stop(new)
        with patch.object(self.m.sessions,'start') as start:
            tc.BaseTrainingManager._run(self.m,self.m.jobs[new]);start.assert_not_called()
        self.assertEqual(self.m.jobs[new]['status'],'stopped');self.assertIn('ended',self.m.jobs[new])
        self.assertEqual(self.m.jobs[self.train]['status'],'running')

    def test_late_command_cannot_resurrect_stopping_viewer(self):
        self.m.stop(self.old)
        self.m._event(self.m.jobs[self.old],{'kind':'command','argv':['viewer'],'cwd':'/tmp'})
        self.assertEqual(self.m.jobs[self.old]['status'],'stopping')

    def test_live_training_keeps_curves_when_old_model_selected(self):
        self.m.jobs[self.train]['metrics']=[{'iteration':42,'reward':12}]
        history={**self.m.jobs[self.train],'id':'history','status':'completed','created':1,'metrics':[{'iteration':1}]}
        self.m.jobs['history']=history
        snap=self.m.snapshot('history')
        self.assertEqual(next(j for j in snap['jobs'] if j['id']==self.train)['metrics'][0]['iteration'],42)

@unittest.skipUnless(sys.platform=='linux','Linux/WSL process isolation')
class RealIsolationTests(unittest.TestCase):
    def setUp(self):
        self.pool=SessionPool(tc.worker_command);self.addCleanup(self.pool.close)
        self.train=self.pool.start(PROFILE,b'import sys;print("TRAINING",flush=True);print(sys.stdin.readline().strip(),flush=True)')
        self.assertEqual(self.train.stdout.readline(),b'TRAINING\n')

    def assert_training_alive(self):
        self.assertIsNone(self.train.poll());self.train.stdin.write(b'TRAINING_CONTINUES\n')
        self.assertEqual(self.train.stdout.readline(),b'TRAINING_CONTINUES\n');self.assertEqual(self.train.wait(3),0)
        self.train.stdout.close()

    def test_kill_hung_viewer_also_kills_detached_child_only(self):
        source=("import subprocess,sys,time\n"
                "p=subprocess.Popen([sys.executable,'-u','-c','import time;time.sleep(60)'],start_new_session=True)\n"
                "print(p.pid,flush=True)\ntime.sleep(60)\n").encode()
        viewer=self.pool.start(PROFILE,source,channel='viewer');child=int(viewer.stdout.readline())
        viewer.kill();self.assertEqual(viewer.wait(3),-9)
        # The detached child inherited stdout: exit receipt requires it to close
        # that pipe as well, so killing just its parent cannot pass this test.
        self.assertEqual(viewer.stdout.read(),b'')
        viewer.stdout.close()
        again=self.pool.start(PROFILE,b'print("NEW_MODEL",flush=True)',channel='viewer')
        self.assertEqual(again.stdout.readline(),b'NEW_MODEL\n');self.assertEqual(again.wait(3),0);again.stdout.close()
        self.assertEqual(len(self.pool.sessions),2);self.assert_training_alive()

    def test_viewer_connection_loss_leaves_training_connection_alive(self):
        viewer=self.pool.start(PROFILE,b'import sys;print("VIEWER",flush=True);sys.stdin.read()',channel='viewer')
        self.assertEqual(viewer.stdout.readline(),b'VIEWER\n')
        viewer.session.proc.stdin.close();self.assertEqual(viewer.wait(3),0);viewer.stdout.close()
        self.assert_training_alive()

    def test_manager_watchdog_stops_unresponsive_viewer_without_blocking_state(self):
        with tempfile.TemporaryDirectory() as d:
            m=tc.BaseTrainingManager(Path(d));m.environment=ENV
            with patch.object(m,'_run'):jid=m.launch('preview',{})['job_id']
            viewer=self.pool.start(PROFILE,b'import time;print("READY",flush=True);time.sleep(60)',channel='viewer')
            self.assertEqual(viewer.stdout.readline(),b'READY\n')
            m.processes[jid]=viewer;m.jobs[jid]['status']='running'
            start=time.monotonic();m.stop(jid);m.snapshot()
            self.assertLess(time.monotonic()-start,.5)
            self.assertEqual(viewer.wait(9),-9);viewer.stdout.close()
            self.assert_training_alive()

if __name__=='__main__':unittest.main()

"""Real Linux processes: console detach/crash/reconnect cannot own training life."""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import training_console as tc
from training import durable_manager, durable_agent, worker

NATIVE_PROCFS = Path('/proc/self').is_dir() and os.readlink('/proc/self') == str(os.getpid())


def wait_until(predicate, timeout=6):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if predicate():return
        time.sleep(.025)
    raise AssertionError('condition timed out')


def fixture_payload(root, job, create):
    agent=Path(durable_agent.__file__).read_text().replace(
        "root=Path.home()/'.local/state/microduck-training-studio/jobs'",'root=Path('+repr(str(root))+')')
    request={'id':job['id'],'offset':job.get('durable_offset',0)}
    if create:
        request['source']='''import json,os,time
from pathlib import Path
stop=Path(WORKER_STOP_PATH);d=stop.parent
with (d/'launches').open('a') as f:f.write(str(os.getpid())+'\\n')
start=time.monotonic();step=0
while not stop.exists() and time.monotonic()-start<30:
    step+=1;(d/'heartbeat').write_text(str(step))
    print('MICRODUCK_TRAINING '+json.dumps({'kind':'metric','data':{'iteration':step,'reward':61,'total':10000}}),flush=True)
    time.sleep(.1)
print('MICRODUCK_TRAINING '+json.dumps({'kind':'stopped' if stop.exists() else 'complete','message':'fixture finished'}),flush=True)
'''
    return ('DURABLE_REQUEST='+repr(request)+'\nDURABLE_SOURCE='+repr(agent)+'\n'+agent).encode()


class DurableTrainingTests(unittest.TestCase):
    def job(self, root):
        return {'id':'c'*16,'op':'train','status':'starting','durable':True,'created':time.time(),
                'profile':{'mode':'local','distro':'Ubuntu','repo':str(root)},
                'request':{'task':tc.DEFAULT_TASK,'iterations':10000,'run_name':'fixture'},
                'logs':[],'metrics':[],'checkpoints':[]}

    def finish(self,directory):
        if directory.exists():
            (directory/'stop.request').touch()
            wait_until(lambda:durable_agent.state_at(directory).get('status')=='finished')

    def test_worker_stdin_eof_is_not_stop_in_durable_mode(self):
        with tempfile.TemporaryDirectory() as root:
            stop=Path(root)/'stop'
            worker.STOP.clear()
            with patch.dict(worker.__dict__,{'WORKER_STOP_PATH':str(stop)}):
                thread=threading.Thread(target=worker.controls,daemon=True);thread.start()
                self.assertFalse(worker.STOP.wait(.2))
                stop.touch();thread.join(1);self.assertTrue(worker.STOP.is_set())
            worker.STOP.clear()

    @unittest.skipUnless(NATIVE_PROCFS, 'PID namespace and /proc do not match; real Linux process ownership unavailable')
    def test_close_reopen_reconnect_and_explicit_stop_without_duplicate_training(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);remote=root/'linux';state=root/'desktop';job=self.job(root);directory=remote/job['id']
            managers=[]
            with patch.object(durable_manager,'monitor_payload',side_effect=lambda j,create=False:fixture_payload(remote,j,create)):
                try:
                    manager=tc.BaseTrainingManager(state);managers.append(manager)
                    manager.jobs[job['id']]=job;manager.persist(job)
                    threading.Thread(target=manager._run,args=(job,),daemon=True).start()
                    wait_until(lambda:job.get('monitor_connected') and len(job['metrics'])>2)
                    pid=durable_agent.state_at(directory)['pid']
                    manager.close()
                    self.assertFalse((directory/'stop.request').exists())
                    before=(directory/'heartbeat').read_text()
                    wait_until(lambda:(directory/'heartbeat').read_text()!=before)
                    again=tc.BaseTrainingManager(state);managers.append(again)
                    restored=again.jobs[job['id']]
                    self.assertEqual(restored['status'],'running')
                    again.reconnect_training();wait_until(lambda:restored.get('monitor_connected'))
                    self.assertEqual(durable_agent.state_at(directory)['pid'],pid)
                    self.assertEqual(len((directory/'launches').read_text().splitlines()),1)
                    # An attachment channel may die; it must reconnect without retraining.
                    broker=next(iter(again.sessions.sessions.values()))
                    broker.proc.kill()
                    count=len(restored['metrics'])
                    wait_until(lambda:len(restored['metrics'])>count)
                    self.assertTrue(durable_agent.alive(durable_agent.state_at(directory)))
                    again.stop(job['id'])
                    wait_until(lambda:durable_agent.state_at(directory).get('status')=='finished')
                    wait_until(lambda:restored.get('ended') is not None)
                    self.assertEqual(restored['status'],'stopped')
                    self.assertEqual(len((directory/'launches').read_text().splitlines()),1)
                finally:
                    self.finish(directory)
                    for manager in managers:manager.close()

    @unittest.skipUnless(NATIVE_PROCFS, 'PID namespace and /proc do not match; real Linux process ownership unavailable')
    def test_monitor_process_tree_kill_leaves_training_owner_alive(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);job=self.job(root);directory=root/'linux'/job['id']
            manager=tc.BaseTrainingManager(root/'desktop')
            try:
                proc=manager.sessions.start(job['profile'],fixture_payload(root/'linux',job,True),channel='training-monitor')
                # Drain output so the disposable monitor has no backpressure.
                threading.Thread(target=proc.stdout.read,daemon=True).start()
                wait_until(lambda:(directory/'heartbeat').exists())
                proc.kill();proc.wait(5)  # Broker recursively kills the monitor's descendants.
                manager.sessions.close()
                before=(directory/'heartbeat').read_text()
                wait_until(lambda:(directory/'heartbeat').read_text()!=before)
                self.assertTrue(durable_agent.alive(durable_agent.state_at(directory)))
            finally:self.finish(directory)

    def test_attach_missing_job_never_creates_training(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);job=self.job(root);manager=tc.BaseTrainingManager(root/'desktop')
            try:
                proc=manager.sessions.start(job['profile'],fixture_payload(root/'linux',job,False),channel='training-monitor')
                output=proc.stdout.read().decode();self.assertEqual(proc.wait(3),3)
                self.assertIn('durable_missing',output)
                self.assertFalse((root/'linux'/job['id']/'worker.py').exists())
            finally:manager.sessions.close()

    @unittest.skipUnless(NATIVE_PROCFS, 'PID namespace and /proc do not match; real Linux process ownership unavailable')
    def test_hard_killed_desktop_process_can_be_reopened(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);remote=root/'linux';directory=remote/('c'*16)
            script='''import sys,time,threading
from pathlib import Path
import training_console as tc
from training import durable_manager
from tests.test_durable_training import fixture_payload,DurableTrainingTests
root=Path(sys.argv[1]);remote=root/'linux'
durable_manager.monitor_payload=lambda j,create=False:fixture_payload(remote,j,create)
m=tc.BaseTrainingManager(root/'desktop');j=DurableTrainingTests().job(root)
m.jobs[j['id']]=j;m.persist(j)
threading.Thread(target=m._run,args=(j,),daemon=True).start()
while not j.get('monitor_connected'):time.sleep(.05)
print('READY',flush=True)
while True:time.sleep(1)
'''
            backend=subprocess.Popen([sys.executable,'-u','-c',script,str(root)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            reopened=None
            try:
                wait_until(lambda:(directory/'heartbeat').exists())
                wait_until(lambda:json.loads((root/'desktop/runs'/('c'*16)/'run.json').read_text()).get('monitor_connected'))
                backend.kill();backend.wait(3)  # No finally/close handler runs.
                before=(directory/'heartbeat').read_text()
                wait_until(lambda:(directory/'heartbeat').read_text()!=before)
                with patch.object(durable_manager,'monitor_payload',side_effect=lambda j,create=False:fixture_payload(remote,j,create)):
                    reopened=tc.BaseTrainingManager(root/'desktop');reopened.reconnect_training()
                    job=reopened.jobs['c'*16]
                    wait_until(lambda:job.get('monitor_connected'))
                    self.assertEqual(len((directory/'launches').read_text().splitlines()),1)
                    reopened.stop(job['id']);wait_until(lambda:job.get('ended') is not None)
                    self.assertEqual(job['status'],'stopped')
            finally:
                if backend.poll() is None:backend.kill();backend.wait(3)
                backend.stdout.close();backend.stderr.close()
                self.finish(directory)
                if reopened:reopened.close()

    def test_replayed_metrics_replace_existing_iteration(self):
        with tempfile.TemporaryDirectory() as temp:
            manager=tc.BaseTrainingManager(Path(temp));job=self.job(Path(temp))
            manager.jobs[job['id']]=job
            for step in (1,2,3,1,2,3,4):manager._event(job,{'kind':'metric','data':{'iteration':step,'reward':step}})
            self.assertEqual([p['iteration'] for p in job['metrics']],[1,2,3,4])


if __name__=='__main__':unittest.main()

"""Workbench protocol and lifecycle checks. No robot or GPU is accessed."""
import io
import json
import subprocess
import sys
import threading
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import training_console as tc
from training import runtime_adapter as adapter
from training import worker
from training.sim_protocol import SimulationControls

TASK = tc.DEFAULT_TASK
ENV = {'ready':True,'revision':'a'*40,'tasks':[TASK], 'configs':{TASK:{'rewards':[
    {'name':'track_velocity','weight':1,'editable':True},
    {'name':'action_rate','weight':-.1,'editable':False},
]}}}


class ControlsTests(unittest.TestCase):
    def test_stop_returns_and_state_is_readable_while_pipe_write_is_blocked(self):
        entered=threading.Event();release=threading.Event()
        class SlowPipe:
            def write(self,data):entered.set();release.wait(3)
            def flush(self):pass
        with tempfile.TemporaryDirectory() as directory,patch.object(tc.BaseTrainingManager,'_run'):
            m=tc.BaseTrainingManager(Path(directory));m.environment=ENV
            jid=m.launch('preview',{})['job_id'];m.jobs[jid]['status']='running'
            m.processes[jid]=SimpleNamespace(stdin=SlowPipe(),poll=lambda:None,wait=lambda timeout:release.wait(timeout))
            try:
                started=time.monotonic();m.stop(jid)
                self.assertLess(time.monotonic()-started,.5)
                self.assertTrue(entered.wait(1))
                self.assertEqual(m.snapshot()['jobs'][0]['status'],'stopping')
            finally:release.set();m.processes.pop(jid,None)

    @unittest.skipUnless(sys.platform=='linux','POSIX process group stop')
    def test_stop_watchdog_is_independent_of_a_blocked_control_writer(self):
        worker.STOP.clear()
        while not worker.CONTROL_QUEUE.empty():worker.CONTROL_QUEUE.get_nowait()
        worker.CONTROL_QUEUE.put({'op':'sim_control','padding':'x'*1000000})
        armed=threading.Event()
        def trigger():
            armed.wait(3)
            # Give the pipe writer time to fill the unread child stdin pipe.
            if not worker.STOP.wait(.15):worker.STOP.set()
        timer=threading.Thread(target=trigger);timer.start()
        try:
            with self.assertRaises(InterruptedError):
                worker.execute([sys.executable,'-u','-c',"import time;print('READY',flush=True);time.sleep(30)"],Path.cwd(),
                               on_line=lambda line:armed.set(),interactive=True,timeout=4)
        finally:
            worker.STOP.set();timer.join(timeout=4);worker.STOP.clear()
            while not worker.CONTROL_QUEUE.empty():worker.CONTROL_QUEUE.get_nowait()

    def test_receipt_distinguishes_expired_delivery_from_an_idle_policy(self):
        clock=[100.0];c=SimulationControls(lambda:clock[0])
        c.receive({'action':'move','velocity':[.2,0,0],'expires_at':99.7,'client':'browser_123','sequence':4})
        self.assertEqual(c.sample(),(0,0,0))
        self.assertEqual(c.status()['sequence'],4);self.assertTrue(c.status()['expired'])
        c.receive({'action':'move','velocity':[.2,0,0],'expires_at':100.7,'client':'browser_123','sequence':5})
        self.assertEqual(c.sample(),(.2,0,0));self.assertFalse(c.status()['expired'])

    @unittest.skipUnless(sys.platform=='linux','Linux supervisor pipe')
    def test_control_passes_through_real_supervisor_and_adapter_stdin(self):
        # Real bootstrap, raw supervisor reads, queue, writer and adapter pipe.
        # The adapter fixture samples SimulationControls; no GPU is emulated.
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);receiver=root/'receiver.py'
            receiver.write_text("import sys,json\nfrom training.sim_protocol import SimulationControls\n"
                                "c=SimulationControls()\nprint('RECEIVER_READY',flush=True)\n"
                                "for line in sys.stdin:\n c.receive(json.loads(line))\n"
                                " print('RECEIVED '+json.dumps({'velocity':c.sample(),'control':c.status()}),flush=True)\n"
                                " if json.loads(line).get('action')=='zero': break\n")
            # Import from the real project in both subprocesses.
            receiver.write_text('import sys\nsys.path.insert(0,'+repr(str(tc.ROOT))+')\n'+receiver.read_text())
            payload=("import sys,threading\nsys.path.insert(0,"+repr(str(tc.ROOT))+")\n"
                     "from training import worker\nthreading.Thread(target=worker.controls,daemon=True).start()\n"
                     "worker.execute([sys.executable,"+repr(str(receiver))+"],"+repr(str(root))+",on_line=lambda x:print(x,flush=True),timeout=8,interactive=True)\n").encode()
            proc=subprocess.Popen(tc.worker_command({'mode':'local'},len(payload)),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            try:
                proc.stdin.write(payload);proc.stdin.flush()
                import queue,threading
                lines=queue.Queue()
                threading.Thread(target=lambda:[lines.put(line.decode().strip()) for line in iter(proc.stdout.readline,b'')],daemon=True).start()
                self.assertEqual(lines.get(timeout=8),'RECEIVER_READY')
                for action,velocity,seq in [('move',[.2,0,0],1),('zero',[0,0,0],2)]:
                    msg={'op':'sim_control','action':action,'velocity':velocity,'expires_at':time.time()+.7,'client':'browser_123','sequence':seq}
                    proc.stdin.write((json.dumps(msg)+'\n').encode());proc.stdin.flush()
                    result=json.loads(lines.get(timeout=5).removeprefix('RECEIVED '))
                    self.assertEqual(result['velocity'],velocity)
                    if action=='move':self.assertEqual(result['control']['sequence'],seq)
                self.assertEqual(proc.wait(timeout=8),0)
            finally:
                if proc.poll() is None:proc.kill();proc.wait(timeout=5)
                proc.stdin.close();proc.stdout.close()

    def test_expired_or_disconnected_control_always_returns_zero(self):
        clock=[100.0];c=SimulationControls(lambda:clock[0])
        c.receive({'action':'move','velocity':[.2,-.1,.6],'expires_at':100.7})
        self.assertEqual(c.sample(),(.2,-.1,.6))
        clock[0]=100.8;self.assertEqual(c.sample(),(0,0,0))
        c.receive({'action':'move','velocity':[.3,0,0],'expires_at':100.5})
        self.assertEqual(c.sample(),(0,0,0),'a delayed command cannot revive expired movement')
        c.receive({'action':'move','velocity':[.2,0,0],'expires_at':102})
        c.close();self.assertEqual(c.sample(),(0,0,0))
        c.receive({'action':'move','velocity':[.2,0,0],'expires_at':102})
        self.assertEqual(c.sample(),(0,0,0))

    def test_pause_reset_cancel_velocity_and_actions_are_consumed_once(self):
        c=SimulationControls(lambda:10)
        c.receive({'action':'move','velocity':[.2,0,0],'expires_at':11})
        c.receive({'action':'pause'})
        self.assertEqual(c.sample(),(0,0,0));self.assertEqual(c.drain(),['pause']);self.assertEqual(c.drain(),[])
        c.receive({'action':'reset'});self.assertEqual(c.drain(),['reset'])

    def test_manager_routes_only_ready_simulation_and_drops_old_sequence(self):
        with tempfile.TemporaryDirectory() as d:
            m=tc.BaseTrainingManager(Path(d));stream=io.BytesIO()
            j={'id':'a'*16,'op':'play','status':'running','sim_controls':{'movement':True}}
            m.jobs[j['id']]=j;m.processes[j['id']]=SimpleNamespace(stdin=stream,poll=lambda:None)
            v={'job_id':j['id'],'client':'browser_123','sequence':2,'action':'move','velocity':[.2,0,0]}
            m.control(v)
            deadline=time.monotonic()+1
            while not stream.getvalue() and time.monotonic()<deadline: time.sleep(.005)
            first=stream.getvalue()
            self.assertEqual(json.loads(first)['velocity'],[.2,0,0])
            self.assertLessEqual(json.loads(first)['expires_at']-time.time(),.7)
            self.assertTrue(m.control({**v,'sequence':1})['ignored']);self.assertEqual(stream.getvalue(),first)
            for velocity in ([1,0,0],[True,0,0],[float('nan'),0,0]):
                with self.assertRaises(ValueError):m.control({**v,'sequence':3,'velocity':velocity})
            j['op']='train'
            with self.assertRaises(ValueError):m.control({**v,'sequence':4})
            j['op']='play';j['status']='stopped'
            with self.assertRaises(ValueError):m.control({**v,'sequence':4})
            for channel in m.control_channels.values(): channel.close()


class WorkbenchTests(unittest.TestCase):
    def test_resume_progress_uses_actual_start_and_finishes_at_100(self):
        j={'op':'train','status':'running','request':{'iterations':5},'created':10,'start_iteration':100,
           'metrics':[{'iteration':100,'total':105,'iteration_seconds':2}]}
        p=tc.progress_for(j,20)
        self.assertEqual((p['done'],p['total'],p['percent'],p['eta_seconds']),(1,5,20,8))
        j['metrics'].append({'iteration':104,'total':105,'iteration_seconds':4})
        self.assertEqual(tc.progress_for(j,20)['percent'],100)
        j['status']='completed';self.assertEqual(tc.progress_for(j,20)['eta_seconds'],0)
        j['status']='stopped';self.assertIsNone(tc.progress_for(j,20)['eta_seconds'])

    def test_parameters_are_real_known_config_fields(self):
        p=tc.validate_parameters({'actor_dims':[256,128],'activation':'lrelu','reward_weights':{'track_velocity':1.4}},ENV)
        self.assertEqual(p['actor_dims'],[256,128])
        for bad in [{'actor_dims':[True,64]},{'actor_dims':[4096]},{'activation':'unknown'},
                    {'reward_weights':{'unknown':1}}, {'reward_weights':{'action_rate':1}},
                    {'reward_weights':{'track_velocity':float('nan')}}]:
            with self.subTest(bad=bad),self.assertRaises(ValueError):tc.validate_parameters(bad,ENV)

    def test_configuration_changes_only_requested_values_and_respects_curriculum(self):
        cfg=SimpleNamespace(rewards={'track_velocity':SimpleNamespace(weight=1),'smooth':SimpleNamespace(weight=-.1)},
                            events={'push_robot':object(),'reset_base':object()},
                            curriculum={'smoothing':SimpleNamespace(params={'reward_name':'smooth'})})
        adapter.apply_env(cfg,{'reward_weights':{'track_velocity':2},'pushes':'off'})
        self.assertEqual(cfg.rewards['track_velocity'].weight,2)
        self.assertIn('reset_base',cfg.events);self.assertNotIn('push_robot',cfg.events)
        with self.assertRaisesRegex(ValueError,'课程'):adapter.apply_env(cfg,{'reward_weights':{'smooth':-1}})

    def test_saved_configuration_survives_restart(self):
        with tempfile.TemporaryDirectory() as d:
            m=tc.BaseTrainingManager(Path(d));m.environment=ENV
            m.save_preset({'name':'平地基线','parameters':{'actor_dims':[256,128],'reward_weights':{'track_velocity':2}}})
            restored=tc.BaseTrainingManager(Path(d))
            self.assertEqual(restored.presets[0]['name'],'平地基线')
            self.assertEqual(restored.presets[0]['parameters']['reward_weights'],{'track_velocity':2})
            self.assertFalse(restored.environment['ready'])

    def test_model_configuration_is_inherited_through_export_and_onnx(self):
        with tempfile.TemporaryDirectory() as d,patch.object(tc.BaseTrainingManager,'_run'):
            m=tc.BaseTrainingManager(Path(d));m.environment=ENV
            train=m.launch('train',{'actor_dims':[256,128],'label':'基线'})['job_id'];j=m.jobs[train]
            j.update(status='completed',revision=ENV['revision'],checkpoints=[{'iteration':4,'path':'/tmp/model_4.pt'}])
            exported=m.launch('export',{'source_job':train,'checkpoint':'/tmp/model_4.pt'})['job_id'];e=m.jobs[exported]
            self.assertEqual(e['request']['policy_parameters']['actor_dims'],[256,128])
            e.update(status='completed',revision=ENV['revision'],artifact='/tmp/exports/model.onnx',artifact_sha256='b'*64)
            onnx=m.launch('onnx',{'export_job':exported})['job_id'];o=m.jobs[onnx]
            self.assertEqual(o['request']['source_label'],'基线');self.assertEqual(o['request']['source_iteration'],4)
            self.assertEqual(o['request']['policy_parameters']['actor_dims'],[256,128])
            self.assertEqual(o['request']['onnx_sha256'],'b'*64)
            replacement=m.launch('preview',{})['job_id']
            self.assertEqual(m.jobs[replacement]['wait_for_viewers'],[onnx])
            self.assertEqual(o['status'],'stopping')
            self.assertEqual(j['status'],'completed')

    def test_resume_refuses_changed_network_and_inherits_missing_dimensions(self):
        with tempfile.TemporaryDirectory() as d,patch.object(tc.BaseTrainingManager,'_run'):
            m=tc.BaseTrainingManager(Path(d));m.environment=ENV
            source=m.launch('train',{'actor_dims':[256,128]})['job_id'];j=m.jobs[source]
            j.update(status='completed',revision=ENV['revision'],checkpoints=[{'iteration':4,'path':'/tmp/model_4.pt'}])
            v={'source_job':source,'checkpoint':'/tmp/model_4.pt'}
            with self.assertRaisesRegex(ValueError,'网络结构'):m.launch('train',{**v,'actor_dims':[512,256]})
            resumed=m.launch('train',v)['job_id'];self.assertEqual(m.jobs[resumed]['request']['actor_dims'],[256,128])

    def test_only_selected_and_comparison_metrics_are_transmitted(self):
        with tempfile.TemporaryDirectory() as d,patch.object(tc.BaseTrainingManager,'_run'):
            m=tc.BaseTrainingManager(Path(d));m.environment=ENV;ids=[]
            for i in range(4):
                jid=m.launch('train',{})['job_id'];m.jobs[jid].update(status='completed',metrics=[{'iteration':i,'reward':i}]);ids.append(jid)
            snap=m.snapshot(ids[0],[ids[1],ids[2]])
            by_id={j['id']:j for j in snap['jobs']}
            for jid in ids[:3]:self.assertTrue(by_id[jid]['metrics'])
            self.assertEqual(by_id[ids[3]]['metrics'],[])
            self.assertEqual(by_id[ids[3]]['latest_metric']['reward'],3)

    def test_actual_iteration_time_and_gpu_unsupported_fields_remain_honest(self):
        out=[];m=worker.Metrics(lambda kind,**v:out.append(v['data']))
        m.feed('Learning iteration 0/5');m.feed('Iteration time: 1.25s');m.feed('Total steps: 1536')
        self.assertEqual(out[-1]['iteration_seconds'],1.25);self.assertEqual(out[-1]['total_steps'],1536)
        with patch.object(worker.shutil,'which',return_value='/usr/bin/nvidia-smi'),patch.object(worker.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='0, [N/A], 1024, 16384, 51\n')):
            sample=worker.gpu_sample()['devices'][0]
        self.assertIsNone(sample['utilization']);self.assertEqual(sample['used_mb'],1024)


if __name__=='__main__':unittest.main()

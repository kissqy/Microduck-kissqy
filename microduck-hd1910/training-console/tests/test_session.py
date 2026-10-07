import hashlib
import io
import json
import subprocess
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
import training_console as tc
from training.session import SessionPool

PROFILE={'mode':'local','distro':'Ubuntu','repo':'/tmp'}

class SessionTests(unittest.TestCase):
    def setUp(self):
        self.starts=[]
        def command(profile,size):
            self.starts.append(dict(profile))
            return tc.worker_command({**profile,'mode':'local'},size)
        self.pool=SessionPool(command)

    def tearDown(self): self.pool.close()

    def test_reuses_connection_across_tasks_repos_and_child_failure(self):
        for i in range(4):
            result=self.pool.run({**PROFILE,'repo':f'/tmp/repo{i}'},f'print({i});raise SystemExit({7 if i==1 else 0})'.encode())
            self.assertEqual(result.returncode,7 if i==1 else 0)
            self.assertEqual(result.stdout.strip(),str(i).encode())
        self.assertEqual(len(self.starts),1)

    def test_two_children_controls_are_isolated(self):
        code=b'import sys;print("ready",flush=True);print(sys.stdin.readline().strip(),flush=True)'
        a=self.pool.start(PROFILE,code);b=self.pool.start(PROFILE,code)
        self.assertEqual(a.stdout.readline(),b'ready\n');self.assertEqual(b.stdout.readline(),b'ready\n')
        a.stdin.write(b'stop first\n');self.assertEqual(a.stdout.readline(),b'stop first\n');a.wait(3)
        self.assertIsNone(b.poll())
        b.stdin.write(b'still alive\n');self.assertEqual(b.stdout.readline(),b'still alive\n');b.wait(3)
        a.stdout.close();b.stdout.close()
        self.assertEqual(len(self.starts),1)

    def test_binary_model_package_through_reused_channel(self):
        with tempfile.TemporaryDirectory() as d:
            cp=Path(d)/'model_999.pt';cp.write_bytes(bytes(range(256))*4000)
            onnx=Path(d)/'model.onnx';onnx.write_bytes(b'onnx binary\x00\xff')
            req={'artifact':str(onnx),'sha256':hashlib.sha256(onnx.read_bytes()).hexdigest(),'checkpoint':str(cp)}
            code=Path('training/model_package.py').read_bytes()
            for _ in range(2):
                result=self.pool.run(PROFILE,code,json.dumps(req).encode())
                self.assertEqual(result.returncode,0,result.stdout)
                with zipfile.ZipFile(io.BytesIO(result.stdout)) as z:
                    self.assertEqual(z.read('checkpoint.pt'),cp.read_bytes());self.assertIsNone(z.testzip())
            self.assertEqual(len(self.starts),1)

    def test_distro_sessions_are_distinct_but_repo_changes_reuse(self):
        for distro,repo in [('Ubuntu','/tmp/a'),('Ubuntu','/tmp/b'),('Debian','/tmp/a')]:
            self.pool.run({'mode':'wsl','distro':distro,'repo':repo},b'print("ok")')
        self.assertEqual(len(self.starts),2)

    def test_disconnect_does_not_replay_job_next_request_reconnects(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'once'
            code=f'from pathlib import Path\nimport sys\np=Path({str(target)!r});p.write_text(p.read_text()+"x" if p.exists() else "x")\nprint("ready",flush=True)\nsys.stdin.read()'.encode()
            job=self.pool.start(PROFILE,code);self.assertEqual(job.stdout.readline(),b'ready\n')
            session=next(iter(self.pool.sessions.values()));session.proc.stdin.close()
            job.wait(5);session.proc.wait(5)
            self.pool.run(PROFILE,b'print("reconnected")')
            self.assertEqual(target.read_text(),'x');self.assertEqual(len(self.starts),2)
            job.stdout.close()

    def test_timeout_only_kills_target_channel_remains_usable(self):
        with self.assertRaises(subprocess.TimeoutExpired):
            self.pool.run(PROFILE,b'import time;time.sleep(30)',timeout=.1)
        result=self.pool.run(PROFILE,b'print("alive")')
        self.assertEqual(result.stdout,b'alive\n');self.assertEqual(len(self.starts),1)

    def test_manager_real_delete_reuses_session_and_closes_it(self):
        with tempfile.TemporaryDirectory() as d:
            m=tc.TrainingManager(Path(d)/'state')
            try:
                root=Path(d)/'repo';run=root/'logs/rsl_rl/run';run.mkdir(parents=True)
                for n in range(2):
                    cp=run/f'model_{n}.pt';cp.write_bytes(b'checkpoint')
                    jid=f'{n:016x}'
                    job={'id':jid,'op':'delete_model','status':'starting','created':time.time(),
                         'profile':{**PROFILE,'repo':str(root)},'request':{'op':'delete_model','repo':str(root),'model_path':str(cp),'model_kind':'pt'},
                         'logs':[],'metrics':[],'checkpoints':[]}
                    m.jobs[jid]=job;m.persist(job);m._run(job)
                    self.assertEqual(job['status'],'completed',job.get('message'));self.assertFalse(cp.exists())
                self.assertEqual(len(m.sessions.sessions),1)
                session=next(iter(m.sessions.sessions.values()))
            finally:m.close()
            self.assertIsNotNone(session.proc.poll())

if __name__=='__main__':unittest.main()

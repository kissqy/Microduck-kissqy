"""CPU checkpoint/save and real managed-file cleanup tests; no GPU training."""
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import training_console as tc
from training import checkpoint_policy, worker


class SavePolicyTests(unittest.TestCase):
    def test_boundaries_custom_runner_and_restore(self):
        class Runner:
            def save(self,path,*args,**kwargs):
                Path(path).write_text(json.dumps({'iter':self.current_learning_iteration,'kwargs':kwargs}))
        class CustomRunner(Runner):pass
        loader=lambda task:CustomRunner if task=='custom' else None
        official=NS(load_runner_cls=loader,MjlabOnPolicyRunner=Runner)
        restore=checkpoint_policy.install(official,Mock())
        with tempfile.TemporaryDirectory() as d:
            for role in ('default','custom'):
                root=Path(d)/role;root.mkdir()
                cls=official.load_runner_cls(role) or official.MjlabOnPolicyRunner
                runner=cls()
                for it in (0,1,4,500,998,999,1000,1499,2000):
                    runner.current_learning_iteration=it
                    runner.save(str(root/('model_%s.pt'%it)),infos={'keep':True})
                    self.assertEqual(runner.current_learning_iteration,it)
                    if it==999:
                        self.assertEqual(json.loads((root/'model_1000.pt').read_text())['iter'],999)
                self.assertEqual({p.name for p in root.iterdir()},{'model_1000.pt','model_1499.pt','model_2000.pt'})
                self.assertEqual(json.loads((root/'model_1000.pt').read_text())['kwargs'],{'infos':{'keep':True}})
        restore();self.assertIs(official.load_runner_cls,loader);self.assertIs(official.MjlabOnPolicyRunner,Runner)


class CleanupTests(unittest.TestCase):
    def owner(self,m,repo,key,iterations,status='completed'):
        root=repo/'logs/rsl_rl/exp'/key;root.mkdir(parents=True)
        cps=[]
        for i in iterations:
            p=root/('model_%s.pt'%i);p.write_bytes(('unique-'+str(i)).encode())
            cps.append({'path':str(p),'name':p.name,'iteration':i,'size':p.stat().st_size})
        job={'id':key,'op':'train','created':1,'status':status,'profile':{'mode':'local','distro':'Ubuntu','repo':str(repo)},
             'request':{'task':tc.DEFAULT_TASK,'iterations':1500},'metrics':[],'logs':[],'checkpoints':cps}
        m.jobs[key]=job;m.persist(job);return job

    def test_real_cleanup_moves_only_eligible_files_and_persists_records(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);m=tc.TrainingManager(root/'state')
            try:
                owner=self.owner(m,root/'engine','a'*16,[0,1,500,999,1000,1500])
                active=self.owner(m,root/'engine','b'*16,[1],status='running')
                protected=next(c['path'] for c in owner['checkpoints'] if c['iteration']==500)
                m.jobs['c'*16]={'id':'c'*16,'op':'train','created':1,'status':'completed','profile':owner['profile'],
                    'request':{'joint':{'walk':{'checkpoint':protected}}},'checkpoints':[],'metrics':[],'logs':[]}
                ids=m.prune_early_models();self.assertEqual(len(ids),1)
                self.assertEqual(m.prune_early_models(),[],'queued cleanup must not duplicate')
                deadline=time.monotonic()+10
                while not m.jobs[ids[0]].get('ended') and time.monotonic()<deadline:time.sleep(.02)
                clean=m.jobs[ids[0]];self.assertEqual(clean['status'],'completed',clean)
                self.assertEqual([c['iteration'] for c in owner['checkpoints']],[500,1000,1500])
                self.assertTrue(Path(active['checkpoints'][0]['path']).is_file())
                trash=root/'engine/logs/rsl_rl/.studio-trash'
                self.assertEqual(sorted(p.name for p in trash.glob('*/*.pt')),['model_0.pt','model_1.pt','model_999.pt'])
                saved=json.loads((m.directory/'runs'/owner['id']/'run.json').read_text())
                self.assertEqual(saved['checkpoints'],owner['checkpoints'])
                self.assertEqual(m.prune_early_models(),[])
            finally:
                for j in m.jobs.values():
                    if j['status']=='running':j['status']='completed'
                m.close()

    def test_worker_rejects_high_iterations_outside_paths_and_symlinks(self):
        with tempfile.TemporaryDirectory() as d,patch.object(worker,'emit'):
            repo=Path(d)/'engine';inside=repo/'logs/rsl_rl/exp/run';inside.mkdir(parents=True)
            low=inside/'model_1.pt';high=inside/'model_1000.pt';outside=Path(d)/'model_5.pt'
            for p in (low,high,outside):p.write_bytes(b'keep')
            with self.assertRaises(ValueError):worker.prune_early_models({'repo':str(repo),'model_paths':[str(low),str(high)]})
            self.assertTrue(low.exists());self.assertTrue(high.exists())
            with self.assertRaises(ValueError):worker.prune_early_models({'repo':str(repo),'model_paths':[str(outside)]})
            link=inside/'model_6.pt';link.symlink_to(outside)
            with self.assertRaises(ValueError):worker.prune_early_models({'repo':str(repo),'model_paths':[str(link)]})
            self.assertEqual(outside.read_bytes(),b'keep')


if __name__=='__main__':unittest.main()

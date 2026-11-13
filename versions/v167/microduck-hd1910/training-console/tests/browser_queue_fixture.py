"""Real queue/HTTP scheduler with explicitly simulated training completions."""
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.environ.get('TRAINING_BROWSER_SOURCE_ROOT', str(Path(__file__).resolve().parents[1])))
import training_console as tc
if os.environ.get('TRAINING_BROWSER_STATIC_ROOT'):
    tc.STATIC = Path(os.environ['TRAINING_BROWSER_STATIC_ROOT'])
from training.official_spec import ENGINE, REVISION, TASKS

directory = tempfile.TemporaryDirectory()
guard = patch.object(tc.BaseTrainingManager, '_run')
guard.start()
manager = tc.TrainingManager(Path(directory.name))
manager.computer_verified = True
manager.environment = {'ready': True, 'engine': ENGINE, 'revision': REVISION, 'status':'ready',
                       'tasks': list(TASKS), 'configs': {}, 'message':'Fixture without GPU'}
base = tc.handler_for(manager, 'queue-test-token')


class Handler(base):
    def do_POST(self):
        if self.path != '/fixture/finish':
            return super().do_POST()
        if not self.trusted() or self.headers.get('X-Training-Token') != 'queue-test-token':
            return self.reply({'error':'fixture token invalid'}, 403)
        value = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        with manager.lock:
            job = manager.jobs[value['job_id']]
            status = value.get('status', 'completed')
            job.update(status=status, ended=time.time(), worker_exit_code=0 if status == 'completed' else 1,
                       revision=REVISION, message='Fixture '+status)
            job['checkpoints'] = [{'path':'/fixture/'+job['id']+'/model_1000.pt','iteration':1000},
                                  {'path':'/fixture/'+job['id']+'/model_1999.pt','iteration':1999}]
            reference = json.loads((tc.ROOT/'data/task-configs'/(job['request']['task']+'.json')).read_text())['inspection']
            job['effective_config'] = {'resolved': reference}
            manager.persist(job)
            manager._queue_wake.set()
        self.reply({'okay':True})


server = tc.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
manager.start_queue_scheduler()
print('FIXTURE_READY '+str(server.server_port), flush=True)
try:
    server.serve_forever()
finally:
    manager.close()
    guard.stop()
    directory.cleanup()

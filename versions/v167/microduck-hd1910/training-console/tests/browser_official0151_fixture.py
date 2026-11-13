"""Local browser fixture; uses real HTTP handlers, never launches a training worker."""
import json
import tempfile
import threading
import time
import os
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0,os.environ.get('TRAINING_BROWSER_BACKEND_ROOT',str(Path(__file__).resolve().parents[1])))
import training_console as tc
if os.environ.get('TRAINING_BROWSER_STATIC_ROOT'):
    tc.STATIC=Path(os.environ['TRAINING_BROWSER_STATIC_ROOT'])
from training.official_spec import ENGINE,REVISION,TASKS,WALK,STAND
from test_v2_compatibility import old_job

directory=tempfile.TemporaryDirectory()
guard=patch.object(tc.BaseTrainingManager,'_run');guard.start()
manager=tc.TrainingManager(Path(directory.name));manager.computer_verified=True
manager.environment={'ready':True,'engine':ENGINE,'revision':REVISION,'status':'ready',
                     'message':'Browser fixture; no GPU process','tasks':list(TASKS),'configs':{}}
for task in (WALK,STAND):
    job=manager.jobs[manager.launch('train',{'task':task})['job_id']]
    job.update(status='completed',ended=time.time(),message='Fixture checkpoint',
               checkpoints=[{'path':'/fixture/'+task+'/model_1000.pt','name':'model_1000.pt','iteration':1000}])
    job['request']['training_action_scale']=1.0
    job['effective_config']={'resolved':json.loads((tc.ROOT/'data/task-configs'/(task+'.json')).read_text())['inspection']}
    if os.environ.get('TRAINING_BROWSER_LEGACY_FILTER') and task == STAND:
        # A saved pre-R1.5.21 model; current new-training API must not create EMA jobs.
        old_filter={'enabled':True,'head_alpha':.5,'legs_alpha':.7,'version':1}
        job['request'].update(label='历史滤波 fixture',training_action_scale=.7,training_firmware_p=3,action_filter=old_filter)
        job['effective_config'].update(training_action_scale=.7,training_firmware_p=3,action_filter=old_filter)
        resolved=job['effective_config']['resolved']
        resolved['full']['env']['actions']['joint_pos'].update(scale=.7,head_alpha=.5,legs_alpha=.7,filter_version=1)
        resolved['full']['env']['scene']['entities']['robot']['articulation']['actuators'][0]['kp_fw']=3.
        resolved['model']['actuators'][0]['kp_fw']=3.
        properties=resolved['model']['actuators'][0]['runtime_properties']
        properties['kp_fw']=3.;properties['duty_slope_per_rad']*=3/5
job=manager.jobs[manager.launch('train',{'task':WALK})['job_id']]
job.update(status='completed',request={**job['request'],'engine':'hd1910','label':'历史模型 fixture'},
           checkpoints=[{'path':'/fixture/legacy/model_5000.pt','iteration':5000}])
for task in (WALK,STAND):
    job=old_job(manager,task)
    job['request']['label']='V2 '+('行走' if task==WALK else '起身')+' fixture'
server=tc.ThreadingHTTPServer(('127.0.0.1',0),tc.handler_for(manager,'browser-fixture-token'))
manager.start_queue_scheduler()
print('FIXTURE_READY '+str(server.server_port),flush=True)
try:server.serve_forever()
finally:manager.close();guard.stop();directory.cleanup()

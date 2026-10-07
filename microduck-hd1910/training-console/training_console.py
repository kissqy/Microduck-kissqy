#!/usr/bin/env python3
"""Independent training dashboard; optional read-only ZERO calibration import."""
import argparse
import base64
import hashlib
import json
import math
import mimetypes
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from training.session import SessionPool
from training.control_channel import ControlChannel
from training.recipe import validate_training_action_scale, validate_training_firmware_p
from training.durable_manager import DurableTrainingMixin
from training.remote_ssh import RemoteTraining, RELEASE

ROOT = Path(__file__).resolve().parent
STATIC = ROOT/'training'/'static'
PREFIX = 'MICRODUCK_TRAINING '
DEFAULT_TASK = 'Mjlab-Velocity-Flat-MicroDuck'
VIEWER_OPS = ('preview','play','onnx')
PARAMETER_KEYS = ('actor_dims','critic_dims','activation','learning_rate','gamma','entropy','clip','seed','reward_weights','pushes','training_action_scale','action_filter','training_firmware_p')


def data_directory():
    if sys.platform == 'win32': base = Path(os.environ.get('LOCALAPPDATA') or Path.home()/'AppData'/'Local')
    elif sys.platform == 'darwin': base = Path.home()/'Library'/'Application Support'
    else: base = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home()/'.config')
    return base/'MicroduckTrainingStudio'


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def event_log_text(event):
    kind = event.get('kind')
    if kind == 'log': return event.get('line','')+'\n'
    if kind=='training_view_error':return '[训练画面] '+event.get('message','')+'\n'
    if kind == 'command':
        return '[运行目录] '+event.get('cwd','')+'\n[启动命令] '+json.dumps(event.get('argv',[]),ensure_ascii=False)+'\n'
    labels = {'failed':'任务失败','stopped':'任务停止','complete':'任务完成'}
    if kind in labels: return '['+labels[kind]+'] '+event.get('message','')+'\n'
    return ''


def validate_profile(value):
    if not isinstance(value, dict): raise ValueError('训练环境配置无效。')
    mode = value.get('mode', 'wsl' if sys.platform == 'win32' else 'local')
    distro, repo = str(value.get('distro', 'Ubuntu')).strip(), str(value.get('repo', '~/microduck_rl')).strip()
    if mode not in ('wsl', 'local'): raise ValueError('请选择 WSL 或 Linux 本机。')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', distro): raise ValueError('WSL 发行版名称无效。')
    if not repo or len(repo) > 1024 or any(ord(c) < 32 for c in repo): raise ValueError('请填写 Linux 中的仓库路径。')
    if not repo.startswith(('/', '~/')): raise ValueError('仓库路径应为 Linux 绝对路径或 ~/microduck_rl。')
    return {'mode': mode, 'distro': distro, 'repo': repo}


def validate_parameters(value, environment):
    if not isinstance(value, dict): raise ValueError('训练参数无效。')
    task = value.get('task', DEFAULT_TASK)
    if task not in environment.get('tasks', []): raise ValueError('所选任务不在本版官方任务列表中。')
    value={**value,'save_interval':1000}
    from training.recipe import validate_training_action_scale
    from training.action_filter import validate as validate_action_filter
    from training.official_spec import new_training_action_scale
    result = {'task': task, 'training_action_scale': validate_training_action_scale(value.get('training_action_scale', new_training_action_scale(task))), 'action_filter': validate_action_filter(value.get('action_filter'))}
    if value.get('training_firmware_p') is not None:
        result['training_firmware_p'] = validate_training_firmware_p(value['training_firmware_p'])
    for key, label, low, high, default in [('num_envs','并行环境数',1,8192,4096), ('iterations','新增迭代数',1,409600000,50000),
                                           ('save_interval','模型保存间隔',1,10000,1000)]:
        n = value.get(key, default)
        if type(n) is not int or not low <= n <= high: raise ValueError(label+'超出允许范围。')
        result[key] = n
    for key, label, low, high in [('learning_rate','学习率',1e-6,.01), ('gamma','折扣系数',.5,.99999),
                                  ('entropy','探索强度',0,.5), ('clip','PPO 裁剪',.01,.5)]:
        n = value.get(key)
        if n in (None, ''): result[key] = None;continue
        if type(n) not in (float, int) or not math.isfinite(n) or not low <= n <= high: raise ValueError(label+'无效。')
        result[key] = n
    seed = value.get('seed')
    if seed in (None, ''): result['seed'] = None
    elif type(seed) is int and 0 <= seed <= 2147483647: result['seed'] = seed
    else: raise ValueError('随机种子应为空或非负整数。')
    label = str(value.get('label','')).strip()
    if len(label) > 60 or any(ord(c) < 32 for c in label): raise ValueError('运行名称应在 60 字以内。')
    result['label'] = label
    for key in ('actor_dims','critic_dims'):
        dims = value.get(key)
        if dims in (None,'',[]): result[key] = None;continue
        if not isinstance(dims,list) or not 1 <= len(dims) <= 5 or any(type(n) is not int or not 16 <= n <= 2048 for n in dims):
            raise ValueError('隐藏层应为 1 至 5 个整数，每层 16 至 2048。')
        result[key] = dims
    activation = value.get('activation') or None
    if activation not in (None,'elu','relu','tanh','selu','lrelu','sigmoid'): raise ValueError('激活函数无效。')
    result['activation'] = activation
    pushes = value.get('pushes','default')
    if pushes not in ('default','off'): raise ValueError('随机推扰设置无效。')
    result['pushes'] = pushes
    weights = value.get('reward_weights',{})
    if not isinstance(weights,dict) or len(weights) > 150: raise ValueError('奖励权重配置无效。')
    schema = environment.get('configs',{}).get(task,{})
    available = {term['name']:term for term in schema.get('rewards',[])}
    for name, n in weights.items():
        if name not in available or not available[name].get('editable'): raise ValueError('奖励项不可编辑：'+str(name))
        if type(n) not in (float,int) or not math.isfinite(n) or abs(n)>1000: raise ValueError('奖励权重必须是 -1000 至 1000 的有限数值。')
    result['reward_weights'] = weights
    return result


def progress_for(job, now=None):
    if job.get('op') != 'train': return None
    points = job.get('metrics',[])
    last = points[-1] if points else {}
    total = job['request'].get('iterations') or last.get('total',0)
    start = job.get('start_iteration', points[0]['iteration'] if points else 0)
    done = min(total,max(0,last.get('iteration',start-1)-start+1))
    if job.get('status') == 'completed': done = total
    samples = [p['iteration_seconds'] for p in points[-20:] if type(p.get('iteration_seconds')) in (float,int) and p['iteration_seconds']>0]
    running = job.get('status') in ('starting','running')
    eta = (total-done)*sum(samples)/len(samples) if samples and running else None
    return {'done':done,'total':total,'percent':100*done/total if total else 0,
            'eta_seconds':0 if job.get('status') == 'completed' else eta,
            'elapsed_seconds':max(0,(job.get('ended') or now or time.time())-job['created'])}


def worker_command(profile, payload_length):
    # Exact raw reads leave every subsequent stop byte for the supervisor and
    # avoid a daemon holding Python's buffered stdin lock during interpreter exit.
    boot = ("import os\ncode=bytearray()\nwhile len(code)<%d:\n"
            " chunk=os.read(0,%d-len(code))\n"
            " if not chunk: raise SystemExit('Training worker input closed')\n"
            " code.extend(chunk)\n"
            "exec(compile(code,'<microduck-training-worker>','exec'))") % (payload_length,payload_length)
    if profile['mode'] == 'wsl':
        if sys.platform != 'win32' or not shutil.which('wsl.exe'):
            raise ValueError('没有找到 Windows WSL，请先安装 WSL2 Ubuntu；已有 Linux 环境可选择 Linux 本机。')
        return ['wsl.exe', '--distribution', profile['distro'], '--exec', 'python3', '-u', '-c', boot]
    if sys.platform != 'linux': raise ValueError('Linux 本机模式需要在 Linux 中启动训练台；Windows 请选 WSL。')
    return [sys.executable, '-u', '-c', boot]


class TrainingManager(DurableTrainingMixin):
    def __init__(self, directory=None):
        self.directory = directory or data_directory()
        self.lock = threading.RLock()
        self.jobs, self.processes, self.last_save = {}, {}, {}
        self.closed = False
        self.sessions = SessionPool(worker_command)
        self.environment = {'ready': False, 'status': 'unchecked', 'message': '本机检查一次后，所有训练项目共用缓存。'}
        self.environment_cache = {}
        try:
            self.environment_cache=json.loads((self.directory/'environments.json').read_text(encoding='utf-8'))
            if not isinstance(self.environment_cache,dict):self.environment_cache={}
        except (OSError,ValueError,TypeError):pass
        self.resources = {'devices':[],'received':None}
        self.presets = []
        self.control_sequences = {}
        self.pipe_locks = {}
        self.control_channels = {}
        self.profile = validate_profile({})
        try: self.profile = validate_profile(json.loads((self.directory/'profile.json').read_text(encoding='utf-8')))
        except (OSError, ValueError, TypeError): pass
        try:
            presets = json.loads((self.directory/'presets.json').read_text(encoding='utf-8'))
            if isinstance(presets,list): self.presets = presets[:40]
        except (OSError,ValueError): pass
        for path in sorted((self.directory/'runs').glob('*/run.json'), key=lambda p:p.stat().st_mtime, reverse=True):
            try:
                job = json.loads(path.read_text(encoding='utf-8'))
                if not isinstance(job, dict) or not re.fullmatch(r'[a-f0-9]{16}', job.get('id', '')): continue
                job.pop('_monitor_thread',None)
                if job.get('status') in ('starting', 'running', 'stopping'):
                    if job.get('durable') and job.get('op')=='train':
                        job.update(monitor_connected=False,message='等待接回 WSL 后台训练；不会重新启动训练。')
                    else:job.update(status='interrupted', message='上次训练台已退出；可从现有模型存档继续。')
                self.jobs[job['id']] = job
            except (OSError, ValueError): pass

    @staticmethod
    def environment_key(profile):
        return json.dumps({k:profile.get(k) for k in ('mode','distro','repo')},sort_keys=True)

    def remember_environment(self):
        if self.environment.get('ready'):
            self.environment_cache[self.environment_key(self.profile)]=json.loads(json.dumps(self.environment))
            save_json(self.directory/'environments.json',self.environment_cache)

    def restore_environment(self,profile,revision=None):
        env=self.environment_cache.get(self.environment_key(profile))
        if not isinstance(env,dict) or not env.get('ready') or revision and env.get('revision')!=revision:return False
        self.profile=dict(profile);self.environment=json.loads(json.dumps(env))
        self.environment['reused']=True
        self.environment['message']='已复用该环境的成功记录；未重复检查。'
        save_json(self.directory/'profile.json',self.profile)
        return True

    def prune_history(self):
        """Keep 10 detailed training records; keep model provenance separately."""
        with self.lock:
            for group in (True,False):
                ordered=sorted((j for j in self.jobs.values() if (j['op']=='train')==group),key=lambda j:j['created'],reverse=True)
                for job in ordered[10:]:
                    if job['status'] in ('starting','running','stopping') or job['id'] in self.processes or job.get('history_retired'):continue
                    job['history_retired']=True;job['logs']=[];job['metrics']=[]
                    self.persist(job)
                    for name in ('output.log','metrics.jsonl'):
                        path=self.directory/'runs'/job['id']/name
                        if path.is_file():path.unlink()

    def prune_early_models(self):
        """Queue recorded early PT files only; keep active and teacher references."""
        with self.lock:
            if self.closed:return []
            def strings(value):
                if isinstance(value,dict):
                    for child in value.values():yield from strings(child)
                elif isinstance(value,list):
                    for child in value:yield from strings(child)
                elif isinstance(value,str):yield value
            blocked=set()
            for job in self.jobs.values():
                if job.get('status') in ('starting','running','stopping'):
                    blocked.add(job['id']);blocked.update(strings(job.get('request',{})))
                for role in ('walk','stand'):
                    path=job.get('request',{}).get('joint',{}).get(role,{}).get('checkpoint')
                    if path:blocked.add(path)
            groups={}
            queue_entries=getattr(self,'training_queue',{}).get('entries',[])
            for entry in queue_entries:
                if entry['status'] not in ('waiting','starting','running','stopping'):continue
                blocked.update(strings(entry['request']))
                for role in ('walk','stand'):
                    dependency=entry['request'].get(role+'_teacher',{}).get('queue_entry')
                    prior=next((e for e in queue_entries if e['id']==dependency),None)
                    if prior and prior.get('job_id'):blocked.add(prior['job_id'])
            for owner in self.jobs.values():
                if owner['op']!='train' or owner['id'] in blocked:continue
                for cp in owner.get('checkpoints',[]):
                    path=cp.get('path','');match=re.fullmatch(r'model_(\d+)\.pt',Path(path).name)
                    if not match or int(match[1])>=1000 or path in blocked:continue
                    key=self.environment_key(owner['profile'])
                    group=groups.setdefault(key,{'profile':dict(owner['profile']),'paths':set()})
                    group['paths'].add(path)
            queued=[]
            for group in groups.values():
                jid=secrets.token_hex(8)
                request={**group['profile'],'op':'prune_models','model_paths':sorted(group['paths'])}
                job={'id':jid,'op':'prune_models','status':'starting','created':time.time(),'profile':group['profile'],
                     'request':request,'logs':[],'metrics':[],'checkpoints':[],'message':'正在清理1000轮以下PT…'}
                self.jobs[jid]=job;self.persist(job);queued.append(jid)
                threading.Thread(target=self._run,args=(job,),daemon=True).start()
            return queued

    def delete_model(self,value):
        with self.lock:
            if self.closed:raise ValueError('训练台正在退出。')
            exported=bool(value.get('export_job'));owner=self.jobs.get(value.get('export_job') if exported else value.get('source_job'))
            if not owner:raise ValueError('模型记录不存在。')
            if exported:
                if owner['op']!='export' or not owner.get('artifact'):raise ValueError('请选择实际导出的模型。')
                path=owner['artifact'];kind='onnx'
            else:
                cp=next((c for c in owner.get('checkpoints',[]) if c['path']==value.get('checkpoint')),None)
                if owner['op']!='train' or not cp:raise ValueError('请选择本台记录的检查点。')
                path=cp['path'];kind='pt'
            def references(obj):
                if isinstance(obj,dict):return any(references(v) for v in obj.values())
                if isinstance(obj,list):return any(references(v) for v in obj)
                return obj==path or obj==owner['id']
            for job in self.jobs.values():
                if job['status'] in ('starting','running','stopping') and (job is owner or references(job.get('request',{}))):
                    raise ValueError('有任务正在使用该模型，请先停止相关训练或仿真。')
            request={**owner['profile'],'op':'delete_model','model_owner':owner['id'],'model_path':path,'model_kind':kind}
            jid=secrets.token_hex(8)
            job={'id':jid,'op':'delete_model','status':'starting','created':time.time(),'profile':dict(owner['profile']),
                 'request':request,'logs':[],'metrics':[],'checkpoints':[],'message':'正在删除所选模型…'}
            self.jobs[jid]=job;self.persist(job)
            threading.Thread(target=self._run,args=(job,),daemon=True).start()
            return {'job_id':jid}

    def snapshot(self, selected=None, compare=None):
        self.prune_history()
        with self.lock:
            jobs = sorted(self.jobs.values(), key=lambda j:j['created'], reverse=True)
            current = next((j for j in jobs if j['id'] == selected), jobs[0] if jobs else None)
            training = next((j for j in jobs if j['op']=='train' and j['status'] in ('starting','running','stopping')), None)
            training = training or (current if current and current['op']=='train' else next((j for j in jobs if j['op']=='train'), None))
            # History metadata stays cheap; only the selected run carries its
            # curves/logs. Do not retransmit every old run on every poll.
            comparisons = set((compare or [])[:2])
            items = [{**j, 'metrics':j['metrics'] if j is training or j['id'] in comparisons else [],
                      'latest_metric':j['metrics'][-1] if j['metrics'] else None, 'progress':progress_for(j),
                      'logs':j['logs'] if j is current else []} for j in jobs]
            return json.loads(json.dumps({'profile':self.profile,'environment':self.environment,'jobs':items,
                                         'resources':self.resources,'presets':self.presets}))

    def save_preset(self, value):
        name = str(value.get('name','')).strip()
        if not name or len(name)>60 or any(ord(c)<32 for c in name): raise ValueError('请填写 1 至 60 字的配置名称。')
        with self.lock:
            parameters = validate_parameters(value.get('parameters'),self.environment)
            self.presets = [p for p in self.presets if p.get('name') != name]
            self.presets.insert(0,{'name':name,'parameters':parameters,'revision':self.environment.get('revision'),'updated':time.time()})
            self.presets = self.presets[:40]
            save_json(self.directory/'presets.json', self.presets)
        return {'okay':True}

    def persist(self, job):
        save_json(self.directory/'runs'/job['id']/'run.json', job)
        self.last_save[job['id']] = time.monotonic()

    def run_log(self, jid):
        with self.lock:
            job = self.jobs.get(jid)
            if not job: raise ValueError('没有找到这次任务的日志。')
            header = ['任务：'+jid, '操作：'+job['op'], '状态：'+job['status'],
                      '任务结果：'+job.get('message','')]
            if 'worker_exit_code' in job: header.append('工作进程退出码：'+str(job['worker_exit_code']))
            if job.get('cwd'): header.append('运行目录：'+job['cwd'])
            if job.get('argv'): header.append('启动命令：'+json.dumps(job['argv'],ensure_ascii=False))
            fallback = '\n'.join(job.get('logs',[])) or job.get('traceback','')
            path = self.directory/'runs'/jid/'output.log'
        # Read on demand, independently of the 160-line live snapshot. Include
        # the saved result even for old jobs that failed before logging began.
        output = path.read_text(encoding='utf-8',errors='replace') if path.is_file() else ''
        return '\n'.join(header)+'\n\n'+(output or fallback or '此任务没有保存进程输出；上方为已保存的错误和状态。')

    def set_execution_profile(self,value):
        self.profile=validate_profile(value)
        save_json(self.directory/'profile.json',self.profile)

    def launch(self, op, value):
        with self.lock:
            if self.closed: raise ValueError('训练台正在退出。')
            if op not in ('probe','setup','preflight','describe','train','preview','play','onnx','export'): raise ValueError('未知任务。')
            busy = [j for j in self.jobs.values() if j['status'] in ('starting','running','stopping')]
            previous_viewers = [j for j in busy if j['op'] in VIEWER_OPS] if op in VIEWER_OPS else []
            if any(j.get('wait_for_viewers') and j['status']=='starting' for j in previous_viewers):
                raise ValueError('正在切换仿真，请等待此次切换完成。')
            if op not in VIEWER_OPS and any(j['op'] == op for j in busy): raise ValueError('同类任务正在运行，请先停止或等待完成。')
            if op in ('probe','setup'):
                if busy: raise ValueError('请先结束当前任务，再切换或检查训练环境。')
                self.profile = validate_profile(value)
                save_json(self.directory/'profile.json', self.profile)
                self.environment_cache[self.environment_key(self.profile)]={'ready':False}
                save_json(self.directory/'environments.json',self.environment_cache)
                self.environment = {'ready': False, 'status': 'checking', 'message': '正在准备所选基线源码与依赖；进度见运行日志…' if op=='setup' else '正在检查 WSL、所选训练环境与 CUDA…'}
                request = {**self.profile, 'op': op}
            else:
                context=self.launch_context(op,value) if hasattr(self,'launch_context') else self.environment
                if not hasattr(self,'launch_context') and not context.get('ready'):
                    raise ValueError('请先让训练环境检查通过；页面打开不代表 GPU 已就绪。')
                request = {**self.profile, 'op': op, 'expected_revision': context['revision']}
                if op in ('train','preflight'): request.update(validate_parameters(value, context))
                if op in ('preview','describe'):
                    task = value.get('task', DEFAULT_TASK)
                    if task not in context.get('tasks',[]): raise ValueError('请选择环境检查返回的官方任务。')
                    request.update(task=task)
                    if op == 'preview':
                        from training.action_filter import validate as validate_action_filter
                        from training.official_spec import new_training_action_scale
                        request['preview_kind']='zero'
                        request['training_action_scale']=validate_training_action_scale(value.get('training_action_scale',new_training_action_scale(task)))
                        request['action_filter']=validate_action_filter(value.get('action_filter'))
                        if value.get('training_firmware_p') is not None:
                            request['training_firmware_p'] = validate_training_firmware_p(value['training_firmware_p'])
                if op in VIEWER_OPS:
                    if type(value.get('eval_pushes',False)) is not bool: raise ValueError('仿真扰动参数无效。')
                    request['eval_pushes'] = value.get('eval_pushes',False)
                source = value.get('source_job')
                if op in ('play','export') or (source and op in ('train','preflight')):
                    job = self.jobs.get(source)
                    chosen = next((c for c in (job or {}).get('checkpoints',[]) if c['path'] == value.get('checkpoint')), None)
                    if not job or job.get('op') != 'train' or not chosen: raise ValueError('请选择本台记录中的实际模型存档。')
                    if any(j['op']=='prune_models' and j['status'] in ('starting','running','stopping') and chosen['path'] in j['request']['model_paths'] for j in self.jobs.values()):
                        raise ValueError('此低轮数PT正在清理，请选择1000轮及以上模型。')
                    if hasattr(self,'validate_model_source'):
                        self.validate_model_source(job,op,context)
                    elif job.get('profile') != self.profile or job.get('revision') != context['revision']:
                        raise ValueError('模型存档与当前训练源码版本不同，请使用相同版本的训练环境。')
                    parameters = {key:job.get('effective_config',{}).get(key,job['request'].get(key)) for key in PARAMETER_KEYS}
                    parameters['reward_weights'] = parameters.get('reward_weights') or {}
                    request.update(task=job['request']['task'], checkpoint=chosen['path'],source_job=source,
                                   source_label=job['request'].get('label') or job['request'].get('run_name',source),
                                   source_iteration=chosen.get('iteration'),policy_parameters=parameters)
                    if op in ('train','preflight'):
                        from training.action_filter import validate as validate_action_filter
                        request['action_filter']=validate_action_filter(parameters.get('action_filter'))
                        # Resume preserves the source mapping, including older 1.0/0.7
                        # runs; a new trial default must never relabel those weights.
                        saved_scale = parameters.get('training_action_scale')
                        request['training_action_scale'] = validate_training_action_scale(1.0 if saved_scale is None else saved_scale)
                        request['training_firmware_p'] = parameters.get('training_firmware_p')
                        for key in ('actor_dims','critic_dims','activation'):
                            if request.get(key) and parameters.get(key) and request[key] != parameters[key]:
                                raise ValueError('继续训练必须沿用模型的网络结构；修改网络结构请新建训练。')
                            request[key] = parameters.get(key) or request.get(key)
                if op == 'onnx':
                    exported = self.jobs.get(value.get('export_job'))
                    if not exported or exported['op'] != 'export' or exported['status'] != 'completed' or not exported.get('artifact_sha256'):
                        raise ValueError('请选择本台已成功导出并记录校验值的 ONNX 模型。')
                    if hasattr(self,'validate_model_source'):
                        self.validate_model_source(exported,op,context)
                    elif exported['profile'] != self.profile or exported.get('revision') != context['revision']:
                        raise ValueError('ONNX 模型与当前训练环境或源码版本不同。')
                    origin = exported['request']
                    request.update(task=origin['task'],onnx_path=exported['artifact'],onnx_sha256=exported['artifact_sha256'],
                                   export_job=exported['id'],source_job=origin.get('source_job'),source_label=origin.get('source_label'),
                                   source_iteration=origin.get('source_iteration'),policy_parameters=origin.get('policy_parameters',{}))
                if op == 'train': request['run_name'] = 'console_'+time.strftime('%Y%m%d_%H%M%S')+'_'+secrets.token_hex(3)
            if hasattr(self,'decorate_request'): request = self.decorate_request(request,value)
            jid = secrets.token_hex(8)
            job = {'id': jid, 'op': op, 'status': 'starting', 'created': time.time(), 'profile': dict(self.profile),
                   'request': request, 'logs': [], 'metrics': [], 'checkpoints': [], 'message': '正在启动…'}
            if op=='train':job['durable']=True
            if previous_viewers:
                job['wait_for_viewers']=[j['id'] for j in previous_viewers]
                job['message']='正在切换模型，等待旧仿真释放资源…'
                for old in previous_viewers:self.stop(old['id'])
            self.jobs[jid] = job
            self.persist(job)
            thread = threading.Thread(target=self._run, args=(job,), daemon=True)
            thread.start()
            return {'job_id': jid}

    def _event(self, job, event):
        kind = event.get('kind')
        with self.lock:
            if kind == 'environment':
                job['environment_result'] = json.loads(json.dumps(event['data']))
                self.environment = {**event['data'], 'status': 'ready' if event['data'].get('ready') else 'unavailable'}
            elif kind == 'task_config':
                if hasattr(self,'remember_task_config'):self.remember_task_config(job,event['data'])
                else:
                    self.environment.setdefault('configs',{})[event['data']['task']] = event['data']
                    if job['op']=='describe':self.remember_environment()
            elif kind == 'effective_config': job['effective_config'] = event['data']
            elif kind == 'sample_clock': job['sample_clock'] = event['data']
            elif kind == 'gpu_sample': self.resources = {**event['data'],'received':time.time()}
            elif kind == 'training_view_ready' and job['op']=='train':
                url=event.get('url','')
                m=re.fullmatch(r'http://127\.0\.0\.1:(\d{4,5})',url)
                if m and 1024<=int(m[1])<=65535 and int(m[1]) not in (8090,8091,8092):
                    job['training_view_url']=url;job['training_view_envs']=event.get('num_envs')
            elif kind=='training_view_state' and job['op']=='train':job['training_view_state']=event.get('data',{})
            elif kind=='training_curriculum_state' and job['op']=='train':job['training_curriculum_state']={**event.get('data',{}),'received':time.time()}
            elif kind=='training_view_error' and job['op']=='train':job['training_view_error']=event.get('message','');job.pop('training_view_url',None)
            elif kind == 'viewer_ready':
                url = event.get('url','')
                m = re.fullmatch(r'http://127\.0\.0\.1:(\d{4,5})',url)
                if job['op'] in VIEWER_OPS and m and 1024 <= int(m[1]) <= 65535 and int(m[1]) not in (8090,8091):
                    job.update(viewer_url=url,sim_controls=event['controls'],viewer_checkpoint=event.get('model'),
                               viewer_iteration=job['request'].get('source_iteration'),message='物理仿真已就绪。')
            elif kind == 'sim_state': job['sim_state'] = {**event['data'],'received':time.time()}
            elif kind == 'identity': job['revision'] = event.get('revision')
            elif kind == 'command':
                job.update(argv=event['argv'],cwd=event['cwd'])
                if job['status']!='stopping':job.update(status='running',message='官方任务正在运行。')
            elif kind == 'log': pass
            elif kind == 'metric':
                data = event.get('data', {})
                if not isinstance(data, dict) or type(data.get('iteration')) is not int: return
                job.setdefault('start_iteration',data['iteration'])
                existing=next((i for i in range(len(job['metrics'])-1,-1,-1) if job['metrics'][i]['iteration']==data['iteration']),None)
                if existing is not None:job['metrics'][existing]=data
                elif not job['metrics'] or data['iteration']>job['metrics'][-1]['iteration']:job['metrics'].append(data)
                job['metrics'] = job['metrics'][-3000:]
            elif kind == 'checkpoints': job['checkpoints'] = [c for c in event['items'] if c['path'] not in job.get('deleted_checkpoints',[])]
            elif kind == 'model_removed':
                if job['op']=='prune_models' and event.get('path') in job['request']['model_paths']:
                    path=event['path']
                    for owner in self.jobs.values():
                        if owner['op']=='train' and owner['profile']==job['profile'] and any(c['path']==path for c in owner.get('checkpoints',[])):
                            owner['checkpoints']=[c for c in owner['checkpoints'] if c['path']!=path]
                            owner.setdefault('deleted_checkpoints',[]).append(path);self.persist(owner)
                owner=self.jobs.get(job['request'].get('model_owner'))
                path=job['request'].get('model_path')
                if owner and event.get('path')==path:
                    if job['request']['model_kind']=='pt':
                        owner['checkpoints']=[c for c in owner.get('checkpoints',[]) if c['path']!=path]
                        owner.setdefault('deleted_checkpoints',[]).append(path)
                    else:
                        owner['deleted_artifact']=path
                        for key in ('artifact','artifact_sha256','artifact_size'):owner.pop(key,None)
                    self.persist(owner)
            elif kind == 'viewer':
                url = event.get('url', '')
                m = re.fullmatch(r'http://127\.0\.0\.1:(\d{4,5})', url)
                if m and 1024 <= int(m[1]) <= 65535 and int(m[1]) not in (8090,8091): job['viewer_url'] = url
            elif kind == 'viewer_model':
                name = event.get('name','')
                m = re.fullmatch(r'model_(\d+)\.pt',name)
                if job['op'] == 'play' and m:
                    job.update(viewer_checkpoint=name, viewer_iteration=int(m[1]))
            elif kind == 'artifact': job.update(artifact=event.get('path'),artifact_sha256=event.get('sha256'),artifact_size=event.get('size'))
            elif kind in ('failed','stopped','complete'):
                job.update(status={'failed':'failed','stopped':'stopped','complete':'completed'}[kind], message=event.get('message',''))
            log_text = event_log_text(event)
            if log_text: job['logs'] = (job.get('logs',[]) + [line[:4000] for line in log_text.splitlines()])[-160:]
            if kind in ('identity','command','checkpoints','viewer','viewer_ready','viewer_model','artifact','failed','stopped','complete','environment','effective_config','task_config','sample_clock','training_view_ready','training_view_error') or (kind == 'metric' and time.monotonic()-self.last_save.get(job['id'],0) >= 2):
                self.persist(job)

    def _run(self, job):
        if job.get('durable') and job['op']=='train':
            self._run_durable(job);return
        proc = None
        try:
            deadline=time.monotonic()+15
            while job.get('wait_for_viewers'):
                with self.lock:
                    if self.closed or job['status']=='stopping':
                        job.update(status='stopped',message='已取消模型切换。');return
                    pending=[jid for jid in job['wait_for_viewers'] if not self.jobs[jid].get('ended')]
                if not pending:break
                if time.monotonic()>deadline:raise RuntimeError('旧仿真尚未退出，未启动新模型。训练任务不受此切换影响。请查看旧仿真日志。')
                time.sleep(.05)
            bundle = {name:(ROOT/'training'/name).read_text(encoding='utf-8') for name in ('runtime_adapter.py','recovery_evaluation.py','sample_alignment.py','checkpoint_policy.py','live_view.py','event_protocol.py','sim_protocol.py','recipe.py','official_spec.py','official_adapter.py','hd1910_actuator.py','hd1910_m6.json','deployment.py','action_filter.py','filtered_actions.py')}
            payload = ('WORKER_REQUEST = '+repr(job['request'])+'\nWORKER_BUNDLE = '+repr(bundle)+'\n'+(ROOT/'training'/'worker.py').read_text(encoding='utf-8')).encode('utf-8')
            with self.lock:
                if self.closed or job['status'] == 'stopping':
                    job.update(status='stopped', message='已取消启动。');self.persist(job);return
            proc = self.sessions.start(job['profile'],payload,channel='viewer' if job['op'] in VIEWER_OPS else 'jobs')
            with self.lock:
                self.processes[job['id']] = proc
                self.pipe_locks[job['id']] = threading.Lock()
                stop_requested=self.closed or job['status']=='stopping'
            if stop_requested:self._stop_process(job,proc)
            with (self.directory/'runs'/job['id']/'output.log').open('w', encoding='utf-8') as logfile:
                for raw in iter(proc.stdout.readline, b''):
                    line = raw.decode('utf-8', errors='replace').replace('\x00','').strip()
                    if not line: continue
                    if line.startswith(PREFIX):
                        try: event = json.loads(line[len(PREFIX):])
                        except ValueError: continue
                    else: event = {'kind':'log','line':line[:4000]}
                    self._event(job, event)
                    log_text = event_log_text(event)
                    if log_text: logfile.write(log_text);logfile.flush()
            code = proc.wait()
            with self.lock:
                job['worker_exit_code'] = code
                if job['status'] == 'stopping':
                    job.update(status='stopped', message='任务进程已停止；已保存的模型和记录保留。')
                elif job['status'] == 'completed' and code != 0:
                    job.update(status='failed', message='任务返回完成记录后异常退出（退出码 %s），未确认环境或训练成功。' % code)
                elif job['status'] not in ('failed','stopped','completed'):
                    if code == 0 and job['op'] == 'probe' and self.environment.get('status') != 'checking':
                        job.update(status='completed', message=self.environment['message'])
                    else:
                        detail = '进程没有返回任务完成记录。' if code == 0 else '进程异常退出，未返回任务结束记录。'
                        job.update(status='failed', message='训练环境进程已退出（退出码 %s）。%s 请导出运行记录查看完整日志。' % (code, detail))
        except Exception as exc:
            detail = traceback.format_exc()
            with self.lock:
                job.update(status='failed', message=str(exc), traceback=detail)
                job['logs'] = (job.get('logs', []) + detail.splitlines())[-160:]
            with (self.directory/'runs'/job['id']/'output.log').open('a', encoding='utf-8') as logfile:
                logfile.write(detail)
        finally:
            if proc:
                for stream in (proc.stdin, proc.stdout):
                    try: stream.close()
                    except (OSError, ValueError): pass
            with self.lock:
                self.processes.pop(job['id'], None)
                channel = self.control_channels.pop(job['id'], None)
                if channel: channel.close()
                self.pipe_locks.pop(job['id'], None)
                job['ended'] = time.time()
                if job['op'] in ('setup', 'probe'):
                    receipt = job.get('environment_result') or {}
                    okay = (job['status']=='completed' and job.get('worker_exit_code')==0
                            and receipt.get('ready') is True)
                    if okay:
                        self.environment = {**receipt, 'status':'ready'}
                        self.remember_environment()
                    else:
                        unavailable = job['status']=='completed' and receipt.get('ready') is False
                        self.environment = {**receipt, 'ready':False,
                            'status':'unavailable' if unavailable else 'failed',
                            'message':receipt.get('message',job['message']) if unavailable else job['message']}
                self.persist(job)


    def control(self, value):
        received_at = time.time()
        with self.lock:
            job = self.jobs.get(value.get('job_id'))
            if not job or job['op'] not in VIEWER_OPS or job['status'] != 'running' or not job.get('sim_controls'):
                raise ValueError('当前仿真尚未就绪，无法操作。')
            proc = self.processes.get(job['id'])
            if not proc or proc.poll() is not None: raise ValueError('仿真进程已退出。')
            action = value.get('action')
            if action not in ('move','zero','pause','resume','reset'): raise ValueError('不支持的仿真操作。')
            client, seq = value.get('client',''), value.get('sequence')
            if not re.fullmatch(r'[a-zA-Z0-9_-]{8,80}',client) or type(seq) is not int or not 0<=seq<2**53:
                raise ValueError('仿真操作序号无效。')
            identity = (job['id'],client)
            if seq <= self.control_sequences.get(identity,-1): return {'ignored':True}
            message = {'op':'sim_control','action':action,'expires_at':received_at+.7,'client':client,'sequence':seq}
            if action == 'move':
                if not job['sim_controls'].get('movement'): raise ValueError('当前任务不支持行走遥控。')
                velocity = value.get('velocity')
                if not isinstance(velocity,list) or len(velocity)!=3 or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>limit for v,limit in zip(velocity,(.4,.3,1.0))):
                    raise ValueError('仿真速度超出范围。')
                message['velocity'] = velocity
            channel = self.control_channels.get(job['id'])
            if channel is None:
                pipe_lock = self.pipe_locks.setdefault(job['id'],threading.Lock())
                channel = self.control_channels[job['id']] = ControlChannel(proc, pipe_lock)
            channel.submit(message)
            self.control_sequences[identity] = seq
            if len(self.control_sequences)>128:
                self.control_sequences = {identity:seq}
            # This is a queue receipt. Actual application is reported by sim_state.
            return {'okay':True, 'queued':True, 'sequence':seq}

    def stop(self, jid):
        with self.lock:
            job = self.jobs.get(jid)
            if not job: raise ValueError('没有找到此任务。')
            if job['status'] not in ('starting','running'): return
            job.update(status='stopping', message='正在停止本任务；保留最近已保存的模型。')
            channel = self.control_channels.pop(jid, None)
            if channel: channel.close()
            proc = self.processes.get(jid)
            pipe_lock = self.pipe_locks.setdefault(jid,threading.Lock())
            self.persist(job)
        if proc and proc.poll() is None:self._stop_process(job,proc)

    def _stop_process(self,job,proc):
        # Never wait on transport or process exit from an HTTP/state-lock thread.
        pipe_lock=self.pipe_locks.setdefault(job['id'],threading.Lock())
        def send_stop():
            with pipe_lock:
                try:proc.stdin.write(b'{"op":"stop"}\n');proc.stdin.flush()
                except (OSError,ValueError):pass
        threading.Thread(target=send_stop,daemon=True).start()
        if job['op'] in VIEWER_OPS:
            def watchdog():
                try:proc.wait(timeout=6)
                except subprocess.TimeoutExpired:
                    with self.lock:
                        if self.processes.get(job['id']) is not proc:return
                    try:proc.kill()
                    except (OSError,ValueError):pass
            threading.Thread(target=watchdog,daemon=True).start()

    def close(self):
        with self.lock:
            self.closed = True
            ids = [jid for jid in self.processes if not self.jobs[jid].get('durable')]
        for jid in ids: self.stop(jid)
        deadline = time.monotonic()+13
        with self.lock: processes = [proc for jid,proc in self.processes.items() if not self.jobs[jid].get('durable')]
        for proc in processes:
            try: proc.wait(timeout=max(.1, deadline-time.monotonic()))
            except subprocess.TimeoutExpired:
                # Closing stdin asks the Linux supervisor to clean up its own group.
                try: proc.stdin.close()
                except (OSError, ValueError): pass

        self.sessions.close()


from studio import enhance
BaseTrainingManager = TrainingManager
TrainingManager = enhance(TrainingManager, save_json)


def handler_for(manager, token):
    remote = getattr(manager, 'remote', None)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass

        def trusted(self):
            port = self.server.server_port
            host = self.headers.get('Host','')
            return host in ('127.0.0.1:'+str(port),'localhost:'+str(port)) and self.headers.get('Origin', 'http://'+host) == 'http://'+host

        def reply(self, value, status=200, mime='application/json'):
            body = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', mime if mime=='application/zip' else mime+'; charset=utf-8')
            if mime=='application/zip': self.send_header('Content-Disposition','attachment; filename='+('Microduck-Policy.zip' if self.path.startswith('/api/model.zip') else 'Microduck-Training-Record.zip'))
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('X-Frame-Options','DENY')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-src http://127.0.0.1:* http://localhost:*; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            try: self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError): pass

        def do_GET(self):
            if not self.trusted(): return self.reply({'error':'禁止跨来源访问。'},403)
            parsed = urlparse(self.path)
            path = parsed.path
            if path == '/api/remote/state':
                return self.reply(remote.snapshot() if remote else {'target':'local','status':'disconnected'})
            if path.startswith('/api/') and path not in ('/api/config', '/api/task-reference') and remote and remote.target == 'ssh':
                try:
                    body, status, mime = remote.proxy(self.path)
                    return self.reply(body, status, mime)
                except (ValueError, OSError) as error:
                    return self.reply({'error':str(error)}, 503)
            if path == '/api/state':
                query = parse_qs(parsed.query)
                return self.reply(manager.snapshot(query.get('selected',[None])[0],query.get('compare',[''])[0].split(',')))
            if path == '/api/config': return self.reply({'token': token, 'version':'Studio R1.5.17 · 固件0.15.1 · 翻身检查', 'platform':sys.platform, 'release':RELEASE, 'remote_workspace':os.environ.get('MICRODUCK_REMOTE_WORKSPACE','')})
            if path == '/api/studio': return self.reply(manager.studio_state())
            if path == '/api/task-reference':
                task=parse_qs(parsed.query).get('task',[''])[0]
                from training.official_spec import TASKS
                if task not in TASKS:return self.reply({'error':'未知任务。'},400)
                return self.reply(json.loads((ROOT/'data/task-configs'/(task+'.json')).read_text(encoding='utf-8')))
            if path == '/api/model.zip':
                try: return self.reply(manager.model_download(parse_qs(parsed.query).get('job',[''])[0]),mime='application/zip')
                except (ValueError,OSError,subprocess.SubprocessError) as e: return self.reply({'error':'模型下载失败：'+str(e)},400)
            if path == '/api/report.zip':
                try: return self.reply(manager.report_zip(parse_qs(parsed.query).get('job',[None])[0]),mime='application/zip')
                except ValueError as e: return self.reply({'error':str(e)},400)
            if path == '/api/log':
                try:
                    text = manager.run_log(parse_qs(parsed.query).get('job',[None])[0])
                    return self.reply(text.encode('utf-8'),mime='text/plain')
                except ValueError as e: return self.reply({'error':str(e)},404)
                except OSError as e: return self.reply({'error':'读取已保存日志失败：'+str(e)},500)
            if path == '/api/sim/state':
                jid = parse_qs(parsed.query).get('job_id',[None])[0]
                with manager.lock:
                    job = manager.jobs.get(jid)
                    if not job or job['op'] not in VIEWER_OPS or job['status'] != 'running':
                        return self.reply({'error':'仿真已停止。'},404)
                    return self.reply(job.get('sim_state',{}))
            names = {'/remote.js':'remote.js','/remote.css':'remote.css','/':'index.html','/training.css':'training.css','/tasks.js':'tasks.js','/training.js':'training.js','/sample_alignment.js':'sample_alignment.js','/studio.js':'studio.js','/studio.css':'studio.css','/workflow.js':'workflow.js','/teachers.js':'teachers.js','/queue.js':'queue.js','/queue.css':'queue.css','/workflow.css':'workflow.css'}
            name = names.get(path)
            if not name: return self.reply({'error':'没有此页面。'},404)
            p = STATIC/name
            mime = 'text/javascript' if p.suffix == '.js' else mimetypes.guess_type(p.name)[0] or 'text/plain'
            return self.reply(p.read_bytes(), mime=mime)

        def do_POST(self):
            if not self.trusted() or not secrets.compare_digest(self.headers.get('X-Training-Token',''), token):
                return self.reply({'error':'页面凭据无效，请刷新训练台。'},403)
            try:
                size = int(self.headers.get('Content-Length','0'))
                if not 0 < size <= 45*1024*1024 or self.headers.get_content_type() != 'application/json' or self.headers.get('Transfer-Encoding'):
                    raise ValueError('请求格式无效。')
                self.connection.settimeout(3)
                value = json.loads(self.rfile.read(size))
                if not isinstance(value, dict): raise ValueError('请求应为对象。')
                if self.path.startswith('/api/remote/'):
                    if not remote: raise ValueError('当前服务未配置SSH连接管理。')
                    if self.path == '/api/remote/configure': return self.reply(remote.configure(value))
                    if self.path == '/api/remote/select': return self.reply(remote.select(value))
                    if self.path == '/api/remote/connect': return self.reply(remote.start('connect'))
                    if self.path == '/api/remote/deploy': return self.reply(remote.start('deploy'))
                    if self.path == '/api/remote/trust-host': return self.reply(remote.trust_pending_host(value))
                    if self.path == '/api/remote/wsl-test': return self.reply(remote.start_wsl_test(value))
                    if self.path == '/api/remote/server-restore': return self.reply(remote.restore_server())
                    if self.path == '/api/remote/disconnect':
                        if remote.operation: raise ValueError('请等待连接或部署完成。')
                        return self.reply(remote.disconnect())
                    return self.reply({'error':'没有此服务器操作。'},404)
                if remote and remote.target == 'ssh':
                    if self.path == '/api/calibration/zero':
                        # ZERO is reached from the user's desktop; only its validated
                        # calibration is transferred to the training server.
                        result = manager.import_zero_calibration(value)
                        payload = {'name':result['calibration']['source'], 'text':json.dumps(result['calibration']['data'])}
                        body, status, mime = remote.proxy('/api/calibration/import', payload)
                    else:
                        body, status, mime = remote.proxy(self.path, value)
                    return self.reply(body, status, mime)
                if self.path == '/api/models/import':
                    from training.model_import import import_model
                    return self.reply(import_model(manager, value, ROOT))
                if self.path == '/api/model/content':
                    jid = value.get('job_id')
                    if not isinstance(jid,str) or not re.fullmatch(r'[a-f0-9]{16}',jid):
                        raise ValueError('模型记录编号无效。')
                    data = manager.model_download(jid)
                    if not data.startswith(b'PK\x03\x04'): raise ValueError('模型包不是有效 ZIP。')
                    # JSON transport deliberately has no attachment header or ZIP URL.
                    return self.reply({'filename':'Microduck-Policy-'+jid+'.zip',
                                       'encoding':'base64','size':len(data),
                                       'sha256':hashlib.sha256(data).hexdigest(),
                                       'data':base64.b64encode(data).decode('ascii')})
                if self.path == '/api/models/delete':return self.reply(manager.delete_model(value))
                if self.path == '/api/models/prune':return self.reply({'jobs':manager.prune_early_models()})
                if self.path == '/api/stop': manager.stop(value.get('job_id'));return self.reply({'okay':True})
                if self.path == '/api/queue/add': return self.reply(manager.queue_add(value))
                if self.path == '/api/queue/control': return self.reply(manager.queue_command(value))
                if self.path == '/api/sim/control': return self.reply(manager.control(value))
                if self.path == '/api/presets': return self.reply(manager.save_preset(value))
                if self.path == '/api/recipe': return self.reply(manager.save_recipe(value))
                if self.path == '/api/calibration/import': return self.reply(manager.import_calibration(value))
                if self.path == '/api/calibration/zero': return self.reply(manager.import_zero_calibration(value))
                if self.path == '/api/calibration/bundled': return self.reply(manager.import_bundled_calibration())
                if self.path == '/api/recipe/archive': return self.reply(manager.archive_recipe(value))
                if self.path == '/api/environment/select':return self.reply(manager.select_environment(value))
                if self.path == '/api/start-checks': return self.reply(manager.start_checks(value))
                ops = {'/api/setup':'setup','/api/preflight':'preflight','/api/probe':'probe','/api/describe':'describe','/api/train':'train','/api/preview':'preview','/api/play':'play','/api/onnx':'onnx','/api/export':'export'}
                op = ops.get(self.path)
                if not op: return self.reply({'error':'没有此操作。'},404)
                return self.reply(manager.launch(op,value))
            except (ValueError, TypeError) as exc: return self.reply({'error':str(exc)},400)
            except Exception as exc: return self.reply({'error':'无法执行请求：'+str(exc)},500)
    return Handler


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8092)
    parser.add_argument('--open', action='store_true')
    parser.add_argument('--data-dir', type=Path, help='独立训练记录目录')
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535: parser.error('端口无效。')
    manager = TrainingManager(directory=args.data_dir)
    manager.remote = RemoteTraining(manager.directory, ROOT, manager, save_json)
    try: server = ThreadingHTTPServer(('127.0.0.1',args.port),handler_for(manager,secrets.token_urlsafe(32)))
    except OSError:
        print('训练台端口已被中控占用，请打开现有页面。更新界面时覆盖原目录 training/static，再刷新浏览器。',flush=True);return 2
    server.daemon_threads = True
    print('Microduck Training Studio R1.5.17 · 固件0.15.1 · 独立训练中控\nhttp://127.0.0.1:%s\n不需要 Zero；本机首次检查后共用缓存，加入队列后点击开始训练。打开页面不会自动训练。\n本版修复倒地老师的评估课程并新增翻身检查，需要运行完整新版后端。' % args.port, flush=True)
    try:
        manager.reconnect_training()
        manager.start_queue_scheduler()
        if args.open: webbrowser.open('http://127.0.0.1:'+str(args.port))
        server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt: pass
    finally: server.server_close();manager.remote.close();manager.close()


if __name__ == '__main__':
    raise SystemExit(main())

"""Preparation, calibration evidence and immutable per-run recipes."""
import copy
import csv
import hashlib
import io
import json
import math
import platform
import re
import subprocess
import sys
import threading
import time
import zipfile
from pathlib import Path
from training.recipe import digest, SERVO_MASS_PROFILE, MASS_CLOSURE_PROFILE, validate_servo_mass, validate_training_action_scale
from training.official_spec import ENGINE, PIN, REVISION, RUNTIME_VERSION, JOINT_TASKS, TEACHER_TASKS, TRAINING_ADAPTER_REVISION, current_request, legacy_v2_request, model_task, training_origin, compatibility_label, normalize_model_recipe, physical_recipe, contract as teacher_contract
from training import zero_calibration
from training.official_spec import ignored_legacy_bam_overrides
from training.training_queue import TrainingQueueMixin

ROOT=Path(__file__).resolve().parent
PINS=json.loads((ROOT/'data/pins.json').read_text(encoding='utf-8'))
ACTIVE=('starting','running','stopping')
TASK_CATALOG=json.loads((ROOT/'data/tasks.json').read_text(encoding='utf-8'))
TASKS={t['id']:t for t in TASK_CATALOG['tasks']}


def fresh_recipe():
    recipe = json.loads((ROOT/'examples/recipe-official-0151.json').read_text(encoding='utf-8'))
    recipe['version'] = 1
    recipe['training_action_scale'] = 0.9
    return recipe


def recipe_digest(recipe):
    values={k:recipe.get(k) for k in ('baseline','purpose','overrides','robot')} | {'calibration':(recipe.get('calibration') or {}).get('data')}
    extra={k:v for k,v in recipe.get('task_overrides',{}).items() if v}
    if extra:values['task_overrides']=extra
    return digest(values)


def simulation_recipe_digest(recipe):
    """Encoder/IMU calibration is deployment metadata, not simulated physics."""
    return recipe_digest({**recipe,'calibration':None})


def task_profile(profile, engine=ENGINE):
    """New jobs use the single official checkout; historic runs retain their paths."""
    profile=dict(profile)
    repo=str(profile.get('repo','')).rstrip('/')
    marker='microduck-training-studio/engines/'
    if marker in repo:
        profile['repo']=repo.split(marker,1)[0]+marker+'official_0151'
    elif repo in ('~/microduck_rl',''):
        profile['repo']=PIN['repo']
    return profile


def parse_calibration(text,name):
    if len(text.encode())>40*1024*1024: raise ValueError('文件太大。')
    source_hash=hashlib.sha256(text.encode()).hexdigest()
    if name.lower().endswith('.toml'):
        try:
            import tomllib
        except ModuleNotFoundError:
            # Python 3.10 has no stdlib TOML parser. The bundled pure-Python
            # fallback keeps calibration import offline and install-free.
            from training._vendor import tomli as tomllib
        raw=tomllib.loads(text)
        origin='标定文件导入'
    else:
        raw=json.loads(text)
        origin='JSON导入'
        if isinstance(raw,dict) and isinstance(raw.get('frames'),list):
            frames=[f for f in raw['frames'] if isinstance(f.get('calibration'),dict) and f['calibration'].get('joints')]
            if not frames: raise ValueError('这份录制没有完整 calibration.joints，不能用“已标定”状态还原零点。请导入 hd1910-calibration.toml 或含完整标定的录制。')
            f=frames[-1]; raw=f['calibration']; origin='录制缓存标定；帧时间 '+str(f.get('at'))+'，缓存年龄 '+str(f.get('channels',{}).get('calibration',{}).get('age_ms'))+' ms'
    if 'calibration' in raw and isinstance(raw['calibration'],dict):raw=raw['calibration']
    rows=raw.get('joints')
    if not isinstance(rows,list) or len(rows)!=15: raise ValueError('需要包含15个关节的完整标定。')
    seen=set(); names=set()
    expected={j['name']:j['id'] for j in json.loads((ROOT/'data/hardware.json').read_text())['joints']}
    for row in rows:
        sid=row.get('id');direction=row.get('direction');zero=row.get('zero_raw');name_=row.get('name')
        if type(sid)is not int or sid in seen or sid not in [*range(10,15),*range(20,25),*range(30,35)]:raise ValueError('ID列表不完整或重复。')
        if not isinstance(name_,str) or name_ in names:raise ValueError('关节名称缺失或重复。')
        if expected.get(name_)!=sid:raise ValueError('关节名称与本机ID映射不符：'+str(name_))
        if direction not in [-1,1] or type(zero)is not int or not 0<=zero<=4095:raise ValueError('方向或编码器零点无效。')
        lo,hi=row.get('min_rad'),row.get('max_rad')
        if any(type(v)not in(int,float) or not math.isfinite(v) for v in (lo,hi)) or lo>=hi:raise ValueError('关节限位无效。')
        seen.add(sid);names.add(name_)
    quat=raw.get('imu_mount_quat')
    if not isinstance(quat,list) or len(quat)!=4 or any(type(v) not in(int,float) or not math.isfinite(v) for v in quat):
        raise ValueError('完整标定需要 imu_mount_quat=[w,x,y,z]。')
    if abs(sum(v*v for v in quat)-1)>0.02:raise ValueError('IMU安装四元数未归一化。')
    return {'data':raw,'source':name,'source_sha256':source_hash,'provenance':origin,'imported_at':time.time(),
            'note':'只保存到训练台；不写入实机。机械限位与模型限位分别保留，不静默相互覆盖。'}


def computer_id():
    try:
        if sys.platform=='win32':
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\Microsoft\Cryptography',0,winreg.KEY_READ|winreg.KEY_WOW64_64KEY) as key:
                identity=winreg.QueryValueEx(key,'MachineGuid')[0]
        else:identity=Path('/etc/machine-id').read_text().strip()
    except (OSError,ImportError):identity=platform.node()
    return hashlib.sha256((sys.platform+':'+identity).encode()).hexdigest()

def enhance(Base,save_json):
    class StudioManager(TrainingQueueMixin, Base):
        def __init__(self,*a,**kw):
            super().__init__(*a,**kw)
            self.zero_connection=zero_calibration.load_connection(self.directory)
            self.zero_fetch_lock=threading.Lock()
            self.computer_id=computer_id()
            try:computer=json.loads((self.directory/'computer.json').read_text(encoding='utf-8'))
            except (OSError,ValueError):computer={}
            changed=bool(computer and computer.get('id')!=self.computer_id)
            if changed:self.environment_cache={}
            self.computer_verified=bool(not changed and computer.get('verified'))
            self.recipe=fresh_recipe()
            try:self.recipe=json.loads((self.directory/'recipe.json').read_text(encoding='utf-8'))
            except (OSError,ValueError):pass
            if self.recipe.get('baseline') != ENGINE:
                previous=copy.deepcopy(self.recipe)
                self.recipe=fresh_recipe()
                self.recipe['calibration']=previous.get('calibration') or self.recipe.get('calibration')
                self.recipe['robot']=previous.get('robot') or self.recipe['robot']
                self.recipe['version']=previous.get('version',0)+1
                save_json(self.directory/'recipe-before-official0151.json',previous)
                save_json(self.directory/'recipe.json',self.recipe)
            routed=task_profile(self.profile)
            if routed != self.profile:self.set_execution_profile(routed)
            self.frozen=None
            self.archives=[]
            try:self.archives=json.loads((self.directory/'recipes.json').read_text(encoding='utf-8'))
            except (OSError,ValueError):pass
            if not (self.directory/'profile.json').exists():self.profile['repo']=PINS[self.recipe['baseline']]['repo']
            # Only source-matched task snapshots are reused. Machine verification
            # remains shared across tasks; calibration imports never invalidate it.
            cached=self.environment_cache.get(self.environment_key(self.profile),{})
            if cached.get('revision') == REVISION:
                self.restore_environment(self.profile,REVISION)
            else:
                self.environment={'ready':False,'status':'unchecked','engine':ENGINE,
                    'revision':REVISION,'tasks':list(TASKS),'configs':{},
                    'message':'使用官方0.15.1对应训练环境；首次安装后直接训练。'}
            if not computer and any(e.get('ready') for e in self.environment_cache.values()):self.computer_verified=True
            save_json(self.directory/'computer.json',{'id':self.computer_id,'verified':self.computer_verified})
            self.directory_source=ROOT
            self.initialize_queue(save_json)

        def remember_environment(self):
            super().remember_environment()
            if self.environment.get('ready'):
                self.computer_verified=True
                save_json(self.directory/'computer.json',{'id':self.computer_id,'verified':True})

        def snapshot(self,*args,**kwargs):
            result=super().snapshot(*args,**kwargs)
            result['computer_verified']=self.computer_verified
            result['target_runtime']=RUNTIME_VERSION
            result['training_queue']=self.queue_snapshot()
            for job in result['jobs']:
                req=job.get('request',{});task=model_task(req)
                job.update(target_compatible=bool(task),resolved_task=task,
                           resume_compatible=current_request(req) and job.get('resume_import_supported', True),compatibility_label=compatibility_label(req))
            return result


        def select_environment(self,value):
            with self.lock:
                profile={k:value.get(k,self.profile[k]) for k in ('mode','distro','repo')}
                task=value.get('task') or self.recipe.get('task')
                engine=ENGINE
                pin=PINS[engine]
                if profile==self.profile and self.environment.get('ready') and self.environment.get('revision')==pin['revision']:
                    self.remember_environment();return {'ready':True}
                if any(j['status'] in ACTIVE for j in self.jobs.values()):raise ValueError('请先结束当前任务再切换执行环境。')
                return {'ready':self.restore_environment(profile,pin['revision'])}


        def studio_state(self):
            p=PINS.get(self.environment.get('engine'),PINS[self.recipe['baseline']])
            hardware=json.loads((ROOT/'data/hardware.json').read_text(encoding='utf-8'))
            bundled={}
            path=ROOT/'data'/'baseline_official0151.json'
            if path.is_file():bundled=json.loads(path.read_text(encoding='utf-8'))
            checks=[{'label':'源码冻结','value':p['revision'],'state':'ok'},
                {'label':'基础参考参数台账','value':str(len(bundled.get('rows',[])))+'个配置条目','state':'ok' if bundled else 'missing'},
                {'label':'GPU环境','value':self.environment.get('message'),'state':'ok' if self.environment.get('ready') else 'missing'},
                {'label':'参数快照','value':'已冻结' if self.frozen and self.frozen['recipe_hash']==recipe_digest(self.recipe) else '运行时自动记录','state':'ok' if self.frozen and self.frozen['recipe_hash']==recipe_digest(self.recipe) else 'missing'},
                {'label':'本实验标定','value':self.recipe['calibration']['source'] if self.recipe.get('calibration') else '完整标定已随包归档；导入本实验后冻结快照','state':'ok' if self.recipe.get('calibration') else 'pending'},
                {'label':'实物质量/动力学','value':'沿用模型假设；见逐项来源，非实测','state':'assumption'}]
            return {'recipe':self.recipe,'zero_connection':dict(self.zero_connection),'pins':PINS,'baseline':bundled,'checks':checks,'frozen':self.frozen,'archives':self.archives,
                'tasks':TASK_CATALOG,'recipe_hash':recipe_digest(self.recipe),
                'hardware':hardware,'servo_references':json.loads((ROOT/'data/servo_references.json').read_text(encoding='utf-8')),
                'servo_mass_profile':copy.deepcopy(SERVO_MASS_PROFILE),
                'mass_closure_profile':copy.deepcopy(MASS_CLOSURE_PROFILE),
                'bundled_calibration_matches':(self.recipe.get('calibration') or {}).get('data')==hardware.get('current_calibration',{}).get('data'),
                'readiness':{'items':[]},'target_runtime':RUNTIME_VERSION}

        def start_checks(self,value):
            """Shared evidence for the start sequence; launch() still enforces the gate."""
            with self.lock:
                return {'environment_ready':bool(self.environment.get('ready')),
                    'preflight_ready':bool(self.frozen and self.frozen['recipe_hash']==recipe_digest(self.recipe)
                        and self.frozen['request_hash']==self.parameter_hash(value))}

        def save_recipe(self,value):
            with self.lock:
                r=value.get('recipe')
                if not isinstance(r,dict) or r.get('schema')!='microduck-training-recipe/v1':raise ValueError('配置格式无效。')
                if r.get('baseline') not in PINS:raise ValueError('未知基线。')
                if r.get('purpose') not in ('replication','sim2real'):raise ValueError('实验目标无效。')
                if not isinstance(r.get('overrides'),list) or not isinstance(r.get('robot'),dict):raise ValueError('覆盖参数无效。')
                r=copy.deepcopy(r)
                r['training_action_scale']=0.9  # New walk-slot experiment default; source records remain immutable.
                if not isinstance(r.get('task_overrides',{}),dict) or any(k not in TASKS or not isinstance(v,list) for k,v in r.get('task_overrides',{}).items()):raise ValueError('动作参数覆盖格式无效。')
                validate_servo_mass(r['robot'], r['baseline'])
                # Calibration changes use the import endpoints. An autosave from
                # another tab must never restore an older calibration snapshot.
                r['calibration']=copy.deepcopy(self.recipe.get('calibration'))
                if r.get('calibration'):
                    parse_calibration(json.dumps(r['calibration'].get('data')), 'recipe-calibration.json')
                r['version']=self.recipe.get('version',0)
                if digest(r)==digest(self.recipe): return {'okay':True}
                r['version']+=1
                json.dumps(r,allow_nan=False)
                self.recipe=r;self.frozen=None
                save_json(self.directory/'recipe.json',r)
                return {'okay':True}

        def import_calibration(self,value):
            with self.lock:
                cal=parse_calibration(value.get('text',''),value.get('name','calibration.json'))
                return self.apply_calibration(cal)

        def apply_calibration(self,cal):
            # Callers hold self.lock. Keep successful computer/GPU receipts and
            # running job snapshots; all future operations bind current metadata.
            cal=copy.deepcopy(cal)
            cal['changes']=zero_calibration.calibration_changes((self.recipe.get('calibration') or {}).get('data'),cal['data'])
            cal['sync']={'simulation_unchanged':True,'environment_rechecked':False}
            updated=copy.deepcopy(self.recipe)
            updated['calibration']=cal;updated['version']+=1
            save_json(self.directory/'recipe.json',updated)
            self.recipe=updated;self.frozen=None
            return {'okay':True,'source':cal['source'],'count':15,'calibration':cal,'changes':cal['changes'],
                    'sync':cal['sync']}

        def import_bundled_calibration(self):
            hardware=json.loads((ROOT/'data/hardware.json').read_text(encoding='utf-8'))
            return self.import_calibration({'name':'随包标定-20261003.json','text':json.dumps(hardware['current_calibration']['data'])})

        def import_zero_calibration(self,value):
            target=zero_calibration.normalize_target(value.get('target',self.zero_connection['target']))
            if not self.zero_fetch_lock.acquire(blocking=False):
                raise ValueError('正在从 ZERO 获取标定，请等待本次读取完成。')
            try:
                with self.lock:
                    if self.closed:raise ValueError('训练中控正在关闭。')
                    before=copy.deepcopy(self.recipe.get('calibration'))
                # Do not hold the training lock across network I/O.
                text=zero_calibration.read_calibration(target)
                cal=parse_calibration(text,'hd1910-calibration.toml')
                changes=zero_calibration.calibration_changes((before or {}).get('data'),cal['data'])
                cal.update(source=target+':'+zero_calibration.CALIBRATION_PATH,
                           provenance='从 ZERO SSH 读取已保存的完整标定',
                           zero_target=target,changes=changes)
                with self.lock:
                    if self.closed:raise ValueError('训练中控已关闭，本次读取未应用。')
                    if self.recipe.get('calibration')!=before:
                        raise ValueError('读取期间标定已被其他操作更新，本次结果未覆盖它；请重新获取。')
                    connection={'target':target,'source':'上次获取'}
                    save_json(self.directory/'zero_connection.json',connection)
                    result=self.apply_calibration(cal)
                    self.zero_connection=connection
                return {**result,'zero_connection':dict(self.zero_connection)}
            finally:
                self.zero_fetch_lock.release()

        def archive_recipe(self,value):
            with self.lock:
                name=str(value.get('name','')).strip()
                if not name or len(name)>80:raise ValueError('请输入实验名称。')
                item={'name':name,'saved_at':time.time(),'sha256':recipe_digest(self.recipe),'recipe':copy.deepcopy(self.recipe)}
                self.archives.insert(0,item);self.archives=self.archives[:100]
                save_json(self.directory/'recipes.json',self.archives);return {'okay':True}

        def launch(self,op,value):
            with self.lock:
                if op=='train' and self.training_queue['enabled'] and not self._launching_queue_entry:
                    raise ValueError('训练队列正在执行；请加入队列，按列表顺序开始训练。')
                value=dict(value)
                if not self.computer_verified and self.environment.get('ready'):self.remember_environment()
                if op=='probe' and self.computer_verified:return {'cached':True}
                if op in ('train','preview','play','onnx','export') and not self.computer_verified:
                    preparing=next((j for j in self.jobs.values() if j['op'] in ('setup','probe') and j['status'] in ACTIVE),None)
                    if preparing:
                        raise ValueError('当前训练机器正在准备或检查环境，请查看实时日志，完成后再开始训练。')
                    raise ValueError('当前训练机器尚未确认环境就绪。若已经安装完成，请在“执行环境”点击“首次检查训练机器”，只检查已有环境，不重新下载依赖。')
                source=self.jobs.get(value.get('export_job') if op=='onnx' else value.get('source_job'),{})
                if source and op in ('train','preflight','play','onnx','export'):
                    tr=source.get('request',{})
                    if not model_task(tr):
                        raise ValueError('此历史模型不属于已支持的新版 V2 / 当前官方模型；记录仍可下载和删除。')
                    if op in ('train','preflight') and not current_request(tr):
                        raise ValueError('既有 V2 可进入仿真、导出和作为联合训练老师；原训练断点请在原版续训。')
                if op in ('train','preflight') and value.get('source_job') and source.get('resume_import_supported') is False:
                    raise ValueError('这个旧模型包未保存原训练并行数，可作为老师；续训请重新导出含原训练配置快照的完整ZIP。')
                if op in ('train','preflight'):value['save_interval']=1000
                if op in ('setup','probe'):
                    value['task']=value.get('task') or self.recipe.get('task',PIN['task'])
                    if op=='setup':value['repo']=PIN['repo']
                task=(model_task(source.get('request',{})) if op in ('play','onnx','export') else value.get('task') or model_task(source.get('request',{}))) or PIN['task']
                if task not in TASKS:raise ValueError('请选择本版列出的官方0.15.1对应任务。')
                if op in ('train','preflight'):
                    if not TASKS[task]['enabled'] and not value.get('source_job'):
                        raise ValueError('此旧配方已移出新训练入口；请选择当前官方动作。历史模型仍可仿真、导出或按原配置续训。')
                    if TASKS[task]['role']=='sitstand' and not value.get('source_job') and value.get('training_action_scale',1.0)!=1.0:
                        raise ValueError('官方0.15.1坐站运行分支固定动作系数1.0；页面已自动使用1.0，请保持此值。')
                    value.setdefault('num_envs',4096)
                    from training.sample_alignment import budget_iterations
                    n = value['num_envs']
                    if type(n) is not int or not 1 <= n <= 8192:
                        raise ValueError('并行环境数超出允许范围。')
                    value.setdefault('iterations',budget_iterations(TASKS[task]['iterations'],n))
                if op in ('train','preflight') and value.get('source_job'):
                    original=source.get('request',{}).get('studio_recipe')
                    if original and simulation_recipe_digest(original)!=simulation_recipe_digest(self.recipe):
                        raise ValueError('续训沿用来源实验的仿真配置；标定更新不影响续训。')
                    if source.get('request',{}).get('task')!=task:raise ValueError('不能跨动作续训。')
                return super().launch(op,value)

        def launch_context(self,op,value):
            # Static task catalog + explicit execution target. No probe or preflight gate.
            source=self.jobs.get(value.get('export_job') if op=='onnx' else value.get('source_job'),{})
            task=model_task(source.get('request',{})) if op in ('play','onnx','export') else value.get('task')
            task=task or PINS[self.recipe['baseline']]['task']
            engine=ENGINE
            pin=PINS[engine]
            source_bound=op in ('play','onnx','export') or (op in ('train','preflight') and bool(value.get('source_job')))
            target=source.get('profile') if source_bound else value.get('execution_profile')
            if not target:
                target={**self.profile}
            if not source_bound or legacy_v2_request(source.get('request',{})):
                routed=task_profile(target,engine)
                # A custom old checkout path is not a new execution environment.
                if source_bound and routed['repo']==target['repo']:
                    same_machine=all(target.get(k)==self.profile.get(k) for k in ('mode','distro'))
                    routed={**target,'repo':self.profile['repo'] if same_machine else PIN['repo']}
                if routed['repo']!=target['repo']:
                    value['_routing_repair']={'previous_repo':target['repo'],'repo':routed['repo']}
                target=routed
            previous=dict(self.profile)
            self.set_execution_profile(target)
            saved=self.environment_cache.get(self.environment_key(self.profile),{})
            cached=self.environment if previous==self.profile else saved
            if cached.get('revision')!=pin['revision']:cached={}
            context={'revision':pin['revision'],'engine':engine,
                     'tasks':[k for k,v in TASKS.items() if v.get('enabled') and v.get('engine')==engine],
                     'configs':copy.deepcopy(cached.get('configs',{}))}
            self.environment={**copy.deepcopy(cached),**context,'ready':bool(cached.get('ready')),
                              'status':cached.get('status','unchecked')}
            # Editable rewards are known from the frozen source shipped with the
            # app. Starting with an edited reward must not require a WSL describe.
            if task not in context['configs']:
                reference=json.loads((ROOT/'data/task-configs'/(task+'.json')).read_text(encoding='utf-8'))
                context={**context,'configs':{**context['configs'],task:{'rewards':reference['rewards']}}}
            if source_bound and task not in context['tasks']:
                # Admit this original historical task only for its own saved
                # model. It remains absent from the new-training catalog.
                context={**context,'tasks':context['tasks']+[task]}
            return context

        def validate_model_source(self,source,op,context):
            if legacy_v2_request(source.get('request',{})) and op in ('play','onnx','export'):
                if any(source.get('profile',{}).get(k)!=self.profile.get(k) for k in ('mode','distro')):
                    raise ValueError('模型位于另一 Linux/WSL 环境，请切回模型所在的训练机。')
                return
            if source.get('profile')!=self.profile or source.get('revision')!=context['revision']:
                raise ValueError('模型与当前训练环境或源码版本不同。')

        def source_inspection(self,source):
            inspection=source.get('effective_config',{}).get('resolved')
            f=self.directory/'runs'/source['id']/'resolved.json'
            if not inspection and f.is_file():inspection=json.loads(f.read_text(encoding='utf-8'))
            return inspection

        def remember_task_config(self,job,data):
            # A describe response can arrive after the user switches engines.
            # Store it against its own request, never the current page profile.
            key=self.environment_key(job['profile'])
            revision=job.get('revision') or job['request'].get('expected_revision')
            cached=copy.deepcopy(self.environment_cache.get(key,{}))
            if self.profile==job['profile'] and self.environment.get('revision')==revision:
                cached=copy.deepcopy(self.environment)
            if cached.get('revision')!=revision:cached={'ready':False,'revision':revision}
            cached.setdefault('configs',{})[data['task']]=copy.deepcopy(data)
            self.environment_cache[key]=cached
            save_json(self.directory/'environments.json',self.environment_cache)
            if self.profile==job['profile'] and self.environment.get('revision')==revision:
                self.environment['configs']=copy.deepcopy(cached['configs'])

        @staticmethod
        def parameter_hash(value):
            keys=('task','num_envs','iterations','save_interval','actor_dims','critic_dims','activation','learning_rate','gamma','entropy','clip','seed','reward_weights','pushes','training_action_scale','action_filter','training_firmware_p','source_job','checkpoint','walk_teacher','stand_teacher')
            return digest({k:(1000 if k=='save_interval' else value.get(k)) for k in keys})

        def decorate_request(self,request,value):
            op=request['op']
            recovery_evaluation=value.get('recovery_evaluation',False)
            if type(recovery_evaluation) is not bool:
                raise ValueError('翻身检查参数无效。')
            if recovery_evaluation and op not in ('play','onnx'):
                raise ValueError('翻身检查仅用于所选倒地起身模型的 PT / ONNX 仿真。')
            if op=='train' and self._launching_queue_entry:
                request['queue_entry_id']=self._launching_queue_entry['id']
                request['queue_attempt']=self._launching_queue_entry.get('attempt',1)
            request.update(engine=ENGINE,task_adapter='hd1910-official0151',baseline_pin=copy.deepcopy(PIN),target_runtime=RUNTIME_VERSION)
            if value.get('_routing_repair'):request['routing_repair']=value['_routing_repair']
            if op=='setup':
                request['pin']={**PIN,'key':ENGINE}
                request['machine_verified']=self.computer_verified
                request['cached_gpu']=copy.deepcopy(self.environment.get('gpu',{}))
            if op in ('setup','probe'):
                request['task']=value.get('task',self.recipe.get('task',PIN['task']))
            request['studio_recipe']=copy.deepcopy(self.recipe)
            request['studio_recipe_hash']=recipe_digest(self.recipe)
            request['parameter_hash']=self.parameter_hash(value)
            request['start_parameters']={k:copy.deepcopy(v) for k,v in value.items() if k!='label'}
            origin={}
            if op in ('play','export','onnx') or (op in ('train','preflight') and request.get('source_job')):
                source_id=request.get('export_job') if op=='onnx' else request.get('source_job')
                origin=self.jobs.get(source_id,{}).get('request',{})
                if origin.get('studio_recipe'):
                    request['studio_recipe']=normalize_model_recipe(origin)
                    if ignored_legacy_bam_overrides(origin):
                        request['ignored_legacy_bam_overrides']=ignored_legacy_bam_overrides(origin)
                    request['training_calibration']=copy.deepcopy(origin.get('training_calibration',origin['studio_recipe'].get('calibration')))
                    request['studio_recipe']['calibration']=copy.deepcopy(self.recipe.get('calibration'))
                    request['studio_recipe_hash']=recipe_digest(request['studio_recipe'])
                if origin.get('model_source'):
                    request['model_source']=copy.deepcopy(origin['model_source'])
                elif legacy_v2_request(origin):
                    source=self.jobs[source_id]
                    if op=='onnx':source=self.jobs.get(origin.get('source_job'),source)
                    request['model_source']={'origin':training_origin(origin),'repo':source['profile']['repo'],
                        'contract':teacher_contract(self.source_inspection(source), source.get('request'))}
                if model_task(origin):request['task']=model_task(origin)
                if op == 'export':
                    # Bind the immutable actual training readback. The export
                    # environment may omit BC/evaluation pushes and is not a
                    # substitute for the configuration used to learn this PT.
                    inspection = self.source_inspection(self.jobs[source_id])
                    if inspection and inspection.get('full') and inspection.get('model'):
                        request['source_training_snapshot'] = {
                            'task': inspection.get('task', request['task']),
                            'full': copy.deepcopy(inspection['full']),
                            'model': copy.deepcopy(inspection['model'])}
            request['training_adapter_revision']=TRAINING_ADAPTER_REVISION if op=='train' else origin.get('training_adapter_revision')
            if op in ('play','onnx'):
                # Validate the bound model task, never the currently selected
                # training page. Recovery checks are an evaluation-only mode.
                if recovery_evaluation and TASKS.get(request.get('task'),{}).get('role')!='stand':
                    raise ValueError('翻身检查需要选择倒地起身老师的 PT 或 ONNX 模型。')
                request['recovery_evaluation']=recovery_evaluation
                if recovery_evaluation:
                    request['eval_pushes']=False
            if op in ('train','preflight'):
                request['sample_alignment_version']=1
                if request.get('source_job'):
                    request['resume_sample_source']={'num_envs':origin.get('num_envs',4096)}
            if request.get('task') in JOINT_TASKS and op in ('train','preflight'):
                request['joint']=self.joint_request(request,value)
            return request

        def delete_model(self,value):
            with self.lock:
                owner=value.get('export_job') or value.get('source_job')
                path=value.get('checkpoint')
                for entry in self.training_queue['entries']:
                    if entry['status'] not in ('waiting','starting','running','stopping'):continue
                    selections=[entry['request'],entry['request'].get('walk_teacher',{}),entry['request'].get('stand_teacher',{})]
                    for pick in selections:
                        dependency=next((e for e in self.training_queue['entries'] if e['id']==pick.get('queue_entry')),None)
                        if (pick.get('source_job')==owner and pick.get('checkpoint')==path) or (dependency and dependency.get('job_id')==owner):
                            raise ValueError('训练队列正在引用该PT；请先移除对应队列任务。')
                return super().delete_model(value)

        def joint_request(self,request,value):
            source=self.jobs.get(value.get('source_job'),{})
            if value.get('source_job'):
                origin=source.get('request',{})
                if origin.get('task')!=request['task'] or not origin.get('joint'):
                    raise ValueError('只能续训本版对应任务的联合PT。')
                joint=copy.deepcopy(origin['joint']);joint['mode']='resume'
                receipt=source.get('effective_config',{}).get('joint') or {}
                for role in ('walk','stand'):
                    if receipt.get('teachers',{}).get(role):joint[role]['sha256']=receipt['teachers'][role]['sha256']
                return joint
            joint={'mode':'warm_start'}
            for role in ('walk','stand'):
                selection=value.get(role+'_teacher') or {}
                if not isinstance(selection,dict):raise ValueError('老师选择格式无效。')
                teacher=self.jobs.get(selection.get('source_job'),{})
                cp=next((c for c in teacher.get('checkpoints',[]) if c['path']==selection.get('checkpoint')),None)
                tr=teacher.get('request',{})
                if teacher.get('op')!='train' or cp is None or model_task(tr) not in TEACHER_TASKS[role]:
                    raise ValueError('请选择已经独立评估会'+('走路' if role=='walk' else '起身')+'的HD1910老师PT；联合模型和ONNX不能代替老师PT。')
                if any(j['op']=='prune_models' and j['status'] in ACTIVE and cp['path'] in j['request']['model_paths'] for j in self.jobs.values()):
                    raise ValueError('此低轮数老师PT正在清理，请选择1000轮及以上模型。')
                if physical_recipe(normalize_model_recipe(tr))!=physical_recipe(self.recipe):
                    raise ValueError('老师与本次机器人物理配置不同，请恢复相同机器人参数或重新训练老师。')
                if any(teacher.get('profile',{}).get(k)!=self.profile.get(k) for k in ('mode','distro')):
                    raise ValueError('老师位于另一Linux/WSL环境，请在同一训练机准备老师。')
                inspection=self.source_inspection(teacher)
                entry={'source_job':teacher['id'],'task':model_task(tr),'checkpoint':cp['path'],
                       'repo':teacher['profile']['repo'],'contract':teacher_contract(inspection, tr),
                       'origin':training_origin(tr),
                       'gear_backlash':copy.deepcopy(inspection['model'].get('gear_backlash', {'enabled':False}))}
                if request['op']=='train' and self.frozen and self.frozen.get('recipe_hash')==recipe_digest(self.recipe) and self.frozen.get('request_hash')==self.parameter_hash(value):
                    prior=self.jobs.get(self.frozen.get('job_id'),{}).get('validation',{}).get('joint',{}).get('teachers',{}).get(role)
                    if prior:entry['sha256']=prior['sha256']
                joint[role]=entry
            return joint

        def _event(self,job,event):
            kind=event.get('kind')
            if kind=='validation':
                with self.lock:
                    job['validation']=event['data']
                    self.frozen={'recipe_hash':job['request']['studio_recipe_hash'],'request_hash':job['request']['parameter_hash'],
                        'start_parameters':job['request'].get('start_parameters'),
                        'resolved_sha256':event['data']['sha256'],'at':time.time(),'job_id':job['id']}
                    save_json(self.directory/'runs'/job['id']/'resolved.json',event['data'])
                    self.persist(job)
                return
            if kind=='effective_config' and event.get('data',{}).get('resolved'):
                save_json(self.directory/'runs'/job['id']/'resolved.json',event['data']['resolved'])
            if kind=='metric':
                with (self.directory/'runs'/job['id']/'metrics.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(event['data'],ensure_ascii=False)+'\n')
            if kind=='task_config' and event.get('data',{}).get('inspection'):
                from training.explanations import annotate_rows
                inspection=event['data']['inspection'];inspection['rows']=annotate_rows(inspection['rows'])
            super()._event(job,event)

        def report_zip(self,jid=None):
            out=io.BytesIO()
            with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
                z.writestr('recipe.json',json.dumps(self.jobs[jid]['request'].get('studio_recipe',self.recipe) if jid and jid in self.jobs else self.recipe,ensure_ascii=False,indent=2))
                z.writestr('pins.json',json.dumps(PINS,ensure_ascii=False,indent=2))
                for p in (ROOT/'data').glob('*.json'):z.write(p,'reference/'+p.name)
                for p in (ROOT/'docs').glob('*'):
                    if p.is_file():z.write(p,'docs/'+p.name)
                if jid:
                    if jid not in self.jobs:raise ValueError('找不到运行记录。')
                    root=self.directory/'runs'/jid
                    for p in root.glob('*'):
                        if p.is_file():z.write(p,'run/'+p.name)
            return out.getvalue()

        def model_download(self,jid):
            with self.lock:
                job=copy.deepcopy(self.jobs.get(jid))
            if not job or job['op']!='export' or job['status']!='completed' or not job.get('artifact_sha256') or not job.get('artifact'):
                raise ValueError('只能下载本台成功导出的模型包。')
            request={'artifact':job['artifact'],'sha256':job['artifact_sha256'],
                     'checkpoint':job['request'].get('checkpoint'),'training_request':job['request']}
            if job['profile']['mode']=='wsl':
                # Keep the Linux path as text: Windows Path would change /home to \home.
                code=(ROOT/'training/model_package.py').read_text(encoding='utf-8')
                try:
                    result=self.sessions.run(job['profile'],code.encode('utf-8'),
                                             data=json.dumps(request).encode('utf-8'),timeout=120)
                except subprocess.TimeoutExpired as error:
                    raise ValueError('从 WSL 读取模型包超时，请确认发行版运行正常后重试。') from error
                if result.returncode:raise ValueError('无法从 WSL 取得模型包：'+(result.stderr or result.stdout).decode(errors='replace')[-1000:])
                if not result.stdout.startswith(b'PK\x03\x04'):
                    raise ValueError('WSL 未返回有效 ZIP 数据，请查看导出日志。')
                return result.stdout
            from training.model_package import model_package
            return model_package(request)
    return StudioManager

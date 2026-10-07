"""Runs inside the selected Linux training environment. No robot / SSH access."""
import json
import hashlib
import os
import queue
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import traceback
import tempfile
import uuid
from pathlib import Path

PREFIX = 'MICRODUCK_TRAINING '
ANSI = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
STOP = threading.Event()
PRINT_LOCK = threading.Lock()
CONTROL_QUEUE = queue.Queue(maxsize=32)
ADAPTER_PREFIX = 'MICRODUCK_ADAPTER '


def emit(kind, **data):
    with PRINT_LOCK:
        try:
            print(PREFIX + json.dumps({'kind': kind, **data}, ensure_ascii=False, allow_nan=False), flush=True)
        except (BrokenPipeError, OSError):
            STOP.set()


def controls():
    # Durable training is owned by WSL. Only an explicit stop file ends it.
    stop_path=globals().get('WORKER_STOP_PATH')
    if stop_path:
        while not STOP.wait(.1):
            if Path(stop_path).exists():STOP.set();return
        return
    # Disposable viewers still stop when their desktop connection disappears.
    pending = b''
    while True:
        try: chunk = os.read(0, 4096)
        except OSError: break
        if not chunk: break
        pending += chunk
        while b'\n' in pending:
            line, pending = pending.split(b'\n', 1)
            try:
                message = json.loads(line)
                if message.get('op') == 'stop': STOP.set()
                elif message.get('op') == 'sim_control':
                    try: CONTROL_QUEUE.put_nowait(message)
                    except queue.Full:
                        try: CONTROL_QUEUE.get_nowait()
                        except queue.Empty: pass
                        CONTROL_QUEUE.put_nowait(message)
            except (ValueError, AttributeError):
                pass
        if len(pending) > 4096: break
    STOP.set()


def terminate(proc):
    if proc.poll() is not None: return
    for sig, delay in ((signal.SIGINT, 6), (signal.SIGTERM, 3), (signal.SIGKILL, 2)):
        try: os.killpg(proc.pid, sig)
        except ProcessLookupError: return
        try:
            proc.wait(timeout=delay)
            return
        except subprocess.TimeoutExpired:
            pass


def execute(argv, cwd, on_line=None, timeout=None, interactive=False):
    if STOP.is_set(): raise InterruptedError('任务已停止。')
    env = {**os.environ, 'PYTHONUNBUFFERED': '1', 'NO_COLOR': '1', 'TERM': 'dumb',
           'WANDB_MODE': 'disabled', 'WANDB_DISABLED': 'true'}
    proc = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.PIPE if interactive else subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, env=env, start_new_session=True)
    expired = threading.Event()
    pipe_guard=threading.Lock()
    def forward_controls():
        while proc.poll() is None and not STOP.is_set():
            try: message = CONTROL_QUEUE.get(timeout=.025)
            except queue.Empty: continue
            try:
                with pipe_guard:
                    proc.stdin.write((json.dumps(message)+'\n').encode('utf-8'))
                    proc.stdin.flush()
            except (OSError, ValueError): return
    def watch():
        begin = time.monotonic()
        while proc.poll() is None:
            if STOP.wait(.025 if interactive else .2):
                if interactive:
                    def ask_close():
                        with pipe_guard:
                            try:proc.stdin.write(b'{"action":"shutdown"}\n');proc.stdin.flush()
                            except (OSError,ValueError):pass
                    threading.Thread(target=ask_close,daemon=True).start()
                    try:proc.wait(timeout=2);return
                    except subprocess.TimeoutExpired:pass
                    # SIGINT can interrupt CUDA/Viser cleanup halfway through.
                    # The viewer got a clean close request; force only this process group if stuck.
                    for sig,delay in ((signal.SIGTERM,1),(signal.SIGKILL,1)):
                        try:os.killpg(proc.pid,sig)
                        except ProcessLookupError:return
                        try:proc.wait(timeout=delay);return
                        except subprocess.TimeoutExpired:pass
                    return
                terminate(proc);return
            if timeout and time.monotonic()-begin > timeout:
                expired.set();terminate(proc);return
    watcher = threading.Thread(target=watch, daemon=True)
    watcher.start()
    writer = threading.Thread(target=forward_controls,daemon=True) if interactive else None
    if writer: writer.start()
    lines = []
    try:
        for raw in iter(proc.stdout.readline, b''):
            line = ANSI.sub('', raw.decode('utf-8', errors='replace')).strip()
            if not line: continue
            lines.append(line[:4000])
            if len(lines) > 1600: lines.pop(0)
            if on_line: on_line(line[:4*1024*1024] if ADAPTER_PREFIX in line else line[:4000])
            else: emit('log', line=line[:4000])
        code = proc.wait()
    finally:
        if proc.poll() is None: terminate(proc)
        proc.stdout.close()
        if writer:
            writer.join(timeout=.5)
            try:proc.stdin.close()
            except (OSError,ValueError):pass
        watcher.join(timeout=.5)
    if expired.is_set(): raise RuntimeError('环境检查超时；请先在 Linux 终端确认官方环境能正常启动。')
    if STOP.is_set(): raise InterruptedError('任务已停止；已保存的模型仍保留在原目录。')
    if code:
        raise RuntimeError(command_failure(code, lines))
    return '\n'.join(lines)


def command_failure(code, lines):
    detail = '\n'.join(lines[-10:])
    prefix = '官方命令执行失败（退出码 %s）。' % code
    if 'Graph creation error' in detail and 'CUDA error 600' in detail:
        prefix = ('CUDA图上传/启动失败（错误600：设备未就绪），训练初始化未完成。'
                  '此错误不能单独证明显存不足；可先降低并行环境作对照，并查看完整日志中的先前CUDA错误。'
                  '本次任务退出码 %s；不停止其他WSL训练。' % code)
    return prefix+'\n'+detail


class Metrics:
    """Parse actual RSL-RL log records; absent values stay absent."""
    def __init__(self, callback):
        self.callback = callback
        self.point = None

    def feed(self, line):
        changed = False
        m = re.search(r'Learning iteration\s+(\d+)\s*/\s*(\d+)', line, re.I)
        if m:
            self.flush()
            self.point = {'iteration': int(m[1]), 'total': int(m[2])}
            changed = True
        if self.point is None: return
        fields = {
            'reward': r'Mean (?:total )?reward:\s*([-+\d.eE]+)',
            'episode_length': r'Mean episode length:\s*([-+\d.eE]+)',
            'value_loss': r'(?:Mean )?value(?: function)? loss:\s*([-+\d.eE]+)',
            'policy_loss': r'(?:Mean )?(?:surrogate|policy) loss:\s*([-+\d.eE]+)',
            'fps': r'(?:Computation|Steps per second):\s*([\d.]+)',
            'iteration_seconds': r'Iteration time:\s*([\d.]+)s',
            'total_steps': r'Total steps:\s*(\d+)',
        }
        for key, pattern in fields.items():
            m = re.search(pattern, line, re.I)
            if m:
                try:
                    value = float(m[1])
                    if float('-inf') < value < float('inf'):
                        self.point[key] = value
                        changed = True
                except ValueError:
                    pass
        m = re.search(r'(?:Episode_Reward|Reward)/([^:]+):\s*([-+\d.eE]+)', line)
        if m:
            try:
                value = float(m[2])
                if float('-inf') < value < float('inf'):
                    self.point.setdefault('rewards', {})[m[1].strip()] = value
                    changed = True
            except ValueError:
                pass
        # Official loss terms, diagnostics and curricula; never fabricate missing metrics.
        for prefix,group in [('Episode_Termination','terminations'),('Curriculum','curriculum'),('Metrics','task_metrics')]:
            m=re.search(re.escape(prefix)+r'/([^:]+):\s*([-+\d.eE]+)',line)
            if m:
                try:
                    val=float(m[2])
                    if float('-inf')<val<float('inf'):self.point.setdefault(group,{})[m[1].strip()]=val;changed=True
                except ValueError:pass
        m=re.search(r'Mean (expert_bc(?:_fallen_frac|_anchor_frac)?) loss:\s*([-+\d.eE]+)',line,re.I)
        if m:
            try:
                val=float(m[2])
                if float('-inf')<val<float('inf'):self.point[m[1].lower()]=val;changed=True
            except ValueError:pass
        if changed: self.callback('metric', data=dict(self.point))

    def flush(self):
        if self.point is not None: self.callback('metric', data=dict(self.point))


def gpu_sample():
    """Read actual driver telemetry; unsupported WSL fields remain None."""
    binary = shutil.which('nvidia-smi')
    if not binary and Path('/usr/lib/wsl/lib/nvidia-smi').is_file(): binary = '/usr/lib/wsl/lib/nvidia-smi'
    if not binary: return {'devices':[], 'message':'无法读取 GPU 实时状态。'}
    def number(value):
        try:
            value = float(value.strip())
            return value if float('-inf') < value < float('inf') else None
        except ValueError: return None
    try:
        result = subprocess.run([binary,'--query-gpu=index,utilization.gpu,memory.used,memory.total,temperature.gpu',
                                 '--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=2)
        rows = []
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                fields = line.split(',')
                if len(fields) == 5:
                    rows.append(dict(zip(('index','utilization','used_mb','total_mb','temperature'),map(number,fields))))
        return {'devices':rows,'message':None if rows else '驱动未返回可用的 GPU 状态。'}
    except (OSError,subprocess.TimeoutExpired): return {'devices':[],'message':'GPU 状态读取暂不可用。'}


def monitor_gpu(done):
    while not done.is_set() and not STOP.is_set():
        emit('gpu_sample',data=gpu_sample())
        if done.wait(3): break


def checkpoints(repo, run_name):
    root = repo/'logs'/'rsl_rl'
    found = []
    if root.is_dir():
        for run in root.glob('*/*'):
            if not run.is_dir() or not run.name.endswith('_'+run_name): continue
            for p in run.glob('model_*.pt'):
                m = re.fullmatch(r'model_(\d+)\.pt', p.name)
                if m and p.is_file(): found.append({'iteration': int(m[1]), 'path': str(p.resolve()), 'name': p.name,
                                                   'modified':p.stat().st_mtime,'size':p.stat().st_size})
    return sorted(found, key=lambda x: x['iteration'])[-100:]


def prepare(req):
    if sys.platform != 'linux': raise RuntimeError('训练引擎请放在 Linux 或 WSL2 中，Windows 只需运行训练台。')
    repo = Path(req['repo']).expanduser().resolve()
    missing = []
    if not (repo/'pyproject.toml').is_file(): missing.append('pyproject.toml')
    if not (repo/'src'/'mjlab_microduck'/'tasks').is_dir(): missing.append('src/mjlab_microduck/tasks')
    if missing:
        detail = '目录尚未创建' if not repo.exists() else '缺少 ' + '、'.join(missing)
        raise RuntimeError('训练源码尚未准备完整：' + str(repo) + '（' + detail + '）。请在“执行环境”点击“安装训练环境”。已有本机检查结果会沿用。')
    uv = shutil.which('uv')
    if not uv:
        for p in (Path.home()/'.local/bin/uv', Path.home()/'.cargo/bin/uv'):
            if p.is_file(): uv = str(p);break
    if not uv: raise RuntimeError('Linux 中未找到 uv，请先完成官方训练环境安装。')
    if not (repo/'.venv/bin/python').is_file():
        raise RuntimeError('仓库还没有训练虚拟环境，请先在该目录执行 uv sync --frozen。检查按钮不会自动下载或安装。')
    revision = execute(['git', 'rev-parse', 'HEAD'], repo, timeout=10).splitlines()[-1]
    if not re.fullmatch(r'[0-9a-f]{40}', revision): raise RuntimeError('无法识别官方训练源码版本。')
    if req.get('expected_revision') and revision != req['expected_revision']:
        raise RuntimeError('所选任务与读取目录的源码版本不匹配。任务：'+str(req.get('task'))+
                           '；目录：'+str(repo)+'；需要：'+str(req['expected_revision'])+'；实际：'+revision+
                           '。标定不会改变Git版本；请使用此任务对应的冻结源码目录。')
    status=execute(['git','status','--porcelain','--untracked-files=no'],repo,timeout=15)
    if status.strip():raise RuntimeError('冻结源码有未提交修改；请保留修改并使用独立的冻结训练目录。')
    return repo, [uv, 'run', '--frozen', '--no-sync'], revision


def setup_engine(req):
    pin=req['pin']
    root=Path.home()/'microduck-training-studio'/'engines'/pin['key']
    root.parent.mkdir(parents=True,exist_ok=True)
    log=lambda line:emit('log',line=line)
    uv=shutil.which('uv')
    if not uv:
        for p in (Path.home()/'.local/bin/uv',Path.home()/'.cargo/bin/uv'):
            if p.is_file():uv=str(p);break
    if not uv:raise RuntimeError('WSL中未找到uv。请按包内说明安装uv后再次点击准备环境。')
    if not shutil.which('git'):raise RuntimeError('WSL中未找到git。')
    if root.exists():
        if not (root/'.git').is_dir():raise RuntimeError('目标目录已存在但不是本训练仓库，未覆盖：'+str(root))
        origin=execute(['git','remote','get-url','origin'],root,timeout=15).strip()
        if origin.removesuffix('.git')!=pin['url'].removesuffix('.git'):raise RuntimeError('已有目录来源不符，未覆盖。')
        status=execute(['git','status','--porcelain','--untracked-files=no'],root,timeout=15)
        if status.strip():raise RuntimeError('已有源码含修改，已保留。请选新目录或先保存修改。')
    else:execute(['git','clone',pin['url'],str(root)],root.parent,log)
    execute(['git','checkout','--detach',pin['revision']],root,log)
    actual=execute(['git','rev-parse','HEAD'],root,timeout=15).strip()
    if actual!=pin['revision']:raise RuntimeError('提交核对失败。')
    repo=root/pin['subdir']
    emit('command',argv=[uv,'sync','--frozen','--python','3.12'],cwd=str(repo))
    execute([uv,'sync','--frozen','--python','3.12'],repo,log)
    if req.get('machine_verified'):
        from importlib import import_module
        spec=import_module((__package__+'.' if __package__ else '')+'official_spec')
        emit('environment',data={'ready':True,'revision':actual,'repo':str(repo),
            'engine':spec.ENGINE,'tasks':list(spec.TASKS),'configs':{},
            'gpu':req.get('cached_gpu',{}),'machine_check_reused':True,
            'message':'官方环境已安装；沿用本机GPU检查缓存，切换任务直接训练。'})
    else:
        probe(repo,[uv,'run','--frozen','--no-sync'],actual,req)
    emit('complete',message='官方0.15.1对应训练环境已准备：'+str(repo))


def probe(repo, uv, revision, req=None):
    code = "import json,torch;print('GPU_JSON '+json.dumps({'cuda':torch.cuda.is_available(),'gpus':[{'name':torch.cuda.get_device_properties(i).name,'memory_gb':round(torch.cuda.get_device_properties(i).total_memory/1024**3,1)} for i in range(torch.cuda.device_count())]}))"
    output = execute(uv+['python', '-c', code], repo, timeout=45)
    gpu = next((json.loads(line[9:]) for line in output.splitlines() if line.startswith('GPU_JSON ')), {})
    # mjlab 1.3.0's console entry point exits with the task count (e.g. 45).
    # Its official module entry point prints the same list without treating the
    # count as an exit status. Exceptions still fail through execute normally.
    tasks_output = execute(uv+['python', '-m', 'mjlab.scripts.list_envs'], repo, timeout=60)
    tasks = sorted(set(re.findall(r'Mjlab-[A-Za-z0-9_-]*MicroDuck[A-Za-z0-9_-]*', tasks_output)))
    if not tasks: raise RuntimeError('官方任务列表没有返回 MicroDuck 任务，请先运行 uv run --frozen --no-sync python -m mjlab.scripts.list_envs 检查环境。')
    if (req or {}).get('engine')=='official_0151':
        from importlib import import_module
        spec=import_module((__package__+'.' if __package__ else '')+'official_spec');TASKS,REVISION=spec.TASKS,spec.REVISION
        if revision!=REVISION:raise RuntimeError('官方 0.15.1 对应训练源码版本不匹配。')
        tasks=[key for key,info in TASKS.items() if info['upstream'] in tasks]
        if len(tasks)!=len(TASKS):raise RuntimeError('官方任务注册不完整。')
    ready = bool(gpu.get('cuda') and gpu.get('gpus'))
    emit('environment', data={'ready': ready, 'revision': revision, 'repo': str(repo), 'tasks': tasks,
                             'engine':(req or {}).get('engine','official_0151'),'training_api':'mjlab.scripts.train.TrainConfig / launch_training', 'gpu': gpu,
                             'message': '环境就绪，可开始官方训练。' if ready else '训练环境已找到，但 CUDA 不可用；请检查 Windows 驱动与 WSL GPU 支持。'})


def build_viewer_args(req, checkpoint=None):
    args = ['play', req['task'], '--viewer', 'viser', '--num-envs', '1']
    if req['op'] == 'preview': return args+['--agent','zero']
    if req['op'] == 'play' and checkpoint:
        return args+['--agent','trained','--checkpoint-file',str(checkpoint)]
    raise RuntimeError('仿真缺少有效模型存档。')


def viewer_line(line, checkpoint=None, callback=emit):
    m = re.search(r'http://(?:localhost|127\.0\.0\.1|0\.0\.0\.0):(\d+)', line)
    if m and 1024 <= int(m[1]) <= 65535 and int(m[1]) not in (8090,8091):
        callback('viewer', url='http://127.0.0.1:'+m[1])
        if checkpoint: callback('viewer_model', name=checkpoint.name)
    # The official viewer logs this AFTER successfully replacing its policy.
    # Its earlier "Loading" line must not mark a new checkpoint as loaded.
    m = re.search(r'\[INFO\]: Loaded (model_\d+\.pt)\s*$',line)
    if m and checkpoint and (checkpoint.parent/m[1]).is_file():
        callback('viewer_model',name=m[1])


def run(req):
    threading.Thread(target=controls, daemon=True).start()
    with tempfile.TemporaryDirectory(prefix='microduck-console-') as directory:
        bundle = globals().get('WORKER_BUNDLE', {})
        for name in ('runtime_adapter.py','recovery_evaluation.py','sample_alignment.py','checkpoint_policy.py','live_view.py','event_protocol.py','sim_protocol.py','recipe.py','official_spec.py','official_adapter.py','hd1910_actuator.py','hd1910_m6.json','deployment.py','action_filter.py','filtered_actions.py'):
            source = bundle.get(name)
            if source is None: source = Path(__file__).with_name(name).read_text(encoding='utf-8')
            (Path(directory)/name).write_text(source,encoding='utf-8')
        sys.path.insert(0,str(directory))
        try:run_prepared(req, Path(directory))
        finally:sys.path.remove(str(directory))


def delete_model_files(req, complete=True):
    """Move only a recorded PT or ONNX bundle inside this engine to its trash."""
    root=(Path(req['repo']).expanduser().resolve()/'logs'/'rsl_rl').resolve()
    source=Path(req['model_path']).expanduser()
    if source.is_symlink():raise ValueError('不能删除符号链接模型。')
    source=source.resolve()
    suffix='.pt' if req['model_kind']=='pt' else '.onnx'
    if source.suffix!=suffix or not source.is_relative_to(root):raise ValueError('模型不属于记录中的训练目录。')
    files=[source]
    if suffix=='.onnx':files += [source.with_suffix(s) for s in ('.contract.json','.zip','.manifest.json','.deployment.toml','.deployment.md')]
    for path in files:
        if path.is_symlink() or (path.exists() and not path.is_file()):raise ValueError('模型附属路径无效。')
    trash=root/'.studio-trash'/uuid.uuid4().hex
    existing=[path for path in files if path.is_file()]
    if existing:trash.mkdir(parents=True)
    moved=[]
    try:
        for path in existing:path.rename(trash/path.name);moved.append(path)
    except OSError:
        for path in reversed(moved):(trash/path.name).rename(path)
        raise
    emit('model_removed',path=req['model_path'])
    if complete:emit('complete',message='模型已删除'+('；文件已移到 '+str(trash) if existing else '；源文件已不存在'))


def prune_early_models(req):
    removed=0
    for path in req['model_paths']:
        match=re.fullmatch(r'model_(\d+)\.pt',Path(path).name)
        if not match or int(match[1])>=1000:raise ValueError('低轮数清理只允许model_0至model_999.pt。')
    for path in req['model_paths']:
        delete_model_files({**req,'model_path':path,'model_kind':'pt'},complete=False)
        removed+=1
    emit('complete',message='已清理1000轮以下PT：%s个；沿用原模型回收目录。'%removed)


def model_roots(req, repo):
    """Execution stays on the current source; assets retain their recorded roots."""
    roots=[repo/'logs/rsl_rl']
    source=req.get('model_source')
    if source:
        if __package__:
            from .official_spec import legacy_v2_request, model_task
        else:
            from official_spec import legacy_v2_request, model_task
        origin=source.get('origin',{})
        if req['op'] not in ('play','onnx','export') or not legacy_v2_request(origin) or model_task(origin)!=req['task']:
            raise ValueError('既有 V2 模型的来源与当前操作不匹配。')
        roots.append(Path(source['repo']).expanduser().resolve()/'logs/rsl_rl')
    return roots


def run_prepared(req, directory):
    if req.get('routing_repair'):
        repair=req['routing_repair']
        emit('log',line='[自动同步] 已匹配任务目录：'+repair['previous_repo']+' → '+repair['repo']+'；复用本机环境检查缓存。')
    if req['op']=='prune_models':
        prune_early_models(req);return
    if req['op']=='delete_model':
        delete_model_files(req);return
    if req['op']=='setup':
        setup_engine(req)
        return
    repo, uv, revision = prepare(req)
    emit('identity', revision=revision, repo=str(repo))
    op = req['op']
    def adapter_command(request):
        path = directory/'request.json'
        path.write_text(json.dumps(request,ensure_ascii=False),encoding='utf-8')
        return uv+['python',str(directory/'runtime_adapter.py'),str(path)]
    if __package__:
        from .event_protocol import split_output
    else:
        from event_protocol import split_output
    def route_adapter_output(line, on_log):
        for category,value in split_output(line):
            if category == 'event':
                event=dict(value);kind=event.pop('kind')
                emit(kind,**event)
            else:on_log(value)
    def adapter_output(line):
        route_adapter_output(line,lambda text:emit('log',line=text))
    if op == 'probe':
        probe(repo, uv, revision,req)
        emit('gpu_sample',data=gpu_sample())
        execute(adapter_command({**req,'op':'describe','task':req.get('task') or req.get('studio_recipe',{}).get('task','Mjlab-Velocity-Flat-MicroDuck')}),repo,adapter_output,timeout=120)
        return
    task = req['task']
    # Task names are discovered from the installed environment by the desktop backend.
    if not re.fullmatch(r'Mjlab-[A-Za-z0-9_-]+', task): raise RuntimeError('任务名称无效。')
    allowed_model_roots=model_roots(req,repo)
    if req.get('model_source'):
        origin=req['model_source']['origin']
        emit('log',line='[既有 V2 模型] 训练来源 '+origin['baseline_pin']['revision'][:12]+
             '；沿用原权重、动作系数与机器人参数；仿真摩擦：'+('固定倍率 1.0' if origin['friction_randomization']=='fixed' else '官方随机化')+'。')
    cp = None
    if req.get('checkpoint'):
        cp = Path(req['checkpoint']).expanduser().resolve()
        if not cp.is_file() or cp.suffix != '.pt' or not any(cp.is_relative_to(root) for root in allowed_model_roots):
            raise RuntimeError('模型存档不存在或不属于记录中的来源训练仓库。')
    if op == 'train':
        # Training uses the official Python API. Its real configuration fields
        # are checked by the adapter; human-readable CLI help is not a schema.
        emit('log', line='正在通过官方 Python 配置接口启动训练：%s 个并行环境，%s 轮。' % (req['num_envs'],req['iterations']))
        argv = adapter_command(req)
    elif op in ('preview','play','describe','preflight'):
        argv = adapter_command(req)
    elif op == 'onnx':
        path = Path(req['onnx_path']).expanduser().resolve()
        if not path.is_file() or path.suffix != '.onnx' or not any(path.is_relative_to(root) for root in allowed_model_roots):
            raise RuntimeError('导出模型不存在或不属于当前训练仓库。')
        argv = adapter_command(req)
    elif op == 'export' and cp:
        destination = (repo/'logs/rsl_rl/imported_v2_exports' if req.get('model_source') else cp.parent/'exports')
        export_path = destination/(cp.stem+'_'+uuid.uuid4().hex[:12]+'.onnx')
        export_path.parent.mkdir(parents=True, exist_ok=True)
        argv = adapter_command({**req,'export_path':str(export_path)})
    else: raise RuntimeError('任务操作无效或缺少模型存档。')
    emit('command', argv=argv, cwd=str(repo))
    metrics = Metrics(emit)
    last_cp = [0.0]
    def training_log(line):
        emit('log', line=line)
        if op == 'train':
            metrics.feed(line)
            if time.monotonic()-last_cp[0] > 3:
                last_cp[0] = time.monotonic()
                emit('checkpoints', items=checkpoints(repo, req['run_name']))
        if op == 'play' and '[INFO]: Loaded ' in line: viewer_line(line,cp)
    def line_received(line):
        route_adapter_output(line,training_log)
    done = threading.Event()
    gpu_thread = None
    if op in ('train','preview','play','onnx','export'):
        gpu_thread = threading.Thread(target=monitor_gpu,args=(done,),daemon=True)
        gpu_thread.start()
    try:
        execute(argv, repo, line_received,timeout=120 if op in ('describe','preflight') else None,
                interactive=op in ('preview','play','onnx'))
    finally:
        done.set()
        if gpu_thread: gpu_thread.join(timeout=2.5)
        metrics.flush()
        if op == 'train': emit('checkpoints', items=checkpoints(repo, req['run_name']))
    if op == 'export':
        if not export_path.is_file(): raise RuntimeError('官方命令已退出，但未找到导出的 ONNX 文件，请查看日志。')
        import zipfile
        pack=export_path.with_suffix('.zip')
        with zipfile.ZipFile(pack,'w',zipfile.ZIP_DEFLATED) as z:
            z.write(export_path,'policy.onnx')
            z.write(cp,'checkpoint.pt')
            contract=export_path.with_suffix('.contract.json')
            if contract.is_file():z.write(contract,'deployment-contract.json')
            z.writestr('training-request.json',json.dumps(req,ensure_ascii=False,indent=2))
            manifest_path=export_path.with_suffix('.manifest.json')
            if not manifest_path.is_file():raise RuntimeError('缺少 0.15.1 模型说明；导出未完成。')
            z.write(manifest_path,'manifest.json')
            z.write(export_path.with_suffix('.deployment.toml'),'deployment-profile.toml')
            z.write(export_path.with_suffix('.deployment.md'),'使用说明.md')
            z.write(export_path.with_suffix('.training.json'),'training-config.json')
            for p in cp.parent.glob('params/*'):
                if p.is_file():z.write(p,'upstream-params/'+p.name)
        emit('log',line='完整模型包：'+str(pack))
        emit('artifact', path=str(export_path),sha256=hashlib.sha256(export_path.read_bytes()).hexdigest(),size=export_path.stat().st_size)
        emit('complete', message='已导出模型：'+str(export_path))
    else: emit('complete', message='官方命令已完成。')


if __name__ == '__main__':
    try:
        run(WORKER_REQUEST)
    except InterruptedError as exc:
        emit('stopped', message=str(exc))
    except Exception as exc:
        for line in traceback.format_exc().splitlines():
            emit('log', line=line)
        emit('failed', message=str(exc))
        sys.exit(2)

"""Linux/WSL training owner and disposable stdio monitor. Standard library only."""
import fcntl
import json
import os
from pathlib import Path
import re
import runpy
import signal
import sys
import threading
import time
import traceback

PREFIX = 'MICRODUCK_TRAINING '


def record(path, value):
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8')
    temporary.replace(path)


def process_birth(pid):
    try:return Path('/proc/%s/stat'%pid).read_text().rsplit(')',1)[1].split()[19]
    except (OSError,IndexError):return None


def state_at(directory):
    try:return json.loads((directory/'state.json').read_text())
    except (OSError,ValueError):return {}


def alive(state):
    return bool(state.get('pid') and state.get('birth') and process_birth(state['pid'])==state['birth'])


def run_owner(directory):
    signal.signal(signal.SIGHUP,signal.SIG_IGN)
    state={'pid':os.getpid(),'birth':process_birth(os.getpid()),'status':'running','started':time.time()}
    record(directory/'state.json',state)
    code=0
    try:
        runpy.run_path(str(directory/'worker.py'),run_name='__main__',
                       init_globals={'WORKER_STOP_PATH':str(directory/'stop.request')})
    except SystemExit as error:
        code=error.code if isinstance(error.code,int) else (0 if error.code is None else 1)
    except BaseException:
        traceback.print_exc();code=1
    finally:
        sys.stdout.flush();sys.stderr.flush()
        record(directory/'state.json',{**state,'status':'finished','code':code,'ended':time.time()})


def ensure_started(directory, request, agent_source):
    directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    with (directory/'launch.lock').open('a') as guard:
        fcntl.flock(guard,fcntl.LOCK_EX)
        state=state_at(directory)
        if state: return  # Same job identity is never launched twice, even after failure.
        if not request.get('source'):raise FileNotFoundError('未找到此 WSL 后台训练记录；没有自动重启训练。')
        (directory/'worker.py').write_text(request['source'],encoding='utf-8')
        (directory/'agent.py').write_text(agent_source,encoding='utf-8')
        record(directory/'state.json',{'status':'launching','started':time.time()})
        # Double-fork: the durable owner must not remain a broker descendant.
        # Broker EOF/kill/desktop process-tree cleanup may end only the monitor.
        child=os.fork()
        if child==0:
            try:
                os.setsid()
                if os.fork():os._exit(0)
                null=os.open(os.devnull,os.O_RDONLY)
                log=os.open(directory/'events.log',os.O_CREAT|os.O_APPEND|os.O_WRONLY,0o600)
                os.dup2(null,0);os.dup2(log,1);os.dup2(log,2)
                os.closerange(3,os.sysconf('SC_OPEN_MAX'))
                os.execv(sys.executable,[sys.executable,'-u',str(directory/'agent.py'),'--run',str(directory)])
            except BaseException:
                traceback.print_exc()
                record(directory/'state.json',{'status':'finished','code':1,'ended':time.time()})
                os._exit(1)
        os.waitpid(child,0)
        deadline=time.monotonic()+10
        while state_at(directory).get('status')=='launching':
            if time.monotonic()>deadline:
                # Retain a receipt to avoid starting another trainer on reconnect.
                record(directory/'state.json',{'status':'launch_uncertain','message':'后台任务启动未确认'})
                break
            time.sleep(.05)


def emit(kind, **data):
    sys.stdout.write(PREFIX+json.dumps({'kind':kind,**data},ensure_ascii=False)+'\n');sys.stdout.flush()


def monitor(request, agent_source):
    jid=request.get('id','')
    if not re.fullmatch(r'[a-f0-9]{16}',jid):raise ValueError('后台训练编号无效。')
    root=Path.home()/'.local/state/microduck-training-studio/jobs'
    directory=root/jid
    if request.get('source'):ensure_started(directory,request,agent_source)
    if not state_at(directory):
        emit('durable_missing',message='没有找到此 WSL 后台训练记录，未自动重启。');return 3
    detached=threading.Event()
    def controls():
        pending=b''
        try:
            while True:
                chunk=os.read(0,4096)
                if not chunk:break
                pending+=chunk
                while b'\n' in pending:
                    line,pending=pending.split(b'\n',1)
                    try:value=json.loads(line)
                    except ValueError:continue
                    if isinstance(value,dict) and value.get('op')=='stop':
                        (directory/'stop.request').write_text('explicit stop\n')
                if len(pending)>4096:break
        except (OSError,ValueError):pass
        finally:detached.set()  # EOF detaches monitoring; it never stops training.
    threading.Thread(target=controls,daemon=True).start()
    offset=max(0,int(request.get('offset',0)))
    emit('durable_attached',directory=str(directory),data=state_at(directory))
    while not detached.is_set():
        state=state_at(directory)
        path=directory/'events.log'
        if path.exists():
            with path.open('rb') as log:
                log.seek(offset)
                for _ in range(200):
                    start=log.tell();line=log.readline()
                    if not line or not line.endswith(b'\n'):break
                    sys.stdout.write(line.decode('utf-8',errors='replace'));sys.stdout.flush()
                    offset=log.tell()
                if offset!=int(request.get('offset',0)):
                    emit('durable_cursor',offset=offset);request['offset']=offset
                drained=offset>=path.stat().st_size
        else:drained=True
        if state.get('status')=='finished' and drained:
            emit('durable_exit',data=state);return int(state.get('code',1))
        if state.get('status')=='running' and not alive(state):
            # Death is confirmed by PID + process birth, never by monitor EOF.
            emit('durable_exit',data={**state,'status':'finished','code':1,'ended':time.time(),
                                     'message':'WSL 后台训练进程已退出，未留下正常退出记录。'});return 1
        if state.get('status')=='launch_uncertain':
            emit('durable_monitor_error',message='后台任务启动未确认，保留记录且不重复启动。');return 4
        if state.get('status')=='launching' and time.time()-state.get('started',0)>15:
            emit('durable_monitor_error',message='后台启动记录尚未确认，不重复启动训练。');return 4
        detached.wait(.1)
    return 0


if __name__=='__main__':
    if len(sys.argv)>2 and sys.argv[1]=='--run':run_owner(Path(sys.argv[2]))
    else:
        try:raise SystemExit(monitor(DURABLE_REQUEST,DURABLE_SOURCE))
        except (BrokenPipeError,ConnectionResetError):pass

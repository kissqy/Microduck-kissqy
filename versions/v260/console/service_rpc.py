"""Console service relay. Each RPC opens robotd IPC, never the motor port."""
import json
import socket
import subprocess
import sys
import threading
import base64
import hashlib
import io
import os
from pathlib import Path
import re
import signal
import tempfile
import time
import zipfile

_ai_lock=threading.RLock()
_ai_write_lock=threading.Lock()
_ai_process=None
_ai_session=None
_ai_closing=False
AI_INPUT_DIRECTORY=Path('/run/padd/ai-input')


def _input_file(path):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'r') as stream:value=stream.read(128)
    if len(value)>=128:raise ValueError('AI 输入租约文件过长')
    return value.strip()


def _input_padd_running():
    try:
        pid=json.loads(Path('/run/padd/input-settings.json').read_text())['pid']
        if type(pid) is int and pid>0 and Path('/proc',str(pid),'comm').read_text().strip()=='padd':return True
    except (OSError,ValueError,KeyError,TypeError):pass
    try:
        for proc in Path('/proc').iterdir():
            if not proc.name.isdecimal():continue
            try:
                if (proc/'comm').read_text().strip()=='padd':return True
            except PermissionError:return True
            except OSError:pass
    except OSError:return True
    return False


def validate_ai_input_token(token,*,directory=None):
    """Self-contained: this relay runs via python -c, outside the worker bundle.

    Native cancellation/expiry blocks future RPCs. It cannot retract a request
    already accepted by robotd on another socket; no cross-process transaction
    or motor-control ownership is claimed here.
    """
    if not isinstance(token,str) or not re.fullmatch(r'[a-f0-9]{32}',token):
        raise ValueError('AI 输入租约编号无效')
    directory=Path(directory) if directory is not None else AI_INPUT_DIRECTORY
    if directory.is_symlink():raise ValueError('AI 输入租约目录无效')
    cancel=directory/(token+'.cancel')
    def cancelled():
        try:reason=_input_file(cancel)
        except FileNotFoundError:return
        except OSError:raise ValueError('AI 输入租约已取消')
        raise ValueError('AI 输入租约已取消：'+reason)
    cancelled()
    try:
        expiry=int(_input_file(directory/(token+'.lease')))
        ack=int(_input_file(directory/(token+'.ack')))
        now=time.monotonic_ns()//1_000_000
        if not 0<expiry-now<=1500 or not 0<ack-now<=1500:
            raise ValueError('AI 输入租约已过期')
        if ack>expiry:raise ValueError('AI 输入租约确认无效')
        if (directory/(token+'.solo')).exists() and _input_padd_running():
            raise ValueError('实体手柄服务已启动，需重新确认输入租约')
    except (OSError,TypeError) as exc:
        raise ValueError('AI 输入租约或确认已失效') from exc
    cancelled()
    return expiry


def stop_ai_worker(proc):
    if proc is None:return
    for sig in (signal.SIGTERM,signal.SIGKILL):
        try:os.killpg(proc.pid,sig)
        except ProcessLookupError:pass
        try:proc.wait(timeout=.7);break
        except subprocess.TimeoutExpired:pass
    for stream in (proc.stdin,proc.stdout,proc.stderr):
        if stream:
            try:stream.close()
            except (OSError,ValueError):pass


def ai_control(request):
    message=request.get('message') or {}
    if message.get('action') not in ('stop','tool_result','mute','speech','commit','vision','tools','voice','voices'):
        raise ValueError('unsupported AI control')
    if message.get('action')=='voice':
        if (not isinstance(message.get('voice_id'),str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,150}',message['voice_id'])
                or not isinstance(message.get('request_id'),str) or not re.fullmatch(r'[a-f0-9]{32}',message['request_id'])):
            raise ValueError('invalid voice selection')
    if message.get('action')=='voices':
        rows=message.get('voices')
        if not isinstance(rows,list) or not 1<=len(rows)<=32 or len(json.dumps(rows))>24576:
            raise ValueError('invalid voice catalog')
    if message.get('action')=='mute' and type(message.get('muted')) is not bool:
        raise ValueError('invalid AI mute state')
    if message.get('action')=='speech':
        if (type(message.get('enabled')) is not bool or not isinstance(message.get('request_id'),str)
                or not re.fullmatch(r'[a-f0-9]{32}',message['request_id'])):
            raise ValueError('invalid speech state or request id')
    if message.get('action')=='tools':
        tools=message.get('tools')
        if not isinstance(tools,list) or len(tools)>32 or any(not isinstance(t,dict) for t in tools) or len(json.dumps(tools).encode())>65536:
            raise ValueError('invalid AI tools')
    if message.get('action')=='vision':
        question=message.get('question')
        if not isinstance(question,str) or not 1<=len(question.strip())<=300:
            raise ValueError('invalid vision question')
    with _ai_lock:
        proc=_ai_process
        if request.get('session_id')!=_ai_session or proc is None or proc.poll() is not None:
            return {'accepted':False,'reason':'Zero AI 会话尚未启动或已经结束'}
        with _ai_write_lock:
            proc.stdin.write((json.dumps(message,ensure_ascii=False)+'\n').encode())
            proc.stdin.flush()
    return {'accepted':True}


def ai_session(request,progress):
    """Ship code over existing SSH stdin; no audio bytes or key in files/argv."""
    global _ai_process,_ai_session
    if progress is None or os.name!='posix':raise ValueError('Zero AI requires a streaming Linux session')
    session=request.get('session_id','')
    if not re.fullmatch(r'[a-f0-9]{32}',session):raise ValueError('invalid AI session id')
    encoded=request.get('bundle','')
    if not isinstance(encoded,str) or len(encoded)>1500000:raise ValueError('invalid AI bundle size')
    bundle=base64.b64decode(encoded,validate=True)
    if hashlib.sha256(bundle).hexdigest()!=request.get('bundle_sha256'):
        raise ValueError('AI bundle checksum mismatch')
    with _ai_lock:
        if _ai_closing:raise ValueError('service channel is closing')
        if _ai_session is not None:raise ValueError('Zero AI already running')
        _ai_session=session
    proc=None;errors=[];reader=None
    try:
        with tempfile.TemporaryDirectory(prefix='microduck-ai-') as directory:
            with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
                members=archive.infolist()
                if len(members)>100 or sum(m.file_size for m in members)>2000000:
                    raise ValueError('invalid AI bundle contents')
                names={m.filename for m in members}
                if not {'ai_zero.py','ai_doubao.py','ai_hat_audio.py','_ai_vendor/__init__.py'}.issubset(names):
                    raise ValueError('AI bundle missing worker code')
                for member in members:
                    name=member.filename
                    allowed=name in ('ai_zero.py','ai_doubao.py','ai_hat_audio.py','ai_mouth_lease.py','ai_input_lease.py','ai_audio_meter.py','ai_pcm.py','ai_persona.py','ai_vision.py','ai_voices.py','_ai_vendor/__init__.py') or re.fullmatch(r'_ai_vendor/websocket/[A-Za-z0-9_]+\.py',name)
                    if not allowed:raise ValueError('unexpected AI bundle path')
                    path=Path(directory)/name;path.parent.mkdir(parents=True,exist_ok=True)
                    path.write_bytes(archive.read(member))
            with _ai_lock:
                if _ai_closing:raise ValueError('service channel is closing')
                proc=subprocess.Popen([sys.executable,'-u',str(Path(directory)/'ai_zero.py')],
                    stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                    start_new_session=True,bufsize=65536)
                _ai_process=proc
            def drain():
                for line in proc.stderr:
                    errors.append(line.decode(errors='replace')[:500]);del errors[:-8]
            reader=threading.Thread(target=drain,daemon=True);reader.start()
            with _ai_write_lock:
                proc.stdin.write((json.dumps(request['config'],ensure_ascii=False)+'\n').encode())
                proc.stdin.flush()
            progress({'kind':'worker_started','message':'Zero AI 工作进程已建立，使用 HAT 录放音。'})
            while True:
                line=proc.stdout.readline(65537)
                if not line:break
                if len(line)>65536:raise ValueError('Zero AI event exceeds limit')
                event=json.loads(line)
                if not isinstance(event,dict) or not isinstance(event.get('kind'),str):
                    raise ValueError('invalid Zero AI event')
                progress(event)
            code=proc.wait(timeout=2)
            if reader:reader.join(.5)
            if code and errors:
                progress({'kind':'provider_error','reason':''.join(errors)[-1500:]})
            return {'accepted':True,'returncode':code}
    finally:
        stop_ai_worker(proc)
        if reader:reader.join(.5)
        with _ai_lock:
            if _ai_session==session:_ai_process=None;_ai_session=None


def execute(request, progress=None):
    if request.get('kind')=='ai_session':return ai_session(request,progress)
    if request.get('kind')=='ai_control':return ai_control(request)
    if request.get('kind') == 'manage':
        command = request['argv']
        if not isinstance(command, list) or not command or not all(isinstance(x, str) for x in command):
            raise ValueError('invalid management command')
        if progress:
            # Keep JSON stdout separate from diagnostics while streaming both
            # into the existing log. Merging them corrupts model/config replies.
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout,stderr = bytearray(),bytearray()
            def read_output(stream,output):
                for line in stream:
                    if len(output) < 512*1024: output.extend(line[:512*1024-len(output)])
                    progress(line.decode('utf-8', errors='replace'))
            readers=[threading.Thread(target=read_output,args=(stream,output),daemon=True)
                     for stream,output in ((process.stdout,stdout),(process.stderr,stderr))]
            for reader in readers:reader.start()
            try:
                process.stdin.write(request.get('input', '').encode());process.stdin.close()
                process.wait(timeout=min(300,max(5,request.get('timeout',120))))
            except subprocess.TimeoutExpired:
                process.kill();process.wait();raise
            finally:
                for reader in readers:reader.join(timeout=2)
                process.stdout.close();process.stderr.close()
            return {'returncode':process.returncode,'stdout':stdout.decode('utf-8',errors='replace'),'stderr':stderr.decode('utf-8',errors='replace')}
        result = subprocess.run(command, input=request.get('input', '').encode(),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        return {'returncode':result.returncode,
                'stdout':result.stdout.decode('utf-8', errors='replace'),
                'stderr':result.stderr.decode('utf-8', errors='replace')}
    allowed = {'robot.busStatus', 'robot.chorale', 'robot.busCommand', 'robot.relax', 'robot.shutdown', 'robot.init', 'robot.enable',
               'robot.skills', 'robot.policies', 'robot.do', 'robot.move', 'robot.head',
               'robot.pose', 'robot.mouth'}
    if request.get('method') not in allowed: raise ValueError('unsupported service method')
    token=request.get('ai_input_token')
    leased='ai_input_token' in request
    if leased:
        if request.get('method') not in {'robot.skills','robot.policies','robot.do','robot.move','robot.head','robot.pose','robot.mouth'}:
            raise ValueError('AI 输入租约不能上力、HOME 或维护机器人')
        validate_ai_input_token(token)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(min(300, max(5, request.get('timeout', 15))))
        s.connect(sys.argv[1])
        if leased:validate_ai_input_token(token)
        s.sendall((json.dumps({'jsonrpc':'2.0', 'id':1, 'method':request['method'],
                              'params':request.get('params', {})})+'\n').encode())
        with s.makefile('rb') as reader: line = reader.readline(262145)
    if not line.endswith(b'\n') or len(line) > 262144: raise ValueError('invalid service response')
    reply = json.loads(line)
    if reply.get('id') != 1: raise ValueError('service response id mismatch')
    return reply


def main():
    global _ai_closing
    def shutdown(signum,frame):
        global _ai_closing
        with _ai_lock:_ai_closing=True;proc=_ai_process
        stop_ai_worker(proc)
        raise SystemExit(0)
    for name in ('SIGTERM','SIGINT','SIGHUP'):
        if hasattr(signal,name):signal.signal(getattr(signal,name),shutdown)
    if '--stream' not in sys.argv:
        print(json.dumps(execute(json.loads(sys.stdin.buffer.readline(8193))), ensure_ascii=False), flush=True)
        return
    write_lock = threading.Lock()
    def emit(request, data):
        with write_lock: print(json.dumps({'channel_id':request['channel_id'],**data},ensure_ascii=False),flush=True)
    def handle(request):
        try:
            progress=(lambda line:emit(request,{'channel_progress':line})) if request.get('progress') else None
            emit(request,{'payload':execute(request,progress)})
        except Exception as exc: emit(request,{'channel_error':str(exc)})
    try:
        for line in sys.stdin.buffer:
            request = json.loads(line)
            # A long management or joint command must not block an explicit relax.
            threading.Thread(target=handle, args=(request,), daemon=True).start()
    finally:
        # EOF means the owning console/SSH channel disappeared. Reclaim only our AI.
        with _ai_lock:_ai_closing=True;proc=_ai_process
        stop_ai_worker(proc)


if __name__ == '__main__':
    try: main()
    except Exception as exc:
        print(json.dumps({'error':{'message':str(exc)}}, ensure_ascii=False), flush=True)
        sys.exit(1)

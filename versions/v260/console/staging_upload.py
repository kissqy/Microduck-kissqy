"""Bounded upload for installer/model staging only; no file browser or terminal."""
import hashlib,re,shlex,subprocess,threading,tempfile
from ssh_connect import ssh_command, ssh_process_options
from process_lifecycle import spawn_process, retire_process
UPLOAD_TIMEOUT = 120

class StagingUpload:
    def __init__(self,target,system_log=None):self.target=target;self.log=system_log
    def upload(self,path,stream,size,progress=None,record_output=True):
        if not re.fullmatch(r'/tmp/microduck-(?:policy-[a-f0-9]{32}\.zip|upgrade-[A-Za-z0-9]{12}/package\.tar\.gz)',path):raise ValueError('只允许内部暂存路径')
        if type(size) is not int or not 0<size<=128*1024*1024:raise ValueError('暂存文件大小无效')
        code="import sys,os,hashlib,json; p=sys.argv[1]; n=int(sys.argv[2]); f=open(p,'xb'); h=hashlib.sha256(); left=n\nwhile left:\n b=sys.stdin.buffer.read(min(left,65536))\n if not b: raise RuntimeError('upload incomplete')\n f.write(b); h.update(b); left-=len(b)\nf.flush(); os.fsync(f.fileno()); f.close(); print(json.dumps({'bytes':n,'sha256':h.hexdigest()}))"
        if self.log and record_output: self.log.add('SSH 文件上传',f'{path} · {size} bytes · Python 校验上传')
        phase='上传固件';sent=0;percent=-1
        def report(status,detail):
            nonlocal progress
            if progress:
                try:progress({'step':phase,'status':status,'detail':detail,'bytes':sent,'total':size,'percent':int(sent*100/size)})
                except Exception:
                    progress=None  # A display callback must not abort file transfer.
        report('开始','正在向 Zero 传输固件')
        # SSH output must not fill an unread pipe while stdin is being written.
        with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
            try:
                proc=spawn_process(ssh_command(self.target)+[shlex.join(['python3','-c',code,path,str(size)])],**ssh_process_options(self.target),stdin=subprocess.PIPE,stdout=output,stderr=errors)
            except Exception as exc:
                report('失败',str(exc));raise
            expired=threading.Event()
            def timeout():
                expired.set()
                proc.kill()
            timer=threading.Timer(UPLOAD_TIMEOUT,timeout);timer.start();h=hashlib.sha256()
            def stderr_tail():
                length=errors.seek(0,2);errors.seek(max(0,length-32768))
                return errors.read().decode(errors='replace').strip()
            try:
                left=size
                while left:
                    b=stream.read(min(left,65536))
                    if not b:raise ValueError('上传中断')
                    proc.stdin.write(b);h.update(b);left-=len(b)
                    sent=size-left;value=int(sent*100/size)
                    if value!=percent:percent=value;report('进行中','已发送到 SSH 通道，等待 Zero 写入与校验')
                proc.stdin.close()
                phase='校验上传';report('开始','比较本机与 Zero 的文件字节数和 SHA256')
                proc.wait();output.seek(0);stdout=output.read(4096)
                if expired.is_set():raise TimeoutError(f'上传总等待超过 {UPLOAD_TIMEOUT:g} 秒，中控已结束本次上传')
                import json
                if proc.returncode:raise RuntimeError(stderr_tail() or f'SSH 上传退出码 {proc.returncode}')
                reply=json.loads(stdout)
                if reply.get('bytes')!=size or reply.get('sha256')!=h.hexdigest():raise ValueError('暂存文件校验不一致')
                phase='上传固件';report('成功','Zero 已完整写入固件文件')
                phase='校验上传'
                report('成功','Zero 文件字节数与本机 SHA256 一致')
                if self.log and record_output: self.log.add('SSH 文件上传 / 回执',json.dumps(reply))
                return reply
            except Exception as exc:
                # BrokenPipe previously skipped stderr and hid the actual SSH/receiver error.
                if isinstance(exc,BrokenPipeError):
                    try:proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:pass
                detail=stderr_tail()
                if expired.is_set():exc=TimeoutError(f'上传总等待超过 {UPLOAD_TIMEOUT:g} 秒，中控已结束本次上传'+('；'+detail if detail else ''))
                elif detail and detail not in str(exc):exc=RuntimeError(str(exc)+'；'+detail)
                report('失败',str(exc))
                if self.log and record_output: self.log.add('SSH 文件上传 / 错误',str(exc))
                raise exc
            finally:
                timer.cancel()
                if proc.poll() is None: proc.kill()
                retire_process(proc, grace=0)

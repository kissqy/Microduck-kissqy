"""Bounded upload for installer/model staging only; no file browser or terminal."""
import hashlib,re,shlex,subprocess,threading
from ssh_connect import ssh_command, ssh_process_options
from process_lifecycle import spawn_process, retire_process
class StagingUpload:
    def __init__(self,target,system_log=None):self.target=target;self.log=system_log
    def upload(self,path,stream,size,progress=None,record_output=True):
        if not re.fullmatch(r'/tmp/microduck-(?:policy-[a-f0-9]{32}\.zip|upgrade-[A-Za-z0-9]{12}/package\.tar\.gz)',path):raise ValueError('只允许内部暂存路径')
        if type(size) is not int or not 0<size<=128*1024*1024:raise ValueError('暂存文件大小无效')
        code="import sys,os,hashlib,json; p=sys.argv[1]; n=int(sys.argv[2]); f=open(p,'xb'); h=hashlib.sha256(); left=n\nwhile left:\n b=sys.stdin.buffer.read(min(left,65536))\n if not b: raise RuntimeError('upload incomplete')\n f.write(b); h.update(b); left-=len(b)\nf.flush(); os.fsync(f.fileno()); f.close(); print(json.dumps({'bytes':n,'sha256':h.hexdigest()}))"
        if self.log and record_output: self.log.add('SSH 文件上传',f'{path} · {size} bytes · Python 校验上传')
        phase='上传固件';sent=0;percent=-1
        def report(status,detail):
            if progress:progress({'step':phase,'status':status,'detail':detail,'bytes':sent,'total':size,'percent':int(sent*100/size)})
        report('开始','正在向 Zero 传输固件')
        try:
            proc=spawn_process(ssh_command(self.target)+[shlex.join(['python3','-c',code,path,str(size)])],**ssh_process_options(self.target),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        except Exception as exc:
            report('失败',str(exc));raise
        timer=threading.Timer(120,proc.kill);timer.start();h=hashlib.sha256()
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
            stdout=proc.stdout.read(4096);stderr=proc.stderr.read(4096);proc.wait(timeout=5)
            import json
            if proc.returncode:raise RuntimeError(stderr.decode(errors='replace'))
            reply=json.loads(stdout)
            if reply.get('bytes')!=size or reply.get('sha256')!=h.hexdigest():raise ValueError('暂存文件校验不一致')
            phase='上传固件';report('成功','Zero 已完整写入固件文件')
            phase='校验上传'
            report('成功','Zero 文件字节数与本机 SHA256 一致')
            if self.log and record_output: self.log.add('SSH 文件上传 / 回执',json.dumps(reply))
            return reply
        except Exception as exc:
            report('失败',str(exc))
            if self.log and record_output: self.log.add('SSH 文件上传 / 错误',str(exc))
            raise
        finally:
            timer.cancel()
            if proc.poll() is None: proc.kill()
            retire_process(proc, grace=0)

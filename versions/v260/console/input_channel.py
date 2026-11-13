"""Persistent SSH input requests and unsolicited hotplug status; no action replay."""
import json
from pathlib import Path
import queue
import shlex
import subprocess
import sys
import threading

from ssh_connect import ssh_command, ssh_process_options
from process_lifecycle import spawn_process, retire_process


class InputChannel:
    def __init__(self,target,path,status,log=None):
        self.target,self.path,self.status,self.log=target,path,status,log
        self.proc=None
        self.lock=threading.RLock()
        self.pending={}
        self.counter=0
        self.ready=threading.Event()
        self.error=None
        self.closed=False
    def start(self):
        with self.lock:
            if self.closed:raise OSError('手柄连接已关闭')
            if self.proc is not None:return
            source=Path(__file__).with_name('remote_input.py').read_text(encoding='utf-8')
            command=['python3' if self.target else sys.executable,'-u','-c',source,self.path]
            argv=ssh_command(self.target)+[shlex.join(command)] if self.target else command
            self.proc=spawn_process(argv,**ssh_process_options(self.target),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            proc=self.proc
            threading.Thread(target=self._read,args=(proc,),daemon=True).start()
            def drain():
                try:
                    for line in proc.stderr:
                        if self.log:self.log.add('手柄 SSH',line.decode(errors='replace'))
                except (OSError,ValueError):pass
            threading.Thread(target=drain,daemon=True).start()
        if not self.ready.wait(12):raise TimeoutError('手柄 SSH 未完成连接；未发送动作')
        if self.error:raise OSError(self.error)
    def _read(self,proc):
        try:
            for raw in iter(lambda:proc.stdout.readline(65537),b''):
                if not raw.endswith(b'\n') or len(raw)>65536:raise ValueError('输入响应无效')
                row=json.loads(raw)
                with self.lock:
                    if self.closed:return
                    if row.get('event')=='status':
                        value=row['payload']
                        self.status(value)
                        self.ready.set()
                    else:
                        result=row['result']
                        self.status(result)
                        response=self.pending.get(row.get('id'))
                        if response:
                            try:response.put_nowait(result)
                            except queue.Full:pass
        except (OSError,ValueError,KeyError) as exc:
            self.error=str(exc)
        finally:
            with self.lock:
                if not self.closed:
                    self.error=self.error or '手柄 SSH 已断开；旧输入未重发'
                    self.status({'accepted':False,'available':False,'event_authoritative':True,'reason':self.error})
                self.ready.set()
                for response in self.pending.values():
                    try:response.put_nowait({'accepted':False,'available':False,'reason':self.error or '连接已关闭'})
                    except queue.Full:pass
            retire_process(proc)
    def request(self,command):
        self.start()
        response=queue.Queue(maxsize=1)
        with self.lock:
            if self.closed or self.error:raise OSError(self.error or '手柄连接已关闭')
            self.counter+=1;ident=self.counter;self.pending[ident]=response
            try:
                self.proc.stdin.write((json.dumps({'id':ident,'command':command},allow_nan=False)+'\n').encode())
                self.proc.stdin.flush()
            except BaseException:
                self.pending.pop(ident,None)
                raise
        try:return response.get(timeout=1.3)
        except queue.Empty:raise TimeoutError('输入回执超时；动作未重发') from None
        finally:
            with self.lock:self.pending.pop(ident,None)
    def close(self):
        with self.lock:
            self.closed=True
            proc=self.proc
            self.proc=None
            for response in self.pending.values():
                try:response.put_nowait({'accepted':False,'available':False,'reason':'手柄连接已关闭'})
                except queue.Full:pass
        if proc:
            try:proc.stdin.close()
            except (OSError,ValueError):pass
            retire_process(proc)

"""AI-owned SSH/RPC connection, independent of the primary service channel.

Reuse the existing login, process ownership and robotd IPC server. Bounded
writes never hold the primary channel's lock and never replay an action.
"""
import json
import queue
import threading
import time
from service_channel import ServiceChannel
from process_lifecycle import retire_process


class _AILog:
    def __init__(self,log):self.log=log
    def add(self,source,message):self.log.add('AI SSH / '+source,message)


class AIChannel(ServiceChannel):
    def __init__(self,target,socket_path,system_log=None,*,write_timeout=3.):
        super().__init__(target,socket_path,_AILog(system_log) if system_log else None)
        self.write_timeout=write_timeout
        self.writes=queue.Queue(maxsize=8)
        self.writer=threading.Thread(target=self._write_loop,daemon=True,name='Microduck-AI-SSH-Write')
        self.writer.start()

    def _write_loop(self):
        while not self.closed:
            try:proc,data,ack=self.writes.get(timeout=.1)
            except queue.Empty:continue
            try:
                with self.lock:current=proc is self.proc and not self.closed
                if not current:raise RuntimeError('AI 连接已变化，旧指令未重发')
                # No state lock is held while a pipe or SSH socket can stall.
                proc.stdin.write(data);proc.stdin.flush()
                ack.put_nowait(None)
            except Exception as exc:
                try:ack.put_nowait(exc)
                except queue.Full:pass
            finally:self.writes.task_done()

    def _abort(self,proc):
        with self.lock:
            if proc is not self.proc:return
            self.proc=None;self.reader=None;self.retry.failed()
        retire_process(proc,grace=0)

    def request(self,request,timeout,progress=None):
        response=queue.Queue(maxsize=1);ack=queue.Queue(maxsize=1)
        deadline=time.monotonic()+timeout
        with self.lock:
            self._ensure();self.counter+=1;ident=self.counter;proc=self.proc
            self.pending[ident]=(proc,response,progress)
        try:
            data=(json.dumps({**request,'channel_id':ident})+'\n').encode()
            if len(data)>2*1024*1024:raise ValueError('AI 请求过大')
            try:self.writes.put_nowait((proc,data,ack))
            except queue.Full:raise RuntimeError('AI 写入队列已满，本次指令未发送') from None
            try:error=ack.get(timeout=min(self.write_timeout,max(.001,deadline-time.monotonic())))
            except queue.Empty:
                self._abort(proc)
                raise TimeoutError('AI 专用连接写入超时；本次AI已中断，指令未重发') from None
            if error is not None:
                self._abort(proc)
                raise RuntimeError('AI 专用连接写入失败；指令未重发') from error
            try:reply=response.get(timeout=max(.001,deadline-time.monotonic()))
            except queue.Empty:
                self._abort(proc)
                raise TimeoutError('AI 专用连接回执超时；指令未重发') from None
            if reply.get('channel_error'):raise RuntimeError('AI 通道：'+str(reply['channel_error']))
            return reply['payload']
        finally:
            with self.lock:self.pending.pop(ident,None)

    def close(self):
        super().close()
        if self.writer is not threading.current_thread():self.writer.join(.2)

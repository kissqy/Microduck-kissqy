"""Desktop side of detached WSL training. Losing monitoring is not job failure."""
import json
from pathlib import Path
import threading
import time

ROOT=Path(__file__).resolve().parent
PREFIX='MICRODUCK_TRAINING '


def monitor_payload(job, create=False):
    source=(ROOT/'durable_agent.py').read_text(encoding='utf-8')
    request={'id':job['id'],'offset':job.get('durable_offset',0)}
    if create:
        names=('runtime_adapter.py','recovery_evaluation.py','sample_alignment.py','checkpoint_policy.py','live_view.py','event_protocol.py',
               'sim_protocol.py','recipe.py','official_spec.py','official_adapter.py','hd1910_actuator.py','hd1910_m6.json','deployment.py','action_filter.py','filtered_actions.py')
        bundle={name:(ROOT/name).read_text(encoding='utf-8') for name in names}
        request['source']=('WORKER_REQUEST = '+repr(job['request'])+'\nWORKER_BUNDLE = '+repr(bundle)+'\n'
                           +(ROOT/'worker.py').read_text(encoding='utf-8'))
    return ('DURABLE_REQUEST = '+repr(request)+'\nDURABLE_SOURCE = '+repr(source)+'\n'+source).encode('utf-8')


class DurableTrainingMixin:
    def reconnect_training(self):
        with self.lock:
            for job in list(self.jobs.values()):
                if (job.get('durable') and job['op']=='train' and
                        (job['status'] in ('starting','running','stopping') or
                         (job['status'] in ('completed','failed','stopped') and not job.get('ended'))) and
                        job['id'] not in self.processes and not job.get('_monitor_thread')):
                    job['_monitor_thread']=True
                    threading.Thread(target=self._run_durable,args=(job,False),daemon=True).start()

    def _run_durable(self, job, create=True):
        terminal=False
        while not self.closed and not terminal:
            proc=None
            try:
                proc=self.sessions.start(job['profile'],monitor_payload(job,create),channel='training-monitor')
                with self.lock:
                    self.processes[job['id']]=proc
                    self.pipe_locks[job['id']]=threading.Lock()
                    stopping=job['status']=='stopping'
                if stopping:self._stop_process(job,proc)
                path=self.directory/'runs'/job['id']/'output.log'
                path.parent.mkdir(parents=True,exist_ok=True)
                with path.open('a',encoding='utf-8') as logfile:
                    for raw in iter(proc.stdout.readline,b''):
                        if self.closed:break
                        line=raw.decode('utf-8',errors='replace').replace('\x00','').strip()
                        if not line:continue
                        try:
                            event=json.loads(line[len(PREFIX):]) if line.startswith(PREFIX) else {'kind':'log','line':line}
                            kind=event.get('kind')
                            if kind=='durable_attached':
                                create=False
                                with self.lock:
                                    job.update(durable_directory=event['directory'],monitor_connected=True)
                                    if job['status'] not in ('stopping','completed','failed','stopped'):
                                        job.update(status='running',message='已连接 WSL 后台训练；关闭中控不停止训练。')
                                    self.persist(job)
                            elif kind=='durable_cursor':
                                with self.lock:
                                    job['durable_offset']=event['offset']
                                    if time.monotonic()-self.last_save.get(job['id'],0)>2:self.persist(job)
                            elif kind in ('durable_exit','durable_missing'):
                                terminal=True
                                with self.lock:
                                    data=event.get('data',{});code=data.get('code',3 if kind=='durable_missing' else 1)
                                    job.update(worker_exit_code=code,ended=data.get('ended',time.time()),monitor_connected=False)
                                    if kind=='durable_missing':job.update(status='failed',message=event['message'])
                                    elif job['status'] not in ('failed','stopped','completed'):
                                        job.update(status='stopped' if job['status']=='stopping' else 'completed' if code==0 else 'failed',
                                                   message=data.get('message') or ('训练已结束。' if code==0 else 'WSL 训练进程退出，退出码 %s。'%code))
                                    self.persist(job)
                            elif kind=='durable_monitor_error':
                                raise OSError(event.get('message','后台训练连接异常'))
                            else:
                                # A display/parser/storage error may interrupt monitoring,
                                # but must never terminate the Linux training owner.
                                self._event(job,event)
                                if kind=='log':text=str(event.get('line',''))
                                elif kind in ('failed','stopped','complete'):text='['+kind+'] '+str(event.get('message',''))
                                elif kind=='command':text='[运行目录] '+str(event.get('cwd',''))+'\n[启动命令] '+json.dumps(event.get('argv'),ensure_ascii=False)
                                else:text=''
                                if text:logfile.write(text+'\n');logfile.flush()
                        except (ValueError,TypeError,KeyError,AttributeError) as error:
                            logfile.write('[中控显示消息异常，WSL训练继续] '+str(error)+'\n'+line+'\n');logfile.flush()
                if not self.closed and not terminal:
                    raise OSError('监控连接已断开，正在重连；WSL 后台训练不受影响。')
            except Exception as error:
                with self.lock:
                    job.update(monitor_connected=False,message='监控暂不可用，WSL训练未被停止：'+str(error))
                    if job['status'] not in ('starting','running','stopping','completed','failed','stopped'):job['status']='running'
                    try:self.persist(job)
                    except OSError:pass
            finally:
                if proc:
                    # EOF closes only this disposable monitor, not the training owner.
                    try:proc.stdin.close()
                    except (OSError,ValueError):pass
                    if proc.poll() is not None:
                        try:proc.stdout.close()
                        except (OSError,ValueError):pass
                with self.lock:
                    if self.processes.get(job['id']) is proc:self.processes.pop(job['id'],None)
                    self.pipe_locks.pop(job['id'],None)
            if not terminal and not self.closed:threading.Event().wait(1)
        with self.lock:
            job.pop('_monitor_thread',None)
            job['monitor_connected']=False
            try:self.persist(job)
            except OSError:pass

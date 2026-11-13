"""Zero voice worker: HAT <-> native Doubao, plus transient browser reply audio."""
import json
import os
import queue
import select
import signal
import sys
import threading
import time
import uuid
from collections import deque
from contextlib import contextmanager
from ai_doubao import DoubaoNative
from ai_hat_audio import hat_device
from ai_persona import DEFAULT_PERSONA, validate_persona, STAY_SILENT_DESCRIPTION
from ai_vision import VisualService, validate_vision, vision_tool
from ai_input_lease import ACTION_TOOLS, InputLease
from ai_voices import catalog,initial,tools as voice_tools


class EventWriter:
    """One bounded, nonblocking JSON writer; normal events precede image chunks.

    A slow diagnostics connection must not hold up the cloud tool receipt or
    native HAT playback. Complete JSON lines retain their order within a class.
    """
    def __init__(self,fd,stop):
        self.fd,self.stop=fd,stop;self.cv=threading.Condition()
        self.normal=deque();self.frames=deque();self.replays=deque(maxlen=24);self.closing=False;self.deadline=0
        self.was_blocking=os.get_blocking(fd);os.set_blocking(fd,False)
        self.thread=threading.Thread(target=self._run,daemon=True,name='Microduck-AI-Output')
        self.thread.start()

    def send(self,kind,event):
        data=(event+'\n').encode('utf-8')
        with self.cv:
            if self.closing:return False
            if kind=='assistant_audio_replay':
                self.replays.append(data)
            elif kind.startswith('vision_frame_'):
                # Preserve complete older photos for their chat turns. A bounded
                # slow relay refuses the current frame, never destroys earlier ones.
                if len(self.frames)>=704:return False
                self.frames.append(data)
            else:
                if len(self.normal)>=2000:
                    self.stop.set();return False
                self.normal.append(data)
            self.cv.notify()
        return True

    def _run(self):
        try:
            while True:
                with self.cv:
                    while not self.normal and not self.frames and not self.replays and not self.closing:self.cv.wait(.1)
                    if self.closing and not self.normal:return
                    data=self.normal.popleft() if self.normal else self.replays.popleft() if self.replays else self.frames.popleft()
                offset=0
                while offset<len(data):
                    if self.closing and time.monotonic()>=self.deadline:return
                    if not select.select([],[self.fd],[],.05)[1]:continue
                    try:offset+=os.write(self.fd,data[offset:])
                    except BlockingIOError:continue
        except (OSError,ValueError):self.stop.set()

    def close(self):
        with self.cv:
            self.deadline=time.monotonic()+.6;self.closing=True;self.frames.clear();self.replays.clear();self.cv.notify_all()
        self.thread.join(.9)
        if not self.thread.is_alive():
            try:os.set_blocking(self.fd,self.was_blocking)
            except OSError:pass


class GateRelay:
    def __init__(self,hub,tools):
        self.hub,self.tools=hub,tools
        self.speaking_enabled=False
        self.pending={}
        self.lock=threading.Lock()
        self.activity=threading.RLock()
        self.lease_factory=InputLease

    def tool_definitions(self):
        visual = [vision_tool()] if self.hub.vision.ready else []
        # HAT audio permission must not alter the model's capabilities or rules.
        tools=[{**t,'description':STAY_SILENT_DESCRIPTION} if t.get('name')=='stay_silent' else t for t in self.tools]
        return tools + visual + voice_tools(getattr(self.hub,'voices',initial(getattr(self.hub,'voice_id','zh_female_vv_jupiter_bigtts'))))

    def transcript(self,text,final=True,**fields):
        self.hub.log('transcript',text=text,final=final,**fields)

    def execute(self,name,args):
        if name not in ACTION_TOOLS:
            return self._execute(name,args)
        if not self.activity.acquire(blocking=False):
            return {'accepted':False,'reason':'正在执行动作或取帧，本次动作不排队'}
        try:return self._execute(name,args)
        finally:self.activity.release()

    @contextmanager
    def capture_guard(self):
        deadline=time.monotonic()+20;acquired=False
        try:
            while not self.hub.stop.is_set() and time.monotonic()<deadline:
                if self.activity.acquire(timeout=.1):acquired=True;break
            if not acquired:raise ValueError('动作尚未结束或会话已停止，本次未拍照')
            result=self._execute('wait_capture_model',{})
            if (result.get('accepted') is not True or result.get('status')!='model_idle'
                    or type(result.get('model_completed_t_ns')) is not int or result['model_completed_t_ns']<=0):
                raise ValueError(result.get('reason','未确认模型动作结束，本次未拍照'))
            yield result
        finally:
            if acquired:self.activity.release()

    def _execute(self,name,args):
        if name=='list_voices':
            return {'accepted':True,'voices':self.hub.voices,'voice_id':self.hub.provider.voice_id}
        if name=='switch_voice':
            if not isinstance(args,dict) or set(args)!={'voice_id'}:return {'accepted':False,'reason':'需要已保存的音色 ID'}
            return self.hub.provider.switch_voice(args['voice_id'])
        if name == 'inspect_scene':
            self.hub.log('tool_call', name=name, arguments=args)
            return self.hub.vision.inspect(args)
        lease=None;yielded=False;provider=getattr(self.hub,'provider',None)
        call_id=uuid.uuid4().hex
        reply=queue.Queue(maxsize=1)
        try:
            if name in ACTION_TOOLS:
                lease=self.lease_factory(self.hub.stop.is_set)
                lease.acquire()
            audible=(name=='express_emotion' or name=='head_expression' and (args or {}).get('gesture') in ('nod','shake')) and not self.hub.muted
            if audible and provider and hasattr(provider,'begin_expression_audio'):
                if not provider.begin_expression_audio():
                    return {'accepted':False,'reason':'HAT 播放通道未释放，本次表情未启动'}
                yielded=True
            with self.lock:self.pending[call_id]=reply
            self.hub.log('action_request',request_id=call_id,name=name,arguments=args,
                         **({'ai_input_token':lease.token} if lease else {}))
            deadline=time.monotonic()+(1.2 if name=='read_distance' else 20)
            while not self.hub.stop.is_set():
                if lease:lease.ensure_current()
                try:
                    result=reply.get(timeout=.1)
                    # A cached model label can change after manual takeover.
                    # An old tool receipt must not turn that into AI completion.
                    if lease:lease.ensure_current()
                    return result
                except queue.Empty:
                    if time.monotonic()>deadline:break
            return {'accepted':False,'available':False,'reason':'TOF 数据暂不可用'} if name=='read_distance' else {'accepted':False,'reason':'中控动作回执超时或会话已停止'}
        except (OSError,ValueError) as exc:
            return {'accepted':False,'reason':str(exc)}
        finally:
            with self.lock:self.pending.pop(call_id,None)
            if lease:
                try:self.hub.log('action_cancelled',ai_input_token=lease.token)
                finally:lease.close()
            if yielded:provider.end_expression_audio()

    def feedback(self,request_id,result):
        with self.lock:entry=self.pending.get(request_id)
        if entry:
            try:entry.put_nowait(result)
            except queue.Full:pass


class ZeroHub:
    def __init__(self,config,stop):
        self.stop=stop
        self.api_key=config['api_key']
        self.vision_settings=validate_vision(**config.get('vision', {}))
        self.persona=validate_persona(config.get('persona',DEFAULT_PERSONA))
        self.error=''
        self.provider_ready=False
        self.provider=None
        self.speech_session=config.get('speech_session','')
        self.voice_id=config.get('voice_id','zh_female_vv_jupiter_bigtts')
        self.voices=catalog(config.get('voices',initial(self.voice_id)),self.voice_id)
        self.muted=config.get('muted') is True
        self.output=None;self.output_lock=threading.Lock()
        self.gate=GateRelay(self,config['tools'])
        self.vision=VisualService(self.vision_settings,stop,self.log,
            distance=lambda stamp:self.gate.execute('read_distance',{'capture_t_ns':stamp}),
            capture_guard=self.gate.capture_guard)
        self.gate.speaking_enabled=config.get('voice_enabled') is True

    def log(self,kind,**fields):
        # Reply PCM has its own bounded live-only relay; no microphone PCM or credentials.
        if kind in ('audio_frame','input_audio','output_audio'):return
        event=json.dumps({'kind':kind,**fields},ensure_ascii=False,default=str)
        if self.api_key:event=event.replace(self.api_key,'[REDACTED]')
        if self.vision_settings['api_key']:event=event.replace(self.vision_settings['api_key'],'[REDACTED]')
        if self.output:return self.output.send(kind,event)
        else:
            with self.output_lock:print(event,flush=True)

    def start_output(self):self.output=EventWriter(sys.stdout.fileno(),self.stop)

    def close_output(self):
        if self.output:self.output.close()


def command_lines(fd,stop):
    """Read our pipe without a BufferedReader held during interpreter shutdown."""
    pending=bytearray()
    while not stop.is_set():
        while b'\n' in pending:
            end=pending.index(b'\n')
            if end>262144:raise ValueError('AI control message too large')
            line=bytes(pending[:end]);del pending[:end+1]
            if line.strip():yield line
            if stop.is_set():return
        if len(pending)>262144:raise ValueError('AI control message too large')
        if not select.select([fd],[],[],.1)[0]:continue
        chunk=os.read(fd,4096)
        if not chunk:return
        pending.extend(chunk)


def main():
    stop=threading.Event()
    lines=command_lines(sys.stdin.fileno(),stop)
    config=json.loads(next(lines))
    hub=ZeroHub(config,stop)
    hub.start_output()
    provider=DoubaoNative(hub,config['api_key'],config['voice_id'],hat_device(),hat_device(),stop)
    hub.provider=provider
    def commands():
        try:
            for line in lines:
                message=json.loads(line)
                if message.get('action')=='stop':break
                if message.get('action')=='mute':provider.set_muted(message.get('muted') is True)
                if message.get('action') in ('voice','voices'):
                    try:
                        if message['action']=='voice':provider.request_voice(message.get('voice_id'),message.get('request_id'))
                        else:provider.update_voices(message.get('voices'))
                    except (ValueError,TypeError) as exc:
                        provider.voice_error(message.get('request_id',''),message.get('voice_id',''),str(exc))
                if message.get('action')=='speech':
                    try:provider.set_speech(message.get('enabled'),message.get('request_id'))
                    except (ValueError,TypeError) as exc:
                        hub.log('speech_control',phase='error',request_id=message.get('request_id'),message=str(exc))
                if message.get('action')=='commit':provider.commit_input('manual')
                if message.get('action')=='vision':provider.inspect_scene(message.get('question'))
                if message.get('action')=='tools':
                    tools=message.get('tools')
                    if isinstance(tools,list) and len(tools)<=32:
                        hub.gate.tools=tools
                        provider.update_tools()
                if message.get('action')=='tool_result':
                    hub.gate.feedback(message.get('request_id'),message.get('result',{}))
        except (OSError,ValueError):pass
        finally:stop.set()
    command_thread=threading.Thread(target=commands,name='Microduck-AI-Control')
    command_thread.start()
    for sig in (signal.SIGTERM,signal.SIGINT):
        signal.signal(sig,lambda *_:stop.set())
    try:
        hub.log('zero_ready',message='AI 运行于 Zero；录音和播放均使用 HAT，电脑只显示日志。')
        provider.run()
    except Exception as exc:
        if not stop.is_set():hub.log('provider_error',reason=str(exc)[:500])
    finally:
        stop.set()
        provider.close()
        hub.vision.close()
        command_thread.join(timeout=1)
        hub.gate.speaking_enabled=False
        hub.log('zero_stopped',message='Zero AI 会话结束，HAT 音频进程已释放。',error=hub.error)
        hub.close_output()


if __name__=='__main__':main()

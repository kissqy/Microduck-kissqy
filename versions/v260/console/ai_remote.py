"""PC-side Zero AI controller; reply audio is relayed live to open browser windows."""
import base64
from contextlib import nullcontext
from collections import deque
import hashlib
import io
import math
from pathlib import Path
import queue
import threading
import time
import uuid
import zipfile
from ai_persona import DEFAULT_PERSONA
from ai_vision import FrameAssembler
from ai_input_lease import ACTION_TOOLS
from ai_voices import initial


def worker_bundle(root=None):
    root=Path(root or Path(__file__).parent)
    stream=io.BytesIO()
    paths=[root/name for name in ('ai_zero.py','ai_doubao.py','ai_hat_audio.py','ai_mouth_lease.py','ai_input_lease.py','ai_audio_meter.py','ai_pcm.py','ai_persona.py','ai_vision.py','ai_voices.py','_ai_vendor/__init__.py')]
    paths+=sorted((root/'_ai_vendor/websocket').glob('*.py'))
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in paths:archive.write(path,path.relative_to(root).as_posix())
    data=stream.getvalue()
    return base64.b64encode(data).decode('ascii'),hashlib.sha256(data).hexdigest()


class SpeechMouth:
    """Timed actual-PCM envelope; one bounded worker never stalls the speaker.

    Native expressions use 0..1 sound-envelope samples too. Frames are scheduled
    from HAT PCM byte timing, not an average duration divided by text length.
    """
    def __init__(self,gate):
        self.gate=gate;self.cv=threading.Condition()
        self.active=False;self.dirty=False;self.closed=False;self.revision=0
        self.audio_id='';self.frames=deque(maxlen=32);self.target=0.;self.until=0.
        self.worker=threading.Thread(target=self._run,name='Microduck-Speech-Mouth',daemon=True)
        self.worker.start()

    def feed(self,audio_id,opening,delay,seconds):
        values=(opening,delay,seconds)
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in values):return
        if not .2<=opening<=1 or not 0<=delay<=3 or not 0<seconds<=1:return
        with self.cv:
            if self.closed or not self.active or audio_id!=self.audio_id:return
            at=time.monotonic()+delay
            self.frames.append((at,float(opening),at+seconds));self.cv.notify_all()

    def set_active(self,active,audio_id=''):
        with self.cv:
            if self.closed:return
            self.active=bool(active);self.audio_id=audio_id;self.frames.clear()
            self.target=0.;self.until=0.;self.dirty=not active
            self.revision+=1;self.cv.notify_all()

    def close(self):
        with self.cv:
            self.active=False;self.dirty=True;self.closed=True;self.target=0.
            self.frames.clear();self.revision+=1;self.cv.notify_all()
        if self.worker is not threading.current_thread():self.worker.join(.2)

    def _run(self):
        while True:
            with self.cv:
                while not self.dirty and not self.closed:
                    now=time.monotonic()
                    while self.frames and self.frames[0][0]<=now:
                        _,self.target,self.until=self.frames.popleft();self.dirty=True
                    if self.dirty:break
                    if self.active and self.until and now>=self.until and self.target!=.2:
                        self.target=.2;self.dirty=True;break
                    due=self.frames[0][0] if self.frames else self.until if self.active and self.until>now else None
                    self.cv.wait(max(.001,min(.1,due-now)) if due else .1)
                opening=self.target if self.active and not self.closed else 0.
                revision=self.revision
            try:sent=self.gate.follow_speech_mouth(opening)
            except Exception:sent=False
            with self.cv:
                if revision!=self.revision:continue
                if self.closed:return
                self.dirty=not sent
                if self.dirty:self.cv.wait(.05)


class RemoteAI:
    def __init__(self,hub,channel,stop_event):
        self.hub,self.channel,self.stop_event=hub,channel,stop_event
        self.session_id=uuid.uuid4().hex
        self.events=queue.Queue(maxsize=2000)
        self.done=threading.Event()
        self.started=False
        self.stop_sent=False
        self.stopping_lock=threading.Lock()
        self.worker=None
        self.failure=None
        self.frames=FrameAssembler()
        self.action_slots=threading.BoundedSemaphore(4)
        self.mouth=None
        self.input_cancellations={};self.input_lock=threading.Lock()

    def close_mouth(self):
        if self.mouth:self.mouth.close()

    def _control(self,message):
        result=self.channel.request({'kind':'ai_control','session_id':self.session_id,
                                     'message':message},timeout=4)
        if result.get('accepted') is not True:raise RuntimeError(result.get('reason','Zero AI 未接收控制请求'))
        return result

    def set_muted(self,muted):return self._control({'action':'mute','muted':muted})

    def set_speech(self,enabled,request_id):
        return self._control({'action':'speech','enabled':enabled,'request_id':request_id})

    def update_tools(self,tools):return self._control({'action':'tools','tools':tools})

    def set_voice(self,identity,request_id):return self._control({'action':'voice','voice_id':identity,'request_id':request_id})

    def update_voices(self,voices):return self._control({'action':'voices','voices':voices})

    def commit_input(self):return self._control({'action':'commit'})

    def inspect_scene(self,question):return self._control({'action':'vision','question':question})

    def close(self):
        self.close_mouth()
        self.stop_event.set()
        with self.stopping_lock:
            if self.started and not self.stop_sent and not self.done.is_set():
                self.stop_sent=True
                try:self._control({'action':'stop'})
                except Exception as exc:self.hub.log('zero_stop_error',reason=str(exc))

    def _event(self,event):
        kind=event.get('kind')
        if kind=='voice_selection':
            self.hub.on_voice_selection(event)
            return
        if kind=='action_cancelled':
            with self.input_lock:
                pending=self.input_cancellations.get(event.get('ai_input_token'))
                if pending:pending.set()
            return
        if kind=='speaker_playback_started' and not self.stop_event.is_set():
            if self.mouth is None:self.mouth=SpeechMouth(self.hub.gate)
            self.mouth.set_active(True,event.get('audio_id',''))
        elif kind in ('speaker_playback_finished','speaker_error','provider_error','worker_stopped'):
            if self.mouth:self.mouth.set_active(False)
        if kind=='speaker_mouth':
            if self.mouth:self.mouth.feed(event.get('audio_id',''),event.get('open'),
                                         event.get('delay_seconds'),event.get('seconds'))
            return
        if kind=='assistant_audio_replay':
            self.hub.relay_audio(event)
            return
        if kind in ('vision_frame_start','vision_frame_chunk','vision_frame_end'):
            try:
                frame=self.frames.feed(event)
                if frame:self.hub.update_vision_frame(*frame)
            except (ValueError,TypeError,KeyError):
                self.frames.reset()
                self.hub.log('vision_preview_error',message='拍照预览传输不完整，请重新拍照；语音会话继续。')
            return
        fields={k:v for k,v in event.items() if k!='kind'}
        if kind=='worker_started':
            self.started=True
            if self.stop_event.is_set():self.close()
        if kind=='transcript':
            self.hub.gate.transcript(str(event.get('text','')),final=event.get('final') is True,
                                     item_id=event.get('item_id'))
            return
        if kind=='action_request':
            def reply(result):
                self._control({'action':'tool_result','request_id':event.get('request_id'),'result':result})
            token=event.get('ai_input_token')
            needs_input=event.get('name') in ACTION_TOOLS
            if needs_input and (not isinstance(token,str) or len(token)!=32 or any(c not in '0123456789abcdef' for c in token)):
                reply({'accepted':False,'reason':'AI 动作缺少已确认的输入租约'})
            elif event.get('name')=='read_distance':
                try:result=self.hub.read_distance(event.get('arguments') or {})
                except Exception as exc:result={'accepted':False,'available':False,'reason':str(exc)}
                reply(result)
            elif not self.action_slots.acquire(blocking=False):
                reply({'accepted':False,'reason':'动作请求过多，本次拒绝，不排队'})
            else:
                cancelled=threading.Event()
                if needs_input:
                    with self.input_lock:
                        if token in self.input_cancellations:
                            self.action_slots.release()
                            reply({'accepted':False,'reason':'AI 输入租约重复，本次动作未执行'})
                            return
                        self.input_cancellations[token]=cancelled
                # Finite native playback can last seconds. Keep draining transcription,
                # preview chunks and status while its completion is awaited on the PC.
                def perform():
                    try:
                        if self.stop_event.is_set():result={'accepted':False,'reason':'AI 会话已停止'}
                        else:
                            try:
                                if needs_input:
                                    with self.hub.gate.input_lease_context(token,
                                            lambda:cancelled.is_set() or self.stop_event.is_set()):
                                        controller=getattr(self.hub,'controller',None)
                                        # A standalone gate fixture has no web controller.
                                        guard=controller.ai_input_context(token) if controller is not None else nullcontext()
                                        with guard:
                                            result=self.hub.gate.execute(event.get('name'),event.get('arguments'))
                                else:
                                    result=(self.hub.gate.wait_capture_model() if event.get('name')=='wait_capture_model'
                                            else self.hub.gate.execute(event.get('name'),event.get('arguments')))
                            except Exception as exc:result={'accepted':False,'reason':str(exc)}
                        reply(result)
                    except Exception as exc:self.hub.log('tool_error',reason=str(exc))
                    finally:
                        if needs_input:
                            with self.input_lock:self.input_cancellations.pop(token,None)
                        self.action_slots.release()
                threading.Thread(target=perform,name='Microduck-AI-Action',daemon=True).start()
            return
        if kind=='provider_session' and event.get('event')=='session.created':self.hub.provider_ready=True
        if kind in ('provider_error','mic_error','speaker_error'):
            self.hub.error=str(event.get('reason','Zero AI 错误'))[:500]
        self.hub.log(kind,**fields)

    def run(self):
        bundle,checksum=worker_bundle()
        config={'api_key':self.hub.api_key,'voice_id':self.hub.voice_id,
                'voices':getattr(self.hub,'voices',initial(self.hub.voice_id)),
                'persona':getattr(self.hub,'persona',DEFAULT_PERSONA),
                'vision':getattr(self.hub,'vision_settings',{}),
                'tools':self.hub.gate.tool_definitions(),'voice_enabled':self.hub.gate.speaking_enabled,
                'speech_session':getattr(self.hub,'speech_session',''),
                'muted':getattr(self.hub,'muted',False)}
        def receive(event):
            # ServiceChannel reader must never execute tools or wait for its own RPC.
            try:self.events.put_nowait(event)
            except queue.Full:self.failure=RuntimeError('Zero AI 日志队列拥堵');self.stop_event.set()
        def request():
            try:
                result=self.channel.request({'kind':'ai_session','session_id':self.session_id,
                    'bundle':bundle,'bundle_sha256':checksum,'config':config,'progress':True},
                    timeout=24*3600,progress=receive)
                if result.get('returncode') and not self.stop_event.is_set():
                    self.failure=RuntimeError('Zero AI 工作进程异常结束')
            except Exception as exc:self.failure=exc
            finally:self.done.set()
        self.worker=threading.Thread(target=request,daemon=True,name='Microduck-Zero-AI-Events')
        self.worker.start()
        try:
            while not self.done.is_set() or not self.events.empty():
                current=getattr(self.hub,'ai_connection_current',None)
                if current and not current(self.channel):self.stop_event.set()
                if self.stop_event.is_set():self.close()
                try:event=self.events.get(timeout=.1)
                except queue.Empty:continue
                self._event(event)
            if self.failure and not self.stop_event.is_set():raise self.failure
        finally:
            self.close()
            self.worker.join(timeout=1)

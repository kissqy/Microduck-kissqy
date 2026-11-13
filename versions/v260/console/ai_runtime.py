"""Local-only AI console runtime with audit events and official robotd IPC.

AI is intentionally not part of robotd or the motion policy. All real speech
comes from the voice provider; no prerecorded/TTS words are substituted.
"""
from collections import deque, OrderedDict
from datetime import datetime
import json
from pathlib import Path
import re
import threading
import time
import uuid
from ai_action_gate import ActionGate, ActionDenied
from ai_conversation import Conversation
from ai_tof import distance_snapshot
from ai_preferences import AIPreferences, DEFAULT_VOICE, validate_credentials
from ai_persona import DEFAULT_PERSONA, validate_persona
from ai_vision import validate_vision, vision_question, BUSY_PHASES
from ai_voices import catalog,initial


class AIHub:
    ALLOWED_IPC = frozenset(('robot.skills','robot.policies','robot.do','robot.move',
                             'robot.head','robot.pose','robot.mouth'))
    def __init__(self, store, controller=None, service_controller=None, connection=None, preferences=None):
        self.store, self.controller = store, controller
        self.service_controller, self.connection = service_controller, connection
        self.started_at = time.time()
        self.closed = False
        self.events = deque(maxlen=3000)
        self.counter=0
        self.cv=threading.Condition()
        self.audio_listeners={}
        self.stop_event=threading.Event()
        self.worker=None
        self.provider=None
        self.ai_channel=None
        self.ai_channel_lock=threading.RLock()
        self.provider_ready=False
        self.speech_session=''
        self.speech_revision=-1
        self.speech_sent_at=0.0
        self.speech={'phase':'idle','request_id':'','enabled':False,'message':'豆包说话未启用'}
        self.error=''
        self.api_key=''
        self.voice_id=DEFAULT_VOICE
        self.voices=initial(self.voice_id)
        self.voice_selection={'phase':'idle','message':'当前音色','request_id':''}
        self.voice_revision=-1
        self.voice_state_revision=0
        self.persona=DEFAULT_PERSONA
        self.vision_settings=validate_vision()
        self.vision_status={'phase':'idle','message':'尚未拍照','observation':'','error':''}
        self.vision_frame=None
        self.vision_frames=OrderedDict()
        self.vision_frame_bytes=0
        self.camera_profile={'phase':'idle','message':'按需取景 · 拍照时临时唤醒'}
        self.camera_revision=0
        self.camera_lock=threading.RLock()
        self.camera_restore=None
        self.preferences=preferences if preferences is not None else AIPreferences()
        self.configuration_saved=False
        self.configuration_error=''
        try:
            saved=self.preferences.load()
            if saved:
                self.api_key,self.voice_id=saved['api_key'],saved['voice_id']
                self.voices=catalog(saved.get('voices',initial(self.voice_id)),self.voice_id)
                self.persona=saved.get('persona',DEFAULT_PERSONA)
                self.vision_settings=validate_vision(**saved.get('vision',{}))
                self.configuration_error=saved.get('vision_configuration_error','')
                self.configuration_saved=True
        except (OSError,ValueError,TypeError,KeyError):
            self.configuration_error='无法读取本机语音配置，请重新填写并保存。'
        self.muted=False
        self.conversation=Conversation()
        self.mic_level=None
        self.last_user_text=''
        self.last_assistant_text=''
        self.last_user_final=True
        self.last_assistant_blocked=False
        self.trace_dir=Path(__file__).resolve().parent/'logs'
        self.trace_dir.mkdir(parents=True,exist_ok=True)
        self.trace_file=self.trace_dir/('AI-Dialogue-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.jsonl')
        self.gate=ActionGate(self.rpc,self.robot_state,self.log,cancelled=lambda:self.stop_event.is_set(),
                             monitor=lambda:self.robot_state(read_policy=False))
        from release_identity import CONSOLE_VERSION
        self.log('ai_ready', console_version=CONSOLE_VERSION,
                 message='语音与独立动作就绪；摄像头默认按需取景。')

    def log(self,kind,**fields):
        for name in ('id','at'):
            if name in fields:fields.setdefault('source_'+name,fields.pop(name))
        # Binary/image data belongs only to the bounded preview relay.
        if kind in ('vision_frame_start','vision_frame_chunk','vision_frame_end','assistant_audio_replay'):return None
        # Never put API credentials into logs, SSE or exported events.
        for key in list(fields):
            if any(mark in key.lower() for mark in ('key','secret','token','password')):
                fields[key]='[REDACTED]'
            else:
                for secret in (self.api_key,self.vision_settings['api_key']):
                    if secret and secret in str(fields[key]):fields[key]=str(fields[key]).replace(secret,'[REDACTED]')
        with self.cv:
            self.counter+=1
            event={**fields,'id':self.counter,'at':datetime.now().isoformat(timespec='milliseconds'),
                   'kind':kind}
            if kind=='speech_control':
                if fields.get('request_id')!=self.speech.get('request_id'):return None
                self.speech.update({k:fields[k] for k in ('phase','message') if k in fields})
            if kind=='voice_state' and fields.get('source') in ('speech_control','startup'):
                if self.stop_event.is_set():return None
                session=fields.get('speech_session')
                if session!=self.speech_session:return None
                revision=fields.get('speech_revision')
                if type(revision) is not int or revision<=self.speech_revision:return None
                self.speech_revision=revision
                self.gate.speaking_enabled=fields.get('unlocked') is True
                if (self.speech['phase']!='pending' or
                        fields.get('control_request_id')==self.speech['request_id']):
                    self.speech.update(phase='applied',enabled=self.gate.speaking_enabled,
                                       message=fields.get('message','Zero已确认说话状态'))
                event['speech']=dict(self.speech)
            if kind=='mic_level':
                self.mic_level={**fields,'received_at_ms':round(time.time()*1000)}
            elif kind=='transcript':
                self.last_user_text=str(fields.get('text',''))
                self.last_user_final=fields.get('final') is True
            elif kind=='assistant_text':
                self.last_assistant_text=str(fields.get('text',''))
                self.last_assistant_blocked=fields.get('blocked') is True
            elif kind=='vision_state':
                if fields.get('phase') in ('queued','waiting_motion','capturing'):
                    self.vision_frame=None
                    for name in ('capture_id','width','height','captured_at_ms','mean_luma','exposure_ready',
                                 'exposure_warning','wait_seconds','sample_count','lift_applied',
                                 'photo_gamma','image_warning','read_ms','image_ms','capture_ms','api_ms',
                                 'total_ms','capture_backend','image_bytes','direct_frame'):self.vision_status.pop(name,None)
                self.vision_status.update(fields)
            elif kind in ('camera_exposure','vision_image','vision_timing'):self.vision_status.update(fields)
            elif kind=='camera_profile':self.camera_profile.update(fields)
            elif kind=='provider_stop' and self.vision_status.get('phase') in BUSY_PHASES:
                self.vision_status.update(phase='stopped',message='识图已随会话停止',error='')
            self.events.append(event)
            update=self.conversation.record(event)
            if update:event['conversation_update']=update
            # Level telemetry is live only. Keep full conversation/tool logs compact.
            if kind!='mic_level':
                with self.trace_file.open('a',encoding='utf-8') as f:
                    f.write(json.dumps({k:v for k,v in event.items() if k!='conversation_update'},ensure_ascii=False,default=str)+'\n')
            self.cv.notify_all()
        return event

    def status(self):
        with self.cv:
            conversation=self.conversation.snapshot()
            speech=dict(self.speech)
            if speech['phase']=='pending' and time.monotonic()-self.speech_sent_at>8:
                speech.update(phase='error',message='未收到Zero确认，当前显示上次确认状态')
        return {'running': bool(self.worker and self.worker.is_alive()),'provider_ready':self.provider_ready,'provider':'豆包实时语音 3.0',
                'voice_unlocked':self.gate.speaking_enabled,
                'speech':speech,'speech_revision':self.speech_revision,'speech_session':self.speech_session,
                'muted':self.muted,'skills':list(self.gate.skills),
                'expressions':list(self.gate.expressions.values()),'head_limits':self.gate.head_ranges(),
                'conversation':conversation,
                'credentials_present':bool(self.api_key),'error':self.error,
                'configuration_saved':self.configuration_saved,'configuration_error':self.configuration_error,
                'trace_file':self.trace_file.name,'connected':bool(self.connection and self.connection.active),
                'audio_route':'Zero / HAT 麦克风与扬声器','execution_host':'Zero',
                'mic_level':self.mic_level,'last_user_text':self.last_user_text,
                'last_assistant_text':self.last_assistant_text,
                'last_user_final':self.last_user_final,'last_assistant_blocked':self.last_assistant_blocked,
                'voice_id':self.voice_id,'persona':self.persona,
                'voices':self.voices,'voice_selection':dict(self.voice_selection),'voice_revision':self.voice_revision,
                'voice_state_revision':self.voice_state_revision,
                'camera_profile':dict(self.camera_profile),'camera_revision':self.camera_revision,
                'vision':{**self.vision_status,'enabled':self.vision_settings['enabled'],
                    'credentials_present':bool(self.vision_settings['api_key']),
                    'model':self.vision_settings['model'],'backlight':self.vision_settings['backlight']}, 'mode':'real', 'test_build':True}

    def _camera_event(self, **fields):
        with self.cv:
            self.camera_revision+=1
            fields['camera_revision']=self.camera_revision
            fields.setdefault('enabled',self.vision_settings['enabled'])
            self.log('camera_profile',**fields)

    def _camera_transport(self):
        from copy import copy
        if self.service_controller is None:
            raise ActionDenied('摄像头服务尚未连接')
        transport=copy(self.service_controller.transport)
        if not self.stop_event.is_set():transport.channel=self._get_ai_channel()
        return transport

    def _apply_camera_mode(self, enabled):
        """Only the camera service changes quality; voice and motion keep running."""
        with self.camera_lock:
            self._camera_event(phase='preparing',enabled=enabled,warning='',
                message='正在开启 720p / 目标15帧取景…' if enabled else '正在恢复按需取景…')
            try:
                transport=self._camera_transport()
                if enabled:
                    result=transport.prepare_ai_camera()
                    if result.get('accepted') is not True:raise ActionDenied('摄像头常开配置未确认')
                    if self.stop_event.is_set():
                        token=result.get('restore')
                        if token is not None:self.camera_restore=token
                        raise ActionDenied('AI 已停止，取消常开摄像头')
                    if result.get('restore') is not None and self.camera_restore is None:
                        self.camera_restore=result['restore']
                    self.vision_settings['enabled']=True
                    self._camera_event(phase='ready',warning='',quality='720p15',target_fps=15,
                        message='摄像头常开 · 720p / 目标15帧；实际帧率见视频回读')
                else:
                    # Release our preview even if restoring the saved quality fails.
                    self.vision_settings['enabled']=False
                    if self.camera_restore is not None:
                        result=transport.restore_ai_camera(self.camera_restore)
                        if result.get('accepted') is not True:raise ActionDenied('摄像头原质量未恢复')
                        self.camera_restore=None
                    self._camera_event(phase='idle',warning='',message='按需取景 · 拍照时临时唤醒')
            except Exception as exc:
                if enabled:self.vision_settings['enabled']=False
                self._camera_event(phase='warning',message='按需取景；常开设置未完成',warning=str(exc)[:300])
                raise

    def _finish_camera_mode(self):
        with self.camera_lock:
            if self.camera_restore is None and self.camera_profile.get('phase')=='warning':return
            if self.camera_restore is not None:
                try:
                    result=self._camera_transport().restore_ai_camera(self.camera_restore)
                    if result.get('accepted') is not True:raise ActionDenied('摄像头原质量未恢复')
                    self.camera_restore=None
                except Exception as exc:
                    self._camera_event(phase='warning',message='AI 取景已结束；原摄像头质量尚未恢复',warning=str(exc)[:300])
                    return
            self._camera_event(phase='idle',warning='',message='按需取景 · 拍照时临时唤醒')

    def set_camera_mode(self,args):
        if not isinstance(args,dict) or set(args)!={'enabled'} or type(args['enabled']) is not bool:
            raise ActionDenied('只允许设置摄像头是否常开')
        enabled=args['enabled']
        if not (self.worker and self.worker.is_alive()):
            return self.configure({'vision_enabled':enabled})
        if self.stop_event.is_set():raise ActionDenied('AI 正在停止')
        self._apply_camera_mode(enabled)
        try:
            self.preferences.save(self.api_key,self.voice_id,self.persona,vision=self.vision_settings,voices=self.voices)
        except (OSError,ValueError) as exc:
            self._camera_event(phase=self.camera_profile.get('phase','warning'),
                warning='本次设置已生效，但未保存：'+str(exc)[:160])
        return self.status()

    def audio_devices(self):
        return {'available':True,'devices':[],'route':'Zero / HAT 麦克风与扬声器',
                'message':'HAT 负责实时收音和播放；中控只在点击聊天喇叭时回听豆包回复，不录音。'}

    def configure(self,args):
        if self.worker and self.worker.is_alive():raise ActionDenied('请先停止 AI，再修改语音或视觉配置')
        if not isinstance(args,dict) or set(args)-{'api_key','voice_id','muted','persona','vision_api_key','vision_model','vision_enabled','vision_backlight','voices'}:
            raise ActionDenied('配置字段无效')
        if 'muted' in args and type(args['muted']) is not bool:raise ActionDenied('静音状态无效')
        if 'api_key' in args and (not isinstance(args['api_key'],str) or not args['api_key'].strip()):
            raise ActionDenied('豆包密钥无效')
        try:
            key,voice=validate_credentials(args.get('api_key',self.api_key),args.get('voice_id',self.voice_id))
            voices=catalog(args.get('voices',self.voices),voice)
            persona=validate_persona(args.get('persona',self.persona))
            vision=validate_vision(args.get('vision_api_key',self.vision_settings['api_key']),
                args.get('vision_model',self.vision_settings['model']),
                args.get('vision_enabled',self.vision_settings['enabled']),
                args.get('vision_backlight',self.vision_settings['backlight']))
        except ValueError as exc:raise ActionDenied(str(exc)) from None
        try:
            self.preferences.save(key,voice,persona,vision=vision,voices=voices)
        except (OSError,ValueError):
            raise ActionDenied('无法保存本机语音配置，请检查当前用户配置目录的写入权限。') from None
        self.api_key,self.voice_id=key,voice
        self.voices=voices
        self.voice_state_revision+=1
        self.persona=persona
        self.vision_settings=vision
        self.muted=args.get('muted',self.muted)
        self.configuration_saved=True
        self.configuration_error=''
        self.log('configuration',message='语音、视觉和角色配置已保存到本机，启动 AI 时生效。')
        return self.status()

    def set_voices(self,args):
        if not isinstance(args,dict) or set(args)!={'voices'}:raise ActionDenied('音色列表字段无效')
        with self.cv:
            if self.worker and self.worker.is_alive() and self.voice_selection.get('phase') in ('pending','unconfirmed'):raise ActionDenied('请先等待音色切换确认，或重连 AI')
            try:rows=catalog(args['voices'],self.voice_id,strict=True)
            except ValueError as exc:raise ActionDenied(str(exc)) from None
            self.preferences.save(self.api_key,self.voice_id,self.persona,vision=self.vision_settings,voices=rows)
            self.voices=rows
            self.voice_state_revision+=1
        if self.provider and self.worker and self.worker.is_alive():self.provider.update_voices(rows)
        return self.status()

    def set_voice(self,args):
        if not isinstance(args,dict) or set(args)!={'voice_id'}:raise ActionDenied('音色切换字段无效')
        identity=args['voice_id']
        with self.cv:
            if identity not in [row['id'] for row in self.voices]:raise ActionDenied('请先添加这个音色 ID')
            running=bool(self.worker and self.worker.is_alive())
            if running:
                if not self.provider_ready or self.stop_event.is_set():raise ActionDenied('豆包会话尚未就绪')
                if self.voice_selection.get('phase') in ('pending','unconfirmed'):raise ActionDenied('上次音色切换尚未确认，请等待或重连 AI')
                request_id=uuid.uuid4().hex
                self.voice_selection={'phase':'pending','request_id':request_id,'voice_id':identity,'message':'正在等待豆包确认音色'}
            else:
                self.preferences.save(self.api_key,identity,self.persona,vision=self.vision_settings,voices=self.voices)
                self.voice_id=identity
                self.voice_selection={'phase':'confirmed','voice_id':identity,'message':'启动 AI 时使用所选音色'}
            self.voice_state_revision+=1
        if running:
            try:self.provider.set_voice(identity,request_id)
            except Exception as exc:
                with self.cv:
                    self.voice_selection.update(phase='error',message=str(exc))
                    self.voice_state_revision+=1
                raise
        return self.status()

    def on_voice_selection(self,event):
        with self.cv:
            revision=event.get('voice_revision')
            if (self.stop_event.is_set() or event.get('voice_session')!=self.speech_session
                    or type(revision) is not int or revision<=self.voice_revision):return
            self.voice_revision=revision
            self.voice_state_revision+=1
            self.voice_selection={k:event[k] for k in ('phase','voice_id','request_id','message') if k in event}
            if event.get('phase')=='confirmed' and event.get('voice_id') in [row['id'] for row in self.voices]:
                self.voice_id=event['voice_id']
                try:self.preferences.save(self.api_key,self.voice_id,self.persona,vision=self.vision_settings,voices=self.voices)
                except (OSError,ValueError):self.voice_selection['message']='音色已切换，但本机保存失败'
            self.log('voice_selection',**{k:v for k,v in event.items() if k!='kind'})

    def set_audio(self,args):
        if not isinstance(args,dict) or set(args)!={'muted'} or type(args['muted']) is not bool:
            raise ActionDenied('只允许设置 HAT 静音开关')
        if self.provider:self.provider.set_muted(args['muted'])
        self.muted=args['muted']
        self.log('audio_state',muted=self.muted,message='HAT 已静音，文字仍正常返回' if self.muted else 'HAT 原生语音播放已开启')
        return self.status()

    def set_speech(self,args):
        if not isinstance(args,dict) or set(args)!={'enabled'} or type(args['enabled']) is not bool:
            raise ActionDenied('只允许设置是否启用豆包说话')
        if not self.provider or not self.provider_ready:raise ActionDenied('请先启动AI并连接豆包')
        with self.cv:
            if self.speech['phase']=='pending' and time.monotonic()-self.speech_sent_at<=8:
                raise ActionDenied('正在等待Zero确认说话状态')
            request_id=uuid.uuid4().hex;self.speech_sent_at=time.monotonic()
            self.speech={'phase':'pending','request_id':request_id,'enabled':args['enabled'],
                         'message':'正在启用说话…' if args['enabled'] else '正在关闭说话…'}
            self.log('speech_control',phase='pending',request_id=request_id,enabled=args['enabled'],message=self.speech['message'])
        try:self.provider.set_speech(args['enabled'],request_id)
        except Exception as exc:
            self.log('speech_control',phase='error',request_id=request_id,message='设置未送达Zero：'+str(exc)[:160])
            raise ActionDenied('说话设置未送达，当前仍显示上次确认状态') from None
        return self.status()

    def commit_input(self):
        if not self.provider or not self.provider_ready:raise ActionDenied('豆包会话尚未连接')
        self.provider.commit_input()
        return self.status()

    def inspect_scene(self,args):
        try:question=vision_question(args)
        except ValueError as exc:raise ActionDenied(str(exc)) from None
        if not self.provider or not self.provider_ready:raise ActionDenied('请先启动 AI 并连接豆包')
        if not self.vision_settings['api_key']:
            raise ActionDenied('请先填写火山方舟视觉 KEY 并保存配置')
        with self.cv:
            if self.vision_status.get('phase') in BUSY_PHASES:raise ActionDenied('正在识图，请稍候')
            self.log('vision_state',phase='queued',message='已请求 Zero 拍照…',error='',observation='')
        try:self.provider.inspect_scene(question)
        except Exception:
            self.log('vision_state',phase='error',message='拍照请求未送达 Zero',error='拍照请求未送达 Zero')
            raise ActionDenied('拍照请求未送达 Zero，请检查连接') from None
        return self.status()

    def update_vision_frame(self,meta,data):
        with self.cv:
            capture_id=meta['capture_id']
            # Keep bounded per-capture bytes for chat; the side preview still follows
            # only the current request. No photos are written to logs or preferences.
            if capture_id in self.vision_frames:
                self.vision_frame_bytes-=len(self.vision_frames.pop(capture_id))
            self.vision_frames[capture_id]=data
            self.vision_frame_bytes+=len(data)
            while len(self.vision_frames)>24 or self.vision_frame_bytes>32*1024*1024:
                _,old=self.vision_frames.popitem(last=False)
                self.vision_frame_bytes-=len(old)
            current=self.vision_status.get('request_id')
            is_current=self.vision_status.get('phase')!='queued' and (not current or current==capture_id)
            if is_current:
                self.vision_frame=(capture_id,data)
                self.vision_status.update({k:meta[k] for k in ('capture_id','width','height','captured_at_ms')})
        self.log('vision_preview',preview_current=is_current,capture_id=meta['capture_id'],width=meta['width'],height=meta['height'],
                 captured_at_ms=meta['captured_at_ms'],message='本次拍照预览已接收')
        return is_current

    def get_vision_frame(self,capture_id):
        with self.cv:
            return self.vision_frames.get(capture_id)

    def tail(self,after=0,limit=200):
        with self.cv:
            return {'events':[e for e in self.events if e['id']>after][:limit],
                    'last':self.counter,'status':self.status()}

    def stream(self,after=0):
        """Audio exists only in each connected stream's bounded transit queue.

        It has no SSE id/history and is never included in status, logs or exports.
        A new or refreshed page cannot retrieve any earlier reply audio.
        """
        listener=object();live=deque(maxlen=24)
        with self.cv:self.audio_listeners[listener]=live
        try:
            while not self.closed:
                with self.cv:
                    unseen=[e for e in self.events if e['id']>after]
                    if not unseen and not live and not self.closed:self.cv.wait(timeout=3)
                    unseen=[e for e in self.events if e['id']>after]
                    audio=list(live);live.clear()
                if not unseen and not audio and not self.closed:yield None
                for event in unseen:
                    after=event['id']
                    yield event
                yield from audio
        finally:
            with self.cv:
                self.audio_listeners.pop(listener,None)
                live.clear()

    def relay_audio(self,event):
        audio_id=event.get('audio_id');sequence=event.get('sequence');phase=event.get('phase')
        if (not isinstance(audio_id,str) or not re.fullmatch(r'[a-f0-9]{32}',audio_id)
                or type(sequence) is not int or not 0<=sequence<=20000
                or phase not in ('chunk','end','error')):return False
        fields={'kind':'assistant_audio_replay','audio_id':audio_id,'sequence':sequence,'phase':phase,'rate':24000}
        if phase=='chunk':
            data=event.get('data')
            if not isinstance(data,str) or not 0<len(data)<=16384:return False
            fields['data']=data
        with self.cv:
            for live in self.audio_listeners.values():live.append(fields)
            self.cv.notify_all()
        return True

    def _get_ai_channel(self):
        if self.closed:raise ActionDenied('AI入口已关闭')
        from ai_channel import AIChannel
        transport=self.service_controller.transport
        primary=transport.channel
        signature=(primary.target,primary.path)
        with self.ai_channel_lock:
            channel=self.ai_channel
            if channel is not None and (channel.target,channel.path)!=signature:
                channel.close();self.ai_channel=None
                if self.worker and self.worker.is_alive():
                    self.stop_event.set()
                    raise ActionDenied('机器人连接已切换，当前AI已停止，请重新启动AI')
                channel=None
            if channel is None or channel.closed:
                channel=AIChannel(*signature,getattr(transport,'log',None))
                self.ai_channel=channel
            return channel

    def _release_ai_channel(self,expected=None):
        with self.ai_channel_lock:
            channel=self.ai_channel
            if expected is not None and channel is not expected:return
            self.ai_channel=None
        if channel is not None:channel.close()

    def ai_connection_current(self,channel):
        if not self.connection or not self.connection.active:return False
        primary=self.service_controller.transport.channel
        return (channel.target,channel.path)==(primary.target,primary.path)

    def rpc(self, method, params=None):
        self.gate.ensure_input_current()
        if method not in self.ALLOWED_IPC:
            raise ActionDenied('AI权限不足：只开放白名单动作与只读动作查询')
        if not self.service_controller or not self.connection or not self.connection.active:
            raise ActionDenied('当前没有连接真实机器人，请先在中控 SSH 连接')
        if self.stop_event.is_set() and method not in ('robot.skills','robot.policies'):
            raise ActionDenied('AI已停止，本次动作未发送')
        token=self.gate.input_token()
        request={'method':method,'params':params or {},'timeout':8}
        if token is not None:request['ai_input_token']=token
        response=self._get_ai_channel().request(request,timeout=11)
        if response.get('id')!=1 or response.get('error'):
            error=response.get('error') or {}
            raise ActionDenied(error.get('message',str(error)) if isinstance(error,dict) else str(error))
        result=response.get('result')
        if not isinstance(result,dict):raise ActionDenied('robotd 返回结构无效')
        return result

    def robot_state(self,read_policy=True):
        snap=self.store.peek()
        bus=snap.get('bus') or {}
        native=bus.get('native') or {}
        control=self.controller.status(snap) if self.controller else {}
        pad=control.get('webpad') or {}
        connected=bool(self.connection and self.connection.active)
        # Prefer fresh snapshot. sit/stand can use robot.policies on explicit command only.
        sitting=bus.get('sitting')
        if type(sitting) is not bool and connected and read_policy:
            try:
                policy=self.rpc('robot.policies',{})
                sitting=policy.get('sitting')
            except Exception:pass
        fresh=snap.get('service_sample_fresh') is True
        checks=[
            (fresh,'实时反馈未就绪（样本年龄 '+str(snap.get('service_sample_age_ms','未知'))+' ms）'),
            (bus.get('mode')=='motion','当前模式不是运动模式：'+str(bus.get('mode','未知'))),
            (bus.get('phase')=='control','控制阶段尚未就绪：'+str(bus.get('phase','未知'))),
            (bus.get('homed') is True,'尚未 HOME' if bus.get('homed') is False else 'HOME 状态未确认'),
            (bus.get('policy_enabled') is True,'策略未启用' if bus.get('policy_enabled') is False else '策略状态未确认'),
            (native.get('torque_state_confirmed') is True,'舵机力矩未使能' if native.get('torque_state_confirmed') is False else '舵机力矩状态未确认'),
            (native.get('imu_ready') is True,'IMU 未就绪' if native.get('imu_ready') is False else 'IMU 状态未确认'),
            (not bus.get('torque_off_pending'),'正在等待卸力'),
        ]
        blockers=[reason for ok,reason in checks if not ok]
        settings=pad.get('settings') or (snap.get('system') or {}).get('pad_settings') or {}
        head_rad=settings.get('head_rad',2.5)
        state=snap.get('state') or {};channel=(snap.get('channels') or {}).get('state') or {}
        age=channel.get('age_ms')
        state_fresh=(channel.get('status')=='live' and type(age) in (int,float)
                     and 0<=age<500)
        return {'connected':connected,'fresh':fresh,'head_rad':head_rad,
                'mouth_percent':settings.get('mouth_percent',100),'audio_muted':self.muted,
                'policy':state.get('policy'),'state_t_ns':state.get('t_ns'),'state_fresh':state_fresh,
                'motion_ready':all(ok for ok,_ in checks[1:]),
                'motion_blockers':blockers,
                'readback':{**{name:bus.get(name) for name in ('mode','phase','homed','policy_enabled','torque_off_pending')},
                    'torque_state_confirmed':native.get('torque_state_confirmed'),
                    'imu_ready':native.get('imu_ready'),
                    'sample_age_ms':snap.get('service_sample_age_ms')},
                'webpad_active':bool(pad.get('owner')) and pad.get('input_active') is not False,
                'maintenance':bool(snap.get('service_operation') or snap.get('connection_paused')),
                'sitting':sitting if type(sitting) is bool else None}

    def load_skills(self):
        report=self.rpc('robot.skills',{})
        result=self.gate.set_skills(report)
        if self.provider and self.provider_ready:
            self.provider.update_tools(self.gate.tool_definitions())
        return result

    def read_distance(self,args):
        if not isinstance(args,dict) or set(args)-{'capture_t_ns'}:raise ActionDenied('测距参数无效')
        stamp=args.get('capture_t_ns')
        if stamp is not None and (type(stamp) is not int or stamp<=0):raise ActionDenied('取图时间无效')
        result=distance_snapshot(self.store.peek(),stamp)
        self.log('tof_context',result=result)
        return {'accepted':True,**result}

    def start(self):
        if self.worker and self.worker.is_alive():raise ActionDenied('豆包语音会话已经运行')
        if not self.api_key:raise ActionDenied('请先填写并保存豆包密钥')
        skills=self.load_skills()  # fail closed if robotd cannot enumerate installed skills
        if not skills:raise ActionDenied('机器人没有报告任何可用技能；拒绝启动')
        self.stop_event=threading.Event()
        self.gate.speaking_enabled=False
        self.speech_session=uuid.uuid4().hex
        self.speech_revision=-1
        self.voice_revision=-1
        self.voice_selection={'phase':'idle','voice_id':self.voice_id,'message':'当前音色'}
        self.voice_state_revision+=1
        self.speech={'phase':'idle','request_id':'','enabled':False,'message':'豆包说话未启用，鸭叫保留'}
        self.error=''
        self.mic_level=None
        self.last_user_text=''
        self.last_assistant_text=''
        self.last_user_final=True
        self.last_assistant_blocked=False
        self.provider_ready=False
        self.vision_status.update(phase='idle',message='视觉已就绪，可语音提问或点击拍照' if self.vision_settings['api_key'] else '视觉未配置，语音对话可正常使用',error='')
        with self.cv:self.conversation.begin()
        from ai_remote import RemoteAI
        self.provider=RemoteAI(self,self._get_ai_channel(),self.stop_event)
        self.worker=threading.Thread(target=self._run,daemon=True,name='Microduck-Zero-AI')
        self.worker.start()
        self.log('voice_state',unlocked=False,muted=self.muted,
                 message='豆包说话默认未启用；勾选“启用说话”后播放语音，鸭叫保留')
        return self.status()

    def _run(self):
        try:
            if self.stop_event.is_set():return
            if self.vision_settings['enabled']:
                try:self._apply_camera_mode(True)
                except Exception as exc:
                    self.log('camera_profile',phase='warning',enabled=False,
                             message='常开摄像头未开启；按需识图与语音仍可用',warning=str(exc)[:300])
            if self.stop_event.is_set():return
            self.provider.run()
        except Exception as exc:
            self.error=str(exc)[:400]
            self.log('provider_error',reason=self.error)
        finally:
            self._finish_camera_mode()
            self._release_ai_channel()
            self.log('provider_stop',message='本次语音会话结束')
            self.provider=None
            self.provider_ready=False
            self.gate.speaking_enabled=False
    
    def stop(self):
        # Close only the AI mouth input before cancellation retires its own SSH
        # channel. Keep this bounded; a failed AI channel cannot hold the console.
        if self.provider and hasattr(self.provider,'close_mouth'):self.provider.close_mouth()
        self.stop_event.set()
        if self.provider:
            try:self.provider.close()
            except Exception:pass
        self._finish_camera_mode()
        self._release_ai_channel()
        self.gate.speaking_enabled=False
        self.provider_ready=False
        self.speech={'phase':'idle','request_id':'','enabled':False,'message':'会话已停止'}
        self.log('voice_state',unlocked=False, message='已停止会话，权限重置')
        return self.status()

    def close(self):
        self.closed = True
        with self.cv:self.cv.notify_all()
        self.stop()
        if self.worker and self.worker.is_alive():self.worker.join(timeout=2)

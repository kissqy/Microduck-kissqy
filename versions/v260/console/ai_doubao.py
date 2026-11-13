"""Native Doubao Seeduplex realtime 3.0 WebSocket (official JSON event protocol).

Runs on Zero using bundled websocket-client + HAT ALSA audio; no pip install.
Requires a genuine Volcengine DoubaoVoice API Key.
Mic: 16 kHz int16 mono 20 ms packets; native PCM16/float32 is decoded to 24 kHz PCM16 for ALSA.
No separate TTS or canned voice. This module cannot change robotd/firmware.
"""
import base64
import math
import struct
from collections import deque, OrderedDict
import json
import queue
import threading
import time
import uuid
from ai_hat_audio import NativeMicrophone, NativeSpeaker
from ai_audio_meter import AudioMeter
from ai_pcm import PcmDecoder
from ai_persona import DEFAULT_PERSONA, TOOL_RULES, validate_persona
from ai_vision import VISION_RULES, vision_question
from ai_voices import catalog,initial

URL = 'wss://openspeech.bytedance.com/api/v3/duplex/realtime/dialogue'
MODEL = '1.2.6.1'
CLOUD_IO_TIMEOUT_S = 3.0


class MouthEnvelope:
    PARTIAL_CLOSE=.2
    def __init__(self):self.peak=.004

    def update(self,pcm):
        if not pcm or len(pcm)%2:raise ValueError('PCM16 packet is not aligned')
        energy=sum(v*v for (v,) in struct.iter_unpack('<h',pcm))
        rms=math.sqrt(energy/(len(pcm)//2))/32768
        self.peak=max(.004,rms,self.peak*.94)
        if rms<.0015:return self.PARTIAL_CLOSE
        voiced=max(0.,min(1.,(rms/self.peak-.1)/.9))
        return self.PARTIAL_CLOSE+(1.-self.PARTIAL_CLOSE)*math.sqrt(voiced)


class PlaybackPCM(bytes):
    """Keep the native PCM bytes tied to their reply across buffered playback."""
    def __new__(cls,data,audio_id):
        instance=super().__new__(cls,data)
        instance.audio_id=audio_id
        return instance


class DoubaoNative:
    def __init__(self, hub, api_key, voice_id, input_device, output_device, stop_event):
        self.hub, self.api_key, self.voice_id = hub, api_key, voice_id
        self.input_device, self.output_device = input_device, output_device
        self.stop_event = stop_event
        self.ws = None
        self.session_updates=deque()
        self.session_update_lock=threading.RLock()
        self.pending_voice=None
        self.voice_revision=0
        self.send_lock=threading.Lock()
        self.audio_queue=queue.Queue(maxsize=150)
        self.playback_bytes=OrderedDict()
        self.playback_cancel=threading.Event()
        if getattr(hub,'muted',False) or not hub.gate.speaking_enabled:self.playback_cancel.set()
        self.input_lock=threading.Lock()
        self.input_playing=False
        self.expression_audio=threading.Event()
        self.expression_audio_ready=threading.Event()
        self.input_release_at=0.0
        self.input_generation=0
        self.input_tail_seconds=.2
        self.mic_thread=None
        self.speaker_thread=None
        self.asr_partial={}
        self.assistant_partial={}
        self.reported_event_types=set()
        self.blocked_output_types=set()
        self.tool_lock=threading.Lock()
        self.tool_threads=set()
        self.pcm_decoder=PcmDecoder()
        self.audio_started=False
        self.turn_lock=threading.Lock()
        self.asr_pending=None
        self.input_sequence=0
        self.reply_waiting=None
        self.clock=time.monotonic
        self.assistant_sequence=0
        self.assistant_display_ids={}
        self.speech_revision=0
        self.seen_speech_ids=deque(maxlen=128)
        self.blocked_speech_ids=deque(maxlen=128)
        self.replay_current=None
        self.replay_response=None
        self.replay_keys=OrderedDict()
        self.replay_states=OrderedDict()

    def _reply_audio_id(self,event):
        keys=[(name,event[name]) for name in ('response_id','item_id') if isinstance(event.get(name),str)]
        found=next((self.replay_keys[key] for key in keys if key in self.replay_keys),None)
        if found:return found
        response=event.get('response_id')
        if self.replay_current is None or response and self.replay_response and response!=self.replay_response:
            self.replay_current=uuid.uuid4().hex;self.replay_response=response
        elif response:self.replay_response=response
        for key in keys:self.replay_keys[key]=self.replay_current
        while len(self.replay_keys)>128:self.replay_keys.popitem(last=False)
        return self.replay_current

    def _record_reply_audio(self,event,final=False):
        """Native returned PCM, live-only, independent of HAT speech permission.

        Keep at most eight bounded partial network buffers, never a recording.
        Ordinary logs and their history must never receive these binary events.
        """
        audio_id=self._reply_audio_id(event)
        state=self.replay_states.get(audio_id)
        if state is None:
            state={'decoder':PcmDecoder(),'pending':bytearray(),'sequence':0}
            self.replay_states[audio_id]=state
        while len(self.replay_states)>8:
            old_id,old=self.replay_states.popitem(last=False)
            self.hub.log('assistant_audio_replay',audio_id=old_id,sequence=old['sequence'],phase='error')
        try:
            raw=event.get('delta') or event.get('audio') or ''
            if not isinstance(raw,str) or len(raw)>2*1024*1024:raise ValueError('invalid reply PCM')
            pcm=state['decoder'].feed(base64.b64decode(raw,validate=True),final=final)
            if len(state['decoder'].pending)>262144:raise ValueError('reply PCM format was not identified')
            state['pending'].extend(pcm)
            while len(state['pending'])>=12000 or final and state['pending']:
                data=bytes(state['pending'][:12000]);del state['pending'][:12000]
                self.hub.log('assistant_audio_replay',audio_id=audio_id,sequence=state['sequence'],phase='chunk',
                    rate=24000,data=base64.b64encode(data).decode('ascii'))
                state['sequence']+=1
            if final:
                self.hub.log('assistant_audio_replay',audio_id=audio_id,sequence=state['sequence'],phase='end',rate=24000)
                self.replay_states.pop(audio_id,None)
        except (ValueError,TypeError):
            self.hub.log('assistant_audio_replay',audio_id=audio_id,sequence=state['sequence'],phase='error')
            self.replay_states.pop(audio_id,None)

    def _send(self,payload):
        if self.stop_event.is_set():return False
        payload.setdefault('event_id','event_'+uuid.uuid4().hex)
        with self.send_lock:
            if self.ws:
                self.ws.send(json.dumps(payload,ensure_ascii=False))
                return True
        return False

    def _session(self,mode='create'):
        # Keep the M6 audio contract; personality is now explicitly configurable.
        session={'instructions':validate_persona(getattr(self.hub,'persona',DEFAULT_PERSONA))+'\n'+TOOL_RULES}
        if getattr(getattr(self.hub,'vision',None),'ready',False):
            session['instructions']+='\n'+VISION_RULES
        data={'type':'session.'+mode,'session':session}
        # The documented create/update schema carries the same native audio
        # contract. Updating tool bounds never swaps models, voice or encoders.
        data['session'].update({'model':MODEL,
           'audio':{'input':{'format':{'type':'pcm','rate':16000}},
                    'output':{'format':{'type':'pcm','rate':24000},'voice':self.pending_voice['voice_id'] if self.pending_voice else self.voice_id,
                              'speed':0,'loudness':0}},
           'tools':self.hub.gate.tool_definitions()})
        if mode=='create':data['extension']={'asr':{},'tts':{},'dialog':{}}
        return data

    def _update_session(self,reason):
        with self.session_update_lock:
            if len(self.session_updates)>=16:raise ValueError('会话更新尚未确认，请重连AI后再发送')
            meta={'reason':reason}
            self.session_updates.append(meta)
            try:sent=self._send(self._session('update'))
            except Exception:
                self.session_updates.pop()
                raise
            if sent is False:
                self.session_updates.pop()
                return False
            return True

    def update_tools(self):return self._update_session('tools')

    def _voice_event(self,phase,identity,request_id,message):
        self.voice_revision+=1
        self.hub.log('voice_selection',phase=phase,voice_id=identity,request_id=request_id,
                     voice_revision=self.voice_revision,voice_session=getattr(self.hub,'speech_session',''),message=message)

    def voice_error(self,request_id,identity,message):
        self._voice_event('error',identity,request_id,message)

    def update_voices(self,rows):
        with self.session_update_lock:
            if self.pending_voice:raise ValueError('音色切换尚未确认，请稍后再改列表')
            self.hub.voices=catalog(rows,self.voice_id,strict=True)
            self.update_tools()

    def request_voice(self,identity,request_id=None):
        with self.session_update_lock:
            if identity not in [row['id'] for row in getattr(self.hub,'voices',initial(self.voice_id))]:raise ValueError('音色未添加到已保存列表')
            if self.pending_voice:raise ValueError('上次音色切换尚未确认；请等待或重连 AI')
            if not getattr(self.hub,'provider_ready',False) or self.stop_event.is_set():raise ValueError('豆包会话尚未就绪')
            request_id=request_id or uuid.uuid4().hex
            request={'voice_id':identity,'request_id':request_id,'done':threading.Event(),
                     'result':{'accepted':False,'reason':'音色切换尚未确认'}}
            if identity==self.voice_id:
                request['result']={'accepted':True,'voice_id':identity,'status':'confirmed'};request['done'].set()
                self._voice_event('confirmed',identity,request_id,'当前已使用该音色')
                return request
            if len(self.session_updates)>=16:raise ValueError('会话更新尚未确认，请稍后重试')
            self.pending_voice=request
            self.session_updates.append({'reason':'voice','request':request})
            self._voice_event('pending',identity,request_id,'正在等待豆包确认音色切换')
            try:
                if self._send(self._session('update')) is False:raise ValueError('豆包连接不可用')
            except Exception:
                self.session_updates.pop();self.pending_voice=None
                self.voice_error(request_id,identity,'音色切换未发送成功')
                raise
            def timeout():
                with self.session_update_lock:
                    if self.pending_voice is request and not request['done'].is_set():
                        request['result']={'accepted':False,'reason':'未收到豆包音色确认，请等待或重连 AI'}
                        request['done'].set();self._voice_event('unconfirmed',identity,request_id,request['result']['reason'])
            request['timer']=threading.Timer(8,timeout);request['timer'].daemon=True;request['timer'].start()
            return request

    def switch_voice(self,identity):
        request=self.request_voice(identity)
        request['done'].wait(8.5)
        return dict(request['result'])

    def _sync_playback_permission(self):
        if (not self.hub.gate.speaking_enabled or getattr(self.hub,'muted',False)
                or self.expression_audio.is_set()):self.playback_cancel.set()
        else:self.playback_cancel.clear()

    def _clear_voice_audio(self):
        self.playback_cancel.set()
        while True:
            try:self.audio_queue.get_nowait()
            except queue.Empty:break
        self.pcm_decoder.discard()

    def _voice_state(self,reason,source='speech_control',control_request_id=None):
        self.speech_revision+=1
        self.hub.log('voice_state',source=source,
            control_request_id=control_request_id,speech_revision=self.speech_revision,
            speech_session=getattr(self.hub,'speech_session',''),
            unlocked=self.hub.gate.speaking_enabled,
            message=reason)

    def _apply_speech_permission(self,enabled):
        self._clear_voice_audio()
        if not enabled:
            for key in tuple(self.seen_speech_ids):
                if key not in self.blocked_speech_ids:self.blocked_speech_ids.append(key)
        self.hub.gate.speaking_enabled=enabled
        self._sync_playback_permission()

    def set_speech(self,enabled,request_id):
        if type(enabled) is not bool:raise ValueError('是否启用说话必须为布尔值')
        with self.session_update_lock:
            self._apply_speech_permission(enabled)
            self._voice_state('Zero已确认：豆包说话已启用' if enabled else 'Zero已确认：豆包说话未启用，鸭叫保留',
                              source='speech_control',control_request_id=request_id)

    def _speech_blocked(self,event):
        keys=[(name,event[name]) for name in ('response_id','item_id') if isinstance(event.get(name),str)]
        for key in keys:
            if key not in self.seen_speech_ids:self.seen_speech_ids.append(key)
        if not self.hub.gate.speaking_enabled:
            for key in keys:
                if key not in self.blocked_speech_ids:self.blocked_speech_ids.append(key)
            return True
        return any(key in self.blocked_speech_ids for key in keys)

    def _ack_session_update(self):
        with self.session_update_lock:
            meta=self.session_updates.popleft() if self.session_updates else None
            if meta and meta.get('reason')=='voice':
                request=meta['request'];self.voice_id=request['voice_id'];self.pending_voice=None
                if request.get('timer'):request['timer'].cancel()
                request['result']={'accepted':True,'status':'confirmed','voice_id':self.voice_id}
                self._voice_event('confirmed',self.voice_id,request['request_id'],'音色已确认切换；后续生成的回复使用新音色')
                request['done'].set()

    def set_muted(self,muted):
        self.hub.muted=bool(muted)
        self._sync_playback_permission()
        if muted:
            while True:
                try:self.audio_queue.get_nowait()
                except queue.Empty:break
        self.hub.log('audio_state',muted=bool(muted),message='HAT 已静音，豆包文字继续返回' if muted else 'HAT 原生语音播放已开启')

    def commit_input(self,reason='manual'):
        with self.turn_lock:
            pending=self.asr_pending
            if not pending or pending['committed'] or self.stop_event.is_set():return False
            pending['committed']=True
            pending['commit_at']=self.clock()
            pending['warned']=False
            text=pending['text'];item_id=pending['display_id']
        if self._send({'type':'input_audio_buffer.commit'}) is False:return False
        self.hub.log('input_turn_commit',reason=reason,text=text,item_id=item_id,
                     message='已按豆包协议提交本句，等待最终识别和模型回复。')
        return True

    def _poll_input(self):
        # Diagnostics only: elapsed time never submits or cuts an utterance.
        now=self.clock();warning=None;stage='reply'
        with self.turn_lock:
            pending=self.asr_pending
            if pending:
                if pending['committed'] and not pending['warned'] and now-pending['commit_at']>=10:
                    pending['warned']=True
                    warning='本句已提交10秒，豆包尚未返回最终识别或回复。'
                elif not pending['committed'] and not pending.get('responded'):
                    if not pending.get('endpoint_warned') and now-pending['progress_at']>=6:
                        pending['endpoint_warned']=True;stage='endpoint'
                        warning='豆包已连接，正在等待豆包自动断句。'
            if self.reply_waiting and not self.reply_waiting['warned'] and now-self.reply_waiting['at']>=10:
                self.reply_waiting['warned']=True
                warning='已识别本句，但10秒内尚未收到豆包文字、语音或动作。'
        if warning:self.hub.log('input_turn_wait',stage=stage,message=warning)

    def _model_responded(self):
        with self.turn_lock:
            self.reply_waiting=None
            if self.asr_pending:
                self.asr_pending['responded']=True
                if self.asr_pending['committed']:self.asr_pending['warned']=True

    def _playback_input(self,playing):
        with self.input_lock:
            if self.input_playing==playing:return
            self.input_playing=playing
            self.input_generation+=1
            self.input_release_at=0.0 if playing else self.clock()+self.input_tail_seconds

    def begin_expression_audio(self):
        if self.stop_event.is_set():return False
        self.expression_audio_ready.clear()
        with self.input_lock:
            self.expression_audio.set();self.input_generation+=1
        self.playback_cancel.set()
        if self.expression_audio_ready.wait(1.2) and not self.stop_event.is_set():
            self.hub.log('expression_audio_state',active=True,message='HAT 已让出豆包播放通道，使用官方表情原配音')
            return True
        self.end_expression_audio()
        return False

    def end_expression_audio(self):
        with self.input_lock:
            self.expression_audio.clear();self.input_generation+=1
            self.input_release_at=self.clock()+self.input_tail_seconds
        self.expression_audio_ready.clear()
        self._sync_playback_permission()
        self.hub.log('expression_audio_state',active=False,message='官方表情结束，豆包语音仍受限'
                     if not self.hub.gate.speaking_enabled else '官方表情结束，豆包原生播放恢复')

    def _input_state(self):
        with self.input_lock:
            reason='playback' if self.input_playing or self.expression_audio.is_set() else 'tail' if self.clock()<self.input_release_at else ''
            return self.input_generation,bool(reason),reason

    def _microphone(self):
        meter=AudioMeter()
        was_blocked=False;reported_blocked=False
        try:
            with NativeMicrophone(self.input_device,self.stop_event) as mic:
                self.hub.log('mic_ready',message='HAT 麦克风已开启：16kHz 单声道，Zero 直接上传豆包。')
                while not self.stop_event.is_set():
                    before=self._input_state()
                    if was_blocked and not before[1]:
                        # Keep reading during playback, then discard any older
                        # capture pipe data before accepting a fresh user frame.
                        flush=getattr(mic,'discard_pending',None)
                        if flush:flush()
                        was_blocked=False
                        before=self._input_state()
                    raw=mic.read()
                    if raw:
                        after=self._input_state()
                        blocked=before[1] or after[1] or before[0]!=after[0]
                        reason=after[2] or before[2] or ('buffer' if blocked else '')
                        was_blocked=blocked
                        if blocked!=reported_blocked:
                            self.hub.log('input_gate',blocked=blocked,reason=reason,
                                message='播放期间已屏蔽麦克风输入' if blocked else 'HAT 播放结束，麦克风输入已恢复')
                            reported_blocked=blocked
                        # Preserve the realtime 20ms uplink/keepalive cadence;
                        # never send the captured speaker echo to the model.
                        outgoing=bytes(len(raw)) if blocked else bytes(raw)
                        try:
                            self._send({'type':'input_audio_buffer.append','audio':base64.b64encode(outgoing).decode('ascii')})
                        except Exception as exc:
                            self.hub.error='豆包语音上传：'+str(exc)[:350]
                            self.hub.log('provider_error',stage='audio_upload',reason=self.hub.error)
                            self.stop_event.set()
                            return
                        level=meter.update(raw)
                        if level:self.hub.log('mic_level',**level,input_blocked=blocked,block_reason=reason)
        except Exception as exc:
            if not self.stop_event.is_set():
                self.hub.error='麦克风：'+str(exc)[:350]
                self.hub.log('mic_error',reason=str(exc))
                self.stop_event.set()

    def _speaker(self):
        playing=False
        audio_id='';envelope=MouthEnvelope()
        def written(pcm,starts,seconds):
            nonlocal playing
            if not playing:
                playing=True
                self.hub.log('speaker_playback_started',audio_id=audio_id,
                             message='已向 HAT 播放进程写入豆包返回的音频。')
            self.hub.log('speaker_mouth',audio_id=audio_id,open=envelope.update(pcm),
                         delay_seconds=max(0.,starts-time.monotonic()),seconds=seconds)
        try:
            with NativeSpeaker(self.output_device,self.stop_event,self.playback_cancel) as out:
                out.pcm_observer=written
                self.hub.log('speaker_ready',message='HAT 扬声器待命：24kHz 单声道，按豆包语音权限播放。')
                while not self.stop_event.is_set():
                    if self.expression_audio.is_set():
                        out.close()
                        if playing:self.hub.log('speaker_playback_finished',message='HAT 豆包播放已让出给官方表情。')
                        playing=False;self._playback_input(False)
                        while True:
                            try:self.audio_queue.get_nowait()
                            except queue.Empty:break
                        self.expression_audio_ready.set()
                        self.stop_event.wait(.05)
                        continue
                    if (getattr(self.hub,'muted',False) or not self.hub.gate.speaking_enabled) and playing:
                        out.close();playing=False
                        self._playback_input(False)
                        self.hub.log('speaker_playback_finished',message='HAT 已停止播放豆包语音。')
                    try:pcm=self.audio_queue.get(timeout=.1)
                    except queue.Empty:continue  # A network gap is not the end of a reply.
                    if pcm is None:
                        completed=out.finish()
                        self._playback_input(False)
                        if playing:
                            self.hub.log('speaker_playback_finished',message='HAT 播放进程已完成本段音频。' if completed is not False else 'HAT 播放已取消。')
                            playing=False
                    elif self.hub.gate.speaking_enabled and not getattr(self.hub,'muted',False) and pcm:
                        audio_id=getattr(pcm,'audio_id','')
                        if not playing:envelope=MouthEnvelope()
                        if not playing:self._playback_input(True)
                        if out.write(pcm) is False:
                            self._playback_input(False)
                            if playing:self.hub.log('speaker_playback_finished',message='HAT 播放已取消。')
                            playing=False
                            continue
                        if not playing:
                            playing=True
                            self.hub.log('speaker_playback_started',audio_id=getattr(pcm,'audio_id',''),
                                         message='已向 HAT 播放进程写入豆包返回的音频。')
        except Exception as exc:
            if not self.stop_event.is_set():
                self.hub.error='扬声器：'+str(exc)[:350]
                self.hub.log('speaker_error',reason=str(exc))
                self.stop_event.set()
        finally:
            if playing:self.hub.log('speaker_playback_finished',message='HAT 豆包播放已结束。')
            self._playback_input(False)

    @staticmethod
    def _text(event):
        for name in ('text','transcript','delta','content'):
            value=event.get(name)
            if isinstance(value,str):return value
        item=event.get('item')
        if isinstance(item,dict):
            for name in ('text','transcript'):
                value=item.get(name)
                if isinstance(value,str):return value
        return ''

    def _tool_calls(self,event):
        items=event.get('items')
        if not isinstance(items,list):
            items=event.get('output') if isinstance(event.get('output'),list) else [event]
        for row in items:
            if not isinstance(row,dict):continue
            name=row.get('name') or (row.get('function') or {}).get('name')
            call_id=row.get('call_id')
            if not isinstance(name,str) or not isinstance(call_id,str):
                self.hub.log('provider_protocol_error',reason='函数回调缺少 name/call_id')
                continue
            args=row.get('arguments') or '{}'
            try:
                args=json.loads(args) if isinstance(args,str) else args
                result=self.hub.gate.execute(name,args)
            except Exception as exc:
                result={'accepted':False,'reason':str(exc)}
            self._send({'type':'conversation.item.create','items':[{
                'call_id':call_id,'role':'tool',
                'content':[{'type':'input_text','text':json.dumps(result,ensure_ascii=False)}]
            }]})
            self.hub.log('tool_feedback',name=name,call_id=call_id,arguments=args,result=result)

    def _handle(self,event):
        et=event.get('type','')
        if et in ('session.created','session.updated'):
            if et == 'session.created':self.hub.provider_ready=True
            elif et == 'session.updated':self._ack_session_update()
            self.hub.log('provider_session',event=et,session_id=(event.get('session') or {}).get('id'))
            if et=='session.created':
                self._voice_state('Zero已确认启动说话状态；鸭叫与电脑回听不受此开关影响',source='startup')
        elif et=='conversation.item.input_audio_transcription.started':
            with self.turn_lock:self.asr_pending=None
            self.hub.log('asr_started',item_id=event.get('item_id'))
        elif et=='conversation.item.input_audio_transcription.delta':
            txt=self._text(event)
            if txt:
                key=event.get('item_id','current')
                # Display the latest ASR hypothesis, as the official demo does.
                # Live deltas in the supplied log repeat/revise earlier words.
                # Concatenating them produced "你你好你好" from a single "你好".
                self.asr_partial[key]=txt
                with self.turn_lock:
                    if not self.asr_pending or self.asr_pending['key']!=key:
                        self.input_sequence+=1
                        self.asr_pending={'key':key,'display_id':event.get('item_id') or 'input-'+str(self.input_sequence),
                                          'committed':False,'text':txt,'progress_at':self.clock()}
                    hypothesis=''.join(c for c in txt if c.isalnum())
                    if hypothesis!=self.asr_pending.get('hypothesis'):
                        self.asr_pending.update(hypothesis=hypothesis,progress_at=self.clock(),endpoint_warned=False)
                    self.asr_pending.update(text=txt)
                    display_id=self.asr_pending['display_id']
                self.hub.gate.transcript(txt,final=False,item_id=display_id)
        elif et=='conversation.item.input_audio_transcription.completed':
            key=event.get('item_id','current')
            txt=self._text(event) or self.asr_partial.get(key,'')
            self.asr_partial.pop(key,None)
            with self.turn_lock:
                pending=self.asr_pending
                display_id=pending['display_id'] if pending and pending['key']==key else event.get('item_id') or key
                if pending and pending['key']==key:self.asr_pending=None
                self.reply_waiting={'at':self.clock(),'warned':False}
            self.hub.gate.transcript(txt,final=True,item_id=display_id)
        elif et=='conversation.item.input_audio_transcription.failed':
            with self.turn_lock:self.asr_pending=None
            self.hub.log('asr_error',reason=str(event.get('error') or '豆包输入语音转写失败'))
        elif et=='response.function_call_arguments.done':
            self._model_responded()
            # Motion skills may last seconds. Never block realtime audio receive on robot IO.
            self._dispatch_tools(event)
        elif et in ('response.output_text.done','response.output_text.delta',
                    'response.output_audio_transcript.done','response.output_audio_transcript.delta'):
            self._model_responded()
            key=event.get('item_id',event.get('response_id','current'))
            final=et.endswith('done')
            txt=self._text(event) or (self.assistant_partial.get(key,'') if final else '')
            if txt:
                if key not in self.assistant_display_ids:
                    self.assistant_sequence+=1
                    self.assistant_display_ids[key]=key if key!='current' else 'reply-'+str(self.assistant_sequence)
                current=self.assistant_partial.get(key,'')+txt if not final and isinstance(event.get('delta'),str) else txt
                self.assistant_partial[key]=current
                self.hub.log('assistant_text',text=current,final=final,blocked=self._speech_blocked(event),
                             message_id=self.assistant_display_ids[key],audio_id=self._reply_audio_id(event))
            if final:
                self.assistant_partial.pop(key,None)
                self.assistant_display_ids.pop(key,None)
            if self._speech_blocked(event):
                self._blocked_output('text')
        elif et in ('response.output_audio.started','response.output_audio.delta'):
            self._model_responded()
            self._record_reply_audio(event)
            if self._speech_blocked(event):
                self.pcm_decoder.discard()
                self._blocked_output('audio')
                return
            if self.expression_audio.is_set():
                self.pcm_decoder.discard()
                return
            if getattr(self.hub,'muted',False):
                self.pcm_decoder.discard()
                if 'muted' not in self.blocked_output_types:
                    self.blocked_output_types.add('muted')
                    self.hub.log('assistant_audio_muted',message='收到豆包语音，HAT 静音开关已拦截播放；文字正常显示。')
                return
            if et.endswith('delta'):
                chunk=event.get('delta') or event.get('audio','')
                if isinstance(chunk,str) and chunk:
                    try:
                        pcm=self.pcm_decoder.feed(base64.b64decode(chunk,validate=True))
                        if pcm:
                            audio_id=self._reply_audio_id(event)
                            self.audio_queue.put_nowait(PlaybackPCM(pcm,audio_id))
                            self.playback_bytes[audio_id]=self.playback_bytes.get(audio_id,0)+len(pcm)
                            while len(self.playback_bytes)>8:self.playback_bytes.popitem(last=False)
                    except (ValueError,queue.Full):
                        self.hub.log('audio_error',reason='音频帧解码失败或播放队列拥堵')
        elif et=='response.output_audio.done':
            self._record_reply_audio(event,final=True)
            if not self._speech_blocked(event) and not getattr(self.hub,'muted',False) and not self.expression_audio.is_set():
                try:
                    audio_id=self._reply_audio_id(event)
                    pcm=self.pcm_decoder.feed(b'',final=True)
                    if pcm:
                        self.audio_queue.put_nowait(PlaybackPCM(pcm,audio_id))
                        self.playback_bytes[audio_id]=self.playback_bytes.get(audio_id,0)+len(pcm)
                    self.hub.log('speaker_audio_duration',audio_id=audio_id,
                                 seconds=self.playback_bytes.pop(audio_id,0)/48000)
                    self.hub.log('assistant_audio_end')
                    self.audio_queue.put_nowait(None)
                except queue.Full:pass
        elif et=='input_audio_buffer.committed':
            with self.turn_lock:
                pending=self.asr_pending
                key=event.get('item_id')
                if pending and (not key or key==pending['key']) and not pending['committed']:
                    pending.update(committed=True,commit_at=self.clock(),warned=False)
            self.hub.log('input_turn_committed',event=et,item_id=event.get('item_id'))
        elif et=='session.closed':
            self.hub.log('provider_session',event=et)
            self.stop_event.set()
        elif et=='error':
            reason=event.get('error') or event
            self.hub.log('provider_error',reason=str(reason)[:600])
            raise RuntimeError('豆包返回错误：'+str(reason)[:350])
        elif et=='response.done':
            self._model_responded()
            finished_id=self.replay_keys.get(('response_id',event.get('response_id')),self.replay_current)
            if finished_id in self.replay_states:
                self._record_reply_audio(event,final=True)
            if finished_id==self.replay_current:self.replay_current=None;self.replay_response=None
            self.hub.log('model_turn_finished',usage=event.get('usage'))
            self.blocked_output_types.clear()
        elif et not in self.reported_event_types:
            self.reported_event_types.add(et)
            self.hub.log('provider_event',event=et,fields=list(event),
                         message='收到额外豆包事件，保留类型和字段名供核对。')

    def _blocked_output(self,kind):
        # Discard forbidden output at the playback boundary, while preserving
        # the microphone, tools and WebSocket for the next user turn.
        if kind in self.blocked_output_types:return
        self.blocked_output_types.add(kind)
        self.hub.log('model_violation',output=kind,
                     reason='豆包语音限制：'+('音频已丢弃，不送到HAT、不补播' if kind=='audio' else '文字仅在中控显示')+'；官方鸭叫保留，会话继续')

    def inspect_scene(self,question):
        """Button diagnostics: show real VLM text, then remember a complete QA pair.

        Seeduplex does not document response.create/text-query inference. Do not
        invent that event or synthesize speech from this text. A spoken question
        uses the real FC path and the server resumes native speech on its receipt.
        """
        question=vision_question({'question':question})
        def inspect():
            result=self.hub.vision.inspect({'question':question},source='button')
            if result.get('accepted') and not self.stop_event.is_set():
                capture_id=result['capture_id']
                context=result['observation']
                if isinstance(result.get('distance'),dict):context+='\n【同次TOF数据，未逐像素配准】'+json.dumps(result['distance'],ensure_ascii=False)
                self._send({'type':'conversation.item.create','items':[
                    {'id':'vision_user_'+capture_id,'type':'message','role':'user',
                     'content':[{'type':'input_text','text':'【中控拍照提问】'+question}]},
                    {'id':'vision_answer_'+capture_id,'type':'message','role':'assistant',
                     'content':[{'type':'input_text','text':'【视觉工具在刚才单帧中的观察】'+context}]}]})
                self.hub.log('vision_context',capture_id=capture_id,
                             message='本帧结果已加入对话；对着 HAT 提问可听语音回答。')
        self._background(inspect)

    def _background(self,operation):
        def run():
            try:operation()
            except Exception as exc:
                if not self.stop_event.is_set():self.hub.log('tool_error',reason=str(exc)[:400])
            finally:
                with self.tool_lock:self.tool_threads.discard(threading.current_thread())
        with self.tool_lock:
            if self.stop_event.is_set():return
            worker=threading.Thread(target=run,daemon=True,name='Microduck-AI-Tool')
            self.tool_threads.add(worker)
            worker.start()

    def _dispatch_tools(self,event):self._background(lambda:self._tool_calls(event))

    def run(self):
        from _ai_vendor import websocket
        self.hub.log('provider_connecting',url=URL,model=MODEL)
        try:
            self.ws=websocket.create_connection(URL,header={'X-Api-Key':self.api_key},timeout=12,enable_multithread=True)
            self.ws.settimeout(CLOUD_IO_TIMEOUT_S)
            self._send(self._session())
            if self.stop_event.is_set():return
            ready_deadline=self.clock()+15
            while not self.stop_event.is_set():
                try:raw=self.ws.recv()
                except websocket.WebSocketTimeoutException:
                    self._poll_input()
                    if not self.hub.provider_ready and self.clock()>ready_deadline:raise RuntimeError('豆包15秒未确认会话创建')
                    continue
                if self.stop_event.is_set():break
                if not raw:raise RuntimeError('豆包语音服务已断开')
                try:evt=json.loads(raw)
                except (TypeError,ValueError):
                    self.hub.log('provider_protocol_error',reason='非JSON事件，请确认 API 为3.0 Seeduplex')
                    continue
                self._handle(evt)
                if self.hub.provider_ready and not self.audio_started:
                    self.audio_started=True
                    self.mic_thread=threading.Thread(target=self._microphone,daemon=True,name='Microduck-Microphone')
                    self.speaker_thread=threading.Thread(target=self._speaker,daemon=True,name='Microduck-Speaker')
                    self.mic_thread.start();self.speaker_thread.start()
                self._poll_input()
        finally:
            self.close()

    def close(self):
        self.stop_event.set()
        with self.session_update_lock:
            if self.pending_voice:
                request=self.pending_voice
                if request.get('timer'):request['timer'].cancel()
                request['result']={'accepted':False,'reason':'会话已结束，音色切换未确认'};request['done'].set()
        with self.send_lock:
            if self.ws:
                try:self.ws.close(timeout=.2)
                except Exception:pass
        for worker in (self.mic_thread,self.speaker_thread):
            if worker and worker is not threading.current_thread():worker.join(timeout=1)
        with self.tool_lock:tools=list(self.tool_threads)
        for worker in tools:
            if worker is not threading.current_thread():worker.join(timeout=1)

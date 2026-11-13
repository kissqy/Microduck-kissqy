"""R17 browser input over persistent SSH to official robotd IPC."""
import re, threading, time
from contextlib import contextmanager
from input_channel import InputChannel
from session_sequences import SequenceWindow
from connection_retry import ConnectionRetry, RetryStopped
class ControlError(Exception):
    def __init__(self,message,status=409):super().__init__(message);self.status=status
class Transport:
    """PC-side input client. SSH only forwards bytes to the activated Unix socket."""
    AUDIO_HELPER = '/opt/robot/feetech-ft5-r5/audio-control.py'

    def __init__(self, target=None, socket_path="/run/robotd.sock", system_log=None):
        self.target, self.socket_path, self.log = target, socket_path, system_log
        self.write_lock = threading.RLock()
        self.connected = False
        self.suspended = False
        self.peer = self.reader = None
        self.input_channel = None
        self.input_retry = ConnectionRetry()
        self.status_listeners = set()
        self.status_lock = threading.RLock()
        self.input_prepared = False
        self.pad_status = {}
        self.pad_status_at = 0.0
        self.audio_status = {'id':0,'status':'idle','message':'声音通道等待连接'}
        self.service_transport = None
        self.audio_requested = False
        self.audio_generation = 0
        self.audio_lock = threading.Lock()

    def attach_service_transport(self, transport):
        self.service_transport = transport

    def ensure(self):
        # Readiness is local. Merely opening the dashboard must not activate an
        # input device or keep a remote status-polling Python process alive.
        if self.suspended:
            raise ControlError('Zero 关机已提交，自动连接已暂停；上电后点击恢复连接',409)
        self.connected = True

    def _close_input(self):
        channel,self.input_channel=self.input_channel,None
        self.input_prepared=False
        if channel is not None:channel.close()

    def _input_status(self, value):
        with self.status_lock:
            current={k:v for k,v in value.items() if k!='accepted'}
            changed=current!=self.pad_status
            self.pad_status=current
            self.pad_status_at=time.monotonic()
            listeners=tuple(self.status_listeners) if changed else ()
        for listener in listeners:
            listener(dict(self.pad_status))

    def subscribe_input_status(self, listener):
        with self.status_lock:
            self.status_listeners.add(listener)
            if self.pad_status:listener(dict(self.pad_status))
        def unsubscribe():
            with self.status_lock:self.status_listeners.discard(listener)
        return unsubscribe

    def _open_input(self, create=True):
        if self.input_channel is not None and self.input_channel.error:
            self._input_failed()
        if self.input_channel is None:
            if not create:return False
            self.input_retry.check()
            self.input_channel=InputChannel(self.target,self.socket_path,self._input_status,self.log)
            self.input_prepared=True
        try:self.input_channel.start()
        except Exception as exc:
            self._input_failed(str(exc))
            raise
        self.input_retry.connected()
        return True

    def _input_failed(self, reason=None):
        if self.input_channel is None:return
        reason = reason or self.input_channel.error or '网页输入连接已断开'
        self._close_input()
        self.connected = False
        self.input_retry.failed()
        self._input_status({'available':False,'event_authoritative':True,
                            'reason':str(reason)+'；'+self.input_retry.message()})
        if self.log:self.log.add('网页手柄重连', self.input_retry.message())

    def _audio(self, action, value=None):
        transport = self.service_transport
        if transport is None:
            raise ControlError('音量维护连接尚未就绪',503)
        args = ['python3', self.AUDIO_HELPER, action]
        if action == 'set-volume':args.append(str(value))
        result = transport._manage(args, privileged=False,record_output=False)
        if result.get('accepted') is not True:
            raise ControlError(result.get('reason') or '音量回读未确认',503)
        volume=result.get('audio',{}).get('volume')
        if type(volume) is not int or not 0<=volume<=100:
            raise ControlError(result.get('audio',{}).get('message') or '未取得有效系统音量',503)
        return result

    def _load_audio_once(self):
        if self.audio_requested or self.service_transport is None:return
        self.audio_requested = True
        generation = self.audio_generation
        self.audio_status = {**self.audio_status,'initializing':True}
        def load():
            try:
                with self.audio_lock:
                    result = self._audio('status')
                    if generation == self.audio_generation:
                        self.audio_status = result['audio']
                        if self.log:self.log.add('系统音量','读取成功 · '+str(result['audio']['volume'])+'%')
            except Exception as exc:
                if generation == self.audio_generation:
                    self.audio_status = {**self.audio_status,'initializing':False,'message':'音量未确认：'+str(exc)}
                    if self.log:self.log.add('系统音量','读取失败 · '+str(exc))
        threading.Thread(target=load,daemon=True).start()

    def _local_status(self):
        return {'accepted':True,'available':True,**self.pad_status,'audio':self.audio_status}

    def call(self, command):
        action = command.get('action')
        self.ensure()
        if action in ('connect','webpad_status'):
            if action == 'connect':
                with self.write_lock:
                    try:self._open_input()
                    except Exception:
                        self._close_input()
                        raise
                self._load_audio_once()
            return self._local_status()
        if action == 'set_volume':
            try:
                with self.audio_lock:
                    result = self._audio('set-volume',command['volume'])
                    if isinstance(result.get('audio'),dict):self.audio_status = result['audio']
            except Exception as exc:
                if self.log:self.log.add('系统音量','设置失败 · '+str(exc))
                raise
            if self.log:self.log.add('系统音量','设置成功 · '+str(result.get('volume',command['volume']))+'% · 已回读并保存')
            return result
        if action not in ('webpad_state','webpad_close'):
            raise ControlError('无效手柄操作',400)
        started = time.monotonic()
        with self.write_lock:
            if action == 'webpad_close' and self.input_channel is None:
                return self._local_status()
            # A slow first SSH authentication may prepare the channel but send
            # no input. Browser error cleanup must not undo that preparation.
            if action == 'webpad_close' and self.input_prepared:
                return self._local_status()
            expired_unsent = False
            try:
                if not self._open_input(create=action!='webpad_close'):
                    return self._local_status()
                if action == 'webpad_state' and time.monotonic()-started > .4:
                    expired_unsent = True
                    raise ControlError('输入已过期，未发送；请重新操作',503)
                request = {'action':'state' if action=='webpad_state' else 'close',
                           'owner':command['owner']}
                if action == 'webpad_state':request['frame'] = command.get('frame')
                self.input_prepared = False
                if action == 'webpad_state':request['context']=command.get('context',{})
                elif command.get('context'):
                    request['context']=command['context']
                result = self.input_channel.request(request)
                if not isinstance(result,dict) or type(result.get('accepted')) is not bool:
                    raise ValueError('手柄接口回执无效')
                # InputChannel._read publishes each response before waking this
                # waiter. A newer status may already be cached; do not replay
                # this older command receipt into the display cache.
                result['audio'] = self.audio_status
                result['control_rtt_ms'] = round((time.monotonic()-started)*1000,1)
                if result.get('accepted') is False and self.log:
                    self.log.add('手柄输入',result.get('reason','输入未接受'))
                # All browser owners share this transport. A delayed close for
                # an old page must not close the new owner's underlying socket.
                # Keep the event listener connected while the console is open.
                return result
            except Exception as exc:
                if not expired_unsent and not isinstance(exc, RetryStopped):self._input_failed()
                if self.log:self.log.add('手柄连接', '本次输入未重发：'+str(exc))
                if isinstance(exc,ControlError):raise
                raise ControlError('手柄连接已断开；本次输入未重发，请重新操作：'+str(exc),503) from exc

    def close(self):
        with self.write_lock:
            self._close_input()
            self.connected = False
            self.pad_status = {}
            self.pad_status_at = 0.0
            self.audio_generation += 1
            self.audio_requested = False
            self.audio_status = {**self.audio_status,'status':'idle','message':'声音通道未连接'}

    def suspend(self):
        with self.write_lock:
            self.suspended = True
            self.close()

    def resume(self):
        with self.write_lock:self.suspended = False

    def pause_input(self):
        with self.write_lock:
            if self.input_channel is not None and not self.input_channel.error:
                result = self.input_channel.request({'action':'reset'})
                if result.get('accepted') is not True:
                    raise ControlError(result.get('reason') or '旧输入清除未确认',503)
                # The ordered SSH reader has already published this receipt.
                # Re-publishing here could overwrite a newer status.

    def reconnect_after_service(self):
        self.pause_input()
        return self.call({'action':'connect'})


class Controller:
    def __init__(self,store,target=None,socket_path="/run/robotd.sock",transport=None,**_):
        self.store=store;self.transport=transport or Transport(target,socket_path,getattr(store,'system_log',None))
        self.lock=threading.RLock();self.sequences=SequenceWindow();self.pad={};self.message="等待网页手柄连接";self.error=""
        self.input_lock=threading.Lock()
        self.ai_input_owner=None
        self.ai_input_generation=0

    @contextmanager
    def ai_input_context(self, token):
        """Reserve only this AI action; reject new web input instead of queuing it."""
        if not isinstance(token,str) or not re.fullmatch(r'[a-f0-9]{32}',token):
            raise ControlError('AI 输入租约编号无效')
        acquired=False
        try:
            with self.input_lock:
                if self.ai_input_owner is not None:
                    raise ControlError('已有 AI 动作占用网页输入，本次拒绝，不排队')
                pad=dict(getattr(self.transport,'pad_status',None) or self.pad)
                if pad.get('owner') and pad.get('input_active') is not False:
                    raise ControlError('网页手柄正在占用，AI 动作暂停')
                self.ai_input_generation+=1
                self.ai_input_owner=token
                acquired=True
                if pad.get('owner'):
                    # Confirm remote handoff before AI can issue an intent.
                    # A later SSH EOF must find no old owner to zero out.
                    result=self.transport.call({'action':'webpad_close','owner':pad['owner'],
                        'context':{'keep_intents':True}})
                    if (result.get('accepted') is not True or 'owner' not in result
                            or result['owner'] is not None or result.get('input_active') is not False):
                        raise ControlError(result.get('reason') or '旧网页占用未释放，AI 动作未开始')
            yield
        finally:
            if acquired:
                with self.input_lock:
                    if self.ai_input_owner == token:
                        self.ai_input_generation+=1
                        self.ai_input_owner=None
    def attach_service_transport(self, transport):
        self.transport.attach_service_transport(transport)
    def status(self, snapshot=None):
        with self.lock:
            if snapshot is None:snapshot=getattr(self.store,'peek',self.store.snapshot)()
            bus=snapshot.get('bus',{})
            pad=dict(getattr(self.transport,'pad_status',None) or self.pad)
            system=snapshot.get('system',{})
            age=snapshot.get('channels',{}).get('system',{}).get('age_ms')
            system_at=time.monotonic()-age/1000 if isinstance(age,(int,float)) else 0
            # The low-rate native system sample supplies display state without
            # activating webpad. A newer input rejection takes precedence until
            # the next system sample; arbitration always remains on the Zero.
            if not pad.get('event_authoritative') and isinstance(system.get('real_gamepads'),list) and system_at>=getattr(self.transport,'pad_status_at',0):
                devices=system['real_gamepads']
                pad.update(real_connected=bool(devices),real_devices=devices)
            if isinstance(system.get('pad_settings'),dict):pad['settings']=system['pad_settings']
            if 'pad_settings_error' in system:pad['settings_error']=system['pad_settings_error']
            return {'available':True,'connected':self.transport.connected,'balance_active':bus.get('policy_enabled') is True,
                    'webpad':pad,'message':self.message,'error':self.error,'audio':self.transport.audio_status}
    def handle(self,payload):
        generation=self.ai_input_generation
        if isinstance(payload,dict) and payload.get('action')=='webpad_state' and self.ai_input_owner is not None:
            raise ControlError('AI 动作执行中，网页手柄输入已暂停；本次输入未排队')
        if isinstance(payload,dict) and isinstance(payload.get('client'),str):
            action=payload.get('action')
            key=(payload['client'],'input' if action in ('webpad_state','webpad_close') else str(action))
            with self.sequences.protect(key):return self._handle(payload,_input_generation=generation)
        return self._handle(payload,_input_generation=generation)
    def _handle(self,payload,*,_input_generation=None):
        if _input_generation is None:_input_generation=self.ai_input_generation
        if getattr(self.store,'connection_paused',None) and self.store.connection_paused.is_set():
            raise ControlError('Zero 关机已提交，自动连接已暂停；上电后点击恢复连接',409)
        if not isinstance(payload,dict) or set(payload)-{'action','client','seq','frame','volume'}:raise ControlError('无效手柄请求',400)
        action=payload.get('action');client=payload.get('client');seq=payload.get('seq')
        if not isinstance(client,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,80}',client):raise ControlError('无效网页标识',400)
        if type(seq) is not int or not 0<=seq<=2**53:raise ControlError('无效请求序号',400)
        if action not in ('connect','webpad_state','webpad_status','webpad_close','set_volume'):raise ControlError('此中控只使用官方手柄动作接口',400)
        if action=='set_volume' and (type(payload.get('volume')) is not int or not 0<=payload['volume']<=100):raise ControlError('音量必须为 0～100 的整数',400)
        # Do not wait behind final AI cleanup and then forward a stale press.
        # The locked send path rechecks after this optimistic fast rejection.
        if action=='webpad_state' and self.ai_input_owner is not None:
            raise ControlError('AI 动作执行中，网页手柄输入已暂停；本次输入未排队')
        if action=='webpad_state' and _input_generation!=self.ai_input_generation:
            raise ControlError('已丢弃跨越 AI 动作的旧网页输入，请重新操作')
        with self.lock:
            lane='input' if action in ('webpad_state','webpad_close') else action
            key=(client,lane)
            try:self.sequences.accept(key,seq)
            except ValueError as exc:raise ControlError(str(exc)) from None
            if action=='webpad_state':
                s=self.store.snapshot();bus=s.get('bus',{})
                if s.get('service_operation') or s.get('service_control',{}).get('busy') and s.get('service_control',{}).get('job',{}).get('action') not in {'set-pad-settings'}:raise ControlError('等待服务操作完成')
                if not s.get('service_compatible') or bus.get('mode')!='motion' or bus.get('phase')!='control':raise ControlError('先升级配套 R17 / 0.15.1 服务并切到运动模式')
        if action=='set_volume':
            result=self.transport.call({'action':action,'volume':payload['volume']})
            if result.get('accepted') is not True:raise ControlError(result.get('reason','音量未确认'))
            if isinstance(result.get('audio'),dict):self.transport.audio_status=result['audio']
            return result
        def send():
            if action in ('webpad_state','webpad_close'):
                with self.lock:
                    if seq<self.sequences.get(key,-1):raise ControlError('过期输入已丢弃')
                if action=='webpad_state' and _input_generation!=self.ai_input_generation:
                    raise ControlError('已丢弃跨越 AI 动作的旧网页输入，请重新操作')
                if self.ai_input_owner is not None:
                    if action=='webpad_state':
                        raise ControlError('AI 动作执行中，网页手柄输入已暂停；本次输入未排队')
                    # Remote ownership was cleared before AI began. A page's
                    # late close must not emit a zero intent during the action.
                    return {'accepted':True,**dict(getattr(self.transport,'pad_status',None) or self.pad)}
            result=self.transport.call({'action':action,'owner':client,**({'frame':payload.get('frame'),'context':{'settings':s.get('system',{}).get('pad_settings',{})}} if action=='webpad_state' else {})})
            return result
        try:
            if action in ('webpad_state','webpad_close'):
                with self.input_lock: result=send()
            else:result=send()
        except Exception:
            if action=='connect':self.sequences.retire(key)
            raise
        with self.lock:
            self.pad={k:v for k,v in result.items() if k not in ('accepted','control_rtt_ms')}
            self.message=result.get('reason') or ('真实手柄已接管' if result.get('real_connected') else '网页输入经持久 SSH 直达官方 robotd IPC')
            if result.get('accepted') is not True:
                if action=='connect':self.sequences.retire(key)
                raise ControlError(self.message)
            return result
    def release_owner(self, owner):
        # Disconnect is an owner-scoped release, never a fabricated button edge.
        # A new connection has its own owner, so late cleanup cannot cancel it.
        try:
            if not (getattr(self.store,'connection_paused',None) and self.store.connection_paused.is_set()):
                with self.input_lock:
                    # Remote handoff already completed before the AI action.
                    if self.ai_input_owner is None:
                        self.transport.call({'action':'webpad_close','owner':owner})
        except Exception as exc:
            if getattr(self.transport,'log',None):self.transport.log.add('手柄长连接错误','断线撤销未确认；由 Zero 输入租约兜底：'+str(exc))
        finally:
            with self.lock:
                for key in list(self.sequences):
                    if key[0]==owner:self.sequences.retire(key)
    def pause_input(self):
        with self.input_lock:self.transport.pause_input()
    def close(self):self.transport.close()
    def reconnect_after_service(self):
        with self.input_lock:
            result=self.transport.reconnect_after_service()
        return self._confirm_service_input(result)
    def refresh_after_service(self):
        with self.input_lock:
            result=self.transport.call({'action':'connect'})
        return self._confirm_service_input(result)
    def _confirm_service_input(self,result):
        with self.lock:
            self.pad={k:v for k,v in result.items() if k not in ('audio','control_rtt_ms')}
            if result.get('accepted') is not True or result.get('available') is not True:
                self.error='服务已更新，但网页手柄连接未恢复：'+str(result.get('reason') or result.get('error') or '接口未确认就绪')
                self.pad={**self.pad,'available':False,'error':self.error}
                raise ControlError(self.error,503)
            self.error='';self.message='服务操作后控制连接已恢复，网页输入可用'
            return {'webpad_reconnected':True,'available':True,'real_connected':result.get('real_connected',False)}
    def suspend_connections(self):self.transport.suspend()
    def resume_connections(self):self.transport.resume()

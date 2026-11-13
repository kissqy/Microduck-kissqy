"""Isolated AI capability gate: only loaded robot actions, never maintenance.

The actual realtime model chooses tools. No text-matching action scripts are used.
Robot readiness, installed skills and active web input are checked at execution.
An attached physical gamepad does not reserve AI actions.
"""
import math
from contextlib import contextmanager
import re
import threading
import time
from ai_persona import STAY_SILENT_DESCRIPTION
from management_profile import PROFILE


class ActionDenied(ValueError):
    def __init__(self,reason,*,state=None):
        super().__init__(reason)
        self.state=state


def numeric(x, low, high, name):
    if type(x) not in (int, float) or not math.isfinite(x) or not low <= x <= high:
        raise ActionDenied(f"{name} 必须为 {low}～{high} 的数字")
    return float(x)


class ActionGate:
    HEAD_KEYS = ('neck_pitch', 'head_pitch', 'head_yaw', 'head_roll')

    def __init__(self, rpc, state, log, *, clock=time.monotonic, sleep=time.sleep, cancelled=lambda:False, monitor=None):
        self.rpc, self.state, self.log = rpc, state, log
        self.clock, self.sleep, self.cancelled = clock, sleep, cancelled
        self.monitor=monitor or state
        self.lock = threading.RLock()
        self.active_action = None
        self.speaking_enabled = False
        self.skills = ()
        self.expressions = {}
        self.head_reference = {}
        self.model_timeouts={}
        self.input_context=threading.local()

    @contextmanager
    def input_lease_context(self,token,cancelled):
        if not isinstance(token,str) or not re.fullmatch(r'[a-f0-9]{32}',token):
            raise ActionDenied('AI 输入租约编号无效')
        previous=getattr(self.input_context,'current',None)
        self.input_context.current=(token,cancelled)
        try:
            self.ensure_input_current()
            yield
        finally:self.input_context.current=previous

    def input_token(self):
        current=getattr(self.input_context,'current',None)
        return current[0] if current else None

    def ensure_input_current(self):
        current=getattr(self.input_context,'current',None)
        if current and current[1]():raise ActionDenied('AI 动作输入租约已取消')

    def transcript(self, text, final=True, **fields):
        self.log('transcript', text=text, final=final,**fields)

    def set_skills(self, report):
        if not isinstance(report, dict) or not isinstance(report.get('skills'), list) or not isinstance(report.get('built_in'), list):
            raise ActionDenied('robot.skills 未返回可验证动作清单，拒绝开放动作')
        names = [];timeouts={}
        for s in report['skills']:
            name = s.get('name') if isinstance(s, dict) else None
            if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9_]{1,63}', name):
                raise ActionDenied('robot.skills 返回无效名称')
            if name in PROFILE.get('retired_skill_names',[]):
                continue
            names.append(name)
            duration=s.get('duration');unwind=s.get('unwind_s',0)
            if type(duration) in (int,float) and math.isfinite(duration) and duration>0:
                if type(unwind) not in (int,float) or not math.isfinite(unwind) or unwind<0:unwind=0
                timeouts[name]=min(18,max(3,duration+unwind+2))
        for name in report['built_in']:
            if name not in ('sit_toggle', 'ground_pick'):
                raise ActionDenied(f'未知内置动作 {name!r}，需要先核对固件')
            names.append(name)
        expressions = {}
        for row in report.get('expressions', []):
            if not isinstance(row, dict):raise ActionDenied('表情清单无效')
            name = row.get('name')
            if (name not in ('sad','devastated','curious','mmh','yes','yes_fast','no','angry','excited','laugh','mock','defiant','impatient')
                    or type(row.get('silent')) is not bool
                    or row.get('skill') != ('emotion_silent_' if row['silent'] else 'emotion_')+name
                    or row.get('silent_skill','emotion_silent_'+name) != 'emotion_silent_'+name
                    or not isinstance(row.get('label'),str) or not isinstance(row.get('meaning'),str)):
                raise ActionDenied('表情清单与官方有限表情不符')
            numeric(row.get('seconds'), .1, 15, '表情时长')
            expressions[name] = dict(row)
        reference = report.get('head_limits') or {}
        axes = reference.get('axes') or {}
        checked = {}
        if reference:
            if reference.get('kind') != 'model_reference' or reference.get('unit') != 'rad':
                raise ActionDenied('头部范围来源或单位无效')
            for axis in self.HEAD_KEYS:
                span = axes.get(axis) or {}
                low = numeric(span.get('min'), -math.pi, 0, axis)
                high = numeric(span.get('max'), 0, math.pi, axis)
                if low >= high:raise ActionDenied('头部范围无效')
                checked[axis] = (low, high)
        self.skills = tuple(dict.fromkeys(names))
        self.model_timeouts=timeouts
        self.expressions = expressions
        self.head_reference = checked
        self.log('catalog', skills=list(self.skills), expressions=list(expressions.values()),
                 head_limits=self.head_ranges(), source='robot.skills')
        return list(self.skills)

    def tool_definitions(self):
        def t(name, desc, fields=None, required=()):
            return {'type':'function','name':name,'description':desc,'parameters':{
                'type':'object','properties':fields or {},'required':list(required),'additionalProperties':False}}
        num = lambda desc,lo,hi: {'type':'number','description':desc,'minimum':lo,'maximum':hi}
        tools = []
        if self.skills:
            tools.append(t('perform_skill','执行当前实机已安装的指定模型动作；有限动作等待实际模型开始并退出后返回completed，再调用下一步或拍照。仅限枚举中存在的技能。',
                           {'skill':{'type':'string','enum':list(self.skills)}},['skill']))
        if self.expressions:
            meanings = '；'.join(name+'='+row['label']+'（'+row['meaning']+'）' for name,row in self.expressions.items())
            tools.append(t('express_emotion',
                '播放指定官方表情。普通交流中主动用它表达肯定、听懂、否认或情绪，无需等主人明确要求做动作；点头同意、摇头否认优先用它。保持原生头部、嘴巴和身体曲线，默认播放与手柄相同的官方表情音效；静音时仅做动作。'
                '需要主人手动 HOME 后进入保持，AI 不自动上力。等待原生播放完成再返回；伤心欲绝会坐下并保持坐姿。'+meanings,
                {'emotion':{'type':'string','enum':list(self.expressions)}},['emotion']))
        if 'sit_toggle' in self.skills:
            tools += [t('sit_down','坐下，仅当当前站着时调用。'),
                      t('stand_up','先清除抬头、转头等手动头部偏移，再从坐姿站起；等实际起身模型结束返回completed。已经站着时只恢复头部中立，不切换坐姿。')]
        tools.append(t('stay_silent',STAY_SILENT_DESCRIPTION))
        tools += [
            t('walk_short','使用现有Walk模型短距离行走/侧移/转向，最多3秒，结束后速度归零。原地转向时vx和vy都设0，只设置vyaw。',
              {'vx':num('前后速度m/s',-.3,.3),'vy':num('左右速度m/s',-.2,.2),'vyaw':num('转向角速度rad/s；正数左转、负数右转；满杆为1.5rad/s',-1.5,1.5),'seconds':num('持续秒数',.1,3)},['vx','vy','vyaw','seconds']),
            t('stop_moving','立刻停止行走。'),
            t('body_pose','短暂调整身体高度、俯仰或侧倾，自动结束。',
              {'z':num('身体升降米',-.025,.01),'pitch':num('身体俯仰',-.25,.25),'roll':num('身体侧倾',-.25,.25),'seconds':num('持续秒数',.1,1.5)},['z','pitch','roll','seconds']),
            t('mouth_pose','只控制嘴巴开度，不会发声。',{'open':num('0到1嘴巴开度',0,1)},['open']),
        ]
        ranges = self.head_ranges()
        if ranges:
            directions = {'neck_pitch':'脖子俯仰', 'head_pitch':'头部俯仰：负数抬头、正数低头',
                          'head_yaw':'转头：正数向鸭子自身左侧、负数向右侧', 'head_roll':'左右歪头'}
            tools.append(t('head_pose',
                '头和脖子目标角度，弧度；未给的轴归零。范围来自当前模型各轴数据与中控保存的头部幅度的交集。'
                '根据用户要求选择幅度，允许明显转头/抬头，不要编造只能转一点的限制。目标由原生策略执行，不代表已测得实际到位。',
                {axis:num(directions[axis]+'（rad）',span[0],span[1]) for axis,span in ranges.items()}))
            tools.append(t('head_expression','简短头部手势；同意和否认优先使用官方表情工具。',
                {'gesture':{'type':'string','enum':['nod','shake','tilt_left','tilt_right','neutral']}},['gesture']))
        return tools

    def _check(self, args, allowed, required=()):
        if not isinstance(args, dict) or (set(args)-set(allowed)) or not set(required).issubset(args):
            raise ActionDenied('非法动作参数')

    def _send(self, method, params):
        self.ensure_input_current()
        self.log('ipc_request', method=method, params=params)
        result = self.rpc(method, params)
        if not isinstance(result, dict) or result.get('accepted') is not True:
            raise ActionDenied((result or {}).get('reason','robotd 无有效接收回执') if isinstance(result,dict) else 'robotd无回执')
        self.log('ipc_accepted', method=method, result=result, message='已接收并排队，不等于运动完成')
        return {**result,'accepted':True,'status':result.get('status','accepted_not_motion_completed')}

    def _ready(self,monitor=False):
        self.ensure_input_current()
        if self.cancelled():raise ActionDenied('AI 会话已停止')
        s = self.monitor() if monitor else self.state()
        if not s.get('connected'):
            raise ActionDenied('机器人未连接',state=s)
        if not s.get('fresh') or not s.get('motion_ready'):
            reasons=s.get('motion_blockers') or ['实时反馈或运动就绪条件未满足']
            raise ActionDenied('AI 动作未就绪：'+'；'.join(reasons),state=s)
        if s.get('webpad_active'):
            raise ActionDenied('网页手柄正在占用，AI 动作暂停',state=s)
        if s.get('maintenance'):
            raise ActionDenied('正在维护或连接已暂停，AI 动作暂停',state=s)
        return s

    @staticmethod
    def _model_sample(state):
        stamp=state.get('state_t_ns');policy=state.get('policy')
        if (state.get('state_fresh') is not True or type(stamp) is not int or stamp<=0
                or not isinstance(policy,str) or not policy):
            raise ActionDenied('缺少新鲜的模型执行反馈，不能确认动作结束',state=state)
        return stamp,policy

    def _run_model(self,skill,expected=None):
        # robot.state already reports the network that drove each tick. Observe
        # entry AND exit; an accepted intent or an elapsed duration is not done.
        stamp,policy=self._model_sample(self._ready(monitor=True))
        if policy not in ('walk','stand','sit'):
            raise ActionDenied('当前模型动作尚未结束：'+policy)
        receipt=self._send('robot.do',{'skill':skill})
        expected=expected or skill;started=None;begin=self.clock()
        deadline=begin+self.model_timeouts.get(skill,18)
        while self.clock()<deadline:
            state=self._ready(monitor=True);current,label=self._model_sample(state)
            if current<stamp:raise ActionDenied('机器人实时反馈时钟已重置，不能确认原动作结束')
            if current>stamp:
                stamp=current
                if label==expected or label.startswith(expected+':'):
                    if started is None:
                        started=current;self.log('model_progress',skill=skill,phase='running',policy=label,
                                                 message='模型动作正在执行：'+skill)
                elif started is not None:
                    if label not in ('walk','stand','sit'):
                        raise ActionDenied('模型动作被其他模型取代：'+label)
                    result={**receipt,'accepted':True,'status':'completed','skill':skill,
                            'model_started_t_ns':started,'model_completed_t_ns':current,
                            'completion_source':'robot.state.policy'}
                    self.log('model_progress',skill=skill,phase='completed',policy=label,
                             message='已确认模型动作结束：'+skill)
                    return result
            if started is None and self.clock()-begin>=2:
                raise ActionDenied('未观测到模型动作开始，不能把接收回执当作执行完成')
            self.sleep(.05)
        raise ActionDenied('等待模型动作结束超时；未确认完成，不继续拍照')

    def _enter_sit(self):
        # Sit is a persistent mode, not a finite model with an exit receipt.
        # Hold the input pause until a newer state confirms the mode switch;
        # this does not claim that the body has physically reached its target.
        stamp,policy=self._model_sample(self._ready(monitor=True))
        if policy not in ('walk','stand','sit'):
            raise ActionDenied('当前模型动作尚未结束：'+policy)
        receipt=self._send('robot.do',{'skill':'sit_toggle'})
        deadline=self.clock()+2
        while self.clock()<deadline:
            state=self._ready(monitor=True);current,label=self._model_sample(state)
            if current<stamp:raise ActionDenied('机器人实时反馈时钟已重置，不能确认坐姿切换')
            if current>stamp and label=='sit' and state.get('sitting') is True:
                return {**receipt,'accepted':True,'status':'sit_mode_entered_not_completion',
                        'mode_entered_t_ns':current,'mode_source':'robot.state.policy'}
            self.sleep(.05)
        raise ActionDenied('未确认进入坐姿模式；没有坐下物理完成回执')

    def wait_capture_model(self):
        deadline=self.clock()+18;acquired=False;reported=None
        try:
            while self.clock()<deadline:
                if self.cancelled():raise ActionDenied('AI 会话已停止')
                if not acquired:
                    acquired=self.lock.acquire(blocking=False)
                    if not acquired:self.sleep(.05);continue
                state=self.monitor()
                if not state.get('connected') or not state.get('fresh'):
                    raise ActionDenied('实时反馈未就绪，未拍照')
                stamp,policy=self._model_sample(state)
                if policy in ('walk','stand','sit','held'):
                    return {'accepted':True,'status':'model_idle','model_completed_t_ns':stamp,
                            'policy':policy,'source':'cached_robot.state.policy'}
                if policy!=reported:
                    reported=policy;self.log('model_progress',phase='waiting_capture',policy=policy,
                                             message='等待当前模型动作结束后拍照：'+policy)
                self.sleep(.05)
            raise ActionDenied('模型动作尚未结束，本次未拍照')
        finally:
            if acquired:self.lock.release()

    def _head(self, **kwargs):
        return self._send('robot.head',{k:float(kwargs.get(k,0)) for k in self.HEAD_KEYS})

    def head_ranges(self):
        if not self.head_reference:return {}
        amplitude=self.state().get('head_rad',2.5)
        if type(amplitude) not in (int,float) or amplitude not in (.5,1.,2.5):return {}
        return {axis:(max(low,-amplitude), min(high,amplitude))
                for axis,(low,high) in self.head_reference.items()}

    def _express(self, name):
        row=self.expressions.get(name)
        if not row:raise ActionDenied('未读取到这个官方表情，请升级配套固件后刷新清单')
        silent=row['silent'] or self.state().get('audio_muted') is True
        skill=row.get('silent_skill',row['skill']) if silent else row['skill']
        receipt=self._send('robot.do',{'skill':skill})
        request_id=receipt.get('request_id')
        if type(request_id) is not int:raise ActionDenied('表情请求没有原生编号，不能确认播放状态')
        deadline=self.clock()+row['seconds']+2
        try:
            while self.clock()<deadline:
                self._ready()
                status=self.rpc('robot.do',{'skill':'emotion_status'})
                if status.get('request_id')!=request_id:
                    raise ActionDenied('表情已被其他请求取代')
                if not silent and self.state().get('audio_muted') is True:
                    raise ActionDenied('已静音，当前有声表情已取消')
                phase=status.get('phase')
                if phase=='completed':
                    return {'accepted':True,'status':'completed','emotion':name,'label':row['label'],
                            'request_id':request_id,'seconds':row['seconds'],'silent':silent}
                if phase=='cancelled':raise ActionDenied('原生表情已取消，请检查手柄、姿态或实时反馈')
                if phase not in ('pending','playing'):raise ActionDenied('原生表情状态无效')
                self.sleep(.2)
            raise ActionDenied('未收到表情完成回执')
        except Exception:
            # Stop only this generation. Do not cancel a new manual R3 selection.
            try:
                current=self.rpc('robot.do',{'skill':'emotion_status'})
                if current.get('request_id')==request_id and current.get('phase') in ('pending','playing'):
                    self.rpc('robot.do',{'skill':'emotion_cancel_'+str(request_id)})
            except Exception:pass
            raise

    def _gesture(self, name):
        if name in ('nod','shake') and self.expressions:
            return self._express('yes' if name=='nod' else 'no')
        ranges=self.head_ranges()
        if not ranges:raise ActionDenied('尚未读取头部各轴范围，请更新配套固件后刷新清单')
        def portion(axis,positive,ratio=.65):
            return ranges[axis][1 if positive else 0]*ratio
        poses = {
            'nod':[{'head_pitch':portion('head_pitch',True,.35)}, {'head_pitch':portion('head_pitch',False,.35)},{}],
            'shake':[{'head_yaw':portion('head_yaw',True,.35)}, {'head_yaw':portion('head_yaw',False,.35)},{}],
            'tilt_left':[{'head_roll':portion('head_roll',False)}],
            'tilt_right':[{'head_roll':portion('head_roll',True)}],
            'neutral':[{}],
        }
        if name not in poses:raise ActionDenied('不支持的头部表达')
        for pose in poses[name]:
            self._ready()
            self._head(**pose)
            if len(poses[name])>1:self.sleep(.25)
        return {'accepted':True,'status':'head_intents_sent'}

    def _walk(self,args):
        speed={k:numeric(args[k],lo,hi,k) for k,lo,hi in [('vx',-.3,.3),('vy',-.2,.2),('vyaw',-1.5,1.5)]}
        duration=numeric(args['seconds'],.1,3,'seconds')
        until=self.clock()+duration
        try:
            while self.clock()<until:
                self._ready()
                self._send('robot.move',speed)
                self.sleep(min(.075,max(0,until-self.clock())))
        except Exception:
            try:self._send('robot.move',{'vx':0,'vy':0,'vyaw':0})
            except Exception:pass
            raise
        else:self._send('robot.move',{'vx':0,'vy':0,'vyaw':0})
        return {'accepted':True,'status':'stop_intent_sent','seconds':duration}

    @contextmanager
    def _exclusive(self,name=None):
        if not self.lock.acquire(blocking=False):raise ActionDenied('已有 AI 动作执行中，本次拒绝，不排队')
        self.active_action=name
        try:yield
        finally:
            self.active_action=None
            self.lock.release()

    def follow_speech_mouth(self,opening):
        """Local HAT playback drives only the existing normalized mouth input.

        Do not take the whole-body action lock: speech can accompany Walk.
        Native expressions retain ownership of their own mouth curves. This is
        not a model tool and never authorizes HOME, torque or another movement.
        """
        opening=numeric(opening,0,1,'open')
        if self.active_action in ('express_emotion','head_expression'):return False
        self._ready(monitor=True)
        # Match the native expression player: 0..1 maps -5° closed to +30° open.
        # Reapplying the manual-pad percentage here would shrink this twice.
        result=self.rpc('robot.mouth',{'open':opening})
        return isinstance(result,dict) and result.get('accepted') is True

    def execute(self,name,args=None):
        args={} if args is None else args
        self.log('tool_call', name=name, arguments=args)
        try:
            with self._exclusive(name):
                if name=='stay_silent':
                    self._check(args,())
                    result={'accepted':True,'status':'silence_no_action'}
                else:
                    self._ready()
                    if name=='express_emotion':
                        self._check(args,('emotion',),('emotion',))
                        result=self._express(args['emotion'])
                    elif name=='perform_skill':
                        self._check(args,('skill',),('skill',))
                        if args['skill'] not in self.skills:raise ActionDenied('未安装这个动作')
                        if args['skill']=='sit_toggle':
                            sitting=self.state().get('sitting')
                            if type(sitting) is not bool:raise ActionDenied('未确认当前坐姿，拒绝盲目切换起坐')
                            result=self._run_model('sit_toggle',expected='rise') if sitting else self._enter_sit()
                        else:result=self._run_model(args['skill'])
                    elif name in ('sit_down','stand_up'):
                        self._check(args,())
                        if 'sit_toggle' not in self.skills:raise ActionDenied('坐下/起身模型未安装')
                        sitting=self.state().get('sitting')
                        if type(sitting) is not bool:raise ActionDenied('未确认当前坐姿，拒绝盲目切换起坐')
                        target=name=='sit_down'
                        # robot.head is persistent intent. A seated look-up must
                        # not leak into rise, walking or the next model skill.
                        # Clear all four axes before rise via the same robotd IPC.
                        if not target:self._head()
                        result=({'accepted':True,'status':'already_target'} if sitting==target else
                                self._enter_sit() if target else
                                self._run_model('sit_toggle',expected='rise'))
                        if not target:result={**result,'head_neutral_intent_sent':True}
                    elif name=='walk_short':
                        self._check(args,('vx','vy','vyaw','seconds'),('vx','vy','vyaw','seconds'))
                        result=self._walk(args)
                    elif name=='stop_moving':
                        self._check(args,())
                        result=self._send('robot.move',{'vx':0,'vy':0,'vyaw':0})
                    elif name=='head_expression':
                        self._check(args,('gesture',),('gesture',))
                        result=self._gesture(args['gesture'])
                    elif name=='head_pose':
                        self._check(args,self.HEAD_KEYS)
                        ranges=self.head_ranges()
                        if not ranges:raise ActionDenied('尚未读取头部各轴范围，请更新配套固件后刷新清单')
                        result=self._head(**{k:numeric(args.get(k,0),*ranges[k],k) for k in self.HEAD_KEYS})
                    elif name=='body_pose':
                        self._check(args,('z','pitch','roll','seconds'),('z','pitch','roll','seconds'))
                        params={k:numeric(args[k],lo,hi,k) for k,lo,hi in [('z',-.025,.01),('pitch',-.25,.25),('roll',-.25,.25)]}
                        seconds=numeric(args['seconds'],.1,1.5,'seconds')
                        try:
                            self._send('robot.pose',{**params,'active':True})
                            self.sleep(seconds)
                        except Exception:
                            try:self._send('robot.pose',{'active':False})
                            except Exception:pass
                            raise
                        else:self._send('robot.pose',{'active':False})
                        result={'accepted':True,'status':'pose_end_intent_sent'}
                    elif name=='mouth_pose':
                        self._check(args,('open',),('open',))
                        result=self._send('robot.mouth',{'open':numeric(args['open'],0,1,'open')})
                    else:raise ActionDenied('无此工具；只开放动作权限')
            self.log('tool_result',name=name,result=result)
            return result
        except (KeyError,ValueError,TypeError) as exc:
            fields={'name':name,'reason':str(exc)}
            if isinstance(exc,ActionDenied) and exc.state is not None:fields['state']=exc.state
            self.log('tool_denied',**fields)
            if isinstance(exc,ActionDenied):raise
            raise ActionDenied(str(exc)) from None

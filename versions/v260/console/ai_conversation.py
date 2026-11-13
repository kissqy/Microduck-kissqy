"""Conversation records derived from provider events; photos stay in a bounded RAM cache."""
from collections import OrderedDict
import time


class Conversation:
    def __init__(self,limit=200):
        self.limit=limit
        self.messages=OrderedDict()
        self.sequence=0
        self.session=0
        self.user_key=None
        self.assistant_key=None
        self.phase='stopped'
        self.note='尚未启动豆包对话'
        self.phase_at_ms=round(time.time()*1000)
        self.revision=0

    def begin(self):
        self.session+=1
        self.user_key=self.assistant_key=None

    def _put(self,key,role,event,**fields):
        if key not in self.messages:
            self.sequence+=1
            self.messages[key]={'id':self.sequence,'role':role,'at':event['at']}
        message=self.messages[key]
        message.update(fields)
        while len(self.messages)>self.limit:self.messages.popitem(last=False)
        return dict(message)

    def record(self,event):
        kind=event['kind'];message=None;phase=None;note=None
        if kind=='provider_connecting':
            phase,note='connecting','正在连接豆包…'
        elif kind=='provider_session' and event.get('event')=='session.created':
            phase,note='listening','豆包已连接，可以对着 HAT 说话'
        elif kind=='transcript':
            source=event.get('item_id')
            if source:key=('user',self.session,str(source))
            else:
                key=self.user_key
                if key is None or self.messages.get(key,{}).get('final'):
                    key=('user',self.session,self.sequence+1)
            self.user_key=key
            message=self._put(key,'user',event,text=str(event.get('text','')),
                              final=event.get('final') is True,type='text')
            phase,note=('waiting','已识别，等待豆包回复…') if event.get('final') else ('transcribing','正在识别，由豆包判断说话结束')
        elif kind=='input_turn_commit':
            phase,note='committing','本句已提交，等待豆包确认并回复…'
        elif kind=='input_turn_committed':
            phase,note='waiting','豆包已确认本句输入，等待最终识别或回复…'
        elif kind=='input_turn_wait':
            phase='transcribing' if event.get('stage')=='endpoint' else 'delayed'
            note=str(event.get('message','豆包回复尚未返回'))
        elif kind=='assistant_text':
            source=event.get('message_id') or event.get('item_id') or event.get('response_id')
            key=('assistant',self.session,str(source)) if source else self.assistant_key
            if key is None or not source and self.messages.get(key,{}).get('final'):
                key=('assistant',self.session,self.sequence+1)
            self.assistant_key=key
            message=self._put(key,'assistant',event,text=str(event.get('text','')),
                final=event.get('final') is True,blocked=event.get('blocked') is True,
                audio_id=event.get('audio_id'),type='text')
            phase,note=('ready','豆包已返回文字') if event.get('final') else ('replying','豆包正在回复…')
        elif kind=='tool_call':
            phase,note=('vision','豆包正在拍照识图…') if event.get('name')=='inspect_scene' else ('acting','豆包正在调用动作：'+str(event.get('name','')))
        elif kind=='vision_preview_error':
            key=('vision',self.session,event.get('capture_id'))
            if key not in self.messages:return None
            message=self._put(key,'system',event,image_error=event.get('message','照片未收到'))
        elif kind=='vision_preview':
            key=('vision',self.session,event.get('capture_id'))
            if key not in self.messages:return None
            message=self._put(key,'system',event,image_available=True,
                width=event.get('width'),height=event.get('height'))
        elif kind=='vision_state':
            phase,note='vision',str(event.get('message','正在拍照识图…'))
            if event.get('phase') in ('waiting_motion','capturing'):
                parent=self.messages.get(self.user_key,{}) if event.get('source')!='button' else {}
                key=('vision',self.session,event.get('request_id'))
                parent_id=self.messages[key].get('parent_id') if key in self.messages else parent.get('id')
                message=self._put(('vision',self.session,event.get('request_id')),
                    'system',event,type='vision',text='等待模型动作结束…' if event.get('phase')=='waiting_motion' else '正在拍照识图…',final=False,
                    question=event.get('question',''),capture_id=event.get('request_id'),
                    parent_id=parent_id)
            if event.get('phase')=='error':
                phase='ready'
                key=('vision',self.session,event.get('request_id')) if event.get('request_id') else ('vision_error',self.session,event['id'])
                message=self._put(key,
                    'system',event,type='vision',text=note,final=True)
        elif kind=='vision_result':
            key=('vision',self.session,event.get('capture_id'))
            message=self._put(key,'system',event,type='vision',text=str(event.get('observation','')),
                question=event.get('question',''),capture_id=event.get('capture_id'),
                distance=event.get('distance'),final=True)
            phase,note='ready','识图结果已返回，语音提问可听回答'
        elif kind=='tool_feedback':
            visual=event.get('name')=='inspect_scene'
            result=event.get('result') or {}
            if visual:
                key=('vision',self.session,result.get('capture_id')) if result.get('accepted') else ('tool',self.session,event.get('call_id'))
                message=self._put(key,'system',event,type='vision',name='inspect_scene',result=result,
                    question=(event.get('arguments') or {}).get('question',''),
                    capture_id=result.get('capture_id'),distance=result.get('distance'),
                    text=result.get('observation') if result.get('accepted') else '未识别：'+str(result.get('reason','未获得有效回执')),final=True)
                phase,note='waiting','识图结果已回传，等待豆包语音回答…'
            else:
                key=('tool',self.session,event.get('call_id') or self.sequence+1)
                message=self._put(key,'assistant',event,type='action',name=event.get('name'),
                    arguments=event.get('arguments') or {},result=result,final=True)
                phase,note='ready','豆包已返回动作结果'
        elif kind=='model_turn_finished':
            phase,note='ready','本轮已结束，可以继续说话'
        elif kind=='provider_stop':
            phase,note='stopped','会话已停止'
        elif kind in ('provider_error','mic_error','speaker_error','asr_error'):
            phase,note='error',str(event.get('reason','对话发生错误'))
            message=self._put(('error',event['id']),'system',event,type='text',text=note,final=True)
        if phase is None and message is None:return None
        if phase is not None:
            if phase!=self.phase:self.phase_at_ms=round(time.time()*1000)
            self.phase,self.note=phase,note
        self.revision=event['id']
        return {'revision':self.revision,'phase':self.phase,'note':self.note,
                'phase_at_ms':self.phase_at_ms,'messages':[message] if message else [],
                'oldest_id':next(iter(self.messages.values()))['id'] if self.messages else 0}

    def snapshot(self):
        return {'revision':self.revision,'phase':self.phase,'note':self.note,
                'phase_at_ms':self.phase_at_ms,'messages':[dict(x) for x in self.messages.values()]}

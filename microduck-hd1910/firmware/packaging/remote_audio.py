"""Native robotd sound intents; no audio player, PCM stream or timed mouth motion."""
import json,re,subprocess,tomllib,shlex
from pathlib import Path
import voice_preferences
CONFIG=Path('/etc/robot/feetech-ft5/robotd.toml')
SETUP=Path('/opt/robot/feetech-ft5-r5/voice-device.json')
NAMES={'chirp':'短叫','wheee':'持续长叫','greet':'打招呼','inquire':'疑问','coo':'咕咕','alarm':'警戒','peck':'啄食声'}
CONTROL=voice_preferences.CONTROL
validate_volume=voice_preferences.validate
volume_raw=voice_preferences.raw
class NativeAudio:
    def __init__(self,rpc,emit=lambda event:None,config=CONFIG,setup=SETUP,runner=subprocess.run,initialize=True):
        self.setup=setup
        self.rpc,self.emit,self.runner=rpc,emit,runner;self.ident=0;self.volume=None;self.card=None
        source='官方 robotd 原生声音通道'
        try:
            settings=tomllib.loads(config.read_text()).get('audio',{});bank=Path(settings.get('bank','/var/lib/robot/sounds'))
            marker=(bank/'.seed').read_text().strip();source+=' · 种子 '+marker.split(':')[0]
        except (OSError,ValueError):source+=' · 音库尚未确认，请更新 R17 声音包'
        try:
            data=json.loads(setup.read_text());self.card=data['card']
            if data.get('seed_origin'):source+=' · '+str(data['seed_origin'])
            if not isinstance(self.card,str) or not re.fullmatch(r'[A-Za-z0-9_-]+',self.card):raise ValueError('声卡配置无效')
        except (OSError,ValueError,KeyError):self.card=None
        self.job={'id':0,'status':'idle','volume':None,'volume_saved':False,'initializing':True,'source':source,'message':'音量回读中；手柄输入独立可用'}
        if initialize:self.initialize()
    def initialize(self):
        try:
            data=json.loads(self.setup.read_text());self.card=data['card']
            if not isinstance(self.card,str) or not re.fullmatch(r'[A-Za-z0-9_-]+',self.card):raise ValueError('声卡配置尚未就绪')
            result=self._mixer(['amixer','-c',self.card,'cget','name='+CONTROL])
            match=re.search(r': values=(\d+)',result.stdout)
            if result.returncode or not match:raise ValueError('未取得声卡音量回读')
            self.volume=voice_preferences.percent(int(match[1]))
            switch=self._mixer(['amixer','-c',self.card,'cget','name='+voice_preferences.MUTE_CONTROL])
            if switch.returncode:raise ValueError('未取得系统静音状态')
            if re.search(r': values=(?:off|0)(?:,|$)',switch.stdout,re.M):self.volume=0
            message=self.job['source']
        except (OSError,ValueError,KeyError,subprocess.TimeoutExpired) as exc:
            message='音量未确认：'+str(exc)
        self.job.update(volume=self.volume,volume_saved=None,initializing=False,message=message)
        self.emit({'event':'audio','audio':self.status()})
    def _mixer(self, command):
        self.emit({'event':'system_log','source':'音量命令','text':shlex.join(command)})
        try:
            result=self.runner(command,capture_output=True,text=True,errors='replace',timeout=4)
            self.emit({'event':'system_log','source':'音量回读','text':f'退出码 {result.returncode}\n'+result.stdout+getattr(result,'stderr','')})
            return result
        except Exception as exc:
            self.emit({'event':'system_log','source':'音量错误','text':str(exc)})
            raise
    def status(self):return dict(self.job)
    def sound(self,params):
        result=self.rpc('robot.sound',params)
        if result.get('accepted') is True:
            self.ident+=1
            release=params=={'tag':'wheee','hold':False}
            self.job.update(id=self.ident,status='completed',kind=params['tag'],message='官方服务已接收收声指令' if release else '官方服务已接收：'+NAMES[params['tag']]+'（指令回执）')
            # A held trigger sends 10 intents/s. Expose a state, not a second playback claim.
            if not release:self.emit({'event':'audio','audio':self.status()})
        return {**result,'audio':self.status()}
    def stop(self):return self.sound({'tag':'wheee','hold':False})
    def set_volume(self,value):
        value=validate_volume(value)
        # Upgrade may have created this file after the persistent SSH bridge started.
        try:
            setup=json.loads(self.setup.read_text());card=setup['card']
            if not isinstance(card,str) or not re.fullmatch(r'[A-Za-z0-9_-]+',card):raise ValueError('声卡配置无效')
            self.card=card
        except (OSError,ValueError,KeyError) as exc:
            self.card=None
            raise RuntimeError('无法读取声音通道配置：'+str(exc)+'；请查看“安装 / 修复 R17”的输出') from exc
        try:
            result=self._mixer(['amixer','-c',self.card,'cset','name='+CONTROL,str(volume_raw(value))])
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError('音量设置等待声卡回读超时（4 秒）；未确认成功，请查看系统日志') from exc
        if result.returncode:raise RuntimeError('音量设置失败：'+result.stderr.strip()[-200:])
        match=re.search(r': values=(\d+)',result.stdout)
        if not match or int(match[1])!=volume_raw(value):raise RuntimeError('音量实际回读不符')
        self.volume=value;self.job.update(volume=value,volume_saved=False)
        try:
            switch=self._mixer(['amixer','-c',self.card,'cset','name='+voice_preferences.MUTE_CONTROL,'off,off' if value==0 else 'on,on'])
            if switch.returncode:raise RuntimeError(switch.stderr.strip()[-300:])
            stored=self._mixer(['sudo','-n',setup.get('alsactl','/usr/sbin/alsactl'),'store',self.card])
            if stored.returncode:raise RuntimeError(stored.stderr.strip()[-300:] or 'alsactl store 未成功')
        except (OSError,ValueError,KeyError,RuntimeError,subprocess.TimeoutExpired) as exc:
            self.job['message']='声卡已调整，但音量保存失败：'+str(exc)
            self.emit({'event':'audio','audio':self.status()})
            raise RuntimeError(self.job['message']) from exc
        self.job.update(volume_saved=True,message=f'系统音量 {value}% 已写入声卡并保存到 ALSA，Zero 开机由系统恢复')
        self.emit({'event':'audio','audio':self.status()})
        return {'accepted':True,'volume':value,'volume_saved':True}
    def close(self):pass

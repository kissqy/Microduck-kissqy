#!/usr/bin/env python3
"""Install native sound once and delegate mixer persistence to system ALSA."""
import argparse,hashlib,json,math,os,pwd,re,shutil,subprocess,tomllib
from pathlib import Path
from configure import atomic_write,dumps
import voice_preferences
BASE=Path(__file__).resolve().parent
ROOT=Path('/')
REVISION='r17-system-alsa.1'

def seed():
    try:identifier=Path('/proc/device-tree/serial-number').read_bytes().decode(errors='replace').strip('\0').strip();kind='主板序列号'
    except OSError:identifier=Path('/etc/machine-id').read_text().strip();kind='machine-id'
    return int.from_bytes(hashlib.sha256(identifier.encode()).digest()[:4],'big'),kind

def run(argv):
    return subprocess.run(argv,capture_output=True,text=True,check=True,timeout=5)

def setup(params):
    data=tomllib.loads(params.read_text());audio=data.setdefault('audio',{})
    try:prior=json.loads((BASE/'voice-device.json').read_text())
    except (OSError,ValueError):prior={}
    original=audio.get('device','plughw:aic3104')
    if original=='microduck_voice':original=prior.get('slave','plughw:aic3104')
    match=re.fullmatch(r'(?:plug)?hw:(?:CARD=)?([A-Za-z0-9_-]+)(?:,.*)?',original)
    if not match:raise ValueError('无法确定系统声卡：'+str(original))
    card=match[1];selected,origin=seed();bank=BASE/'voice-bank'
    try:ready=(bank/'.seed').read_text().strip()==f'{selected}:5'
    except OSError:ready=False
    if prior.get('revision')==REVISION and prior.get('slave')==original and ready and audio.get('bank')==str(bank):
        print('沿用现有原生音库与系统 ALSA 音量；不重复初始化。',flush=True);return
    alsactl=shutil.which('alsactl')
    if not alsactl:raise ValueError('系统缺少 alsactl（alsa-utils）')
    operator=os.environ.get('SUDO_USER')
    user=pwd.getpwnam(operator) if operator and operator!='root' else pwd.getpwuid(prior.get('preferences_uid',params.stat().st_uid))
    if user.pw_uid!=0:
        rule=ROOT/'etc/sudoers.d/microduck-alsa-volume'
        atomic_write(rule,f'{user.pw_name} ALL=(root) NOPASSWD: {alsactl} store {card}\n',mode=0o440)
    # The official board script resets PCM at boot. Restore system state after it,
    # before robotd; neither operation runs on a later robotd restart.
    for unit in ('alsa-restore.service','alsa-state.service'):
        atomic_write(ROOT/f'etc/systemd/system/{unit}.d/microduck-audio.conf','[Unit]\nWants=aic3104-init.service\nAfter=aic3104-init.service\nBefore=robotd.service\n')
    run(['systemctl','--no-reload','add-wants','multi-user.target','alsa-restore.service','alsa-state.service'])
    if not ready:
        subprocess.run([str(BASE/'sounds'),'ensure-bank','--dir',str(bank),'--seed',str(selected),'--force'],check=True,timeout=60)
    if prior.get('revision')!=REVISION:
        value=None
        # One-time migration from the previous software attenuation preserves
        # current loudness when returning robotd directly to the native PCM.
        try:
            old=run(['amixer','-c',card,'cget','name=Microduck Voice Playback Volume'])
            match=re.search(r': values=(\d+)',old.stdout)
            if match:
                raw=int(match[1]);value=0 if raw==0 else max(0,min(100,round(100*10**((raw*60/1000-60)/20))))
        except subprocess.CalledProcessError:pass
        if value is None and not (ROOT/'var/lib/alsa/asound.state').exists():value=voice_preferences.DEFAULT_VOLUME
        if value is not None:
            run(['amixer','-c',card,'cset','name='+voice_preferences.CONTROL,str(voice_preferences.raw(value))])
            run(['amixer','-c',card,'cset','name='+voice_preferences.MUTE_CONTROL,'off,off' if value==0 else 'on,on'])
        (ROOT/'var/lib/alsa').mkdir(parents=True,exist_ok=True)
        run([alsactl,'store',card])
    device={'card':card,'slave':original,'control':voice_preferences.CONTROL,'revision':REVISION,'alsactl':alsactl,'seed':selected,'seed_origin':origin,'volume_backend':'system ALSA'}
    audio.update(enabled=True,device=original,bank=str(bank))
    atomic_write(params,dumps(data))
    atomic_write(BASE/'voice-device.json',json.dumps(device,ensure_ascii=False,indent=2)+'\n')
    (BASE/'voice-alsa.conf').unlink(missing_ok=True)
    print('系统 PCM 音量已接入；alsactl 保存，Zero 开机由系统恢复；固件重启不调整音量。',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('params',type=Path);args=parser.parse_args();setup(args.params)

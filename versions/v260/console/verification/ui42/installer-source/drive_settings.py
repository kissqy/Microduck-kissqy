"""Three persisted linear speed choices, using official padd CLI options."""
import json
from pathlib import Path
import sys
import time

PATH = Path('/etc/robot/feetech-ft5/drive-settings.json')
BASE = Path('/opt/robot/feetech-ft5-r5')
REPORT = Path('/run/padd/input-settings.json')
RECORDER = Path('/run/padd/recorder.json')
PROC = Path('/proc')
CHOICES = (.1, .2, .3)
RECORDER_PHASES = frozenset(('idle','recording','saving','playing','error','pending'))

def validate(speed):
    if type(speed) not in (int, float) or speed not in CHOICES:
        raise ValueError('平移速度请选择 0.1、0.2 或 0.3 m/s')
    return float(speed)

def load():
    return validate(json.loads(PATH.read_text())['speed']) if PATH.exists() else .2

def save(speed):
    from configure import atomic_write
    atomic_write(PATH, json.dumps({'speed': validate(speed)})+'\n')

def recorder_status(padd_pid):
    """Display-only metadata; never starts recording or sends a robot request."""
    now = time.monotonic_ns()//1_000_000
    try:
        if padd_pid is None:raise ValueError('等待实体手柄服务启动')
        with RECORDER.open('rb') as stream:raw=stream.read(16*1024+1)
        if len(raw)>16*1024:raise ValueError('录放报告超过上限')
        data=json.loads(raw)
        if not isinstance(data,dict):raise ValueError('录放报告格式无效')
        if type(data.get('pid')) is not int or data['pid']!=padd_pid:
            raise ValueError('录放报告不属于当前实体手柄服务')
        stamp=data.get('t_ms')
        if type(stamp) is not int or not 0<=now-stamp<=3000:
            raise ValueError('录放报告已过期或时钟无效')
        phase=data.get('phase')
        if phase not in RECORDER_PHASES:raise ValueError('录放阶段无效')
        for key in ('elapsed_ms','duration_ms'):
            if type(data.get(key)) is not int or not 0<=data[key]<=2**53-1:
                raise ValueError('录放时长无效')
        if type(data.get('has_last')) is not bool or not isinstance(data.get('reason',''),str):
            raise ValueError('录放状态无效')
        return {'available':True,'checked_ms':now,'pid':padd_pid,'t_ms':stamp,'phase':phase,
                'elapsed_ms':data['elapsed_ms'],'duration_ms':data['duration_ms'],
                'has_last':data['has_last'],'reason':data.get('reason','')[:300]}
    except (OSError,ValueError,KeyError,TypeError) as exc:
        reason=('安装配套更新后支持录放' if isinstance(exc,FileNotFoundError) else
                '录放状态暂不可读取' if isinstance(exc,OSError) else str(exc))
        return {'available':False,'checked_ms':now,'reason':reason[:300]}

def status():
    result = {'supported': True, 'speed': None}
    padd_pid = None
    try:
        result['saved_speed'] = load()
        pid = json.loads(REPORT.read_text())['pid']
        if type(pid) is not int or pid<=0:raise ValueError('等待实体手柄服务启动')
        args = (PROC/str(pid)/'cmdline').read_bytes().decode().rstrip('\0').split('\0')
        if args[0] != str(BASE/'padd'):
            raise ValueError('等待实体手柄服务启动')
        padd_pid = pid
        values = []
        for flag in ('--max-linear', '--max-linear-backward'):
            if args.count(flag) != 1:
                raise ValueError('请升级 V196 配套固件以启用三档速度')
            values.append(validate(float(args[args.index(flag)+1])))
        if values != [result['saved_speed']]*2:
            raise ValueError('保存速度与实体手柄实际参数不一致，请重新选择档位')
        result['speed'] = values[0]
    except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
        result['error'] = str(exc)
    result['recorder'] = recorder_status(padd_pid)
    return result

def apply(speed):
    speed = validate(speed)
    save(speed)
    # Reuse the installer: preserve head/mouth settings and all existing input flags.
    # Only padd restarts; robotd, models and motor enable state are untouched.
    from gamepad import upgrade_client
    upgrade_client()
    until = time.monotonic()+8
    while time.monotonic() < until:
        result = status()
        if result['speed'] == speed:
            return {'accepted': True, 'drive_speed': result,
                    'message': f'平移速度 {speed:.1f} m/s 已保存并确认生效；网页和实体手柄同步，转向速度不变。'}
        time.sleep(.1)
    raise ValueError('速度已保存，但尚未确认生效：'+result.get('error', '手柄服务未就绪'))

if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise ValueError('用法：drive_settings.py 0.1|0.2|0.3')
    # Keep stdout a single machine-readable receipt; installer messages go to stderr.
    import contextlib
    with contextlib.redirect_stdout(sys.stderr):
        receipt = apply(float(sys.argv[1]))
    print(json.dumps(receipt, ensure_ascii=False))

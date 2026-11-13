"""Read-only fixed walking speed and handpad recorder status."""
import json
from pathlib import Path
import time

BASE = Path('/opt/robot/feetech-ft5-r5')
REPORT = Path('/run/padd/input-settings.json')
RECORDER = Path('/run/padd/recorder.json')
PROC = Path('/proc')
LINEAR_SPEED = .3
RECORDER_PHASES = frozenset(('idle','recording','saving','playing','error','pending'))

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
    result = {'supported': True, 'fixed': True, 'speed': None}
    padd_pid = None
    try:
        pid = json.loads(REPORT.read_text())['pid']
        if type(pid) is not int or pid<=0:raise ValueError('等待实体手柄服务启动')
        args = (PROC/str(pid)/'cmdline').read_bytes().decode().rstrip('\0').split('\0')
        if args[0] != str(BASE/'padd'):
            raise ValueError('等待实体手柄服务启动')
        padd_pid = pid
        values = []
        for flag in ('--max-linear', '--max-linear-backward'):
            if args.count(flag) > 1:
                raise ValueError('实体手柄速度参数重复，请安装配套更新')
            values.append(float(args[args.index(flag)+1]) if flag in args else LINEAR_SPEED)
        if values != [LINEAR_SPEED]*2:
            raise ValueError('实体手柄仍在使用旧速度参数，请安装配套更新')
        result['speed'] = values[0]
    except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
        result['error'] = str(exc)
    result['recorder'] = recorder_status(padd_pid)
    return result


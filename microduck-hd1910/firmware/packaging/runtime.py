#!/usr/bin/env python3
"""HAT deployment helpers. Motor operations use the single robotd IPC owner."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import socket
import subprocess
import sys
import tempfile
import time
import tomllib
from management_profile import PROFILE, SLOTS, DEFAULTS

from configure import dumps, atomic_write
from release_identity import BUILD, CONSOLE_VERSION
from advanced_parameters import validate_servo,load as load_servo_test,save as save_servo_test

# Installation and management read the same shipped default; no UI-side scale.
DEFAULT_POLICY = DEFAULTS['policy']
DEFAULT_ACTION_SCALE = DEFAULT_POLICY['action_scale']

BASE = Path('/opt/robot/feetech-ft5-r5')
CONFIG = Path('/etc/robot/feetech-ft5/robotd.toml')
MODEL_DIR = BASE / 'models'
STATE_DIR = Path('/var/lib/robot/feetech-ft5/r5')
DROPINS = Path('/etc/systemd/system/robotd.service.d')
DROPIN_NAME = 'zzzz-r17-0151.conf'
RUNTIME_DROPINS = Path('/run/systemd/system/robotd.service.d')
PROC = Path('/proc')
# Keep the R17 management identifier; report the package version separately.
MANAGEMENT_REVISION = 'R17'
PORT = '/dev/ttyS2'


def run(*args, timeout=20):
    p = subprocess.run(list(map(str, args)), capture_output=True, text=True, errors='replace', timeout=timeout)
    if p.returncode:
        raise RuntimeError((p.stderr or p.stdout or '命令未成功').strip()[-1500:])
    return p.stdout.strip()


def atomic(path, data, mode=0o644):
    atomic_write(Path(path),data,mode=mode)


def config():
    return tomllib.loads(CONFIG.read_text())


def effective():
    return run('systemctl', 'show', 'robotd.service', '-p', 'ExecStart', '--value')


def detect_port():
    command = effective()
    match = re.search(r'--port(?:=|\s+)(/dev/[A-Za-z0-9/_-]+)', command)
    if match:
        port = match[1]
    else:
        # Read old deployment evidence; every new startup uses the fixed HAT port.
        cfg_match = re.search(r'--params(?:=|\s+)(/[^\s;]+)', command)
        path = Path(cfg_match[1]) if cfg_match else CONFIG
        port = tomllib.loads(path.read_text()).get('bus', {}).get('port')
    if not isinstance(port, str) or not port.startswith('/dev/'):
        raise ValueError('无法核对现有服务的串口配置')
    return port


def effective_config_path():
    match = re.search(r'--params(?:=|\s+)(/[^\s;]+)', effective())
    return Path(match[1]) if match else CONFIG


def configure_hat_port():
    cfg = config()
    if cfg.get('bus',{}).get('port')==PORT:return
    cfg.setdefault('bus', {})['port'] = PORT
    atomic(CONFIG, dumps(cfg))


def retire_legacy_dropins():
    """Consolidate obsolete startup commands when replacing the service."""
    retired = []
    for path in [*DROPINS.glob('*.conf'), *RUNTIME_DROPINS.glob('*.conf')]:
        if path == DROPINS / DROPIN_NAME: continue
        text = path.read_text()
        logical = re.sub(r'\\\n[ \t]*', ' ', text)
        legacy = re.search(r'^\s*ExecStart=\s*' + re.escape(str(BASE.parent)) + r'/feetech-ft5-r[2-5]/robotd(?:-[\w-]+)?(?:\s|$)', logical, re.M)
        foreign = re.search(r'^\s*Exec(?:Start(?:Pre|Post)?|Stop(?:Post)?|Condition)=.*?/opt/microduck-0151(?:/|\s|$)', logical, re.M)
        if legacy or foreign:
            backup = STATE_DIR / 'retired-startup' / (hashlib.sha256(str(path).encode()).hexdigest()[:12]+'-'+path.name+'.bak')
            if not backup.exists(): atomic(backup, text, mode=0o600)
            # Keep operator environment, identities and resource settings; retire
            # only the obsolete startup commands. Only the obsolete launch lines are retired.
            kept = []
            continuation = False
            for line in text.splitlines():
                obsolete_profile_settings = line.strip() in {
                    'TimeoutStartSec=20s', f'ReadWritePaths=/run {CONFIG.parent}', 'PrivateDevices=no'}
                remove = continuation or obsolete_profile_settings or bool(re.match(r'^\s*Exec(?:Start(?:Pre|Post)?|Stop(?:Post)?|Condition)=', line)) or bool(re.match(r'^\s*DeviceAllow=/dev/(?:tty|serial)', line))
                continuation = remove and line.rstrip().endswith('\\')
                if not remove and line.startswith('Environment='):
                    values=shlex.split(line.partition('=')[2]);remaining=[v for v in values if not v.startswith(('ORT_DYLIB_PATH=','ALSA_CONFIG_PATH='))]
                    if values!=remaining:
                        if not remaining:continue
                        line='Environment='+shlex.join(remaining)
                if not remove and not line.lstrip().startswith(('#',';')): kept.append(line)
            if any('=' in line and not line.lstrip().startswith(('#',';')) for line in kept):
                atomic(path, '# Startup commands consolidated by Microduck HAT service.\n'+'\n'.join(kept)+'\n')
            else:
                path.unlink()
            retired.append(path.name)
    return retired


def verify_startup(mode):
    """Check merged systemd commands, including hooks appended after our drop-in."""
    properties = ('ExecStart', 'ExecStartPre', 'ExecStartPost', 'ExecStopPost', 'ExecStop', 'ExecCondition')
    merged = {key: run('systemctl', 'show', 'robotd.service', '-p', key, '--value') for key in properties}
    start = merged['ExecStart']
    if (f'path={BASE}/robotd ;' not in start or f'--params {CONFIG}' not in start
            or f'--port {PORT}' not in start or '--uart-setup' not in start
            or ('--commissioning' in start) != (mode == 'commissioning')):
        raise ValueError('systemd 实际启动命令不匹配本版 R17，未启动服务：'+start)
    for key in properties:
        if '/opt/microduck-0151' in merged[key]:
            raise ValueError('其他安装目录仍在接管 '+key+'，未启动服务：'+merged[key])
    if (f'{BASE}/uart-service.py prepare' not in merged['ExecStartPre']
            or f'{BASE}/uart-service.py apply' not in merged['ExecStartPost']):
        raise ValueError('UART 启动钩子未生效，未启动服务')
    return {'startup_verified': True, 'build': BUILD, 'mode': mode}


def verify_ready(mode):
    deadline=time.monotonic()+12
    last='等待 UART 之后的总线反馈'
    while time.monotonic()<deadline:
        try:
            bus=rpc('robot.busStatus',timeout=2)
            if bus.get('build')!=BUILD or bus.get('mode')!=mode:
                raise ValueError('实际服务版本或模式不匹配：'+json.dumps(bus,ensure_ascii=False))
            if bus.get('phase')=='configuration_error':raise ValueError(bus.get('error') or '总线配置失败')
            ready=(bus.get('phase')=='ready' and bus.get('torque_state')=='off') if mode=='commissioning' else (
                bus.get('phase')=='control' and bus.get('fresh_sample') is True
                and bus.get('native',{}).get('torque_state_confirmed') is False
                and bus.get('policy_enabled') is False and bus.get('homed') is False)
            if ready:return {'service_ready':True,'build':BUILD,'mode':mode,'torque':'off'}
            last=bus.get('error') or bus.get('phase') or last
        except (OSError,RuntimeError) as exc:last=str(exc)
        time.sleep(.05)
    raise ValueError('UART 配置已结束，但总线尚未就绪：'+last)

def verify_calibration():
    """Check the file robotd actually loaded, independently of live servo samples."""
    path=CONFIG.with_name('hd1910-calibration.toml')
    if config().get('bus',{}).get('feetech_calibration')!=str(path):
        raise ValueError('服务参数没有指向本机统一标定路径')
    expected=tomllib.loads(path.read_text())
    report=rpc('robot.busCommand',{'action':'calibration-status'},timeout=3)
    actual=report.get('calibration',{})
    if report.get('calibration_path')!=str(path):raise ValueError('运行服务读取了其他标定文件：'+str(report.get('calibration_path')))
    def same(a,b):
        if type(a) in (int,float) and type(b) in (int,float):return abs(a-b)<1e-8
        return a==b
    for field in ('motion_enabled','imu_mount_verified','units_verified','current_ma_per_count'):
        if not same(actual.get(field),expected.get(field,0 if field=='current_ma_per_count' else False)):raise ValueError('标定运行回读不一致：'+field)
    if len(actual.get('imu_mount_quat',[]))!=4 or any(not same(a,b) for a,b in zip(actual['imu_mount_quat'],expected['imu_mount_quat'])):
        raise ValueError('IMU 安装四元数未按保存文件加载')
    if len(actual.get('joints',[]))!=15:raise ValueError('运行服务未加载 15 个关节标定')
    for row,loaded in zip(expected['joints'],actual['joints']):
        for key in ('name','id','zero_raw','direction','calibrated','min_rad','max_rad'):
            if not same(loaded.get(key),row.get(key)):raise ValueError('关节标定运行回读不一致：'+row['name']+' / '+key)
    count=sum(r.get('calibrated') is True for r in actual['joints'])
    print(f'标定保存与运行回读一致：{path}；已保存 {count}/15；ID 33 零位 {actual["joints"][8]["zero_raw"]}；IMU 已确认 {actual["imu_mount_verified"]}',flush=True)
    return {'calibration_verified':True,'calibration_path':str(path),'saved_calibrated_count':count,'imu_mount_quat':actual['imu_mount_quat']}


def unit(mode):
    if mode not in ('commissioning', 'motion'): raise ValueError('服务模式无效')
    extra = ' --commissioning' if mode == 'commissioning' else ''
    return (f'# R17 / official 0.15.1 / self-trained HD1910 exports.\n'
            f'[Unit]\nAfter=alsa-restore.service alsa-state.service\n[Service]\nEnvironment=ORT_DYLIB_PATH={BASE}/onnxruntime/libonnxruntime.so.1.28.0\nUnsetEnvironment=ALSA_CONFIG_PATH\nExecStart=\nExecStart={BASE}/robotd --socket /run/robotd.sock --params {CONFIG} --port {PORT}{extra} --uart-setup\n'
            f'ExecStartPre=\nExecStartPost=\n'
            f'ExecStopPost=\nRestart=no\n'
            f'ExecStopPost=-/usr/bin/logger -t robotd-exit "result=${{SERVICE_RESULT}} code=${{EXIT_CODE}} status=${{EXIT_STATUS}}"\n'
            f'ExecStartPre=+/usr/bin/python3 {BASE}/uart-service.py prepare\n'
            f'ExecStartPost=+/usr/bin/python3 {BASE}/uart-service.py apply --pid $MAINPID --mode {mode}\n'
            f'TimeoutStartSec=20s\nReadWritePaths=/run {CONFIG.parent} {MODEL_DIR} {STATE_DIR}\nPrivateDevices=no\nDeviceAllow={PORT} rw\nDeviceAllow=char-alsa rw\nSupplementaryGroups=audio\n')


def configure_startup(mode):
    """Consolidate old startup commands into one fixed HAT profile."""
    selected = unit(mode)
    MODEL_DIR.mkdir(parents=True,exist_ok=True)
    STATE_DIR.mkdir(parents=True,exist_ok=True,mode=0o700)
    configure_hat_port()
    retired = retire_legacy_dropins()
    atomic(DROPINS / DROPIN_NAME, selected)
    return {'port': PORT, 'mode': mode, 'retired': retired}


def argument(argv, name):
    values = []
    for index, value in enumerate(argv):
        if value == name and index + 1 < len(argv): values.append(argv[index + 1])
        elif value.startswith(name + '='): values.append(value.split('=', 1)[1])
    return values[0] if len(values) == 1 else None


def running_process():
    pid = int(run('systemctl', 'show', 'robotd.service', '-p', 'MainPID', '--value') or '0')
    if pid <= 0: return {'pid': 0, 'running': False, 'error': '机器人服务未运行'}
    try:
        argv = (PROC / str(pid) / 'cmdline').read_bytes().decode().rstrip('\0').split('\0')
        if not argv or not argv[0]: raise ValueError('服务进程已经退出')
        try: executable = str((PROC / str(pid) / 'exe').readlink())
        except PermissionError: executable = None  # Read-only status may run as radxa.
        if str(pid) != run('systemctl', 'show', 'robotd.service', '-p', 'MainPID', '--value'):
            raise ValueError('服务正在切换进程，请刷新')
        return {'pid': pid, 'running': True, 'argv': argv, 'executable': executable,
                'port': argument(argv, '--port'), 'params': argument(argv, '--params'),
                'mode': 'commissioning' if '--commissioning' in argv else 'motion',
                'uart_setup': '--uart-setup' in argv}
    except (OSError, ValueError) as exc:
        return {'pid': pid, 'running': False, 'error': str(exc)}


def verify_running(mode, port):
    if port != PORT: raise ValueError('服务进程必须使用 HAT /dev/ttyS2')
    process = running_process()
    argv = process.get('argv', [])
    if (not process['running'] or process.get('executable') != str(BASE / 'robotd')
            or not argv or argv[0] != str(BASE / 'robotd')
            or process.get('params') != str(CONFIG) or process.get('port') != port
            or process.get('mode') != mode
            or process.get('uart_setup') is not True
            or argument(argv, '--socket') != '/run/robotd.sock'
            or '--fake' in argv or '--read-only' in argv):
        raise ValueError('实际服务进程与所选配置不一致：' + json.dumps(process, ensure_ascii=False))
    print(f'实际进程已核对：PID {process["pid"]}；{port}；{mode}')


def motion_readiness():
    import importlib.util
    try:
        spec = importlib.util.spec_from_file_location('r17_saved_calibration', Path(__file__).with_name('calibration-config.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.validate(tomllib.loads(CONFIG.with_name('hd1910-calibration.toml').read_text()))
        return {'motion_ready': True, 'motion_readiness_message': '本机保存的 15 关节标定与 IMU 已通过检查'}
    except (OSError, ValueError, TypeError) as exc:
        return {'motion_ready': False, 'motion_readiness_message': str(exc)}


def connection_status():
    selected = detect_port()
    process = running_process()
    expected_mode = 'commissioning' if '--commissioning' in effective() else 'motion'
    matches = (selected == PORT and process['running'] and process.get('port') == PORT
               and process.get('mode') == expected_mode
               and process.get('params') == str(CONFIG)
               and process.get('uart_setup') is True)
    return {'management_revision': MANAGEMENT_REVISION, 'profile':'hd1910-selftrained-v1',
            'release':'Microduck-Robotd-FT6-R17', 'console_version': CONSOLE_VERSION, 'management_capabilities': {feature:True for feature in PROFILE['features']}, 'boot_port': PORT,
            'selected_port': selected, **motion_readiness(),
            'actual_port': process.get('port'), 'actual_mode': process.get('mode'),
            'pid': process['pid'], 'running': process['running'], 'process_matches': bool(matches),
            'error': process.get('error'), 'device_present': Path(selected).is_char_device()}


def rpc(method, params=None, timeout=15):
    with socket.socket(socket.AF_UNIX) as s:
        s.settimeout(timeout); s.connect('/run/robotd.sock')
        s.sendall((json.dumps({'jsonrpc':'2.0','id':1,'method':method,'params':params or {}})+'\n').encode())
        with s.makefile('rb') as f: response = json.loads(f.readline(1048576))
    if response.get('error'): raise RuntimeError(str(response['error']))
    result = response['result']
    if isinstance(result, dict) and result.get('accepted') is False:
        raise RuntimeError(result.get('reason', '服务拒绝请求'))
    return result


def torque_off(report):
    if report.get('torque_off_pending'): return False
    if report.get('mode') == 'commissioning': return report.get('torque_state') == 'off'
    return report.get('mode') == 'motion' and report.get('native', {}).get('torque_state_confirmed') is False


def relax_confirmed():
    rpc('robot.relax')
    until = time.monotonic() + 8
    while time.monotonic() < until:
        if torque_off(rpc('robot.busStatus')): return
        time.sleep(.1)
    raise RuntimeError('未确认全部关节扭矩 OFF；操作未继续')


def request_relax():
    """Best-effort stop before reconnecting the HAT service."""
    try:
        rpc('robot.relax', timeout=2)
        return {'requested': True, 'message': '已请求旧服务停止；正在重新连接 HAT'}
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        return {'requested': False, 'message': '旧服务未返回停止确认；将在 HAT 重新初始化',
                'detail': str(exc)[-300:]}


def power(action):
    from power_control import power as submit_power
    return submit_power(action,runner=run)



def validate_scale(value):
    scale=float(value)
    if scale not in tuple(round(n/100,2) for n in range(10,101)):raise ValueError('缩放只能选择 0.10 到 1.00，步长 0.01')
    return scale

def set_action_scale(ident,value,kp,kd,torque_limit):
    scale=validate_scale(value)
    servo=validate_servo(kp,kd,torque_limit)
    if not re.fullmatch('[a-f0-9]{32}',ident):raise ValueError('模型标识无效')
    data=tomllib.loads(CONFIG.read_text())
    policy=data.setdefault('policy',{})
    active={Path(str(policy.get(slot,''))).parent.name for slot in ('walk','sitstand')}
    if ident not in active:raise ValueError('请选择已安装且启用的自训模型')
    policy['action_scale']=scale
    policy.pop('r17_inference_scale',None)
    for key in ('walk_action_scale','hold_action_scale','action_scales'):policy.pop(key,None)
    text=dumps(data)
    atomic_write(CONFIG,text)
    atomic_write(CONFIG.with_name(CONFIG.stem+'.saved'+CONFIG.suffix),text)
    save_servo_test(CONFIG,servo)
    return {'model':ident,'action_scale':scale,'servo_parameters':servo,'sitstand_base_action_scale':1.0,'message':'高级参数已保存：动作缩放及全部 15 个舵机的 P / D / 转矩限制；重启后重新 HOME，上力时写入并回读确认。'}

def model_list():
    from model_packages import catalog
    result=catalog(BASE,CONFIG);policy=tomllib.loads(CONFIG.read_text()).get('policy',{})
    for row in result['models']:
        row['action_scale']=policy.get('action_scale',DEFAULT_ACTION_SCALE) if row.get('slot')=='walk' else 1.0
        if row.get('slot')=='roulade':
            row['action_scale']=next((a.get('params',{}).get('action_scale',policy.get('action_scale',DEFAULT_ACTION_SCALE)) for a in policy.get('skill',[]) if a.get('name')=='roulade'),policy.get('action_scale',DEFAULT_ACTION_SCALE))
    return {**result,'management_actions':['advanced-parameters'],'servo_parameters':load_servo_test(CONFIG),'default_servo_parameters':DEFAULTS['servo'],'action_scale':policy.get('action_scale',DEFAULT_ACTION_SCALE),'default_action_scale':DEFAULT_ACTION_SCALE,'port':detect_port()}

def verify_loaded_models():
    expected={slot:hashlib.sha256(Path(path).read_bytes()).hexdigest() for slot,path in config()['policy'].items()
              if slot in SLOTS and path and path!='none'}
    until=time.monotonic()+8;last='等待控制器加载'
    while time.monotonic()<until:
        try:
            bus=rpc('robot.busStatus',timeout=2)
            actual=bus.get('loaded_models') or {}
            policy=config()['policy']
            settings={key:policy.get(key,default) for key,default in DEFAULT_POLICY.items()}
            params_match=all(bus.get(key)==value for key,value in settings.items())
            if 'roulade' in expected:
                scale=next((a.get('params',{}).get('action_scale',policy.get('action_scale',DEFAULT_ACTION_SCALE)) for a in policy.get('skill',[]) if a.get('name')=='roulade'),policy.get('action_scale',DEFAULT_ACTION_SCALE))
                params_match=params_match and (bus.get('model_action_scales') or {}).get('roulade')==scale
            if params_match and bus.get('build')==BUILD and all((actual.get(slot) or {}).get('sha256')==sha for slot,sha in expected.items()):
                print('已确认控制器实际加载：',json.dumps(actual,ensure_ascii=False),flush=True)
                return {'loaded_models_verified':True,'models':actual,'action_scale':bus['action_scale'],'head_lowpass':bus['head_lowpass'],'legs_lowpass':bus['legs_lowpass']}
            last=json.dumps({'build':bus.get('build'),'loaded_models':actual},ensure_ascii=False)
        except (OSError,ValueError,RuntimeError,KeyError) as exc:last=str(exc)
        time.sleep(.1)
    raise ValueError('安装文件已更新，但未确认运行模型一致：'+last[-1500:])

def model_assignment(ident,slot):
    from model_packages import verify_directory,check_calibration,SLOTS
    if slot not in SLOTS or not re.fullmatch('[a-f0-9]{32}',ident):raise ValueError('动作或模型标识无效')
    info=verify_directory(BASE/'models'/ident)
    if info['slot']!=slot or config()['policy'].get(slot)!=str(BASE/'models'/ident/'policy.onnx'):raise ValueError('模型未绑定到所选动作')
    if tomllib.loads(CONFIG.with_name(CONFIG.stem+'.saved'+CONFIG.suffix).read_text()).get('policy',{}).get(slot)!=config()['policy'][slot]:raise ValueError('动作模型绑定未持久保存')
    bus=rpc('robot.busStatus',timeout=2);mode=bus.get('mode')
    if bus.get('build')!=BUILD or mode not in ('motion','commissioning'):raise ValueError('未取得当前固件模式确认')
    loaded=(bus.get('loaded_models') or {}).get(slot) or {}
    if mode=='motion' and loaded.get('sha256')!=info['sha256']:raise ValueError('所选动作实际模型哈希不匹配')
    return {'model_assignment':{'slot':slot,'id':ident,'sha256':info['sha256'],'saved_verified':True,'running_verified':mode=='motion','mode':mode},'warnings':check_calibration(info),'id':ident,'slot':slot,'name':info['label'],'message':'已绑定 '+info['label']+('，实际模型已确认' if mode=='motion' else '；标定模式仅保存，运动模式加载后确认')+'；请重新 HOME。'}

def main():
    action, *args = sys.argv[1:]
    if action == 'validate-scale': print(validate_scale(*args)); return
    if action == 'port': print(detect_port()); return
    if action == 'config-path': print(effective_config_path()); return
    if action == 'connection': print(json.dumps(connection_status(), ensure_ascii=False)); return
    if action == 'verify-running': verify_running(*args); return
    if action == 'model-assignment': print(json.dumps(model_assignment(*args),ensure_ascii=False)); return
    if action == 'verify-models': print(json.dumps(verify_loaded_models(),ensure_ascii=False)); return
    if action == 'verify-calibration': print(json.dumps(verify_calibration(),ensure_ascii=False)); return
    if action == 'bus-status': result = rpc('robot.busStatus', timeout=2)
    elif action == 'models': result = model_list()
    else:
        if os.geteuid() != 0: raise PermissionError('此操作需要 sudo')
        if action == 'configure-startup': result = configure_startup(*args)
        elif action == 'verify-startup': result = verify_startup(*args)
        elif action == 'verify-ready': result = verify_ready(*args)
        elif action == 'retire-legacy': result = retire_legacy_dropins()
        elif action == 'power': result = power(*args)
        elif action == 'validate-advanced': result={'action_scale':validate_scale(args[0]),'servo_parameters':validate_servo(*args[1:])}
        elif action == 'set-action-scale': result = set_action_scale(*args)
        elif action == 'relax-confirmed': relax_confirmed(); result = {'torque':'off'}
        elif action == 'relax-request': result = request_relax()
        elif action == 'import-model':
            from model_packages import import_package
            result=import_package(args[0],args[1],target_slot=args[2])
        elif action == 'assign-model':
            from model_packages import assign_model
            result=assign_model(*args)
        elif action == 'delete-model':
            from model_packages import delete_model
            result=delete_model(*args)
        else: raise ValueError('不支持的运行管理操作')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    try: main()
    except Exception as exc: print(str(exc), file=sys.stderr); sys.exit(1)

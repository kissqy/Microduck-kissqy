#!/usr/bin/env python3
"""Install the unchanged R7 input bridge without deployment rollback."""
from pathlib import Path
import shutil
import subprocess
import sys
import json,time,stat
import os,tempfile
from pad_settings import load,save,validate,PATH as SETTINGS_PATH

ROOT = Path('/')
FILES = {
    'gamesir-xboxd':'usr/local/sbin/gamesir-xboxd',
    'gamesir-xbox-status':'usr/local/sbin/gamesir-xbox-status',
    'gamesir-xboxd.service':'etc/systemd/system/gamesir-xboxd.service',
    '70-gamesir-xbox-bridge.rules':'etc/udev/rules.d/70-gamesir-xbox-bridge.rules',
}
MODULE = 'etc/modules-load.d/gamesir-xbox.conf'
PAD_DROPIN = 'etc/systemd/system/padd.service.d/zzzz-r17-0151.conf'
BASE = Path('/opt/robot/feetech-ft5-r5')
CONFIG = Path('/etc/robot/feetech-ft5/robotd.toml')
LEGACY = ['etc/systemd/system/gamesir-n2lite-24g.service',
          'etc/udev/rules.d/71-gamesir-n2lite-24g.rules','usr/local/sbin/gamesir-n2lite-24g']
SERVICES = ['gamesir-xboxd.service','gamesir-n2lite-24g.service','padd.service']
ACTIVE_INSTALL_STEP='安装实体手柄配置'

def run(*args,check=True):
    result=subprocess.run(args,check=False,text=True,encoding='utf-8',errors='replace',capture_output=True)
    if check and result.returncode:raise RuntimeError((result.stderr or result.stdout or '命令未成功').strip())
    return result

def log_step(label,status,detail):
    global ACTIVE_INSTALL_STEP
    if status=='开始':ACTIVE_INSTALL_STEP=label
    print(f'[固件安装 / {label}] {status} · {detail}',flush=True)

def replace_owned_file(source,target,mode):
    # Replace the directory entry, not a mask symlink or a live executable inode.
    target.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.'+target.name+'-',dir=target.parent)
    os.close(fd)
    prepared=Path(name)
    try:
        shutil.copy2(source,prepared)
        prepared.chmod(mode)
        os.replace(prepared,target)
    finally:prepared.unlink(missing_ok=True)

def install(bundle, deferred=False):
    # Mapping source and uinput descriptor are exactly R7; binary is precompiled.
    # upgrade_client installs a missing padd unit later in the same upgrade.
    if deferred:log_step('安装 R7 输入桥配置','开始','写入桥接程序、systemd 单元与 uinput 规则')
    if not deferred:
        run('modprobe','uinput')
        for service in SERVICES:run('systemctl','stop',service,check=False)
    legacy=any((ROOT/rel).exists() for rel in LEGACY)
    if legacy:run('systemctl','--no-reload','disable','gamesir-n2lite-24g.service',check=False)
    for rel in LEGACY:(ROOT/rel).unlink(missing_ok=True)
    source=Path(bundle)/'gamepad-r7'
    for name,rel in FILES.items():
        target=ROOT/rel
        replace_owned_file(source/name,target,0o755 if rel.startswith('usr/') else 0o644)
    from configure import atomic_write
    atomic_write(ROOT/'etc/systemd/system/gamesir-xboxd.service.d/zzzz-r17-ready.conf',
                 '[Unit]\nAfter=robotd.service\n[Service]\nType=exec\nExecStart=\n'
                 'ExecStart=/usr/bin/python3 '+str(BASE/'startup_gate.py')+' --timeout 60 --exec /usr/local/sbin/gamesir-xboxd\n'
                 'Environment=PYTHONDONTWRITEBYTECODE=1\nRestartPreventExitStatus=78\n')
    p=ROOT/MODULE;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('uinput\n')
    if not deferred:
        run('systemctl','daemon-reload')
        run('udevadm','control','--reload-rules')
        run('udevadm','trigger','--subsystem-match=input','--action=change')
        run('systemctl','--no-reload','enable','gamesir-xboxd.service')
    # Start is explicit; never change a working input service during model replacement.
    if deferred:log_step('安装 R7 输入桥配置','成功','R7 Xbox 输入桥配置已就绪')
    else:print('R7 标准 Xbox 输入桥已安装；映射源码不变，运行服务为 R17。')

def start():
    run('systemctl','start','gamesir-xboxd.service')
    run('systemctl','restart','padd.service')
    print('GameSir R7 与官方 padd 已启动；保持已配对的 A+HOME 模式，连接初期不要碰摇杆/扳机。')

def upgrade_client(deferred=False):
    # Always install the frozen official unit; old unit/drop-in text may be
    # malformed or UTF-16 and must not be decoded before it can be repaired.
    if deferred:log_step('安装官方 padd 配置','开始','安装官方服务单元与本机手柄幅度参数')
    run('systemd-sysusers',str(BASE/'padd-sysusers.conf'))
    dest=ROOT/'etc/systemd/system/padd.service'
    replace_owned_file(BASE/'padd.service',dest,0o644)
    settings=load()
    if not SETTINGS_PATH.exists():save(**settings)
    dest=ROOT/PAD_DROPIN;dest.parent.mkdir(parents=True,exist_ok=True)
    from configure import atomic_write
    atomic_write(dest,'[Service]\nExecStart=\nExecStart=/usr/bin/python3 '+str(BASE/'startup_gate.py')+' --timeout 60 --exec '+str(BASE/'padd')+' --socket /run/robotd.sock --config '+str(CONFIG)+' --max-head '+format(settings['head_rad'],'g')+' --input-settings '+str(SETTINGS_PATH)+'\nRuntimeDirectory=padd\nEnvironment=PYTHONDONTWRITEBYTECODE=1\nRestartPreventExitStatus=78\n')
    if not deferred:
        run('systemctl','daemon-reload')
        run('systemctl','--no-reload','enable','padd.service')
        run('systemctl','restart','padd.service')
    if deferred:log_step('安装官方 padd 配置','成功','官方 padd 配置已就绪；R7 映射保持')
    else:print('官方 0.15.1 手柄客户端已配套升级；R7 输入映射保持。')

def retire_webpad():
    names=('microduck-webpad.socket','microduck-webpad.service')
    existing=[name for name in names if (ROOT/'etc/systemd/system'/name).exists() or (ROOT/'etc/systemd/system'/name).is_symlink()]
    module=ROOT/'etc/modules-load.d/microduck-webpad.conf'
    if not existing and not module.exists():return
    log_step('清理旧网页虚拟手柄','开始','停用旧服务并删除其单元和模块配置')
    if existing:run('systemctl','--no-reload','disable','--now',*existing)
    for name in ('microduck-webpad.socket','microduck-webpad.service'):
        (ROOT/'etc/systemd/system'/name).unlink(missing_ok=True)
    module.unlink(missing_ok=True)
    log_step('清理旧网页虚拟手柄','成功','旧服务已停用，旧单元与模块配置已删除')

def prepare_all(bundle):
    # The caller stops inputs and reloads systemd once after every unit is ready.
    run('modprobe','uinput')
    rules=ROOT/FILES['70-gamesir-xbox-bridge.rules']
    changed=not rules.exists() or rules.read_bytes()!=(Path(bundle)/'gamepad-r7/70-gamesir-xbox-bridge.rules').read_bytes()
    install(bundle,deferred=True)
    upgrade_client(deferred=True)
    retire_webpad()
    log_step('启用实体手柄开机启动','开始','systemd 启用 GameSir 输入桥与 padd')
    run('systemctl','--no-reload','enable','gamesir-xboxd.service','padd.service')
    log_step('启用实体手柄开机启动','成功','GameSir 输入桥与 padd 已设为开机启动')
    if changed:
        log_step('加载输入设备规则','开始','重载 udev 并应用更新后的输入设备规则')
        run('udevadm','control','--reload-rules')
        run('udevadm','trigger','--subsystem-match=input','--action=change')
        log_step('加载输入设备规则','成功','输入设备规则已应用')

def live_settings_process():
    pid=int(run('systemctl','show','padd.service','-p','MainPID','--value').stdout.strip())
    args=(Path('/proc')/str(pid)/'cmdline').read_bytes().decode().rstrip('\0').split('\0')
    if args[0]!=str(BASE/'padd') or args.count('--input-settings')!=1 or args[args.index('--input-settings')+1]!=str(SETTINGS_PATH):
        raise ValueError('当前手柄服务不支持运行中更新幅度，请先升级配套 R17 服务')
    return pid

def verify_settings():
    settings=load();until=time.monotonic()+4
    while time.monotonic()<until:
        try:
            pid=live_settings_process()
            report=json.loads(Path('/run/padd/input-settings.json').read_text())
            if report.get('pid')==pid and report.get('path')==str(SETTINGS_PATH) and report.get('settings')==settings:
                print(json.dumps({'pad_settings_verified':True,'pid':pid,'settings':settings,'head_source':'official padd head target','mouth_source':'official padd mouth intent; raw sound triggers unchanged'},ensure_ascii=False));return
        except (OSError,ValueError,IndexError):pass
        time.sleep(.05)
    raise ValueError('未确认手柄服务实际加载嘴巴和头部幅度；未执行卸力或重启，请查看 padd 日志')


def main():
    action=sys.argv[1]
    if action=='validate-settings':print(json.dumps(validate(float(sys.argv[2]),float(sys.argv[3]))))
    elif action=='save-settings':print(json.dumps(save(float(sys.argv[2]),float(sys.argv[3]))))
    elif action=='verify-settings':verify_settings()
    elif action=='check-live-settings':live_settings_process()
    elif action=='start':start()
    elif action=='install':install(sys.argv[2])
    elif action=='prepare-all':prepare_all(sys.argv[2])
    elif action=='upgrade-client':upgrade_client()
    else:raise ValueError('unknown gamepad installation action')

if __name__=='__main__':
    try:main()
    except Exception as exc:
        if os.environ.get('MICRODUCK_INSTALL_LOG')!='1':raise
        log_step(ACTIVE_INSTALL_STEP,'失败',str(exc));sys.exit(1)

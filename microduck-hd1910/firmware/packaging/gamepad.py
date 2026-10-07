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

def run(*args,check=True):
    return subprocess.run(args,check=check,text=True,encoding='utf-8',errors='replace',capture_output=True)

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
    p=ROOT/MODULE;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('uinput\n')
    if not deferred:
        run('systemctl','daemon-reload')
        run('udevadm','control','--reload-rules')
        run('udevadm','trigger','--subsystem-match=input','--action=change')
        run('systemctl','--no-reload','enable','gamesir-xboxd.service')
    # Start is explicit; never change a working input service during model replacement.
    print('R7 Xbox 输入桥配置已就绪。' if deferred else 'R7 标准 Xbox 输入桥已安装；映射源码不变，运行服务为 R17。')

def start():
    run('systemctl','start','gamesir-xboxd.service')
    run('systemctl','restart','padd.service')
    print('GameSir R7 与官方 padd 已启动；保持已配对的 A+HOME 模式，连接初期不要碰摇杆/扳机。')

def upgrade_client(deferred=False):
    # Always install the frozen official unit; old unit/drop-in text may be
    # malformed or UTF-16 and must not be decoded before it can be repaired.
    run('systemd-sysusers',str(BASE/'padd-sysusers.conf'))
    dest=ROOT/'etc/systemd/system/padd.service'
    replace_owned_file(BASE/'padd.service',dest,0o644)
    settings=load()
    if not SETTINGS_PATH.exists():save(**settings)
    dest=ROOT/PAD_DROPIN;dest.parent.mkdir(parents=True,exist_ok=True)
    from configure import atomic_write
    atomic_write(dest,'[Service]\nExecStart=\nExecStart='+str(BASE/'padd')+' --socket /run/robotd.sock --config '+str(CONFIG)+' --max-head '+format(settings['head_rad'],'g')+' --input-settings '+str(SETTINGS_PATH)+'\nRuntimeDirectory=padd\n')
    if not deferred:
        run('systemctl','daemon-reload')
        run('systemctl','--no-reload','enable','padd.service')
        run('systemctl','restart','padd.service')
    print('官方 padd 配置已就绪；R7 映射保持。' if deferred else '官方 0.15.1 手柄客户端已配套升级；R7 输入映射保持。')

def install_webpad(verify=True, deferred=False):
    if not deferred:
        run('modprobe','uinput')
        run('systemctl','stop','microduck-webpad.socket','microduck-webpad.service',check=False)
    path=ROOT/'etc/modules-load.d/microduck-webpad.conf';path.parent.mkdir(parents=True,exist_ok=True);path.write_text('uinput\n')
    for name in ('microduck-webpad.service','microduck-webpad.socket'):
        replace_owned_file(BASE/name,ROOT/'etc/systemd/system'/name,0o644)
    run('systemctl','--no-reload','disable','microduck-webpad.service',check=False)
    if not deferred:
        run('systemctl','daemon-reload')
        run('systemctl','--no-reload','enable','microduck-webpad.socket')
        restart_webpad()
        if verify:verify_webpad()
    print('网页 Xbox 输入配置已就绪。' if deferred else 'R17 网页 Xbox 输入监听已就绪；首次输入按需启动，真手柄连接时撤销网页输入。')

def webpad_logs():
    for argv in [('systemctl','status','microduck-webpad.socket','microduck-webpad.service','--no-pager','--full'),
                 ('journalctl','-u','microduck-webpad.service','-n','35','--no-pager','-o','cat')]:
        result=run(*argv,check=False)
        print(result.stdout,flush=True)
        if getattr(result,'stderr',''):print(result.stderr,file=sys.stderr,flush=True)

def restart_webpad():
    run('systemctl','reset-failed','microduck-webpad.socket','microduck-webpad.service')
    try:run('systemctl','restart','microduck-webpad.socket')
    except subprocess.CalledProcessError as exc:
        if exc.stdout:print(exc.stdout,flush=True)
        if exc.stderr:print(exc.stderr,file=sys.stderr,flush=True)
        webpad_logs()
        raise ValueError('网页手柄监听重启失败；实际服务日志见上方') from None

def webpad_socket_ready():
    status=run('systemctl','is-active','--quiet','microduck-webpad.socket',check=False)
    try:return status.returncode==0 and stat.S_ISSOCK((ROOT/'run/microduck-webpad/input.sock').stat().st_mode)
    except OSError:return False

def verify_webpad():
    until=time.monotonic()+4
    while time.monotonic()<until:
        # Connecting for a health check would activate the worker. Check the
        # kernel listener and unit only; actual input receives its own reply.
        if webpad_socket_ready():
            print(json.dumps({'webpad_socket_verified':True,'path':'/run/microduck-webpad/input.sock'},ensure_ascii=False));return
        time.sleep(.05)
    webpad_logs()
    raise ValueError('网页手柄接口未启动：监听单元或 socket 路径未就绪；实际服务日志见上方')

def prepare_all(bundle):
    # The caller stops inputs and reloads systemd once after every unit is ready.
    run('modprobe','uinput')
    rules=ROOT/FILES['70-gamesir-xbox-bridge.rules']
    changed=not rules.exists() or rules.read_bytes()!=(Path(bundle)/'gamepad-r7/70-gamesir-xbox-bridge.rules').read_bytes()
    install(bundle,deferred=True)
    upgrade_client(deferred=True)
    install_webpad(verify=False,deferred=True)
    run('systemctl','--no-reload','enable','gamesir-xboxd.service','padd.service','microduck-webpad.socket')
    if changed:
        run('udevadm','control','--reload-rules')
        run('udevadm','trigger','--subsystem-match=input','--action=change')
    print('输入配置已集中安装；等待一次 systemd 重载和启动。',flush=True)

def ensure_webpad():
    if webpad_socket_ready():
        print('网页手柄监听已就绪；输入工作进程按需启动。');return
    restart_webpad()

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
    elif action=='install-webpad':install_webpad(verify='--no-verify' not in sys.argv[2:])
    elif action=='ensure-webpad':ensure_webpad()
    elif action=='verify-webpad':verify_webpad()
    else:raise ValueError('unknown gamepad installation action')

if __name__=='__main__':main()

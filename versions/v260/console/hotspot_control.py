"""Schedule an explicit Wi-Fi reset using this release's installed portal.

Runs as root on Zero through the existing management SSH channel. No robot IPC.
The queue receipt is deliberately not an assertion that an AP has started.
"""
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import shutil
import subprocess
import sys
import zlib

R5_SHA256 = '71fef0e3c179e6a39f04029dbbe937515a8c446918763e1d6fc33910bf0bc0c7'
R7_MODULE_SHA256 = '3b23f4224af343b88e92410ca6bd4bcbc10165bfadf626cd5e445379b67db191'
SSID = 'Microduck-kissqy'
PASSWORD = '12345678'
PORTAL_URL = 'http://10.42.0.1:8088'
FUNCTIONS = ('log', 'die', 'legacy_wifi_files', 'wifi_uuids_to_remove',
             'write_hotspot_profile', 'remove_wifi_profiles')


def run(*args, timeout=12):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    missing_unit = (args[:2] == ('systemctl', 'show')
                    and '--property=ActiveState' in args
                    and result.stdout.strip() == 'inactive')
    if result.returncode and not missing_unit:
        # Never copy arbitrary NetworkManager output, profile names or secrets.
        raise RuntimeError('热点操作预检或调度失败；尚未确认执行，请查看 Zero 系统日志')
    return result.stdout


def decode_original(encoded):
    if not isinstance(encoded, str) or len(encoded) > 120000:
        raise ValueError('R5 原脚本传输长度无效')
    packed = base64.b64decode(encoded, validate=True)
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    source = decoder.decompress(packed, 128 * 1024 + 1)
    if len(source) > 128 * 1024 or not decoder.eof or decoder.unused_data:
        raise ValueError('R5 原脚本压缩格式无效')
    if hashlib.sha256(source).hexdigest() != R5_SHA256:
        raise ValueError('R5 原脚本校验失败；未清除 Wi-Fi')
    return source


def r5_portal(original):
    return original.split(b'#__PORTAL_BEGIN__\n', 1)[1].split(b'#__PORTAL_END__', 1)[0]


def r5_functions(original, root=Path('/')):
    """Only these original function bodies are loaded; no installer dispatch."""
    source = original.decode('utf-8')
    path = lambda name: str(root / name.lstrip('/'))
    values = {'AP_NAME': SSID, 'AP_PASSWORD': PASSWORD, 'AP_IP': '10.42.0.1',
              'PORT': '8088', 'WIFI_DIR': path('/etc/NetworkManager/system-connections'),
              'HOTSPOT_FILE': path('/etc/NetworkManager/system-connections/Microduck-Setup.nmconnection')}
    header = 'set -Eeuo pipefail\numask 077\n' + ''.join(
        key + '=' + shlex.quote(value) + '\n' for key, value in values.items())
    bodies = []
    for name in FUNCTIONS:
        start = source.index(name + '(){')
        body_start = start + len(name) + 3
        next_function = re.search(r'^\w+\(\)\{', source[body_start:], re.M)
        end = body_start + next_function.start() if next_function else len(source)
        bodies.append(source[start:end].rstrip() + '\n')
    return header + '\n'.join(bodies)


def atomic_write(path, data, mode=0o600):
    temporary = path.with_name('.' + path.name + '-' + secrets.token_hex(6))
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(fd, 'wb') as output:
            output.write(data); output.flush(); os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def worker_script(library, interface, root=Path('/')):
    quote = shlex.quote
    state = root / 'var/lib/microduck-wifi-setup'
    # This path is an explicit, confirmed reset request, not automatic recovery.
    # Clear saved profiles before starting the explicitly requested AP.
    return ('#!/bin/bash\nset -Eeuo pipefail\numask 077\n'
            'source ' + quote(str(library)) + '\nIFACE=' + quote(interface) + '\n'
            'systemctl is-active --quiet NetworkManager.service\n'
            'test "$(nmcli -g WIFI-PROPERTIES.AP device show "$IFACE")" = yes\n'
            'test -z "$(legacy_wifi_files)"\n'
            'write_hotspot_profile\n'
            'systemctl stop microduck-setup.service\n'
            'rm -f -- ' + ' '.join(quote(str(state / name)) for name in
                ('skip-until-sealed', 'provisioned', 'ap-verified')) + '\n'
            'remove_wifi_profiles\n'
            'if test -n "$(wifi_uuids_to_remove)"; then\n'
            '  echo "仍有 Wi-Fi 配置未删除，未继续手动开启热点。" >&2\n'
            '  exit 1\nfi\n'
            'systemctl reset-failed microduck-setup.service\n'
            'systemctl enable microduck-setup.service >/dev/null\n'
            'systemctl start microduck-setup.service\n'
            'systemctl is-active --quiet microduck-setup.service\n')


def schedule(original, runner=run, root=Path('/'), which=shutil.which, uid=os.geteuid):
    if uid() != 0:
        raise RuntimeError('开启热点需要 Zero sudo 权限；未清除 Wi-Fi')
    if hashlib.sha256(original).hexdigest() != R5_SHA256:
        raise ValueError('R5 原脚本校验失败；未清除 Wi-Fi')
    for command in ('nmcli', 'systemctl', 'systemd-run', 'dnsmasq', 'bash',
                    'python3', 'chpasswd', 'ssh-keygen', 'getent'):
        if not which(command):
            raise RuntimeError('缺少配网依赖，请重新安装本版配套固件；未清除 Wi-Fi')
    program = root / 'usr/local/sbin/microduck-public-image'
    portal = root / 'usr/local/libexec/microduck-setup-portal.py'
    unit = root / 'etc/systemd/system/microduck-setup.service'
    for path in (program, portal, unit):
        if not path.is_file() or path.is_symlink():
            raise RuntimeError('尚未完整安装本版配网组件，请重新安装本版配套固件；未清除 Wi-Fi')
    mismatches = [path.name for path, expected_bytes in
                  ((program, original), (portal, r5_portal(original)))
                  if path.read_bytes() != expected_bytes]
    if mismatches:
        raise RuntimeError('配网组件与本版固件不一致：' + '、'.join(mismatches)
                           + '；请重新安装本版配套固件；未清除 Wi-Fi')
    module = root / 'usr/local/libexec/microduck_wifi_r7.py'
    if (module.is_symlink() or not module.is_file()
            or hashlib.sha256(module.read_bytes()).hexdigest() != R7_MODULE_SHA256):
        raise RuntimeError('热点启动模块缺失或与本版不一致，请重新安装本版配套固件；未清除 Wi-Fi')
    runner('systemctl', 'is-active', '--quiet', 'NetworkManager.service')
    runner('getent', 'passwd', 'radxa')
    devices = runner('nmcli', '-t', '-f', 'DEVICE,TYPE', 'device', 'status')
    interfaces = [line.split(':')[0] for line in devices.splitlines()
                  if line.endswith(':wifi')]
    if not interfaces or not re.fullmatch(r'[A-Za-z0-9_.-]{1,32}', interfaces[0]):
        raise RuntimeError('未找到可用 Wi-Fi 网卡；未清除 Wi-Fi')
    interface = interfaces[0]
    if runner('nmcli', '-g', 'WIFI-PROPERTIES.AP', 'device', 'show', interface).strip() != 'yes':
        raise RuntimeError('未确认无线网卡支持热点；未清除 Wi-Fi')
    starts = re.findall(r'^ExecStart=(.*)$', unit.read_text(), re.M)
    expected = '/usr/bin/python3 ' + str(portal) + ' --serve ' + interface
    if starts not in ([expected], ['/usr/bin/python3 ' + str(portal) + ' --serve auto']) or runner('systemctl', 'show', '--property=DropInPaths',
                                    '--value', 'microduck-setup.service').strip():
        raise RuntimeError('R5 配网服务启动配置不匹配；未清除 Wi-Fi')
    state = root / 'run'
    if (state / 'microduck-wifi-test-restore').exists():
        raise RuntimeError('R5 热点测试尚未结束；未清除 Wi-Fi')
    for other in ('microduck-image-seal.timer', 'microduck-ap-test.timer',
                  'microduck-ap-test.service', 'microduck-ap-restore.timer'):
        active = runner('systemctl', 'show', '--property=ActiveState', '--value', other).strip()
        if active in ('active', 'activating', 'reloading'):
            raise RuntimeError('已有 R5 测试或镜像封存任务；未清除 Wi-Fi')
    functions = r5_functions(original, root)
    if runner('/bin/bash', '-c', functions + '\nlegacy_wifi_files\n').strip():
        raise RuntimeError('发现非 NetworkManager 的旧 Wi-Fi 配置，请先人工处理；未清除 Wi-Fi')
    runtime = root / 'run/microduck-hotspot-reset'
    runtime.mkdir(mode=0o700, parents=True, exist_ok=True)
    if runtime.is_symlink() or runtime.stat().st_mode & 0o077:
        raise RuntimeError('热点任务目录权限异常；未清除 Wi-Fi')
    lock_path = runtime / 'submit.lock'
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'r+') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('已有热点切换请求正在提交；未重复执行') from None
        pending = runtime / 'pending.json'
        if pending.exists():
            previous = json.loads(pending.read_text()).get('unit', '')
            if not re.fullmatch(r'microduck-hotspot-reset-[0-9a-f]{16}', previous):
                raise RuntimeError('热点任务状态无效，请重启后核对；未清除 Wi-Fi')
            for suffix in ('.timer', '.service'):
                active = runner('systemctl', 'show', '--property=ActiveState', '--value',
                                previous + suffix).strip()
                if active in ('active', 'activating', 'reloading'):
                    raise RuntimeError('热点切换任务已调度；未重复执行')
        name = 'microduck-hotspot-reset-' + secrets.token_hex(8)
        task = runtime / name
        task.mkdir(mode=0o700)
        library = task / 'r5-functions.sh'
        worker = task / 'reset.sh'
        atomic_write(library, functions.encode())
        atomic_write(worker, worker_script(library, interface, root).encode(), 0o700)
        # Preparation loads the AP profile but does not disconnect any network.
        runner('/bin/bash', '-c', 'source ' + shlex.quote(str(library)) +
               '\nIFACE=' + shlex.quote(interface) + '\nwrite_hotspot_profile\n')
        atomic_write(pending, json.dumps({'unit': name}).encode())
        runner('systemd-run', '--quiet', '--collect', '--unit=' + name,
               '--on-active=5s', '--timer-property=AccuracySec=1s',
               '--property=Type=oneshot', '--property=TimeoutStartSec=120',
               '/bin/bash', str(worker))
        return {'accepted': True, 'queued': True, 'delay_seconds': 5,
                'ssid': SSID, 'password': PASSWORD, 'portal_url': PORTAL_URL,
                'unit': name, 'r5_sha256': R5_SHA256, 'hotspot_revision': 'R10-boot-only',
                'message': '热点切换任务已调度，约5秒后断开网络；配网时需设置Zero登录密码。热点是否出现请用手机确认。'}


if __name__ == '__main__':
    try:
        if len(sys.argv) != 2: raise ValueError('热点请求参数无效')
        print(json.dumps(schedule(decode_original(sys.argv[1])), ensure_ascii=False))
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)

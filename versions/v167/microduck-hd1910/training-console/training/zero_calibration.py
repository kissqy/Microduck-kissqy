"""Read the saved ZERO calibration using the desktop's existing OpenSSH identity."""
import ipaddress
import json
import re
import shutil
import subprocess

CALIBRATION_PATH = '/etc/robot/feetech-ft5/hd1910-calibration.toml'
MAX_BYTES = 256 * 1024


def normalize_target(value):
    if not isinstance(value, str):
        raise ValueError('请填写 ZERO 的 IP 或 用户名@IP。')
    target = value.strip()
    if '@' not in target:
        target = 'radxa@' + target
    if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}@[A-Za-z0-9][A-Za-z0-9_.-]{0,252}', target):
        raise ValueError('ZERO 地址格式无效，请填写 IP、主机名或 radxa@IP。')
    host = target.split('@', 1)[1]
    if re.fullmatch(r'[\d.]+', host):
        try:
            ipaddress.IPv4Address(host)
        except ValueError:
            raise ValueError('ZERO 的 IP 地址无效，每段应为 0～255。') from None
    return target


def load_connection(directory):
    """Prefer our last successful import, then the runtime console's saved target."""
    for path, key, source in [
        (directory / 'zero_connection.json', 'target', '上次获取'),
        (directory.parent / 'MicroduckConsole' / 'connection.json', 'last_target', '运行中控'),
    ]:
        try:
            value = json.loads(path.read_text(encoding='utf-8'))
            return {'target': normalize_target(value[key]), 'source': source}
        except (OSError, ValueError, TypeError, KeyError):
            pass
    return {'target': '', 'source': ''}


def failure_message(detail, target):
    raw = detail.lower()
    if 'remote host identification has changed' in raw or 'offending' in raw and 'host key' in raw:
        return 'ZERO 的 SSH 主机指纹已变化，请在运行中控确认当前设备后重试。'
    if 'host key verification failed' in raw or 'strict checking' in raw:
        return f'此电脑尚未确认 ZERO 的 SSH 身份，请先在终端执行 ssh {target} 确认设备，再点击获取。'
    if 'permission denied' in raw and CALIBRATION_PATH in detail:
        return '已连接 ZERO，但当前账户无权读取标定文件。原标定未替换。'
    if 'permission denied' in raw or 'no supported authentication' in raw or 'sign_and_send_pubkey' in raw:
        return f'ZERO 的 SSH 密钥登录失败。请使用运行中控所在的 Windows 账户，并确认 ssh {target} 可以免密登录。'
    if 'no such file' in raw:
        return 'ZERO 上未找到 ' + CALIBRATION_PATH + '，请先在运行中控保存新标定。'
    if 'could not resolve' in raw or 'name or service not known' in raw:
        return '无法解析 ZERO 地址，请填写机器人当前的 IP。'
    if 'connection refused' in raw:
        return 'ZERO 拒绝 SSH 连接，请检查地址及 SSH 服务。'
    if any(word in raw for word in ('timed out', 'timeout', 'no route to host', 'network is unreachable')):
        return '连接 ZERO 超时，请检查地址和网络。原标定未替换。'
    return '从 ZERO 读取标定失败，请确认机器人在线及 SSH 连接正常。原标定未替换。'


def read_calibration(target):
    target = normalize_target(target)
    executable = shutil.which('ssh')
    if not executable:
        raise ValueError('未找到系统 OpenSSH 客户端，请启用 Windows 的 OpenSSH 客户端后重试。')
    # Same key/known_hosts files as the runtime console. No remote setup, probe,
    # sudo, daemon operation, shell interpolation or interactive password prompt.
    options = [
        'BatchMode=yes', 'PreferredAuthentications=publickey', 'PubkeyAuthentication=yes',
        'PasswordAuthentication=no', 'KbdInteractiveAuthentication=no', 'NumberOfPasswordPrompts=0',
        'StrictHostKeyChecking=yes', 'ConnectionAttempts=1', 'ConnectTimeout=6',
        'ServerAliveInterval=3', 'ServerAliveCountMax=2', 'ClearAllForwardings=yes',
        'PermitLocalCommand=no', 'ControlMaster=no', 'ControlPath=none',
    ]
    argv = [executable, '-T'] + [v for option in options for v in ('-o', option)]
    argv += [target, 'head -c ' + str(MAX_BYTES + 1) + ' -- ' + CALIBRATION_PATH]
    try:
        result = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=15,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except subprocess.TimeoutExpired:
        raise ValueError('获取 ZERO 标定超过15秒，请检查地址和网络后重试。原标定未替换。') from None
    except OSError:
        raise ValueError('无法启动系统 SSH 客户端，请检查 OpenSSH 安装。') from None
    if result.returncode:
        raise ValueError(failure_message(result.stderr.decode('utf-8', errors='replace'), target))
    if not result.stdout or len(result.stdout) > MAX_BYTES:
        raise ValueError('ZERO 标定文件为空或超过256KB，原标定未替换。')
    try:
        return result.stdout.decode('utf-8-sig')
    except UnicodeError:
        raise ValueError('ZERO 标定文件不是有效的 UTF-8 文本，原标定未替换。') from None


def calibration_changes(before, after):
    old = {row['name']: row for row in (before or {}).get('joints', [])}
    changes = []
    for row in after['joints']:
        previous = old.get(row['name'], {})
        fields = {key: {'before': previous.get(key), 'after': row.get(key)}
                  for key in ('id', 'zero_raw', 'direction', 'min_rad', 'max_rad', 'calibrated')
                  if previous.get(key) != row.get(key)}
        if fields:
            changes.append({'name': row['name'], 'id': row['id'], 'fields': fields})
    return {'joints': changes,
            'imu_changed': any((before or {}).get(k) != after.get(k)
                               for k in ('imu_mount_quat', 'imu_mount_verified'))}

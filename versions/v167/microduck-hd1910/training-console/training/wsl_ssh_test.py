"""Windows-side WSL test connection; then use the ordinary SSH deployment path."""
import base64
import hashlib
import json
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time


def text_output(value):
    if value.startswith((b'\xff\xfe', b'\xfe\xff')):
        return value.decode('utf-16').strip()
    if b'\x00' in value:
        return value.decode('utf-16-le', errors='replace').strip()
    return value.decode('utf-8', errors='replace').strip()


def validate_distro(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', value):
        raise ValueError('WSL发行版名称无效，例如Ubuntu或Ubuntu-24.04。')
    return value


def run(argv, timeout=30):
    result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise ValueError(text_output(result.stderr or result.stdout)[-2200:] or 'WSL命令失败，请检查所选发行版。')
    return result.stdout


def prepare(directory, root, distro, report):
    distro = validate_distro(distro)
    if sys.platform != 'win32':
        raise ValueError('本机WSL测试入口需在Windows中启动训练中控。')
    wsl, keygen, ssh = shutil.which('wsl.exe'), shutil.which('ssh-keygen'), shutil.which('ssh')
    if not wsl:
        raise ValueError('未找到WSL。请使用已有WSL2 Ubuntu；本入口不会安装或重建发行版。')
    if not keygen or not ssh:
        raise ValueError('请在Windows可选功能中启用OpenSSH客户端，再点击本机WSL测试。')
    report('正在检查所选WSL的默认账户…')
    user = text_output(run([wsl, '--distribution', distro, '--exec', 'id', '-un']))
    if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}', user):
        raise ValueError('无法取得WSL默认用户名，请检查所选发行版。')
    local = directory / 'wsl-ssh-test' / hashlib.sha256(distro.encode()).hexdigest()[:12]
    local.mkdir(parents=True, exist_ok=True)
    identity = local / 'id_ed25519'
    if not identity.exists():
        run([keygen, '-q', '-t', 'ed25519', '-N', '', '-f', str(identity), '-C', 'microduck-wsl-test'])
    public = Path(str(identity) + '.pub')
    if not public.is_file():
        raise ValueError('WSL测试密钥的公钥缺失，请恢复测试密钥后重试。')
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        preferred_port = listener.getsockname()[1]
    payload = {'user': user, 'public_key': public.read_text().strip(), 'preferred_port': preferred_port}
    encoded = base64.b64encode(json.dumps(payload).encode()).decode()
    report('正在准备WSL专用SSH服务（缺少OpenSSH时自动安装），不会启动GPU训练…')
    boot = (root / 'training/wsl_ssh_boot.py').read_text(encoding='utf-8')
    output = text_output(run([wsl, '--distribution', distro, '--user', 'root', '--exec', 'python3', '-c', boot, encoded], timeout=540))
    line = next((line for line in output.splitlines() if line.startswith('MICRODUCK_WSL_SSH ')), None)
    if not line:
        raise ValueError('WSL未返回测试SSH信息。请确认WSL中已有Python3。')
    info = json.loads(line[len('MICRODUCK_WSL_SSH '):])
    port = info.get('port')
    if type(port) is not int or not 1024 <= port <= 65535 or info.get('user') != user:
        raise ValueError('WSL测试SSH信息无效。')
    host_key = info.get('host_key', '')
    if not re.fullmatch(r'ssh-ed25519 [A-Za-z0-9+/=]+', host_key):
        raise ValueError('WSL测试主机公钥无效。')
    # Fingerprint is obtained through the selected local WSL execution channel,
    # rather than by trusting an unauthenticated ssh-keyscan network response.
    known_hosts = local / 'known_hosts'
    known_hosts.write_text('[127.0.0.1]:%d %s\n' % (port, host_key), encoding='utf-8')
    report('正在检查Windows到WSL的本机端口转发…')
    for attempt in range(30):
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=.5) as connection:
                if connection.recv(255).startswith(b'SSH-'):
                    break
        except OSError:
            time.sleep(.2)
    else:
        raise ValueError('Windows无法通过127.0.0.1访问WSL测试SSH端口。请检查WSL的localhostForwarding；本入口不会重启WSL或修改网络配置。')
    return {'host': '127.0.0.1', 'user': user, 'port': port, 'identity': str(identity),
            'known_hosts': str(known_hosts), 'workspace': info['workspace'], 'wsl_distro': distro}

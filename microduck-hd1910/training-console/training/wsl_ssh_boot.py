"""Run as root in the selected WSL: prepare a dedicated key-only loopback sshd."""
import base64
import fcntl
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import socket
import subprocess
import sys
import time


def execute(argv, timeout=30):
    result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout,
                            env=dict(os.environ, DEBIAN_FRONTEND='noninteractive'))
    if result.returncode:
        raise RuntimeError(result.stdout.decode(errors='replace')[-2200:] or 'WSL SSH命令执行失败。')
    return result.stdout.decode(errors='replace').strip()


def prepare(payload):
    if sys.platform != 'linux' or os.geteuid() != 0:
        raise RuntimeError('WSL SSH准备需要在所选WSL的root账户执行。')
    user = payload['user']
    if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}', user):
        raise ValueError('WSL默认用户名无效。')
    account = pwd.getpwnam(user)
    public_key = payload['public_key'].strip()
    if not re.fullmatch(r'ssh-ed25519 [A-Za-z0-9+/=]+(?: [^\r\n]+)?', public_key):
        raise ValueError('测试公钥无效。')
    directory = Path(account.pw_dir) / '.config/MicroduckTrainingStudio/wsl-ssh-test'
    directory.mkdir(parents=True, exist_ok=True)
    directory.chmod(0o700)
    os.chown(directory, account.pw_uid, account.pw_gid)
    with (directory / 'prepare.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('WSL测试SSH正在准备，请稍后重试。')
        sshd = shutil.which('sshd') or ('/usr/sbin/sshd' if Path('/usr/sbin/sshd').is_file() else None)
        if not sshd:
            if not shutil.which('apt-get'):
                raise RuntimeError('WSL中没有sshd；当前入口支持Ubuntu/Debian自动安装OpenSSH。')
            execute(['apt-get', 'update'], timeout=180)
            execute(['apt-get', 'install', '-y', 'openssh-server'], timeout=240)
            sshd = '/usr/sbin/sshd'
        keygen = shutil.which('ssh-keygen')
        if not keygen:
            raise RuntimeError('WSL中缺少ssh-keygen，请检查OpenSSH安装。')
        Path('/run/sshd').mkdir(mode=0o755, exist_ok=True)
        host_key = directory / 'host_ed25519'
        if not host_key.exists():
            execute([keygen, '-q', '-t', 'ed25519', '-N', '', '-f', str(host_key)])
        host_key.chmod(0o600)
        authorized = directory / 'authorized_keys'
        authorized.write_text(public_key + '\n', encoding='utf-8')
        authorized.chmod(0o600)
        os.chown(authorized, account.pw_uid, account.pw_gid)
        # This is a separate daemon/config, never rewrite /etc/ssh/sshd_config
        # or the user's regular ~/.ssh/authorized_keys.
        info_path = directory / 'server.json'
        info = None
        try:
            saved = json.loads(info_path.read_text())
            pid, port = saved['pid'], saved['port']
            if type(pid) is not int or pid <= 1 or type(port) is not int or not 1024 <= port <= 65535:
                raise ValueError('invalid sshd registration')
            os.kill(pid, 0)
            command = Path('/proc/%d/cmdline' % pid).read_bytes()
            if str(directory / 'sshd_config').encode() not in command:
                raise RuntimeError('WSL测试SSH记录的进程身份不符，未结束该进程。')
            with socket.create_connection(('127.0.0.1', port), timeout=2) as connection:
                if not connection.recv(255).startswith(b'SSH-'):
                    raise RuntimeError('WSL测试端口未返回SSH服务。')
            info = saved
        except (OSError, ValueError, KeyError):
            # If a recorded daemon is alive but does not respond, fail closed.
            if 'saved' in locals() and type(saved.get('pid')) is int and saved['pid'] > 1:
                try:
                    os.kill(saved['pid'], 0)
                except ProcessLookupError:
                    pass
                else:
                    raise RuntimeError('WSL测试SSH进程仍在运行但端口无响应，请查看测试SSH日志。')
        if info is None:
            preferred = payload.get('preferred_port')
            with socket.socket() as listener:
                try:
                    listener.bind(('127.0.0.1', preferred if type(preferred) is int and 1024 <= preferred <= 65535 else 0))
                except OSError:
                    listener.bind(('127.0.0.1', 0))
                port = listener.getsockname()[1]
            def quote(path):
                return '"' + str(path).replace('\\', '\\\\').replace('"', '\\"') + '"'
            config = directory / 'sshd_config'
            config.write_text('\n'.join([
                'Port %d' % port, 'ListenAddress 127.0.0.1', 'HostKey ' + quote(host_key),
                'AuthorizedKeysFile ' + quote(authorized), 'PidFile ' + quote(directory / 'sshd.pid'),
                'PasswordAuthentication no', 'KbdInteractiveAuthentication no', 'UsePAM yes',
                'PermitRootLogin prohibit-password', 'AllowUsers ' + user, 'StrictModes yes',
                'AllowTcpForwarding yes', 'PermitOpen 127.0.0.1:*', 'LogLevel ERROR', '']))
            execute([sshd, '-t', '-f', str(config)])
            with (directory / 'sshd.log').open('ab', buffering=0) as log:
                process = subprocess.Popen([sshd, '-D', '-e', '-f', str(config)], stdin=subprocess.DEVNULL,
                                           stdout=log, stderr=log, start_new_session=True, close_fds=True)
            for attempt in range(40):
                if process.poll() is not None:
                    raise RuntimeError('WSL测试SSH启动失败：' + (directory / 'sshd.log').read_text(errors='replace')[-1800:])
                try:
                    with socket.create_connection(('127.0.0.1', port), timeout=.5) as connection:
                        if connection.recv(255).startswith(b'SSH-'):
                            break
                except OSError:
                    time.sleep(.1)
            else:
                process.terminate()
                raise RuntimeError('WSL测试SSH启动超时。')
            info = {'port': port, 'pid': process.pid}
            temporary = info_path.with_suffix('.tmp')
            temporary.write_text(json.dumps(info))
            temporary.replace(info_path)
        host_public = host_key.with_suffix('.pub').read_text().split()
        return {**info, 'user': user, 'host_key': ' '.join(host_public[:2]),
                'workspace': '~/microduck-training-ssh-wsl-test', 'ssh_directory': str(directory)}


if __name__ == '__main__':
    try:
        print('MICRODUCK_WSL_SSH ' + json.dumps(prepare(json.loads(base64.b64decode(sys.argv[1])))))
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)

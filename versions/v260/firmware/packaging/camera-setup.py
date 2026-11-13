#!/usr/bin/env python3
"""Replace only mediad's executable; retain its installed service arguments and environment."""
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys


def run(*args):
    return subprocess.run(['systemctl', *args], check=True, capture_output=True, text=True).stdout


def installed_arguments(description):
    match = re.search(r'argv\[\]=(.*?)\s*;\s*ignore_errors=', description, re.S)
    if not match:
        raise ValueError('无法读取 mediad 的实际启动命令；未修改服务')
    arguments = shlex.split(match.group(1))
    if not arguments or Path(arguments[0]).name != 'mediad':
        raise ValueError('mediad 使用了自定义包装命令；未修改服务')
    return arguments


def quote_argument(argument):
    if any(c in argument for c in '\n\r\0'):
        raise ValueError('mediad 启动参数包含无法保留的字符；未修改服务')
    return '"' + argument.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%').replace('$', '$$') + '"'


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_bytes(data)
    temporary.chmod(0o644)
    os.replace(temporary, path)


def setup(bundle, command=run, directory=Path('/etc/systemd/system/mediad.service.d')):
    executable = Path(bundle).resolve() / 'mediad'
    if not executable.is_file():
        raise ValueError('新版 mediad 文件缺失；未修改服务')
    arguments = installed_arguments(command('show', 'mediad.service', '--property=ExecStart', '--value'))
    arguments[0] = str(executable)
    payload = ('# Microduck camera demand: the installed arguments are preserved.\n'
               '[Service]\nExecStart=\nExecStart=' + ' '.join(map(quote_argument, arguments)) + '\n').encode()
    path = Path(directory) / '40-microduck-camera-demand.conf'
    previous = path.read_bytes() if path.exists() else None
    try:
        atomic_write(path, payload)
        command('daemon-reload')
        command('restart', 'mediad.service')
    except Exception:
        if previous is None:
            path.unlink(missing_ok=True)
        else:
            atomic_write(path, previous)
        try:
            command('daemon-reload')
            command('restart', 'mediad.service')
        except Exception as rollback:
            print(f'摄像头配置已恢复；mediad 重启失败：{rollback}', file=sys.stderr)
        raise
    return payload


def main():
    try:
        if len(sys.argv) != 2:
            raise ValueError('用法：camera-setup.py 安装目录')
        setup(sys.argv[1])
        print('已提交 mediad 启动请求；视频会话按需唤醒，最后一个使用者退出后休眠')
        return 0
    except Exception as error:
        detail = error.stderr.strip() if isinstance(error, subprocess.CalledProcessError) and error.stderr else str(error)
        print(f'摄像头配置失败：{detail}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

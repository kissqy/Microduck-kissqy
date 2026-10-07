"""Executed through SSH; installs an isolated dashboard and starts its daemon."""
import base64
import io
import json
import os
from pathlib import Path
import socket
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile

RELEASE = 'R1.5.17'


def find_uv(root):
    candidates = (shutil.which('uv'), Path.home() / '.local/bin/uv',
                  Path.home() / '.cargo/bin/uv', root / 'bootstrap/bin/uv')
    for candidate in candidates:
        if not candidate or not os.access(candidate, os.X_OK):
            continue
        try:
            result = subprocess.run([str(candidate), '--version'], stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, timeout=10)
            if result.returncode == 0:
                return str(candidate)
        except (OSError, subprocess.TimeoutExpired):
            pass
    return None


def gpu_summary():
    # Noninteractive SSH in WSL does not inherit the terminal's PATH.
    binary = shutil.which('nvidia-smi')
    if not binary and Path('/usr/lib/wsl/lib/nvidia-smi').is_file():
        binary = '/usr/lib/wsl/lib/nvidia-smi'
    if not binary:
        return '未找到GPU状态工具；不代表CUDA不可用，以训练环境状态为准。'
    try:
        result = subprocess.run([binary, '--query-gpu=name,memory.total,driver_version', '--format=csv,noheader'],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=12)
    except subprocess.TimeoutExpired:
        return 'GPU状态读取超时；以训练环境状态为准。'
    except OSError:
        return 'GPU状态工具无法执行；以训练环境状态为准。'
    value = result.stdout.decode(errors='replace').strip()
    return value if result.returncode == 0 and value else 'GPU状态工具未返回有效数据；以训练环境状态为准。'


def launch(payload):
    if sys.platform != 'linux' or sys.version_info < (3, 10):
        raise RuntimeError('服务器需要 Linux 和 Python 3.10 或更新版本。')
    root = Path(payload['workspace']).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    app = root / 'releases' / RELEASE
    state = root / 'state' / 'MicroduckTrainingStudio'
    if payload['operation'] == 'deploy':
        packed = sys.stdin.buffer.read(64 * 1024 * 1024 + 1)
        if len(packed) > 64 * 1024 * 1024:
            raise RuntimeError('训练中控包超过上传上限。')
        with zipfile.ZipFile(io.BytesIO(packed)) as archive:
            if len(archive.infolist()) > 5000 or sum(i.file_size for i in archive.infolist()) > 150 * 1024 * 1024:
                raise RuntimeError('训练中控包大小无效。')
            for item in archive.infolist():
                destination = (app / item.filename).resolve()
                if not destination.is_relative_to(app) or item.filename.startswith('/'):
                    raise RuntimeError('训练中控包包含无效路径。')
            archive.extractall(app)
        if not (app / 'training_console.py').is_file():
            raise RuntimeError('训练中控包不完整。')
        state.mkdir(parents=True, exist_ok=True)
        if not (state / 'recipe.json').exists():
            (state / 'recipe.json').write_text(json.dumps(payload['recipe'], ensure_ascii=False), encoding='utf-8')
        if not (state / 'profile.json').exists():
            (state / 'profile.json').write_text(json.dumps(payload['profile']), encoding='utf-8')
        # Explicit deploy already prepares missing OS components in one pass.
        # Keep trainer dependencies isolated and preserve the pinned uv lock.
        if not shutil.which('git'):
            raise RuntimeError('服务器缺少 git，请先安装 git，再点击部署。')
        uv = find_uv(root)
        if not uv:
            print('MICRODUCK_SETUP 正在准备独立uv组件…', flush=True)
            bootstrap = root / 'bootstrap'
            commands = [[sys.executable, '-m', 'venv', str(bootstrap)],
                        [str(bootstrap / 'bin/python'), '-m', 'pip', 'install', '--disable-pip-version-check', 'uv']]
            for command in commands:
                result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
                if result.returncode:
                    raise RuntimeError('准备 uv 失败（需 python3-venv 和包下载网络）：' + result.stdout.decode(errors='replace')[-1800:])
    if not (app / 'training_console.py').is_file():
        raise RuntimeError('服务器还没有本版训练中控，请先点击“部署并连接”。')
    registration = root / 'server.json'
    info = None
    saved = {}
    try:
        saved = json.loads(registration.read_text())
        port = saved['port']
        if type(port) is not int or not 1024 <= port <= 65535:
            raise ValueError('invalid port')
        with urllib.request.urlopen('http://127.0.0.1:%d/api/config' % port, timeout=2) as response:
            cfg = json.load(response)
        if cfg.get('remote_workspace') != str(root):
            raise RuntimeError('已记录的端口被其他服务占用，未启动第二个训练服务。')
        if cfg.get('release') != RELEASE:
            raise RuntimeError('该目录正在运行其他版本训练服务，请先结束其队列并关闭该服务，再部署。')
        info = saved
    except (OSError, ValueError, KeyError):
        pass
    if info is None:
        recorded_pid = saved.get('pid')
        if type(recorded_pid) is int and recorded_pid > 1:
            try:
                os.kill(recorded_pid, 0)
            except ProcessLookupError:
                pass
            else:
                raise RuntimeError('记录的训练服务仍在运行但没有响应，未启动第二个服务。请稍后重连并检查服务器日志。')
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        env = dict(os.environ, PYTHONUTF8='1', MICRODUCK_REMOTE_WORKSPACE=str(root))
        env['PATH'] = os.pathsep.join((str(root / 'bootstrap/bin'), str(Path.home() / '.local/bin'), str(Path.home() / '.cargo/bin'), env.get('PATH', '')))
        if Path('/usr/lib/wsl/lib').is_dir():
            env['PATH'] = '/usr/lib/wsl/lib' + os.pathsep + env['PATH']
        state.mkdir(parents=True, exist_ok=True)
        with (root / 'server.log').open('ab', buffering=0) as log:
            process = subprocess.Popen([sys.executable, str(app / 'training_console.py'), '--port', str(port), '--data-dir', str(state)],
                                       cwd=app, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                       start_new_session=True, close_fds=True)
        info = {'port': port, 'pid': process.pid, 'release': RELEASE, 'workspace': str(root)}
        for attempt in range(50):
            try:
                with urllib.request.urlopen('http://127.0.0.1:%d/api/config' % port, timeout=1) as response:
                    cfg = json.load(response)
                if cfg.get('release') != RELEASE or cfg.get('remote_workspace') != str(root):
                    raise RuntimeError('训练服务启动身份不符。')
                break
            except OSError:
                if process.poll() is not None:
                    raise RuntimeError('训练服务启动失败：' + (root / 'server.log').read_text(errors='replace')[-1800:])
                time.sleep(.2)
        else:
            process.terminate()
            raise RuntimeError('训练服务启动超时，请检查服务器日志。')
        temporary = registration.with_suffix('.tmp')
        temporary.write_text(json.dumps(info), encoding='utf-8')
        temporary.replace(registration)
    info.update(gpu=gpu_summary(), python=sys.version.split()[0])
    return info


if __name__ == '__main__':
    try:
        payload = json.loads(base64.b64decode(sys.argv[1]))
        root = Path(payload['workspace']).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        import fcntl
        with (root / 'deployment.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError('该服务器目录正在被另一个中控部署或连接，请稍后重试。')
            result = launch(payload)
        print('MICRODUCK_SSH_RESULT ' + json.dumps(result, ensure_ascii=False))
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)

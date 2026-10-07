"""OpenSSH transport for a remote copy of the SAME Training Studio backend."""
import base64
import copy
import io
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import zipfile

RELEASE = 'R1.5.17'
DEFAULT_CONNECTION = {'host': '', 'user': 'ubuntu', 'port': 22, 'identity': '',
                      'workspace': '~/microduck-training-ssh', 'known_hosts': '', 'wsl_distro': '', 'auth': 'key'}


def validate_connection(value):
    if not isinstance(value, dict):
        raise ValueError('服务器连接配置无效。')
    result = {k: value.get(k, v) for k, v in DEFAULT_CONNECTION.items()}
    for key in ('host', 'user', 'identity', 'workspace', 'known_hosts', 'wsl_distro', 'auth'):
        if not isinstance(result[key], str):
            raise ValueError('服务器连接字段应为文本。')
        result[key] = result[key].strip()
    if result['auth'] not in ('key', 'password'):
        raise ValueError('请选择密码或密钥登录。')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,252}', result['host']):
        raise ValueError('请填写服务器 IP、主机名或 SSH 配置别名。')
    if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}', result['user']):
        raise ValueError('SSH 用户名无效。')
    if type(result['port']) is not int or not 1 <= result['port'] <= 65535:
        raise ValueError('SSH 端口应为 1～65535。')
    for key in ('identity', 'workspace', 'known_hosts'):
        if len(result[key]) > 1024 or any(ord(c) < 32 for c in result[key]):
            raise ValueError('服务器路径无效。')
    if result['workspace'] in ('/', '~/', '/tmp', '/home') or not result['workspace'].startswith(('/', '~/')):
        raise ValueError('远程工作目录应是独立目录，例如 ~/microduck-training-ssh。')
    if result['wsl_distro']:
        from training.wsl_ssh_test import validate_distro
        validate_distro(result['wsl_distro'])
        if result['host'] != '127.0.0.1' or not result['known_hosts'] or not result['identity']:
            raise ValueError('WSL测试连接应使用专用的本机密钥和主机公钥。')
    return result


def available_port():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        return listener.getsockname()[1]


def ssh_argv(connection):
    executable = shutil.which('ssh')
    if not executable:
        raise ValueError('未找到 OpenSSH。Windows 请启用“OpenSSH 客户端”，再启动中控。')
    options = ['BatchMode=yes', 'StrictHostKeyChecking=yes', 'ConnectTimeout=10',
               'ConnectionAttempts=1', 'ServerAliveInterval=15', 'ServerAliveCountMax=3',
               'ExitOnForwardFailure=yes', 'PermitLocalCommand=no', 'RemoteCommand=none',
               'ControlMaster=no', 'ControlPath=none', 'ForwardAgent=no']
    argv = [executable, '-T', '-p', str(connection['port'])]
    argv += [part for option in options for part in ('-o', option)]
    if connection.get('known_hosts'):
        known = Path(connection['known_hosts']).expanduser()
        if not known.is_file():
            raise ValueError('WSL测试主机公钥文件不存在，请重新运行本机WSL测试。')
        name = str(known).replace(chr(92), '/').replace('"', chr(92) + '"')
        argv += ['-o', 'UserKnownHostsFile="' + name + '"']
    if connection['identity']:
        identity = Path(os.path.expandvars(connection['identity'])).expanduser()
        if not identity.is_file():
            raise ValueError('SSH 密钥路径不存在；填写本机密钥文件路径，或留空使用系统密钥。')
        argv += ['-i', str(identity), '-o', 'IdentitiesOnly=yes']
    return argv


def failure_message(detail):
    lower = detail.lower()
    if 'host key verification failed' in lower or 'remote host identification has changed' in lower:
        return 'SSH 主机身份尚未确认或已变化。请先用页面显示的 SSH 命令在本机终端核对服务器指纹，然后重试。'
    if 'permission denied' in lower or 'sign_and_send_pubkey' in lower:
        return 'SSH 密钥登录失败。请先配置免密登录；加密密钥需先加入 ssh-agent。'
    if 'could not resolve' in lower:
        return '无法解析服务器地址，请检查 IP 或主机名。'
    if 'connection refused' in lower or 'timed out' in lower or 'no route to host' in lower:
        return '无法连接服务器，请检查 SSH 端口、服务器状态和网络。'
    return detail.strip()[-2200:] or 'SSH 操作失败。'


class RemoteTraining:
    def __init__(self, directory, root, manager, save_json):
        self.directory, self.root, self.manager, self.save_json = directory, root, manager, save_json
        self.lock = threading.RLock()
        self.target = 'local'
        self.connection = {**DEFAULT_CONNECTION, 'auth': 'password'}
        self.operation = None
        self.status, self.message = 'disconnected', '本机训练；尚未连接训练服务器。'
        self.info, self.tunnels, self.remote_token = {}, {}, ''
        self.closed = False
        self.passwords, self.password_client, self.pending_host = {}, None, None
        try:
            saved = json.loads((directory / 'remote_connection.json').read_text(encoding='utf-8'))
            self.connection = validate_connection({'auth': 'key', **saved['connection']})
            if saved.get('target') == 'ssh':
                self.target = 'ssh'
                self.message = '请重新连接服务器；未自动启动训练，也不会转到本机执行。'
        except (OSError, KeyError, TypeError, ValueError):
            pass

    def snapshot(self):
        with self.lock:
            tunnel = self.tunnels.get(self.info.get('port'))
            if self.status == 'connected' and (not tunnel or tunnel['process'].poll() is not None):
                self.status = 'disconnected'
                self.message = 'SSH 已断开，服务器任务继续；请点击重新连接。'
            return {'target': self.target, 'connection': dict(self.connection), 'status': self.status,
                    'message': self.message, 'busy': bool(self.operation), 'info': dict(self.info),
                    'wsl_test_supported': sys.platform == 'win32',
                    'wsl_distro': self.connection.get('wsl_distro') or self.manager.profile.get('distro', 'Ubuntu'),
                    'has_server_backup': (self.directory / 'remote_server_connection.json').is_file(),
                    'password_available': bool(self.passwords.get(self.password_id())),
                    'pending_host': dict(self.pending_host['details']) if self.pending_host else None}

    def password_id(self):
        return tuple(self.connection[k] for k in ('host', 'user', 'port'))

    def persist(self):
        self.save_json(self.directory / 'remote_connection.json',
                       {'target': self.target, 'connection': self.connection})

    def configure(self, value):
        incoming = value.get('connection')
        if not isinstance(incoming, dict):
            raise ValueError('服务器连接配置无效。')
        with self.lock:
            merged = {**self.connection, **incoming}
            if any(merged.get(k) != self.connection.get(k) for k in ('host', 'user', 'port', 'identity', 'auth')):
                merged.update(known_hosts='', wsl_distro='')
            connection = validate_connection(merged)
            if self.operation:
                raise ValueError('正在连接或部署，请等待完成。')
            password = value.get('password')
            if password is not None and (not isinstance(password, str) or len(password) > 4096 or '\x00' in password):
                raise ValueError('SSH密码格式无效。')
            if connection != self.connection:
                self.disconnect()
                self.pending_host = None
            self.connection = connection
            if connection['auth'] == 'password' and password:
                self.passwords[self.password_id()] = password
            self.persist()
        return self.snapshot()

    def select(self, value):
        target = value.get('target')
        if target not in ('local', 'ssh'):
            raise ValueError('训练位置无效。')
        with self.lock:
            if self.operation:
                raise ValueError('连接或部署完成后再切换训练位置。')
            self.target = target
            self.persist()
        return self.snapshot()

    def start(self, operation):
        if operation not in ('connect', 'deploy'):
            raise ValueError('远程操作无效。')
        with self.lock:
            if self.operation:
                raise ValueError('已有服务器操作正在进行。')
            self.connection = validate_connection(self.connection)
            if self.closed:
                raise ValueError('中控已经关闭。')
            if self.connection['auth'] == 'password' and not self.passwords.get(self.password_id()):
                raise ValueError('请输入SSH登录密码；中控重启后需重新输入。')
            # Authentication failure must never fall back to local training.
            self.target, self.operation = 'ssh', operation
            self.status = 'deploying' if operation == 'deploy' else 'connecting'
            self.message = '正在上传中控、准备服务器并连接…' if operation == 'deploy' else '正在通过 SSH 重新连接服务器…'
            self.persist()
            threading.Thread(target=self._connect, args=(operation,), daemon=True).start()
        return self.snapshot()

    def start_wsl_test(self, value):
        from training.wsl_ssh_test import validate_distro
        if sys.platform != 'win32':
            raise ValueError('本机WSL测试入口需在Windows中启动训练中控。')
        distro = validate_distro(value.get('distro', self.manager.profile.get('distro', 'Ubuntu')))
        with self.lock:
            if self.operation or self.closed:
                raise ValueError('请等待当前服务器操作完成。')
            if self.connection['host'] and not self.connection.get('wsl_distro'):
                self.save_json(self.directory / 'remote_server_connection.json', self.connection)
            self.disconnect(update=False)
            self.target, self.operation, self.status = 'ssh', 'wsl_test', 'deploying'
            self.message = '正在准备本机WSL的SSH测试连接…'
            self.persist()
            threading.Thread(target=self._wsl_test, args=(distro,), daemon=True).start()
        return self.snapshot()

    def _wsl_test(self, distro):
        from training.wsl_ssh_test import prepare
        def report(message):
            with self.lock:
                self.message = message
        try:
            connection = validate_connection({'auth': 'key', **prepare(self.directory, self.root, distro, report)})
            with self.lock:
                if self.closed:
                    self.operation = None
                    return
                self.connection = connection
                self.persist()
                self.message = '本机WSL的SSH已准备，正在上传并连接同一套训练后端…'
            self._connect('deploy')
        except Exception as error:
            with self.lock:
                self.status, self.message, self.operation = 'failed', str(error), None

    def restore_server(self):
        with self.lock:
            if self.operation:
                raise ValueError('请等待WSL测试或服务器操作完成。')
            try:
                saved = validate_connection(json.loads((self.directory / 'remote_server_connection.json').read_text(encoding='utf-8')))
            except (OSError, ValueError):
                raise ValueError('没有可恢复的服务器连接。')
            self.disconnect(update=False)
            self.connection, self.target, self.status = saved, 'ssh', 'disconnected'
            self.info = {}
            self.message = '已恢复服务器连接；点击连接或部署，不会自动启动训练。'
            self.persist()
        return self.snapshot()

    def trust_pending_host(self, value):
        from training.password_ssh import trust_host
        with self.lock:
            pending = self.pending_host
            if self.operation or not pending or pending['connection'] != self.connection:
                raise ValueError('服务器连接已变化，请重新连接以核对指纹。')
            if value.get('fingerprint') != pending['details']['fingerprint']:
                raise ValueError('服务器指纹确认不一致。')
            trust_host(self.directory, pending['details'])
            self.pending_host = None
            return self.start(pending['operation'])

    def package(self):
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(self.root.rglob('*')):
                relative = path.relative_to(self.root)
                if not path.is_file() or any(part in ('__pycache__', '.git', 'tests') for part in relative.parts):
                    continue
                if relative.parts[0] not in ('training', 'data', 'examples', 'tools') and len(relative.parts) != 1:
                    continue
                archive.write(path, relative.as_posix())
        return output.getvalue()

    def _connect(self, operation):
        try:
            from training.official_spec import PIN
            self.disconnect(update=False)
            with self.manager.lock:
                recipe = copy.deepcopy(self.manager.recipe)
            payload = {'operation': operation, 'workspace': self.connection['workspace'], 'recipe': recipe,
                       'profile': {'mode': 'local', 'distro': 'Ubuntu', 'repo': PIN['repo']}}
            encoded = base64.b64encode(json.dumps(payload, ensure_ascii=False).encode()).decode()
            boot = (self.root / 'training/remote_server_boot.py').read_text(encoding='utf-8')
            command = 'python3 -c ' + shlex.quote(boot) + ' ' + shlex.quote(encoded)
            prerequisites = (self.root / 'training/server_prerequisites.sh').read_text(encoding='utf-8')
            prepare_command = 'bash -c ' + shlex.quote(prerequisites) + ' -- ' + shlex.quote(self.connection['workspace']) + ' ' + ('wsl' if self.connection.get('wsl_distro') else 'server')

            if self.connection['auth'] == 'password':
                from training.password_ssh import PasswordClient
                def report(message):
                    with self.lock:
                        self.message = message
                client = PasswordClient(self.directory, self.connection, self.passwords.get(self.password_id()), report)
                with self.lock:
                    if self.closed:
                        client.close()
                        return
                    self.password_client = client
                if operation == 'deploy':
                    secret = self.passwords.get(self.password_id(), '')
                    ready = client.execute(prepare_command, (secret + '\n').encode('utf-8'), timeout=900)
                    if ready.returncode:
                        raise ValueError(failure_message(ready.stderr.decode(errors='replace') or ready.stdout.decode(errors='replace')))
                result = client.execute(command, self.package() if operation == 'deploy' else b'', timeout=900)

            else:
                if operation == 'deploy':
                    ready = subprocess.run(ssh_argv(self.connection) + [self.connection['user'] + '@' + self.connection['host'], prepare_command],
                                           input=b'', stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=900,
                                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                    if ready.returncode:
                        raise ValueError(failure_message(ready.stderr.decode(errors='replace') or ready.stdout.decode(errors='replace')))
                argv = ssh_argv(self.connection) + [self.connection['user'] + '@' + self.connection['host'], command]
                result = subprocess.run(argv, input=self.package() if operation == 'deploy' else b'',
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=900,
                                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if result.returncode:
                raise ValueError(failure_message(result.stderr.decode(errors='replace')))
            line = next((line for line in result.stdout.decode(errors='replace').splitlines()
                         if line.startswith('MICRODUCK_SSH_RESULT ')), None)
            if not line:
                raise ValueError('服务器未返回训练服务信息。')
            info = json.loads(line[len('MICRODUCK_SSH_RESULT '):])
            port = info.get('port')
            if type(port) is not int or not 1024 <= port <= 65535 or info.get('release') != RELEASE:
                raise ValueError('服务器训练服务身份无效。')
            with self.lock:
                if self.closed:
                    return
                self.info = info
                local_port = self.forward(port)
            cfg = None
            last_error = None
            for attempt in range(50):
                try:
                    with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:%d/api/config' % local_port, headers={'Host':'127.0.0.1:%d' % port}), timeout=2) as response:
                        cfg = json.load(response)
                    break
                except OSError as error:
                    last_error = error
                    with self.lock:
                        if self.closed:
                            return
                        tunnel = self.tunnels[port]
                        if tunnel['process'].poll() is not None:
                            raise ValueError(failure_message(self.tunnel_error(tunnel)))
                    time.sleep(.2)
            if not cfg or cfg.get('release') != RELEASE or cfg.get('remote_workspace') != info.get('workspace'):
                raise ValueError('SSH 已连接，但训练服务没有响应或版本不符。' + (' ' + str(last_error) if last_error else ''))
            with self.lock:
                self.remote_token = cfg['token']
                self.status, self.message = 'connected', '已连接；队列、训练和模型现在使用服务器。'
            if operation == 'deploy':
                body, status, _ = self.proxy('/api/state')
                current = json.loads(body)
                if status != 200:
                    raise ValueError(current.get('error', '无法读取服务器训练状态。'))
                if not current.get('environment', {}).get('ready') and not any(j.get('op') == 'setup' and j.get('status') in ('starting','running','stopping') for j in current.get('jobs', [])):
                    # Existing WSL may already be training: inspect its installed
                    # engine, never auto-checkout/sync that live environment.
                    wsl_test = bool(self.connection.get('wsl_distro'))
                    body, status, _ = self.proxy('/api/probe' if wsl_test else '/api/setup', payload['profile'])
                    if status != 200:
                        raise ValueError(json.loads(body).get('error', '服务器环境检查启动失败。'))
                    with self.lock:
                        self.message = ('WSL的SSH已连接；正在检查已有训练环境，未启动新训练。' if wsl_test else
                                        '已连接；固定版本训练环境正在准备，请查看本页运行日志。')

        except Exception as error:
            with self.lock:
                self.disconnect(update=False)
                from training.password_ssh import UnknownHostKey
                self.status, self.message = 'failed', str(error)
                for password in self.passwords.values():
                    if password:
                        self.message = self.message.replace(password, '[已隐藏]')
                if isinstance(error, UnknownHostKey):
                    self.pending_host = {'details': error.details, 'connection': dict(self.connection), 'operation': operation}
        finally:
            with self.lock:
                self.operation = None

    @staticmethod
    def tunnel_error(tunnel):
        tunnel['error'].seek(0)
        return tunnel['error'].read().decode(errors='replace')

    def forward(self, remote_port):
        with self.lock:
            old = self.tunnels.get(remote_port)
            if old and old['process'].poll() is None:
                return old['local_port']
            if self.closed:
                raise ValueError('本地中控已关闭。')
            if old:
                old['error'].close()
            if self.connection['auth'] == 'password':
                if not self.password_client:
                    raise ValueError('密码SSH连接已断开，请重新连接。')
                process = self.password_client.forward(remote_port)
                self.tunnels[remote_port] = {'process': process, 'local_port': process.local_port, 'error': io.BytesIO()}
                return process.local_port
            local_port = available_port()
            # Separate viewer tunnels also forward WebSocket traffic unchanged.
            import tempfile
            error = tempfile.TemporaryFile()
            argv = ssh_argv(self.connection) + ['-N', '-L', '127.0.0.1:%d:127.0.0.1:%d' % (local_port, remote_port),
                                              self.connection['user'] + '@' + self.connection['host']]
            try:
                process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=error,
                                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            except Exception:
                error.close()
                raise
            self.tunnels[remote_port] = {'process': process, 'local_port': local_port, 'error': error}
            for attempt in range(30):
                if process.poll() is not None:
                    error.seek(0)
                    raise ValueError(failure_message(error.read().decode(errors='replace')))
                try:
                    with socket.create_connection(('127.0.0.1', local_port), timeout=.1):
                        return local_port
                except OSError:
                    time.sleep(.1)
            process.terminate()
            raise ValueError('SSH 隧道启动超时，请检查网络及服务器转发设置。')

    def proxy(self, path, value=None):
        state = self.snapshot()
        if state['status'] != 'connected' or not self.remote_token:
            raise ValueError(state['message'])
        port = self.tunnels[self.info['port']]['local_port']
        headers = {'X-Training-Token': self.remote_token, 'Content-Type': 'application/json', 'Host':'127.0.0.1:%d' % self.info['port']}
        data = None if value is None else json.dumps(value, ensure_ascii=False).encode()
        request = urllib.request.Request('http://127.0.0.1:%d%s' % (port, path), data=data, headers=headers)
        try:
            response = urllib.request.urlopen(request, timeout=150 if path.startswith(('/api/model', '/api/report', '/api/log')) else 20)
        except urllib.error.HTTPError as error:
            response = error
        except OSError as error:
            raise ValueError('服务器暂时无法访问；任务不会转到本机，请重新连接。') from error
        with response:
            body, status, mime = response.read(), response.code, response.headers.get_content_type()
        if mime == 'application/json':
            result = json.loads(body)
            if path.startswith('/api/state') and status == 200:
                self.rewrite_viewers(result)
                result['execution_target'] = 'ssh'
            body = json.dumps(result, ensure_ascii=False).encode()
        return body, status, mime

    def rewrite_viewers(self, value):
        if isinstance(value, dict):
            if value.get('op') and value.get('status') not in ('starting', 'running', 'stopping'):
                value.pop('viewer_url', None)
                value.pop('training_view_url', None)
            for key, child in list(value.items()):
                if key in ('viewer_url', 'training_view_url') and isinstance(child, str):
                    match = re.fullmatch(r'http://127\.0\.0\.1:(\d{4,5})', child)
                    if match and 1024 <= int(match[1]) <= 65535:
                        value[key] = 'http://127.0.0.1:%d' % self.forward(int(match[1]))
                    else:
                        value.pop(key)
                else:
                    self.rewrite_viewers(child)
        elif isinstance(value, list):
            for child in value:
                self.rewrite_viewers(child)

    def disconnect(self, update=True):
        with self.lock:
            for tunnel in self.tunnels.values():
                process = tunnel['process']
                if self.connection['auth'] == 'password' or process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=3)
                tunnel['error'].close()
            self.tunnels.clear()
            if self.password_client:
                self.password_client.close()
                self.password_client = None
            self.remote_token = ''
            if update:
                self.status, self.message = 'disconnected', 'SSH 已断开；服务器上的训练与队列继续。'
        return self.snapshot() if update else None

    def close(self):
        with self.lock:
            self.closed = True
            self.disconnect(update=False)
            self.passwords.clear()
            self.pending_host = None

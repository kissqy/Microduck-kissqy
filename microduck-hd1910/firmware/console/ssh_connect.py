"""Shared OpenSSH login settings for the existing persistent channels."""
import ipaddress
import json
import os
import re
import sys
import tempfile
import subprocess
from pathlib import Path

DEFAULT_TARGET = "radxa@192.168.6.151"
SSH_OPTIONS = [
    "BatchMode=yes", "PreferredAuthentications=publickey", "PubkeyAuthentication=yes",
    "PasswordAuthentication=no", "KbdInteractiveAuthentication=no", "NumberOfPasswordPrompts=0",
    "StrictHostKeyChecking=accept-new", "ConnectionAttempts=1", "ConnectTimeout=6",
    "ServerAliveInterval=5", "ServerAliveCountMax=2", "ControlMaster=no", "ControlPath=none",
]
_credentials = {}


def set_credential(target, credential):
    _credentials[normalize_target(target)] = credential


def login_password(target):
    credential = _credentials.get(normalize_target(target)) if target else None
    return credential.get() if credential else None


def ssh_process_options(target):
    if not target:
        return {}
    env = os.environ.copy()
    password = login_password(target)
    if password:
        helper = Path(__file__).with_name('ssh-askpass.exe' if sys.platform == 'win32' else 'ssh-askpass')
        env.update(SSH_ASKPASS=str(helper), SSH_ASKPASS_REQUIRE='force',
                   MICRODUCK_SSH_PASSWORD=password, DISPLAY=env.get('DISPLAY') or ':0')
    options = {'env': env}
    if sys.platform == 'win32':
        options['creationflags'] = subprocess.CREATE_NO_WINDOW
    return options


class SSHConnectError(RuntimeError):
    pass


def normalize_target(value, default_user="radxa"):
    if not isinstance(value, str): raise SSHConnectError("SSH 地址格式无效")
    target = value.strip()
    if "@" not in target: target = default_user + "@" + target
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}@[A-Za-z0-9][A-Za-z0-9_.-]{0,252}", target):
        raise SSHConnectError("请填写 用户名@IP 或 用户名@主机名，例如 radxa@192.168.6.151。")
    host = target.split("@", 1)[1]
    if re.fullmatch(r"[\d.]+", host):
        try: ipaddress.IPv4Address(host)
        except ValueError: raise SSHConnectError("IP 地址无效，每段应为 0～255，例如 192.168.6.151。") from None
    return target


def ssh_command(target):
    target = normalize_target(target)
    options = SSH_OPTIONS
    if login_password(target):
        options = ['BatchMode=no', 'PreferredAuthentications=password,keyboard-interactive,publickey',
                   'PubkeyAuthentication=yes', 'PasswordAuthentication=yes',
                   'KbdInteractiveAuthentication=yes', 'NumberOfPasswordPrompts=1', *SSH_OPTIONS[6:]]
    return ["ssh", "-T"] + [v for option in options for v in ("-o", option)] + [target]


def failure_message(detail, target):
    raw = str(detail).lower()
    if "remote host identification has changed" in raw or "offending" in raw and "host key" in raw:
        return "Zero 的主机身份与已保存记录不一致，请先在终端核实设备和主机指纹。"
    if "host key verification failed" in raw or "strict checking" in raw:
        return "SSH 主机记录有冲突，请核对 Zero 地址和终端中的主机记录。"
    if "permission denied" in raw or "no supported authentication" in raw or "sign_and_send_pubkey" in raw:
        return "SSH 登录失败，请检查地址、用户名和密码；免密登录可留空密码。"
    if "could not resolve" in raw or "name or service not known" in raw or "hostname contains invalid" in raw:
        return "无法解析 SSH 主机名，请检查填写的地址。"
    if "timed out" in raw or "timeout" in raw or "no route to host" in raw or "network is unreachable" in raw:
        return f"无法连接 {target}：网络不可达或连接超时，请检查 IP 和 Zero 的网络连接。"
    if "connection refused" in raw:
        return "目标拒绝 SSH 连接，请检查 IP 是否正确、Zero 的 SSH 服务是否正在运行。"
    if "python3" in raw and ("not found" in raw or "no such file" in raw):
        return "SSH 已登录，但远端没有可用的 Python 3，采集器无法启动。"
    if "connection reset" in raw or "connection closed" in raw or "broken pipe" in raw:
        return "SSH 连接在验证或采集启动期间中断，请检查 Zero 的网络连接后重试。"
    return f"SSH 连接失败：{target}，请检查系统日志中的具体错误。"


def preferences_path():
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home()/"AppData"/"Local")
    elif sys.platform == "darwin":
        base = Path.home()/"Library"/"Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home()/".config")
    return base/"MicroduckConsole"/"connection.json"


def saved_target(path=None):
    try:
        data = json.loads((path or preferences_path()).read_text(encoding="utf-8"))
        return normalize_target(data["last_target"])
    except (OSError, ValueError, TypeError, KeyError, SSHConnectError):
        return DEFAULT_TARGET


def save_target(target, path=None):
    target = normalize_target(target)
    path = path or preferences_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix="connection-", suffix=".tmp", delete=False) as f:
            temp = Path(f.name)
            json.dump({"schema": 1, "last_target": target}, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        temp.replace(path)
    finally:
        if temp is not None and temp.exists(): temp.unlink()

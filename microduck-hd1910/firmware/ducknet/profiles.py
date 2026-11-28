"""客户端本地记住的东西：每个 Wi-Fi 的密码，和每台机器人在某个网络上的固定 IP。

为什么这些必须记在客户端：

* 机器人把凭据交给 NetworkManager，``net.scan`` 只回一个 ``saved`` 布尔，而 ``net.connect``
  对非开放网络**要求带 PSK**——所以“已经输入过的密码”只有本地存一份，才能做到
  “点连接就直接连”，不用每次都弹框；
* 固定 IP 是 ``net.connect`` 的一个可选参数（机器人侧 ``configd`` 写进 NM profile），
  机器人不回读它，所以客户端得记住自己给它下发过什么。

存放位置：``$XDG_CONFIG_HOME/ducknet/profiles.json``（默认 ``~/.config/ducknet/profiles.json``），
文件权限 0600、目录 0700。**明文**，和 ``~/.netrc`` 是同一个量级：能读这个文件的只有本机
同一个用户，而他能读到的东西里本来就有 NetworkManager 的 keyfile 和系统钥匙串。要换成
系统钥匙串，替换 ``Store.password`` / ``Store.set_password`` 两个方法即可。

密码按 SSID 存（同一个密码换台机器人也一样适用），固定 IP 按「机器人 + SSID」存——同一个
网段里两台机器人拿到同一个地址，是这套东西最难查的一种故障。
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")) / "ducknet"
DEFAULT_PATH = CONFIG_DIR / "profiles.json"

VERSION = 1


class InvalidStaticIP(ValueError):
    """输入的固定 IP 配置不可用；消息直接给用户看。"""


# ── 校验与格式化（不碰文件，方便单测）──────────────────────────────────────


def parse_ipv4(text: str) -> str:
    """规范化为点分十进制，或抛 :class:`InvalidStaticIP`。

    和机器人侧 ``configd`` 的校验同一套严格度：``192.168.110.256`` 这种如果被宽容地解析成
    ``192.168.110.0``，写进 NM profile 之后就是“重启以后再也没人找得到”的机器人。
    """
    parts = str(text).strip().split(".")
    if len(parts) != 4:
        raise InvalidStaticIP(f"「{text}」不是 IPv4 地址（要 4 段，例如 192.168.110.50）")
    octets: list[int] = []
    for part in parts:
        if not part or len(part) > 3 or not part.isdigit():
            raise InvalidStaticIP(f"「{text}」不是 IPv4 地址")
        value = int(part)
        if value > 255:
            raise InvalidStaticIP(f"「{text}」里有大于 255 的段")
        octets.append(value)
    return ".".join(str(o) for o in octets)


def mask_to_prefix(text: str) -> int:
    """``255.255.255.0`` / ``24`` / ``/24`` → ``24``。

    接受掩码写法，是因为大多数人手里只有 ``255.255.255.0``，而协议要的是前缀长度。
    """
    raw = str(text).strip().lstrip("/")
    if not raw:
        raise InvalidStaticIP("子网掩码不能为空（例如 255.255.255.0 或 24）")
    if raw.isdigit():
        prefix = int(raw)
        if not 1 <= prefix <= 32:
            raise InvalidStaticIP("前缀长度要在 1–32 之间")
        return prefix

    mask = parse_ipv4(raw)
    bits = 0
    seen_zero = False
    for octet in (int(part) for part in mask.split(".")):
        for shift in range(7, -1, -1):
            if octet & (1 << shift):
                if seen_zero:
                    raise InvalidStaticIP(f"「{text}」不是连续的子网掩码")
                bits += 1
            else:
                seen_zero = True
    if bits == 0:
        raise InvalidStaticIP("子网掩码不能是 0.0.0.0")
    return bits


def build_static(
    address: str,
    mask: str,
    gateway: str = "",
    dns: str | Iterable[str] = "",
) -> dict[str, Any]:
    """三个输入框 → ``net.connect`` 的 ``ipv4`` 参数。

    ``dns`` 可以是逗号/空格分隔的字符串，也可以是列表；空表示“沿用机器人现在的”。
    """
    cfg: dict[str, Any] = {"address": parse_ipv4(address), "prefix": mask_to_prefix(mask)}
    gateway = str(gateway).strip()
    if gateway:
        cfg["gateway"] = parse_ipv4(gateway)

    if isinstance(dns, str):
        entries = [item for item in dns.replace(",", " ").split() if item]
    else:
        entries = [str(item).strip() for item in dns if str(item).strip()]
    if entries:
        cfg["dns"] = [parse_ipv4(item) for item in entries]
    return cfg


def prefix_to_mask(prefix: int) -> str:
    prefix = max(0, min(32, int(prefix)))
    bits = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF
    return ".".join(str((bits >> shift) & 0xFF) for shift in (24, 16, 8, 0))


def describe(cfg: Mapping[str, Any]) -> str:
    """一行给人看的摘要：``192.168.110.50/24（255.255.255.0）· 网关 192.168.110.1``。"""
    prefix = int(cfg.get("prefix", 24))
    text = f"{cfg.get('address', '—')}/{prefix}（{prefix_to_mask(prefix)}）"
    gateway = cfg.get("gateway")
    if gateway:
        text += f" · 网关 {gateway}"
    dns = cfg.get("dns") or []
    if dns:
        text += " · DNS " + ", ".join(str(item) for item in dns)
    return text


# ── 存储 ────────────────────────────────────────────────────────────────────


class Store:
    """``profiles.json`` 的读写。坏文件不会让 App 起不来。"""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else DEFAULT_PATH
        self._data: dict[str, Any] = {"version": VERSION, "passwords": {}, "static": {}}
        self.last_error: str | None = None
        self.load()

    # ── 文件 ────────────────────────────────────────────────────────────────

    def load(self) -> None:
        try:
            raw = json.loads(self.path.read_text("utf-8"))
        except FileNotFoundError:
            return
        except (OSError, ValueError) as exc:
            self._quarantine(f"读不出来（{exc}）")
            return
        if not isinstance(raw, dict):
            self._quarantine("顶层不是对象")
            return

        passwords = raw.get("passwords")
        if isinstance(passwords, dict):
            self._data["passwords"] = {
                str(k): str(v) for k, v in passwords.items() if isinstance(v, str) and v
            }
        static = raw.get("static")
        if isinstance(static, dict):
            for robot, networks in static.items():
                if not isinstance(networks, dict):
                    continue
                for ssid, cfg in networks.items():
                    if isinstance(cfg, dict) and cfg.get("address") and cfg.get("prefix"):
                        self._data["static"].setdefault(str(robot), {})[str(ssid)] = dict(cfg)

    def _quarantine(self, why: str) -> None:
        """坏文件改名留证，然后当作空配置——比让 App 起不来好。"""
        try:
            self.path.replace(self.path.with_suffix(".json.broken"))
        except OSError:
            pass
        self.last_error = f"配置文件{why}，已备份并重新开始"

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(self.path.parent, 0o700)
        except OSError:
            pass

        payload = json.dumps(self._data, ensure_ascii=False, indent=2, sort_keys=True)
        # 权限从一开始就是 0600、并且先写临时文件再 rename：别的进程没有一刻能读到半截密码。
        handle, tmp = tempfile.mkstemp(dir=str(self.path.parent), prefix=".profiles-")
        try:
            os.fchmod(handle, 0o600)
            with os.fdopen(handle, "w", encoding="utf-8") as fh:
                fh.write(payload + "\n")
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    # ── 密码 ────────────────────────────────────────────────────────────────

    def password(self, ssid: str) -> str | None:
        return self._data["passwords"].get(ssid)

    def set_password(self, ssid: str, psk: str) -> None:
        if not psk:
            return
        self._data["passwords"][ssid] = psk
        self.save()

    def drop_password(self, ssid: str) -> None:
        if self._data["passwords"].pop(ssid, None) is not None:
            self.save()

    # ── 固定 IP ─────────────────────────────────────────────────────────────

    def static_ipv4(self, robot: str, ssid: str) -> dict[str, Any] | None:
        cfg = self._data["static"].get(robot, {}).get(ssid)
        return dict(cfg) if cfg else None

    def set_static_ipv4(self, robot: str, ssid: str, cfg: Mapping[str, Any] | None) -> None:
        networks = self._data["static"].setdefault(robot, {})
        if cfg is None:
            if networks.pop(ssid, None) is None:
                return
        else:
            networks[ssid] = dict(cfg)
        if not networks:
            self._data["static"].pop(robot, None)
        self.save()

    def forget(self, ssid: str) -> None:
        """机器人忘掉这个网络时，本地跟着忘：留着密码只会被下一次连接当成对的重发。"""
        self._data["passwords"].pop(ssid, None)
        for networks in self._data["static"].values():
            networks.pop(ssid, None)
        self._data["static"] = {
            robot: networks for robot, networks in self._data["static"].items() if networks
        }
        self.save()

"""假机器人：在进程内实现 ``btd`` + ``configd`` 的最小行为。

两个用途：

* ``app.py --demo`` / ``acceptance.py --demo``：没有机器人也能把界面和流程走一遍；
* 单元测试：完整走一遍分帧、认证、``net.*``、``system.*`` 和错误路径，不需要蓝牙。

它刻意和真机一样按 ``Reassembler`` 分行、按 MTU 分块，所以测到的是真正会出问题的
边界，而不是一个“直接传字符串”的假接口。
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Callable

import protocol

PIN_ATTEMPTS = 3


@dataclass
class FakeNetwork:
    ssid: str
    signal: int
    security: str
    psk: str | None = None
    saved: bool = False

    def as_reply(self) -> dict[str, Any]:
        return {
            "ssid": self.ssid,
            "signal": self.signal,
            "security": self.security,
            "saved": self.saved,
        }


DEFAULT_NETWORKS = (
    FakeNetwork("Pollen", 84, "wpa_psk", "pollen123"),
    FakeNetwork("CafeGuest", 61, "open"),
    FakeNetwork("Home-5G", 72, "wpa3_sae", "home12345", saved=True),
    FakeNetwork("OldBox", 25, "wep"),
    FakeNetwork("Corp-Net", 48, "enterprise"),
)


def _check_ipv4(cfg: Any) -> str | None:
    """假机器人只做最粗的校验：形状对、地址能解析。真机的严格版在 configd 里。"""
    if not isinstance(cfg, dict):
        return "ipv4 必须是对象"
    address = cfg.get("address")
    prefix = cfg.get("prefix")
    if not isinstance(address, str) or address.count(".") != 3:
        return f"{address!r} 不是 IPv4 地址"
    if not all(part.isdigit() and int(part) <= 255 for part in address.split(".")):
        return f"{address!r} 不是 IPv4 地址"
    if not isinstance(prefix, int) or not 1 <= prefix <= 32:
        return f"前缀 {prefix!r} 不在 1-32 之间"
    return None


class FakeRobot:
    """一台只认识 ``net.*``、``system.*`` 与 ``system.authenticate`` 的机器人。"""

    def __init__(
        self,
        *,
        pin: str = protocol.DEFAULT_PIN,
        name: str = "Microduck-DEMO",
        serial: str = "demo-5b21",
        mtu: int = 185,
        scan_delay: float = 0.05,
        connect_delay: float = 0.2,
        log: Callable[[str], None] | None = None,
    ) -> None:
        self.pin = pin
        self.name = name
        self.serial = serial
        self.mtu = mtu
        self.scan_delay = scan_delay
        self.connect_delay = connect_delay
        self._log = log or (lambda _: None)
        self.networks: list[FakeNetwork] = [
            FakeNetwork(
                ssid=n.ssid,
                signal=n.signal,
                security=n.security,
                psk=n.psk,
                saved=n.saved,
            )
            for n in DEFAULT_NETWORKS
        ]
        self.authenticated = False
        self.attempts_left = PIN_ATTEMPTS
        self.state = "disconnected"
        self.ssid: str | None = None
        self.last_connect: dict[str, Any] | None = None
        self.ip4: str | None = None
        self.signal: int | None = None
        self.uptime_seconds = 3 * 86400 + 4 * 3600 + 12 * 60
        self.reboot_in_seconds: int | None = None
        self._links: list["LoopbackLink"] = []
        self._tasks: set[asyncio.Task[None]] = set()

    # ── 给客户端的一侧 ──────────────────────────────────────────────────────

    def link(self) -> "LoopbackLink":
        link = LoopbackLink(self)
        self._links.append(link)
        return link

    async def close(self) -> None:
        for link in list(self._links):
            await link.close()

    # ── 机器人侧 ────────────────────────────────────────────────────────────

    async def feed(self, chunk: bytes, link: "LoopbackLink") -> None:
        try:
            for line in link.robot_reassembler.push(chunk):
                task = asyncio.create_task(self._dispatch(line, link))
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)
        except protocol.FramingError as exc:
            self._log(f"[fake] 分帧错误：{exc}")

    async def _dispatch(self, line: str, link: "LoopbackLink") -> None:
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            await self._reply(link, None, error=(-32700, "请求不是合法 JSON"))
            return

        request_id = request.get("id")
        method = request.get("method", "")
        params = request.get("params") or {}
        self._log(f"[fake] ← {method}")

        if method == "system.authenticate":
            await self._authenticate(link, request_id, params)
            return

        if not self.authenticated:
            await self._reply(
                link,
                request_id,
                error=(
                    -32000,
                    f"{method} needs authentication first: send system.authenticate with the "
                    "robot's PIN",
                ),
            )
            return

        if method == "net.status":
            await self._reply(link, request_id, result=self._status())
        elif method == "net.scan":
            await asyncio.sleep(self.scan_delay)
            await self._reply(
                link,
                request_id,
                result={"networks": [network.as_reply() for network in self.networks]},
            )
        elif method == "net.connect":
            await self._connect(link, request_id, params)
        elif method == "net.forget":
            await self._forget(link, request_id, params)
        elif method == "system.info":
            await self._reply(link, request_id, result=self._info())
        elif method == "system.setName":
            await self._reply(link, request_id, result=self._set_name(params))
        elif method == "system.reboot":
            self.reboot_in_seconds = 3
            await self._reply(link, request_id, result={"in_seconds": 3})
        elif method == "system.logs":
            await asyncio.sleep(0.01)
            await self._reply(link, request_id, result=self._logs(params))
        else:
            await self._reply(link, request_id, error=(-32601, f"未知方法：{method}"))

    async def _authenticate(
        self, link: "LoopbackLink", request_id: Any, params: dict[str, Any]
    ) -> None:
        given = str(params.get("pin", ""))
        if given == self.pin:
            self.authenticated = True
            self.attempts_left = PIN_ATTEMPTS
            await self._reply(
                link,
                request_id,
                result={"authenticated": True, "attempts_remaining": PIN_ATTEMPTS},
            )
            return

        self.attempts_left = max(0, self.attempts_left - 1)
        await self._reply(
            link,
            request_id,
            result={"authenticated": False, "attempts_remaining": self.attempts_left},
        )
        if self.attempts_left == 0:
            await link.close()

    async def _connect(
        self, link: "LoopbackLink", request_id: Any, params: dict[str, Any]
    ) -> None:
        ssid = str(params.get("ssid", ""))
        psk = params.get("psk")
        ipv4 = params.get("ipv4")
        # 记下最后一次 net.connect 的参数，好让测试看出「有没有带密码/固定地址」。
        self.last_connect = {"ssid": ssid, "psk": psk, "ipv4": ipv4}
        network = next((n for n in self.networks if n.ssid == ssid), None)

        if network is None:
            await self._failed(link, request_id, "not_found", "没有看到这个 SSID")
            return
        if network.security in ("wep", "enterprise"):
            await self._failed(
                link,
                request_id,
                "unsupported",
                f"{network.security} 不在本 API 的支持范围",
            )
            return
        if network.security != "open" and not psk and not network.saved:
            await self._failed(link, request_id, "unsupported", "这个网络需要密码")
            return
        if network.security != "open" and psk is not None and psk != network.psk:
            await self._failed(link, request_id, "bad_key", "预共享密钥被拒绝")
            return

        if ipv4 is not None:
            # 和真机一致：坏配置在这里就被拒，不会留下一半写好的 profile。
            bad = _check_ipv4(ipv4)
            if bad is not None:
                await self._failed(link, request_id, "unsupported", bad)
                return

        self.state = "connecting"
        self.ssid = ssid
        self.ip4 = None
        await asyncio.sleep(self.connect_delay)
        self.state = "connected"
        self.ip4 = (ipv4 or {}).get("address") or "192.168.1.42"
        self.signal = network.signal
        network.saved = True
        await self._reply(
            link,
            request_id,
            result={"outcome": "connected", "ssid": ssid, "ip4": self.ip4},
        )

    async def _failed(
        self, link: "LoopbackLink", request_id: Any, reason: str, detail: str
    ) -> None:
        await self._reply(
            link,
            request_id,
            result={"outcome": "failed", "reason": reason, "detail": detail},
        )

    async def _forget(
        self, link: "LoopbackLink", request_id: Any, params: dict[str, Any]
    ) -> None:
        ssid = str(params.get("ssid", ""))
        removed = False
        for network in self.networks:
            if network.ssid == ssid and network.saved:
                network.saved = False
                removed = True
        if removed and self.ssid == ssid:
            self.state = "disconnected"
            self.ssid = None
            self.ip4 = None
            self.signal = None
        await self._reply(link, request_id, result={"removed": removed})

    def _info(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "serial": self.serial,
            "uptime_seconds": self.uptime_seconds,
            "simulated": False,
        }

    def _set_name(self, params: dict[str, Any]) -> dict[str, Any]:
        name = str(params.get("name", "")).strip()
        if name:
            self.name = name[:32]
        return {"name": self.name}

    def _logs(self, params: dict[str, Any]) -> dict[str, Any]:
        unit = str(params.get("unit", "robotd"))
        requested = int(params.get("lines", 40) or 40)
        boot = int(params.get("boot", 0) or 0)
        requested = max(1, min(requested, 500))
        catalogue = [
            f"{unit}: 控制环 50.0 Hz",
            f"{unit}: 策略 walk 已加载",
            f"{unit}: peer AA:BB:CC:DD:EE:FF read version",
            f"{unit}: authenticated (default_pin=true)",
            f"-- new {unit} process, pid 3227 --",
            f"{unit}: advertisement refreshed: {self.ip4 or '0.0.0.0'}",
        ]
        boot_note = [] if boot == 0 else [f"-- boot {boot} --"]
        lines = (boot_note + catalogue)[-requested:]
        return {"unit": unit, "lines": lines, "truncated": requested < len(catalogue)}

    def _status(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "ssid": self.ssid,
            "signal": self.signal,
            "ip4": self.ip4,
            "ip6": None,
            "mac": "02:00:00:fa:42:00",
            "iface": "wlan0",
        }

    async def _reply(
        self,
        link: "LoopbackLink",
        request_id: Any,
        *,
        result: Any = None,
        error: tuple[int, str] | None = None,
    ) -> None:
        message: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id}
        if error is not None:
            message["error"] = {"code": error[0], "message": error[1]}
        else:
            message["result"] = result
        line = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
        for chunk in protocol.chunks(line, self.mtu):
            await link.deliver(chunk)


class LoopbackLink:
    """实现了 ``session.Link`` 的进程内链路。"""

    def __init__(self, robot: FakeRobot) -> None:
        self.robot = robot
        self.robot_reassembler = protocol.Reassembler(protocol.MAX_LINE)
        self._disconnect = asyncio.Event()
        self._on_chunk: Callable[[bytes], None] | None = None
        self._closed = False

    @property
    def mtu(self) -> int:
        return self.robot.mtu

    @property
    def disconnect_event(self) -> asyncio.Event:
        return self._disconnect

    async def read_version(self) -> int:
        if self._closed:
            raise ConnectionError("链路已关闭")
        return protocol.API_VERSION

    async def start_notify(self, callback: Callable[[bytes], None]) -> None:
        self._on_chunk = callback

    async def write_line(self, line: str) -> None:
        if self._closed:
            raise ConnectionError("链路已关闭")
        for chunk in protocol.chunks(line, self.robot.mtu):
            await self.robot.feed(chunk, self)

    async def deliver(self, chunk: bytes) -> None:
        if self._closed or self._on_chunk is None:
            return
        self._on_chunk(chunk)

    async def close(self) -> None:
        self._closed = True
        self._on_chunk = None
        self._disconnect.set()

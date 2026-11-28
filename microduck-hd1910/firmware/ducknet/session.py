"""BLE 链路上的 JSON-RPC 会话：认证、发请求、等回答。

传输被抽象成 ``Link``（见 ``ble.BleLink`` 与 ``fake.LoopbackLink``），
因此这套逻辑可以在没有蓝牙的机器上完整测试。

与 ``duckctl`` 的会话流程一致：

1. 连上后先 **读** RPC 特征值——拿到 API 版本，并顺带触发配对/加密；
2. 订阅同一特征值的通知；
3. 第一件事是 ``system.authenticate`` 证明 PIN；
4. 之后才发 ``net.*`` / ``system.*``。
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Callable, Mapping, Protocol

import protocol

DEFAULT_TIMEOUT = 15.0
SLOW_TIMEOUT = 60.0
"""``net.scan`` / ``net.connect`` / ``system.logs`` 这类要等机器人的调用。"""

AUTH_TIMEOUT = 15.0

Log = Callable[[str], None]


def _no_log(_: str) -> None:
    pass


class RobotError(Exception):
    """机器人回了 JSON-RPC error（是机器人拒绝，不是链路故障）。"""

    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


def rejects_ipv4(exc: BaseException) -> bool:
    """机器人是不是"不认识 ``ipv4`` 这个参数"。

    上游 0.15.1 的 ``NetConnectParams`` 带 ``deny_unknown_fields``，多给一个字段是**整条请求**
    被拒（serde 的原话里既有 ``unknown field`` 也有 ``ipv4``），而不是忽略它。于是"给固定 IP"
    在没升级 configd 的机器人上会连 DHCP 都连不上；调用方据此退回一次不带 ``ipv4`` 的连接，
    总比让人对着一条参数错误发呆好。
    """
    if not isinstance(exc, RobotError):
        return False
    text = f"{exc.message} {exc.data}".lower()
    # 两个词都要有："unknown field `psk`" 是另一个 bug，不能也当成"这台机器人不支持固定 IP"。
    return "ipv4" in text and ("unknown" in text or "unexpected" in text)


class LinkClosed(Exception):
    """链路断了。"""


class CallTimeout(Exception):
    """等回答超时。"""


class AuthError(Exception):
    """PIN 不对。``attempts_remaining`` 是机器人给的剩余次数。"""

    def __init__(self, attempts_remaining: int | None) -> None:
        self.attempts_remaining = attempts_remaining
        if attempts_remaining == 0:
            super().__init__("PIN 错误，且已没有重试次数（机器人已关闭本次会话）")
        elif attempts_remaining is None:
            super().__init__("PIN 验证失败")
        else:
            super().__init__(f"PIN 错误，还可重试 {attempts_remaining} 次")


class Link(Protocol):
    """客户端需要的最小蓝牙接口。"""

    @property
    def mtu(self) -> int: ...

    @property
    def disconnect_event(self) -> asyncio.Event: ...

    async def read_version(self) -> int: ...

    async def start_notify(self, callback: Callable[[bytes], None]) -> None: ...

    async def write_line(self, line: str) -> None: ...

    async def close(self) -> None: ...


class RobotSession:
    """一个已连接、已认证的机器人会话。"""

    def __init__(self, link: Link, log: Log | None = None) -> None:
        self._link = link
        self._log = log or _no_log
        self._lines: asyncio.Queue[str] = asyncio.Queue()
        self._reassembler = protocol.Reassembler(protocol.MAX_REPLY_LINE)
        self._next_id = 1
        self._lock = asyncio.Lock()
        self.api_version = 0
        self.authenticated = False

    # ── 建立会话 ────────────────────────────────────────────────────────────

    @classmethod
    async def open(cls, link: Link, pin: str, log: Log | None = None) -> "RobotSession":
        session = cls(link, log)
        session.api_version = await link.read_version()
        if session.api_version and session.api_version != protocol.API_VERSION:
            session._log(
                f"提示：机器人 API v{session.api_version}，本客户端按 v{protocol.API_VERSION} 编写；"
                "如遇未知方法，请先升级客户端"
            )
        await link.start_notify(session._on_chunk)
        await session.authenticate(pin)
        return session

    @property
    def disconnect_event(self) -> asyncio.Event:
        return self._link.disconnect_event

    def _on_chunk(self, chunk: bytes) -> None:
        try:
            for line in self._reassembler.push(chunk):
                self._lines.put_nowait(line)
        except protocol.FramingError as exc:
            self._log(f"分帧错误，丢弃本次数据：{exc}")

    async def authenticate(self, pin: str) -> None:
        reply = await self._call(
            "system.authenticate", {"pin": pin}, timeout=AUTH_TIMEOUT, request_id=0
        )
        if reply.get("authenticated") is True:
            self.authenticated = True
            self._log("PIN 验证通过")
            return
        self.authenticated = False
        remaining = reply.get("attempts_remaining")
        raise AuthError(remaining if isinstance(remaining, int) else None)

    # ── 请求 ────────────────────────────────────────────────────────────────

    async def call(
        self,
        method: str,
        params: Mapping[str, Any] | None = None,
        *,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> dict[str, Any]:
        """发一个请求并等它的回答。返回 JSON-RPC 的 ``result``。"""
        async with self._lock:
            return await self._call(method, params, timeout=timeout)

    async def _call(
        self,
        method: str,
        params: Mapping[str, Any] | None,
        *,
        timeout: float,
        request_id: int | None = None,
    ) -> dict[str, Any]:
        if request_id is None:
            request_id = self._next_id
            self._next_id += 1

        line = protocol.request_line(request_id, method, params)
        self._log(f"→ {method} {json.dumps(protocol.redact(params), ensure_ascii=False)}")
        try:
            await self._link.write_line(line)
        except Exception as exc:  # bleak 的异常类型随版本变，统一转成链路错误
            raise LinkClosed(f"写入失败：{exc}") from exc

        while True:
            raw = await self._next_reply(timeout, method)
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                self._log(f"← 非 JSON 数据，已忽略：{raw[:120]}")
                continue

            if not isinstance(message, dict):
                self._log(f"← 非对象消息，已忽略：{raw[:120]}")
                continue

            reply_id = message.get("id")
            if reply_id is None:
                # 没有 id 的是进度通知（例如 update.progress），记录下来继续等。
                self._log(f"· {raw}")
                continue
            if reply_id != request_id:
                # 上一次超时请求迟到的回答，丢掉，别让它顶替本次。
                self._log(f"← 忽略过期回答 id={reply_id}")
                continue

            if message.get("error") is not None:
                error = message["error"]
                if isinstance(error, dict):
                    raise RobotError(
                        int(error.get("code", 0)),
                        str(error.get("message", "机器人拒绝了请求")),
                        error.get("data"),
                    )
                raise RobotError(0, str(error))

            result = message.get("result")
            self._log("← ok")
            return result if isinstance(result, dict) else {"value": result}

    async def _next_reply(self, timeout: float, method: str) -> str:
        if not self._lines.empty():
            return self._lines.get_nowait()

        getter = asyncio.ensure_future(self._lines.get())
        closed = asyncio.ensure_future(self._link.disconnect_event.wait())
        try:
            done, _ = await asyncio.wait(
                {getter, closed}, timeout=timeout, return_when=asyncio.FIRST_COMPLETED
            )
        finally:
            closed.cancel()
            if not getter.done():
                getter.cancel()

        if getter in done:
            return getter.result()
        if closed in done:
            if not self._lines.empty():
                return self._lines.get_nowait()
            raise LinkClosed("与机器人的连接已断开")
        raise CallTimeout(f"等待 {method} 回答超时（{timeout:.0f} 秒）")

    # ── 网络 ────────────────────────────────────────────────────────────────

    async def net_status(self) -> dict[str, Any]:
        return await self.call("net.status")

    async def net_scan(self) -> list[dict[str, Any]]:
        result = await self.call("net.scan", timeout=SLOW_TIMEOUT)
        networks = result.get("networks")
        return networks if isinstance(networks, list) else []

    async def net_connect(
        self,
        ssid: str,
        psk: str | None,
        ipv4: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """连一个网络。``ipv4`` 是 ``profiles.build_static`` 的形状，None 表示用 DHCP。"""
        params: dict[str, Any] = {"ssid": ssid}
        if psk:
            params["psk"] = psk
        if ipv4:
            params["ipv4"] = dict(ipv4)
        return await self.call("net.connect", params, timeout=SLOW_TIMEOUT)

    async def net_forget(self, ssid: str) -> bool:
        result = await self.call("net.forget", {"ssid": ssid})
        return bool(result.get("removed"))

    # ── 机器人 ──────────────────────────────────────────────────────────────

    async def system_info(self) -> dict[str, Any]:
        return await self.call("system.info")

    async def set_name(self, name: str) -> str:
        result = await self.call("system.setName", {"name": name})
        return str(result.get("name", name))

    async def reboot(self) -> int:
        result = await self.call("system.reboot")
        seconds = result.get("in_seconds")
        return int(seconds) if isinstance(seconds, (int, float)) else 0

    async def logs(self, unit: str, *, lines: int = 40, boot: int = 0) -> dict[str, Any]:
        params = {"unit": unit, "lines": lines, "boot": boot}
        return await self.call("system.logs", params, timeout=SLOW_TIMEOUT)

    async def close(self) -> None:
        await self._link.close()

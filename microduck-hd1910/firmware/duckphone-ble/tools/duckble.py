#!/usr/bin/env python3
"""Microduck 机器人的 BLE 传输层（PC 侧）。

与手机 App 说的是同一套协议，见
`firmware/docs/design/duckphone-ble-implementation.zh-CN.md` §3.1：

* Service `6f5d2a10-…`，一个 RPC 特征 `6f5d2a11-…`：写请求、订阅回答与状态；
* NDJSON 分块，按 `MTU-3` 切；连接后读一次特征取 `API_VERSION`；
* JSON-RPC 2.0：请求带 `id` 等回答，控制用不带 `id` 的通知。

这个模块只依赖 `bleak`。扫描不需要认证；连接后的任何调用（除 `hello` 与
`system.authenticate`）都需要先过 PIN。

用法（只读探针见 `probe_ble.py`，验收见 `acceptance.py`）：

    async with DuckBle(address) as duck:
        print(duck.api_version, duck.mtu)
        await duck.authenticate("000000")
        await duck.subscribe(hz=10, profile="phone")
        async for frame in duck.states():
            print(frame)
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, AsyncIterator

from bleak import BleakClient, BleakScanner

SERVICE_UUID = "6f5d2a10-3b47-4c8e-9a1f-2d7e8c4b6019"
RPC_UUID = "6f5d2a11-3b47-4c8e-9a1f-2d7e8c4b6019"

#: 广播里 IPv4 的公司 ID。`0xFFFF` 是 SIG 留给测试的，所以它不构成身份校验——
#: 真正的判别是设备广播了上面的 Service UUID。
COMPANY_ID = 0xFFFF


def _decode_version(raw: bytes | bytearray) -> int | None:
    """RPC 特征读回来的 API 版本。

    `btd` 写的是**一个字节**（`API_VERSION as u8`，API 40 就是 0x28），不是十进制文本。
    两种都认，免得以后改了编码两端对不上。
    """
    data = bytes(raw)
    if not data:
        return None
    text = data.decode("utf-8", "replace").strip()
    if text.isdigit():
        return int(text)
    return int.from_bytes(data, "big")


class RpcError(Exception):
    """服务端返回的 JSON-RPC error。"""

    def __init__(self, code: int | None, message: str):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


@dataclass
class Robot:
    address: str
    name: str = ""
    rssi: int | None = None
    ipv4: str | None = None
    extended: bool = False

    def label(self) -> str:
        address = self.ipv4 or "无 Wi-Fi"
        return f"{self.name or '(未命名)'}  {self.address}  rssi={self.rssi}  ipv4={address}"


def _address_of(manufacturer_data: dict[int, bytes]) -> tuple[str | None, bool]:
    data = manufacturer_data.get(COMPANY_ID)
    if data is None or len(data) not in (4, 5):
        return None, False
    address = ".".join(str(byte) for byte in data[:4])
    extended = len(data) == 5 and data[4] == 1
    return (None if address == "0.0.0.0" else address), extended


async def scan(timeout: float = 8.0) -> list[Robot]:
    """扫机器人，按 Service UUID 过滤。

    `btd` 会把同一份载荷发两遍（legacy + extended），所以同一个名字可能出现在两个随机
    地址上。这里按名字合并，优先保留 legacy 那一条——`duckctl` 也是这么做的。
    """
    found: dict[str, Robot] = {}
    devices = await BleakScanner.discover(timeout=timeout, return_adv=True)
    for device, adv in devices.values():
        uuids = {str(uuid).lower() for uuid in (adv.service_uuids or [])}
        if SERVICE_UUID.lower() not in uuids:
            continue
        ipv4, extended = _address_of(dict(adv.manufacturer_data or {}))
        robot = Robot(
            address=device.address,
            name=adv.local_name or device.name or "",
            rssi=getattr(adv, "rssi", None),
            ipv4=ipv4,
            extended=extended,
        )
        previous = found.get(robot.name)
        if previous is None or (previous.extended and not extended):
            found[robot.name] = robot
    return sorted(found.values(), key=lambda r: (r.name, r.address))


def choose(robots: list[Robot], address: str | None, name: str | None) -> Robot:
    """从一次扫描的结果里选一台。脚本先扫一次、再选，避免用第二个短超时重扫。"""
    if address:
        for robot in robots:
            if robot.address.lower() == address.lower():
                return robot
        raise SystemExit(f"扫到的列表里没有 {address}")
    if name:
        matches = [r for r in robots if name.lower() in r.name.lower()]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise SystemExit(f"没有名字匹配 {name!r} 的机器人")
        raise SystemExit("名字匹配到多台：" + ", ".join(r.address for r in matches))
    if len(robots) == 1:
        return robots[0]
    raise SystemExit("扫到多台，请用 --address 或 --name 指定：" + ", ".join(r.label() for r in robots))


async def pick(address: str | None, name: str | None, timeout: float) -> Robot:
    robots = await scan(timeout)
    if not robots:
        raise SystemExit("没有扫到机器人：确认它已上电、btd 正在广播、蓝牙适配器可用。")
    return choose(robots, address, name)


class DuckBle:
    """一条连接的 JSON-RPC 会话。一次只有一个请求在等回答（BLE 本来也是串行的）。"""

    def __init__(self, address: str, *, timeout: float = 10.0, debug: bool = False):
        self.address = address
        self.timeout = timeout
        self.debug = debug
        self.api_version: int | None = None
        self.mtu = 23
        self.client: BleakClient | None = None
        self.disconnected = asyncio.Event()
        self._buffer = bytearray()
        self._pending: dict[Any, asyncio.Future[dict[str, Any]]] = {}
        self._notes: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._next_id = 1
        self._send_lock = asyncio.Lock()

    # ── 会话 ────────────────────────────────────────────────────────────────

    async def connect(self) -> "DuckBle":
        self.client = BleakClient(self.address, disconnected_callback=self._on_disconnect)
        await self.client.connect()
        # **先读版本，再订阅通知。** BlueZ 会把特征读取的缓存值也当成一次
        # PropertiesChanged 推给已经订阅的客户端——先订阅就会收到一个孤零零的版本字节
        # （0x28），它和后面的 JSON 拼成一行，整条回答就废了。ducknet 也是这个顺序。
        raw = await self.client.read_gatt_char(RPC_UUID)
        self.api_version = _decode_version(raw)
        # 再拿协商后的 MTU：BlueZ 不主动告诉 bleak，必须显式 AcquireWrite 一次。
        # 失败不要紧——20 字节一包仍然能工作，只是控制帧退化成分块写。
        try:
            await self.client._backend._acquire_mtu()  # noqa: SLF001 — bleak 3.1 只有这个入口
        except Exception:
            pass
        self.mtu = getattr(self.client, "mtu_size", 23) or 23
        await self.client.start_notify(RPC_UUID, self._on_notify)
        return self

    async def __aenter__(self) -> "DuckBle":
        return await self.connect()

    async def __aexit__(self, *_exc: object) -> None:
        await self.close()

    async def close(self) -> None:
        if self.client is not None:
            try:
                if self.client.is_connected:
                    await self.client.disconnect()
            finally:
                self.client = None

    def _on_disconnect(self, _client: BleakClient) -> None:
        self.disconnected.set()
        for future in self._pending.values():
            if not future.done():
                future.set_exception(ConnectionError("BLE 链路断开"))
        self._pending.clear()

    # ── 帧 ──────────────────────────────────────────────────────────────────

    def _on_notify(self, _char: Any, data: bytearray) -> None:
        self._buffer.extend(data)
        while b"\n" in self._buffer:
            line, _, rest = self._buffer.partition(b"\n")
            self._buffer = bytearray(rest)
            if not line.strip():
                continue
            if not line.lstrip().startswith(b"{"):
                # 不是 JSON-RPC 对象：BlueZ 偶尔把特征值本身也推过来（见 connect 的注释）。
                if self.debug:
                    print(f"[ble] 丢弃非 JSON 片段：{bytes(line)[:40]!r}")
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                if self.debug:
                    print(f"[ble] 非 JSON 行：{line[:120]!r}")
                continue
            key = message.get("id")
            if key is not None and key in self._pending:
                future = self._pending.pop(key)
                if not future.done():
                    future.set_result(message)
            else:
                # 状态帧与进度通知没有 id。队列有界：一个不读状态的客户端不该把内存吃光。
                if self._notes.qsize() > 500:
                    self._notes.get_nowait()
                self._notes.put_nowait(message)

    async def _write(self, payload: bytes, *, response: bool) -> None:
        assert self.client is not None, "先 connect()"
        chunk = max(20, self.mtu - 3)
        for start in range(0, len(payload), chunk):
            await self.client.write_gatt_char(
                RPC_UUID, payload[start : start + chunk], response=response
            )

    # ── 调用 ────────────────────────────────────────────────────────────────

    async def call(self, method: str, params: dict[str, Any] | None = None,
                   timeout: float | None = None) -> Any:
        """发一个请求并等它的回答。"""
        async with self._send_lock:
            request_id = self._next_id
            self._next_id += 1
            future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
            self._pending[request_id] = future
            payload = json.dumps(
                {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}},
                separators=(",", ":"),
            ).encode() + b"\n"
            if self.debug:
                print(f"[ble] → {payload[:160]!r}")
            await self._write(payload, response=True)
            try:
                message = await asyncio.wait_for(future, timeout or self.timeout)
            finally:
                self._pending.pop(request_id, None)
        if "error" in message:
            error = message["error"]
            raise RpcError(error.get("code"), str(error.get("message", "")))
        return message.get("result")

    async def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        """发一个不带 `id` 的通知——控制用这条路径，20 Hz 也不会有回答流量。"""
        payload = json.dumps(
            {"jsonrpc": "2.0", "method": method, "params": params or {}},
            separators=(",", ":"),
        ).encode() + b"\n"
        async with self._send_lock:
            await self._write(payload, response=False)

    # ── 具体方法 ────────────────────────────────────────────────────────────

    async def authenticate(self, pin: str) -> dict[str, Any]:
        result = await self.call("system.authenticate", {"pin": pin})
        if not result.get("authenticated"):
            raise RpcError(None, f"PIN 不正确，剩余尝试 {result.get('attempts_remaining')} 次")
        return result

    async def subscribe(self, hz: int = 10, profile: str | None = "phone") -> dict[str, Any]:
        params: dict[str, Any] = {"hz": hz}
        if profile:
            params["profile"] = profile
        return await self.call("robot.subscribe", params)

    async def states(self) -> AsyncIterator[dict[str, Any]]:
        """按到达顺序产出 `robot.state` 的 params。"""
        while True:
            message = await self._notes.get()
            if message.get("method") == "robot.state":
                yield message.get("params") or {}

    async def next_note(self, timeout: float = 2.0) -> dict[str, Any] | None:
        try:
            return await asyncio.wait_for(self._notes.get(), timeout)
        except asyncio.TimeoutError:
            return None

    def frame_size_estimate(self) -> int:
        """一帧通知在空中的字节数上界：MTU-3 一包，或按 JSON 长度估算。

        btd 把回答/通知按 `min(MTU-3, 512)` 切块，所以一个 300 B 的 phone 帧在
        MTU≥64 时是一包。这里只做展示，不做分块模拟。
        """
        return max(20, self.mtu - 3)

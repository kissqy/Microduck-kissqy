"""Microduck 机器人的 BLE 线上契约（与上游 ``duck-ble`` crate 逐字节对齐）。

上游把“客户端和机器人必须一致”的三件事抽成了 ``duck-ble``：

* ``gatt``    —— 服务与特征 UUID
* ``framing`` —— NDJSON 如何切成通知、又如何拼回整行
* ``adv``     —— 广播里除名字之外带的机器人 IPv4

对应源码：

    microduck-community-kit/.../firmware/duck-ble/src/{gatt,framing,adv}.rs

本模块只做字节与算术，不 import 蓝牙栈，因此可以在没有蓝牙的机器上跑单元测试。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

# ── GATT 契约（duck-ble/src/gatt.rs）─────────────────────────────────────────

SERVICE_UUID = "6f5d2a10-3b47-4c8e-9a1f-2d7e8c4b6019"
"""机器人广播的服务 UUID，扫描时用它认出机器人。"""

RPC_UUID = "6f5d2a11-3b47-4c8e-9a1f-2d7e8c4b6019"
"""同一个特征既写又收：读一次拿到 API 版本，写 NDJSON 请求，订阅取回答。"""

# ── 广播契约（duck-ble/src/adv.rs）───────────────────────────────────────────

COMPANY_ID = 0xFFFF
"""manufacturer data 用的公司 ID；蓝牙 SIG 留给内部测试，不是身份凭证。"""

EXTENDED_MARK = 0x01
"""IPv4 之后多出来的这个字节表示“这是扩展广播那一份”。"""

# ── 分帧契约（duck-ble/src/framing.rs）───────────────────────────────────────

MAX_LINE = 8 * 1024
"""机器人愿意为一个客户端拼多长的行（安全上限，限制的是对端）。"""

MAX_REPLY_LINE = 64 * 1024
"""客户端愿意为机器人拼多长的行（机器人是我们选中的，放宽）。"""

FLOOR_MTU = 20
"""每条 BLE 链路都必须支持的 ATT 载荷。"""

MAX_ATTRIBUTE_VALUE = 512
"""GATT 特征值的上限；517 的 MTU 减 3 会超两字节，必须夹住。"""

DEFAULT_PIN = "000000"
"""出厂 PIN。真机若改过 PIN，用 ``robotctl system pin`` 查看。"""

API_VERSION = 40
"""本客户端对齐的机器人 API 版本（``duck-ipc-proto/src/lib.rs``）。"""

LOG_UNITS = (
    "robotd",
    "btd",
    "configd",
    "updaterd",
    "padd",
    "mediad",
    "tofd",
    "bluetooth",
    "NetworkManager",
)
"""``system.logs`` 可以读取的 unit（机器人侧是固定白名单）。"""


def notification_payload(mtu: int) -> int:
    """这条链路一次通知能承载多少字节（``mtu - 3``，夹在 20..512）。"""
    return max(FLOOR_MTU, min(int(mtu) - 3, MAX_ATTRIBUTE_VALUE))


def chunks(line: str, mtu: int) -> list[bytes]:
    """把一整行切成可写进特征值的块，换行符在最后一块里。

    与上游 ``framing::chunks`` 一致：调用方不需要另加“消息结束”标记，
    对端拼到换行就是一条完整消息。
    """
    payload = max(int(mtu), FLOOR_MTU)
    data = line.encode("utf-8")
    if not data.endswith(b"\n"):
        data += b"\n"
    return [data[i : i + payload] for i in range(0, len(data), payload)]


class FramingError(Exception):
    """对端的字节无法按 NDJSON 分帧。"""


class Reassembler:
    """把一条特征值的多个分块拼回整行。"""

    def __init__(self, limit: int = MAX_LINE) -> None:
        self._limit = limit
        self._buf = bytearray()

    @property
    def pending(self) -> int:
        """还没等到换行的字节数。"""
        return len(self._buf)

    def push(self, chunk: bytes) -> list[str]:
        """喂一块；返回这一块凑齐的所有整行（不含换行）。"""
        if len(self._buf) + len(chunk) > self._limit:
            self._buf.clear()
            raise FramingError(f"{self._limit} 字节内没有换行")
        self._buf.extend(chunk)

        lines: list[str] = []
        while True:
            at = self._buf.find(b"\n")
            if at < 0:
                break
            raw = bytes(self._buf[:at])
            del self._buf[: at + 1]
            if raw.endswith(b"\r"):
                raw = raw[:-1]
            if not raw:
                continue
            try:
                lines.append(raw.decode("utf-8"))
            except UnicodeDecodeError as exc:
                self._buf.clear()
                raise FramingError("不是合法的 UTF-8") from exc
        return lines


# ── 广播解析 ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RobotAdvertisement:
    """扫描到的一次广播，已按契约解析。"""

    address: str
    name: str | None
    ipv4: str | None
    has_address_field: bool
    extended: bool
    rssi: int | None

    @property
    def label(self) -> str:
        return self.name or self.address


def address_bytes(manufacturer_data: Mapping[int, bytes]) -> bytes | None:
    """取 manufacturer data 里的四个 IPv4 字节；长度不对就不认。"""
    raw = manufacturer_data.get(COMPANY_ID)
    if raw is None or len(raw) not in (4, 5):
        return None
    if len(raw) == 5 and raw[4] != EXTENDED_MARK:
        return None
    return bytes(raw[:4])


def has_address_field(manufacturer_data: Mapping[int, bytes]) -> bool:
    """广播里有没有 IPv4 字段（0.0.0.0 也算有）。"""
    return address_bytes(manufacturer_data) is not None


def is_extended(manufacturer_data: Mapping[int, bytes]) -> bool:
    raw = manufacturer_data.get(COMPANY_ID)
    return raw is not None and len(raw) == 5 and raw[4] == EXTENDED_MARK


def advertised_ipv4(manufacturer_data: Mapping[int, bytes]) -> str | None:
    raw = address_bytes(manufacturer_data)
    if raw is None or raw == b"\x00\x00\x00\x00":
        return None
    return ".".join(str(byte) for byte in raw)


def service_uuid_present(service_uuids: Iterable[str]) -> bool:
    return any(str(uuid).lower() == SERVICE_UUID for uuid in service_uuids)


def parse_advertisement(
    *,
    address: str,
    local_name: str | None,
    manufacturer_data: Mapping[int, bytes],
    service_uuids: Iterable[str],
    rssi: int | None,
) -> RobotAdvertisement | None:
    """把一次扫描结果转成机器人广播；看起来不是机器人就返回 ``None``。

    判据与 ``duckctl`` 相同：服务 UUID 是优化，manufacturer 字段是补充。
    机器人被别的主机连接后可能只报出其中一种，所以两者有一个就算候选；
    真正的身份确认发生在连上之后（特征值存不存在）。
    """
    looks_like_robot = service_uuid_present(service_uuids) or has_address_field(
        manufacturer_data
    )
    if not looks_like_robot:
        return None
    return RobotAdvertisement(
        address=address,
        name=local_name,
        ipv4=advertised_ipv4(manufacturer_data),
        has_address_field=has_address_field(manufacturer_data),
        extended=is_extended(manufacturer_data),
        rssi=rssi,
    )


# ── JSON-RPC（architecture.md §2.2：所有传输都是 NDJSON）────────────────────


def request_line(request_id: int, method: str, params: Mapping[str, Any] | None = None) -> str:
    """构造一行 JSON-RPC 请求（不含换行，交给 ``chunks`` 补）。"""
    message = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": dict(params or {}),
    }
    return json.dumps(message, ensure_ascii=False, separators=(",", ":"))


def redact(params: Mapping[str, Any] | None) -> dict[str, Any]:
    """日志用：把密码/PIN 换成占位符，值本身绝不进日志。"""
    safe = dict(params or {})
    for key in ("psk", "pin", "passphrase", "password"):
        if key in safe:
            safe[key] = "<已隐藏>"
    return safe


def format_uptime(seconds: int | float | None) -> str:
    """把 ``system.info`` 的秒数变成 ``3 天 04:12`` 这种可读形式。"""
    if seconds is None:
        return "—"
    total = max(0, int(seconds))
    days, rest = divmod(total, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    if days:
        return f"{days} 天 {hours:02d}:{minutes:02d}"
    return f"{hours:02d}:{minutes:02d}"

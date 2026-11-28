"""bleak 后端：扫描机器人、建立链路、按 MTU 分块收发。

除 ``bleak`` 外没有别的依赖；配对代理见 ``agent.py``。所有回调都在同一个后台
事件循环里被调用，界面负责把它们转回 Tk 主线程。
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable

import protocol

SCAN_TIME = 8.0
CONNECT_TIMEOUT = 20.0
READ_TIMEOUT = 20.0
PAIR_TIMEOUT = 25.0

Log = Callable[[str], None]


def _no_log(_: str) -> None:
    pass


class BleError(Exception):
    """连接/读取失败，消息已经是可以直接显示的说明。"""


@dataclass
class Found:
    """扫描结果：广播内容 + 用来连接的 bleak 设备对象。

    同一台机器人会同时发传统与扩展两份广播，来自两个不同的随机地址。**哪一份能连上
    取决于主机控制器**：上游 `duckctl` 记录的是 Linux/Intel 上从扩展那份连，实测这块
    Intel 网卡两者都会间歇性地以 HCI `0x3E (Connection Failed to be Established)` 失败。
    所以这里保留**两个候选**并按偏好排序，连接失败就换下一个重试。
    """

    adv: protocol.RobotAdvertisement
    devices: list[Any]
    is_robot: bool = True

    @property
    def device(self) -> Any:
        """首选连接对象（扩展广播优先）。"""
        return self.devices[0] if self.devices else None


def describe_ble_error(exc: BaseException) -> str:
    """把 bleak 的异常翻译成用户能照做的中文。"""
    text = str(exc)
    lowered = text.lower()
    try:
        from bleak.exc import (
            BleakBluetoothNotAvailableError,
            BleakBluetoothNotAvailableReason,
            BleakDeviceNotFoundError,
        )
    except ImportError:
        return text

    if isinstance(exc, BleakBluetoothNotAvailableError):
        reason = getattr(exc, "reason", None)
        if reason == BleakBluetoothNotAvailableReason.POWERED_OFF:
            return "蓝牙适配器已关闭：先执行 rfkill unblock bluetooth，再执行 bluetoothctl power on"
        return "没有可用的蓝牙适配器：检查 rfkill list 与 bluetoothctl list"
    if isinstance(exc, BleakDeviceNotFoundError):
        return "找不到机器人：可能不在范围内，或已被手机 App / 另一台电脑连着"
    if "insufficient authentication" in lowered or "insufficient encryption" in lowered:
        return "蓝牙链路未加密：配对没有完成。可先在 bluetoothctl 里 pair/trust 一次再试"
    if "not permitted" in lowered or "not authorized" in lowered:
        return "蓝牙权限不足：确认当前用户在 bluetooth 组，且 BlueZ 的 D-Bus 策略允许访问"
    if "in progress" in lowered:
        return "上一条蓝牙操作还没结束，等一两秒再试"
    if "already exists" in lowered or "already paired" in lowered:
        return "已经配对过，但链路仍未加密：先在 bluetoothctl 里 remove 掉旧配对再试"
    return text


async def _stop_discovery() -> None:
    """让 BlueZ 停掉当前的发现过程（尽力而为）。

    连续 start/stop 扫描时，BlueZ 偶尔会有一段时间对 `StartDiscovery` 回
    `org.bluez.Error.InProgress`——此时先 `StopDiscovery` 一下就能回到可用状态。
    """
    try:
        from dbus_fast import BusType, Message
        from dbus_fast.aio import MessageBus
    except ImportError:
        return
    bus = None
    try:
        bus = await asyncio.wait_for(MessageBus(bus_type=BusType.SYSTEM).connect(), 2.0)
        await asyncio.wait_for(
            bus.call(
                Message(
                    destination="org.bluez",
                    path="/org/bluez/hci0",
                    interface="org.bluez.Adapter1",
                    member="StopDiscovery",
                )
            ),
            2.0,
        )
    except Exception:
        pass
    finally:
        if bus is not None:
            try:
                bus.disconnect()
            except Exception:
                pass


async def scan(
    duration: float = SCAN_TIME,
    *,
    include_all: bool = False,
    on_update: Callable[[list["Found"]], None] | None = None,
) -> list["Found"]:
    """扫描 ``duration`` 秒，返回去重后的设备列表。

    同一台机器人会同时发传统广播与扩展广播，两者来自不同的随机地址。上游
    ``duckctl`` 的结论是：Linux 上从传统广播发起连接常常失败，要从扩展广播连。
    所以按（名字, IPv4）合并，并优先保留扩展那一份。
    """
    from bleak import BleakScanner

    found: dict[tuple[Any, ...], Found] = {}
    last_publish = 0.0

    def publish(force: bool = False) -> None:
        nonlocal last_publish
        now = time.monotonic()
        if not force and now - last_publish < 0.2:
            return
        last_publish = now
        if on_update is not None:
            on_update(_sorted(found.values()))

    def on_advertisement(device: Any, advertisement: Any) -> None:
        parsed = protocol.parse_advertisement(
            address=device.address,
            local_name=advertisement.local_name,
            manufacturer_data=advertisement.manufacturer_data,
            service_uuids=advertisement.service_uuids,
            rssi=advertisement.rssi,
        )
        is_robot = parsed is not None
        if parsed is None:
            if not include_all:
                return
            parsed = protocol.RobotAdvertisement(
                address=device.address,
                name=advertisement.local_name,
                ipv4=None,
                has_address_field=False,
                extended=False,
                rssi=advertisement.rssi,
            )

        if not is_robot:
            key: tuple[Any, ...] = ("addr", parsed.address)
        elif parsed.name:
            key = (parsed.name, parsed.ipv4)
        else:
            key = ("addr", parsed.address)

        previous = found.get(key)
        if previous is None:
            found[key] = Found(adv=parsed, devices=[device], is_robot=is_robot)
        else:
            # 同一台机器人的另一份广播：加到候选列表里（扩展优先），而不是替换掉——
            # 两份随机地址里总有一份能连上，丢掉就等于丢掉一次重试机会。
            devices = [d for d in previous.devices if d.address != device.address]
            if parsed.extended or not previous.adv.extended:
                devices.insert(0, device)
                adv = parsed
            else:
                devices.append(device)
                adv = previous.adv
            found[key] = Found(adv=adv, devices=devices, is_robot=is_robot or previous.is_robot)
        publish()

    for round_ in range(2):
        try:
            async with BleakScanner(
                detection_callback=on_advertisement, scanning_mode="active"
            ):
                await asyncio.sleep(duration)
            break
        except Exception as exc:
            if round_ == 0 and "in progress" in str(exc).lower():
                await _stop_discovery()
                await asyncio.sleep(1.5)
                continue
            raise BleError(describe_ble_error(exc)) from exc

    publish(force=True)
    return _sorted(found.values())


def _sorted(items: Iterable[Found]) -> list[Found]:
    return sorted(items, key=lambda f: (not f.is_robot, (f.adv.label or "").casefold()))


CONNECT_ATTEMPTS = 8
"""连接尝试次数：HCI 0x3E 是间歇性的，且会成串出现（几十秒内每次都在建立后掉线）。

实测同一位置：有时第一次就成功，有时连续失败半分钟。8 次 × ~1.5 秒的窗口覆盖了
这种成串失败，又不会让一次误操作卡上一分钟以上。
"""

RETRY_PAUSE = 1.5
"""两次尝试之间的间隔。控制器需要一点时间清理失败的连接。"""

BUSY_PAUSE = 3.0
"""BlueZ 还在处理上一条命令时的等待。

`org.bluez.Error.InProgress` 说明上一条 connect/scan 还没收尾。这时立刻再发一条只会
再失败一次，而且重扫也会跟着失败——所以遇到它要停久一点，并且**跳过重扫**。"""

BUSY_HINTS = ("in progress", "busy", "上一条蓝牙操作")


class BleLink:
    """一条到机器人的 BLE 链路。"""

    def __init__(self, device: Any, log: Log | None = None) -> None:
        self._device = device
        self._log = log or _no_log
        self._client: Any = None
        self._notify: Callable[[bytes], None] | None = None
        self._disconnect = asyncio.Event()
        self._paired = False
        self._closed = False

    # ── session.Link ────────────────────────────────────────────────────────

    @property
    def mtu(self) -> int:
        client = self._client
        mtu = getattr(client, "mtu_size", None) if client is not None else None
        return int(mtu) if mtu else 23

    @property
    def disconnect_event(self) -> asyncio.Event:
        return self._disconnect

    async def connect(self) -> None:
        from bleak import BleakClient

        # 用地址字符串而不是 BLEDevice：蓝牙扫描一结束，BlueZ 就可能把那个临时设备对象
        # 回收掉，拿着旧对象连接会得到 "device 'dev_…' not found"。地址是公开且稳定的。
        target = getattr(self._device, "address", self._device)
        self._client = BleakClient(
            target,
            disconnected_callback=self._on_disconnect,
            timeout=CONNECT_TIMEOUT,
        )
        try:
            await self._client.connect()
        except Exception as exc:
            raise BleError(describe_ble_error(exc)) from exc
        self._log(f"已连接 {target}")

    async def read_version(self) -> int:
        value = await self._read_rpc()
        return value[0] if value else 0

    async def start_notify(self, callback: Callable[[bytes], None]) -> None:
        self._notify = callback

        def handler(_characteristic: Any, data: bytearray) -> None:
            if self._notify is not None:
                self._notify(bytes(data))

        try:
            await self._client.start_notify(protocol.RPC_UUID, handler)
        except Exception as exc:
            raise BleError(describe_ble_error(exc)) from exc

    async def write_line(self, line: str) -> None:
        if self._closed:
            raise BleError("链路已关闭")
        payload = protocol.notification_payload(self.mtu)
        try:
            await self._write_chunks(protocol.chunks(line, payload))
        except Exception as exc:
            # 第一次写入才暴露“需要加密”也很常见：btd 可以只要求写加密。
            if self._paired:
                raise BleError(describe_ble_error(exc)) from exc
            await self._pair()
            try:
                await self._write_chunks(protocol.chunks(line, payload))
            except Exception as again:
                raise BleError(describe_ble_error(again)) from again

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._notify = None
        self._disconnect.set()
        client, self._client = self._client, None
        if client is not None:
            try:
                await client.stop_notify(protocol.RPC_UUID)
            except Exception:
                pass
            try:
                await asyncio.wait_for(client.disconnect(), timeout=5.0)
            except Exception:
                pass

    # ── 内部 ────────────────────────────────────────────────────────────────

    async def _write_chunks(self, parts: list[bytes]) -> None:
        for chunk in parts:
            await self._client.write_gatt_char(protocol.RPC_UUID, chunk, response=False)

    async def _read_rpc(self) -> bytes:
        try:
            value = await asyncio.wait_for(
                self._client.read_gatt_char(protocol.RPC_UUID), timeout=READ_TIMEOUT
            )
            return bytes(value)
        except Exception as first:
            self._log(f"读版本号失败（{describe_ble_error(first)}），尝试配对…")
            await self._pair()
            last: Exception = first
            for _ in range(3):
                await asyncio.sleep(0.5)
                try:
                    value = await asyncio.wait_for(
                        self._client.read_gatt_char(protocol.RPC_UUID),
                        timeout=READ_TIMEOUT,
                    )
                    return bytes(value)
                except Exception as exc:
                    last = exc
            raise BleError(describe_ble_error(last)) from last

    async def _pair(self) -> None:
        if self._client is None:
            return
        try:
            await asyncio.wait_for(self._client.pair(), timeout=PAIR_TIMEOUT)
            self._paired = True
            self._log("蓝牙配对完成")
        except Exception as exc:
            self._log(f"按需配对没有成功：{describe_ble_error(exc)}")

    def _on_disconnect(self, _client: Any) -> None:
        if not self._closed:
            self._log("与机器人的连接已断开")
        self._disconnect.set()


async def robot_already_connected(
    adv: protocol.RobotAdvertisement,
) -> bool:
    """这台机器人现在是不是已经有一条 BLE 连接（可能是别的客户端）。

    BlueZ 对"已经连着"的对端再发 Connect 会回 `org.bluez.Error.InProgress`，和"控制器正忙"
    是同一个错误码。分清楚值得一次 D-Bus 查询：前者要告诉用户"先断开另一个客户端"。

    **按名字/服务 UUID 找，而不是按地址**：机器人同时用公开地址和随机地址广播，
    连着的那份和刚扫到的那份地址经常不一样。
    """
    try:
        from dbus_fast import BusType, Message, MessageType
        from dbus_fast.aio import MessageBus
    except ImportError:
        return False

    bus = None
    try:
        bus = await asyncio.wait_for(MessageBus(bus_type=BusType.SYSTEM).connect(), 2.0)
        reply = await asyncio.wait_for(
            bus.call(
                Message(
                    destination="org.bluez",
                    path="/",
                    interface="org.freedesktop.DBus.ObjectManager",
                    member="GetManagedObjects",
                )
            ),
            2.5,
        )
        if reply.message_type == MessageType.ERROR or not reply.body:
            return False
        objects = reply.body[0]
        for path, interfaces in objects.items():
            device = interfaces.get("org.bluez.Device1")
            if device is None:
                continue
            connected = getattr(device.get("Connected"), "value", False)
            if not connected:
                continue
            name = str(getattr(device.get("Name"), "value", "") or "")
            aliases = str(getattr(device.get("Alias"), "value", "") or "")
            uuids = [
                str(getattr(u, "value", u))
                for u in (getattr(device.get("UUIDs"), "value", []) or [])
            ]
            if adv.name:
                # 有名字就按名字认，免得把另一台连着的东西（比如耳机）也算进来。
                if adv.name in (name, aliases):
                    return True
            elif protocol.SERVICE_UUID in [u.lower() for u in uuids]:
                return True
        return False
    except Exception:
        return False
    finally:
        if bus is not None:
            try:
                bus.disconnect()
            except Exception:
                pass


def _is_busy(exc: BaseException | None) -> bool:
    """BlueZ 正在忙（`InProgress`），不是链路问题也不是机器人问题。"""
    if exc is None:
        return False
    text = str(exc).lower()
    return any(hint in text for hint in BUSY_HINTS)


def _describe(exc: BaseException | None) -> str:
    """异常的中文/英文消息；有些 bleak 异常``str()``是空的，退回类名。"""
    if exc is None:
        return "未知原因"
    text = str(exc).strip()
    return text or type(exc).__name__


def _matches(
    adv: protocol.RobotAdvertisement, device: Any, advertisement: Any
) -> bool:
    """扫描到的这台是不是我们要连的那台机器人。"""
    parsed = protocol.parse_advertisement(
        address=device.address,
        local_name=advertisement.local_name,
        manufacturer_data=advertisement.manufacturer_data,
        service_uuids=advertisement.service_uuids,
        rssi=advertisement.rssi,
    )
    if parsed is not None:
        return True
    # 广播里既没有服务 UUID 也没有我们的 manufacturer 字段时（被别的主机连着、
    # 或刚重启还没挂上 GATT），退回按名字比较。
    if adv.name and advertisement.local_name:
        return adv.name == advertisement.local_name
    return device.address == adv.address


async def _find_device(
    adv: protocol.RobotAdvertisement, seconds: float, log: Log
) -> Any | None:
    """扫出一台机器人并**在返回前关掉扫描**。

    BlueZ 在发现过程进行中会以 `org.bluez.Error.InProgress` 拒绝 `Device1.Connect()`,
    所以扫描必须停掉再连；设备对象在 StopDiscovery 之后仍然可用。
    """
    from bleak import BleakScanner

    # 注意：``find_device_by_filter`` 是**类方法**，它自己会开一个扫描会话。早先写成
    # ``async with BleakScanner(...)`` 再调用实例方法，等于同时开了两个发现过程，BlueZ
    # 直接回 InProgress——那次“怎么都连不上”就是它。
    for round_ in range(3):
        try:
            return await BleakScanner.find_device_by_filter(
                lambda d, a: _matches(adv, d, a),
                timeout=seconds,
                scanning_mode="active",
            )
        except Exception as exc:
            if round_ < 2 and "in progress" in str(exc).lower():
                log("扫描被上一次操作挡住，停掉发现过程后重试")
                await _stop_discovery()
                await asyncio.sleep(2.0)
                continue
            raise BleError(describe_ble_error(exc)) from exc
    return None


async def open_session(
    adv: protocol.RobotAdvertisement,
    pin: str,
    log: Log | None = None,
    *,
    attempts: int = CONNECT_ATTEMPTS,
    scan_time: float = 6.0,
) -> tuple["BleLink", Any]:
    """扫描 → 连接 → 认证，整段一起重试。

    重试必须包住整段：HCI `0x3E` 常常在第一次 ATT 写之后才把链路拆掉，而失败的连接会
    让机器人换一个随机地址重新广播，所以每一轮都要重新扫。
    """
    import session as sessions  # 延迟导入：session 不依赖 bleak，避免环

    log = log or _no_log
    last: BaseException | None = None

    for attempt in range(1, attempts + 1):
        link: "BleLink | None" = None
        try:
            device = await _find_device(adv, scan_time, log)
            if device is None:
                raise BleError(f"{scan_time:.0f} 秒内没有看到这台机器人在广播")
            log(f"连接尝试 {attempt}/{attempts} · {getattr(device, 'address', device)}")
            link = BleLink(device, log=log)
            await link.connect()
            session = await sessions.RobotSession.open(link, pin, log=log)
            return link, session
        except BaseException as exc:  # 连接/认证任何一步失败都重来
            last = exc
            if link is not None:
                await link.close()
            log(f"这次没连上（{_describe(exc)}）")

        if _is_busy(last):
            # 已经连着的时候控制器会一直回 InProgress，重试没有意义。
            if await robot_already_connected(adv):
                raise BleError(
                    "这台机器人已经有一个客户端连着（另一个 ducknet 窗口、手机 App，或 "
                    "bluetoothctl）。BLE 一次只服务一个中心——先断开那边，再连。"
                ) from last

        if attempt < attempts:
            await asyncio.sleep(BUSY_PAUSE if _is_busy(last) else RETRY_PAUSE)

    if _is_busy(last):
        raise BleError(
            f"连接失败 {attempts} 轮：蓝牙控制器一直在忙（{_describe(last)}）。"
            "通常是另一处也在用它——关掉另一个 ducknet / 手机 App / bluetoothctl 会话再试。"
        ) from last
    raise BleError(
        f"连接失败 {attempts} 轮：{_describe(last)}。"
        "蓝牙链路的 0x3E 通常是间歇性的——靠近机器人、关掉其它连着它的 App/电脑后再试。"
    ) from last

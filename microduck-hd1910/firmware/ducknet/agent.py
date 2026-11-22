"""BlueZ 配对代理。

机器人那一侧是 just-works 配对：链路会加密，但不在链路层认人；真正的认证是
链路之上的 ``system.authenticate``（见上游 ``btd/src/pairing.rs``）。

客户端这一侧的坑是：BlueZ 发起配对时需要有一个已注册的 agent，而一个从终端
启动的 Python 程序默认没有。不注册的话，机器人要求加密时会以
``No agent available`` 失败。所以这里注册一个 ``NoInputNoOutput`` 代理——
just-works 不需要任何交互，注册本身就是为了让 BlueZ 有地方回调。

失败是允许的：``btd`` 默认并不要求加密链路，读版本号能直接成功；桌面上也可
能已经有 ``bluetoothctl`` 之类的 agent。失败只记日志，连接流程继续。
"""

from __future__ import annotations

import asyncio
import os
from typing import Callable

AGENT_MANAGER = "org.bluez.AgentManager1"
BLUEZ = "org.bluez"
BLUEZ_PATH = "/org/bluez"


def _no_log(_: str) -> None:
    pass


# BlueZ 的 D-Bus 签名用 ``typing.Annotated`` 声明。这些别名必须是**模块级**的：
# 本文件开了 ``from __future__ import annotations``，dbus-fast 会在**模块**命名空间里
# 求值注解字符串，函数内的局部别名它看不到。
# 没装 dbus-fast 时退化成普通类型——那种情况下 ``start()`` 会先返回 False，类不会注册。
try:
    from typing import Annotated

    from dbus_fast.annotations import DBusSignature

    DevicePath = Annotated[str, DBusSignature("o")]
    Passkey = Annotated[str, DBusSignature("s")]
    PasskeyNumber = Annotated[int, DBusSignature("u")]
    Entered = Annotated[int, DBusSignature("q")]
    ServiceUuid = Annotated[str, DBusSignature("s")]
except ImportError:  # pragma: no cover - 只在没装 blueprint 依赖的机器上
    DevicePath = str  # type: ignore[misc,assignment]
    Passkey = str  # type: ignore[misc,assignment]
    PasskeyNumber = int  # type: ignore[misc,assignment]
    Entered = int  # type: ignore[misc,assignment]
    ServiceUuid = str  # type: ignore[misc,assignment]


class BluezPairingAgent:
    def __init__(self, log: Callable[[str], None] | None = None) -> None:
        self._log = log or _no_log
        self._bus = None
        self._agent = None
        self._path = f"/org/ducknet/agent/{os.getpid()}"
        self.registered = False

    async def start(self) -> bool:
        """注册代理；失败返回 False，不抛异常。"""
        try:
            from dbus_fast import BusType, Message
            from dbus_fast.aio import MessageBus
            from dbus_fast.service import ServiceInterface, method
        except ImportError:
            self._log("未安装 dbus-fast，跳过配对代理（bleak 会带上它）")
            return False

        class _Agent(ServiceInterface):
            """just-works 代理。

            BlueZ 的签名用 ``typing.Annotated`` 声明，而不是字符串注解——字符串注解会
            被静态检查当成未定义名字，而 ``Annotated`` 在 dbus-fast ≥ 4 里是官方的写法。
            没有返回值的成员**不要**写 ``-> None``：dbus-fast 会把注解当 D-Bus 签名解析，
            ``None`` 会让它在导入时就报错。
            """

            def __init__(self, log: Callable[[str], None]) -> None:
                super().__init__("org.bluez.Agent1")
                self._log = log

            @method()
            def Release(self):
                pass

            @method()
            def RequestPinCode(self, device: DevicePath) -> Passkey:
                # 机器人不会走这条路（它没有键盘也没有屏幕），留着以免 BlueZ 卡住。
                return "000000"

            @method()
            def DisplayPinCode(self, device: DevicePath, pincode: Passkey):
                pass

            @method()
            def RequestPasskey(self, device: DevicePath) -> PasskeyNumber:
                return 0

            @method()
            def DisplayPasskey(self, device: DevicePath, passkey: PasskeyNumber, entered: Entered):
                pass

            @method()
            def RequestConfirmation(self, device: DevicePath, passkey: PasskeyNumber):
                # just-works：直接同意。
                pass

            @method()
            def RequestAuthorization(self, device: DevicePath):
                pass

            @method()
            def AuthorizeService(self, device: DevicePath, uuid: ServiceUuid):
                pass

            @method()
            def Cancel(self):
                pass

        try:
            self._bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
            self._agent = _Agent(self._log)
            self._bus.export(self._path, self._agent)

            await self._call(
                Message(
                    destination=BLUEZ,
                    path=BLUEZ_PATH,
                    interface=AGENT_MANAGER,
                    member="RegisterAgent",
                    signature="os",
                    body=[self._path, "NoInputNoOutput"],
                )
            )
            self.registered = True
            self._log("已注册 BlueZ 配对代理（NoInputNoOutput）")

            # 让 BlueZ 优先问我们；桌面已有默认 agent 时会失败，不影响使用。
            try:
                await self._call(
                    Message(
                        destination=BLUEZ,
                        path=BLUEZ_PATH,
                        interface=AGENT_MANAGER,
                        member="RequestDefaultAgent",
                        signature="o",
                        body=[self._path],
                    )
                )
            except Exception:
                pass
            return True
        except Exception as exc:
            self._log(f"注册 BlueZ 配对代理失败（继续连接）：{exc}")
            await self.stop()
            return False

    async def _call(self, message) -> None:
        from dbus_fast import MessageType

        reply = await self._bus.call(message)
        if reply.message_type == MessageType.ERROR:
            raise RuntimeError(f"{reply.error_name}: {reply.body}")

    async def stop(self) -> None:
        if self._bus is None:
            return
        try:
            if self.registered:
                from dbus_fast import Message

                try:
                    await asyncio.wait_for(
                        self._call(
                            Message(
                                destination=BLUEZ,
                                path=BLUEZ_PATH,
                                interface=AGENT_MANAGER,
                                member="UnregisterAgent",
                                signature="o",
                                body=[self._path],
                            )
                        ),
                        timeout=2.0,
                    )
                except Exception:
                    pass
            try:
                self._bus.unexport(self._path, self._agent)
            except Exception:
                pass
            self._bus.disconnect()
        finally:
            self._bus = None
            self._agent = None
            self.registered = False

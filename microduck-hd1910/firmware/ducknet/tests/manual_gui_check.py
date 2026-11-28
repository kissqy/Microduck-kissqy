#!/usr/bin/env python3
"""手动联调：把“真机分支”接在假机器人上，不需要蓝牙。

``app.py --demo`` 走的是另一条分支（直接构造 ``FakeRobot``）。这个脚本故意把
``ble.BleLink`` / ``ble.scan`` / ``BluezPairingAgent`` 换成假的，让界面跑真正的
“真机”代码路径：agent 启动 → 连接 → 认证 → 刷新 → 扫描网络 → 加入网络 → 改名 → 读日志 → 重启。

需要图形环境（会真的开一个窗口）：

    DISPLAY=:0 python3 tests/manual_gui_check.py

退出码 0 表示每一步都符合预期。
"""

from __future__ import annotations

import sys
import tempfile
import tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app  # noqa: E402
import ble  # noqa: E402
import profiles  # noqa: E402
import protocol  # noqa: E402
import session as sessions  # noqa: E402
from fake import FakeRobot  # noqa: E402

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(("  OK   " if condition else "  FAIL ") + name + (f" — {detail}" if detail else ""))
    if not condition:
        failures.append(name)


def main() -> int:
    if not app.tk.TkVersion:
        print("没有 Tk")
        return 2

    robot = FakeRobot(scan_delay=0.0, connect_delay=0.0, mtu=23)

    class FakeBleLink:
        """替换 ``ble.BleLink``：底层接假机器人的 LoopbackLink。"""

        def __init__(self, device, log=None) -> None:
            self._inner = robot.link()

        @property
        def mtu(self) -> int:
            return self._inner.mtu

        @property
        def disconnect_event(self):
            return self._inner.disconnect_event

        async def connect(self) -> None:
            return None

        async def read_version(self) -> int:
            return await self._inner.read_version()

        async def start_notify(self, callback) -> None:
            await self._inner.start_notify(callback)

        async def write_line(self, line: str) -> None:
            await self._inner.write_line(line)

        async def close(self) -> None:
            await self._inner.close()

    class FakeAgent:
        def __init__(self, log=None) -> None:
            self.log = log

        async def start(self) -> bool:
            return True

        async def stop(self) -> None:
            return None

    async def fake_scan(duration=1.0, *, include_all=False, on_update=None):
        adv = protocol.RobotAdvertisement(
            address="AA:BB:CC:DD:EE:FF",
            name="Microduck-FAKE",
            ipv4="192.168.1.42",
            has_address_field=True,
            extended=True,
            rssi=-55,
        )
        found = [ble.Found(adv=adv, devices=[object()], is_robot=True)]
        if on_update is not None:
            on_update(found)
        return found

    async def fake_open_session(adv, pin, log=None, *, attempts=3, scan_time=0.0):
        link = FakeBleLink(object())
        session = await sessions.RobotSession.open(link, pin, log=log)
        return link, session

    ble.scan = fake_scan
    ble.open_session = fake_open_session
    app.BLEAK_AVAILABLE = True

    import agent as agent_module

    agent_module.BluezPairingAgent = FakeAgent

    # 控制台地址点一下就开浏览器，这里只记下它要开的 URL，不真开。
    opened: list[str] = []
    app.webbrowser.open = lambda url, *a, **k: opened.append(url) or True

    root = tk.Tk()
    gui = app.App(root, demo=False, scan_seconds=0.5)
    gui.hide_banner()

    # 用临时文件当本地记忆，别碰用户真实的 ~/.config/ducknet。
    tmp = tempfile.TemporaryDirectory()
    gui.profiles = profiles.Store(Path(tmp.name) / "profiles.json")
    # 已经记住过 Pollen 的密码——这正是"第二次点连接不该再问密码"的场景。
    gui.profiles.set_password("Pollen", "pollen123")

    def click_confirm() -> None:
        for window in root.winfo_children():
            if isinstance(window, tk.Toplevel):
                for frame in window.winfo_children():
                    for sub in frame.winfo_children():
                        if sub.winfo_class() in ("TFrame", "Frame"):
                            for button in sub.winfo_children():
                                if button.winfo_class() == "TButton" and button.cget("text") == "重启":
                                    button.invoke()
                                    return

    def step_scan() -> None:
        check("扫描列出机器人", len(gui._robots) == 1, str(len(gui._robots)))
        gui.robots_tree.selection_set("0")

    def step_connect() -> None:
        gui.on_connect()

    def step_after_connect() -> None:
        check("会话已建立", gui._session is not None)
        check(
            "API 版本",
            gui._session is not None and gui._session.api_version == protocol.API_VERSION,
        )
        check("身份已加载", gui.robot_vars["name"].get() == "Microduck-DEMO")
        check("Wi-Fi 列表已扫描", len(gui.wifi_tree.get_children()) == 5)
        check("未联网时显示“未接入网络”", gui.status_ssid.cget("text") == "未接入网络")

    def step_join() -> None:
        gui.wifi_tree.selection_set("1")  # CafeGuest，开放网络
        gui.on_connect_network()

    def step_after_join() -> None:
        check("加入后 IPv4", gui.status_vars["ip4"].get() == "192.168.1.42")
        check("加入后 SSID", gui.status_ssid.cget("text") == "CafeGuest")
        check("成功横幅", "已连接 CafeGuest" in gui.banner_text.cget("text"))
        gui.new_name.set("Ducky")
        gui.on_rename()

    def step_after_rename() -> None:
        check("改名后身份", gui.robot_vars["name"].get() == "Ducky")
        values = gui.robots_tree.item("0", "values")
        check("改名后列表", bool(values) and values[0] == "Ducky", str(values))
        gui.log_unit.set("btd")
        gui.log_lines.set("5")
        gui.on_read_logs()

    def step_after_logs() -> None:
        body = gui.device_log.get("1.0", "end").strip().splitlines()
        check("日志有内容", len(body) >= 2, f"{len(body)} 行")
        check("截断提示", "截断" in gui.logs_note.cget("text"))
        root.after(150, click_confirm)
        gui.on_reboot()

    def step_after_reboot() -> None:
        check("重启提示", "将在约 3 秒后重启" in gui.banner_text.cget("text"))
        # 下面三项都要在一个已连接的会话里做；重启提示不解除会话。
        gui.wifi_tree.selection_set("0")  # Pollen，加密网络
        gui.static_enabled.set(True)
        gui._sync_static_entries()
        gui.static_address.set("192.168.110.50")
        gui.static_mask.set("255.255.255.0")
        gui.static_gateway.set("192.168.110.1")
        gui.static_dns.set("192.168.110.1")
        gui.on_save_static()

    def step_after_save_static() -> None:
        stored = gui.profiles.static_ipv4(gui._robot_key, "Pollen")
        check(
            "固定 IP 已记住",
            stored
            == {
                "address": "192.168.110.50",
                "prefix": 24,
                "gateway": "192.168.110.1",
                "dns": ["192.168.110.1"],
            },
            str(stored),
        )
        check("固定 IP 提示已更新", "固定 192.168.110.50" in gui.static_hint.cget("text"))
        # 已经记住密码：这一步不该弹框，直接连。
        gui.on_connect_network()

    def step_after_pinned_join() -> None:
        sent = robot.last_connect or {}
        check("沿用记住的密码", sent.get("psk") == "pollen123", str(sent.get("psk")))
        check(
            "固定 IP 随连接下发",
            sent.get("ipv4", {}).get("address") == "192.168.110.50",
            str(sent.get("ipv4")),
        )
        check("用的是固定地址", gui.status_vars["ip4"].get() == "192.168.110.50")
        check("状态页标出地址来源", "固定" in gui.status_source.cget("text"))
        check(
            "控制台地址可点",
            gui.console_label.cget("cursor") == "hand2"
            and gui._console_url == "http://192.168.110.50:8001",
            f"{gui.console_label.cget('cursor')} {gui._console_url}",
        )
        gui.console_label.event_generate("<Button-1>")
        root.update()
        check("点击打开浏览器", opened == ["http://192.168.110.50:8001"], str(opened))

    def finish() -> None:
        root.destroy()

    schedule = [
        (600, step_scan),
        (1000, step_connect),
        (2600, step_after_connect),
        (3200, step_join),
        (4600, step_after_join),
        (5800, step_after_rename),
        (7000, step_after_logs),
        (8200, step_after_reboot),
        (9000, step_after_save_static),
        (10200, step_after_pinned_join),
        (11000, finish),
    ]
    for delay, fn in schedule:
        root.after(delay, fn)
    root.mainloop()

    print()
    tmp.cleanup()
    if failures:
        print(f"失败 {len(failures)} 项：{', '.join(failures)}")
        return 1
    print("真机分支联调全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())

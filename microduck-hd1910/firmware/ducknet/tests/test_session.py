"""会话层测试：认证、net.*、system.*、错误与超时。

跑在进程内假机器人上，走的路径和真机一样：请求按 MTU 分块、机器人按换行重组、
回答再分块回来。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import protocol  # noqa: E402
import session as sessions  # noqa: E402
from fake import FakeRobot  # noqa: E402


class SessionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.robot = FakeRobot(scan_delay=0.0, connect_delay=0.0)
        self.link = self.robot.link()
        self.session = await sessions.RobotSession.open(self.link, protocol.DEFAULT_PIN)

    async def asyncTearDown(self) -> None:
        await self.session.close()
        await self.robot.close()

    async def test_reading_the_version_and_authenticating(self) -> None:
        self.assertEqual(self.session.api_version, protocol.API_VERSION)
        self.assertTrue(self.session.authenticated)

    async def test_status_after_connect(self) -> None:
        status = await self.session.net_status()
        self.assertEqual(status["state"], "disconnected")
        self.assertEqual(status["iface"], "wlan0")

        result = await self.session.net_connect("Pollen", "pollen123")
        self.assertEqual(result["outcome"], "connected")
        self.assertEqual(result["ip4"], "192.168.1.42")

        status = await self.session.net_status()
        self.assertEqual(status["state"], "connected")
        self.assertEqual(status["ssid"], "Pollen")

    async def test_scan_lists_security_and_saved(self) -> None:
        networks = await self.session.net_scan()
        by_ssid = {network["ssid"]: network for network in networks}
        self.assertEqual(by_ssid["CafeGuest"]["security"], "open")
        self.assertEqual(by_ssid["Pollen"]["security"], "wpa_psk")
        self.assertTrue(by_ssid["Home-5G"]["saved"])

    async def test_wrong_password_is_bad_key(self) -> None:
        result = await self.session.net_connect("Pollen", "nope")
        self.assertEqual(result["outcome"], "failed")
        self.assertEqual(result["reason"], "bad_key")

    async def test_a_saved_profile_connects_without_a_password(self) -> None:
        result = await self.session.net_connect("Home-5G", None)
        self.assertEqual(result["outcome"], "connected")

    async def test_open_network_needs_no_password(self) -> None:
        result = await self.session.net_connect("CafeGuest", None)
        self.assertEqual(result["outcome"], "connected")

    async def test_a_fixed_address_is_sent_and_used(self) -> None:
        cfg = {
            "address": "192.168.110.50",
            "prefix": 24,
            "gateway": "192.168.110.1",
            "dns": ["192.168.110.1"],
        }
        result = await self.session.net_connect("Pollen", "pollen123", cfg)
        self.assertEqual(result["outcome"], "connected")
        # 机器人回了被钉住的地址，而不是 DHCP 的地址——客户端据此能看出配置生效了。
        self.assertEqual(result["ip4"], "192.168.110.50")
        # 参数原样过线：字段名是 configd 的契约（ssid/psk/ipv4/address/prefix/gateway/dns）。
        self.assertEqual(self.robot.last_connect["ipv4"], cfg)

    async def test_an_unusable_fixed_address_is_refused(self) -> None:
        result = await self.session.net_connect(
            "Pollen", "pollen123", {"address": "192.168.110.256", "prefix": 24}
        )
        self.assertEqual(result["outcome"], "failed")
        self.assertEqual(result["reason"], "unsupported")

    async def test_dhcp_stays_the_default_when_no_address_is_given(self) -> None:
        await self.session.net_connect("Pollen", "pollen123")
        self.assertIsNone(self.robot.last_connect["ipv4"])

    async def test_unsupported_security_is_reported(self) -> None:
        for ssid in ("OldBox", "Corp-Net"):
            result = await self.session.net_connect(ssid, "whatever")
            self.assertEqual(result["outcome"], "failed")
            self.assertEqual(result["reason"], "unsupported")

    async def test_forget_reports_whether_a_profile_existed(self) -> None:
        self.assertTrue(await self.session.net_forget("Home-5G"))
        self.assertFalse(await self.session.net_forget("Home-5G"))
        self.assertFalse(await self.session.net_forget("Nowhere"))

    async def test_system_info(self) -> None:
        info = await self.session.system_info()
        self.assertEqual(info["name"], "Microduck-DEMO")
        self.assertEqual(info["serial"], "demo-5b21")
        self.assertGreater(info["uptime_seconds"], 0)
        self.assertFalse(info["simulated"])

    async def test_rename_returns_the_stored_name(self) -> None:
        stored = await self.session.set_name("Ducky")
        self.assertEqual(stored, "Ducky")
        info = await self.session.system_info()
        self.assertEqual(info["name"], "Ducky")

    async def test_reboot_reports_delay(self) -> None:
        seconds = await self.session.reboot()
        self.assertEqual(seconds, 3)

    async def test_logs_are_bounded_and_flagged(self) -> None:
        result = await self.session.logs("btd", lines=2)
        self.assertEqual(result["unit"], "btd")
        self.assertEqual(len(result["lines"]), 2)
        self.assertTrue(result["truncated"])
        self.assertTrue(all("btd" in line or line.startswith("--") for line in result["lines"]))

    async def test_unknown_method_is_a_robot_error(self) -> None:
        with self.assertRaises(sessions.RobotError) as caught:
            await self.session.call("robot.move")
        self.assertEqual(caught.exception.code, -32601)

    async def test_calls_work_at_the_ble_floor_mtu(self) -> None:
        robot = FakeRobot(mtu=20, scan_delay=0.0, connect_delay=0.0)
        session = await sessions.RobotSession.open(robot.link(), protocol.DEFAULT_PIN)
        try:
            result = await session.net_connect("Pollen", "pollen123")
            self.assertEqual(result["outcome"], "connected")
            networks = await session.net_scan()
            self.assertEqual(len(networks), 5)
            info = await session.system_info()
            self.assertEqual(info["name"], "Microduck-DEMO")
        finally:
            await session.close()
            await robot.close()

    async def test_closing_the_link_fails_the_next_call(self) -> None:
        await self.link.close()
        with self.assertRaises(sessions.LinkClosed):
            await self.session.net_status()


class OlderRobotTests(unittest.TestCase):
    """老 configd 不认识 ``ipv4``：App 要能认出这一点并退回 DHCP，而不是当成密码错。"""

    def test_an_unknown_field_is_recognised(self) -> None:
        # 上游 `NetConnectParams` 的 `deny_unknown_fields` 拒绝整条请求，消息取决于 serde 版本。
        for message in (
            "invalid params: unknown field `ipv4`, expected `ssid` or `psk`",
            "unexpected field, ipv4",
        ):
            self.assertTrue(
                sessions.rejects_ipv4(sessions.RobotError(-32602, message)),
                message,
            )

    def test_other_errors_are_not_mistaken_for_it(self) -> None:
        for exc in (
            sessions.RobotError(-32000, "network is unreachable"),
            sessions.RobotError(-32602, "unknown field `psk`"),
            # 只有字段名、没有"多出来的"语气时不算：那是别的参数错误。
            sessions.RobotError(-32602, "ipv4 is invalid"),
            sessions.CallTimeout("no answer"),
            ValueError("ipv4"),
        ):
            self.assertFalse(sessions.rejects_ipv4(exc), repr(exc))


class AuthenticationTests(unittest.IsolatedAsyncioTestCase):
    async def test_wrong_pin_reports_attempts_left(self) -> None:
        robot = FakeRobot(scan_delay=0.0, connect_delay=0.0)
        link = robot.link()
        with self.assertRaises(sessions.AuthError) as caught:
            await sessions.RobotSession.open(link, "999999")
        self.assertEqual(caught.exception.attempts_remaining, 2)
        await link.close()
        await robot.close()

    async def test_three_wrong_pins_end_the_session(self) -> None:
        robot = FakeRobot(scan_delay=0.0, connect_delay=0.0)
        with self.assertRaises(sessions.AuthError) as caught:
            await sessions.RobotSession.open(robot.link(), "999999")
        self.assertEqual(caught.exception.attempts_remaining, 2)

        with self.assertRaises(sessions.AuthError):
            await sessions.RobotSession.open(robot.link(), "999999")

        # 第三次机器人仍会先回包（attempts_remaining=0），然后关闭会话。
        with self.assertRaises(sessions.AuthError) as last:
            await sessions.RobotSession.open(robot.link(), "999999")
        self.assertEqual(last.exception.attempts_remaining, 0)
        await robot.close()

    async def test_unauthenticated_call_is_refused(self) -> None:
        robot = FakeRobot(scan_delay=0.0, connect_delay=0.0)
        link = robot.link()
        session = sessions.RobotSession(link)
        session.api_version = await link.read_version()
        await link.start_notify(session._on_chunk)

        with self.assertRaises(sessions.RobotError) as caught:
            await session.net_status()
        self.assertIn("authentication first", caught.exception.message)

        await session.close()
        await robot.close()


class SilenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_a_mute_robot_times_out(self) -> None:
        class MuteAfterAuth(FakeRobot):
            async def _dispatch(self, line: str, link) -> None:  # noqa: ANN001
                if '"system.authenticate"' in line:
                    await super()._dispatch(line, link)

        robot = MuteAfterAuth()
        link = robot.link()
        session = await sessions.RobotSession.open(link, protocol.DEFAULT_PIN)
        with self.assertRaises(sessions.CallTimeout):
            await session.call("net.status", timeout=0.05)
        await session.close()
        await robot.close()


if __name__ == "__main__":
    unittest.main()

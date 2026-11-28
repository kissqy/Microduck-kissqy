"""本地记住的东西：密码与固定 IP。

这两样都必须记在客户端——``net.scan`` 只回 ``saved`` 布尔，``net.connect`` 却要求带密码、
并且不回读 ``ipv4``——所以这里测的是「会不会记、记不记得住、记错了会不会出事」。
"""

from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import profiles  # noqa: E402


class ValidationTests(unittest.TestCase):
    def test_addresses_are_strict(self) -> None:
        self.assertEqual(profiles.parse_ipv4(" 192.168.110.50 "), "192.168.110.50")
        self.assertEqual(profiles.parse_ipv4("192.168.110.050"), "192.168.110.50")
        for bad in ("192.168.110", "192.168.110.256", "192.168..1", "a.b.c.d", ""):
            with self.assertRaises(profiles.InvalidStaticIP, msg=bad):
                profiles.parse_ipv4(bad)

    def test_a_mask_may_be_written_either_way(self) -> None:
        self.assertEqual(profiles.mask_to_prefix("255.255.255.0"), 24)
        self.assertEqual(profiles.mask_to_prefix("255.255.255.252"), 30)
        self.assertEqual(profiles.mask_to_prefix("24"), 24)
        self.assertEqual(profiles.mask_to_prefix("/16"), 16)
        # 非连续的掩码不是掩码：NM 会接受它，然后把地址算错。
        for bad in ("255.0.255.0", "0.0.0.0", "33", "", "255.255.255.1"):
            with self.assertRaises(profiles.InvalidStaticIP, msg=bad):
                profiles.mask_to_prefix(bad)

    def test_prefix_and_mask_round_trip(self) -> None:
        for prefix in (1, 8, 16, 23, 24, 30, 32):
            self.assertEqual(profiles.mask_to_prefix(profiles.prefix_to_mask(prefix)), prefix)

    def test_building_a_configuration(self) -> None:
        cfg = profiles.build_static("192.168.110.50", "255.255.255.0", "192.168.110.1", "1.1.1.1, 8.8.8.8")
        self.assertEqual(
            cfg,
            {
                "address": "192.168.110.50",
                "prefix": 24,
                "gateway": "192.168.110.1",
                "dns": ["1.1.1.1", "8.8.8.8"],
            },
        )
        # 网关与 DNS 都可以不填：一条没有路由器的链路上，只有一个地址也是合法的。
        bare = profiles.build_static("10.0.0.2", "8")
        self.assertEqual(bare, {"address": "10.0.0.2", "prefix": 8})

        with self.assertRaises(profiles.InvalidStaticIP):
            profiles.build_static("10.0.0.2", "24", "10.0.0")


class StoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "ducknet" / "profiles.json"

    def tearDown(self) -> None:
        self.dir.cleanup()

    def test_a_password_survives_a_restart(self) -> None:
        store = profiles.Store(self.path)
        self.assertIsNone(store.password("Pollen"))
        store.set_password("Pollen", "pollen123")

        again = profiles.Store(self.path)
        self.assertEqual(again.password("Pollen"), "pollen123")
        again.drop_password("Pollen")
        self.assertIsNone(profiles.Store(self.path).password("Pollen"))

    def test_the_file_is_private(self) -> None:
        store = profiles.Store(self.path)
        store.set_password("Pollen", "pollen123")
        # 明文密码放在这里，权限就是唯一的屏障——和 ~/.netrc 同一个量级。
        mode = stat.S_IMODE(os.stat(self.path).st_mode)
        self.assertEqual(mode, 0o600, oct(mode))
        self.assertEqual(stat.S_IMODE(os.stat(self.path.parent).st_mode), 0o700)

    def test_a_fixed_address_is_per_robot_and_per_ssid(self) -> None:
        store = profiles.Store(self.path)
        cfg = profiles.build_static("192.168.110.50", "24", "192.168.110.1")
        store.set_static_ipv4("duck-0001", "Pollen", cfg)

        self.assertEqual(profiles.Store(self.path).static_ipv4("duck-0001", "Pollen"), cfg)
        # 同一个网段里两台机器人拿到同一个地址，是最难查的一种故障。
        self.assertIsNone(store.static_ipv4("duck-0002", "Pollen"))
        self.assertIsNone(store.static_ipv4("duck-0001", "CafeGuest"))

        store.set_static_ipv4("duck-0001", "Pollen", None)
        self.assertIsNone(profiles.Store(self.path).static_ipv4("duck-0001", "Pollen"))

    def test_forgetting_clears_the_password_and_the_address(self) -> None:
        store = profiles.Store(self.path)
        store.set_password("Pollen", "pollen123")
        store.set_static_ipv4("duck-0001", "Pollen", profiles.build_static("10.0.0.2", "24"))

        store.forget("Pollen")
        again = profiles.Store(self.path)
        # 留着密码，下次点连接就会把一个机器人已经不接受的密码再发一遍。
        self.assertIsNone(again.password("Pollen"))
        self.assertIsNone(again.static_ipv4("duck-0001", "Pollen"))

    def test_a_broken_file_is_backed_up_rather_than_fatal(self) -> None:
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{ not json", "utf-8")

        store = profiles.Store(self.path)
        self.assertIsNone(store.password("Pollen"))
        self.assertTrue((self.path.parent / "profiles.json.broken").exists())
        self.assertIn("备份", store.last_error or "")
        # 之后照常能写。
        store.set_password("Pollen", "x")
        self.assertEqual(json.loads(self.path.read_text("utf-8"))["passwords"]["Pollen"], "x")


if __name__ == "__main__":
    unittest.main()

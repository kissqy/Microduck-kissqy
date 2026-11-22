"""线上契约的单元测试：分帧、广播、请求行。

对应上游 ``duck-ble`` 的同名测试。这里没有蓝牙，也不需要机器人。
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import protocol  # noqa: E402


class FramingTests(unittest.TestCase):
    def test_a_line_survives_every_mtu(self) -> None:
        line = json.dumps(
            {"jsonrpc": "2.0", "id": 7, "result": {"pad": "y" * 300}},
            separators=(",", ":"),
        )
        for mtu in (20, 23, 100, 185, 512, 4096):
            reassembler = protocol.Reassembler(protocol.MAX_REPLY_LINE)
            got: list[str] = []
            for chunk in protocol.chunks(line, mtu):
                self.assertLessEqual(len(chunk), max(mtu, 20))
                got.extend(reassembler.push(chunk))
            self.assertEqual(got, [line], f"mtu {mtu}")
            self.assertEqual(reassembler.pending, 0)

    def test_several_lines_in_one_chunk(self) -> None:
        reassembler = protocol.Reassembler()
        self.assertEqual(len(reassembler.push(b'{"a":1}\n{"b":2}\n')), 2)

    def test_a_partial_trailing_line_is_retained(self) -> None:
        reassembler = protocol.Reassembler()
        self.assertEqual(reassembler.push(b'{"a":1}\n{"b":'), ['{"a":1}'])
        self.assertEqual(reassembler.push(b'2}\n'), ['{"b":2}'])

    def test_blank_lines_are_skipped_and_crlf_tolerated(self) -> None:
        reassembler = protocol.Reassembler()
        self.assertEqual(reassembler.push(b'\n\r\n{"a":1}\r\n'), ['{"a":1}'])

    def test_a_line_without_a_newline_is_refused_at_the_cap(self) -> None:
        reassembler = protocol.Reassembler(limit=64)
        with self.assertRaises(protocol.FramingError):
            reassembler.push(b"x" * 65)
        self.assertEqual(reassembler.pending, 0)

    def test_invalid_utf8_is_refused(self) -> None:
        reassembler = protocol.Reassembler()
        with self.assertRaises(protocol.FramingError):
            reassembler.push(b"\xff\xfe\n")

    def test_chunks_end_with_exactly_one_newline(self) -> None:
        for line in ('{"a":1}', '{"a":1}\n'):
            flat = b"".join(protocol.chunks(line, 512))
            self.assertEqual(flat.count(b"\n"), 1, line)
            self.assertTrue(flat.endswith(b"\n"))

    def test_a_degenerate_mtu_falls_back_to_the_floor(self) -> None:
        self.assertEqual(len(protocol.chunks("z" * 40, 0)), 3)

    def test_notification_payload_clamps_both_ends(self) -> None:
        self.assertEqual(protocol.notification_payload(0), protocol.FLOOR_MTU)
        self.assertEqual(protocol.notification_payload(23), 20)
        self.assertEqual(protocol.notification_payload(185), 182)
        self.assertEqual(protocol.notification_payload(517), protocol.MAX_ATTRIBUTE_VALUE)
        self.assertEqual(protocol.notification_payload(65535), protocol.MAX_ATTRIBUTE_VALUE)


class AdvertisementTests(unittest.TestCase):
    def test_an_address_round_trips(self) -> None:
        adv = protocol.parse_advertisement(
            address="AA:BB:CC:DD:EE:FF",
            local_name="duck-5b21",
            manufacturer_data={protocol.COMPANY_ID: bytes([192, 168, 1, 42])},
            service_uuids=[protocol.SERVICE_UUID],
            rssi=-60,
        )
        assert adv is not None
        self.assertEqual(adv.ipv4, "192.168.1.42")
        self.assertTrue(adv.has_address_field)
        self.assertFalse(adv.extended)
        self.assertEqual(adv.label, "duck-5b21")

    def test_no_wifi_is_a_present_field_and_no_address(self) -> None:
        adv = protocol.parse_advertisement(
            address="AA:BB:CC:DD:EE:FF",
            local_name="duck",
            manufacturer_data={protocol.COMPANY_ID: bytes(4)},
            service_uuids=[],
            rssi=-70,
        )
        assert adv is not None
        self.assertIsNone(adv.ipv4)
        self.assertTrue(adv.has_address_field)

    def test_the_extended_twin_is_marked(self) -> None:
        adv = protocol.parse_advertisement(
            address="11:22:33:44:55:66",
            local_name="duck",
            manufacturer_data={
                protocol.COMPANY_ID: bytes([10, 0, 0, 7, protocol.EXTENDED_MARK])
            },
            service_uuids=[],
            rssi=-50,
        )
        assert adv is not None
        self.assertTrue(adv.extended)
        self.assertEqual(adv.ipv4, "10.0.0.7")

    def test_a_payload_of_the_wrong_length_is_not_an_address(self) -> None:
        for length in (0, 1, 3, 6, 16):
            data = {protocol.COMPANY_ID: bytes(length)}
            self.assertIsNone(protocol.advertised_ipv4(data), f"{length} bytes")
            self.assertFalse(protocol.has_address_field(data), f"{length} bytes")
        five = {protocol.COMPANY_ID: bytes([1, 2, 3, 4, 9])}
        self.assertIsNone(protocol.advertised_ipv4(five))
        self.assertFalse(protocol.has_address_field(five))
        self.assertFalse(protocol.is_extended(five))

    def test_a_foreign_device_is_not_a_robot(self) -> None:
        adv = protocol.parse_advertisement(
            address="AA:BB:CC:DD:EE:FF",
            local_name="headphones",
            manufacturer_data={76: b"\x02\x15"},  # Apple
            service_uuids=["0000180f-0000-1000-8000-00805f9b34fb"],
            rssi=-80,
        )
        self.assertIsNone(adv)

    def test_the_advertised_payload_fits_a_legacy_advertisement(self) -> None:
        flags = 3
        service_uuid = 2 + 16
        manufacturer_header = 2 + 2
        spent = flags + service_uuid + manufacturer_header + 4
        self.assertLessEqual(spent, 31)


class RequestLineTests(unittest.TestCase):
    def test_request_line_is_compact_ndjson(self) -> None:
        line = protocol.request_line(5, "net.connect", {"ssid": "Pollen", "psk": "secret"})
        message = json.loads(line)
        self.assertEqual(message["jsonrpc"], "2.0")
        self.assertEqual(message["id"], 5)
        self.assertEqual(message["method"], "net.connect")
        self.assertEqual(message["params"]["ssid"], "Pollen")
        self.assertNotIn("\n", line)

    def test_redaction_hides_secrets(self) -> None:
        safe = protocol.redact({"ssid": "Pollen", "psk": "secret", "pin": "000000"})
        self.assertEqual(safe["ssid"], "Pollen")
        self.assertEqual(safe["psk"], "<已隐藏>")
        self.assertEqual(safe["pin"], "<已隐藏>")

    def test_uptime_is_readable(self) -> None:
        self.assertEqual(protocol.format_uptime(None), "—")
        self.assertEqual(protocol.format_uptime(0), "00:00")
        self.assertEqual(protocol.format_uptime(3 * 86400 + 4 * 3600 + 12 * 60), "3 天 04:12")
        self.assertEqual(protocol.format_uptime(2 * 3600 + 5 * 60), "02:05")


if __name__ == "__main__":
    unittest.main()

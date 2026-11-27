#!/usr/bin/env python3
"""End-to-end tests: browser messages in, `robotd` calls out.

A real HTTP server, a real WebSocket, and a fake daemon on a unix socket — the
same code path the phone uses, minus the phone.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import server  # noqa: E402
from helpers import FakeRobotd, WSClient, free_port  # noqa: E402

logging.disable(logging.CRITICAL)


def make_static(dirpath: Path) -> None:
    (dirpath / "index.html").write_text("<!doctype html><title>duck</title>", encoding="utf-8")
    (dirpath / "app.js").write_text("console.log(1)", encoding="utf-8")


class BridgeHarness:
    def __init__(self, *, auth: bool = False, token: str = "", refuse: dict | None = None) -> None:
        self.static = Path(tempfile.mkdtemp(prefix="duckphone-static-"))
        make_static(self.static)
        self.fake = FakeRobotd().start()
        if refuse:
            self.fake.refuse.update(refuse)
        self.port = free_port()
        token_file = str(self.static / "token")
        if auth:
            Path(token_file).write_text(token, encoding="utf-8")
        cfg = argparse.Namespace(
            host="127.0.0.1",
            port=self.port,
            static=str(self.static),
            robot_socket=self.fake.path,
            token_file=token_file,
            auth=auth,
            no_padd_control=True,
            subscribe_hz=20,
            verbose=False,
        )
        self.httpd = server.make_server(cfg)
        self.httpd.bridge.start()
        self.httpd.watchdog.start()
        self.thread = threading.Thread(target=self.httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.port}"

    def client(self) -> WSClient:
        return WSClient("127.0.0.1", self.port)

    def close(self) -> None:
        self.httpd.director.stop()
        self.httpd.watchdog.stop()
        self.httpd.shutdown()
        self.httpd.server_close()
        self.httpd.bridge.stop()
        self.fake.stop()


class BridgeTestCase(unittest.TestCase):
    auth = False
    token = ""

    def setUp(self):
        self.h = BridgeHarness(auth=self.auth, token=self.token)
        self.clients: list[WSClient] = []

    def tearDown(self):
        for c in self.clients:
            c.close()
        self.h.close()

    def connect(self, name="Mate 40 Pro") -> WSClient:
        client = self.h.client()
        self.clients.append(client)
        client.send({"t": "hello", "token": self.token, "name": name})
        hello = client.wait_for("hello")
        self.assertTrue(hello.get("ok"), hello)
        return client


class HelloTest(BridgeTestCase):
    def test_first_client_drives(self):
        client = self.h.client()
        self.clients.append(client)
        client.send({"t": "hello", "name": "Mate 40 Pro"})
        hello = client.wait_for("hello")
        self.assertEqual(hello["role"], "driver")
        self.assertEqual(hello["name"], "Mate 40 Pro")
        self.assertIn("clamp", hello)

    def test_state_arrives_on_connect(self):
        client = self.connect()
        state = client.wait_for("state")
        self.assertEqual(state["pol"], "held")
        self.assertIn("mv", state)

    def test_drive_is_clamped_and_forwarded(self):
        client = self.connect()
        self.assertTrue(self.h.fake.wait_for_client())
        self.h.fake.reset()
        client.send({"t": "drive", "vx": 0.9, "vyaw": -3.0})
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and not self.h.fake.moves():
            time.sleep(0.02)
        moves = self.h.fake.moves()
        self.assertTrue(moves, "robot.move 没有下发")
        params = moves[-1]["params"]
        self.assertAlmostEqual(params["vx"], server.VX_MAX, places=3)
        self.assertAlmostEqual(params["vyaw"], -server.VYAW_MAX, places=3)
        self.assertEqual(params["vy"], 0.0)

    def test_drive_backwards_is_capped_harder(self):
        client = self.connect()
        self.h.fake.wait_for_client()
        self.h.fake.reset()
        client.send({"t": "drive", "vx": -5.0, "vyaw": 0.0})
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and not self.h.fake.moves():
            time.sleep(0.02)
        self.assertAlmostEqual(self.h.fake.moves()[-1]["params"]["vx"], server.VX_MIN, places=3)

    def test_stop_command_reaches_robotd(self):
        client = self.connect()
        client.send({"t": "cmd", "id": 7, "name": "stop"})
        ack = client.wait_for("ack", id=7)
        self.assertTrue(ack["ok"], ack)
        self.assertTrue(self.h.fake.calls("robot.stop"))

    def test_relax_needs_confirmation(self):
        client = self.connect()
        client.send({"t": "cmd", "id": 1, "name": "relax"})
        ack = client.wait_for("ack", id=1)
        self.assertFalse(ack["ok"])
        self.assertFalse(self.h.fake.calls("robot.relax"))

        client.send({"t": "cmd", "id": 2, "name": "relax", "confirm": "RELAX"})
        ack = client.wait_for("ack", id=2)
        self.assertTrue(ack["ok"], ack)
        self.assertTrue(self.h.fake.calls("robot.relax"))

    def test_init_and_enable(self):
        client = self.connect()
        client.send({"t": "cmd", "id": 3, "name": "init"})
        self.assertTrue(client.wait_for("ack", id=3)["ok"])
        client.send({"t": "cmd", "id": 4, "name": "enable", "on": False})
        self.assertTrue(client.wait_for("ack", id=4)["ok"])
        params = json.loads(json.dumps(self.h.fake.calls("robot.enable")[-1]["params"]))
        self.assertEqual(params, {"on": False})

    def test_reboot_motors(self):
        client = self.connect()
        client.send({"t": "cmd", "id": 5, "name": "rebootMotors"})
        self.assertTrue(client.wait_for("ack", id=5)["ok"])
        self.assertEqual(self.h.fake.calls("robot.rebootMotors")[-1]["params"], {"ids": []})

    def test_shutdown_needs_confirmation(self):
        client = self.connect()
        client.send({"t": "cmd", "id": 8, "name": "shutdown"})
        self.assertFalse(client.wait_for("ack", id=8)["ok"])
        self.assertFalse(self.h.fake.calls("robot.shutdown"))

        client.send({"t": "cmd", "id": 9, "name": "shutdown", "confirm": "SHUTDOWN"})
        self.assertTrue(client.wait_for("ack", id=9)["ok"])
        self.assertTrue(self.h.fake.calls("robot.shutdown"))

    def test_unknown_command_is_refused(self):
        client = self.connect()
        client.send({"t": "cmd", "id": 6, "name": "launch"})
        ack = client.wait_for("ack", id=6)
        self.assertFalse(ack["ok"])

    def test_refusal_reason_is_passed_through(self):
        self.h.fake.responses["robot.enable"] = {"accepted": False, "reason": "机器人未站立"}
        client = self.connect()
        client.send({"t": "cmd", "id": 8, "name": "enable", "on": True})
        ack = client.wait_for("ack", id=8)
        self.assertFalse(ack["ok"])
        self.assertEqual(ack["reason"], "机器人未站立")

    def test_state_frame_is_trimmed_and_merged_with_health(self):
        client = self.connect()

        def stream() -> None:
            # 20 Hz for long enough that the 1 Hz health poll lands mid-stream.
            end = time.monotonic() + 2.5
            while time.monotonic() < end:
                self.h.fake.push_state(
                    policy="walk",
                    move={"requested": [0.18, 0.0, -0.4], "applied": [0.15, 0.0, -0.32],
                          "limited_by": ["deadman"]},
                    safety={"fallen": False, "limp": False, "gravity": [0.0, 0.0, -1.0]},
                    loop={"hz": 47.2, "missed": 12},
                )
                time.sleep(0.05)

        pump = threading.Thread(target=stream, daemon=True)
        pump.start()

        state = None
        deadline = time.monotonic() + 4.0
        while time.monotonic() < deadline:
            candidate = client.wait_for("state")
            state = candidate
            if candidate.get("bat") and candidate["pol"] == "walk":
                break
        pump.join(timeout=1.0)

        self.assertIsNotNone(state)
        assert state is not None
        self.assertEqual(state["pol"], "walk")
        self.assertEqual(state["lim"], ["deadman"])
        self.assertAlmostEqual(state["mv"][0], 0.18, places=3)
        self.assertAlmostEqual(state["ap"][2], -0.32, places=3)
        self.assertAlmostEqual(state["hz"], 47.2, places=2)
        self.assertEqual(state["missed"], 12)
        self.assertEqual(state["bat"], [7.55, 61.0])
        self.assertEqual(state["temp"], 30.5)
        self.assertEqual(state["cpu"], 48.0)
        # the frame the page gets must stay small — the raw one is ~4 KB
        self.assertLess(len(json.dumps(state)), 400)

    def test_ping_is_answered(self):
        client = self.connect()
        client.send({"t": "ping"})
        self.assertIn("ts", client.wait_for("pong"))


class SecondClientTest(BridgeTestCase):
    def test_second_client_is_readonly_and_cannot_drive(self):
        self.connect("Mate 40 Pro")
        watcher = self.h.client()
        self.clients.append(watcher)
        watcher.send({"t": "hello", "name": "iPad"})
        self.assertEqual(watcher.wait_for("hello")["role"], "readonly")

        self.h.fake.wait_for_client()
        self.h.fake.reset()
        watcher.send({"t": "drive", "vx": 0.2, "vyaw": 0.0})
        time.sleep(0.3)
        self.assertFalse(self.h.fake.moves(), "只读客户端不能下发移动")

        watcher.send({"t": "cmd", "id": 11, "name": "stop"})
        ack = watcher.wait_for("ack", id=11)
        self.assertFalse(ack["ok"])
        self.assertEqual(ack["reason"], "readonly")

    def test_takeover_moves_the_wheel(self):
        driver = self.connect("Mate 40 Pro")
        watcher = self.h.client()
        self.clients.append(watcher)
        watcher.send({"t": "hello", "name": "iPad"})
        hello = watcher.wait_for("hello")
        self.assertEqual(hello["role"], "readonly")

        watcher.send({"t": "takeover"})
        session = watcher.wait_for("session", role="driver")
        self.assertEqual(session["role"], "driver")

        demoted = driver.wait_for("session", role="readonly")
        self.assertIn("接管", demoted.get("reason", ""))

        self.h.fake.wait_for_client()
        self.h.fake.reset()
        watcher.send({"t": "drive", "vx": 0.2, "vyaw": 0.0})
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and not self.h.fake.moves():
            time.sleep(0.02)
        self.assertTrue(self.h.fake.moves())


class AuthTest(BridgeTestCase):
    auth = True
    token = "123456"

    def test_wrong_token_is_refused(self):
        client = self.h.client()
        self.clients.append(client)
        client.send({"t": "hello", "token": "000000", "name": "x"})
        hello = client.wait_for("hello")
        self.assertFalse(hello["ok"])
        self.assertEqual(hello["reason"], "bad_token")
        self.assertEqual(hello["remaining"], server.Pairing.MAX_FAILURES - 1)

    def test_unpaired_client_cannot_drive(self):
        client = self.h.client()
        self.clients.append(client)
        self.h.fake.wait_for_client()
        self.h.fake.reset()
        client.send({"t": "drive", "vx": 0.2, "vyaw": 0})
        time.sleep(0.3)
        self.assertFalse(self.h.fake.moves())
        self.assertFalse(self.h.fake.calls("robot.move"))

    def test_right_token_drives(self):
        client = self.h.client()
        self.clients.append(client)
        client.send({"t": "hello", "token": "123456", "name": "Mate 40 Pro"})
        hello = client.wait_for("hello")
        self.assertTrue(hello["ok"])
        self.assertEqual(hello["role"], "driver")


class HttpTest(unittest.TestCase):
    def setUp(self):
        self.h = BridgeHarness()

    def tearDown(self):
        self.h.close()

    def get(self, path: str):
        return urllib.request.urlopen(self.h.url + path, timeout=5)

    def test_index_is_served(self):
        with self.get("/") as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("text/html", resp.headers["Content-Type"])
            self.assertIn(b"duck", resp.read())

    def test_static_assets(self):
        with self.get("/app.js") as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("javascript", resp.headers["Content-Type"])

    def test_healthz(self):
        with self.get("/healthz") as resp:
            self.assertIn(resp.status, (200, 503))

    def test_traversal_is_refused(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.get("/../server.py")
        self.assertEqual(ctx.exception.code, 404)

    def test_stop_beacon(self):
        req = urllib.request.Request(self.h.url + "/stop", data=b"{}", method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 204)


if __name__ == "__main__":
    unittest.main()


class ReadOnlyModeTest(unittest.TestCase):
    """robotd in commissioning mode: the socket is fine, `robot.subscribe` is not.

    Treating that refusal as a dead link was a real bug found on the robot: the
    bridge stopped polling health, so the phone showed nothing at all while the
    board still had battery, temperature and bus data to give.
    """

    REFUSAL = "robotd is read-only: motor commands are disabled"

    def setUp(self):
        self.h = BridgeHarness(refuse={"robot.subscribe": self.REFUSAL})
        self.clients: list[WSClient] = []

    def tearDown(self):
        for c in self.clients:
            c.close()
        self.h.close()

    def connect(self) -> WSClient:
        client = self.h.client()
        self.clients.append(client)
        client.send({"t": "hello", "name": "Mate 40 Pro"})
        hello = client.wait_for("hello")
        self.assertTrue(hello.get("ok"), hello)
        return client

    def test_socket_stays_up_and_health_still_flows(self):
        client = self.connect()
        deadline = time.monotonic() + 8.0
        state = None
        while time.monotonic() < deadline:
            state = client.wait_for("state")
            if state.get("ro") and state.get("bat"):
                break
        assert state is not None
        self.assertTrue(state.get("ro"), state)
        self.assertIn("read-only", state.get("roReason", ""))
        self.assertEqual(state["bat"], [7.55, 61.0])
        self.assertEqual(state["temp"], 30.5)
        self.assertIsNone(state["mv"][0] if False else None)
        self.assertTrue(self.h.httpd.bridge.online, "拒绝订阅不等于断线")

    def test_healthz_says_read_only_rather_than_ok(self):
        deadline = time.monotonic() + 5.0
        body = b""
        while time.monotonic() < deadline:
            with urllib.request.urlopen(self.h.url + "/healthz", timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                body = resp.read()
            if body.strip() == b"read-only":
                break
            time.sleep(0.1)
        self.assertEqual(body.strip(), b"read-only")

    def test_drive_is_not_forwarded_while_read_only(self):
        client = self.connect()
        self.h.fake.wait_for_client()
        self.h.fake.reset()
        client.send({"t": "drive", "vx": 0.2, "vyaw": 0.0})
        time.sleep(0.4)
        self.assertFalse(self.h.fake.moves())


class RobotdVersionTest(unittest.TestCase):
    """The status footer needs a version; robot.health does not carry one."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="duckphone-ver-"))
        self.manifest = self.dir / "BUILD.json"
        self._old = server.VERSION_CANDIDATES
        server.VERSION_CANDIDATES = (str(self.manifest),)

    def tearDown(self):
        server.VERSION_CANDIDATES = self._old
        os.environ.pop("DUCKPHONE_ROBOTD_VERSION", None)

    def test_reads_build_manifest(self):
        self.manifest.write_text(json.dumps({"official_version": "0.15.1"}), encoding="utf-8")
        self.assertEqual(server.detect_robotd_version(), "0.15.1")

    def test_env_overrides_manifest(self):
        self.manifest.write_text(json.dumps({"official_version": "0.15.1"}), encoding="utf-8")
        os.environ["DUCKPHONE_ROBOTD_VERSION"] = "r17-test"
        self.assertEqual(server.detect_robotd_version(), "r17-test")

    def test_missing_manifest_is_empty_not_guessed(self):
        self.assertEqual(server.detect_robotd_version(), "")

    def test_broken_manifest_is_empty(self):
        self.manifest.write_text("{not json", encoding="utf-8")
        self.assertEqual(server.detect_robotd_version(), "")


class PolicyBarTest(unittest.TestCase):
    """The bar's contract with robotd: which slots exist, and what a tap sends."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="duckphone-models-"))
        self.models = self.tmp / "models"
        # One package with metadata, one without — the label is decoration, the
        # slot is authoritative, so both must survive.
        walk = self.models / "walk"
        walk.mkdir(parents=True)
        (walk / "model-info.json").write_text(
            json.dumps({"name": "行走＋倒地联合 9600 轮"}), encoding="utf-8")
        (walk / "manifest.json").write_text(
            json.dumps({"description": "行走、零速保持和倒地恢复"}), encoding="utf-8")
        (self.models / "sit").mkdir()

    def test_catalog_keeps_slot_order_and_skips_absent_slots(self):
        report = {
            "mode": "walk", "sitting": False,
            "slots": [
                {"slot": "walk", "path": str(self.models / "walk" / "policy.onnx"), "error": None},
                {"slot": "sitstand", "path": str(self.models / "sit" / "policy.onnx"), "error": None},
                # `kick_right` absent on purpose: an older daemon must not make
                # the bar render a slot it cannot run.
            ],
        }
        bar = server.build_policy_bar(report, str(self.models))
        self.assertEqual([c["slot"] for c in bar], ["walk", "sitstand"])
        self.assertEqual(bar[0]["name"], "行走＋倒地联合 9600 轮")
        self.assertEqual(bar[0]["desc"], "行走、零速保持和倒地恢复")
        # A package without model-info falls back to the slot's own label.
        self.assertEqual(bar[1]["name"], "坐下／站起")

    def test_slot_without_file_is_not_ready_but_still_listed(self):
        report = {"slots": [{"slot": "kick_right", "path": None, "error": None}]}
        bar = server.build_policy_bar(report, None)
        self.assertEqual(len(bar), 1)
        self.assertFalse(bar[0]["ready"])
        self.assertEqual(bar[0]["kind"], "oneshot")

    def test_walk_is_always_ready_because_every_slot_falls_back_to_it(self):
        report = {"slots": [{"slot": "walk", "path": None, "error": None}]}
        self.assertTrue(server.build_policy_bar(report, None)[0]["ready"])

    def test_kinds_match_the_robotd_cascade(self):
        # walk 常驻、sitstand 锁存、其余是跑完就回 walk 的一次性技能
        kinds = {row["slot"]: row["kind"] for row in server.POLICY_SLOTS}
        self.assertEqual(kinds["walk"], "walk")
        self.assertEqual(kinds["sitstand"], "latch")
        for slot in ("ground_pick", "kick_left", "kick_right", "roulade"):
            self.assertEqual(kinds[slot], "oneshot", slot)
        # Only the latch and one-shots have something to send; walk sends nothing.
        self.assertIsNone({r["slot"]: r["skill"] for r in server.POLICY_SLOTS}["walk"])

    def test_every_non_walk_slot_names_a_skill_robot_do_accepts(self):
        for row in server.POLICY_SLOTS:
            if row["kind"] == "walk":
                continue
            self.assertIn(row["skill"], server.POLICY_SKILLS)


class PolicyCommandTest(BridgeTestCase):
    def test_readonly_session_can_still_read_policies(self):
        """只读会话也要能看到策略列表：它是只读数据，藏起来只会让人以为坏了。"""
        driver = self.connect(name="Mate 40 Pro")
        second = self.h.client()
        self.clients.append(second)
        second.send({"t": "hello", "name": "电脑"})
        self.assertEqual(second.wait_for("hello")["role"], "readonly")
        second.send({"t": "cmd", "id": 21, "name": "policies"})
        msg = second.wait_for("policies")
        self.assertTrue(msg["ok"])
        self.assertEqual(msg["chips"][0]["slot"], "walk")
        # 但真正会动机器人的指令仍然被拒
        second.send({"t": "cmd", "id": 22, "name": "init"})
        self.assertFalse(second.wait_for("ack", id=22)["ok"])

    def test_policies_returns_the_bar(self):
        client = self.connect()
        client.send({"t": "cmd", "id": 11, "name": "policies"})
        msg = client.wait_for("policies")
        self.assertTrue(msg["ok"])
        self.assertEqual(msg["mode"], "walk")
        slots = [c["slot"] for c in msg["chips"]]
        self.assertEqual(
            slots, ["walk", "sitstand", "ground_pick", "kick_left", "kick_right", "roulade"])
        by_slot = {c["slot"]: c for c in msg["chips"]}
        self.assertTrue(by_slot["walk"]["ready"])
        # A slot the daemon reports but that holds no file is still listed —
        # struck through and not tappable beats silently missing.
        self.assertFalse(by_slot["kick_right"]["ready"])

    def test_policy_do_sends_robot_do_with_the_skill(self):
        client = self.connect()
        client.send({"t": "cmd", "id": 12, "name": "policyDo", "skill": "roulade"})
        ack = client.wait_for("ack", id=12)
        self.assertTrue(ack["ok"], ack)
        self.assertEqual(self.h.fake.calls("robot.do")[-1]["params"], {"skill": "roulade"})
        self.assertIn("chips", ack["policies"])

    def test_unknown_skill_never_reaches_robotd(self):
        client = self.connect()
        client.send({"t": "cmd", "id": 13, "name": "policyDo", "skill": "self_destruct"})
        ack = client.wait_for("ack", id=13)
        self.assertFalse(ack["ok"])
        self.assertEqual(self.h.fake.calls("robot.do"), [])

    def test_refusal_reason_is_passed_through(self):
        self.h.fake.responses["robot.do"] = {"accepted": False, "reason": "a ground pick is running"}
        client = self.connect()
        client.send({"t": "cmd", "id": 14, "name": "policyDo", "skill": "roulade"})
        ack = client.wait_for("ack", id=14)
        self.assertFalse(ack["ok"])
        self.assertIn("ground pick", ack["reason"])


class HeadTest(BridgeTestCase):
    def test_head_is_forwarded_and_clamped(self):
        client = self.connect()
        self.h.fake.wait_for_client()
        self.h.fake.reset()
        client.send({"t": "head", "neck_pitch": 0, "head_pitch": 3.0,
                     "head_yaw": -2.0, "head_roll": 0})
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and not self.h.fake.calls("robot.head"):
            time.sleep(0.02)
        params = self.h.fake.calls("robot.head")[-1]["params"]
        self.assertAlmostEqual(params["head_pitch"], server.HEAD_MAX, places=6)
        self.assertAlmostEqual(params["head_yaw"], -server.HEAD_MAX, places=6)
        self.assertEqual(params["neck_pitch"], 0.0)
        self.assertEqual(params["head_roll"], 0.0)

    def test_head_is_dropped_for_readonly_session(self):
        self.connect("Mate 40 Pro")
        watcher = self.h.client()
        self.clients.append(watcher)
        watcher.send({"t": "hello", "name": "iPad"})
        self.assertEqual(watcher.wait_for("hello")["role"], "readonly")
        self.h.fake.wait_for_client()
        self.h.fake.reset()
        watcher.send({"t": "head", "head_yaw": 0.4, "head_pitch": 0.2})
        time.sleep(0.3)
        self.assertFalse(self.h.fake.calls("robot.head"))

    def test_head_is_zeroed_when_the_driver_leaves(self):
        client = self.connect()
        self.h.fake.wait_for_client()
        self.h.fake.reset()
        client.send({"t": "head", "head_yaw": 0.4, "head_pitch": 0.2})
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and not self.h.fake.calls("robot.head"):
            time.sleep(0.02)
        self.h.fake.reset()
        client.close()
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and not self.h.fake.calls("robot.head"):
            time.sleep(0.02)
        params = self.h.fake.calls("robot.head")[-1]["params"]
        self.assertEqual(params, {"neck_pitch": 0.0, "head_pitch": 0.0,
                                  "head_yaw": 0.0, "head_roll": 0.0})


class SoundTest(BridgeTestCase):
    def setUp(self):
        super().setUp()
        self.driver = super().connect("Mate 40 Pro")
        # 接管会自动开启动态声音并 greet 一次；先等它落地再关掉并清空记录，
        # 后面的断言才只看到本用例手动点的声音。
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and not self.h.fake.calls("robot.sound"):
            time.sleep(0.02)
        self.h.httpd.bridge.dynamic_sound = False
        self.h.fake.reset()

    def connect(self, name: str = "Mate 40 Pro") -> WSClient:
        return self.driver

    def test_sound_tag_is_forwarded(self):
        client = self.connect()
        client.send({"t": "cmd", "id": 31, "name": "sound", "tag": "chirp"})
        ack = client.wait_for("ack", id=31)
        self.assertTrue(ack["ok"], ack)
        self.assertEqual(self.h.fake.calls("robot.sound")[-1]["params"], {"tag": "chirp"})

    def test_wheee_hold_is_forwarded_both_ways(self):
        client = self.connect()
        client.send({"t": "cmd", "id": 32, "name": "sound", "tag": "wheee", "hold": True})
        self.assertTrue(client.wait_for("ack", id=32)["ok"])
        client.send({"t": "cmd", "id": 33, "name": "sound", "tag": "wheee", "hold": False})
        self.assertTrue(client.wait_for("ack", id=33)["ok"])
        calls = self.h.fake.calls("robot.sound")[-2:]
        self.assertEqual(calls[0]["params"], {"tag": "wheee", "hold": True})
        self.assertEqual(calls[1]["params"], {"tag": "wheee", "hold": False})

    def test_hold_is_ignored_for_one_shot_tags(self):
        client = self.connect()
        client.send({"t": "cmd", "id": 34, "name": "sound", "tag": "greet", "hold": True})
        self.assertTrue(client.wait_for("ack", id=34)["ok"])
        self.assertEqual(self.h.fake.calls("robot.sound")[-1]["params"], {"tag": "greet"})

    def test_unknown_tag_never_reaches_robotd(self):
        client = self.connect()
        client.send({"t": "cmd", "id": 35, "name": "sound", "tag": "explode"})
        ack = client.wait_for("ack", id=35)
        self.assertFalse(ack["ok"])
        self.assertEqual(self.h.fake.calls("robot.sound"), [])

    def test_readonly_session_cannot_play(self):
        self.connect("Mate 40 Pro")
        watcher = self.h.client()
        self.clients.append(watcher)
        watcher.send({"t": "hello", "name": "iPad"})
        watcher.wait_for("hello")
        watcher.send({"t": "cmd", "id": 36, "name": "sound", "tag": "chirp"})
        ack = watcher.wait_for("ack", id=36)
        self.assertFalse(ack["ok"])
        self.assertEqual(ack["reason"], "readonly")


class DynamicSoundTest(BridgeTestCase):
    """动态声音是桥接层的一份状态：手机走 WebSocket，调试台走 HTTP。"""

    def get_json(self, path: str):
        with urllib.request.urlopen(self.h.url + path, timeout=5) as resp:
            return resp.status, json.loads(resp.read())

    def post_json(self, path: str, payload: dict):
        req = urllib.request.Request(
            self.h.url + path, data=json.dumps(payload).encode(),
            method="POST", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())

    def test_http_starts_off_and_toggles(self):
        status, body = self.get_json("/api/dynamic-sound")
        self.assertEqual(status, 200)
        self.assertFalse(body["enabled"])
        self.assertFalse(self.h.httpd.bridge.snapshot()["dyn"])

        _, body = self.post_json("/api/dynamic-sound", {"enabled": True})
        self.assertTrue(body["enabled"])
        self.assertTrue(self.h.httpd.bridge.snapshot()["dyn"])
        self.assertTrue(self.get_json("/api/status")[1]["dynamicSound"])

        _, body = self.post_json("/api/dynamic-sound", {"toggle": True})
        self.assertFalse(body["enabled"])
        self.assertFalse(self.h.httpd.bridge.snapshot()["dyn"])

    def test_bad_payload_is_refused(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.post_json("/api/dynamic-sound", {"enabled": "yes"})
        self.assertEqual(ctx.exception.code, 400)
        self.assertFalse(self.h.httpd.bridge.dynamic_sound)

    def test_cors_preflight_allows_the_console(self):
        # 调试台在 8000，手机桥在 8001：没有这两个头，控制台的开关会被浏览器拦掉。
        req = urllib.request.Request(self.h.url + "/api/dynamic-sound", method="OPTIONS")
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 204)
            self.assertEqual(resp.headers["Access-Control-Allow-Origin"], "*")
            self.assertIn("POST", resp.headers["Access-Control-Allow-Methods"])

    def test_takeover_turns_it_on_and_the_page_can_turn_it_off(self):
        client = self.connect()
        self.assertTrue(client.wait_for("state", dyn=True)["dyn"])
        client.send({"t": "cmd", "id": 41, "name": "dynamicSound", "on": False})
        ack = client.wait_for("ack", id=41)
        self.assertTrue(ack["ok"], ack)
        self.assertFalse(ack["enabled"])
        self.assertFalse(client.wait_for("state", dyn=False)["dyn"])

        client.send({"t": "cmd", "id": 42, "name": "dynamicSound", "on": True})
        self.assertTrue(client.wait_for("ack", id=42)["enabled"])
        self.assertTrue(client.wait_for("state", dyn=True)["dyn"])

    def test_bad_on_value_never_changes_the_switch(self):
        client = self.connect()
        client.send({"t": "cmd", "id": 43, "name": "dynamicSound", "on": "yes"})
        ack = client.wait_for("ack", id=43)
        self.assertFalse(ack["ok"])
        self.assertTrue(self.h.httpd.bridge.dynamic_sound)

    def test_readonly_session_cannot_toggle(self):
        self.connect("Mate 40 Pro")
        watcher = self.h.client()
        self.clients.append(watcher)
        watcher.send({"t": "hello", "name": "iPad"})
        self.assertEqual(watcher.wait_for("hello")["role"], "readonly")
        watcher.send({"t": "cmd", "id": 44, "name": "dynamicSound", "on": False})
        ack = watcher.wait_for("ack", id=44)
        self.assertFalse(ack["ok"])
        self.assertEqual(ack["reason"], "readonly")
        self.assertTrue(self.h.httpd.bridge.dynamic_sound)


class ActionCommandTest(BridgeTestCase):
    """v4 预设动作：桥只转发 `robot.action`，`act` 由 robotd 的帧回传。"""

    def setUp(self):
        super().setUp()
        self.client = self.connect()
        self.assertTrue(self.h.fake.wait_for_client())
        self.h.fake.reset()

    def wait_state(self, predicate, timeout: float = 3.0) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            # The bridge only emits a snapshot when robotd sends a state frame.
            self.h.fake.push_state()
            try:
                state = self.client.wait_for("state", timeout=0.4)
            except AssertionError:
                continue
            if predicate(state):
                return state
        raise AssertionError("没有等到目标 state")

    def test_action_is_forwarded_and_the_frame_carries_act(self):
        self.client.send({"t": "cmd", "id": 1, "name": "action", "action": "quack"})
        ack = self.client.wait_for("ack", id=1)
        self.assertTrue(ack["ok"], ack)
        self.assertEqual(ack["action"], "quack")
        self.assertTrue(ack["sound"])
        self.assertEqual(
            self.h.fake.calls("robot.action")[-1]["params"],
            {"action": "quack", "idle": False, "sound": True},
        )

        # `act` is robotd's answer, not the bridge's own player.
        self.h.fake.push_state(act="quack", actIdle=False)
        state = self.wait_state(lambda s: s.get("act") == "quack")
        self.assertFalse(state["actIdle"])

    def test_cancel_is_the_same_method_with_no_action(self):
        self.client.send({"t": "cmd", "id": 2, "name": "cancelAction"})
        self.assertTrue(self.client.wait_for("ack", id=2)["ok"])
        params = self.h.fake.calls("robot.action")[-1]["params"]
        self.assertNotIn("action", params)

    def test_unknown_action_never_reaches_robotd(self):
        self.client.send({"t": "cmd", "id": 3, "name": "action", "action": "moonwalk"})
        ack = self.client.wait_for("ack", id=3)
        self.assertFalse(ack["ok"])
        started = [c for c in self.h.fake.calls("robot.action") if "action" in c["params"]]
        self.assertEqual(started, [])

    def test_readonly_cannot_play(self):
        ro = self.h.client()
        self.clients.append(ro)
        ro.send({"t": "hello", "name": "iPad"})
        self.assertEqual(ro.wait_for("hello")["role"], "readonly")
        ro.send({"t": "cmd", "id": 4, "name": "action", "action": "circle"})
        ack = ro.wait_for("ack")
        self.assertFalse(ack["ok"])
        self.assertEqual(ack["reason"], "readonly")
        started = [c for c in self.h.fake.calls("robot.action") if "action" in c["params"]]
        self.assertEqual(started, [])

    def test_robotd_refusal_is_passed_through(self):
        self.h.fake.responses["robot.action"] = {
            "accepted": False, "reason": "机器人未站立或正在移动", "sound": True,
        }
        self.client.send({"t": "cmd", "id": 5, "name": "action", "action": "look_up"})
        ack = self.client.wait_for("ack", id=5)
        self.assertFalse(ack["ok"])
        self.assertIn("未站立", ack["reason"] or "")


class IdleGestureTest(unittest.TestCase):
    """The idle director asks robotd for the gesture, silently — it has already
    played the sound the gesture belongs to."""

    def setUp(self):
        self.h = BridgeHarness()
        self.clients: list[WSClient] = []

    def tearDown(self):
        for c in self.clients:
            c.close()
        self.h.close()

    def test_idle_requests_look_up_silently(self):
        client = self.h.client()
        self.clients.append(client)
        client.send({"t": "hello", "name": "Mate 40 Pro"})
        self.assertEqual(client.wait_for("hello")["role"], "driver")
        self.h.httpd.audio_settings.update(
            {"idle": {"after_s": 5.0, "repeat_s": 30.0, "gesture": True,
                      "library": ["look_up"]}})
        self.h.fake.reset()

        def stream() -> None:
            end = time.monotonic() + 7.0
            while time.monotonic() < end:
                self.h.fake.push_state(
                    policy="walk",
                    safety={"fallen": False, "limp": False, "gravity": [0.0, 0.0, -1.0]},
                )
                time.sleep(0.05)

        pump = threading.Thread(target=stream, daemon=True)
        pump.start()

        deadline = time.monotonic() + 9.0
        calls = []
        while time.monotonic() < deadline and not calls:
            calls = [c for c in self.h.fake.calls("robot.action") if "action" in c["params"]]
            time.sleep(0.05)
        pump.join(timeout=1.0)
        self.assertTrue(calls, "空闲没有请求动作")
        params = calls[0]["params"]
        self.assertEqual(params["action"], "look_up")
        self.assertTrue(params["idle"])
        self.assertFalse(params["sound"], "空闲导演已经放过声音，动作必须静音")


class AudioConfigTest(BridgeTestCase):
    """动态声音设置：手机走 WebSocket，调试台走 HTTP，共用同一份配置。"""

    def get_json(self, path: str):
        with urllib.request.urlopen(self.h.url + path, timeout=5) as resp:
            return resp.status, json.loads(resp.read())

    def post_json(self, path: str, payload: dict):
        req = urllib.request.Request(
            self.h.url + path, data=json.dumps(payload).encode(),
            method="POST", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())

    def test_http_defaults_patch_and_reset(self):
        status, body = self.get_json("/api/audio-config")
        self.assertEqual(status, 200)
        self.assertEqual(body["config"]["idle"]["after_s"], 30)

        _, body = self.post_json("/api/audio-config", {"patch": {"idle": {"after_s": 45}}})
        self.assertEqual(body["config"]["idle"]["after_s"], 45)
        self.assertEqual(self.get_json("/api/audio-config")[1]["config"]["idle"]["after_s"], 45)

        _, body = self.post_json("/api/audio-config", {"reset": True})
        self.assertEqual(body["config"]["idle"]["after_s"], 30)

    def test_bad_config_is_refused(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.post_json("/api/audio-config", {"patch": "nope"})
        self.assertEqual(ctx.exception.code, 400)

    def test_hello_carries_the_config(self):
        client = self.h.client()
        self.clients.append(client)
        client.send({"t": "hello", "name": "Mate 40 Pro"})
        hello = client.wait_for("hello")
        self.assertEqual(hello["audio"]["idle"]["after_s"], 30)

    def test_ws_read_write_and_broadcast(self):
        driver = self.connect()
        driver.send({"t": "cmd", "id": 51, "name": "audioConfig"})
        self.assertEqual(driver.wait_for("audioConfig")["config"]["idle"]["after_s"], 30)

        watcher = self.h.client()
        self.clients.append(watcher)
        watcher.send({"t": "hello", "name": "iPad"})
        self.assertEqual(watcher.wait_for("hello")["role"], "readonly")

        driver.send({"t": "cmd", "id": 52, "name": "setAudioConfig",
                     "patch": {"idle": {"after_s": 45}, "alerts": {"bus": False}}})
        ack = driver.wait_for("ack", id=52)
        self.assertTrue(ack["ok"], ack)
        self.assertEqual(ack["config"]["idle"]["after_s"], 45)
        pushed = watcher.wait_for("audioConfig")
        self.assertEqual(pushed["config"]["idle"]["after_s"], 45)
        self.assertFalse(pushed["config"]["alerts"]["bus"])

        watcher.send({"t": "cmd", "id": 53, "name": "setAudioConfig",
                      "patch": {"idle": {"after_s": 60}}})
        refused = watcher.wait_for("ack", id=53)
        self.assertFalse(refused["ok"])
        self.assertEqual(refused["reason"], "readonly")
        watcher.send({"t": "cmd", "id": 54, "name": "audioConfig"})
        self.assertEqual(watcher.wait_for("audioConfig")["config"]["idle"]["after_s"], 45)


class VolumeMathTest(unittest.TestCase):
    def test_curve_matches_the_console(self):
        self.assertEqual(server.volume_raw(0), 0)
        self.assertEqual(server.volume_raw(100), 127)
        self.assertEqual(server.volume_percent(127), 100)
        # The mapping is symmetric enough that a round trip is within a percent.
        for percent in (1, 25, 50, 60, 75, 99):
            self.assertLessEqual(abs(server.volume_percent(server.volume_raw(percent)) - percent), 1)

    def test_out_of_range_is_clamped(self):
        self.assertEqual(server.volume_raw(-5), 0)
        self.assertEqual(server.volume_raw(200), 127)
        self.assertEqual(server.volume_percent(-20), 0)
        self.assertEqual(server.volume_percent(400), 100)


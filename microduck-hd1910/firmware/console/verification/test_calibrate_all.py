"""Fault injection for one-click CAL(0x0B) and calibration readback."""
import copy
import math
import sys
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from controls import ControlError
from service_control import ServiceController, ServiceTransport, validate
from telemetry import IDS, LABELS, NAMES


def calibration_status(zero=2048):
    joints = [{"id": sid, "name": NAMES[index], "direction": 1 if index % 2 == 0 else -1,
               "min_rad": math.radians(-90), "max_rad": math.radians(90),
               "zero_raw": zero, "calibrated": True}
              for index, sid in enumerate(IDS)]
    return {"calibration_path": "/etc/robot/feetech-ft5/hd1910-calibration.toml",
            "calibration": {"joints": joints, "imu_mount_quat": [1, 0, 0, 0],
                            "imu_mount_verified": True, "motion_enabled": False},
            "uncalibrated_joints": []}


def snapshot(zero=1000, native=True):
    status = calibration_status(zero)
    joints = status["calibration"]["joints"]
    servos = [{"id": sid, "name": NAMES[index], "label": LABELS[index], "status": "live",
               "position_raw": 2048, "angle_deg": 0.0, "calibrated": True,
               "calibration": joints[index]} for index, sid in enumerate(IDS)]
    bus = {"build": f"1fa8438-feetech-ft6-control.{44 if native else 43}",
           "mode": "commissioning", "phase": "ready", "torque_state": "off",
           "torque_off_pending": None, "motion": None, "power_pending": False}
    if native:
        bus["calibrate_all"] = True
    return {"bus": bus, "servos": servos, "calibration": status,
            "saved_calibrated_count": len(IDS), "service_sample_fresh": True,
            "service_compatible": True}


class FakeStore:
    def __init__(self, data):
        self.data = copy.deepcopy(data)
        self.service_operation = False
        self.connection_paused = None
        self.system_log = None
        self.robotd_restarting = threading.Event()
        self.commands = []
        self.ingested = []

    def snapshot(self, record=True):
        return copy.deepcopy(self.data)

    def ingest(self, event):
        self.ingested.append(copy.deepcopy(event))

    def record_service_command(self, job):
        self.commands.append(copy.deepcopy(job))


class FakeTransport:
    def __init__(self, store, failure=None, gate=None):
        self.store = store
        self.failure = failure
        self.gate = gate
        self.calls = []

    def call(self, command):
        self.calls.append(copy.deepcopy(command))
        if command["action"] == "calibration-status":
            return calibration_status(2048)
        if command["action"] != "calibrate-all":
            raise AssertionError(f"unexpected RPC: {command!r}")
        if self.failure:
            if self.gate:
                self.store.data["bus"]["calibration_all"] = {
                    "total": len(IDS), "done_ids": [IDS[0]], "current_id": IDS[1], "stage": "calibrate"}
                self.gate.wait(2)
            raise ControlError(self.failure, 503)
        for index, sid in enumerate(IDS):
            self.store.data["bus"]["calibration_all"] = {
                "total": len(IDS), "done_ids": IDS[:index], "current_id": sid, "stage": "calibrate"}
            if self.gate:
                self.gate.wait(2)
            time.sleep(.005)
        self.store.data["bus"]["calibration_all"] = None
        return {"completed_ids": list(IDS), "positions": {str(sid): 2048 for sid in IDS},
                "backup": "/etc/robot/feetech-ft5/hd1910-calibration.toml.bak-test",
                "calibration": calibration_status(2048)}


def wait_job(controller, timeout=5):
    deadline = time.monotonic() + timeout
    while controller.job and controller.job.get("status") == "running" and time.monotonic() < deadline:
        time.sleep(.01)
    return controller.job


def post(controller, command, seq=1, client="a" * 8):
    return controller.handle({"client": client, "seq": seq, "command": command})


class ValidateTests(unittest.TestCase):
    def test_explicit_confirmation_is_required(self):
        for command in ({"action": "calibrate-all"},
                        {"action": "calibrate-all", "confirmed": False},
                        {"action": "calibrate-all", "confirmed": 1},
                        {"action": "calibrate-all", "confirmed": True, "extra": 1}):
            with self.subTest(command=command), self.assertRaises(ControlError):
                validate(command)

    def test_native_operation_rejects_sudo_password(self):
        with self.assertRaises(ControlError):
            validate({"action": "calibrate-all", "confirmed": True, "sudo_password": "x"})


class PreflightTests(unittest.TestCase):
    def test_valid_preflight_preserves_saved_direction_and_limits(self):
        preflight = ServiceController._cal_all_preflight(snapshot())
        self.assertEqual(len(preflight["joints"]), len(IDS))
        self.assertEqual(preflight["joints"][0]["direction"], 1)
        self.assertAlmostEqual(preflight["joints"][0]["min_deg"], -90)
        self.assertTrue(preflight["path"].endswith(".toml"))

    def test_all_hardware_and_calibration_gates_fail_closed(self):
        mutations = (
            lambda s: s["bus"].update(mode="motion"),
            lambda s: s["bus"].update(phase="configuring_uart"),
            lambda s: s["bus"].update(torque_state="single_joint_enabled"),
            lambda s: s["bus"].update(torque_off_pending="pending"),
            lambda s: s.update(service_sample_fresh=False),
            lambda s: s["bus"].update(motion={"action": "move"}),
            lambda s: s["bus"].update(power_pending=True),
            lambda s: s.update(saved_calibrated_count=14),
            lambda s: s["servos"].pop(),
            lambda s: s["servos"][0].update(status="stale"),
            lambda s: s["servos"][0].update(calibrated=False),
            lambda s: s["calibration"]["calibration"]["joints"][0].update(calibrated=False),
            lambda s: s["calibration"]["calibration"]["joints"][0].update(name="wrong_joint"),
            lambda s: s["calibration"]["calibration"]["joints"][0].update(direction=0),
            lambda s: s["calibration"]["calibration"]["joints"][0].update(min_rad=0.1),
            lambda s: s["calibration"]["calibration"]["joints"][0].update(
                min_rad=math.radians(-180), max_rad=math.radians(180)),
        )
        for mutate in mutations:
            state = snapshot()
            mutate(state)
            with self.subTest(state=state), self.assertRaises(ControlError):
                ServiceController._cal_all_preflight(state)


class TransportTests(unittest.TestCase):
    def test_rpc_timeout_leaves_margin_over_robotd_deadline(self):
        class Channel:
            timeout = None

            def request(self, payload, timeout):
                self.timeout = timeout
                return {"id": 1, "result": {}}

        transport = object.__new__(ServiceTransport)
        transport.log = None
        transport.channel = Channel()
        transport.call({"action": "calibrate-all"})
        self.assertEqual(transport.channel.timeout, 72)


class OrchestrationTests(unittest.TestCase):
    def make(self, native=True, failure=None, gate=None):
        store = FakeStore(snapshot(native=native))
        transport = FakeTransport(store, failure=failure, gate=gate)
        controller = ServiceController(store, transport=transport, warm=False)
        return store, transport, controller

    def test_native_calibration_verifies_and_records_backup(self):
        store, transport, controller = self.make()
        self.assertTrue(post(controller, {"action": "calibrate-all", "confirmed": True})["accepted"])
        job = wait_job(controller)
        self.assertEqual(job["status"], "completed", job)
        self.assertEqual([call["action"] for call in transport.calls],
                         ["calibrate-all", "calibration-status"])
        self.assertEqual(job["calibration_all"]["done_ids"], list(IDS))
        self.assertEqual(len(job["calibration_all"]["sync_results"]), len(IDS))
        self.assertTrue(job["result"]["backup"].endswith(".bak-test"))
        self.assertTrue(any(event.get("channel") == "calibration" for event in store.ingested))
        self.assertFalse(store.robotd_restarting.is_set())

    def test_legacy_robotd_is_rejected_before_rpc(self):
        _, transport, controller = self.make(native=False)
        with self.assertRaises(ControlError):
            post(controller, {"action": "calibrate-all", "confirmed": True})
        self.assertEqual(transport.calls, [])

    def test_native_failure_does_not_attempt_single_joint_capture(self):
        _, transport, controller = self.make(failure="bus write failed")
        post(controller, {"action": "calibrate-all", "confirmed": True})
        job = wait_job(controller)
        self.assertEqual(job["status"], "error", job)
        self.assertIn("bus write failed", job["error"])
        self.assertEqual([call["action"] for call in transport.calls], ["calibrate-all"])

    def test_stop_and_reboot_are_rejected_during_calibration(self):
        _, _, controller = self.make()
        controller.job = {"action": "calibrate-all", "status": "running"}
        for action in ("relax", "reboot", "shutdown"):
            with self.subTest(action=action), self.assertRaises(ControlError):
                post(controller, {"action": action}, client=action + "-client")

    def test_live_native_progress_is_forwarded_to_job(self):
        store = FakeStore(snapshot())
        gate = threading.Event()
        transport = FakeTransport(store, gate=gate)
        controller = ServiceController(store, transport=transport, warm=False)
        post(controller, {"action": "calibrate-all", "confirmed": True})
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            job = controller.job or {}
            if job.get("calibration_all", {}).get("current_id"):
                break
            time.sleep(.01)
        self.assertEqual(job["phase"], "calibrating")
        self.assertEqual(job["calibration_all"]["current_id"], IDS[0])
        gate.set()
        self.assertEqual(wait_job(controller)["status"], "completed")


if __name__ == "__main__":
    unittest.main()
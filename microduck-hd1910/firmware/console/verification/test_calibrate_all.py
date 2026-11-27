"""Fault injection for one-click CAL(0x0B) + TOML sync; no real bus, SSH or systemd."""
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

BUILD_LEGACY = "1fa8438-feetech-ft6-control.43"
BUILD_NATIVE = "1fa8438-feetech-ft6-control.44"


def calibration_status(zero=2048):
    joints = [{"id": sid, "name": NAMES[index], "direction": 1 if index % 2 == 0 else -1,
               "min_rad": math.radians(-90), "max_rad": math.radians(90),
               "zero_raw": zero, "calibrated": True}
              for index, sid in enumerate(IDS)]
    return {"calibration_path": "/etc/robot/feetech-ft5/hd1910-calibration.toml",
            "calibration": {"joints": joints, "imu_mount_quat": [1, 0, 0, 0],
                            "imu_mount_verified": True, "motion_enabled": False},
            "uncalibrated_joints": []}


def snapshot(zero=1000, session=1, native=False):
    status = calibration_status(zero)
    joints = status["calibration"]["joints"]
    servos = [{"id": sid, "name": NAMES[index], "label": LABELS[index], "status": "live",
               "position_raw": 2048, "angle_deg": 0.0, "calibrated": True,
               "calibration": joints[index]} for index, sid in enumerate(IDS)]
    bus = {"build": BUILD_NATIVE if native else BUILD_LEGACY,
           "mode": "commissioning", "phase": "ready",
           "torque_state": "off", "torque_off_pending": None, "motion": None,
           "session": session, "native": {}}
    if native:
        bus["calibrate_all"] = True
    return {"bus": bus,
            "servos": servos, "calibration": status, "saved_calibrated_count": 15,
            "service_sample_fresh": True, "service_compatible": True}


class FakeLog:
    def __init__(self):
        self.lines = []

    def add(self, *args):
        self.lines.append(args)


class FakeStore:
    def __init__(self, data):
        self.data = copy.deepcopy(data)
        self.service_operation = False
        self.connection_paused = None
        self.system_log = FakeLog()
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
    def __init__(self, store, fail_capture_id=None, native_error=None,
                 native_block=None, native_partial=None):
        self.store = store
        self.fail_capture_id = fail_capture_id
        self.native_error = native_error
        self.native_block = native_block
        self.native_partial = native_partial
        self.capture_calls = []
        self.calls = []

    def call(self, command):
        self.calls.append(copy.deepcopy(command))
        if command["action"] == "capture":
            self.capture_calls.append(copy.deepcopy(command))
            if str(command["id"]) == str(self.fail_capture_id):
                raise ControlError("capture failed", 503)
            return {"saved": True, "id": command["id"], "calibration": calibration_status(2048)}
        if command["action"] == "calibration-status":
            return calibration_status(2048)
        if command["action"] == "calibrate-all":
            return self.native_calibrate_all()
        raise AssertionError("unexpected service call: " + repr(command))

    def native_calibrate_all(self):
        if self.native_partial is not None:
            self.store.data["bus"]["calibration_all"] = {
                "status": "running", "total": 15, "done_ids": [IDS[0]],
                "current_id": IDS[1], "stage": "calibrate"}
            time.sleep(.2)
            raise ControlError(self.native_partial, 503)
        for index, sid in enumerate(IDS, 1):
            if self.native_error and index == 5:
                raise ControlError(self.native_error, 503)
            self.store.data["bus"]["calibration_all"] = {
                "status": "running", "total": 15, "done_ids": IDS[:index - 1],
                "current_id": sid, "stage": "calibrate"}
            if self.native_block:
                self.native_block.wait(2)
            time.sleep(.02)
        positions = {str(sid): 2048 for sid in IDS}
        answer = {"completed_ids": IDS, "positions": positions,
                  "backup": "/etc/robot/feetech-ft5/hd1910-calibration.toml.bak-native",
                  "calibration": calibration_status(2048)}
        self.store.data["bus"]["calibration_all"] = None
        return answer


def wait_job(controller, timeout=5):
    deadline = time.monotonic() + timeout
    while controller.job and controller.job.get("status") == "running" and time.monotonic() < deadline:
        time.sleep(.01)
    return controller.job


def post(controller, command, seq=1, client="a" * 8):
    return controller.handle({"client": client, "seq": seq, "command": command})


class ValidateTests(unittest.TestCase):
    def test_confirmation_is_required(self):
        for command in ({"action": "calibrate-all"},
                        {"action": "calibrate-all", "confirmed": False},
                        {"action": "calibrate-all", "confirmed": 1},
                        {"action": "calibrate-all", "confirmed": True, "extra": 1}):
            with self.subTest(command=command), self.assertRaises(ControlError):
                validate(command)

    def test_native_command_does_not_accept_a_sudo_password(self):
        # Native CAL runs inside robotd; accepting a password would imply the
        # console still owns a root SSH path that this firmware no longer needs.
        with self.assertRaises(ControlError):
            validate({"action": "calibrate-all", "confirmed": True, "sudo_password": "p"})


class PreflightTests(unittest.TestCase):
    def test_happy_preflight_keeps_saved_direction_and_limits(self):
        pre = ServiceController._cal_all_preflight(snapshot())
        self.assertEqual(len(pre["joints"]), 15)
        self.assertEqual(pre["joints"][0]["direction"], 1)
        self.assertAlmostEqual(pre["joints"][0]["min_deg"], -90.0)
        self.assertTrue(pre["path"].endswith(".toml"))

    def test_each_gate_fails_closed(self):
        cases = []
        for mutate in (
            lambda s: s["bus"].update(mode="motion"),
            lambda s: s["bus"].update(phase="configuring_uart"),
            lambda s: s["bus"].update(torque_state="single_joint_enabled"),
            lambda s: s["bus"].update(torque_off_pending="off pending"),
            lambda s: s.update(service_sample_fresh=False),
            lambda s: s["bus"].update(motion={"action": "move", "id": 20}),
            lambda s: s["bus"].update(power_pending="reboot"),
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
        ):
            state = snapshot()
            mutate(state)
            cases.append(state)
        for state in cases:
            with self.assertRaises(ControlError):
                ServiceController._cal_all_preflight(state)


class TransportTests(unittest.TestCase):
    def test_calibrate_all_rpc_timeout_exceeds_robotd_deadline(self):
        # robotd gives the CAL state machine 30 s. A shorter RPC timeout would
        # report failure while the robot is still writing servo EEPROMs.
        class Channel:
            timeout = None

            def request(self, payload, timeout):
                self.timeout = timeout
                return {"id": 1, "result": {"completed_ids": [], "positions": {}}}

        transport = object.__new__(ServiceTransport)
        transport.log = None
        transport.channel = Channel()
        transport.call({"action": "calibrate-all"})
        self.assertEqual(transport.channel.timeout, 72)  # 60 s job + 12 s channel margin


class OrchestrationTests(unittest.TestCase):
    def make(self, native=True, **kwargs):
        store = FakeStore(snapshot(native=native))
        transport = FakeTransport(store, **kwargs)
        controller = ServiceController(store, transport=transport, warm=False)
        return store, transport, controller

    def test_native_cal_writes_eeprom_and_backup(self):
        store, transport, controller = self.make()
        answer = post(controller, {"action": "calibrate-all", "confirmed": True})
        self.assertTrue(answer["accepted"])
        job = wait_job(controller)
        self.assertEqual(job["status"], "completed", job)
        self.assertEqual([call["action"] for call in transport.calls],
                         ["calibrate-all", "calibration-status"])
        self.assertEqual(transport.capture_calls, [])
        self.assertEqual(job["calibration_all"]["done_ids"], IDS)
        self.assertEqual(len(job["calibration_all"]["sync_results"]), 15)
        self.assertEqual(job["result"]["backup"],
                         "/etc/robot/feetech-ft5/hd1910-calibration.toml.bak-native")
        self.assertTrue(any(event.get("channel") == "calibration" for event in store.ingested))
        self.assertFalse(store.robotd_restarting.is_set(),
                         'native CAL must not mark robotd as restarting')

    def test_unsupported_robotd_is_rejected_before_any_bus_write(self):
        store, transport, controller = self.make(native=False)
        post(controller, {"action": "calibrate-all", "confirmed": True})
        job = wait_job(controller)
        self.assertEqual(job["status"], "error", job)
        self.assertIn("不支持", job["error"])
        self.assertEqual(transport.calls, [])
        self.assertEqual(store.data["calibration"]["calibration"]["joints"][0]["zero_raw"], 1000)

    def test_native_failure_never_writes_toml(self):
        store, transport, controller = self.make(native_error="bus write failed")
        post(controller, {"action": "calibrate-all", "confirmed": True})
        job = wait_job(controller)
        self.assertEqual(job["status"], "error", job)
        self.assertIn("bus write failed", job["error"])
        self.assertEqual(transport.capture_calls, [])
        self.assertEqual(store.data["calibration"]["calibration"]["joints"][0]["zero_raw"], 1000)

    def test_native_partial_failure_does_not_sync(self):
        store, transport, controller = self.make(native_partial="bus write failed")
        post(controller, {"action": "calibrate-all", "confirmed": True})
        job = wait_job(controller)
        self.assertEqual(job["status"], "error", job)
        self.assertIn("bus write failed", job["error"])
        self.assertEqual(transport.capture_calls, [])
        self.assertEqual(store.data["calibration"]["calibration"]["joints"][0]["zero_raw"], 1000)

    def test_relax_is_rejected_while_calibration_runs(self):
        store, transport, controller = self.make()
        controller.job = {"action": "calibrate-all", "status": "running"}
        with self.assertRaises(ControlError) as raised:
            post(controller, {"action": "relax"}, client="b" * 8)
        self.assertEqual(raised.exception.status, 409)

    def test_reboot_is_rejected_while_calibration_runs(self):
        store, transport, controller = self.make()
        controller.job = {"action": "calibrate-all", "status": "running"}
        with self.assertRaises(ControlError):
            post(controller, {"action": "reboot"}, client="c" * 8)

    def test_native_progress_tracks_current_joint(self):
        store = FakeStore(snapshot(native=True))
        gate = threading.Event()
        transport = FakeTransport(store, native_block=gate)
        controller = ServiceController(store, transport=transport, warm=False)
        post(controller, {"action": "calibrate-all", "confirmed": True})
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            job = controller.job or {}
            if job.get("calibration_all", {}).get("current_id"):
                break
            time.sleep(.01)
        self.assertEqual(job["phase"], "calibrating")
        self.assertIn("CAL 0/15", job["message"])
        self.assertEqual(job["calibration_all"]["current_id"], IDS[0])
        gate.set()
        job = wait_job(controller)
        self.assertEqual(job["status"], "completed", job)


if __name__ == "__main__":
    unittest.main()

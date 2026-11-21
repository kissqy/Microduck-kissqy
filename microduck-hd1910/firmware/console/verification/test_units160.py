"""Robot service rows: unit parsing, hardware presence, and autostart changes.

Runs without a robot. `systemctl` is replaced by a fake runner and the board's
sysfs/dev/proc tree by a temp directory, so the rules are checked against real
shapes: `masked` units, `not-found` units, `MemoryCurrent=[not set]`, and a ToF
whose bus is present while the sensor has not been asked anything.
"""
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import system_probe as probe
import units
from controls import ControlError
from service_control import validate

SHOW = """\
NRestarts=0
ExecStart={ path=/opt/robot/daemon/current/bin/robotd ; argv[]=/opt/robot/daemon/current/bin/robotd --socket /run/robotd.sock ; ignore_errors=no ; start_time=[n/a] ; stop_time=[n/a] ; pid=0 ; code=(null) ; status=0/0 }
MemoryCurrent=48230400
MainPID=812
UnitFileState=enabled
SubState=running
ActiveState=active
LoadState=loaded
Id=robotd.service

NRestarts=3
ExecStart=
MemoryCurrent=[not set]
MainPID=0
UnitFileState=masked
SubState=dead
ActiveState=inactive
LoadState=masked
Id=tofd.service

NRestarts=0
ExecStart=
MemoryCurrent=[not set]
MainPID=0
UnitFileState=
SubState=dead
ActiveState=inactive
LoadState=not-found
Id=updaterd.service
"""


class UnitParsingTests(unittest.TestCase):
    def run_show(self, text, names):
        calls = []

        def runner(command, **kwargs):
            calls.append(command)
            return SimpleNamespace(returncode=0, stdout=text, stderr="")

        rows, error = probe.read_units(names, runner=runner)
        self.assertEqual(error, "")
        self.assertEqual(len(calls), 1, "one systemctl call per sample, not one per unit")
        return rows, calls[0]

    def test_every_requested_unit_comes_back_in_order(self):
        rows, command = self.run_show(SHOW, ["robotd.service", "tofd.service", "updaterd.service"])
        self.assertEqual([row["unit"] for row in rows], ["robotd.service", "tofd.service", "updaterd.service"])
        # Asking about a unit this board does not have must still be one call.
        self.assertIn("robotd.service", command)

    def test_running_unit_keeps_pid_memory_and_restarts(self):
        rows, _ = self.run_show(SHOW, ["robotd.service"])
        row = rows[0]
        self.assertEqual((row["load"], row["active"], row["sub"], row["enabled"]),
                         ("loaded", "active", "running", "enabled"))
        self.assertEqual(row["pid"], 812)
        self.assertEqual(row["memory"], 48230400)
        self.assertEqual(row["executable"], "/opt/robot/daemon/current/bin/robotd")
        self.assertIs(row["executable_present"], False, "this PC does not have the board's robotd")

    def test_masked_unit_is_reported_not_hidden(self):
        rows, _ = self.run_show(SHOW, ["tofd.service"])
        row = rows[0]
        self.assertEqual(row["load"], "masked")
        self.assertEqual(row["enabled"], "masked")
        self.assertIsNone(row["pid"], "MainPID=0 is no process, not pid 0")
        self.assertIsNone(row["memory"], "[not set] is not a measurement")
        self.assertIsNone(row["executable_present"])

    def test_missing_unit_is_not_found_and_still_renders(self):
        rows, _ = self.run_show(SHOW, ["updaterd.service"])
        self.assertEqual(rows[0]["load"], "not-found")
        self.assertEqual(rows[0]["enabled"], "")

    def test_zero_restarts_is_a_measurement(self):
        # Only MainPID=0 means "no process"; a restart count of 0 is real data.
        rows, _ = self.run_show(SHOW, ["robotd.service"])
        self.assertEqual(rows[0]["restarts"], 0)

    def test_systemctl_failure_is_an_error_not_an_empty_success(self):
        def runner(command, **kwargs):
            raise OSError("systemctl: not found")

        rows, error = probe.read_units(["robotd.service"], runner=runner)
        self.assertEqual(rows, [])
        self.assertIn("systemctl", error)

    def test_no_units_asked_for_means_no_call(self):
        def runner(command, **kwargs):
            raise AssertionError("must not run systemctl for an empty list")

        self.assertEqual(probe.read_units([], runner=runner), ([], ""))


def bitmap(*bits, words=9):
    """Render a sysfs capability bitmap: 64-bit words, most significant first."""
    value = 0
    for bit in bits:
        value |= 1 << bit
    text = format(value, "0%dX" % (words * 16))
    return " ".join(text[i:i + 16] for i in range(0, len(text), 16))


class HardwareTests(unittest.TestCase):
    def board(self):
        root = tempfile.mkdtemp(prefix="duck-hw-")
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        return Path(root)

    def write(self, root, relative, text):
        path = root / relative.lstrip("/")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_empty_board_reports_absent_hardware_but_unverified_tof(self):
        root = self.board()
        reading = probe.read_hardware(str(root))
        self.assertFalse(reading["servo_bus"]["present"])
        self.assertFalse(reading["bluetooth"]["present"])
        self.assertFalse(reading["gamepad"]["present"])
        self.assertFalse(reading["camera"]["present"])
        self.assertFalse(reading["i2c3"]["present"])
        self.assertFalse(reading["audio_codec"]["present"])
        # The console never claims the sensor is missing: it has not asked I2C.
        self.assertIsNone(reading["tof"]["present"])

    def test_servo_port_follows_robotd_config(self):
        root = self.board()
        self.write(root, "etc/robot/feetech-ft5/robotd.toml",
                   "[bus]\nport = \"/dev/ttyUSB9\"\n\n[policy]\nenabled = true\n")
        (root / "dev").mkdir(exist_ok=True)
        self.write(root, "dev/ttyUSB9", "")
        reading = probe.read_hardware(str(root))
        self.assertTrue(reading["servo_bus"]["present"])
        self.assertEqual(reading["servo_bus"]["detail"], "/dev/ttyUSB9")

    def test_default_port_when_config_is_missing(self):
        reading = probe.read_hardware(str(self.board()))
        self.assertEqual(reading["servo_bus"]["detail"], "/dev/ttyS2")

    def test_camera_and_i2c_are_read_from_the_device_nodes(self):
        root = self.board()
        (root / "dev").mkdir(exist_ok=True)
        self.write(root, "dev/video0", "")
        self.write(root, "dev/i2c-3", "")
        self.write(root, "sys/class/video4linux/video0/name", "imx219 10-0010\n")
        reading = probe.read_hardware(str(root))
        self.assertTrue(reading["camera"]["present"])
        self.assertIn("imx219", reading["camera"]["detail"])
        self.assertTrue(reading["i2c3"]["present"])
        self.assertIsNone(reading["tof"]["present"])
        self.assertIn("0x29", reading["tof"]["detail"])

    def test_tof_detail_explains_a_missing_bus(self):
        reading = probe.read_hardware(str(self.board()))
        self.assertIn("总线不在", reading["tof"]["detail"])

    def test_audio_needs_the_codec_card_or_a_playback_pcm(self):
        root = self.board()
        self.write(root, "proc/asound/cards",
                   " 0 [rockchiphdmi0 ]: rockchip_hdmi0 - rockchip-hdmi0\n"
                   " 1 [aic3104       ]: aic3104 - aic3104\n")
        self.assertTrue(probe.read_hardware(str(root))["audio_codec"]["present"])

    def test_audio_absent_when_only_hdmi_is_bound(self):
        root = self.board()
        self.write(root, "proc/asound/cards",
                   " 0 [rockchiphdmi0 ]: rockchip_hdmi0 - rockchip-hdmi0\n")
        self.assertFalse(probe.read_hardware(str(root))["audio_codec"]["present"])

    def gamepad(self, root, name, keys, axes):
        self.write(root, "sys/class/input/event3/device/name", name + "\n")
        self.write(root, "sys/class/input/event3/device/capabilities/key", keys)
        self.write(root, "sys/class/input/event3/device/capabilities/abs", axes)

    def test_gamepad_needs_a_pad_button_and_two_axes(self):
        root = self.board()
        self.gamepad(root, "GameSir Nova 2 Lite", bitmap(0x130, 0x131, 0x133), bitmap(0, 1, 0x10))
        self.assertTrue(probe.read_hardware(str(root))["gamepad"]["present"])

    def test_keyboard_is_not_a_gamepad(self):
        root = self.board()
        # Keys present, but no absolute axes: a keyboard.
        self.gamepad(root, "AT Keyboard", bitmap(0x130, 30, 31), "")
        self.assertFalse(probe.read_hardware(str(root))["gamepad"]["present"])

    def test_unit_installed_distinguishes_a_mask_from_a_missing_unit(self):
        root = self.board()
        # A mask is a /dev/null symlink and is not the unit itself.
        (root / "etc/systemd/system").mkdir(parents=True)
        (root / "etc/systemd/system/tofd.service").symlink_to("/dev/null")
        self.assertFalse(probe.unit_installed("tofd.service", str(root)))
        # A real file behind the mask is.
        (root / "usr/lib/systemd/system").mkdir(parents=True)
        (root / "usr/lib/systemd/system/tofd.service").write_text("[Unit]\n", encoding="utf-8")
        self.assertTrue(probe.unit_installed("tofd.service", str(root)))
        self.assertFalse(probe.unit_installed("mediad.service", str(root)))

    def test_capability_bit_matches_sysfs_word_order(self):
        words = bitmap(0x130, 0x100, 3, words=9)
        self.assertTrue(probe.capability_bit(words, 0x130))
        self.assertTrue(probe.capability_bit(words, 0x100))
        self.assertTrue(probe.capability_bit(words, 3))
        self.assertFalse(probe.capability_bit(words, 0x131))
        self.assertFalse(probe.capability_bit(words, 575), "past the last word is not a bit")
        self.assertFalse(probe.capability_bit("", 0x130))
        self.assertFalse(probe.capability_bit("zzzz", 0x130))


class AutostartPlanTests(unittest.TestCase):
    def test_robotd_is_never_autostartable(self):
        commands, reason = units.autostart_plan("robotd.service", False, "enabled")
        self.assertEqual(commands, ())
        self.assertIn("不允许", reason)

    def test_unknown_unit_is_refused(self):
        self.assertEqual(units.autostart_plan("sshd.service", True, "disabled")[0], ())

    def test_the_catalogue_holds_only_upstream_units(self):
        # duck-webpanel was this project's own 8001 panel, not an upstream unit, so
        # it is not part of the robot's service list any more.
        self.assertNotIn("duck-webpanel.service", units.UNIT_NAMES)
        names = [row["unit"] for row in units.UNITS]
        self.assertEqual(len(names), len(set(names)), "no duplicate rows")
        self.assertIn("robotd.service", names)
        self.assertTrue(all(name.endswith(".service") for name in names))

    def test_enable_a_disabled_unit(self):
        commands, reason = units.autostart_plan("mediad.service", True, "disabled")
        self.assertEqual(reason, "")
        self.assertEqual(commands, (["enable", "--", "mediad.service"],))

    def test_masked_unit_is_unmasked_before_it_is_enabled(self):
        commands, reason = units.autostart_plan("tofd.service", True, "masked", True)
        self.assertEqual(reason, "")
        self.assertEqual(commands, (["unmask", "--", "tofd.service"],
                                    ["enable", "--", "tofd.service"]),
                         "enable alone leaves a masked unit off at boot")

    def test_masked_but_not_installed_is_never_unmasked(self):
        # This board's tofd.service is a /dev/null symlink with no unit file
        # behind it: unmasking then enabling fails with "does not exist" and
        # leaves the mask removed, which is a state the click did not ask for.
        commands, reason = units.autostart_plan("tofd.service", True, "masked", False)
        self.assertEqual(commands, (), "no unmask, no enable")
        self.assertIn("没有安装", reason)

    def test_enable_of_a_disabled_but_missing_unit_is_refused(self):
        commands, reason = units.autostart_plan("mediad.service", True, "disabled", False)
        self.assertEqual(commands, ())
        self.assertIn("没有安装", reason)

    def test_disable_a_masked_unit_is_refused_rather_than_faked(self):
        commands, reason = units.autostart_plan("tofd.service", False, "masked")
        self.assertEqual(commands, ())
        self.assertIn("屏蔽", reason)

    def test_already_in_the_requested_state_is_not_a_command(self):
        self.assertEqual(units.autostart_plan("mediad.service", True, "enabled")[0], ())
        self.assertEqual(units.autostart_plan("mediad.service", False, "disabled")[0], ())

    def test_not_found_and_static_cannot_be_changed(self):
        self.assertIn("未安装", units.autostart_plan("mediad.service", True, "not-found")[1])
        self.assertIn("内建", units.autostart_plan("mediad.service", True, "static")[1])


class ManualActionPlanTests(unittest.TestCase):
    def test_continuous_service_can_start_and_stop(self):
        self.assertEqual(units.manual_action_plan(
            "mediad.service", "start", "loaded", "disabled", "inactive"),
            (["start", "--", "mediad.service"], ""))
        self.assertEqual(units.manual_action_plan(
            "mediad.service", "stop", "loaded", "enabled", "active"),
            (["stop", "--", "mediad.service"], ""))

    def test_masked_or_missing_services_do_not_start(self):
        self.assertIn("屏蔽", units.manual_action_plan(
            "tofd.service", "start", "masked", "masked", "inactive")[1])
        self.assertIn("未安装", units.manual_action_plan(
            "tofd.service", "start", "not-found", "", "inactive", installed=False)[1])

    def test_repeated_and_in_flight_actions_are_not_issued(self):
        self.assertEqual(units.manual_action_plan(
            "padd.service", "start", "loaded", "enabled", "active"), ((), "already-active"))
        self.assertEqual(units.manual_action_plan(
            "padd.service", "stop", "loaded", "enabled", "inactive"), ((), "already-inactive"))
        self.assertIn("正在变更", units.manual_action_plan(
            "padd.service", "stop", "loaded", "enabled", "deactivating")[1])

    def test_oneshot_codec_has_no_stop_action(self):
        commands, reason = units.manual_action_plan(
            "aic3104-init.service", "stop", "loaded", "enabled", "active")
        self.assertEqual(commands, ())
        self.assertIn("不支持", reason)

    def test_unknown_units_are_never_actionable(self):
        self.assertEqual(units.manual_action_plan(
            "sshd.service", "stop", "loaded", "enabled", "active")[0], ())


class ValidationTests(unittest.TestCase):
    def command(self, **fields):
        return validate({**fields, "supported": True})

    def test_accepts_a_listed_unit(self):
        self.assertEqual(self.command(action="unit-autostart", unit="mediad.service", enabled=False)["unit"],
                         "mediad.service")

    def test_accepts_only_listed_manual_service_operations(self):
        command = self.command(action="unit-control", unit="mediad.service", operation="stop")
        self.assertEqual(command["operation"], "stop")
        with self.assertRaises(ControlError):
            self.command(action="unit-control", unit="sshd.service", operation="start")
        with self.assertRaises(ControlError):
            self.command(action="unit-control", unit="aic3104-init.service", operation="stop")
        with self.assertRaises(ControlError):
            self.command(action="unit-control", unit="mediad.service", operation="restart")

    def test_manual_control_requires_explicit_confirmation(self):
        with self.assertRaises(ControlError):
            validate({"action": "unit-control", "unit": "mediad.service",
                      "operation": "start"})

    def test_rejects_a_unit_outside_the_catalogue(self):
        with self.assertRaises(ControlError) as caught:
            self.command(action="unit-autostart", unit="sshd.service", enabled=True)
        self.assertEqual(caught.exception.status, 400)

    def test_rejects_robotd_with_a_conflict(self):
        with self.assertRaises(ControlError) as caught:
            self.command(action="unit-autostart", unit="robotd.service", enabled=False)
        self.assertEqual(caught.exception.status, 409)

    def test_requires_a_real_boolean(self):
        with self.assertRaises(ControlError):
            validate({"action": "unit-autostart", "unit": "mediad.service", "enabled": "true", "supported": True})

    def test_requires_the_explicit_confirmation_flag(self):
        with self.assertRaises(ControlError):
            validate({"action": "unit-autostart", "unit": "mediad.service", "enabled": True})

    def test_probe_needs_no_unit_but_needs_confirmation(self):
        self.assertEqual(self.command(action="tof-probe")["action"], "tof-probe")
        with self.assertRaises(ControlError):
            validate({"action": "tof-probe"})

    def test_sudo_password_is_allowed_only_on_management_actions(self):
        accepted = validate({"action": "unit-autostart", "unit": "mediad.service",
                             "enabled": True, "supported": True, "sudo_password": "x"})
        self.assertEqual(accepted["unit"], "mediad.service")


class FakeLog:
    def __init__(self):
        self.lines = []

    def add(self, *args):
        self.lines.append(args)


class FakeStore:
    def __init__(self, data):
        import copy
        self.data = copy.deepcopy(data)
        self.service_operation = False
        self.connection_paused = None
        self.system_log = FakeLog()
        self.commands = []

    def snapshot(self, record=True):
        import copy
        return copy.deepcopy(self.data)

    def ingest(self, event):
        pass

    def record_service_command(self, job):
        self.commands.append(job)


class FakeTransport:
    """Stands in for the SSH channel; records what would have been run."""

    def __init__(self, fail_readback=None):
        self.fail_readback = fail_readback
        self.calls = []

    def autostart(self, unit, enabled, password=None):
        self.calls.append((unit, enabled, password))
        if self.fail_readback:
            raise ControlError(self.fail_readback, 503)
        return {"accepted": True, "unit": unit, "enabled": enabled,
                "message": "%s 已改" % unit}

    def control_unit(self, unit, operation, password=None):
        self.calls.append(("unit-control", unit, operation, password))
        return {"accepted": True, "unit": unit, "operation": operation,
                "message": "%s 已%s" % (unit, "启动" if operation == "start" else "停止")}

    def tof_probe(self, password=None):
        self.calls.append(("tof-probe", password))
        return {"accepted": True, "found": ["29"], "message": "I²C3 上发现 0x29"}


class UnitControlTransportTests(unittest.TestCase):
    def transport(self, before, after):
        from service_control import ServiceTransport
        transport = object.__new__(ServiceTransport)
        states = iter((before, after))
        transport.unit_runtime_state = lambda unit, password=None: next(states)
        transport.unit_installed = lambda unit, password=None: True
        calls = []
        transport._manage = lambda command, password=None, **kwargs: calls.append(command)
        return transport, calls

    def test_systemctl_property_options_precede_the_unit_separator(self):
        from service_control import ServiceTransport
        transport = object.__new__(ServiceTransport)
        calls = []

        def manage(command, *args, **kwargs):
            calls.append(command)
            return {"message": "LoadState=loaded\nActiveState=inactive\nUnitFileState=disabled\n"}

        transport._manage = manage
        state = transport.unit_runtime_state("mediad.service")
        self.assertEqual(state["LoadState"], "loaded")
        self.assertLess(calls[0].index("-p"), calls[0].index("--"))
        self.assertEqual(calls[0][-1], "mediad.service")

        self.assertEqual(transport.unit_state("mediad.service"), "disabled")
        self.assertLess(calls[1].index("-p"), calls[1].index("--"))
        self.assertEqual(calls[1][-1], "mediad.service")

    def test_start_and_stop_are_read_back(self):
        inactive = {"LoadState": "loaded", "UnitFileState": "enabled", "ActiveState": "inactive"}
        active = {**inactive, "ActiveState": "active"}
        transport, calls = self.transport(inactive, active)
        result = transport.control_unit("mediad.service", "start")
        self.assertTrue(result["accepted"])
        self.assertEqual(calls, [["/bin/systemctl", "start", "--", "mediad.service"]])

        transport, calls = self.transport(active, inactive)
        result = transport.control_unit("mediad.service", "stop")
        self.assertTrue(result["accepted"])
        self.assertEqual(calls, [["/bin/systemctl", "stop", "--", "mediad.service"]])

    def test_masked_start_and_bad_readback_are_not_reported_as_success(self):
        masked = {"LoadState": "masked", "UnitFileState": "masked", "ActiveState": "inactive"}
        transport, calls = self.transport(masked, masked)
        with self.assertRaises(ControlError):
            transport.control_unit("tofd.service", "start")
        self.assertEqual(calls, [])

        inactive = {"LoadState": "loaded", "UnitFileState": "disabled", "ActiveState": "inactive"}
        transport, _ = self.transport(inactive, inactive)
        with self.assertRaises(ControlError):
            transport.control_unit("mediad.service", "start")

    def test_oneshot_start_uses_exit_status_instead_of_active_state(self):
        inactive = {"LoadState": "loaded", "UnitFileState": "enabled", "ActiveState": "inactive"}
        exited = {**inactive, "SubState": "dead", "Result": "success", "ExecMainStatus": "0"}
        transport, calls = self.transport(inactive, exited)
        self.assertTrue(transport.control_unit("aic3104-init.service", "start")["accepted"])
        self.assertEqual(calls, [["/bin/systemctl", "start", "--", "aic3104-init.service"]])


def controller_store(tofd_active="inactive"):
    return {"bus": {"mode": "commissioning", "phase": "ready", "torque_state": "off",
                     "motion": None, "power_pending": False, "torque_off_pending": None},
            "servos": [], "service_sample_fresh": True, "service_compatible": True,
            # The units channel, not `system`: in --feetech mode `system` is
            # robotd's telemetry and carries no unit rows.
            "units": {"units": [{"unit": "tofd.service", "active": tofd_active,
                                 "enabled": "masked", "load": "masked"}]}}


class ControllerTests(unittest.TestCase):
    def controller(self, tofd_active="inactive", **kwargs):
        from service_control import ServiceController
        store = FakeStore(controller_store(tofd_active))
        transport = FakeTransport(**kwargs)
        return store, transport, ServiceController(store, transport=transport, warm=False)

    def send(self, controller, command, seq=1):
        return controller.handle({"client": "test-client-160", "seq": seq, "command": command})

    def wait(self, controller, timeout=3):
        import time
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            job = controller.job
            if job and job.get("status") != "running":
                return job
            time.sleep(0.01)
        self.fail("job did not finish")

    def test_autostart_runs_without_fresh_motor_telemetry(self):
        # robotd down means no sample at all; editing a unit file must still work.
        store, transport, controller = self.controller()
        store.data["service_sample_fresh"] = False
        store.data["bus"] = {}
        self.send(controller, {"action": "unit-autostart", "unit": "mediad.service",
                               "enabled": True, "supported": True})
        job = self.wait(controller)
        self.assertEqual(job["status"], "completed", job)
        self.assertEqual(transport.calls, [("mediad.service", True, None)])

    def test_manual_start_runs_with_robotd_down(self):
        store, transport, controller = self.controller()
        store.data["service_sample_fresh"] = False
        store.data["bus"] = {}
        self.send(controller, {"action": "unit-control", "unit": "mediad.service",
                               "operation": "start", "supported": True})
        job = self.wait(controller)
        self.assertEqual(job["status"], "completed", job)
        self.assertEqual(transport.calls, [("unit-control", "mediad.service", "start", None)])

    def test_robotd_stop_refuses_any_unconfirmed_or_busy_state(self):
        unsafe = (
            lambda s: s.update(service_sample_fresh=False),
            lambda s: s["bus"].update(phase="moving"),
            lambda s: s["bus"].update(torque_state="single_joint_enabled"),
            lambda s: s["bus"].update(motion={"action": "move"}),
        )
        for mutate in unsafe:
            store, transport, controller = self.controller()
            mutate(store.data)
            with self.subTest(data=store.data), self.assertRaises(ControlError):
                self.send(controller, {"action": "unit-control", "unit": "robotd.service",
                                       "operation": "stop", "supported": True})
            self.assertEqual(transport.calls, [])

    def test_robotd_stop_is_allowed_only_after_policy_and_torque_are_off(self):
        store, transport, controller = self.controller()
        store.data["bus"] = {"mode": "motion", "phase": "control", "fresh_sample": True,
                             "policy_enabled": False, "torque_off_pending": False,
                             "native": {"torque_state_confirmed": False,
                                        "hd1910": {"restore_pending": False,
                                                   "temporary_gains_applied": False}}}
        self.send(controller, {"action": "unit-control", "unit": "robotd.service",
                               "operation": "stop", "supported": True})
        job = self.wait(controller)
        self.assertEqual(job["status"], "completed", job)
        self.assertEqual(transport.calls, [("unit-control", "robotd.service", "stop", None)])

    def test_policy_enabled_robotd_cannot_be_stopped_even_with_torque_off(self):
        store, transport, controller = self.controller()
        store.data["bus"] = {"mode": "motion", "phase": "control", "fresh_sample": True,
                             "policy_enabled": True, "torque_off_pending": False,
                             "native": {"torque_state_confirmed": False}}
        with self.assertRaises(ControlError):
            self.send(controller, {"action": "unit-control", "unit": "robotd.service",
                                   "operation": "stop", "supported": True})
        self.assertEqual(transport.calls, [])

    def test_robotd_cannot_be_toggled_through_the_api(self):
        store, transport, controller = self.controller()
        with self.assertRaises(ControlError) as caught:
            self.send(controller, {"action": "unit-autostart", "unit": "robotd.service",
                                   "enabled": False, "supported": True})
        self.assertEqual(caught.exception.status, 409)
        self.assertEqual(transport.calls, [])

    def test_a_readback_mismatch_is_reported_as_unconfirmed(self):
        store, transport, controller = self.controller(fail_readback="tofd.service 回读为 masked，不是 enabled")
        self.send(controller, {"action": "unit-autostart", "unit": "tofd.service",
                               "enabled": True, "supported": True})
        job = self.wait(controller)
        self.assertEqual(job["status"], "error")
        self.assertIn("回读", job["error"])

    def test_tof_probe_is_refused_while_tofd_owns_the_bus(self):
        store, transport, controller = self.controller(tofd_active="active")
        with self.assertRaises(ControlError) as caught:
            self.send(controller, {"action": "tof-probe", "supported": True})
        self.assertEqual(caught.exception.status, 409)
        self.assertIn("I²C3", str(caught.exception))
        self.assertEqual(transport.calls, [], "the probe must not reach the bus")

    def test_tof_probe_runs_when_tofd_is_down(self):
        store, transport, controller = self.controller(tofd_active="inactive")
        self.send(controller, {"action": "tof-probe", "supported": True})
        job = self.wait(controller)
        self.assertEqual(job["status"], "completed", job)
        self.assertEqual(transport.calls, [("tof-probe", None)])

    def test_the_same_unit_toggle_cannot_be_replayed(self):
        store, transport, controller = self.controller()
        self.send(controller, {"action": "unit-autostart", "unit": "mediad.service",
                               "enabled": True, "supported": True}, seq=7)
        self.wait(controller)
        with self.assertRaises(ControlError):
            self.send(controller, {"action": "unit-autostart", "unit": "mediad.service",
                                   "enabled": True, "supported": True}, seq=7)
        self.assertEqual(len(transport.calls), 1)


if __name__ == "__main__":
    unittest.main()

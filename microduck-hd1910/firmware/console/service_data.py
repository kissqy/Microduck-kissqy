"""R17 display adapter; older reports remain readable for migration diagnostics."""
import math

from release_identity import BUILD

from management_profile import supports_feature


def finite(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def adapt_service(result, report, calibration, sample_elapsed_ms):
    channels = result["channels"]
    active = channels["bus"]["status"] == "live"
    commissioning = report.get("mode") == "commissioning"
    sample = report.get("last_sample") or {}
    diagnostic = report.get("native") or report
    source_rows = sample.get("servos", []) if commissioning else diagnostic.get("joints", [])
    raw_rows = {r.get("id"): r for r in source_rows if isinstance(r, dict)}
    if len(raw_rows) != len(source_rows): raw_rows = {}
    server_age = diagnostic.get("sample_age_ms")
    if commissioning:
        a, b = report.get("updated_at_us"), sample.get("at_us")
        server_age = max(0, (a-b)/1000) if finite(a) and finite(b) else None
    local_age = channels["bus"].get("age_ms") or 0
    age = max(sample_elapsed_ms or 0, server_age+local_age) if finite(server_age) else None
    fresh = active and age is not None and age < 500 and report.get("phase") not in ("configuration_error", "waiting_for_bus", "read_error", "configuring_uart")
    if not commissioning and report.get("fresh_sample") is False:
        fresh = False
    # A changing bus-status cycle proves the control loop is still running even
    # while the measured pose is old. Only an existing held gait may continue;
    # this does not authorize a new start or replace the control-link watchdog.
    continuable = (active and finite(sample_elapsed_ms) and sample_elapsed_ms < 500
                  and supports_feature(report, "coast") and report.get("mode") == "motion"
                  and report.get("phase") == "control"
                  and report.get("read_recovery") in ("fresh", "coasting", "holding")
                  and report.get("policy_enabled") is True and report.get("homed") is True
                  and not report.get("torque_off_pending")
                  and diagnostic.get("torque_state_confirmed") is True)
    mapping = (calibration.get("calibration") or {}).get("joints", [])
    calibrated = {r.get("id"): r for r in mapping if isinstance(r, dict)}
    saved_count=sum(r.get("calibrated") is True and r.get("name")==next((s["name"] for s in result["servos"] if s["id"]==r.get("id")),None) for r in calibrated.values())
    motion = report.get("motion") or {}
    state = report.get("torque_state")
    for row in result["servos"]:
        raw, cal = raw_rows.get(row["id"], {}), calibrated.get(row["id"], {})
        pos = raw.get("position_raw")
        valid = type(pos) is int and -32767 <= pos <= 32767 and (raw.get("joint") or raw.get("name")) == row["name"]
        device_fresh = commissioning or raw.get('feedback_fresh') is not False
        row.update(source="robot.busStatus", status="live" if fresh and valid and device_fresh else "stale" if valid else "unavailable",
                   calibrated=False, position_raw=pos, speed_raw=raw.get("speed_raw"), load_raw=raw.get("load_raw"),
                   current_raw=raw.get("current_raw"), voltage_v=raw.get("voltage_v", raw.get("volts")),
                   temperature_c=raw.get("temperature_c"), current_source="飞特原始计数；未经电流单位标定",
                   encoder_deg=(pos-2048)*360/4096 if valid else None, calibration=cal or None,
                   sample_age_ms=age, moving=raw.get("moving"))
        row["current_ma"] = raw.get("current_ma") if not commissioning else None
        if commissioning:
            row.update(angle_deg=None, target_deg=None, error_deg=None, velocity_rpm=None)
            okay = (valid and raw.get("calibrated") is True and cal.get("calibrated") is True
                    and cal.get("name") == row["name"] and type(cal.get("zero_raw")) is int
                    and 0 <= cal["zero_raw"] <= 4095 and type(cal.get("direction")) is int and cal["direction"] in (-1, 1)
                    and finite(cal.get("min_rad")) and finite(cal.get("max_rad")) and cal["min_rad"] < cal["max_rad"])
            if okay:
                row["angle_deg"] = (pos-cal["zero_raw"])*360/4096*cal["direction"]
                row["calibrated"] = True
            goal = motion.get("target_raw") if motion.get("id") == row["id"] else None
            row["goal_position_raw"] = goal
            if okay and finite(goal):
                row["target_deg"] = (goal-cal["zero_raw"])*360/4096*cal["direction"]
                row["error_deg"] = row["angle_deg"]-row["target_deg"]
            # This is the service's last confirmed switch state, not a per-tick register poll.
            row["torque_enabled"] = (False if state == "off" else row["id"] == motion.get("id") if state == "single_joint_enabled" else None) if active else None
        else:
            row["calibrated"] = raw.get("calibrated") is True
            row.update(angle_deg=None, target_deg=None, error_deg=None)
            if finite(raw.get("position_rad")): row["angle_deg"] = math.degrees(raw["position_rad"])
            if finite(raw.get("velocity_rad_s")): row["velocity_rpm"] = raw["velocity_rad_s"]*30/math.pi
            row["torque_enabled"] = diagnostic.get("torque_state_confirmed") if active else None
            if channels["state"]["status"] == "live":
                targets = result["state"].get("targets", [])
                if len(targets) == 15 and finite(targets[row["index"]]): row["target_deg"] = math.degrees(targets[row["index"]])
                if finite(row.get("angle_deg")) and finite(row.get("target_deg")): row["error_deg"] = row["angle_deg"]-row["target_deg"]
    if commissioning:
        imu = sample.get("imu") or {}
        g = imu.get("gravity")
        g = g if isinstance(g, list) and len(g) == 3 and all(finite(v) for v in g) else None
        result["imu"].update(gravity=g, gyro=imu.get("gyro_rad_s"), quat=imu.get("quaternion_wxyz"),
                             ready=imu.get("ready"), sequence=imu.get("sequence"), age_ms=imu.get("age_ms"),
                             age_upper_bound_ms=imu.get("age_upper_bound_ms"), firmware_status=imu.get("status"),
                             mount_verified=report.get("imu_mount_verified") is True,
                             status="live" if fresh and g and imu.get("valid") is True else "stale" if g else "unavailable",
                             source="robotd / "+"FT6"+" / 当前安装变换", reason=None if fresh else "等待新鲜的整链样本")
        result["imu"]["roll_deg"] = math.degrees(math.atan2(-g[1], -g[2])) if g else None
        result["imu"]["pitch_deg"] = math.degrees(math.atan2(g[0], math.hypot(g[1], g[2]))) if g else None
    else:
        result["imu"]["mount_verified"] = diagnostic.get("imu_mount_verified") is True
        result["imu"]["age_upper_bound_ms"] = diagnostic.get("imu_age_upper_bound_ms")
        result["imu"]["firmware_status"] = diagnostic.get("imu_status")
    count = sum(r["calibrated"] for r in result["servos"])
    result.update(bus=report, calibration=calibration, service_sample_fresh=fresh, service_sample_age_ms=age,
                  service_walk_continuable=continuable,
                  calibrated_count=count, saved_calibrated_count=saved_count, pose_calibrated=count == 15, read_only=False,
                  service_compatible=supports_feature(report, "supported"))
    return result

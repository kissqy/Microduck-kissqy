"""Microduck 590b986 observer. No actuator writes; missing is never zero."""
import copy
import math
import threading
import time
from collections import deque

BASELINE = "1fa84386f07884e27866411bc1ba166977bced95"
from release_identity import CONSOLE_VERSION
VERSION = CONSOLE_VERSION
IDS = [20, 21, 22, 23, 24, 30, 31, 32, 33, 34, 10, 11, 12, 13, 14]
NAMES = ["left_hip_yaw", "left_hip_roll", "left_hip_pitch", "left_knee", "left_ankle",
         "neck_pitch", "head_pitch", "head_yaw", "head_roll", "mouth",
         "right_hip_yaw", "right_hip_roll", "right_hip_pitch", "right_knee", "right_ankle"]
LABELS = ["左髋旋转", "左髋侧摆", "左髋俯仰", "左膝", "左踝", "颈部俯仰", "头部俯仰",
          "头部转向", "头部侧倾", "嘴巴", "右髋旋转", "右髋侧摆", "右髋俯仰", "右膝", "右踝"]
HOME = [0, -.0873, -.4579, -.0049, .4530, .3491, .3491, 0, 0, 0, 0, .0873, .4579, .0049, -.4530]
TTL = {"state": 1.5, "health": 5, "tof": 2, "system": 7, "capabilities": 20, "bus": 1.5, "calibration": float("inf")}


def number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def vector(value, size):
    if isinstance(value, list) and len(value) == size and all(number(x) is not None for x in value):
        return value
    return None


def item(values, index):
    return number(values[index]) if isinstance(values, list) and index < len(values) else None


def deg(value):
    return math.degrees(value) if number(value) is not None else None


def attitude(gravity):
    g = vector(gravity, 3)
    if not g or sum(x*x for x in g) < .01:
        return None, None
    # Trunk frame: x forward, y left, z up. Consistent with inverse RPY * world down.
    return math.degrees(math.atan2(-g[1], -g[2])), math.degrees(math.atan2(g[0], math.hypot(g[1], g[2])))


class Store:
    def __init__(self, mode="local", clock=time.monotonic, control_enabled=False):
        self.clock, self.mode = clock, mode
        self.control_enabled = control_enabled
        self.started = clock()
        self.lock = threading.RLock()
        self.data = {}
        self.channels = {k: {"status": "waiting", "at": None, "error": "", "seq": 0} for k in TTL}
        self.events = deque(maxlen=150)
        self.service_commands = deque(maxlen=150)
        self.system_log = None
        self.service_operation = False
        self.connection_paused = threading.Event()
        self.history = deque(maxlen=1200)  # 120 seconds at 10 Hz, in RAM only.
        self.last_record = -1
        self.inspection_active = mode != "service"
        self.gait_capture_until = -1
        self.bus_sample_key = None
        self.bus_sample_at = None

    def ingest(self, event):
        if not isinstance(event, dict) or event.get("channel") not in TTL:
            return
        channel = event["channel"]
        with self.lock:
            c = self.channels[channel]
            previous = (c["status"], c["error"])
            subscription = (event.get("data") or {}).get("subscription") if isinstance(event.get("data"), dict) else None
            if channel == "tof" and "error" not in event and isinstance(subscription, dict):
                # An acknowledgement is service metadata, never a measured frame.
                first = "subscription" not in self.data.get(channel, {})
                self.data.setdefault(channel, {})["subscription"] = copy.deepcopy(subscription)
                age = self.clock() - c["at"] if c["at"] is not None else None
                c.update(status="waiting" if age is None else "stale" if age > TTL[channel] else "live", error="")
                if first or previous != (c["status"], c["error"]):
                    self.events.append({"at": time.time(), "channel": channel, "level": c["status"],
                                        "message": "测距服务已连接，等待有效测距数据"})
                return
            if "error" in event:
                c["status"], c["error"] = "error", str(event["error"])[:500]
            elif isinstance(event.get("data"), dict):
                self.data[channel] = copy.deepcopy(event["data"])
                if channel == "bus":
                    sample = event["data"].get("last_sample") or {}
                    key = (sample.get("at_us"), sample.get("cycle", event["data"].get("cycle")), event["data"].get("mode"))
                    if key != self.bus_sample_key:
                        self.bus_sample_key, self.bus_sample_at = key, self.clock()
                c.update(status="live", error="", at=self.clock(), seq=c["seq"] + 1)
            else:
                return
            if previous != (c["status"], c["error"]):
                self.events.append({"at": time.time(), "channel": channel, "level": c["status"],
                                    "message": c["error"] or "数据连接已恢复"})

    def disconnected(self, message):
        for name in TTL:
            self.ingest({"channel": name, "error": message})

    def peek(self):
        return self.snapshot(record=False)

    def snapshot(self, record=True):
        with self.lock:
            now = self.clock()
            channels = copy.deepcopy(self.channels)
            for name, c in channels.items():
                at = c.pop("at")
                c["age_ms"] = round((now - at) * 1000) if at is not None else None
                if c["status"] == "live" and now - at > TTL[name]:
                    c["status"] = "stale"
            state = copy.deepcopy(self.data.get("state", {}))
            health = copy.deepcopy(self.data.get("health", {}))
            extension = state.get("diagnostics") or {}
            slow = extension.get("slow") or {}
            slow_age = number(slow.get("age_ms"))
            temps_fresh = slow_age is not None and slow_age <= 5000
            servos = []
            for index, (sid, name, label) in enumerate(zip(IDS, NAMES, LABELS)):
                angle = item(state.get("joints"), index)
                target = item(state.get("targets"), index)
                row = {"id": sid, "name": name, "label": label, "index": index,
                       "group": "left" if index < 5 else "head" if index < 10 else "right",
                       "angle_deg": deg(angle), "target_deg": deg(target),
                       "error_deg": deg(angle-target) if angle is not None and target is not None else None,
                       "velocity_rpm": None, "current_ma": item(extension.get("currents_ma"), index),
                       "temperature_c": item(slow.get("temps_c"), index) if temps_fresh else None,
                       "voltage_v": None, "pwm_percent": None, "current_ratio_percent": None,
                       "torque_enabled": None, "hardware_error": None,
                       "status": channels["state"]["status"] if angle is not None else "unavailable",
                       "source": "robot.state", "temperature_age_ms": slow_age,
                       "current_source": "robot.state.diagnostics / 绝对值" if extension else "未导出"}
                velocity = item(extension.get("velocities"), index)
                if velocity is not None:
                    row["velocity_rpm"] = velocity * 60 / (2*math.pi)
                # The hottest joint alone is measured in the unmodified health response.
                thermal = health.get("motors") or {}
                if not extension and thermal.get("hottest") == name:
                    row["temperature_c"] = number(thermal.get("max_c")) if channels["health"]["status"] == "live" else None
                    row["temperature_source"] = "robot.health / 仅最高温关节"
                servos.append(row)
            gravity = vector((state.get("safety") or {}).get("gravity"), 3)
            raw_imu = extension.get("imu") or {}
            imu_source = "robot.state.diagnostics" if raw_imu else "robot.state.safety.gravity"
            roll, pitch = attitude(gravity)
            imu_status = channels["state"]["status"]
            imu_reason = raw_imu.get("reason") or raw_imu.get("error")
            if imu_status == "live":
                imu_health = health.get("imu") or {}
                if roll is None or pitch is None:
                    imu_status, imu_reason = "unavailable", "没有有效重力方向"
                elif channels["health"]["status"] == "live":
                    stale_blocks = number(imu_health.get("consecutive_stale_blocks"))
                    if stale_blocks is not None and stale_blocks >= 25:
                        imu_status, imu_reason = "stale", "官方报告 IMU 连续旧样本达到 25，不能当作新姿态"
                    elif imu_health.get("ready") is False:
                        imu_status, imu_reason = "waiting", "官方 SFLP 融合尚未就绪"
            imu = {"gravity": gravity, "roll_deg": roll, "pitch_deg": pitch,
                   "gyro": vector(raw_imu.get("gyro"), 3), "quat": vector(raw_imu.get("quat"), 4),
                   "source": imu_source, "health": health.get("imu"),
                   "status": imu_status, "reason": imu_reason,
                   "ready": raw_imu.get("ready"), "sequence": raw_imu.get("sequence"), "age_ms": raw_imu.get("age_ms")}
            result = {"schema": "microduck-console/v1", "service_operation": self.service_operation, "connection_paused": self.connection_paused.is_set(), "version": VERSION, "baseline": BASELINE,
                      "mode": self.mode, "read_only": not self.control_enabled, "at": time.time(), "uptime": now-self.started,
                      "channels": channels, "state": state, "health": health, "imu": imu,
                      "capabilities": copy.deepcopy(self.data.get("capabilities", {})),
                      "tof": copy.deepcopy(self.data.get("tof", {})), "servos": servos,
                      "system": copy.deepcopy(self.data.get("system", {})), "events": list(self.events),
                      "extended": extension.get("schema") == "microduck-observer/v1",
                      "pose_calibrated": True}
            if self.mode == "service":
                from service_data import adapt_service
                elapsed = (now-self.bus_sample_at)*1000 if self.bus_sample_at is not None else None
                adapt_service(result, copy.deepcopy(self.data.get("bus", {})),
                              copy.deepcopy(self.data.get("calibration", {})), elapsed)
            # Reuse existing loop reports for recording; never start another
            # serial reader when the motion loop is already collecting data.
            bus = result.get("bus", {})
            loop_capture = (self.mode == "service" and bus.get("mode") == "motion"
                            and number(bus.get("cycle")) is not None and channels["bus"]["status"] == "live")
            if record and (self.inspection_active or loop_capture or now < self.gait_capture_until) and now - self.last_record >= .095:
                frame = {k: v for k, v in result.items() if k != "events"}
                if "bus" in frame: frame["bus"]={k:v for k,v in frame["bus"].items() if k not in ("last_failure","diagnostics")}
                self.history.append(frame)
                self.last_record = now
            return result

    def handle(self, payload):
        if not isinstance(payload,dict) or set(payload)!={"enabled"} or type(payload["enabled"]) is not bool:
            raise ValueError("检测开关无效")
        with self.lock:
            if payload["enabled"] and not self.inspection_active: self.history.clear()
            self.inspection_active=payload["enabled"]
            return {"enabled":self.inspection_active}

    def capture_gait(self, start=False):
        """Keep a bounded motion trace, including two seconds after release."""
        with self.lock:
            now = self.clock()
            if start and not self.inspection_active and now >= self.gait_capture_until:
                self.history.clear()
                self.last_record = -1
            self.gait_capture_until = now + 2
            if start:
                self.snapshot()  # record the Home baseline before the first control RPC

    def record_service_command(self, job):
        with self.lock:
            self.service_commands.append(copy.deepcopy({**job, "recorded_at": time.time()}))

    def recording(self):
        with self.lock:
            return {"schema": "microduck-console-recording/v1", "baseline": BASELINE,
                    "mode": self.mode, "created_at": time.time(), "frames": list(self.history) or [self.snapshot()],
                    "service_commands": list(self.service_commands),
                    "last_failure": copy.deepcopy(self.data.get("bus", {}).get("last_failure"))}

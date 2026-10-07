"""Read-only 590b986 collector; can execute in memory over SSH. Python 3.9+."""
import json
import math
import os
import re
import socket
import sys
import threading
import time
from pathlib import Path

MAX_LINE = 262144
# The SSH-only envelope adds at most 25 bytes to a complete IPC line.
MAX_COLLECTOR_LINE = MAX_LINE + 64
TOF_IDLE_SECONDS = 5
SURROGATE_ESCAPE = re.compile(br'\\u[dD][89a-fA-F][0-9a-fA-F]{2}')


class IPCMessage(dict):
    def __init__(self, line):
        self.line = line
        self.nonfinite = False
        # json.loads(bytes) accepts BOMs, UTF-16/32 and surrogate-pass UTF-8.
        # Those bytes cannot safely become a nested UTF-8 JSON object. Escaped
        # surrogates also need the original output encoder's Unicode checks.
        self.reencode = (line.startswith(b'\xef\xbb\xbf') or b'\0' in line[:4]
                         or SURROGATE_ESCAPE.search(line) is not None)
        try:
            text = line.decode("utf-8")
        except UnicodeDecodeError:
            self.reencode = True
        value = json.loads(line if self.reencode else text,
                           parse_float=self.number, parse_constant=self.number)
        if not isinstance(value, dict):
            raise ValueError("IPC 消息必须是对象")
        super().__init__(value)

    def number(self, text):
        value = float(text)
        if not math.isfinite(value):
            self.nonfinite = True
        return value


def json_line(reader):
    line = reader.readline(MAX_LINE + 1)
    if not line:
        raise ConnectionError("连接已关闭")
    if len(line) > MAX_LINE or not line.endswith(b"\n"):
        raise ValueError("IPC 消息超出上限")
    return IPCMessage(line)


class CollectorOutput:
    """Preserve validated IPC bytes; only the desktop unwraps their payload."""
    prefixes = {
        ("state", "params"): b'{"channel":"state","rpc":',
        ("tof", "params"): b'{"channel":"tof","rpc":',
        ("bus", "result"): b'{"channel":"bus","rpc":',
    }

    def __init__(self, stream=None):
        self.stream = sys.stdout.buffer if stream is None else stream
        self.lock = threading.Lock()

    def _write(self, line):
        try:
            remaining = memoryview(line)
            while remaining:
                written = self.stream.write(remaining)
                if written is None or written <= 0:
                    raise OSError("采集输出已关闭")
                remaining = remaining[written:]
            self.stream.flush()
        except (BrokenPipeError, OSError):
            os._exit(0)

    def __call__(self, event):
        with self.lock:
            self._write((json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8"))

    def ipc(self, channel, message, field):
        # Retain allow_nan=False exactly, including ignored RPC fields: the old
        # encoder rejected nonfinite payloads, not nonfinite fields it discarded.
        if message.nonfinite or message.reencode:
            self({"channel": channel, "data": message[field]})
            return
        with self.lock:
            self._write(self.prefixes[channel, field] + message.line[:-1] + b'}\n')


def emit_ipc(emit, channel, message, field):
    # Local agent.run callbacks still receive ordinary channel/data events.
    if isinstance(emit, CollectorOutput):
        emit.ipc(channel, message, field)
    else:
        emit({"channel": channel, "data": message[field]})


def connect(path):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(3)
    try:
        s.connect(path)
    except Exception:
        s.close()
        raise
    return s


def subscription(path, method, notification, hz, emit, stop, channel):
    tof_refreshed = False
    while not stop.is_set():
        accepted = False
        try:
            with connect(path) as s:
                request = {"jsonrpc": "2.0", "id": 1, "method": method}
                if hz:
                    request["params"] = {"hz": hz}
                s.sendall(json.dumps(request).encode() + b"\n")
                # A quiet robot can be waiting for missing servos for minutes. Do not
                # repeatedly tear down its subscriber; freshness is tracked by the UI.
                # tofd only reports sensor availability in its subscribe response.
                # Refresh once per period without frames. Frozen tofd only retires
                # a disconnected subscriber when it next emits a frame, so polling
                # quiet subscriptions repeatedly would accumulate server sockets.
                # This only reads IPC; it never accesses or reinitializes I2C.
                s.settimeout(TOF_IDLE_SECONDS if channel == "tof" and not tof_refreshed else None)
                with s.makefile("rb") as reader:
                    while not stop.is_set():
                        msg = json_line(reader)
                        if msg.get("id") == 1:
                            if msg.get("error"):
                                raise ValueError(str(msg["error"]))
                            if not (msg.get("result") or {}).get("accepted"):
                                raise ValueError("订阅未获接受")
                            accepted = True
                            if channel == "tof":
                                emit({"channel": channel, "data": {"subscription": msg["result"]}})
                            elif channel == "state":
                                emit({"channel": "capabilities", "data": msg["result"]})
                        elif msg.get("method") == notification and isinstance(msg.get("params"), dict):
                            if channel == "tof" and tof_refreshed:
                                tof_refreshed = False
                                s.settimeout(TOF_IDLE_SECONDS)
                            emit_ipc(emit, channel, msg, "params")
        except socket.timeout as exc:
            # A connected sensor service may have no frames yet. Preserve its
            # availability reason instead of replacing it with a socket timeout.
            if channel == "tof" and accepted:
                tof_refreshed = True
            else:
                emit({"channel": channel, "error": str(exc)})
        except Exception as exc:
            emit({"channel": channel, "error": str(exc)})
        stop.wait(2)


def health_loop(path, emit, stop):
    while not stop.is_set():
        try:
            with connect(path) as s, s.makefile("rb") as reader:
                n = 0
                while not stop.is_set():
                    n += 1
                    s.sendall(json.dumps({"jsonrpc": "2.0", "id": n, "method": "robot.health"}).encode() + b"\n")
                    msg = json_line(reader)
                    if msg.get("id") != n or msg.get("error"):
                        raise ValueError("robot.health: " + str(msg.get("error", "响应 ID 不符")))
                    emit({"channel": "health", "data": msg.get("result", {})})
                    stop.wait(1)
        except Exception as exc:
            emit({"channel": "health", "error": str(exc)})
        stop.wait(2)


def capabilities_loop(path, emit, stop):
    # Policies can finish loading after the first subscription acknowledgement.
    # robotd retires this read-only subscriber on EOF; no ToF connection is used.
    while not stop.wait(10):
        try:
            with connect(path) as s, s.makefile("rb") as reader:
                s.sendall(b'{"jsonrpc":"2.0","id":1,"method":"robot.subscribe","params":{"hz":1}}\n')
                msg = json_line(reader)
                result = msg.get("result")
                if msg.get("id") != 1 or msg.get("error") or not isinstance(result, dict) or not result.get("accepted"):
                    raise ValueError("官方可用动作列表未就绪")
                emit({"channel": "capabilities", "data": result})
        except Exception as exc:
            emit({"channel": "capabilities", "error": str(exc)})


def system_loop(emit, stop):
    last_cpu = None
    while not stop.is_set():
        d = {"hostname": socket.gethostname(), "identities": {}}
        try:
            boot_id = Path("/proc/sys/kernel/random/boot_id")
            if boot_id.exists(): d["boot_id"] = boot_id.read_text().strip()
            p = Path("/proc/uptime")
            if p.exists():
                d["uptime_s"] = float(p.read_text().split()[0])
            if Path("/proc/meminfo").exists():
                memory = {a: int(b.split()[0])*1024 for a, b in (x.split(":", 1) for x in Path("/proc/meminfo").read_text().splitlines())}
                d["memory_total"] = memory.get("MemTotal")
                d["memory_available"] = memory.get("MemAvailable")
            if Path("/proc/stat").exists():
                counts = [int(x) for x in Path("/proc/stat").read_text().splitlines()[0].split()[1:9]]
                current = (sum(counts), counts[3] + counts[4])
                if last_cpu and current[0] > last_cpu[0]:
                    d["cpu_percent"] = 100*(1-(current[1]-last_cpu[1])/(current[0]-last_cpu[0]))
                last_cpu = current
            if hasattr(os, "getloadavg"):
                d["load_average"] = list(os.getloadavg())
            temps = []
            for p in Path("/sys/class/thermal").glob("thermal_zone*/temp"):
                try:
                    temps.append(float(p.read_text())/1000)
                except (OSError, ValueError):
                    pass
            d["cpu_temp_c"] = max(temps) if temps else None
            for service in ("robotd", "tofd", "mediad", "padd", "updaterd", "configd"):
                p = Path("/run") / service / "identity.json"
                try:
                    # These are public build identities, not config files or environment dumps.
                    identity = json.loads(p.read_text())
                    d["identities"][service] = identity
                except (OSError, ValueError):
                    pass
            try:
                p = Path("/run/mediad/camera.json")
                camera = json.loads(p.read_text())
                if isinstance(camera, dict):
                    # Capture statistics are independent of the browser receiver.
                    # This file can outlive the process that published it.
                    d["camera"] = camera
                    d["camera_age_ms"] = max(0, round((time.time()-p.stat().st_mtime)*1000))
            except (OSError, ValueError):
                pass
            emit({"channel": "system", "data": d})
        except Exception as exc:
            emit({"channel": "system", "error": str(exc)})
        stop.wait(2)


def bus_loop(path, emit, stop):
    """Poll the service cache, not the UART. A blocked bus remains distinguishable."""
    while not stop.is_set():
        try:
            with connect(path) as s, s.makefile("rb") as reader:
                calibration_loaded=False
                while not stop.is_set():
                    s.sendall(b'{"jsonrpc":"2.0","id":1,"method":"robot.busStatus"}\n')
                    msg = json_line(reader)
                    if msg.get("id") != 1 or msg.get("error") or not isinstance(msg.get("result"), dict):
                        raise ValueError("robot.busStatus: " + str(msg.get("error", "无效响应")))
                    report=msg["result"]
                    emit_ipc(emit, "bus", msg, "result")
                    if not calibration_loaded and report.get("phase") not in ("configuration_error","configuring_uart"):
                        s.sendall(b'{"jsonrpc":"2.0","id":2,"method":"robot.busCommand","params":{"action":"calibration-status"}}\n')
                        calibration=json_line(reader)
                        if calibration.get("result"):
                            emit({"channel":"calibration","data":calibration["result"]});calibration_loaded=True
                    stop.wait(.1)
        except Exception as exc:
            emit({"channel": "bus", "error": str(exc)})
        stop.wait(2)


def run(config, emit, stop=None):
    stop = stop or threading.Event()
    if config.get('startup_nonce'):
        emit({'channel':'collector','data':{'nonce':config['startup_nonce'],
              'hostname':socket.gethostname(),'python':list(sys.version_info[:3]),
              'unix_socket':hasattr(socket,'AF_UNIX')}})
    jobs = [(system_loop, (emit, stop)),
            (subscription, (config.get("tofd_socket", "/run/tofd/tof.sock"), "tof.stream", "tof.frame", None, emit, stop, "tof"))]
    path = config.get("robotd_socket", "/run/robotd.sock")
    jobs += [(subscription, (path, "robot.subscribe", "robot.state", config.get("hz", 20), emit, stop, "state")),
             (health_loop, (path, emit, stop)),
             (capabilities_loop, (path, emit, stop))]
    if config.get("service"):
        jobs += [(bus_loop, (path, emit, stop))]
    for fn, args in jobs:
        threading.Thread(target=fn, args=args, daemon=True).start()
    while not stop.wait(1):
        pass


if __name__ == "__main__":
    run(globals().get("OBSERVER_CONFIG", {}), CollectorOutput())

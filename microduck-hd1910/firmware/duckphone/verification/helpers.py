#!/usr/bin/env python3
"""Test doubles: a scriptable `robotd` and a minimal WebSocket client.

Both exist so the bridge can be tested end to end on a laptop, with no robot and
no `pip install`. The fake daemon speaks the same newline-delimited JSON-RPC as
the real one and records everything it is told.
"""

from __future__ import annotations

import base64
import json
import os
import socket
import struct
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import ws as wsproto  # noqa: E402


class FakeRobotd:
    """Accepts clients, answers requests, and lets a test push state frames."""

    def __init__(self, path: str | None = None) -> None:
        self.dir = tempfile.mkdtemp(prefix="duckphone-test-")
        self.path = path or os.path.join(self.dir, "robotd.sock")
        self.received: list[dict] = []
        # Method → error message. robotd answers `robot.subscribe` with an error
        # while it is in commissioning mode; the fake has to be able to do that.
        self.refuse: dict[str, str] = {}
        self._lock = threading.Lock()
        self._clients: list[socket.socket] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._server: socket.socket | None = None
        self.responses: dict[str, dict] = {
            "robot.subscribe": {"accepted": True, "walk": "walk.onnx"},
            "robot.stop": {"accepted": True},
            "robot.init": {"accepted": True},
            "robot.relax": {"accepted": True},
            "robot.rebootMotors": {"accepted": True},
            "robot.shutdown": {"accepted": True},
            "robot.policies": {
                "enabled": True, "homed": False, "mode": "walk", "sitting": False,
                "skills": ["roulade", "kick_left"],
                "slots": [
                    {"slot": "walk", "path": "/opt/robot/feetech-ft5-r5/models/walk/policy.onnx",
                     "origin": "local", "overridden": True, "error": None},
                    {"slot": "stand", "path": None, "origin": None, "overridden": True, "error": None},
                    {"slot": "sitstand", "path": "/opt/robot/feetech-ft5-r5/models/sit/policy.onnx",
                     "origin": "local", "overridden": True, "error": None},
                    {"slot": "ground_pick", "path": "/opt/robot/feetech-ft5-r5/models/pick/policy.onnx",
                     "origin": "local", "overridden": True, "error": None},
                    {"slot": "kick_left", "path": "/opt/robot/feetech-ft5-r5/models/kl/policy.onnx",
                     "origin": "local", "overridden": True, "error": None},
                    {"slot": "kick_right", "path": None, "origin": None, "overridden": True, "error": None},
                    {"slot": "roulade", "path": "/opt/robot/feetech-ft5-r5/models/rl/policy.onnx",
                     "origin": "local", "overridden": True, "error": None},
                ],
            },
            "robot.do": {"accepted": True},
            "robot.action": {"accepted": True, "sound": True},
            "robot.health": {
                "healthy": True,
                "battery": {"volts": 7.55, "percent": 61.0},
                "motors": {"hottest": "knee_l", "max_c": 30.5, "mean_c": 28.0},
                "cpu_temp_c": 48.0,
                "control_loop": {
                    "target_hz": 50.0, "achieved_hz": 49.9, "ticks": 10, "missed": 0,
                },
            },
        }

    def start(self) -> "FakeRobotd":
        if os.path.exists(self.path):
            os.unlink(self.path)
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(self.path)
        server.listen(4)
        server.settimeout(0.2)
        self._server = server
        self._thread = threading.Thread(target=self._accept_loop, name="fake-robotd", daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        for closer in [*self._clients, self._server]:
            if closer is None:
                continue
            try:
                closer.close()
            except OSError:
                pass
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        try:
            os.unlink(self.path)
        except OSError:
            pass

    def _accept_loop(self) -> None:
        assert self._server is not None
        while not self._stop.is_set():
            try:
                conn, _ = self._server.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            self._clients.append(conn)
            threading.Thread(target=self._serve, args=(conn,), daemon=True).start()

    def _serve(self, conn: socket.socket) -> None:
        buf = b""
        try:
            while not self._stop.is_set():
                chunk = conn.recv(65536)
                if not chunk:
                    return
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if not line.strip():
                        continue
                    msg = json.loads(line)
                    with self._lock:
                        self.received.append(msg)
                    if msg.get("id") is None:
                        continue
                    method = msg.get("method")
                    if method in self.refuse:
                        conn.sendall(
                            json.dumps({
                                "jsonrpc": "2.0", "id": msg["id"],
                                "error": {"code": -32600, "message": self.refuse[method]},
                            }).encode() + b"\n"
                        )
                        continue
                    result = self.responses.get(method, {})
                    extra = {"accepted": True} if method.startswith("robot.") else {}
                    body = {**extra, **result}
                    conn.sendall(
                        json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": body}).encode()
                        + b"\n"
                    )
        except OSError:
            return

    # ── driving the fake ─────────────────────────────────────────────────
    def wait_for_client(self, timeout: float = 5.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._clients:
                return True
            time.sleep(0.01)
        return False

    def push_state(self, **overrides) -> None:
        frame = {
            "t": 12.5,
            "move": {"requested": [0.0, 0.0, 0.0], "applied": [0.0, 0.0, 0.0]},
            "head": [0.0, 0.0, 0.0, 0.0],
            "policy": "held",
            "safety": {"fallen": False, "limp": True, "gravity": [0.0, 0.0, -1.0], "gain": 32},
            "loop": {"hz": 49.9, "missed": 3},
            "joints": [0.0] * 15,
            "targets": [0.0] * 15,
            "odom": {"position": [0.0, 0.0, 0.0], "yaw": 0.0},
        }
        for key, value in overrides.items():
            if key in ("move", "safety", "loop") and isinstance(value, dict):
                frame[key] = {**frame[key], **value}
            else:
                frame[key] = value
        line = json.dumps({"jsonrpc": "2.0", "method": "robot.state", "params": frame}).encode() + b"\n"
        for client in list(self._clients):
            try:
                client.sendall(line)
            except OSError:
                pass

    def moves(self) -> list[dict]:
        with self._lock:
            return [m for m in self.received if m.get("method") == "robot.move"]

    def methods(self) -> list[str]:
        with self._lock:
            return [str(m.get("method")) for m in self.received]

    def calls(self, method: str) -> list[dict]:
        with self._lock:
            return [m for m in self.received if m.get("method") == method]

    def reset(self) -> None:
        with self._lock:
            self.received.clear()


def mask(payload: bytes, key: bytes) -> bytes:
    n = len(payload)
    if not n:
        return b""
    stream = (key * (n // 4 + 1))[:n]
    return (int.from_bytes(payload, "big") ^ int.from_bytes(stream, "big")).to_bytes(n, "big")


def client_frame(opcode: int, payload: bytes, *, fin: bool = True) -> bytes:
    key = os.urandom(4)
    head = bytearray()
    head.append((0x80 if fin else 0) | opcode)
    n = len(payload)
    if n < 126:
        head.append(0x80 | n)
    elif n < 65536:
        head.append(0x80 | 126)
        head += struct.pack("!H", n)
    else:
        head.append(0x80 | 127)
        head += struct.pack("!Q", n)
    return bytes(head) + key + mask(payload, key)


class WSClient:
    """Just enough client to drive the bridge: text in, text out."""

    def __init__(self, host: str, port: int, path: str = "/ws", timeout: float = 5.0) -> None:
        self._sock = socket.create_connection((host, port), timeout=timeout)
        self._sock.settimeout(timeout)
        self._reader = self._sock.makefile("rb")
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self._sock.sendall(request.encode())
        status = self._reader.readline()
        if b"101" not in status:
            raise RuntimeError(f"handshake failed: {status!r}")
        while True:
            line = self._reader.readline()
            if line in (b"\r\n", b"\n", b""):
                break

    def send(self, payload: dict) -> None:
        self._sock.sendall(client_frame(0x1, json.dumps(payload).encode()))

    def send_raw(self, data: bytes) -> None:
        self._sock.sendall(data)

    def recv(self) -> dict | None:
        head = self._reader.read(2)
        if not head or len(head) != 2:
            return None
        opcode = head[0] & 0x0F
        length = head[1] & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._reader.read(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._reader.read(8))[0]
        payload = self._reader.read(length) if length else b""
        if opcode == 0x8:
            return None
        if opcode not in (0x1, 0x2):
            return {}
        try:
            return json.loads(payload.decode())
        except ValueError:
            return {}

    def wait_for(self, kind: str, timeout: float = 5.0, **match) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self._sock.settimeout(max(0.05, deadline - time.monotonic()))
            try:
                msg = self.recv()
            except (socket.timeout, TimeoutError):
                continue
            if not msg:
                continue
            if msg.get("t") != kind:
                continue
            if all(msg.get(k) == v for k, v in match.items()):
                return msg
        raise AssertionError(f"没有等到 {kind} {match}")

    def close(self) -> None:
        try:
            self._sock.sendall(client_frame(0x8, struct.pack("!H", 1000)))
        except OSError:
            pass
        for closer in (self._reader.close, self._sock.close):
            try:
                closer()
            except OSError:
                pass


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def ping_frame() -> bytes:
    return wsproto.encode_frame(wsproto.OP_PING, b"hi")

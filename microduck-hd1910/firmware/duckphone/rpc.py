#!/usr/bin/env python3
"""robotd JSON-RPC client: one unix socket, a request/reply map and a state stream.

robotd speaks newline-delimited JSON-RPC 2.0 on `/run/robotd.sock`. Continuous
intents (`robot.move`, `robot.head`) are *notifications* — no `id`, no reply —
and `robot.subscribe` turns the same connection into a stream of `robot.state`
notifications. Everything else is a request.

Why one connection: the socket is cheap, the state stream is per-connection, and
opening a second socket for commands would double the teardown cases in
`server.py`. If the link drops, this class reconnects and re-subscribes by
itself; the caller only sees `connected` flip.
"""

from __future__ import annotations

import json
import socket
import threading
import time
from typing import Any, Callable

DEFAULT_SOCKET = "/run/robotd.sock"


class RobotUnavailable(RuntimeError):
    """The daemon is not reachable, or dropped the call."""


class RobotRPC:
    """Thread-safe client. One reader thread, lazy writer, auto-reconnect."""

    def __init__(
        self,
        path: str = DEFAULT_SOCKET,
        *,
        subscribe_hz: int = 20,
        on_state: Callable[[dict], None] | None = None,
        on_link: Callable[[bool, str], None] | None = None,
        reconnect_delay: tuple[float, float] = (0.5, 3.0),
    ) -> None:
        self.path = path
        self.subscribe_hz = subscribe_hz
        self.on_state = on_state
        self.on_link = on_link
        self._reconnect_delay = reconnect_delay

        self._sock: socket.socket | None = None
        self._send_lock = threading.Lock()
        self._pending: dict[int, tuple[threading.Event, dict]] = {}
        self._pending_lock = threading.Lock()
        self._next_id = 0
        self._stop = threading.Event()
        self._reader: threading.Thread | None = None
        self._connected = False
        self._subscribed = False
        # Why `robot.subscribe` was refused. robotd answers it with an error while
        # it is in commissioning mode — the socket is up and `robot.health` still
        # works, so this is *not* a broken link and must not be reported as one.
        self.subscribe_error = ""
        self.last_state_at = 0.0
        self.link_error = ""

    # ── lifecycle ────────────────────────────────────────────────────────
    def start(self) -> None:
        self._reader = threading.Thread(target=self._run, name="robotd-rpc", daemon=True)
        self._reader.start()

    def stop(self) -> None:
        self._stop.set()
        self._close_socket(RobotUnavailable("client stopped"))

    @property
    def connected(self) -> bool:
        """The socket is up. Says nothing about whether state is streaming."""
        return self._connected

    @property
    def streaming(self) -> bool:
        return self._subscribed and self._connected

    def _run(self) -> None:
        delay = self._reconnect_delay[0]
        while not self._stop.is_set():
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                sock.settimeout(2.0)
                sock.connect(self.path)
                sock.settimeout(None)
            except OSError as exc:
                try:
                    sock.close()
                except OSError:
                    pass
                self._set_link(False, f"无法连接 robotd：{exc.strerror or exc}")
                if self._stop.wait(delay):
                    return
                delay = min(delay * 2, self._reconnect_delay[1])
                continue

            delay = self._reconnect_delay[0]
            with self._send_lock:
                self._sock = sock
            self._set_link(True, "")
            try:
                # The reply has to be read before it can be matched, so the
                # subscribe goes out on its own thread; this one owns the socket.
                threading.Thread(
                    target=self._subscribe_async, name="robotd-subscribe", daemon=True
                ).start()
                self._read_loop(sock)
            except OSError as exc:
                self._set_link(False, f"robotd 连接断开：{exc.strerror or exc}")
            finally:
                self._subscribed = False
                self._close_socket(RobotUnavailable("link dropped"))
            if self._stop.is_set():
                return
            if self._stop.wait(0.2):
                return

    def _subscribe_async(self) -> None:
        """Subscribe, and keep trying while the socket is up.

        Retrying matters because the refusal is a *mode*, not a fault: robotd
        answers "read-only" while it is being commissioned, and the same socket
        starts streaming the moment it is restarted into drive mode. Treating
        that rejection as a dead link made the bridge give up on state forever
        and never poll health either — which is exactly the information that
        still works in that mode.
        """
        while not self._stop.is_set() and self.connected:
            try:
                self._subscribe()
            except RobotUnavailable as exc:
                self.subscribe_error = str(exc)
                self._set_link(True, "")   # socket fine; mode is not
                if self._stop.wait(2.0):
                    return
                continue
            self.subscribe_error = ""
            self._subscribed = True
            return

    def _read_loop(self, sock: socket.socket) -> None:
        buf = b""
        while not self._stop.is_set():
            chunk = sock.recv(65536)
            if not chunk:
                raise OSError("robotd closed the socket")
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if line.strip():
                    self._dispatch(line)
            if len(buf) > 8 * 1024 * 1024:
                raise OSError("robotd sent an oversized line")

    def _dispatch(self, line: bytes) -> None:
        try:
            msg = json.loads(line)
        except ValueError:
            return
        if not isinstance(msg, dict):
            return

        msg_id = msg.get("id")
        if msg_id is not None:
            with self._pending_lock:
                slot = self._pending.pop(msg_id, None)
            if slot is not None:
                event, box = slot
                box.update(msg)
                event.set()
            return

        method = msg.get("method")
        if method == "robot.state":
            self.last_state_at = time.monotonic()
            params = msg.get("params")
            if isinstance(params, dict) and self.on_state is not None:
                try:
                    self.on_state(params)
                except Exception:  # a consumer bug must not kill the reader
                    pass

    def _set_link(self, up: bool, error: str) -> None:
        if up == self._connected and error == self.link_error:
            return          # the read-only retry loop would otherwise log every 2 s
        self._connected = up
        self.link_error = error
        if self.on_link is not None:
            try:
                self.on_link(up, error)
            except Exception:
                pass

    def _close_socket(self, exc: Exception) -> None:
        with self._send_lock:
            sock, self._sock = self._sock, None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
        self._connected = False
        with self._pending_lock:
            waiting = list(self._pending.values())
            self._pending.clear()
        for event, box in waiting:
            box["error"] = {"message": str(exc)}
            event.set()

    # ── sending ──────────────────────────────────────────────────────────
    def _write(self, payload: dict) -> None:
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n"
        with self._send_lock:
            sock = self._sock
            if sock is None:
                raise RobotUnavailable("robotd 未连接")
            try:
                sock.sendall(data)
            except OSError as exc:
                # 半开的 socket：走同一套"链路断了"的收尾，别把调用方留在 pending 里
                raise RobotUnavailable(f"发送失败：{exc.strerror or exc}") from exc

    def _subscribe(self) -> None:
        self.request("robot.subscribe", {"hz": self.subscribe_hz}, timeout=4.0)

    def notify(self, method: str, params: dict | None = None) -> None:
        payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        self._write(payload)

    def request(self, method: str, params: dict | None = None, timeout: float = 3.0) -> dict:
        with self._pending_lock:
            self._next_id += 1
            msg_id = self._next_id
            event = threading.Event()
            box: dict[str, Any] = {}
            self._pending[msg_id] = (event, box)
        payload = {"jsonrpc": "2.0", "id": msg_id, "method": method}
        if params is not None:
            payload["params"] = params
        try:
            self._write(payload)
        except RobotUnavailable:
            with self._pending_lock:
                self._pending.pop(msg_id, None)
            raise

        if not event.wait(timeout):
            with self._pending_lock:
                self._pending.pop(msg_id, None)
            raise RobotUnavailable(f"{method} 超时（{timeout:.1f}s）")
        if "error" in box:
            err = box["error"] or {}
            raise RobotUnavailable(str(err.get("message") or err))
        result = box.get("result")
        return result if isinstance(result, dict) else {}

    # ── intents ──────────────────────────────────────────────────────────
    def move(self, vx: float, vy: float, vyaw: float) -> None:
        self.notify("robot.move", {"vx": vx, "vy": vy, "vyaw": vyaw})

    def head(self, neck_pitch: float, head_pitch: float, head_yaw: float, head_roll: float) -> None:
        """Continuous head intent. Like `move`, a notification with no reply."""
        self.notify("robot.head", {
            "neck_pitch": neck_pitch, "head_pitch": head_pitch,
            "head_yaw": head_yaw, "head_roll": head_roll,
        })

    def mouth(self, open: float) -> None:
        """Continuous mouth intent; 0 closed, 1 fully open."""
        level = min(1.0, max(0.0, float(open)))
        self.notify("robot.mouth", {"open": level})

    def pose(self, z: float, roll: float, pitch: float, active: bool = True) -> None:
        """Standing body-pose offsets, clamped to the trained envelope."""
        self.notify("robot.pose", {
            "z": min(0.010, max(-0.025, float(z))),
            "roll": min(0.26, max(-0.26, float(roll))),
            "pitch": min(0.26, max(-0.26, float(pitch))),
            "active": bool(active),
        })

    def sound(self, tag: str, hold: bool | None = None) -> dict:
        """Play one voice-bank tag. `hold` is only meaningful for `wheee`."""
        params: dict[str, Any] = {"tag": tag}
        if hold is not None:
            params["hold"] = bool(hold)
        return self.request("robot.sound", params, timeout=3.0)

    def sound_async(self, tag: str) -> None:
        """Fire-and-forget beat for an action; never blocks the 20 Hz loop."""
        self.notify("robot.sound", {"tag": tag})

    def stop(self) -> dict:
        return self.request("robot.stop", None, timeout=2.0)

    def init(self) -> dict:
        return self.request("robot.init", None, timeout=6.0)

    def enable(self, on: bool) -> dict:
        return self.request("robot.enable", {"on": bool(on)}, timeout=4.0)

    def relax(self) -> dict:
        return self.request("robot.relax", None, timeout=4.0)

    def reboot_motors(self, ids: list[int] | None = None) -> dict:
        return self.request("robot.rebootMotors", {"ids": list(ids or [])}, timeout=8.0)

    def policies(self, timeout: float = 3.0) -> dict:
        """Which `.onnx` sits in each slot, and what is driving right now."""
        return self.request("robot.policies", None, timeout=timeout)

    def do_skill(self, skill: str, timeout: float = 4.0) -> dict:
        """Run one one-shot skill (`roulade`, `kick_left`, `sit_toggle`, …).

        The robot returns to the walking network by itself when the skill's
        window expires — nothing here has to undo it.
        """
        return self.request("robot.do", {"skill": skill}, timeout=timeout)

    def health(self, timeout: float = 2.5) -> dict:
        return self.request("robot.health", None, timeout=timeout)

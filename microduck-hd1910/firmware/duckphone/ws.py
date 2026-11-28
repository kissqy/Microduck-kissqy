#!/usr/bin/env python3
"""Minimal RFC 6455 WebSocket, server side, standard library only.

Only what the duckphone page needs: text messages, fragmentation, ping/pong and
close. No extensions, no compression, no binary payloads.

The board has no `websockets` / `aiohttp` / `pip`, so this file is the whole
WebSocket stack. It is deliberately small enough to read in one sitting: a bug
here shows up as a phone that cannot connect at all.
"""

from __future__ import annotations

import base64
import hashlib
import os
import socket
import struct
import threading

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

OP_CONT = 0x0
OP_TEXT = 0x1
OP_BINARY = 0x2
OP_CLOSE = 0x8
OP_PING = 0x9
OP_PONG = 0xA

# A page message is a few hundred bytes; anything near this is a bug or an
# attacker, and either way must not be buffered.
MAX_MESSAGE = 64 * 1024

CLOSE_NORMAL = 1000
CLOSE_PROTOCOL_ERROR = 1002
CLOSE_TOO_BIG = 1009


class WSError(Exception):
    """Framing or handshake failure. Carries the close code to report."""

    def __init__(self, message: str, code: int = CLOSE_PROTOCOL_ERROR) -> None:
        super().__init__(message)
        self.code = code


def accept_key(client_key: str) -> str:
    """The `Sec-WebSocket-Accept` value for a client's `Sec-WebSocket-Key`."""
    digest = hashlib.sha1((client_key.strip() + GUID).encode("ascii")).digest()
    return base64.b64encode(digest).decode("ascii")


def _mask(payload: bytes, key: bytes) -> bytes:
    if not payload:
        return b""
    # int.from_bytes/to_bytes in one XOR is what makes this fast enough for the
    # 20 Hz state stream without pulling in a dependency.
    n = len(payload)
    stream = (key * (n // 4 + 1))[:n]
    return (int.from_bytes(payload, "big") ^ int.from_bytes(stream, "big")).to_bytes(n, "big")


def encode_frame(opcode: int, payload: bytes = b"", *, fin: bool = True) -> bytes:
    """One unmasked server→client frame."""
    head = bytearray()
    head.append((0x80 if fin else 0x00) | (opcode & 0x0F))
    n = len(payload)
    if n < 126:
        head.append(n)
    elif n < 65536:
        head.append(126)
        head += struct.pack("!H", n)
    else:
        head.append(127)
        head += struct.pack("!Q", n)
    return bytes(head) + payload


def encode_close(code: int = CLOSE_NORMAL, reason: str = "") -> bytes:
    body = b""
    if code:
        body = struct.pack("!H", code) + reason.encode("utf-8")[:120]
    return encode_frame(OP_CLOSE, body)


class WebSocket:
    """One upgraded connection.

    Reads happen on the caller's thread; writes are serialised by a lock so the
    broadcast thread and the request thread cannot interleave frames.
    """

    def __init__(self, sock: socket.socket, *, is_server: bool = True, reader=None) -> None:
        self._sock = sock
        self._is_server = is_server
        self._write_lock = threading.Lock()
        self._closed = False
        self._frag_opcode: int | None = None
        self._frag_buf = bytearray()
        # A caller that already owns a buffered reader (http.server's `rfile`)
        # must pass it in: a second buffer over one socket eats frames.
        self._reader = reader if reader is not None else sock.makefile("rb")
        self._owns_reader = reader is None

    # ── writing ──────────────────────────────────────────────────────────
    def send_text(self, text: str) -> None:
        self._send_raw(encode_frame(OP_TEXT, text.encode("utf-8")))

    def ping(self, payload: bytes = b"") -> None:
        self._send_raw(encode_frame(OP_PING, payload))

    def pong(self, payload: bytes = b"") -> None:
        self._send_raw(encode_frame(OP_PONG, payload))

    def close(self, code: int = CLOSE_NORMAL, reason: str = "") -> None:
        if self._closed:
            return
        try:
            self._send_raw(encode_close(code, reason))
        except OSError:
            pass
        self._closed = True
        closers = [self._sock.close] if self._owns_reader else []
        closers.insert(0, self._reader.close)
        for closer in closers:
            try:
                closer()
            except OSError:
                pass

    def _send_raw(self, data: bytes) -> None:
        if self._closed:
            raise OSError("websocket closed")
        with self._write_lock:
            self._sock.sendall(data)

    @property
    def closed(self) -> bool:
        return self._closed

    # ── reading ──────────────────────────────────────────────────────────
    def _read_exact(self, n: int) -> bytes:
        data = self._reader.read(n)
        if data is None or len(data) != n:
            raise WSError("connection closed mid-frame", CLOSE_NORMAL)
        return data

    def recv_frame(self) -> tuple[bool, int, bytes]:
        """Read one frame, answering control frames internally."""
        while True:
            head = self._reader.read(2)
            if not head or len(head) != 2:
                raise WSError("connection closed", CLOSE_NORMAL)
            fin = bool(head[0] & 0x80)
            rsv = head[0] & 0x70
            opcode = head[0] & 0x0F
            masked = bool(head[1] & 0x80)
            length = head[1] & 0x7F

            if rsv:
                raise WSError("reserved bits set")
            if self._is_server and not masked:
                # RFC 6455 §5.1: every client→server frame must be masked.
                raise WSError("client frame not masked")

            if length == 126:
                length = struct.unpack("!H", self._read_exact(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self._read_exact(8))[0]
            if length > MAX_MESSAGE:
                raise WSError("frame too large", CLOSE_TOO_BIG)

            key = self._read_exact(4) if masked else b""
            payload = self._read_exact(length) if length else b""
            if masked:
                payload = _mask(payload, key)

            if opcode == OP_PING:
                self.pong(payload)
                continue
            if opcode == OP_PONG:
                continue
            if opcode == OP_CLOSE:
                code = struct.unpack("!H", payload[:2])[0] if len(payload) >= 2 else CLOSE_NORMAL
                raise WSError("peer closed", code)
            if opcode == OP_BINARY:
                raise WSError("binary frames are not accepted")

            return fin, opcode, payload

    def recv_message(self) -> str | None:
        """Next complete text message, or None when the peer closed cleanly."""
        try:
            while True:
                fin, opcode, payload = self.recv_frame()
                if opcode == OP_CONT:
                    if self._frag_opcode is None:
                        raise WSError("continuation without a start frame")
                    self._frag_buf += payload
                    if len(self._frag_buf) > MAX_MESSAGE:
                        raise WSError("message too large", CLOSE_TOO_BIG)
                    if fin:
                        data = bytes(self._frag_buf)
                        opcode = self._frag_opcode
                        self._frag_opcode = None
                        self._frag_buf.clear()
                        if opcode == OP_TEXT:
                            return data.decode("utf-8", "replace")
                        raise WSError("binary frames are not accepted")
                    continue
                if not fin:
                    self._frag_opcode = opcode
                    self._frag_buf = bytearray(payload)
                    continue
                return payload.decode("utf-8", "replace")
        except WSError as exc:
            if exc.code == CLOSE_NORMAL:
                return None
            raise


def upgrade_response(handler_headers, sock: socket.socket) -> WebSocket:
    """Validate an HTTP upgrade and return the wrapped socket."""
    if (handler_headers.get("Upgrade") or "").lower() != "websocket":
        raise WSError("not a websocket upgrade", CLOSE_PROTOCOL_ERROR)
    key = handler_headers.get("Sec-WebSocket-Key")
    if not key:
        raise WSError("missing Sec-WebSocket-Key", CLOSE_PROTOCOL_ERROR)
    return WebSocket(sock)


def handshake_bytes(headers) -> bytes:
    accept = accept_key(headers["Sec-WebSocket-Key"])
    return (
        "HTTP/1.1 101 Switching Protocols\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {accept}\r\n"
        "\r\n"
    ).encode("ascii")


def random_nonce(n: int = 16) -> str:
    return base64.b64encode(os.urandom(n)).decode("ascii")

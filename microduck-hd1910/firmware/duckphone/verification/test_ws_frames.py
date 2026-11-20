#!/usr/bin/env python3
"""Framing tests for the hand-rolled WebSocket.

A framing bug on this robot shows up as "the phone cannot connect", with no other
symptom, so the byte-level cases are pinned here rather than exercised through a
browser.
"""

from __future__ import annotations

import io
import os
import socket
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ws  # noqa: E402


class SocketPair:
    """A connected socket pair, with the server side wrapped as a WebSocket."""

    def __init__(self) -> None:
        self.server, self.client = socket.socketpair()
        self.reader = self.server.makefile("rb")
        self.ws = ws.WebSocket(self.server, reader=self.reader)

    def send_client(self, data: bytes) -> None:
        self.client.sendall(data)

    def close(self) -> None:
        self.ws.close()
        try:
            self.client.close()
        except OSError:
            pass


def masked(opcode: int, payload: bytes, *, fin: bool = True) -> bytes:
    key = b"\x01\x02\x03\x04"
    mask = bytes((payload[i] ^ key[i % 4]) for i in range(len(payload))) if payload else b""
    first = (0x80 if fin else 0) | opcode
    n = len(payload)
    if n < 126:
        head = bytes([first, 0x80 | n])
    elif n < 65536:
        head = bytes([first, 0x80 | 126]) + struct.pack("!H", n)
    else:
        head = bytes([first, 0x80 | 127]) + struct.pack("!Q", n)
    return head + key + mask


class AcceptKeyTest(unittest.TestCase):
    def test_rfc_example(self):
        # RFC 6455 §1.3, the value every implementation is expected to reproduce.
        self.assertEqual(
            ws.accept_key("dGhlIHNhbXBsZSBub25jZQ=="),
            "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=",
        )

    def test_whitespace_trimmed(self):
        self.assertEqual(
            ws.accept_key("  dGhlIHNhbXBsZSBub25jZQ==\r\n"),
            "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=",
        )


class EncodeFrameTest(unittest.TestCase):
    def test_short_payload(self):
        self.assertEqual(ws.encode_frame(ws.OP_TEXT, b"hi"), b"\x81\x02hi")

    def test_extended_16_bit_length(self):
        payload = b"x" * 200
        frame = ws.encode_frame(ws.OP_TEXT, payload)
        self.assertEqual(frame[0], 0x81)
        self.assertEqual(frame[1], 126)
        self.assertEqual(struct.unpack("!H", frame[2:4])[0], 200)
        self.assertEqual(frame[4:], payload)

    def test_extended_64_bit_length(self):
        payload = b"y" * 70000
        frame = ws.encode_frame(ws.OP_TEXT, payload)
        self.assertEqual(frame[1], 127)
        self.assertEqual(struct.unpack("!Q", frame[2:10])[0], 70000)

    def test_close_carries_code(self):
        frame = ws.encode_close(1000)
        self.assertEqual(frame[0], 0x88)
        self.assertEqual(struct.unpack("!H", frame[2:4])[0], 1000)


class RecvTest(unittest.TestCase):
    def setUp(self):
        self.pair = SocketPair()

    def tearDown(self):
        self.pair.close()

    def test_text_round_trip(self):
        self.pair.send_client(masked(ws.OP_TEXT, "机器人".encode()))
        self.assertEqual(self.pair.ws.recv_message(), "机器人")

    def test_fragmented_message_is_joined(self):
        self.pair.send_client(masked(ws.OP_TEXT, b"he", fin=False))
        self.pair.send_client(masked(ws.OP_CONT, b"llo", fin=True))
        self.assertEqual(self.pair.ws.recv_message(), "hello")

    def test_ping_is_answered_with_pong_and_skipped(self):
        self.pair.send_client(masked(ws.OP_PING, b"hb"))
        self.pair.send_client(masked(ws.OP_TEXT, b"after"))
        self.assertEqual(self.pair.ws.recv_message(), "after")
        head = self.pair.client.recv(2)
        self.assertEqual(head[0] & 0x0F, ws.OP_PONG)
        self.assertEqual(self.pair.client.recv(head[1] & 0x7F), b"hb")

    def test_unmasked_client_frame_is_refused(self):
        self.pair.send_client(ws.encode_frame(ws.OP_TEXT, b"naked"))
        with self.assertRaises(ws.WSError) as ctx:
            self.pair.ws.recv_message()
        self.assertEqual(ctx.exception.code, ws.CLOSE_PROTOCOL_ERROR)

    def test_binary_is_refused(self):
        self.pair.send_client(masked(ws.OP_BINARY, b"\x00\x01"))
        with self.assertRaises(ws.WSError):
            self.pair.ws.recv_message()

    def test_close_returns_none(self):
        self.pair.send_client(masked(ws.OP_CLOSE, struct.pack("!H", 1000)))
        self.assertIsNone(self.pair.ws.recv_message())

    def test_oversized_frame_is_refused(self):
        self.pair.send_client(masked(ws.OP_TEXT, b"z" * (ws.MAX_MESSAGE + 1)))
        with self.assertRaises(ws.WSError) as ctx:
            self.pair.ws.recv_message()
        self.assertEqual(ctx.exception.code, ws.CLOSE_TOO_BIG)

    def test_eof_returns_none(self):
        self.pair.client.close()
        self.assertIsNone(self.pair.ws.recv_message())

    def test_reserved_bits_refused(self):
        frame = bytearray(masked(ws.OP_TEXT, b"x"))
        frame[0] |= 0x40
        self.pair.send_client(bytes(frame))
        with self.assertRaises(ws.WSError):
            self.pair.ws.recv_message()


class HandshakeTest(unittest.TestCase):
    def test_handshake_headers(self):
        headers = {"Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ=="}
        text = ws.handshake_bytes(headers).decode("ascii")
        self.assertTrue(text.startswith("HTTP/1.1 101 "))
        self.assertIn("Upgrade: websocket", text)
        self.assertIn("Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=", text)
        self.assertTrue(text.endswith("\r\n\r\n"))


if __name__ == "__main__":
    unittest.main()

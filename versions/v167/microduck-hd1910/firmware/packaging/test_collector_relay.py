"""The SSH relay removes encoding work without changing collected events."""
import io
import json
import math
import socket
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "console"))
import agent
import console as ui


def wire(value):
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def reply(data, ident=1):
    return wire({"jsonrpc": "2.0", "id": ident, "result": data})


class Reader(io.BytesIO):
    def __init__(self, lines, end_error=None):
        super().__init__(b"".join(lines))
        self.end_error = end_error

    def readline(self, size=-1):
        line = super().readline(size)
        if not line and self.end_error:
            raise self.end_error
        return line


class IPC:
    """Mock only the Unix transport, leaving production collector loops intact."""
    def __init__(self, lines, end_error=None):
        self.reader = Reader(lines, end_error)
        self.requests = []
        self.timeouts = []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.closed = True
        self.reader.close()

    def makefile(self, mode):
        assert mode == "rb"
        return self.reader

    def sendall(self, line):
        self.requests.append(json.loads(line))

    def settimeout(self, timeout):
        self.timeouts.append(timeout)


class Stop:
    def __init__(self, interval, after):
        self.interval, self.after = interval, after
        self.calls = []
        self.stopped = False

    def is_set(self):
        return self.stopped

    def wait(self, seconds):
        self.calls.append(seconds)
        if self.calls.count(self.interval) >= self.after:
            self.stopped = True
        return self.stopped


class EncodedOutput:
    """The previous stdout encoding, used as an event-equivalence oracle."""
    def __init__(self, stream):
        self.stream = stream

    def __call__(self, event):
        self.stream.write((json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8"))


class CollectorRelayTests(unittest.TestCase):
    def collect(self, run, connections, stop, raw=True):
        stream = io.BytesIO()
        emit = agent.CollectorOutput(stream) if raw else EncodedOutput(stream)
        with patch.object(agent, "connect", side_effect=connections) as connect:
            run(emit, stop)
        self.assertEqual(connect.call_count, len(connections))
        self.assertTrue(all(c.closed for c in connections))
        output = stream.getvalue()
        return [ui.collector_event(line) for line in output.splitlines(keepends=True)], output

    def test_state_messages_keep_subscription_validation_and_payload(self):
        data = {"t": 1.25, "joints": [-0.0, -1.25, 2.5], "name": "鸭子🙂",
                "id": 2**63 + 1, "frames": {"head": [1, 0, 0, 0]},
                "literal": 'quotes " and newline\n and slash \\'}
        lines = [reply({"accepted": True, "policies": ["walk"]}),
                 reply({"ignored": True}, 9),
                 wire({"method": "other", "params": {"wrong": True}}),
                 wire({"method": "robot.state", "params": []}),
                 wire({"method": "robot.state", "params": data}),
                 wire({"id": 1, "error": {"code": -1, "message": "拒绝"}})]
        run = lambda emit, stop: agent.subscription("robot", "robot.subscribe", "robot.state", 20, emit, stop, "state")
        old, _ = self.collect(run, [IPC(lines)], Stop(2, 1), False)
        current, output = self.collect(run, [IPC(lines)], Stop(2, 1))
        self.assertEqual(current, old)
        self.assertEqual(current[:2], [{"channel": "capabilities", "data": {"accepted": True, "policies": ["walk"]}},
                                      {"channel": "state", "data": data}])
        self.assertIn("拒绝", current[2]["error"])
        self.assertEqual(output.count(b'"rpc":'), 1)

    def test_bus_reconnect_reloads_calibration_once_and_preserves_polling(self):
        def connections():
            return [IPC([reply({"phase": "configuring_uart", "cycle": 1}),
                         reply({"phase": "control", "cycle": 2, "native": {"joints": []}}),
                         reply({"calibration": {"joints": [{"id": 20, "zero_raw": 2035}]}}, 2),
                         reply({"phase": "control", "cycle": 3})]),
                    IPC([reply({"phase": "control", "cycle": 4}),
                         reply({"calibration": {"joints": [{"id": 20, "zero_raw": 2040}]}}, 2)])]
        run = lambda emit, stop: agent.bus_loop("robot", emit, stop)
        old, _ = self.collect(run, connections(), Stop(.1, 4), False)
        peers = connections()
        stop = Stop(.1, 4)
        current, output = self.collect(run, peers, stop)
        self.assertEqual(current, old)
        self.assertEqual([e["data"]["cycle"] for e in current if e["channel"] == "bus" and "data" in e], [1, 2, 3, 4])
        self.assertEqual(len([e for e in current if e["channel"] == "calibration"]), 2)
        self.assertEqual([r["method"] for r in peers[0].requests],
                         ["robot.busStatus", "robot.busStatus", "robot.busCommand", "robot.busStatus", "robot.busStatus"])
        self.assertEqual(peers[1].requests[1]["params"], {"action": "calibration-status"})
        self.assertEqual(stop.calls.count(.1), 4)
        self.assertEqual(stop.calls.count(2), 2)
        self.assertEqual(output.count(b'"rpc":'), 4)

    def test_tof_quiet_refresh_and_next_frame_keep_the_same_subscription_events(self):
        def connections():
            return [IPC([reply({"accepted": True, "available": False})], socket.timeout()),
                    IPC([reply({"accepted": True, "available": True}),
                         wire({"method": "tof.frame", "params": {"seq": 12, "distance_mm": [100, None, 200]}})])]
        run = lambda emit, stop: agent.subscription("tof", "tof.stream", "tof.frame", None, emit, stop, "tof")
        old, _ = self.collect(run, connections(), Stop(2, 2), False)
        peers = connections()
        current, _ = self.collect(run, peers, Stop(2, 2))
        self.assertEqual(current, old)
        self.assertEqual(peers[0].timeouts, [agent.TOF_IDLE_SECONDS])
        self.assertEqual(peers[1].timeouts, [None, agent.TOF_IDLE_SECONDS])
        self.assertTrue(all("params" not in p.requests[0] for p in peers))
        self.assertEqual(current[2], {"channel": "tof", "data": {"seq": 12, "distance_mm": [100, None, 200]}})

    def test_rejected_bus_ids_and_subscription_acknowledgements_are_not_forwarded(self):
        cases = [
            (lambda emit, stop: agent.bus_loop("robot", emit, stop), reply({"phase": "control"}, 99)),
            (lambda emit, stop: agent.bus_loop("robot", emit, stop), reply([])),
            (lambda emit, stop: agent.subscription("robot", "robot.subscribe", "robot.state", 20, emit, stop, "state"), reply({"accepted": False})),
        ]
        for run, line in cases:
            with self.subTest(line=line):
                old, _ = self.collect(run, [IPC([line])], Stop(2, 1), False)
                current, output = self.collect(run, [IPC([line])], Stop(2, 1))
                self.assertEqual(current, old)
                self.assertEqual(len(current), 1)
                self.assertIn("error", current[0])
                self.assertNotIn(b'"rpc":', output)

    def test_nonfinite_payloads_keep_strict_output_errors_before_calibration(self):
        run = lambda emit, stop: agent.bus_loop("robot", emit, stop)
        for number in (b"NaN", b"Infinity", b"-Infinity", b"1e400", b"-1e400"):
            with self.subTest(number=number):
                line = b'{"id":1,"result":{"phase":"control","nested":[{"number":' + number + b'}]}}\n'
                old, _ = self.collect(run, [IPC([line])], Stop(2, 1), False)
                peer = IPC([line])
                current, output = self.collect(run, [peer], Stop(2, 1))
                self.assertEqual(current, old)
                self.assertIn("Out of range float", current[0]["error"])
                self.assertEqual(len(peer.requests), 1)
                self.assertNotIn(b'"rpc":', output)

    def test_nonfinite_ignored_rpc_fields_do_not_reject_a_valid_payload(self):
        # The old encoder only saw params; unrelated RPC data must stay irrelevant.
        lines = [reply({"accepted": True}),
                 b'{"method":"ignored","params":{"x":NaN}}\n',
                 b'{"method":"robot.state","params":{"t":1.5,"x":"NaN Infinity 1e400"},"unused":1e400}\n']
        run = lambda emit, stop: agent.subscription("robot", "robot.subscribe", "robot.state", 20, emit, stop, "state")
        old, _ = self.collect(run, [IPC(lines)], Stop(2, 1), False)
        current, output = self.collect(run, [IPC(lines)], Stop(2, 1))
        self.assertEqual(current, old)
        self.assertEqual(current[1]["data"], {"t": 1.5, "x": "NaN Infinity 1e400"})
        self.assertNotIn(b'"rpc":', output)

    def test_bom_and_utf16_utf32_frames_preserve_existing_payload_encoding(self):
        # bytes accepted by json.loads need not be valid inside a UTF-8 object.
        text = '{"method":"robot.state","params":{"t":1.5,"name":"鸭"}}\n'
        lines = [text.encode("utf-8-sig"), text.encode("utf-16-be"), text.encode("utf-32-be"),
                 b"\xfe\xff" + text.encode("utf-16-be"), b"\x00\x00\xfe\xff" + text.encode("utf-32-be")]
        run = lambda emit, stop: agent.subscription("robot", "robot.subscribe", "robot.state", 20, emit, stop, "state")
        for line in lines:
            with self.subTest(encoding_prefix=line[:4]):
                expected = json.loads(line)
                self.assertEqual(agent.json_line(io.BytesIO(line)), expected)
                messages = [reply({"accepted": True}), line]
                old, old_output = self.collect(run, [IPC(messages)], Stop(2, 1), False)
                current, output = self.collect(run, [IPC(messages)], Stop(2, 1))
                self.assertEqual(current, old)
                self.assertEqual(current[1], {"channel": "state", "data": expected["params"]})
                self.assertEqual(output, old_output)
                self.assertNotIn(b'"rpc":', output)
        # Little-endian LF splits its final code unit in the original byte-line
        # reader; retaining the original bytes must retain that decode failure.
        for encoding in ("utf-16-le", "utf-32-le"):
            line = io.BytesIO(text.encode(encoding)).readline(agent.MAX_LINE + 1)
            with self.assertRaises(UnicodeDecodeError):
                json.loads(line)
            with self.assertRaises(UnicodeDecodeError):
                agent.json_line(io.BytesIO(line))

    def test_lone_surrogates_keep_original_utf8_output_errors(self):
        run = lambda emit, stop: agent.subscription("robot", "robot.subscribe", "robot.state", 20, emit, stop, "state")
        payloads = [b'{"name":"\\ud800"}', b'{"name":"\\uDFFF"}',
                    b'{"\\ud800":1}', b'{"nested":[{"name":"\xed\xa0\x80"}]}',
                    b'{"name":"\xed\xb0\x80"}']
        for payload in payloads:
            with self.subTest(payload=payload):
                line = b'{"method":"robot.state","params":' + payload + b'}\n'
                # The old input decoder accepts these; the old output rejects.
                json.loads(line)
                messages = [reply({"accepted": True}), line]
                old, old_output = self.collect(run, [IPC(messages)], Stop(2, 1), False)
                current, output = self.collect(run, [IPC(messages)], Stop(2, 1))
                self.assertEqual(current, old)
                self.assertEqual(output, old_output)
                self.assertIn("surrogates not allowed", current[1]["error"])
                self.assertNotIn(b'"rpc":', output)

    def test_valid_pairs_and_ignored_surrogates_are_not_rejected(self):
        run = lambda emit, stop: agent.subscription("robot", "robot.subscribe", "robot.state", 20, emit, stop, "state")
        lines = [b'{"method":"robot.state","params":{"name":"\\ud83d\\ude42"}}\n',
                 b'{"method":"robot.state","params":{"text":"\\\\ud800"}}\n',
                 b'{"method":"robot.state","params":{"t":1.5},"unused":"\\ud800"}\n',
                 b'{"method":"robot.state","params":{"t":2.5},"unused":"\xed\xa0\x80"}\n']
        messages = [reply({"accepted": True}), *lines]
        old, old_output = self.collect(run, [IPC(messages)], Stop(2, 1), False)
        current, output = self.collect(run, [IPC(messages)], Stop(2, 1))
        self.assertEqual(current, old)
        self.assertEqual(output, old_output)
        self.assertEqual([e["data"] for e in current[1:-1]],
                         [{"name": "🙂"}, {"text": "\\ud800"}, {"t": 1.5}, {"t": 2.5}])
        self.assertNotIn(b'"rpc":', output)

    def test_local_callbacks_preserve_surrogates_and_unusual_encodings(self):
        lines = [b'{"method":"robot.state","params":{"name":"\\ud800"}}\n',
                 b'{"method":"robot.state","params":{"name":"\xed\xa0\x80"}}\n',
                 '{"method":"robot.state","params":{"name":"鸭"}}\n'.encode("utf-16-be")]
        events = []
        with patch.object(agent, "connect", return_value=IPC([reply({"accepted": True}), *lines])):
            agent.subscription("robot", "robot.subscribe", "robot.state", 20, events.append, Stop(2, 1), "state")
        self.assertEqual(events[1:-1], [{"channel": "state", "data": json.loads(line)["params"]} for line in lines])
        self.assertTrue(all(type(event) is dict and type(event["data"]) is dict for event in events[:-1]))

    def test_small_health_and_capability_events_keep_their_existing_encoding(self):
        for run, lines, stop_args in (
            (lambda emit, stop: agent.health_loop("robot", emit, stop), [reply({"healthy": True})], (1, 1)),
            (lambda emit, stop: agent.capabilities_loop("robot", emit, stop), [reply({"accepted": True, "policies": ["walk"]})], (10, 2)),
        ):
            old, old_output = self.collect(run, [IPC(lines)], Stop(*stop_args), False)
            current, output = self.collect(run, [IPC(lines)], Stop(*stop_args))
            self.assertEqual(current, old)
            self.assertEqual(output, old_output)

    def test_local_callback_payloads_are_plain_events_without_transport_metadata(self):
        events = []
        peer = IPC([reply({"phase": "control", "position": float("nan")}), reply({"calibration": {}}, 2)])
        with patch.object(agent, "connect", return_value=peer):
            agent.bus_loop("robot", events.append, Stop(.1, 1))
        self.assertEqual(set(events[0]), {"channel", "data"})
        self.assertIs(type(events[0]), dict)
        self.assertIs(type(events[0]["data"]), dict)
        self.assertTrue(math.isnan(events[0]["data"]["position"]))
        self.assertEqual(events[1], {"channel": "calibration", "data": {"calibration": {}}})

    def test_ipc_limits_eof_and_bad_json_remain_enforced(self):
        for data, error in ((b"", ConnectionError), (b"{}", ValueError),
                            (b"[]\n", ValueError), (b"{broken}\n", ValueError),
                            (b" " * agent.MAX_LINE + b"{}\n", ValueError)):
            with self.subTest(data=data[:40]):
                with self.assertRaises(error):
                    agent.json_line(io.BytesIO(data))

    def test_maximum_ipc_line_fits_the_bounded_ssh_envelope(self):
        prefix, suffix = b'{"id":1,"result":{"payload":"', b'"}}\n'
        raw = prefix + b"x" * (agent.MAX_LINE - len(prefix) - len(suffix)) + suffix
        stream = io.BytesIO()
        agent.emit_ipc(agent.CollectorOutput(stream), "bus", agent.json_line(io.BytesIO(raw)), "result")
        output = stream.getvalue()
        self.assertLessEqual(len(output), agent.MAX_COLLECTOR_LINE)
        self.assertEqual(ui.collector_event(output)["data"], json.loads(raw)["result"])
        with self.assertRaises(ValueError):
            ui.collector_event(output[:-1])
        with self.assertRaises(ValueError):
            ui.collector_event(b" " * agent.MAX_COLLECTOR_LINE + b"{}\n")

    def test_desktop_rejects_malformed_raw_envelopes_and_nonfinite_data(self):
        for event in ({"channel": "bus", "rpc": {"id": 2, "result": {}}},
                      {"channel": "state", "rpc": {"method": "wrong", "params": {}}},
                      {"channel": "state", "rpc": {"id": 1, "method": "robot.state", "params": {}}},
                      {"channel": "tof", "rpc": {"method": "tof.frame", "params": []}},
                      {"channel": "unknown", "rpc": {}}, {"channel": "bus", "rpc": None},
                      {"channel": "bus", "rpc": {"id": 1, "result": {}}, "data": {}}, []):
            with self.subTest(event=event):
                with self.assertRaises(ValueError):
                    ui.collector_event(wire(event))
        for number in (b"NaN", b"Infinity", b"-Infinity", b"1e400"):
            with self.assertRaises(ValueError):
                ui.collector_event(b'{"channel":"bus","rpc":{"id":1,"result":{"n":' + number + b'}}}\n')

    def test_partial_writes_and_concurrent_channels_cannot_interleave_json_lines(self):
        class PartialStream:
            def __init__(self):
                self.data = bytearray()
                self.flushes = 0

            def write(self, data):
                count = min(len(data), 13)
                self.data.extend(data[:count])
                time.sleep(0)
                return count

            def flush(self):
                self.flushes += 1

        stream = PartialStream()
        output = agent.CollectorOutput(stream)
        def write_channel(channel):
            for seq in range(8):
                data = {"seq": seq, "text": "鸭" * 20}
                if channel == "system":
                    output({"channel": channel, "data": data})
                else:
                    message = agent.json_line(io.BytesIO(wire({"method": "robot.state", "params": data})))
                    agent.emit_ipc(output, channel, message, "params")
        workers = [threading.Thread(target=write_channel, args=(channel,)) for channel in ("state", "system")]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=5)
            self.assertFalse(worker.is_alive())
        events = [ui.collector_event(line) for line in bytes(stream.data).splitlines(keepends=True)]
        self.assertEqual(len(events), 16)
        self.assertEqual(stream.flushes, 16)
        for channel in ("state", "system"):
            self.assertEqual([event["data"]["seq"] for event in events if event["channel"] == channel], list(range(8)))

    def test_closed_stdout_exits_instead_of_retrying_or_spinning(self):
        class Closed:
            def __init__(self, result):
                self.result = result

            def write(self, _):
                if isinstance(self.result, Exception):
                    raise self.result
                return self.result
        for result in (BrokenPipeError(), 0, None):
            with self.subTest(result=result):
                with patch.object(agent.os, "_exit", side_effect=SystemExit) as exit_process:
                    with self.assertRaises(SystemExit):
                        agent.CollectorOutput(Closed(result))({"channel": "system", "data": {}})
                exit_process.assert_called_once_with(0)


if __name__ == "__main__":
    unittest.main()

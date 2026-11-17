"""Voice test: what the panel says, and that playback is the official intent.

A fake Unix socket stands in for `robotd`, so the request bytes and the refusal
handling are checked for real: tag names, `hold` on the wheee ride, and the
read-only refusal that commissioning mode produces today. Nothing here plays
audio or touches the board.
"""
import json
import os
import socket
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import controls
import sound_test


class FakeDaemon:
    """Accepts one connection and answers like robotd's JSON-RPC socket."""

    def __init__(self, reply):
        self.reply = reply
        self.requests = []
        self.path = os.path.join(tempfile.mkdtemp(prefix="duck-sock-"), "robotd.sock")
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(self.path)
        self.server.listen(4)
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()

    def serve(self):
        while True:
            try:
                client, _ = self.server.accept()
            except OSError:
                return
            with client, client.makefile("rwb") as stream:
                while True:
                    line = stream.readline()
                    if not line:
                        break
                    request = json.loads(line)
                    self.requests.append(request)
                    answer = self.reply(request)
                    if answer is None:
                        break
                    stream.write(json.dumps(answer).encode() + b"\n")
                    stream.flush()

    def close(self):
        self.server.close()
        os.unlink(self.path)


def accepted(request):
    return {"jsonrpc": "2.0", "id": request["id"],
            "result": {"accepted": True, "tag": request["params"]["tag"]}}


def refused(message):
    def answer(request):
        return {"jsonrpc": "2.0", "id": request["id"], "error": {"code": -32600, "message": message}}
    return answer


class VoiceTests(unittest.TestCase):
    def daemon(self, reply):
        daemon = FakeDaemon(reply)
        self.addCleanup(daemon.close)
        original = sound_test.SOCKET
        sound_test.SOCKET = daemon.path
        self.addCleanup(lambda: setattr(sound_test, "SOCKET", original))
        return daemon

    def board(self, enabled="true", bank=True):
        root = Path(tempfile.mkdtemp(prefix="duck-snd-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        config = root / "robotd.toml"
        config.write_text('[audio]\n# enabled = false\nenabled = %s\ndevice = "plughw:aic3104"\n'
                          'bank = "%s"\n' % (enabled, root / "bank"), encoding="utf-8")
        if bank:
            for tag in sound_test.TAGS:
                (root / "bank" / tag).mkdir(parents=True)
                (root / "bank" / tag / (tag + "_a.wav")).write_bytes(b"RIFF")
        original = sound_test.CONFIG
        sound_test.CONFIG = str(config)
        self.addCleanup(lambda: setattr(sound_test, "CONFIG", original))
        return root

    def test_a_one_shot_is_one_robot_sound_with_no_hold(self):
        daemon = self.daemon(accepted)
        answer = sound_test.play("chirp")
        self.assertTrue(answer["accepted"])
        self.assertEqual(answer["via"], "robotd")
        self.assertEqual([request["method"] for request in daemon.requests], ["robot.sound"])
        self.assertEqual(daemon.requests[0]["params"], {"tag": "chirp"})

    def test_the_ride_is_started_and_released_on_one_connection(self):
        daemon = self.daemon(accepted)
        answer = sound_test.play("wheee")
        self.assertTrue(answer["accepted"])
        self.assertEqual(daemon.requests[0]["params"], {"tag": "wheee", "hold": True})
        self.assertEqual(daemon.requests[1]["params"], {"tag": "wheee", "hold": False})
        self.assertEqual(len(daemon.requests), 2)

    def test_the_ride_release_follows_a_short_hold(self):
        daemon = self.daemon(accepted)
        started = time.monotonic()
        sound_test.play("wheee")
        self.assertGreaterEqual(time.monotonic() - started, sound_test.WHEEE_HOLD * .9)
        self.assertEqual([request["params"]["hold"] for request in daemon.requests], [True, False])

    def test_commissioning_read_only_is_explained_rather_than_retried(self):
        daemon = self.daemon(refused(
            "robotd is read-only: motor commands are disabled; uncalibrated telemetry is "
            "available via robot.busStatus"))
        answer = sound_test.play("chirp")
        self.assertFalse(answer["accepted"])
        self.assertIn("标定模式", answer["reason"])
        self.assertIn("运动模式", answer["reason"])
        self.assertEqual(len(daemon.requests), 1, "a refusal is not retried")

    def test_a_ride_refused_at_the_start_is_not_released_afterwards(self):
        daemon = self.daemon(refused("robotd is read-only: motor commands are disabled"))
        answer = sound_test.play("wheee")
        self.assertFalse(answer["accepted"])
        self.assertEqual(len(daemon.requests), 1, "no release after a refused start")

    def test_an_unknown_tag_never_reaches_the_socket(self):
        daemon = self.daemon(accepted)
        answer = sound_test.play("nope")
        self.assertFalse(answer["accepted"])
        self.assertEqual(daemon.requests, [])

    def test_a_missing_socket_says_robotd_may_not_be_running(self):
        original = sound_test.SOCKET
        sound_test.SOCKET = "/run/definitely-not-here.sock"
        self.addCleanup(lambda: setattr(sound_test, "SOCKET", original))
        answer = sound_test.main({"action": "play", "tag": "chirp"})
        self.assertEqual(answer, 1, "a failed play is a non-zero exit for the SSH caller")

    def test_describe_counts_the_bank_the_daemon_will_read(self):
        self.board()
        described = sound_test.describe()
        self.assertTrue(described["can_play"])
        self.assertEqual([row["tag"] for row in described["tags"]], list(sound_test.TAGS))
        self.assertTrue(all(row["wavs"] == 1 for row in described["tags"]))
        self.assertEqual(described["reason"], "")

    def test_describe_calls_out_a_disabled_audio_section(self):
        self.board(enabled="false")
        described = sound_test.describe()
        self.assertFalse(described["can_play"])
        self.assertIn("enabled = false", described["reason"])

    def test_describe_calls_out_an_empty_bank(self):
        self.board(bank=False)
        described = sound_test.describe()
        self.assertFalse(described["can_play"])
        self.assertIn("wav", described["reason"])

    def test_every_tag_has_a_chinese_name(self):
        self.assertEqual(set(sound_test.NAMES), set(sound_test.TAGS))
        for name in sound_test.NAMES.values():
            self.assertTrue(name.strip())


class ConsoleWiringTests(unittest.TestCase):
    """The console must reject a tag before it reaches the board, and use no aplayer."""

    def test_console_tag_list_matches_the_board_helper(self):
        self.assertEqual(tuple(controls.SOUND_TAGS), tuple(sound_test.TAGS),
                         "a tag the page offers must be one the helper can play")

    def test_helper_source_has_no_aplay_fallback(self):
        import ast
        source = Path(controls.ROOT, "sound_test.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        identifiers = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                identifiers.add(node.id)
            elif isinstance(node, ast.Attribute):
                identifiers.add(node.attr)
            elif isinstance(node, ast.alias):
                identifiers.add(node.name)
            elif isinstance(node, ast.ImportFrom):
                identifiers.add(node.module or "")
        for forbidden in ("aplay", "arecord", "amixer", "subprocess", "Popen", "amixer"):
            self.assertNotIn(forbidden, identifiers, "%s would bypass the official intent" % forbidden)
        # The socket protocol is the only way this file talks to the robot.
        self.assertIn("socket", identifiers)

    def test_console_runs_the_helper_unprivileged(self):
        source = Path(controls.ROOT, "controls.py").read_text(encoding="utf-8")
        start = source.index("def _sound(")
        body = source[start:source.index("def _local_status(", start)]
        self.assertIn("privileged=False", body)
        self.assertIn("sound_test.py", body)


if __name__ == "__main__":
    unittest.main()

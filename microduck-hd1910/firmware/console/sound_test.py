"""Play the robot's voice through the official `robot.sound` intent, and nothing else.

Runs on the board as an ordinary process, pushed inline over the existing SSH
channel (`python3 -u -c <this source> <json>`), so nothing is installed and no
`sudo` is involved. It speaks JSON-RPC over `/run/robotd.sock` exactly as `padd`
does, which means a test button and the trigger on a real hand controller take
the same path through the daemon — the same wav, the same single client PCM, the
same volume.

There is deliberately no `aplay` fallback. `aplay` here would prove the speaker
works while the thing that actually plays during play does not, and it would
race `robotd` for the one PCM. When the daemon refuses — commissioning mode is
read-only, audio is disabled in `robotd.toml`, the bank never rendered — the
answer says which of those it is and the page points at the mode switch.
"""
import json
import os
import re
import socket
import sys
import time

SOCKET = "/run/robotd.sock"
CONFIG = "/etc/robot/feetech-ft5/robotd.toml"

# The daemon's own tag list (`SoundTag`); the wav directories are named after it.
TAGS = ("chirp", "wheee", "greet", "inquire", "coo", "alarm", "peck")
NAMES = {"chirp": "短叫", "wheee": "持续长叫", "greet": "打招呼",
         "inquire": "疑问", "coo": "咕咕", "alarm": "警戒", "peck": "啄食声"}
# How long a held wheee rides before release. Long enough to hear the loop,
# short enough that a click cannot leave the duck mid-ride.
WHEEE_HOLD = 0.9


def audio_settings():
    """`[audio]` from robotd.toml, read with a tiny parser.

    tomllib exists on the board's Python 3.11+, but this file is also pushed to
    whatever `python3` SSH lands on, and a syntax error in the source would be
    indistinguishable from a connection failure. Keys and table names may be
    quoted (`["audio"]`, `"enabled" = true`), which is what the board ships, so
    the quotes are optional in every pattern here.
    """
    try:
        with open(CONFIG, encoding="utf-8", errors="replace") as handle:
            text = handle.read()
    except OSError:
        return {"enabled": None, "bank": None, "error": "读不到 robotd.toml"}
    section = re.search(r"""^\s*\[\s*["']?audio["']?\s*\](.*?)(?=^\s*\[|\Z)""", text, re.M | re.S)
    if not section:
        return {"enabled": None, "bank": None, "error": "robotd.toml 没有 [audio] 段"}
    body = section[1]
    enabled = re.search(r"""^\s*["']?enabled["']?\s*=\s*(true|false)""", body, re.M)
    bank = re.search(r"""^\s*["']?bank["']?\s*=\s*["']([^"']+)["']""", body, re.M)
    return {"enabled": enabled[1] == "true" if enabled else None,
            "bank": bank[1] if bank else None, "error": ""}


def bank_counts(bank):
    """How many wavs each tag has, so an empty bank reads as empty."""
    counts = {}
    if not bank:
        return counts
    for tag in TAGS:
        path = os.path.join(bank, tag)
        try:
            counts[tag] = len([name for name in os.listdir(path) if name.endswith(".wav")])
        except OSError:
            counts[tag] = 0
    return counts


def describe():
    settings = audio_settings()
    counts = bank_counts(settings["bank"])
    total = sum(counts.values())
    reason = ""
    if settings["enabled"] is False:
        reason = "robotd.toml 里 [audio] enabled = false，服务不会发声"
    elif settings["error"]:
        reason = settings["error"]
    elif total == 0:
        reason = "音库 %s 里没有 wav，服务会拒绝发声" % (settings["bank"] or "(未配置)")
    return {"tags": [{"tag": tag, "name": NAMES[tag], "wavs": counts.get(tag, 0)} for tag in TAGS],
            "bank": settings["bank"], "enabled": settings["enabled"],
            "can_play": not reason, "reason": reason}


def connect(timeout=3.0):
    channel = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    channel.settimeout(timeout)
    try:
        channel.connect(SOCKET)
    except OSError:
        channel.close()
        raise
    return channel


def call(channel, ident, method, params):
    request = {"jsonrpc": "2.0", "id": ident, "method": method}
    if params is not None:
        request["params"] = params
    channel.sendall(json.dumps(request).encode() + b"\n")
    reader = channel.makefile("rb")
    line = reader.readline(1 << 20)
    if not line:
        raise ConnectionError("robotd 关闭了连接")
    return json.loads(line)


def refusal(error):
    """Turn the daemon's error into something a person can act on."""
    message = str(error or "")
    if "read-only" in message:
        return ("当前 robotd 处于标定模式，官方接口拒绝发声；"
                "到「机器人服务模式」切到运动模式后再试")
    if "audio" in message.lower() and "enabled" in message.lower():
        return "robotd 的声音功能被配置关掉了（[audio] enabled = false）"
    return message or "robotd 没有说明拒绝原因"


def play(tag):
    if tag not in TAGS:
        return {"accepted": False, "via": "robotd", "tag": tag, "reason": "不支持的声音"}
    channel = connect()
    try:
        if tag == "wheee":
            # The ride is a level: start, hold briefly, release. All three go
            # through this one connection so the release cannot outlive us.
            started = call(channel, 1, "robot.sound", {"tag": "wheee", "hold": True})
            if started.get("error"):
                return {"accepted": False, "via": "robotd", "tag": tag,
                        "reason": refusal(started["error"].get("message")),
                        "detail": started["error"]}
            time.sleep(WHEEE_HOLD)
            released = call(channel, 2, "robot.sound", {"tag": "wheee", "hold": False})
            if released.get("error"):
                return {"accepted": False, "via": "robotd", "tag": tag,
                        "reason": refusal(released["error"].get("message")),
                        "detail": released["error"]}
            result = released.get("result") or {}
        else:
            answer = call(channel, 1, "robot.sound", {"tag": tag})
            if answer.get("error"):
                return {"accepted": False, "via": "robotd", "tag": tag,
                        "reason": refusal(answer["error"].get("message")),
                        "detail": answer["error"]}
            result = answer.get("result") or {}
    finally:
        channel.close()
    if result.get("accepted") is not True:
        return {"accepted": False, "via": "robotd", "tag": tag,
                "reason": refusal(result.get("reason")), "detail": result}
    return {"accepted": True, "via": "robotd", "tag": tag, "name": NAMES[tag],
            "detail": result, "reason": ""}


def main(request):
    action = request.get("action")
    if action == "list":
        print(json.dumps(describe(), ensure_ascii=False))
        return 0
    if action != "play":
        print(json.dumps({"accepted": False, "reason": "未知操作"}, ensure_ascii=False))
        return 2
    try:
        answer = play(request.get("tag"))
    except OSError as exc:
        answer = {"accepted": False, "via": "robotd", "tag": request.get("tag"),
                  "reason": "连不上 %s：%s；robotd 可能没在运行" % (SOCKET, exc)}
    except Exception as exc:  # noqa: BLE001 - the page shows the reason verbatim
        answer = {"accepted": False, "via": "robotd", "tag": request.get("tag"),
                  "reason": "%s: %s" % (type(exc).__name__, exc)}
    print(json.dumps(answer, ensure_ascii=False))
    return 0 if answer.get("accepted") else 1


if __name__ == "__main__":
    sys.exit(main(json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}))

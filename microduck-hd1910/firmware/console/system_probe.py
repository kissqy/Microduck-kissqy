"""What systemd and the board's sysfs say, collected without touching a device.

Runs on the board as an ordinary process (`python3 -u -c <this source> <json>`),
pushed over the existing SSH channel exactly like the repair and diagnostic
helpers: nothing installed, no `sudo`, no device node opened. It answers the one
question the raw robotd telemetry cannot — which services are up, whether the
hardware behind each one is fitted, and which of them start at boot.

Kept separate from `agent.py` because the deployed console mode (`--feetech`)
talks to `robotd` over a raw byte channel and never runs that collector; this
file is the single implementation both modes share.
"""
import glob
import json
import os
import re
import subprocess
import sys
from pathlib import Path

UNIT_FIELDS = ("Id", "LoadState", "ActiveState", "SubState", "UnitFileState",
               "MainPID", "MemoryCurrent", "NRestarts", "ExecStart")


def parse_systemctl_show(text):
    """Split `systemctl show` output into one record per unit."""
    records, block = [], {}
    for line in text.splitlines() + [""]:
        if line.strip():
            key, _, value = line.partition("=")
            block[key.strip()] = value
        elif block:
            records.append(block)
            block = {}
    return records


def _integer(value):
    # systemd prints `[not set]` for absent properties and UINT64_MAX for an
    # unset MemoryCurrent; neither is a measurement.
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return None if number < 0 or number >= 2**63 else number


# Where systemd looks for a unit file, in its own precedence order.
UNIT_DIRS = ("/etc/systemd/system", "/run/systemd/system", "/usr/local/lib/systemd/system",
             "/usr/lib/systemd/system", "/lib/systemd/system")


def unit_installed(name, root="/"):
    """Is there a real unit file, as opposed to only a mask?

    `systemctl mask` works without the unit existing at all (it just plants a
    /dev/null symlink), so `masked` alone cannot tell "installed but silenced"
    from "never installed on this board". Unmasking the latter and then calling
    `enable` fails with "Unit X does not exist", which would leave the board in a
    state it was not in before — so this is checked first.
    """
    for directory in UNIT_DIRS:
        path = os.path.join(root, directory.lstrip("/"), name)
        if not os.path.lexists(path):
            continue
        if os.path.islink(path) and os.path.realpath(path) == os.devnull:
            continue  # the mask itself is not the unit
        return True
    return False


def read_units(names, runner=subprocess.run, root="/"):
    """Ask systemd about every watched unit in one call.

    Units this board never installed still come back, with LoadState=not-found,
    which is what lets the page say "未安装" instead of pretending they are fine.
    """
    names = [str(name) for name in names if str(name)]
    if not names:
        return [], ""
    command = ["systemctl", "show", *names, "--no-pager"]
    for field in UNIT_FIELDS:
        command += ["-p", field]
    try:
        result = runner(command, capture_output=True, text=True, timeout=6)
    except (OSError, subprocess.SubprocessError) as exc:
        return [], "systemctl 不可用：" + str(exc)
    if isinstance(getattr(result, "stdout", None), bytes):
        text = result.stdout.decode(errors="replace")
    else:
        text = result.stdout or ""
    by_id = {row.get("Id"): row for row in parse_systemctl_show(text)}
    units = []
    for name in names:
        row = by_id.get(name, {})
        exec_start = row.get("ExecStart") or ""
        path = re.search(r"path=([^ ;]+)", exec_start)
        executable = path[1] if path else ""
        units.append({
            "unit": name,
            "load": row.get("LoadState") or "not-found",
            "active": row.get("ActiveState") or "unknown",
            "sub": row.get("SubState") or "",
            "enabled": row.get("UnitFileState") or "",
            # MainPID=0 is "no process", not pid 0; the rest are real zeros.
            "pid": _integer(row.get("MainPID")) or None,
            "memory": _integer(row.get("MemoryCurrent")),
            "restarts": _integer(row.get("NRestarts")),
            "executable": executable,
            # presence, not runnability: the file is what systemd would exec, and
            # the collector may not hold the permission the unit runs with.
            "executable_present": os.path.exists(executable) if executable else None,
            "installed": unit_installed(name, root),
        })
    return units, ""


def capability_bit(words, bit):
    """Read one bit from a `/sys/class/input/*/capabilities/*` hex bitmap."""
    parts = str(words).split()
    index, offset = divmod(bit, 64)
    if index >= len(parts):
        return False
    try:
        return bool(int(parts[-1 - index], 16) & (1 << offset))
    except ValueError:
        return False


def gamepad_names(root="/"):
    """Gamepads, by the same rule robotd uses for `real_gamepads`.

    A gamepad button (BTN_SOUTH) plus two absolute axes: keyboards and
    accelerometers also have `event*` nodes and none of them is a pad.
    """
    found = []
    for path in sorted(glob.glob(os.path.join(root, "sys/class/input/event*"))):
        if not os.path.basename(path)[len("event"):].isdigit():
            continue
        device = os.path.join(path, "device")
        try:
            name = Path(device, "name").read_text(errors="replace").strip()
            keys = Path(device, "capabilities/key").read_text(errors="replace")
            axes = Path(device, "capabilities/abs").read_text(errors="replace")
        except OSError:
            continue
        if capability_bit(keys, 0x130) and capability_bit(axes, 0) and capability_bit(axes, 1):
            found.append(name or os.path.basename(path))
    return found


def servo_port(root="/"):
    """The bus port robotd is configured for, so the check follows the config."""
    path = os.path.join(root, "etc/robot/feetech-ft5/robotd.toml")
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "/dev/ttyS2"
    section = re.search(r"^\[bus\](.*?)(?=^\[|\Z)", text, re.M | re.S)
    port = re.search(r'^\s*port\s*=\s*"([^"]+)"', section[1] if section else "", re.M)
    return port[1] if port else "/dev/ttyS2"


def read_hardware(root="/"):
    """Hardware presence from sysfs, /dev and /proc only.

    Nothing here opens a device node: a probe that writes to the bus could
    interleave with a tick, and `tof` stays unknown until someone asks for it.
    `servos` is absent on purpose — only robotd can count them.
    """
    def at(relative):
        return os.path.join(root, relative.lstrip("/"))

    def present(relative):
        return os.path.exists(at(relative))

    def show(relative):
        try:
            return Path(at(relative)).read_text(errors="replace").strip()
        except OSError:
            return ""

    port = servo_port(root)
    bluetooth = present("/sys/class/bluetooth/hci0")
    pads = gamepad_names(root)
    video = present("/dev/video0")
    video_name = show("/sys/class/video4linux/video0/name") if video else ""
    i2c3 = present("/dev/i2c-3")
    cards = show("/proc/asound/cards")
    codec = re.search(r"^\s*\d+\s+\[\s*aic3104\s*\]", cards, re.M) is not None
    pcm = sorted(glob.glob(at("dev/snd/pcmC*D0p")))
    return {
        "servo_bus": {"present": present(port), "detail": port},
        "bluetooth": {"present": bluetooth, "detail": "hci0" if bluetooth else "无 HCI 设备"},
        "gamepad": {"present": bool(pads), "detail": "、".join(pads) if pads else "无手柄输入设备"},
        "camera": {"present": video, "detail": (video_name or "/dev/video0") if video else "无 /dev/video0"},
        "i2c3": {"present": i2c3, "detail": "/dev/i2c-3" if i2c3 else "无 /dev/i2c-3（overlay 未加载或排针未接）"},
        "tof": {"present": None,
                "detail": "I²C3 在，0x29 待探测" if i2c3 else "I²C3 总线不在，无法探测"},
        "audio_codec": {"present": bool(codec or pcm),
                        "detail": "、".join(filter(None, ["ALSA aic3104" if codec else "",
                                                         "播放 PCM" if pcm else ""])) or "未绑定 aic3104"},
    }


def collect(names, root="/"):
    """One sample for the page: unit rows plus the hardware readings."""
    units, error = read_units(names, root=root)
    sample = {"units": units, "hardware": read_hardware(root)}
    if error:
        sample["error"] = error
    return sample


def main(argv):
    request = json.loads(argv[1]) if len(argv) > 1 else {}
    names = request.get("units") or []
    if not isinstance(names, list):
        print(json.dumps({"error": "unit 名单无效"}, ensure_ascii=False))
        return 2
    print(json.dumps(collect([str(n) for n in names]), ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

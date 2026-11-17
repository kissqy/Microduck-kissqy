"""Robot services the console watches, and the hardware each one needs.

One list, shared by the SSH collector (which units to ask systemd about), the
HTTP layer (which labels and permissions the page receives) and the service
controller (which units may have their autostart changed). Keeping it here
means a unit name sent by a browser can be checked against a constant instead
of being passed to systemctl.

Autostart is deliberately the only thing the page may change. Starting or
stopping a unit is not offered: `systemctl stop robotd` does not release
torque, so a web page that could stop it could also freeze the robot in
place, and "restart the firmware" already exists for the case that needs it.
"""

# hardware ids -> operator-facing name and what a "present" reading means
HARDWARE = {
    "servo_bus": {"label": "FT6 舵机总线", "detail": "半双工 UART"},
    "servos": {"label": "HD-1910 舵机", "detail": "经 robotd 回读"},
    "bluetooth": {"label": "蓝牙适配器", "detail": "HCI 设备"},
    "gamepad": {"label": "无线手柄", "detail": "含摇杆的手柄输入设备"},
    "camera": {"label": "IMX219 摄像头", "detail": "V4L2 采集节点"},
    "i2c3": {"label": "I²C3 总线", "detail": "40 针 M0 排针"},
    "tof": {"label": "VL53L5CX 测距", "detail": "I²C3 0x29"},
    "audio_codec": {"label": "TLV320AIC3104", "detail": "ALSA 声卡 + 播放 PCM"},
}

# Order is the order the page renders; every entry is checked with
# `systemctl show`, including the ones this board may not have installed.
UNITS = (
    {"unit": "robotd.service", "label": "运动控制守护", "note": "策略 / 总线 / IMU",
     "hardware": ("servo_bus", "servos"), "autostart": False},
    {"unit": "padd.service", "label": "手柄意图客户端", "note": "实体手柄 → robotd",
     "hardware": (), "autostart": True},
    {"unit": "gamesir-xboxd.service", "label": "蓝牙手柄桥", "note": "GameSir → Xbox 输入",
     "hardware": ("bluetooth", "gamepad"), "autostart": True},
    {"unit": "mediad.service", "label": "摄像头服务", "note": "IMX219 / WebRTC",
     "hardware": ("camera",), "autostart": True},
    {"unit": "tofd.service", "label": "ToF 测距", "note": "VL53L5CX · J5",
     "hardware": ("i2c3", "tof"), "autostart": True},
    {"unit": "aic3104-init.service", "label": "codec 混音器", "note": "TLV320AIC3104 音量",
     "hardware": ("audio_codec",), "autostart": True},
    {"unit": "bluetooth.service", "label": "蓝牙栈", "note": "手柄链路底座",
     "hardware": ("bluetooth",), "autostart": True},
)

UNIT_NAMES = tuple(row["unit"] for row in UNITS)
AUTOSTART_UNITS = frozenset(row["unit"] for row in UNITS if row["autostart"])
# Units whose bus a manual probe may touch. Kept separate from AUTOSTART_UNITS:
# a unit can be safe to enable and still be the wrong thing to poke at.
PROBE_UNITS = frozenset({"tofd.service"})

# UnitFileState values where `systemctl enable` succeeds as asked. `masked`
# needs an unmask first; `not-found`/`static` cannot be changed at all.
ENABLE_STATES = frozenset({"disabled", "enabled", "linked", "linked-runtime", "indirect", "generated"})
FIXED_STATES = frozenset({"not-found", "static", "bad"})


def label(unit):
    """Chinese name for a unit, falling back to the unit name itself."""
    for row in UNITS:
        if row["unit"] == unit:
            return row["label"]
    return unit


def unit_meta():
    """The page's copy of the catalogue: labels, hardware and what may change."""
    return [{"unit": row["unit"], "label": row["label"], "note": row["note"],
             "hardware": list(row["hardware"]), "autostart": row["autostart"]}
            for row in UNITS]


def hardware_meta():
    return [{"id": key, "label": value["label"], "detail": value["detail"]}
            for key, value in HARDWARE.items()]


def autostart_plan(unit, enabled, unit_file_state, installed=True):
    """The systemctl calls needed to reach `enabled`, or a reason it cannot.

    Returns `(commands, reason)`; exactly one of them is empty. `masked` is a
    symlink to /dev/null, which `enable` does not clear, so it is unmasked
    first — otherwise the toggle would silently leave the unit off at boot.
    A masked unit whose file does not exist is *not* unmasked: `enable` would
    fail with "Unit X does not exist" and the board would be left un-masked,
    which is a state it was not in before the click.
    """
    if unit not in AUTOSTART_UNITS:
        return (), "该服务不允许从中控修改开机自启"
    state = unit_file_state or ""
    if state in FIXED_STATES:
        return (), ("本机未安装 %s" if state == "not-found" else "%s 为内建或损坏的 unit，不能改自启") % unit
    if not installed:
        return (), "本机没有安装 %s（unit 文件不存在），无法设置开机自启" % unit
    if enabled:
        if state == "enabled":
            return (), "当前已经是开机自启"
        commands = []
        if state == "masked":
            commands.append(["unmask", "--", unit])
        commands.append(["enable", "--", unit])
        return tuple(commands), ""
    if state == "masked":
        return (), "该服务已被屏蔽，本身就不会开机自启；先开启自启再关闭即可"
    if state in ("disabled", "indirect", "generated"):
        return (), "当前已经不自启"
    return (["disable", "--", unit],), ""

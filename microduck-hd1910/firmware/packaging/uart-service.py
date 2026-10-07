#!/usr/bin/env python3
"""Persist the receive settings verified on this Zero3's ttyS2.

Invoked by systemd before/after robotd, with its own privileges. Never opens the
UART or sends motor commands. IRQ procfs entries need not exist while the UART
is closed. Apply affinity and FIFO after robotd opens/configures it, before any transactions.
"""
import argparse
import json
import os
from pathlib import Path
import re
import socket
import struct
import subprocess
import sys
import tempfile
import time
from release_identity import BUILD

PORT = "/dev/ttyS2"
TRIGGER = Path("/sys/class/tty/ttyS2/rx_trig_bytes")
STATE = Path("/var/lib/robot/feetech-ft5/r5/uart-state.json")
BOOT = Path("/proc/sys/kernel/random/boot_id")
IRQ_ROOT = Path("/proc/irq")


def cpu_set(text):
    cpus = set()
    if not text.strip():
        return cpus
    for part in text.strip().split(","):
        a, _, b = part.partition("-")
        cpus.update(range(int(a), int(b or a) + 1))
    return cpus


def identify():
    if Path("/sys/class/tty/ttyS2/device").resolve().name != "fe660000.serial":
        raise RuntimeError("不是已确认的 fe660000.serial/ttyS2，未修改串口设置")
    if 3 not in cpu_set(Path("/sys/devices/system/cpu/online").read_text()):
        raise RuntimeError("本机已验证的 CPU3 不在线")
    line = next((s for s in Path("/proc/tty/driver/serial").read_text().splitlines()
                 if s.startswith("2:")), "")
    found = re.search(r"\birq:(\d+)", line)
    if not found or "mmio:0xFE660000" not in line or not TRIGGER.exists():
        raise RuntimeError("UART 地址、实际 IRQ 或 RX FIFO 接口不符合本机记录")
    irq = int(found[1])
    return irq, line


def cpu_list(cpus):
    return ",".join(str(cpu) for cpu in sorted(cpus))


def read_affinity(irq, effective=False):
    """Return actual values; only an absent interface is optional."""
    stem = "effective_affinity" if effective else "smp_affinity"
    for name in (stem + "_list", stem):
        path = IRQ_ROOT / str(irq) / name
        try:
            value = path.read_text().strip()
        except FileNotFoundError:
            continue
        if name.endswith("_list"):
            cpus = cpu_set(value)
        else:
            mask = int(value.replace(",", ""), 16)
            if mask < 0:
                raise ValueError("无效的 IRQ CPU 掩码")
            cpus = {bit for bit in range(mask.bit_length()) if mask & (1 << bit)}
        return {"path": path, "cpus": cpus, "value": value}
    return None


def write_affinity(observed, cpus):
    if observed["path"].name.endswith("_list"):
        value = cpu_list(cpus)
    else:
        # CPU3 is mask 0x8, NOT the list value "3".
        mask = sum(1 << cpu for cpu in cpus)
        parts = []
        while mask:
            parts.append(f"{mask & 0xffffffff:08x}")
            mask >>= 32
        value = ",".join(reversed(parts))
    write(observed["path"], value)


def capture():
    irq, _ = identify()
    observed = read_affinity(irq)
    return {"boot_id": BOOT.read_text().strip(), "irq": irq,
            "affinity_before": cpu_list(observed["cpus"]) if observed else None,
            "affinity_observed_via": observed["path"].name if observed else None,
            "trigger_before": TRIGGER.read_text().strip()}


def sync_state_directory():
    fd = os.open(STATE.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def load_state():
    try:
        value=json.loads(STATE.read_text(encoding='utf-8'))
        if not isinstance(value,dict):raise ValueError('UART 临时记录必须是对象')
        return value
    except FileNotFoundError:return None


def atomic_state(value):
    STATE.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix=STATE.name + ".tmp-", dir=STATE.parent)
    temp = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, STATE)
        sync_state_directory()
    finally:
        temp.unlink(missing_ok=True)


def require_closed():
    check = subprocess.run(["fuser", PORT], capture_output=True, timeout=3)
    if check.returncode != 1:
        raise RuntimeError("先停止 robotd 并释放 ttyS2，再准备或恢复 UART 设置")


def write(path, value):
    path.write_text(str(value).strip() + "\n")


def prepare():
    require_closed()
    current=capture()
    saved=load_state()
    if saved is None or saved.get("boot_id")!=current["boot_id"] or saved.get("irq")!=current["irq"]:
        atomic_state(current)
        print("UART 临时记录缺失、损坏或已过期，已重新创建。",flush=True)
    else:
        print("UART 临时记录有效，沿用现有记录。",flush=True)
    print("等待 robotd 打开串口后设置 IRQ / RX FIFO，配置完成再开始采集。",flush=True)


def cached_bus(pid, method="robot.busStatus"):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(0.4)
        connection.connect("/run/robotd.sock")
        peer, _, _ = struct.unpack("3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        if peer != pid:
            raise RuntimeError("IPC 对端不是本次 systemd 启动的 robotd")
        connection.sendall((json.dumps({"jsonrpc":"2.0","id":1,"method":method})+"\n").encode())
        with connection.makefile("rb") as reader:
            raw = reader.readline(262145)
        if not raw.endswith(b"\n") or len(raw) > 262144:
            raise RuntimeError("robot.busStatus 回执缺失或过长")
        reply = json.loads(raw)
        if reply.get("id") != 1 or reply.get("error") or not isinstance(reply.get("result"), dict):
            raise RuntimeError("robot.busStatus 回执无效")
        return reply["result"]


def ready(bus, mode, builds=(BUILD,)):
    if bus.get("build") not in builds or bus.get("mode") != mode:
        return False
    if mode == "commissioning":
        return bus.get("phase") == "ready" and bus.get("torque_state") == "off"
    return (bus.get("native", {}).get("torque_state_confirmed") is False
            and not bus.get("policy_enabled") and not bus.get("homed")
            and bus.get("fresh_sample") is True)


def verify_settings(irq, affinity_requested):
    if TRIGGER.read_text().strip() != "1":
        raise RuntimeError("UART RX FIFO 1 设置被覆盖或未生效")
    observed = read_affinity(irq)
    effective = read_affinity(irq, effective=True)
    if affinity_requested:
        if observed is None or observed["cpus"] != {3}:
            raise RuntimeError("UART IRQ CPU3 设置被覆盖或接口消失")
        if effective is not None and effective["cpus"] != {3}:
            raise RuntimeError("UART IRQ CPU3 有效亲和性不符")
    return {"affinity": cpu_list(observed["cpus"]) if observed else None,
            "effective_affinity": cpu_list(effective["cpus"]) if effective else None,
            "affinity_status": ("verified" if effective else "configured_unverified")
                if affinity_requested else "unavailable"}


def apply(pid, mode):
    deadline=time.monotonic()+8
    last_error="等待机器人打开串口"
    while time.monotonic()<deadline:
        try:
            bus=cached_bus(pid)
            if bus.get('build') and bus['build'] != BUILD:
                raise ValueError(f"UART 助手期望 {BUILD}，实际服务 {bus['build']}；配套版本不一致")
            if bus.get("build")==BUILD and bus.get("mode")==mode and bus.get("phase")=="configuring_uart":
                break
            if bus.get("phase")=="configuration_error":
                raise RuntimeError(bus.get("error", "启动失败"))
            last_error=bus.get("error") or last_error
        except ValueError:
            raise
        except (OSError, RuntimeError) as exc:
            last_error=str(exc)
        time.sleep(.03)
    else:
        raise RuntimeError("UART 初始化未开始："+last_error)
    irq,_=identify()
    saved=load_state()
    if saved is None:
        saved=capture()
        atomic_state(saved)
    if saved.get("boot_id")!=BOOT.read_text().strip() or saved.get("irq")!=irq:
        raise RuntimeError("缺少本次启动的 UART 恢复记录")
    observed=read_affinity(irq)
    if observed is not None:
        if saved.get("affinity_before") is None:
            saved["affinity_before"]=cpu_list(observed["cpus"])
            saved["affinity_observed_via"]=observed["path"].name
            atomic_state(saved)
        write_affinity(observed,{3})
    if TRIGGER.read_text().strip()!="1":
        write(TRIGGER,"1")
    settings=verify_settings(irq,observed is not None)
    saved["last_applied"]={"pid":pid,"trigger":"1","mode":mode,**settings}
    atomic_state(saved)
    # Release the only UART owner only AFTER configuration has been verified.
    if cached_bus(pid,"robot.uartConfigured").get("accepted") is not True:
        raise RuntimeError("robotd 未确认 UART 初始化完成")
    from importlib.util import spec_from_file_location, module_from_spec
    spec=spec_from_file_location('rebuild_config',Path(__file__).with_name('rebuild-config.py'))
    recovery=module_from_spec(spec);spec.loader.exec_module(recovery)
    recovery.record()
    print("UART 配置完成，正式服务开始初始化与采集。",flush=True)


def restore(pid=None):
    if pid is None:
        require_closed()
    saved = load_state()
    if saved is None:
        return
    if saved.get("boot_id") != BOOT.read_text().strip():
        print("已跨重启，旧 IRQ 恢复记录不写入本次启动。")
        return
    irq, _ = identify()
    if saved.get("irq") != irq:
        raise RuntimeError("UART IRQ 与恢复记录不一致")
    if pid is not None:
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            try:
                bus = cached_bus(pid)
                if bus.get("mode") in ("commissioning", "motion") and ready(
                        bus, bus["mode"], tuple(f"590b986-feetech-ft5-control.{n}" for n in (2, 3, 4, 5, 6)) + ("590b986-feetech-ft6-control.7", BUILD,)):
                    break
            except (OSError, ValueError, RuntimeError):
                pass
            time.sleep(0.06)
        else:
            raise RuntimeError("原服务尚未确认停扭矩，未在线恢复 FIFO 设置")
    errors, notes = [], []
    try:
        if TRIGGER.read_text().strip() != saved["trigger_before"]:
            write(TRIGGER, saved["trigger_before"])
        if TRIGGER.read_text().strip() != saved["trigger_before"]:
            raise RuntimeError("RX FIFO 恢复读回不符")
    except (OSError, RuntimeError) as exc:
        errors.append(str(exc))
    try:
        before = saved.get("affinity_before")
        observed = read_affinity(irq)
        if before is None:
            notes.append("快照未记录 IRQ 亲和性，未写入")
        elif observed is None:
            notes.append("IRQ 亲和性接口当前未提供，未写回")
        else:
            write_affinity(observed, cpu_set(before))
            actual = read_affinity(irq)
            if actual is None or actual["cpus"] != cpu_set(before):
                raise RuntimeError("IRQ 亲和性恢复读回不符")
    except (OSError, ValueError, RuntimeError) as exc:
        errors.append(str(exc))
    if errors:
        raise RuntimeError("UART 设置恢复不完整：" + "; ".join(errors))
    print("UART RX FIFO 已恢复；" + ("；".join(notes) if notes else "IRQ 亲和性已恢复") + "。")


def snapshot():
    print(json.dumps(capture()))


def status():
    irq, line = identify()
    affinity = read_affinity(irq)
    effective = read_affinity(irq, effective=True)
    print(json.dumps({"irq": irq,
                      "affinity": cpu_list(affinity["cpus"]) if affinity else None,
                      "effective_affinity": cpu_list(effective["cpus"]) if effective else None,
                      "affinity_interface": affinity["path"].name if affinity else None,
                      "affinity_note": "接口可读取" if affinity else "接口未提供，未确认 CPU3 设置",
                      "rx_trig_bytes": TRIGGER.read_text().strip(), "serial": line,
                      "saved": load_state()},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "apply", "restore", "status", "snapshot"])
    parser.add_argument("--pid", type=int)
    parser.add_argument("--state", type=Path, help="restore only: saved UART snapshot")
    parser.add_argument("--mode", choices=["commissioning", "motion"], default="commissioning")
    args = parser.parse_args()
    if args.state is not None:
        if args.action != "restore":
            parser.error("--state 只用于恢复之前的快照")
        STATE = args.state
    if os.geteuid() != 0:
        parser.error("请使用 sudo；本工具只用于这台 Zero 的 UART 服务配置")
    if args.action == "apply" and (args.pid is None or args.pid <= 1):
        parser.error("apply 需要 systemd 本次启动的 MainPID")
    try:
        if args.action == "apply":
            apply(args.pid, args.mode)
        elif args.action == "restore":
            restore(args.pid)
        else:
            {"prepare": prepare, "status": status, "snapshot": snapshot}[args.action]()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        parser.exit(1, str(exc) + "\n")

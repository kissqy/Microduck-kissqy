#!/usr/bin/env python3
"""真机 / 演示自动验收。

默认 **只读**：扫描、认证、``system.info``、``net.status``、``net.scan``、
``system.logs``，再故意发一个未知方法确认错误通道。不会改动机器人的网络。

要真的加入网络（会改变机器人配置）必须显式加 ``--join``：

    ./acceptance.py --join Pollen --psk '...'        # 连上后再切回原来的网络
    ./acceptance.py --join CafeGuest                 # 开放网络

用法：

    ./acceptance.py --demo            # 假机器人，作为回归
    ./acceptance.py --pin 123456      # 真机，指定 PIN
    ./acceptance.py --name duck-5b21  # 多台机器人时按名字选
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from dataclasses import dataclass
from typing import Any

import ble
import profiles
import protocol
import session as sessions


@dataclass
class Result:
    name: str
    status: str  # PASS / FAIL / WARN / SKIP
    detail: str = ""


class Report:
    def __init__(self) -> None:
        self.items: list[Result] = []

    def add(self, name: str, status: str, detail: str = "") -> None:
        self.items.append(Result(name, status, detail))
        if status == "SKIP":
            return
        print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""), flush=True)

    @property
    def failed(self) -> int:
        return sum(1 for item in self.items if item.status == "FAIL")

    def print_summary(self) -> None:
        print()
        width = max((len(item.name) for item in self.items), default=10)
        print(f"{'检查项'.ljust(width)}  结果   说明")
        print("-" * (width + 34))
        for item in self.items:
            print(f"{item.name.ljust(width)}  {item.status:<5}  {item.detail}")
        print()
        passed = sum(1 for item in self.items if item.status == "PASS")
        print(f"通过 {passed} / {len(self.items)}，失败 {self.failed}")


def _pin(args: argparse.Namespace) -> str:
    return (args.pin or os.environ.get("DUCK_PIN") or protocol.DEFAULT_PIN).strip()


def _find_robot(items: list[ble.Found], wanted: str | None) -> ble.Found | None:
    robots = [item for item in items if item.is_robot]
    if not robots:
        return None
    if not wanted:
        return robots[0]
    needle = wanted.casefold()
    for item in robots:
        label = (item.adv.label or "").casefold()
        if needle == label or needle in label:
            return item
    return None


async def _read_only_checks(
    session: sessions.RobotSession, report: Report, advertisement: Any
) -> dict[str, Any]:
    info = await session.system_info()
    name = str(info.get("name", "?"))
    serial = str(info.get("serial") or "—")
    report.add("system.info", "PASS", f"{name} · 序列号 {serial}")

    status = await session.net_status()
    state = str(status.get("state"))
    if state == "connected":
        report.add(
            "net.status",
            "PASS",
            f"{status.get('ssid')} · {status.get('ip4')} · {status.get('signal')}%",
        )
        advertised = getattr(advertisement.adv, "ipv4", None) if advertisement else None
        current = status.get("ip4")
        if advertised and current and advertised != current:
            report.add(
                "广播 IPv4 与 net.status",
                "WARN",
                f"广播 {advertised}，实际 {current}（广播每 5 秒刷新，可能滞后）",
            )
        else:
            report.add("广播 IPv4 与 net.status", "PASS", advertised or "广播未带地址")
    else:
        report.add("net.status", "PASS", f"state={state}（当前没有联网）")

    networks = await session.net_scan()
    report.add("net.scan", "PASS", f"{len(networks)} 个网络")
    if networks:
        sample = networks[0]
        report.add(
            "net.scan 字段",
            "PASS" if {"ssid", "signal", "security", "saved"} <= set(sample) else "FAIL",
            f"首个：{sample.get('ssid')} / {sample.get('security')}",
        )

    logs = await session.logs("btd", lines=10)
    lines = logs.get("lines") or []
    report.add(
        "system.logs",
        "PASS" if lines else "WARN",
        f"btd {len(lines)} 行" + ("（已截断）" if logs.get("truncated") else ""),
    )

    try:
        await session.call("robot.move")
        report.add("未知方法应被拒绝", "FAIL", "机器人接受了 robot.move")
    except sessions.RobotError as exc:
        report.add("未知方法应被拒绝", "PASS", f"{exc.code}: {exc.message[:60]}")
    return status


async def _join_check(
    session: sessions.RobotSession,
    report: Report,
    ssid: str,
    psk: str | None,
    static: dict[str, Any] | None = None,
) -> None:
    networks = await session.net_scan()
    network = next((n for n in networks if str(n.get("ssid")) == ssid), None)
    if network is None:
        report.add("加入网络", "FAIL", f"扫描不到 {ssid}")
        return

    security = str(network.get("security", "open"))
    if security in ("wep", "enterprise"):
        report.add("加入网络", "FAIL", f"{ssid} 的加密方式不支持（{security}）")
        return
    if security != "open" and not psk:
        report.add("加入网络", "FAIL", f"{ssid} 需要密码，请加 --psk")
        return

    result = await session.net_connect(ssid, psk, static)
    if result.get("outcome") != "connected":
        report.add(
            "加入网络",
            "FAIL",
            f"{result.get('reason')}: {result.get('detail') or ''}".strip(),
        )
        return
    ip = result.get("ip4")
    report.add("加入网络", "PASS", f"{ssid} · {ip or '还没有 IP'}")

    await asyncio.sleep(1.0)
    status = await session.net_status()
    report.add(
        "加入后 net.status",
        "PASS"
        if status.get("state") == "connected" and status.get("ssid") == ssid
        else "FAIL",
        f"{status.get('state')} · {status.get('ssid')} · {status.get('ip4')}",
    )
    if static:
        # 固定地址是这次要验的东西：机器人报回来的必须是被钉住的那个，而不是租约。
        report.add(
            "固定 IP 生效",
            "PASS" if ip == static.get("address") else "FAIL",
            f"要求 {static.get('address')}，得到 {ip}",
        )
    elif ip:
        report.add("DHCP 拿到 IPv4", "PASS", str(ip))


async def _restore(
    session: sessions.RobotSession,
    report: Report,
    previous: dict[str, Any],
    *,
    psk: str | None = None,
    joined: str | None = None,
) -> None:
    if previous.get("state") != "connected" or not previous.get("ssid"):
        report.add("恢复原网络", "SKIP", "测试前没有连接网络")
        return
    ssid = str(previous["ssid"])
    # 切回原来那个网络，也只有它有密码时才行：`net.connect` 对加密网络要求带 PSK，
    # 机器人上存着的那份不会被"空密码"复用（App 里"记住密码"就是为了填上这一步）。
    if ssid != joined or not psk:
        report.add(
            "恢复原网络",
            "SKIP",
            f"没有 {ssid} 的密码；用 App 里记住的密码，或 robotctl net connect {ssid} --psk-stdin",
        )
        return
    result = await session.net_connect(ssid, psk)
    report.add(
        "恢复原网络",
        "PASS" if result.get("outcome") == "connected" else "FAIL",
        f"{ssid} · {result.get('reason') or result.get('ip4') or ''}",
    )


async def run_demo(args: argparse.Namespace) -> int:
    from fake import FakeRobot

    print("演示模式：进程内假机器人，不需要蓝牙\n")
    report = Report()
    robot = FakeRobot(mtu=20, log=lambda line: None)
    link = robot.link()
    try:
        robot_name = "Microduck-DEMO"
        report.add("扫描", "PASS", f"{robot_name}（模拟）")
        session = await sessions.RobotSession.open(link, _pin(args), log=lambda _: None)
        report.add("BLE 会话 + PIN 认证", "PASS", f"API v{session.api_version}")
        previous = await _read_only_checks(session, report, advertisement=None)
        if args.join:
            await _join_check(session, report, args.join, args.psk, args.static)
            await _restore(session, report, previous, psk=args.psk, joined=args.join)
        await session.close()
    finally:
        await robot.close()
    report.print_summary()
    return 1 if report.failed else 0


async def run_real(args: argparse.Namespace) -> int:
    from agent import BluezPairingAgent

    print(f"扫描 {args.scan_time:.0f} 秒…")
    try:
        items = await ble.scan(args.scan_time)
    except ble.BleError as exc:
        print(f"扫描失败：{exc}")
        return 2

    robots = [item for item in items if item.is_robot]
    print(f"找到 {len(robots)} 台机器人：")
    for item in robots:
        print(
            f"  · {item.adv.label}  {item.adv.address}  "
            f"IPv4 {item.adv.ipv4 or '—'}  {item.adv.rssi or '—'} dBm"
        )
    if not robots:
        print("\n没有找到机器人。检查：机器人是否开机、蓝牙是否开启、是否被手机/电脑占着。")
        return 2

    chosen = _find_robot(items, args.name)
    if chosen is None:
        print(f"\n没有匹配 --name {args.name!r} 的机器人。")
        return 2

    report = Report()
    report.add("扫描", "PASS", f"{chosen.adv.label} · {chosen.adv.address}")

    agent = BluezPairingAgent(log=lambda line: print(f"  · {line}"))
    session = None
    link = None
    previous: dict[str, Any] = {}
    try:
        await agent.start()
        print(f"\n连接 {chosen.adv.label}…")
        link, session = await ble.open_session(
            chosen.adv, _pin(args), log=lambda line: print(f"  {line}")
        )
        report.add("BLE 会话 + PIN 认证", "PASS", f"API v{session.api_version}")

        previous = await _read_only_checks(session, report, advertisement=chosen)

        if args.join:
            await _join_check(session, report, args.join, args.psk, args.static)
            await _restore(session, report, previous, psk=args.psk, joined=args.join)
    except (ble.BleError, sessions.RobotError, sessions.AuthError, sessions.LinkClosed) as exc:
        report.add("连接/认证", "FAIL", str(exc))
    finally:
        if session is not None:
            try:
                await session.close()
            except Exception:
                pass
        try:
            await agent.stop()
        except Exception:
            pass

    report.print_summary()
    if report.failed:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="acceptance",
        description="ducknet 自动验收：默认只读；--join 才会真的改网络。",
    )
    parser.add_argument("--demo", action="store_true", help="使用进程内假机器人")
    parser.add_argument("--name", help="按名称选择机器人（默认第一台）")
    parser.add_argument("--pin", help="机器人 PIN（默认 $DUCK_PIN 或 000000）")
    parser.add_argument(
        "--scan-time", type=float, default=8.0, help="扫描秒数（默认 8）"
    )
    parser.add_argument(
        "--join",
        metavar="SSID",
        help="真正加入这个网络（会改机器人配置；测试结束尝试切回原网络）",
    )
    parser.add_argument("--psk", help="--join 的密码；开放网络可省略")
    parser.add_argument(
        "--static-ip",
        metavar="ADDRESS/PREFIX",
        help="配合 --join：要求机器人用这个固定地址（例如 192.168.110.240/23）。"
        "会写进机器人的 NetworkManager 配置，所以地址要选你留得住的那个。",
    )
    parser.add_argument("--gateway", help="配合 --static-ip 的默认网关")
    parser.add_argument("--dns", help="配合 --static-ip 的解析器，逗号分隔")
    args = parser.parse_args(argv)

    args.static: dict[str, Any] | None = None
    if args.static_ip:
        if not args.join:
            parser.error("--static-ip 要和 --join 一起用：固定地址是随加入网络下发的")
        address, _, prefix = args.static_ip.partition("/")
        try:
            args.static = profiles.build_static(
                address, prefix or "24", args.gateway or "", args.dns or ""
            )
        except profiles.InvalidStaticIP as exc:
            parser.error(str(exc))

    started = time.time()
    if args.demo:
        code = asyncio.run(run_demo(args))
    else:
        code = asyncio.run(run_real(args))
    print(f"耗时 {time.time() - started:.1f} 秒")
    return code


if __name__ == "__main__":
    sys.exit(main())

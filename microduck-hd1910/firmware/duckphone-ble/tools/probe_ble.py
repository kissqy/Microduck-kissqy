#!/usr/bin/env python3
"""只读探针：扫到机器人，握手、认证，读一遍它能回答什么，再测 10 Hz phone 状态。

**不发送任何会动机器人的调用。** 它只做：扫描、读版本、PIN 认证、`robot.health`、
`system.info`、`net.status`、`system.services`、`update.status`、`robot.subscribe
{profile:"phone"}`，以及断开后的一次重连。

用法：

    python3 probe_ble.py                      # 扫 8 秒，只有一台就选它
    python3 probe_ble.py --name duck-3f9c
    python3 probe_ble.py --address AA:BB:CC:DD:EE:FF --pin 000000
    python3 probe_ble.py --json               # 机器可读

退出码：0 全部通过；1 有检查失败；2 参数/环境问题。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from duckble import DuckBle, RpcError, choose, scan  # noqa: E402

READ_ONLY_CALLS = [
    ("robot.health", {}),
    ("system.info", {}),
    ("system.services", {}),
    ("net.status", {}),
    ("update.status", {}),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Microduck BLE 只读探针")
    parser.add_argument("--address", help="机器人 BLE 地址")
    parser.add_argument("--name", help="机器人名字的一部分")
    parser.add_argument("--pin", default="", help="配对 PIN；给了才会认证")
    parser.add_argument("--scan-time", type=float, default=8.0)
    parser.add_argument("--state-seconds", type=float, default=3.0, help="10 Hz 状态采样时长")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args()


async def run(args: argparse.Namespace) -> int:
    report: dict[str, object] = {"checks": [], "fatal": None}

    def record(name: str, ok: bool, detail: str = "") -> None:
        report["checks"].append({"check": name, "ok": ok, "detail": detail})
        if not args.json:
            mark = "PASS" if ok else "FAIL"
            print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))

    if not args.json:
        print("扫描中…")
    robots = await scan(args.scan_time)
    if not args.json:
        for robot in robots:
            print("  " + robot.label())
    if not robots:
        record("scan", False, f"{args.scan_time:.0f} s 内没有扫到广播")
        report["fatal"] = "no-robot"
        return finish(report, args)

    robot = choose(robots, args.address, args.name)
    report["robot"] = {"address": robot.address, "name": robot.name, "ipv4": robot.ipv4}
    record("scan", True, robot.label())

    duck = DuckBle(robot.address, debug=args.debug)
    try:
        started = time.monotonic()
        await duck.connect()
        record("connect", True, f"{time.monotonic() - started:.2f} s")
        record("api_version", duck.api_version == 41,
               f"{duck.api_version}" + ("" if duck.api_version == 41 else "（旧固件；部署后应为 41）"))
        record("mtu", duck.mtu >= 64, f"{duck.mtu} B（控制一包发完需要 ≥64）")

        if args.pin:
            try:
                result = await duck.authenticate(args.pin)
                record("authenticate", True, f"attempts_remaining={result.get('attempts_remaining')}")
            except RpcError as error:
                record("authenticate", False, str(error))
                return finish(report, args)
        else:
            record("authenticate", True, "跳过（未给 --pin）")

        for method, params in READ_ONLY_CALLS:
            try:
                result = await duck.call(method, params)
                record(method, True, summarise(result))
            except RpcError as error:
                record(method, False, str(error))

        try:
            ack = await duck.subscribe(hz=10, profile="phone")
            record("robot.subscribe", bool(ack.get("accepted")), summarise(ack))
        except RpcError as error:
            hint = "（旧固件不认识 profile；部署 API 41 后再测）" if (duck.api_version or 0) < 41 else ""
            record("robot.subscribe", False, f"{error}{hint}")
            return finish(report, args)

        sizes: list[int] = []
        times: list[float] = []
        last = time.monotonic()
        deadline = last + args.state_seconds
        async for frame in duck.states():
            now = time.monotonic()
            sizes.append(len(json.dumps(frame, separators=(",", ":"))))
            times.append(now - last)
            last = now
            if now >= deadline:
                break

        rate = (len(times) / sum(times)) if times else 0.0
        interval_ok = bool(times) and abs(statistics.median(times) - 0.1) <= 0.04
        size_ok = bool(sizes) and max(sizes) <= 400
        record("phone state", bool(sizes) and interval_ok and size_ok,
               f"{len(sizes)} 帧 / {args.state_seconds:.1f} s ≈ {rate:.1f} Hz，"
               f"中位 {statistics.median(times) * 1000:.0f} ms，最大 {max(sizes, default=0)} B")
        report["phone_state"] = {
            "frames": len(sizes),
            "hz": round(rate, 1),
            "median_ms": round(statistics.median(times) * 1000) if times else None,
            "max_bytes": max(sizes, default=0),
            "sample": frame if sizes else None,
        }

        await duck.close()
        reconnected = DuckBle(robot.address, debug=args.debug)
        try:
            await reconnected.connect()
            if args.pin:
                await reconnected.authenticate(args.pin)
            record("reconnect", True, "断开后重新连接成功")
        except Exception as error:  # noqa: BLE001 — 探针要把任何失败都变成一行
            record("reconnect", False, str(error))
        finally:
            await reconnected.close()
    except Exception as error:  # noqa: BLE001
        record("session", False, str(error))
        report["fatal"] = str(error)
    finally:
        await duck.close()

    return finish(report, args)


def summarise(result: object) -> str:
    if isinstance(result, dict):
        for key in ("healthy", "state", "name", "version", "accepted", "ok"):
            if key in result:
                return f"{key}={result[key]}"
        return json.dumps(result, ensure_ascii=False)[:120]
    return str(result)[:120]


def finish(report: dict[str, object], args: argparse.Namespace) -> int:
    checks = report.get("checks", [])
    failures = [check for check in checks if not check["ok"]]  # type: ignore[index]
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"\n{len(checks) - len(failures)}/{len(checks)} 通过")
    return 0 if not failures else 1


def main() -> int:
    try:
        return asyncio.run(run(parse_args()))
    except KeyboardInterrupt:
        print("已中断", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

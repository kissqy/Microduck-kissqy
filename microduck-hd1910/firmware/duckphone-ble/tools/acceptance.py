#!/usr/bin/env python3
"""真机验收：按 `duckphone-ble-implementation.zh-CN.md` §8.2 的 A1–A10 跑一遍。

默认只做**不动机器人**的项目：扫描、连接、认证、phone 状态、网络读、日志、断链重连。
写入分三档，必须显式打开：

    --allow-writes          20 Hz 零速控制写、`robot.stop`、音量写（会改机器人音量，最后还原）
    --allow-service-action  停/启 `padd.service`
    --allow-motion          **不用**：凡是会让关节上力的动作由人工按验收表做，脚本不碰

用法：

    python3 acceptance.py --name duck-3f9c --pin 000000
    python3 acceptance.py --name duck-3f9c --pin 000000 --allow-writes
    python3 acceptance.py --name duck-3f9c --pin 000000 --allow-writes --allow-service-action --json

退出码：0 全部通过；1 有失败；2 参数/环境问题。
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Microduck 手机蓝牙版 · 真机验收")
    parser.add_argument("--address")
    parser.add_argument("--name")
    parser.add_argument("--pin", default="000000", help="默认 000000；改过就传新的")
    parser.add_argument("--scan-time", type=float, default=8.0)
    parser.add_argument("--allow-writes", action="store_true", help="允许零速控制写、stop、音量")
    parser.add_argument("--allow-service-action", action="store_true", help="允许停/启 padd")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args()


class Report:
    def __init__(self, as_json: bool):
        self.as_json = as_json
        self.checks: list[dict[str, object]] = []

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        self.checks.append({"check": name, "ok": ok, "detail": detail})
        if not self.as_json:
            print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
        return ok

    def skip(self, name: str, why: str) -> None:
        self.checks.append({"check": name, "ok": True, "skipped": True, "detail": why})
        if not self.as_json:
            print(f"[SKIP] {name} — {why}")

    def finish(self) -> int:
        failed = [c for c in self.checks if not c["ok"]]
        skipped = [c for c in self.checks if c.get("skipped")]
        if self.as_json:
            print(json.dumps({"checks": self.checks}, ensure_ascii=False, indent=2))
        else:
            passed = len(self.checks) - len(failed) - len(skipped)
            print(f"\n{passed} 通过 · {len(skipped)} 跳过 · {len(failed)} 失败")
        return 0 if not failed else 1


async def measure_states(duck: DuckBle, seconds: float = 3.0) -> dict[str, object]:
    sizes: list[int] = []
    intervals: list[float] = []
    last = time.monotonic()
    deadline = last + seconds
    async for frame in duck.states():
        now = time.monotonic()
        sizes.append(len(json.dumps(frame, separators=(",", ":"))))
        intervals.append(now - last)
        last = now
        if now >= deadline:
            break
    return {
        "frames": len(sizes),
        "hz": round(len(intervals) / sum(intervals), 1) if intervals else 0.0,
        "median_ms": round(statistics.median(intervals) * 1000) if intervals else None,
        "max_bytes": max(sizes, default=0),
    }


async def run(args: argparse.Namespace) -> int:
    report = Report(args.json)
    robots = await scan(args.scan_time)
    if not robots:
        report.check("A1 扫描", False, f"{args.scan_time:.0f} s 内没有扫到广播")
        return report.finish()
    robot = choose(robots, args.address, args.name)
    report.check("A1 扫描", True, robot.label())

    duck = DuckBle(robot.address, debug=args.debug)
    try:
        started = time.monotonic()
        await duck.connect()
        elapsed = time.monotonic() - started
        report.check("A1 连接", elapsed <= 10, f"{elapsed:.2f} s")
        report.check("A1 API 版本", duck.api_version == 41, f"{duck.api_version}（要求 41）")
        report.check("A1 MTU", duck.mtu >= 64, f"{duck.mtu} B")

        try:
            auth = await duck.authenticate(args.pin)
            report.check("A2 认证", True, f"attempts_remaining={auth.get('attempts_remaining')}")
        except RpcError as error:
            report.check("A2 认证", False, str(error))
            return report.finish()

        try:
            ack = await duck.subscribe(hz=10, profile="phone")
            report.check("A3 phone 订阅", bool(ack.get("accepted")), f"skills={ack.get('skills')}")
        except RpcError as error:
            report.check("A3 phone 订阅", False, str(error))
            return report.finish()

        state = await measure_states(duck)
        hz_ok = 7.0 <= float(state["hz"]) <= 12.0
        size_ok = 0 < int(state["max_bytes"]) <= 400
        report.check("A3 phone 状态", hz_ok and size_ok,
                     f"{state['frames']} 帧，{state['hz']} Hz，中位 {state['median_ms']} ms，"
                     f"最大 {state['max_bytes']} B")

        # ── A4 20 Hz 控制写：零速，所以不发运动 ─────────────────────────────
        if args.allow_writes:
            frames = 200
            started = time.monotonic()
            errors = 0
            for _ in range(frames):
                try:
                    await duck.notify("robot.move", {"vx": 0.0, "vy": 0.0, "vyaw": 0.0})
                except Exception:  # noqa: BLE001
                    errors += 1
                await asyncio.sleep(0.05)
            took = time.monotonic() - started
            report.check("A4 20 Hz 控制写", errors == 0,
                         f"{frames} 帧 / {took:.1f} s，失败 {errors}")
        else:
            report.skip("A4 20 Hz 控制写", "未给 --allow-writes")

        # ── A5 停下：零速，不卸力（卸力需人工） ────────────────────────────
        if args.allow_writes:
            try:
                result = await duck.call("robot.stop")
                report.check("A5 robot.stop", True, json.dumps(result, ensure_ascii=False))
            except RpcError as error:
                report.check("A5 robot.stop", False, str(error))
            report.skip("A5 robot.relax", "会瘫下，由人工按验收表做")
        else:
            report.skip("A5 停下", "未给 --allow-writes")

        # ── A6 音量：写 60，回读一致，再还原 ──────────────────────────────
        if args.allow_writes:
            try:
                before = await duck.call("robot.volume", {})
                result = await duck.call("robot.volume", {"percent": 60})
                ok = int(result.get("percent", -1)) == 60 and not result.get("muted")
                report.check("A6 音量写", ok,
                             f"{before.get('percent')}% → {result.get('percent')}%"
                             f" muted={result.get('muted')}")
                restored = await duck.call(
                    "robot.volume",
                    {"percent": int(before.get("percent") or 0),
                     "muted": bool(before.get("muted"))},
                )
                report.check("A6 音量还原", True,
                             f"{restored.get('percent')}% muted={restored.get('muted')}")
            except RpcError as error:
                report.check("A6 音量", False, str(error))
        else:
            report.skip("A6 音量", "未给 --allow-writes")

        # ── A7 停/启 padd ─────────────────────────────────────────────────
        if args.allow_service_action:
            try:
                stopped = await duck.call(
                    "system.serviceAction", {"unit": "padd", "action": "stop"})
                report.check("A7 停止 padd", bool(stopped.get("accepted")),
                             f"state={stopped.get('state')}")
                started_ok = await duck.call(
                    "system.serviceAction", {"unit": "padd", "action": "start"})
                report.check("A7 恢复 padd", bool(started_ok.get("accepted")),
                             f"state={started_ok.get('state')}")
            except RpcError as error:
                report.check("A7 停/启 padd", False, str(error))
        else:
            report.skip("A7 停/启 padd", "未给 --allow-service-action")

        # ── A8 网络 ───────────────────────────────────────────────────────
        try:
            status = await duck.call("net.status")
            report.check("A8 net.status", True,
                         f"state={status.get('state')} ssid={status.get('ssid')} ip4={status.get('ip4')}")
            networks = (await duck.call("net.scan") or {}).get("networks") or []
            report.check("A8 net.scan", isinstance(networks, list), f"{len(networks)} 个网络")
        except RpcError as error:
            report.check("A8 网络", False, str(error))

        # ── A9 日志 ───────────────────────────────────────────────────────
        try:
            logs = await duck.call("system.logs", {"unit": "robotd", "lines": 20, "boot": -1})
            text = json.dumps(logs, ensure_ascii=False)
            report.check("A9 system.logs", len(text) > 0, f"{len(text)} B")
        except RpcError as error:
            report.check("A9 system.logs", False, str(error))

        # ── A10 断链重连 ──────────────────────────────────────────────────
        await duck.close()
        report.check("A10 断开", True, "已主动断开")
        again = DuckBle(robot.address, debug=args.debug)
        try:
            started = time.monotonic()
            await again.connect()
            await again.authenticate(args.pin)
            await again.subscribe(hz=10, profile="phone")
            frame = await again.next_note(3.0)
            ok = bool(frame) and frame.get("method") == "robot.state"
            report.check("A10 重连", ok, f"{time.monotonic() - started:.2f} s 后重新收到状态")
        except Exception as error:  # noqa: BLE001
            report.check("A10 重连", False, str(error))
        finally:
            await again.close()
    finally:
        await duck.close()

    return report.finish()


def main() -> int:
    try:
        return asyncio.run(run(parse_args()))
    except KeyboardInterrupt:
        print("已中断", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

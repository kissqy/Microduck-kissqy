#!/usr/bin/env python3
"""Live IMU-only test for imu-to-dxl RevA.

Bus access uses ROBOTIS Dynamixel SDK. Decoding mirrors MicroDuck's official
duck-control/src/imu.rs format at ID 200, address 124, length 12.
"""

from __future__ import annotations

import argparse
import math
import struct
import sys
import time
from dataclasses import dataclass

DXL_ID = 200
DXL_BAUD = 1_000_000
READ_ADDRESS = 124
READ_LENGTH = 12
GYRO_RAD_PER_LSB = 0.0175 * math.pi / 180.0
SQRT_HALF = math.sqrt(0.5)
DEFAULT_MOUNT = (SQRT_HALF, 0.0, SQRT_HALF, 0.0)


def half(data: bytes) -> float:
    return struct.unpack("<e", data)[0]


def quat_mul(a: tuple[float, ...],
             b: tuple[float, ...]) -> tuple[float, float, float, float]:
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    )


def cross_terms(q: tuple[float, ...],
                v: tuple[float, ...]) -> tuple[tuple[float, ...],
                                                tuple[float, ...]]:
    _, x, y, z = q
    vx, vy, vz = v
    t = (
        2.0 * (y * vz - z * vy),
        2.0 * (z * vx - x * vz),
        2.0 * (x * vy - y * vx),
    )
    c = (
        y * t[2] - z * t[1],
        z * t[0] - x * t[2],
        x * t[1] - y * t[0],
    )
    return t, c


def rotate(q: tuple[float, ...],
           v: tuple[float, ...]) -> tuple[float, float, float]:
    t, c = cross_terms(q, v)
    return (
        v[0] + q[0] * t[0] + c[0],
        v[1] + q[0] * t[1] + c[1],
        v[2] + q[0] * t[2] + c[2],
    )


def rotate_inverse(q: tuple[float, ...],
                   v: tuple[float, ...]) -> tuple[float, float, float]:
    t, c = cross_terms(q, v)
    return (
        v[0] - q[0] * t[0] + c[0],
        v[1] - q[0] * t[1] + c[1],
        v[2] - q[0] * t[2] + c[2],
    )


def normalise3(v: tuple[float, ...]) -> tuple[float, float, float]:
    mag = math.sqrt(sum(x * x for x in v))
    if mag > 0.1:
        return tuple(x / mag for x in v)  # type: ignore[return-value]
    return (0.0, 0.0, -1.0)


def median3_each(history: list[tuple[float, float, float]],
                 now: tuple[float, float, float]
                 ) -> tuple[float, float, float]:
    return tuple(
        sorted((history[0][i], history[1][i], now[i]))[1]
        for i in range(3)
    )  # type: ignore[return-value]


@dataclass
class ImuData:
    gyro_rad_s: tuple[float, float, float]
    gravity: tuple[float, float, float]
    quat: tuple[float, float, float, float]
    live_quaternion: bool
    ready_samples: int


class OfficialDecoder:
    """Python equivalent of the official MicroDuck SflpDecoder."""

    def __init__(self) -> None:
        self.mount = DEFAULT_MOUNT
        self.last_quat = (1.0, 0.0, 0.0, 0.0)
        self.quat_samples = 0
        self.gyro_history = [(0.0, 0.0, 0.0)] * 2
        self.gravity_history = [(0.0, 0.0, -1.0)] * 2

    def decode(self, block: bytes) -> ImuData:
        if len(block) != READ_LENGTH:
            raise ValueError(f"expected {READ_LENGTH} bytes, got {len(block)}")

        raw_gyro = struct.unpack("<hhh", block[:6])
        gyro_sensor = tuple(x * GYRO_RAD_PER_LSB for x in raw_gyro)
        gyro = rotate(self.mount, gyro_sensor)

        packed = struct.unpack("<HHH", block[6:12])
        live = packed != (0, 0, 0)
        if live:
            x, y, z = (half(block[6:8]), half(block[8:10]),
                       half(block[10:12]))
            norm_sq = x * x + y * y + z * z
            if (math.isfinite(x) and math.isfinite(y) and math.isfinite(z)
                    and norm_sq <= 1.02):
                w = math.sqrt(max(0.0, 1.0 - norm_sq))
                mount_inv = (
                    self.mount[0], -self.mount[1],
                    -self.mount[2], -self.mount[3],
                )
                q = quat_mul((w, x, y, z), mount_inv)
                norm = math.sqrt(sum(c * c for c in q))
                if norm > 0.5:
                    self.last_quat = tuple(c / norm for c in q)
                    self.quat_samples = min(self.quat_samples + 1, 0xFFFFFFFF)

        gravity_now = normalise3(
            rotate_inverse(self.last_quat, (0.0, 0.0, -1.0))
        )
        output = ImuData(
            gyro_rad_s=median3_each(self.gyro_history, gyro),
            gravity=median3_each(self.gravity_history, gravity_now),
            quat=self.last_quat,
            live_quaternion=live,
            ready_samples=min(self.quat_samples, 25),
        )
        self.gyro_history = [self.gyro_history[1], gyro]
        self.gravity_history = [self.gravity_history[1], gravity_now]
        return output


def choose_port(requested: str | None) -> str:
    if requested:
        return requested

    try:
        from serial.tools import list_ports
    except ImportError as exc:
        raise RuntimeError("Dynamixel SDK/pyserial 未安装") from exc

    found = [
        item for item in list_ports.comports()
        if item.device.startswith("/dev/cu.")
        and "Bluetooth-Incoming-Port" not in item.device
    ]
    if not found:
        raise RuntimeError("没有找到串口；确认 U2D2 已插入 Mac")
    if len(found) == 1:
        return found[0].device

    preferred = [
        item for item in found
        if any(key in (item.description or "").lower()
               for key in ("u2d2", "ftdi", "usb serial", "usb-serial"))
    ]
    if len(preferred) == 1:
        return preferred[0].device

    print("检测到多个串口：")
    for index, item in enumerate(found, 1):
        print(f"  {index}. {item.device}  {item.description or ''}")
    choice = int(input("输入 U2D2 对应序号："))
    if choice < 1 or choice > len(found):
        raise RuntimeError("串口序号无效")
    return found[choice - 1].device


def self_test() -> None:
    qx = struct.pack("<e", 0.125)
    block = struct.pack("<hhh", -1000, 2000, -3000) + qx + b"\0\0\0\0"
    decoder = OfficialDecoder()
    output = None
    for _ in range(25):
        output = decoder.decode(block)
    assert output is not None
    gyro_dps = tuple(x * 180.0 / math.pi for x in output.gyro_rad_s)
    assert all(abs(a - b) < 1e-9
               for a, b in zip(gyro_dps, (-52.5, 35.0, 17.5)))
    assert output.ready_samples == 25
    gravity_norm = math.sqrt(sum(x * x for x in output.gravity))
    assert abs(gravity_norm - 1.0) < 1e-9
    print("PASS: official block decode, mount transform, quaternion and gravity")


def run(port_name: str, rate_hz: float) -> None:
    try:
        from dynamixel_sdk import COMM_SUCCESS, PacketHandler, PortHandler
    except ImportError as exc:
        raise RuntimeError(
            "缺少 ROBOTIS 官方 Dynamixel SDK。先运行：\n"
            "python3 -m pip install dynamixel-sdk"
        ) from exc

    port = PortHandler(port_name)
    packet = PacketHandler(2.0)
    if not port.openPort():
        raise RuntimeError(f"打不开串口 {port_name}")
    if not port.setBaudRate(DXL_BAUD):
        port.closePort()
        raise RuntimeError("无法设置 1,000,000 baud")

    try:
        model, result, error = packet.ping(port, DXL_ID)
        if result != COMM_SUCCESS:
            raise RuntimeError("ID 200 Ping 失败：" +
                               packet.getTxRxResult(result))
        if error:
            raise RuntimeError("ID 200 返回错误：" +
                               packet.getRxPacketError(error))

        print(f"已连接 {port_name} | ID={DXL_ID} | model=0x{model:04X}")
        print("正在读取官方数据块……按 Ctrl-C 退出")
        time.sleep(0.5)
        print("\033[2J", end="")

        decoder = OfficialDecoder()
        previous: bytes | None = None
        stale_run = 0
        failures = 0
        attempts = 0
        last_error = "无"
        interval = 1.0 / rate_hz
        while True:
            started = time.monotonic()
            attempts += 1
            data, result, error = packet.readTxRx(
                port, DXL_ID, READ_ADDRESS, READ_LENGTH
            )
            if result != COMM_SUCCESS or error:
                failures += 1
                message = (packet.getTxRxResult(result)
                           if result != COMM_SUCCESS
                           else packet.getRxPacketError(error))
                last_error = time.strftime("%H:%M:%S") + "  " + message
                print(f"\033[H通信失败 #{failures}: {message}\033[K")
            else:
                raw = bytes(data)
                stale_run = stale_run + 1 if raw == previous else 0
                previous = raw
                imu = decoder.decode(raw)
                gyro_dps = tuple(
                    x * 180.0 / math.pi for x in imu.gyro_rad_s
                )
                if imu.ready_samples >= 25:
                    state = "OK（SFLP 实时输出）"
                elif imu.live_quaternion:
                    state = f"预热 {imu.ready_samples}/25"
                else:
                    state = "等待 SFLP 四元数"

                print("\033[H", end="")
                print("IMU_TO_DXL RevA 实时测试｜ROBOTIS SDK｜Ctrl-C 退出\033[K")
                print(f"状态: {state:<24}  连续重复: {stale_run:<5} "
                      f"通信失败: {failures}/{attempts}\033[K")
                print(f"最后错误: {last_error}\033[K")
                print("陀螺仪 trunk [°/s]  "
                      f"X {gyro_dps[0]:+8.2f}  "
                      f"Y {gyro_dps[1]:+8.2f}  "
                      f"Z {gyro_dps[2]:+8.2f}\033[K")
                print("重力向量 trunk       "
                      f"X {imu.gravity[0]:+7.3f}  "
                      f"Y {imu.gravity[1]:+7.3f}  "
                      f"Z {imu.gravity[2]:+7.3f}\033[K")
                print("四元数 [w x y z]     " +
                      " ".join(f"{x:+7.4f}" for x in imu.quat) + "\033[K")
                print("原始 12 字节         " + raw.hex(" ") + "\033[K")
                sys.stdout.flush()

            remaining = interval - (time.monotonic() - started)
            if remaining > 0:
                time.sleep(remaining)
    finally:
        port.closePort()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read ID200 IMU block through U2D2 on macOS"
    )
    parser.add_argument("--port", help="例如 /dev/cu.usbserial-FTxxxx")
    parser.add_argument("--hz", type=float, default=50.0,
                        help="刷新率，默认 50 Hz")
    parser.add_argument("--self-test", action="store_true",
                        help="仅测试解码算法，不连接硬件")
    args = parser.parse_args()

    try:
        if args.self_test:
            self_test()
            return 0
        if args.hz <= 0 or args.hz > 100:
            raise RuntimeError("--hz 必须在 0 到 100 之间")
        run(choose_port(args.port), args.hz)
        return 0
    except KeyboardInterrupt:
        print("\n已停止")
        return 0
    except (RuntimeError, ValueError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

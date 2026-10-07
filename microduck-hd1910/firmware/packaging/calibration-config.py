#!/usr/bin/env python3
"""Validate stored per-robot calibration and opt into the normal service loop."""
from __future__ import annotations

import argparse
import math
import os
from pathlib import Path
import tempfile
import tomllib

from configure import dumps, atomic_write

NAMES = (
    'left_hip_yaw', 'left_hip_roll', 'left_hip_pitch', 'left_knee', 'left_ankle',
    'neck_pitch', 'head_pitch', 'head_yaw', 'head_roll', 'mouth',
    'right_hip_yaw', 'right_hip_roll', 'right_hip_pitch', 'right_knee', 'right_ankle',
)
HOME = tuple(math.radians(v) for v in (0, -5, -24, 0, 24, 20, 20, 0, 0, 0,
                                              0, 5, 24, 0, -24))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def integer(value: object, lo: int, hi: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and lo <= value <= hi


def validate(data: dict) -> None:
    require(data.get('imu_mount_verified') is True, 'IMU 安装方向尚未确认，请在正式服务中执行 bus verify-imu --confirmed。')
    quat = data.get('imu_mount_quat')
    require(isinstance(quat, list) and len(quat) == 4 and all(number(x) for x in quat), 'IMU 四元数必须包含四个有限数值。')
    require(abs(sum(x*x for x in quat) - 1.0) <= 1e-6, 'IMU 安装四元数未归一化。')
    joints = data.get('joints')
    require(isinstance(joints, list) and len(joints) == 15, '需要 15 个关节的实际标定。')
    ids = set()
    for name, home, row in zip(NAMES, HOME, joints, strict=True):
        require(isinstance(row, dict) and row.get('name') == name, f'关节顺序错误：应为 {name}。')
        raw_id = row.get('id')
        require(integer(raw_id, 0, 253) and raw_id != 200 and raw_id not in ids, f'{name}：ID 无效或重复。')
        ids.add(raw_id)
        zero = row.get('zero_raw')
        require(integer(zero, 0, 4095), f'{name}：零位必须在 0..4095。')
        direction = row.get('direction')
        require(type(direction) is int and direction in (-1, 1), f'{name}：方向必须为 -1 或 1。')
        require(row.get('calibrated') is True, f'{name}：尚未记录实际标定。')
        lower, upper = row.get('min_rad'), row.get('max_rad')
        require(number(lower) and number(upper) and lower < upper, f'{name}：缺少有效机械限位。')
        require(lower <= home <= upper, f'{name}：限位不包含模型 Home 角 {home} rad。')
        for angle in (lower, upper):
            raw = zero + angle * direction * 4096.0 / math.tau
            raw = math.copysign(math.floor(abs(raw) + .5), raw)
            require(0 <= raw <= 4095, f'{name}：限位跨越了单圈编码器边界。')
    if data.get('units_verified', False):
        for field in ('current_ma_per_count',):
            require(number(data.get(field)) and data[field] > 0, f'{field}：已确认的物理单位系数必须大于零。')


RETIRED_FIELDS = ('command_acceleration_raw', 'command_speed_raw', 'speed_rad_s_per_count')


def save(path: Path, data: dict) -> None:
    text='# Actual per-robot calibration. Motion still requires explicit init.\n'+dumps(data)
    atomic_write(path,text)
    atomic_write(path.with_name(path.stem+'.saved'+path.suffix),text)


def migrate(path: Path) -> list[str]:
    data = tomllib.loads(path.read_text())
    removed = [key for key in RETIRED_FIELDS if key in data]
    if removed:
        for key in removed: del data[key]
        save(path, data)
    return removed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check', 'enable', 'migrate', 'copy'])
    parser.add_argument('path', type=Path)
    parser.add_argument('--output',type=Path)
    args = parser.parse_args()
    try:
        if args.action == 'copy':
            require(args.output is not None,'copy 需要 --output')
            raw=args.path.read_bytes();atomic_write(args.output,raw);atomic_write(args.output.with_name(args.output.stem+".saved"+args.output.suffix),raw);return
        if args.action == 'migrate':
            removed = migrate(args.path)
            print('清理旧运动参数：' + (', '.join(removed) if removed else '无需清理'))
            return
        data = tomllib.loads(args.path.read_text())
        validate(data)
        if args.action == 'enable':
            data['motion_enabled'] = True
            save(args.path, data)
        print('15 关节标定和 IMU 安装配置完整；实际运行仍由 robotd 后端检查。')
    except (OSError, ValueError, TypeError) as exc:
        parser.exit(1, f'无法处理标定配置：{exc}\n')


if __name__ == '__main__':
    main()

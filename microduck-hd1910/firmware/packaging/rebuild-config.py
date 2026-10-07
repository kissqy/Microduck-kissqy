#!/usr/bin/env python3
"""Preserve installation settings and record successfully loaded configuration."""
import argparse
import copy
from pathlib import Path
import tomllib
from configure import atomic_write, dumps

BASE=Path(__file__).resolve().parent
CONFIG=Path('/etc/robot/feetech-ft5/robotd.toml')
CALIBRATION=CONFIG.with_name('hd1910-calibration.toml')
STATE=Path('/var/lib/robot/feetech-ft5/r5/uart-state.json')

def saved_path(path):return path.with_name(path.stem+'.saved'+path.suffix)

def read_config(path, kind):
    """Check recovery inputs, without changing valid per-robot values."""
    try:
        data=tomllib.loads(path.read_text(encoding='utf-8'))
        if kind=='params':
            if not data or not isinstance(data.get('policy'),dict):return None
            for key in ('bus','control','safety'):
                if key in data and not isinstance(data[key],dict):return None
            if not isinstance(data['policy'].get('walk'),str):return None
            data['policy'].pop('r17_inference_scale',None)
        else:
            joints=data.get('joints')
            if not isinstance(joints,list) or len(joints)!=15:return None
            names=set();ids=set()
            for joint in joints:
                if not isinstance(joint,dict):return None
                name=joint.get('name');ident=joint.get('id');zero=joint.get('zero_raw');direction=joint.get('direction')
                if not isinstance(name,str) or name in names:return None
                if type(ident) is not int or not 0<=ident<254 or ident==200 or ident in ids:return None
                if type(zero) is not int or not 0<=zero<=4095 or type(direction) is not int or direction not in (-1,1):return None
                names.add(name);ids.add(ident)
        return data
    except (OSError,ValueError,UnicodeError):return None

def source_data(path, kind, base):
    fallback=base/('robotd-profile.toml' if kind=='params' else 'hd1910-calibration.template.toml')
    original=(Path('/etc/robot/robotd.toml'),) if path==CONFIG else ()
    for candidate in (path,saved_path(path),*original,fallback):
        data=read_config(candidate,kind)
        if data is not None:
            if kind=="calibration" and candidate==fallback:
                data["motion_enabled"]=False
                for joint in data["joints"]:joint["calibrated"]=False
            if candidate!=path:print(f'按完整来源重建：{path} ← {candidate}',flush=True)
            return data
    raise ValueError(f'没有可用于重建的完整配置：{path}')

def prepare(directory, params=CONFIG, calibration=CALIBRATION, base=BASE):
    # Stage before service mutation; malformed old files must not abort replacement.
    values=(source_data(params,'params',base),prepare_calibration(calibration,base))
    for name,data in zip(('robotd.toml','hd1910-calibration.toml'),values):
        atomic_write(directory/name,dumps(data))

def prepare_calibration(path,base=BASE):
    """Installation only: restore known assembled robot values where no saved ones exist.

    Later restarts/failure recovery never reapply the model snapshot. Calibrated
    local joints (and their limits) always win, then saved local data, then the
    explicitly supplied robot snapshot. A fresh all-unmarked template also has
    a placeholder IMU orientation, even if its default was just confirmed.
    """
    current=source_data(path,'calibration',base)
    saved=read_config(saved_path(path),'calibration') or {}
    seed=read_config(base/'hd1910-calibration.robot.toml','calibration')
    if seed is None:raise ValueError('缺少随模型核对的本机装配标定')
    data=copy.deepcopy(current)
    has_local=any(r.get('calibrated') is True for r in current['joints'])
    saved_rows={r['name']:r for r in saved.get('joints',[])}
    seed_rows={r['name']:r for r in seed['joints']}
    restored=[]
    for i,row in enumerate(data['joints']):
        if row.get('calibrated') is True:continue
        candidate=saved_rows.get(row['name'],{})
        if candidate.get('calibrated') is not True:candidate=seed_rows[row['name']]
        if candidate['id']!=row['id']:raise ValueError('本机标定 ID 与随包装配记录不符：'+row['name'])
        data['joints'][i]=copy.deepcopy(candidate);restored.append(row['name'])
    imu_source=None
    if not has_local or data.get('imu_mount_verified') is not True:
        imu_source=saved if saved.get('imu_mount_verified') is True and any(r.get('calibrated') is True for r in saved.get('joints',[])) else seed
        for name in ('imu_mount_quat','imu_mount_verified'):data[name]=copy.deepcopy(imu_source[name])
    if restored or imu_source is not None:
        data['motion_enabled']=False
        print('安装恢复装配标定：补齐 '+str(len(restored))+' 个关节；头部 ID 33 零位 '+str(data['joints'][8]['zero_raw'])+'；IMU '+('已恢复' if imu_source is not None else '保留本机设置'),flush=True)
    return data

def record(params=CONFIG,calibration=CALIBRATION):
    # Called only after robotd accepted UART setup, or after a calibration save.
    values=[read_config(params,'params'),read_config(calibration,'calibration')]
    if any(data is None for data in values):raise ValueError('未保存不完整的配置副本')
    for path,data in zip((params,calibration),values):atomic_write(saved_path(path),dumps(data))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    actions=parser.add_mutually_exclusive_group(required=True)
    actions.add_argument('--record',action='store_true')
    actions.add_argument('--prepare',type=Path)
    args=parser.parse_args()
    if args.prepare:prepare(args.prepare)
    else:record()

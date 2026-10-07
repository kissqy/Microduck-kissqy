#!/usr/bin/env python3
"""Derive the FT5 service params without editing the existing official configuration."""
from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import re
import sys
import tempfile
from pathlib import Path
import tomllib
from management_profile import PROFILE, SLOTS

def atomic_write(path: Path, text: str | bytes, mode=None) -> None:
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    previous=path.stat() if path.exists() else None
    fd,name=tempfile.mkstemp(prefix='.'+path.name+'-',dir=path.parent)
    try:
        if previous:os.fchown(fd,previous.st_uid,previous.st_gid)
        os.fchmod(fd,mode if mode is not None else previous.st_mode & 0o777 if previous else 0o644)
        with os.fdopen(fd,'wb') as stream:
            stream.write(text.encode() if isinstance(text,str) else text);stream.flush();os.fsync(stream.fileno())
        os.replace(name,path)
        directory_fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(directory_fd)
        finally:os.close(directory_fd)
    finally:
        if os.path.exists(name):os.unlink(name)



def key(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def atom(value: object) -> str:
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value):
            return 'nan'
        if math.isinf(value):
            return 'inf' if value > 0 else '-inf'
        return repr(value)
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, list):
        return '[' + ', '.join(atom(v) for v in value) + ']'
    if isinstance(value, dict):
        return '{ ' + ', '.join(f'{key(k)} = {atom(v)}' for k, v in value.items()) + ' }'
    raise TypeError(f'unsupported TOML value: {type(value).__name__}')


def dumps(data: dict) -> str:
    lines: list[str] = []

    def table(values: dict, path: tuple[str, ...] = ()) -> None:
        if path:
            lines.append('[' + '.'.join(key(k) for k in path) + ']')
        for name, value in values.items():
            if not isinstance(value, dict):
                lines.append(f'{key(name)} = {atom(value)}')
        lines.append('')
        for name, value in values.items():
            if isinstance(value, dict):
                table(value, (*path, name))

    table(data)
    return '\n'.join(lines).strip() + '\n'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--previous-overrides', type=Path, help='previously installed defaults; migrate an unchanged default once')
    parser.add_argument('--replace-models', action='store_true', help='use all supplied model slots for this replacement')
    parser.add_argument('--overrides', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:data=tomllib.loads(args.source.read_text()) if args.source else {}
    except (OSError,ValueError,UnicodeError):
        data={}
        print('读取服务参数失败，按随包配置重建。',file=sys.stderr)
    changes = tomllib.loads(args.overrides.read_text())
    previous_defaults = {}
    previous_profile = {}
    previous_managed = {}
    if args.previous_overrides:
        try:
            previous_profile = tomllib.loads(args.previous_overrides.read_text())
            previous_defaults = previous_profile.get('policy', {})
        except (OSError, ValueError, UnicodeError):pass
        if not isinstance(previous_defaults, dict):previous_defaults = {}
        try:previous_managed=json.loads(args.previous_overrides.with_name('management-profile.json').read_text()).get('defaults',{}).get('policy',{})
        except (OSError,ValueError,UnicodeError):pass
    # Relinquish keys removed from the installed management descriptor. Omitted
    # fields resolve in robotd itself; no R17 replacement values or repair flags.
    retired_managed=set(previous_managed) - PROFILE['defaults']['policy'].keys()
    old_policy=data.get('policy',{})
    replacement=PROFILE.get('requested_model_replacement',{})
    replacement_slot=replacement.get('slot')
    replacement_path=changes.get('policy',{}).get(replacement_slot)
    replace_requested_walk=(replacement_slot=='walk'
        and isinstance(replacement_path,str)
        and '/models/'+str(replacement.get('id'))+'/' in replacement_path
        and previous_defaults.get('walk')!=replacement_path)
    recovery_request=PROFILE.get('requested_skill_replacement',{})
    requested_recovery=next((s for s in changes.get('policy',{}).get('skill',[]) if s.get('name')==recovery_request.get('name')),None)
    previous_recovery=next((s for s in previous_defaults.get('skill',[]) if s.get('name')==recovery_request.get('name')),None)
    replace_requested_recovery=bool(requested_recovery and '/models/'+str(recovery_request.get('id'))+'/' in requested_recovery.get('path','') and (previous_recovery or {}).get('path')!=requested_recovery['path'])
    preserve_custom=(not args.replace_models and isinstance(old_policy,dict) and old_policy.get('custom_only') is True)
    for table_name, values in changes.items():
        if not isinstance(values, dict):
            data[table_name] = values
            continue
        if table_name == 'policy':
            old=data.get('policy',{})
            selected=values.copy()
            if preserve_custom:selected.update(old)
            if preserve_custom:
                # Add newly shipped named skills without replacing the operator's
                # existing skills or reapplying an installed skill's defaults.
                previous_names={s.get('name') for s in previous_defaults.get('skill',[])}
                saved=list(old.get('skill',[]))
                saved_names={s.get('name') for s in saved}
                added=[s for s in values.get('skill',[]) if s.get('name') not in previous_names|saved_names]
                if added:selected['skill']=saved+added
            if not args.replace_models and isinstance(old,dict):
                # Preserve native settings without taking ownership of each
                # parameter. Model reset remains a separate explicit operation.
                selected.update({name:value for name,value in old.items()
                                 if name not in (*SLOTS,'skill')})
            # Recovery is independent of the saved gait scale. Update only
            # these scales, preserving skill paths, timing and pad bindings.
            if replace_requested_recovery and not any(s.get('name')==requested_recovery['name'] for s in selected.get('skill',[])):
                selected['skill']=[*selected.get('skill',[]),requested_recovery]
            if 'standing_action_scale' in values:
                selected['standing_action_scale']=values['standing_action_scale']
            recovery=next((s for s in values.get('skill',[]) if s.get('name')=='stand_test'),None)
            if recovery:
                for skill in selected.get('skill',[]):
                    if skill.get('name')=='stand_test':
                        skill['params']={**skill.get('params',{}),'action_scale':recovery['params']['action_scale']}
                        if replace_requested_recovery:skill['path']=requested_recovery['path']
            # The console now controls the official action_scale directly.
            # Move an unchanged installed default to this release's default.
            # Once the new profile is installed, later operator choices survive
            # upgrades, including selecting the former 0.9 default again.
            if isinstance(old,dict):
                for name in ('action_scale',):
                    value=old.get(name)
                    if type(value) in (int,float) and math.isfinite(value) and value in tuple(round(n/100,2) for n in range(10,101)):
                        previous_default=previous_defaults.get(name)
                        if not replace_requested_walk and value == previous_default and values.get(name) != previous_default:
                            selected[name]=values[name]
                            print(f'沿用的动作系数默认值已更新：{value:g} → {selected[name]:g}。')
                        else:selected[name]=value
            if replace_requested_walk:
                # This release explicitly replaces Walk only. Keep the saved
                # official action scale and all other action bindings.
                selected['walk']=replacement_path
                print('已替换唯一 Walk 为 9600 轮联合模型；全程使用基础缩放 0.9、头滤波 0.5、腿滤波 0.7，全局参数及其他动作沿用本机设置。')
            for name in retired_managed:selected.pop(name,None)
            selected.pop('r17_inference_scale',None)
            for name in ('walk_action_scale','hold_action_scale','action_scales'):
                selected.pop(name,None)
            selected['custom_only']=True
            data[table_name] = selected
            continue
        table_values = data.setdefault(table_name, {})
        if not isinstance(table_values, dict):
            raise ValueError(f'{table_name} must be a TOML table')
        if preserve_custom and table_name not in ('bus','control'):
            data[table_name]={**values,**table_values}
            if table_name=='pad':
                # A newly bound formerly empty button is part of the requested
                # release. Preserve any non-empty operator binding.
                for name,value in values.items():
                    if value and not table_values.get(name) and not previous_profile.get('pad',{}).get(name):
                        data[table_name][name]=value
        else:table_values.update(values)
    if replace_requested_recovery:
        data.setdefault('pad',{})[recovery_request['button']]=recovery_request['name']
        print('已替换 LB 为起身老师 11000 轮；起身基础动作系数 1.0，其他动作和本机标定保留。')
    # Explicit retirement must not leave configuration pointing at deleted files.
    retired=set(PROFILE.get('retired_model_ids',[]))
    def retired_path(path):
        return isinstance(path,str) and Path(path).parent.name in retired
    policy=data.setdefault('policy',{})
    for slot in SLOTS:
        if retired_path(policy.get(slot)):
            policy[slot]=changes.get('policy',{}).get(slot,'none')
    supplied_skills={s['name']:s for s in changes.get('policy',{}).get('skill',[])}
    removed=set();skills=[]
    for skill in policy.get('skill',[]):
        if retired_path(skill.get('path')):
            replacement=supplied_skills.get(skill['name'])
            if not replacement:
                removed.add(skill['name']);continue
            skill={**skill,'path':replacement['path']}
        skills.append(skill)
    if 'skill' in policy:policy['skill']=skills
    for button,name in data.get('pad',{}).items():
        if name in removed:data['pad'][button]=''
    result = dumps(data)
    if tomllib.loads(result) != data:
        raise ValueError('TOML serialization changed the parameter values')
    source_name = str(args.source) if args.source else 'robotd built-in defaults'
    atomic_write(args.output,'# Derived from: ' + source_name + '\n' + result)


if __name__ == '__main__':
    main()

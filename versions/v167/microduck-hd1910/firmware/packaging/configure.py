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
    encoded=text.encode() if isinstance(text,str) else text
    previous=path.stat() if path.exists() else None
    if previous and path.read_bytes()==encoded:return
    if previous and path.suffix in ('.toml','.json','.conf') and not any(x in path.stem for x in ('.saved','.previous')):
        # A backup of a systemd .conf must not itself be another active .conf.
        atomic_write(path.with_name(path.name+'.previous'),path.read_bytes(),mode=previous.st_mode & 0o777)
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
    source_pad=dict(data.get('pad',{})) if isinstance(data.get('pad'),dict) else {}
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
    # Replacing the shipped action is a one-time request, measured against the
    # previous bundle, so a later operator binding survives reinstalling it.
    requested_actions={}
    retired_ids=set(PROFILE.get('retired_model_ids',[]))
    for request in PROFILE.get('requested_action_replacements',[]):
        slot=request.get('slot')
        path=changes.get('policy',{}).get(slot)
        saved_paths=[old_policy.get(slot)] if isinstance(old_policy,dict) else []
        if slot=='roulade' and isinstance(old_policy,dict):
            saved_paths.extend(s.get('path') for s in old_policy.get('skill',[]) if s.get('name')=='roulade')
        # Files can finish installing before the atomic params commit. Retired
        # saved paths prove that interrupted migration still needs its scale.
        pending_retirement=any(isinstance(p,str) and Path(p).parent.name in retired_ids for p in saved_paths)
        if (slot in ('roulade','ground_pick','kick_left','kick_right') and isinstance(path,str)
            and Path(path).parent.name==request.get('id')
            and (previous_defaults.get(slot)!=path or pending_retirement)):
            requested_actions[slot]=path
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
                print('已替换唯一 Walk 为 9600 轮联合模型；基础缩放与头腿滤波读取该模型执行配置，全局参数及其他动作沿用本机设置。')
            for slot,path in requested_actions.items():
                selected[slot]=path
                if slot=='ground_pick':
                    selected['ground_pick_action_scale']=values['ground_pick_action_scale']
                else:
                    supplied=next(s for s in values['skill'] if s['name']==slot)
                    skill=next((s for s in selected.get('skill',[]) if s.get('name')==slot),None)
                    if skill is None:
                        skill={**supplied,'params':dict(supplied.get('params',{}))}
                        selected['skill']=[*selected.get('skill',[]),skill]
                    # The slot is authoritative in robotd; keep any explicit
                    # named-skill path consistent with the same replacement.
                    if 'path' in skill:skill['path']=path
                    skill['params']={**skill.get('params',{}),'action_scale':supplied['params']['action_scale']}
                    if slot in ('kick_left','kick_right'):
                        skill.update({key:value for key,value in supplied.items() if key!='params'})
                print(f'已更新随包动作 {slot}；基础缩放 1，按原合同无目标滤波。')
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
    # Explicit retirement must not leave configuration pointing at deleted files.
    retired=retired_ids
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
            # A built-in named skill may inherit its model from the slot and
            # omit path entirely (roulade does). Never retain a deleted path.
            path=replacement.get('path',changes.get('policy',{}).get(skill['name']))
            if not path or path=='none':
                removed.add(skill['name']);continue
            skill={**skill,'path':path}
        skills.append(skill)
    if 'skill' in policy:policy['skill']=skills
    for button,name in data.get('pad',{}).items():
        if name in removed:data['pad'][button]=''
    # The joint Walk policy owns recovery; retire only the former standalone
    # teacher name and its default pad bindings, preserving operator mappings.
    if PROFILE.get('retire_standalone_recovery'):
        policy['stand']='none'
        policy['skill']=[skill for skill in policy.get('skill',[]) if skill.get('name')!='stand_test']
        old_pad=source_pad
        pad=data.setdefault('pad',{})
        if old_pad.get('lb')=='stand_test':pad['lb']='kick_left'
        elif 'lb' in old_pad and old_pad['lb'] not in removed:pad['lb']=old_pad['lb']
        if not old_pad.get('rb'):pad['rb']='kick_right'
        elif old_pad['rb'] not in removed:pad['rb']=old_pad['rb']
    result = dumps(data)
    if tomllib.loads(result) != data:
        raise ValueError('TOML serialization changed the parameter values')
    source_name = str(args.source) if args.source else 'robotd built-in defaults'
    atomic_write(args.output,'# Derived from: ' + source_name + '\n' + result)


if __name__ == '__main__':
    main()

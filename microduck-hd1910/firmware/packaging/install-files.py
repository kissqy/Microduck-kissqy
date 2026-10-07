#!/usr/bin/env python3
"""Stage the complete bundle, then replace files without truncating live inodes."""
import hashlib
import json
from pathlib import Path
import os
import re
import shutil
import sys
import tempfile

RETIRED={'model_cleanup.py','upgrade.py','upgrade.sh','toml_config.py',
         'robotd-ft5-overrides.toml','R17-FIX1.zh-CN.md','R17-FIX2.zh-CN.md',
         'prepare-models.py','release_check.py'}

def owned_files(installed):
    owned=set()
    try:
        previous=json.loads((installed/'install-files.json').read_text(encoding='utf-8'))
        if isinstance(previous,list):owned.update(p for p in previous if isinstance(p,str))
    except (OSError,ValueError,UnicodeError):pass
    try:
        for line in (installed/'SHA256SUMS').read_text(encoding='utf-8').splitlines():
            digest,separator,name=line.partition('  ')
            if separator and len(digest)==64 and all(c in '0123456789abcdef' for c in digest):owned.add(name)
    except (OSError,UnicodeError):pass
    return owned

def contract_refresh(bundle, installed):
    """Restore unreadable shipped contracts instead of preserving a broken install."""
    refresh=set()
    for directory in (bundle/'models').glob('*'):
        old=installed/'models'/directory.name/'deployment-contract.json'
        if not directory.is_dir() or not old.is_file():continue
        try:
            data=json.loads(old.read_text(encoding='utf-8'))
            if not isinstance(data,dict):refresh.add(directory.name)
        except (OSError,ValueError,UnicodeError):refresh.add(directory.name)
    # Same ONNX weights may also ship a newer, explicitly requested contract.
    try:
        request=json.loads((bundle/'management-profile.json').read_text())['requested_model_replacement']
        ident=request['id'];revision=request.get('export_contract_revision',0)
        old=json.loads((installed/'models'/ident/'deployment-contract.json').read_text())
        if revision>old.get('export_contract_revision',0):refresh.add(ident)
    except (OSError,ValueError,KeyError,TypeError,AttributeError):pass
    return refresh

def execution_refresh(bundle, installed):
    """Apply the explicitly requested model execution profile once per release profile.

    A previously imported copy of the same weights keeps all original training
    data. Only this independently hashed deployment file is added/replaced. The
    installed management descriptor is the last payload marker, so an interrupted
    first installation retries the file before marking the request applied.
    """
    try:
        request=json.loads((bundle/'management-profile.json').read_text()).get('requested_model_replacement',{})
    except (OSError,ValueError,AttributeError):return set()
    expected=request.get('execution_profile_sha256')
    if expected is None:return set()
    ident=request.get('id')
    if (request.get('slot')!='walk' or not isinstance(ident,str)
        or not re.fullmatch('[a-f0-9]{32}',ident)
        or not isinstance(expected,str) or not re.fullmatch('[a-f0-9]{64}',expected)):
        raise ValueError('随包模型执行配置的绑定信息无效')
    name=f'models/{ident}/deployment-execution.json'
    source=bundle/name
    if source.is_symlink() or not source.is_file() or not source.resolve().is_relative_to(bundle.resolve()):
        raise ValueError('随包模型执行配置不存在或路径无效')
    if hashlib.sha256(source.read_bytes()).hexdigest()!=expected:
        raise ValueError('随包模型执行配置的 SHA256 不匹配')
    try:
        previous=json.loads((installed/'management-profile.json').read_text()).get('requested_model_replacement',{})
    except (OSError,ValueError,AttributeError):previous={}
    if previous.get('id')==ident and previous.get('execution_profile_sha256')==expected:return set()
    return {name}

def cleanup(bundle, installed, replace_models=False, previous_owned=None):
    current=set(json.loads((bundle/'install-files.json').read_text(encoding='utf-8')))
    current.update({'install-files.json','SHA256SUMS'})
    owned=owned_files(installed) if previous_owned is None else previous_owned
    retired=RETIRED|{p.name for p in installed.glob('CLEANUP-v*.zh-CN.md')}|{p.name for p in installed.glob('R16-*.md')}
    root=installed.resolve()
    for name in sorted((owned|retired)-current):
        rel=Path(name)
        if rel.is_absolute() or '..' in rel.parts or not rel.parts or rel.parts[0]=='models':continue
        path=installed/rel
        if path.resolve().is_relative_to(root) and (path.is_file() or path.is_symlink()):
            path.unlink();print(f'清理旧配套文件：{rel}',flush=True)
    # Ordinary upgrade removes only the exact models the user has retired.
    profile=json.loads((bundle/'management-profile.json').read_text()) if (bundle/'management-profile.json').is_file() else {}
    for ident in profile.get('retired_model_ids',[]):
        if not isinstance(ident,str) or not re.fullmatch('[a-f0-9]{32}',ident):continue
        path=installed/'models'/ident
        if path.is_symlink() or path.is_file():path.unlink()
        elif path.is_dir():shutil.rmtree(path)
        else:continue
        print(f'清理已弃用训练模型：{ident}',flush=True)
    if not replace_models:return
    # User model deletion belongs only to an explicitly requested reset.
    keep={Path(name).parts[1] for name in current if len(Path(name).parts)>2 and Path(name).parts[0]=='models'}
    for path in (installed/'models').glob('*'):
        if path.name in keep:continue
        if path.is_symlink() or path.is_file():path.unlink()
        elif path.is_dir() and path.resolve().is_relative_to(root):shutil.rmtree(path)
        print(f'清理旧训练模型：{path.name}',flush=True)

def install(bundle, installed, replace_models=False):
    bundle=bundle.resolve();installed=installed.resolve()
    installed.mkdir(parents=True,exist_ok=True)
    names=json.loads((bundle/'install-files.json').read_text(encoding='utf-8'))
    if not isinstance(names,list) or any(not isinstance(name,str) for name in names):
        raise ValueError('安装文件清单无效')
    names=sorted(set(names)|{'install-files.json','SHA256SUMS'})
    previous_owned=owned_files(installed)
    executions=execution_refresh(bundle,installed)
    if not executions.issubset(names):raise ValueError('安装清单缺少请求的模型执行配置')
    preserved={p.name for p in (installed/'models').glob('*') if p.is_dir() and (p/'deployment-contract.json').is_file()} if not replace_models else set()
    refreshed=contract_refresh(bundle,installed)&preserved
    preserved-=refreshed
    # Copy the complete release once. Existing user models do not need another
    # copy merely to be discarded; executable entries still change by rename.
    with tempfile.TemporaryDirectory(prefix='.r17-stage-',dir=installed) as tmp:
        stage=Path(tmp)
        for name in names:
            rel=Path(name)
            if rel.is_absolute() or '..' in rel.parts or not rel.parts:
                raise ValueError('安装文件路径无效：'+name)
            if len(rel.parts)>2 and rel.parts[0]=='models' and rel.parts[1] in preserved and name not in executions:continue
            source=bundle/rel;target=installed/rel
            if source.is_symlink() or not source.is_file() or not source.resolve().is_relative_to(bundle):
                raise ValueError('安装源文件无效：'+name)
            if any(parent.is_symlink() for parent in (target,*target.parents) if parent.is_relative_to(installed)):
                raise ValueError('安装目标含符号链接：'+name)
            prepared=stage/rel;prepared.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,prepared)
        # Keep ownership metadata last so an interrupted install retains the
        # previous inventory for cleanup on the next attempt.
        payload=[name for name in names if name not in {'install-files.json','SHA256SUMS'}]
        # Write contract revisions after their model files, and the management
        # descriptor after the requested execution profile it records.
        payload.sort(key=lambda name:(name=='management-profile.json',Path(name).name=='deployment-contract.json' and len(Path(name).parts)>2 and Path(name).parts[1] in refreshed))
        for name in payload:
            rel=Path(name)
            if len(rel.parts)>2 and rel.parts[0]=='models' and rel.parts[1] in preserved and name not in executions:continue
            target=installed/name;target.parent.mkdir(parents=True,exist_ok=True)
            os.replace(stage/name,target)
        cleanup(bundle,installed,replace_models=replace_models,previous_owned=previous_owned)
        for name in ('SHA256SUMS','install-files.json'):
            os.replace(stage/name,installed/name)
    print('服务文件已完成逐文件原子替换；'+('模型已按明确请求重置。' if replace_models else '已保留导入模型。'),flush=True)
    if refreshed:print('已恢复随包模型的损坏合同或更新修正版合同：'+', '.join(sorted(refreshed)),flush=True)
    if executions:print('已应用联合模型全程统一的缩放与滤波配置；原模型权重与训练数据保留。',flush=True)

if __name__=='__main__':install(Path(sys.argv[1]),Path(sys.argv[2]),replace_models='--replace-models' in sys.argv[3:])

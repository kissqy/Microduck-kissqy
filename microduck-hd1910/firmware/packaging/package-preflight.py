#!/usr/bin/env python3
"""Verify the package and execute every retained model before stopping the old service."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tomllib
from model_packages import runtime_environment, verify_directory
from release_identity import BUILD

def preflight(bundle):
    bundle=Path(bundle).resolve()
    for row in (bundle/'SHA256SUMS').read_text().splitlines():
        digest,sep,name=row.partition('  ')
        path=(bundle/name).resolve()
        if not sep or not path.is_relative_to(bundle) or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise ValueError('服务包校验失败：'+name)
    env=runtime_environment()
    env['ORT_DYLIB_PATH']=str(bundle/'onnxruntime/libonnxruntime.so.1.28.0')
    metadata=json.loads((bundle/'BUILD.json').read_text())
    if metadata['build'] != BUILD:
        raise ValueError('UART/安装助手与服务包版本不一致；原服务尚未停止')
    result=subprocess.run([str(bundle/'robotd'),'deployment-info'],env=env,capture_output=True,text=True,timeout=10)
    if result.returncode or json.loads(result.stdout).get('build') != BUILD:
        raise ValueError('实际 robotd 与 UART/安装助手版本不一致；原服务尚未停止')
    for name in ('robotd','padd','robotctl','sounds'):
        result=subprocess.run([str(bundle/name),'--version'],env=env,capture_output=True,text=True,timeout=10)
        if result.returncode:raise ValueError('新版程序兼容性预检查失败；原服务尚未停止：'+name+' '+(result.stderr or result.stdout)[-1000:])
    for entry in metadata['models'].values():
        ident=entry['id']
        model=bundle/'models'/ident;verify_directory(model)
        result=subprocess.run([str(bundle/'robotd'),'validate-policy',str(model/'policy.onnx')],env=env,capture_output=True,text=True,timeout=45)
        if result.returncode:raise ValueError('新版模型或 ONNX Runtime 预检查失败；原服务尚未停止：'+(result.stderr or result.stdout)[-1500:])
    walk_id=metadata['models']['walk']['id']
    contract=json.loads((bundle/'models'/walk_id/'deployment-contract.json').read_text())
    snapshot=tomllib.loads((bundle/'hd1910-calibration.robot.toml').read_text())
    if snapshot!=contract['hardware_calibration']['data']:raise ValueError('随包装配标定与指定模型记录不一致；原服务尚未停止')
    print(f"服务包、{len(metadata['models'])} 个自训模型、新版推理运行库及装配标定来源已通过预检查。",flush=True)

if __name__=='__main__':
    try:preflight(sys.argv[1])
    except Exception as exc:print(str(exc),file=sys.stderr);sys.exit(1)

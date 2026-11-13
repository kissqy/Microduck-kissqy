#!/usr/bin/env python3
"""Exercise the actual release robotd under QEMU without robot hardware."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--binary', type=Path, default=ROOT/'packaging/robotd')
parser.add_argument('--qemu', type=Path, default=os.environ.get('QEMU_AARCH64'))
parser.add_argument('--runtime-prefix', type=Path, default=os.environ.get('ARM64_RUNTIME_PREFIX'))
parser.add_argument('--ort-library', type=Path, default=ROOT/'packaging/onnxruntime/libonnxruntime.so.1.28.0')
args = parser.parse_args()
if not args.qemu or not args.runtime_prefix:
    parser.error('Set QEMU_AARCH64 and ARM64_RUNTIME_PREFIX, or provide the matching options.')
args.binary = args.binary.resolve()
args.qemu = args.qemu.resolve()
args.runtime_prefix = args.runtime_prefix.resolve()
args.ort_library = args.ort_library.resolve()
prefix = [str(args.qemu), '-L', str(args.runtime_prefix), '-E', 'ORT_DYLIB_PATH='+str(args.ort_library), str(args.binary)]
env = {**os.environ, 'TOKIO_WORKER_THREADS':'2'}
def run(command):
    start = time.monotonic()
    result = subprocess.run(prefix+command, env=env, capture_output=True, text=True, timeout=60)
    return {'exit_code':result.returncode, 'stdout':result.stdout, 'stderr':result.stderr,
            'elapsed_seconds':round(time.monotonic()-start, 3)}
info = run(['deployment-info'])
assert info['exit_code'] == 0, info
deployment = json.loads(info['stdout'])
assert deployment['build'] == '1fa8438-feetech-ft6-control.43', deployment
profile = json.loads((ROOT/'packaging/management-profile.json').read_text())
models = [(m['slot'], ROOT/'packaging/models'/m['id']/'policy.onnx') for m in profile['builtin_models']]
models += [('roller_'+name, ROOT/'packaging/roller'/name/'policy.onnx') for name in ('swizzle','crouch','spin','standup')]
results = []
for name, path in models:
    result = {'model':name, 'sha256':hashlib.sha256(path.read_bytes()).hexdigest(), **run(['validate-policy',str(path)])}
    results.append(result)
    print(name, result['exit_code'], result['stdout'].strip(), flush=True)
record = {'hardware_tested':False, 'emulator':'QEMU ARM64', 'build':deployment['build'],
          'robotd_sha256':hashlib.sha256(args.binary.read_bytes()).hexdigest(),
          'deployment_info':deployment, 'results':results}
out = ROOT/'verification/v167/arm64-models.json'
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
assert len(results) == 10
assert all(r['exit_code'] == 0 and json.loads(r['stdout']) == {'actions':14,'input':'obs','observations':61,'valid':True} for r in results)

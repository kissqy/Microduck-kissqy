#!/usr/bin/env python3
"""Run release tests; isolate robotd cases because deployment HOME is a process OnceLock."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

parser=argparse.ArgumentParser()
parser.add_argument('--release-scope',action='store_true',help='Control/protocol/padd unit tests and the V167 roller tests; retain historical diagnostics separately')
options=parser.parse_args()
ROOT = Path(__file__).resolve().parents[1]
record_name='release-tests' if options.release_scope else 'rust-tests'
OUT = ROOT / 'verification/v167'
OUT.mkdir(parents=True, exist_ok=True)
env = {**os.environ, 'CARGO_INCREMENTAL': '0'}
if not env.get('ORT_DYLIB_PATH'):
    raise SystemExit('Set ORT_DYLIB_PATH to the host ONNX Runtime library before testing')
command = ['cargo', '--config', 'profile.dev.package.pet-detect.codegen-units=1',
           '--config', 'profile.dev.package.robotd.codegen-units=1', 'test', '--locked', '--no-run', '--message-format=json',
           '-p', 'duck-control', '-p', 'duck-ipc-proto', '-p', 'robotd', '-p', 'padd']
start = time.monotonic()
built = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
log = [built.stderr]
artifacts = []
for line in built.stdout.splitlines():
    try:
        row = json.loads(line)
    except ValueError:
        continue
    if row.get('reason') == 'compiler-artifact' and row.get('executable') and row['profile']['test']:
        artifacts.append(row)
    elif row.get('reason') == 'compiler-message':
        log.append(row['message'].get('rendered', ''))
if built.returncode:
    (OUT / (record_name+'.log')).write_text('\n'.join(log))
    print(built.stderr)
    sys.exit(built.returncode)
results = []
for artifact in artifacts:
    binary = artifact['executable']
    name = artifact['target']['name']
    if options.release_scope and name not in ('duck_control','duck_ipc_proto','padd','robotd'):
        continue
    isolate = name == 'robotd'
    if isolate:
        listed = subprocess.check_output([binary, '--list'], cwd=ROOT, env=env, text=True)
        cases = [line[:-6] for line in listed.splitlines() if line.endswith(': test')]
        if options.release_scope:
            cases=[case for case in cases if case.startswith('roller::tests::')]
    else:
        cases = [None]
    for case in cases:
        args = [binary, '--test-threads=1']
        if case:
            args += ['--exact', case]
        run = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
        output = run.stdout + run.stderr
        log.append('COMMAND: ' + ' '.join(args) + '\n' + output)
        counts = re.findall(r'test result: (?:ok|FAILED)\. (\d+) passed; (\d+) failed; (\d+) ignored;', output)
        passed, failed, ignored = map(int, counts[-1]) if counts else (0, 1, 0)
        result = dict(target=name, case=case, exit_code=run.returncode,
                      passed=passed, failed=failed, ignored=ignored)
        results.append(result)
        if run.returncode:
            print('FAILED:', name, case or 'suite', flush=True)
        if len(results) % 40 == 0:
            print('completed test processes:', len(results), flush=True)
record = dict(scope=['duck-control', 'duck-ipc-proto', 'robotd', 'padd'],
              selected_scope=('duck-control unit; duck-ipc-proto unit; padd unit; robotd roller::tests' if options.release_scope else 'all unit/integration artifacts of four crates'),
              robotd_process_isolation=True, hardware_tested=False,
              passed=sum(r['passed'] for r in results),
              failed=sum(r['failed'] for r in results),
              ignored=sum(r['ignored'] for r in results),
              elapsed_seconds=round(time.monotonic()-start, 2), results=results)
(OUT / (record_name+'.log')).write_text('\n'.join(log))
(OUT / (record_name+'.json')).write_text(json.dumps(record, indent=2)+'\n')
print(json.dumps({k:v for k,v in record.items() if k!='results'}), flush=True)
sys.exit(1 if record['failed'] or any(r['exit_code'] for r in results) else 0)

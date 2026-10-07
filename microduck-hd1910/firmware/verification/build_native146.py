"""Build the frozen R17 ARM64 release and record the actual inputs and outputs."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import subprocess

B = Path(__file__).resolve().parent
SOURCE = B / 'source/Microduck-Source-R17-v1.0.146'
TARGET = Path('/tmp/r17-native-target')
HOST = Path('/tmp/r17-debian-build-deps/host')
ARM = Path('/tmp/r17-debian-build-deps/arm64')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources():
    return {str(p.relative_to(SOURCE)): digest(p) for p in sorted(SOURCE.rglob('*'))
            if p.is_file() and ('verification' not in p.relative_to(SOURCE).parts)
            and (p.suffix == '.rs' or p.name in {'Cargo.toml', 'Cargo.lock'})}


env = os.environ.copy()
env.update(
    PATH='/tmp/r17-rust/toolchains/1.99.0-x86_64-unknown-linux-gnu/bin:/tmp/r17-native-tools/bin:/tmp/r17-native-tools/ziglang:' + env['PATH'],
    CARGO_HOME='/tmp/r17-cargo', RUSTUP_HOME='/tmp/r17-rust',
    CARGO_TARGET_DIR=str(TARGET),
    ORT_DYLIB_PATH='/tmp/r17-native-tools/onnxruntime/capi/libonnxruntime.so.1.28.0',
    LD_LIBRARY_PATH=str(HOST / 'usr/lib/x86_64-linux-gnu'),
    LIBRARY_PATH=str(HOST / 'usr/lib/x86_64-linux-gnu'),
    PKG_CONFIG_ALLOW_CROSS='1', PKG_CONFIG_SYSROOT_DIR=str(ARM),
    PKG_CONFIG_LIBDIR=str(ARM / 'usr/lib/aarch64-linux-gnu/pkgconfig'),
)
command = ['cargo', 'zigbuild', '-p', 'robotd', '-p', 'robotctl', '-p', 'padd',
           '--release', '--target', 'aarch64-unknown-linux-gnu.2.31', '--locked']
record = dict(command=command, source=str(SOURCE),
              started_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
              target='aarch64-unknown-linux-gnu.2.31', robot_hardware_access=False,
              source_files_sha256=sources(),
              build_environment={k: env[k] for k in ['CARGO_HOME', 'RUSTUP_HOME', 'CARGO_TARGET_DIR',
                  'ORT_DYLIB_PATH', 'LD_LIBRARY_PATH', 'LIBRARY_PATH', 'PKG_CONFIG_ALLOW_CROSS',
                  'PKG_CONFIG_SYSROOT_DIR', 'PKG_CONFIG_LIBDIR']},
              dependency_provenance_sha256=digest(B / 'native-dependencies146.json'))
record['tool_versions'] = {}
for name, args in [('rustc', ['rustc', '--version']), ('cargo', ['cargo', '--version']),
                   ('cargo-zigbuild', ['cargo-zigbuild', '--version']), ('zig', ['zig', 'version']),
                   ('pkg-config', ['pkg-config', '--version'])]:
    record['tool_versions'][name] = subprocess.check_output(args, env=env, text=True).strip()
metadata = B / 'native-build-environment146.json'
metadata.write_text(json.dumps(record, indent=2) + '\n')
with (B / 'native-build146.log').open('w') as log:
    result = subprocess.run(command, cwd=SOURCE, env=env, stdout=log, stderr=subprocess.STDOUT)
record['exit_code'] = result.returncode
record['finished_at_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
record['source_files_unchanged'] = sources() == record['source_files_sha256']
if result.returncode == 0:
    record['binary_sha256'] = {name: digest(TARGET / 'aarch64-unknown-linux-gnu/release' / name)
                               for name in ['robotd', 'robotctl', 'padd']}
metadata.write_text(json.dumps(record, indent=2) + '\n')
assert record['source_files_unchanged'], 'Source changed during the release build'
if result.returncode:
    raise SystemExit(result.returncode)
print(json.dumps({k: record[k] for k in ['exit_code', 'tool_versions', 'source_files_unchanged',
                                        'binary_sha256', 'finished_at_utc']}, indent=2))

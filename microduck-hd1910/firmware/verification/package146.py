"""Build the v146 delivery from v145 payload bytes and current verification logs.

No robot, systemd service, uinput device, or external publication is operated here.
Run after native/frontend/input verification and the final ARM64 cross-build.
"""
from pathlib import Path
import contextlib
import datetime
import hashlib
import importlib.util
import io
import json
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import zipfile

B = Path(__file__).resolve().parent
VERSION = '1.0.146'
BUILD = '1fa8438-feetech-ft6-control.29'
S = B / f'source/Microduck-Source-R17-v{VERSION}'
OLD = B.parent / 'work-r17-145/source/Microduck-Source-R17-v1.0.145'
OLD_STAGE = B.parent / 'work-r17-145/stage/Microduck-Robotd-FT6-R17'
STAGE = B / 'stage/Microduck-Robotd-FT6-R17'
OUT = B.parent / f'output/R17-v{VERSION}'
NATIVE = Path('/tmp/r17-native-target/aarch64-unknown-linux-gnu/release')
RETIRED_WALK = '9e3ff8bde021be28a728c02dbd8e7aaf'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def records(root, exclude=()):
    return [dict(path=str(p.relative_to(root)), bytes=p.stat().st_size, sha256=digest(p))
            for p in sorted(root.rglob('*')) if p.is_file()
            and '__pycache__' not in p.parts and str(p.relative_to(root)) not in exclude]


def same_tree(a, b):
    ar, br = records(a), records(b)
    assert ar == br, (str(a), str(b))
    return len(ar)


def elf_record(path):
    header = subprocess.check_output(['readelf', '-h', str(path)], text=True)
    dynamic = subprocess.check_output(['readelf', '-d', str(path)], text=True)
    versions = subprocess.check_output(['readelf', '--version-info', str(path)], text=True)
    assert 'AArch64' in header, path
    glibc = sorted(set(re.findall(r'GLIBC_(\d+\.\d+)', versions)),
                   key=lambda v: tuple(map(int, v.split('.'))))
    assert glibc and max(tuple(map(int, v.split('.'))) for v in glibc) <= (2, 31)
    return dict(sha256=digest(path), machine='AArch64',
                needed=re.findall(r'Shared library: \[(.*?)\]', dynamic),
                glibc_versions=glibc, bytes=path.stat().st_size)


RUST_RESULT = re.compile(
    r'test result: ok\. (\d+) passed; (\d+) failed; (\d+) ignored; '
    r'(\d+) measured; (\d+) filtered out;')


def native_summary(log):
    assert 'test result: FAILED.' not in log and 'error: test failed' not in log
    starts = list(re.finditer(r'Running unittests [^\n]*[/\\]([a-z0-9_]+)-[0-9a-f]+\)', log))
    suites = {}
    for i, start in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(log)
        results = list(RUST_RESULT.finditer(log[start.end():end]))
        assert results, start.group(1)
        passed, failed, ignored, measured, filtered = map(int, results[-1].groups())
        assert passed and not failed and not measured and not filtered
        suites[start.group(1)] = dict(passed=passed, failed=failed, ignored=ignored)
    assert 'robotd' in suites
    return suites


def python_summary(log):
    counts = re.findall(r'^Ran (\d+) tests? in ', log, re.M)
    result = re.search(r'^OK(?: \(skipped=(\d+)\))?\s*\Z', log, re.M)
    assert counts and result, 'Python unittest run did not finish successfully'
    total = int(counts[-1]); skipped = int(result.group(1) or 0)
    assert total > 0
    return dict(run=total, passed=total - skipped, skipped=skipped)


assert S.is_dir() and OLD.is_dir() and OLD_STAGE.is_dir()
suites = native_summary((B / 'native-tests146.log').read_text())
python_result = python_summary((B / 'python-tests146.log').read_text())
build_log = (B / 'native-build146.log').read_text()
assert 'Finished `release`' in build_log and 'error:' not in build_log
build_evidence = json.loads((B / 'native-build-environment146.json').read_text())
assert build_evidence['exit_code'] == 0
assert all(digest(S / name) == expected for name, expected in build_evidence['source_files_sha256'].items())
assert all(digest(NATIVE / name) == expected for name, expected in build_evidence['binary_sha256'].items())
evidence = json.loads((B / 'focused-verification146.json').read_text())
assert evidence['all_passed'] is True
tests = dict(python=python_result['passed'], python_run=python_result['run'],
             python_skipped=python_result['skipped'], native_suites=suites, focused=evidence,
             robotd_rebuilt=True, robotctl_rebuilt=True, padd_rebuilt=True,
             reused_binary_payload_from='1.0.145', hardware_tested=False,
             windows_hardware_tested=False, full_system_integration_verified=False,
             integration_scope='Real ONNX control/formula tests with fake hardware, execution profile tests, import/configuration and frontend/input regressions. No physical Zero, systemd/uinput or GameSir activation.')
log_names = ['native-tests146.log', 'python-tests146.log', 'native-build146.log',
             'native-build-environment146.json', 'focused-verification146.json',
             'joint-model-audit.json', 'joint-model-audit.txt', 'audit_joint_model.py',
             'native-dependencies146.json', 'prepare_build_deps146.py', 'build_native146.py']
for name in evidence['evidence_files']:
    assert (B / name).is_file(), name
    if name not in log_names: log_names.append(name)

OUT.mkdir(parents=True, exist_ok=True)
for cache in S.rglob('__pycache__'): shutil.rmtree(cache)
verification = S / 'verification'
if verification.exists(): shutil.rmtree(verification)
verification.mkdir()
for name in log_names: shutil.copy2(B / name, verification / name)
shutil.copytree(B / 'official-reference', verification / 'official-reference')
shutil.copy2(__file__, verification / 'package146.py')

if STAGE.exists(): shutil.rmtree(STAGE)
shutil.copytree(OLD_STAGE, STAGE)
for cache in STAGE.rglob('__pycache__'): shutil.rmtree(cache)
for name in json.loads((S / 'packaging/install-files.json').read_text()):
    source = S / 'packaging' / name
    if source.is_file():
        target = STAGE / name; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
for name in ['robotd', 'robotctl', 'padd']: shutil.copy2(NATIVE / name, STAGE / name)
assert BUILD.encode() in (STAGE / 'robotd').read_bytes()
assert BUILD in (STAGE / 'release_identity.py').read_text()
assert (S / 'console/release_identity.py').read_bytes() == (STAGE / 'release_identity.py').read_bytes()
assert not (S / 'console/remote_control.py').exists()

sys.path.insert(0, str(S / 'packaging'))
from model_packages import verify_directory, catalog
from configure import dumps
joint = verify_directory(S / 'policies/walk')
JOINT_ID = joint['id']; JOINT_SHA = joint['sha256']
assert len(JOINT_ID) == 32 and JOINT_ID == JOINT_SHA[:32]
assert joint['policy_settings'] == dict(action_scale=1.0, head_lowpass=1.0, legs_lowpass=1.0)
assert joint['execution_profile'] == dict(schema='microduck-runtime-execution/v1',
    model_sha256=JOINT_SHA, mode='uniform', action_scale=.9, head_lowpass=.5, legs_lowpass=.7)
new_model = STAGE / 'models' / JOINT_ID
shutil.copytree(S / 'policies/walk', new_model, dirs_exist_ok=True)
for cache in new_model.rglob('__pycache__'): shutil.rmtree(cache)
shutil.rmtree(STAGE / 'models' / RETIRED_WALK)
assert len([p for p in (STAGE / 'models').iterdir() if p.is_dir()]) == 5
assert not (S / 'policies/joint_walk').exists()

preserved = {'source_directories': {}, 'source_files': {}, 'payload_files': {}}
for directory in ['gamepad-r7', 'padd', 'robotctl', 'sounds', 'odometry', 'firmware', 'kinematics']:
    preserved['source_directories'][directory] = same_tree(OLD / directory, S / directory)
for directory in ['stand', 'sitstand', 'ground_pick', 'roulade']:
    preserved['source_directories']['policies/' + directory] = same_tree(OLD / 'policies' / directory, S / 'policies' / directory)
preserved['source_test_fixture_only'] = dict(
    directory='test-data/walk-teacher14000',
    files=same_tree(OLD / 'policies/walk', S / 'test-data/walk-teacher14000'),
    shipped_in_runtime=False)
for name in ['Cargo.lock', 'robotd/src/params.rs', 'robotd/src/intents.rs', 'robotd/src/home_start.rs',
             'robotd/src/raw_codec.rs',
             'robotd/src/telemetry_system.rs', 'robotd/src/telemetry_geometry.rs',
             'console/static/duck.js', 'console/static/webpad-controls.js',
             'console/static/raw-telemetry.js', 'console/static/raw-kinematics.js',
             'console/static/control-socket.js', 'console/raw_telemetry.py',
             'console/socket_transport.py', 'console/console.py',
             'console/controls.py', 'console/control_socket.py']:
    assert digest(OLD / name) == digest(S / name), name
    preserved['source_files'][name] = digest(S / name)
for name in ['sounds', 'uart-service.py', 'hd1910-calibration.robot.toml',
             'hd1910-calibration.training.toml', 'hd1910-calibration.template.toml',
             'gamepad-r7/gamesir-xboxd', 'webpad.py', 'microduck-webpad.service', 'microduck-webpad.socket']:
    assert digest(OLD_STAGE / name) == digest(STAGE / name), name
    preserved['payload_files'][name] = digest(STAGE / name)
preserved['payload_old_models'] = {}
for directory in (OLD_STAGE / 'models').iterdir():
    if directory.is_dir():
        if directory.name == RETIRED_WALK:
            assert not (STAGE / 'models' / directory.name).exists()
        else:
            preserved['payload_old_models'][directory.name] = same_tree(directory, STAGE / 'models' / directory.name)
preserved['onnxruntime_files'] = same_tree(OLD_STAGE / 'onnxruntime', STAGE / 'onnxruntime')
hat = 'console/updates/imu_to_feetech_ReVA_FT6_SYNC15_UART_IRQ_v1.bin'
assert digest(S / hat) == digest(OLD / hat)
preserved['hat_firmware_sha256'] = digest(S / hat)
preserved['uploaded_training_files'] = {}
for path in sorted((B / 'model-input').rglob('*')):
    if not path.is_file() or path.name == 'checkpoint.pt': continue
    name = str(path.relative_to(B / 'model-input'))
    assert path.read_bytes() == (new_model / name).read_bytes(), name
    preserved['uploaded_training_files'][name] = digest(path)

elf = {name: elf_record(STAGE / name)
       for name in ['robotd', 'robotctl', 'padd', 'sounds', 'gamepad-r7/gamesir-xboxd']}
build = json.loads((OLD / 'BUILD.json').read_text())
build.update(build=BUILD, console_version=VERSION, api_version=40,
             source_distribution=S.name + '.tar.gz',
             generated_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
             release_changes='Replace the sole Walk with the 9600-iteration joint model; retire the old 14000 Walk. Uniform SHA-bound output settings 0.9/0.5/0.7 in all postures; preserve raw action history, independent LB and low-overhead telemetry.',
             tests=tests, rebuilt_binaries=['robotd', 'robotctl', 'padd'],
             reused_binaries=['sounds', 'gamepad-r7/gamesir-xboxd'],
             toolchain='Rust 1.99.0, cargo-zigbuild 0.23.4 and Zig 0.14.1; aarch64-unknown-linux-gnu.2.31',
             mechanism_docs=['docs/design/robotd-design.md', 'docs/design/r17-settings-design.md', 'docs/design/r17-connection-design.md'])
build.pop('build_status', None)
build['built_binaries'] = elf
build.pop('retained_walk_teacher', None)
build['retired_walk_model_id'] = RETIRED_WALK
build['runtime_model_count'] = 5
build['models']['walk'] = dict(id=JOINT_ID, sha256=JOINT_SHA, task=joint['task'], epochs=9600,
    source_iteration=9599, num_envs=2560, source_policy_directory='policies/walk',
    trained_action_scale=1.0, trained_head_alpha=1.0, trained_legs_alpha=1.0,
    execution_profile=joint['execution_profile'], deployment_verified=False)
build['manual_recovery_test']['existing_walk_preserved'] = False
build['manual_recovery_test']['requested_replacement'] = False
build['manual_recovery_test']['walk_replacement_in_this_release'] = JOINT_ID
build['joint_execution'] = dict(introduced_in=VERSION, model_sha256=JOINT_SHA,
    profile_file='deployment-execution.json', profile_sha256=digest(new_model / 'deployment-execution.json'),
    experimental=True, trained_with_this_profile=False, profile=joint['execution_profile'],
    unchanged_voltage_compensation=True, inference_hz=50, additional_network_inference=False,
    uniform_all_postures=True, additional_posture_detection=False,
    raw_previous_action=True, no_profile_uses_training_1_1_1=True,
    ordinary_upgrade_preserves_other_models_and_calibration=True, physical_tested=False)
build['official_filter_algorithm_unchanged'] = True
build['model_specific_filter_selection_changed'] = True
build['release_native_production_changes'] = [r['path'] for r in records(S)
    if r['path'].startswith(('robotd/src/', 'duck-control/src/', 'duck-ipc-proto/src/', 'kinematics/src/', 'robotd-params/src/'))
    and not r['path'].endswith('_tests.rs')
    and (not (OLD / r['path']).is_file() or digest(OLD / r['path']) != r['sha256'])]
build['release_native_test_changes'] = [r['path'] for r in records(S)
    if r['path'].startswith(('robotd/', 'duck-control/', 'duck-ipc-proto/', 'kinematics/', 'robotd-params/'))
    and (r['path'].endswith('_tests.rs') or '/tests/' in r['path'])
    and (not (OLD / r['path']).is_file() or digest(OLD / r['path']) != r['sha256'])]
for meta in build['models'].values():
    assert verify_directory(STAGE / 'models' / meta['id'])['sha256'] == meta['sha256']
for root in [S, STAGE]:
    write(root / 'BUILD.json', build); write(root / 'ELF-CHECK.json', elf)
write(STAGE / 'install-files.json', [r['path'] for r in records(STAGE, ['SHA256SUMS', 'install-files.json'])])
shutil.copy2(STAGE / 'install-files.json', S / 'packaging/install-files.json')
(STAGE / 'SHA256SUMS').write_text(''.join(f"{r['sha256']}  {r['path']}\n" for r in records(STAGE, ['SHA256SUMS'])))

spec = importlib.util.spec_from_file_location('installer146', STAGE / 'install-files.py')
installer = importlib.util.module_from_spec(spec); spec.loader.exec_module(installer)
install_log = io.StringIO()
with contextlib.redirect_stdout(install_log):
    for preimported in [False, True]:
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary); live = temp / 'installed'; shutil.copytree(OLD_STAGE, live)
            if preimported:
                target = live / 'models' / JOINT_ID
                shutil.copytree(new_model, target)
                (target / 'deployment-execution.json').unlink()
            old_models = {p.name: records(p) for p in (live / 'models').iterdir() if p.is_dir()}
            previous = temp / 'old/robotd-profile.toml'; replacement = temp / 'new/robotd-profile.toml'
            for source, target in [(OLD_STAGE, previous), (STAGE, replacement)]:
                target.parent.mkdir()
                target.write_text((source / 'robotd-profile.toml').read_text().replace('/opt/robot/feetech-ft5-r5', str(live)))
                shutil.copy2(source / 'management-profile.json', target.with_name('management-profile.json'))
            cfg = temp / 'robotd.toml'; params = tomllib.loads(previous.read_text())
            params['policy'].update(action_scale=.63, head_lowpass=.41, legs_lowpass=.69, voltage_adapt=True)
            next(s for s in params['policy']['skill'] if s['name']=='stand_test')['duration'] = 8.0
            cfg.write_text(dumps(params))
            expected = json.loads(json.dumps(params))
            expected['policy']['walk'] = str(live / 'models' / JOINT_ID / 'policy.onnx')
            operator = {'hd1910-calibration.local.toml': (OLD_STAGE / 'hd1910-calibration.robot.toml').read_bytes(),
                        'servo-test-parameters.json': b'{"kp":5,"kd":20,"torque_limit":1000}',
                        'pad-settings.json': b'{"mouth_percent":70,"head_rad":1.0}',
                        'voice-device.json': b'{"card":"aic3104","operator_saved":true}'}
            for name, data in operator.items(): (live / name).write_bytes(data)
            for attempt in range(2):
                next_cfg = temp / 'next.toml'
                result = subprocess.run([sys.executable, str(STAGE / 'configure.py'), '--source', str(cfg),
                    '--previous-overrides', str(previous), '--overrides', str(replacement), '--output', str(next_cfg)],
                    check=True, capture_output=True, text=True)
                print(result.stdout.strip())
                installer.install(STAGE, live); cfg.write_bytes(next_cfg.read_bytes())
                assert all((live / name).read_bytes() == data for name, data in operator.items())
                actual = tomllib.loads(cfg.read_text())
                assert actual['policy'] == expected['policy'], 'only requested Walk binding may change'
                assert actual['pad'] == params['pad']
                assert actual['control']['hz'] == 50
                for ident, before in old_models.items():
                    if ident == RETIRED_WALK:
                        assert not (live / 'models' / ident).exists(), 'old Walk must be removed on ordinary upgrade'
                        continue
                    after = records(live / 'models' / ident)
                    if ident == JOINT_ID: after = [r for r in after if r['path'] != 'deployment-execution.json']
                    assert after == before, ident
                assert (live / 'models' / JOINT_ID / 'deployment-execution.json').read_bytes() == (new_model / 'deployment-execution.json').read_bytes()
                for name in ['robotd', 'robotctl', 'padd', 'release_identity.py', 'webpad.py']:
                    assert digest(live / name) == digest(STAGE / name), name
                listing = catalog(live, cfg)
                assert len(listing['models']) == 5 and all(row['available'] for row in listing['models'])
                assert RETIRED_WALK not in {row['id'] for row in listing['models']}
                assert listing['configured_model'] == JOINT_ID
                assert sum(row['slot'] == 'walk' for row in listing['slots']) == 1
                assert listing['manual_recovery']['model']['id'] == build['models']['stand']['id']
                assert next(row for row in listing['slots'] if row['slot'] == 'stand')['model'] is None
                previous.write_bytes(replacement.read_bytes())
                previous.with_name('management-profile.json').write_bytes(replacement.with_name('management-profile.json').read_bytes())
            print(f'PASS actual v145-to-v146 payload twice; preimported joint={preimported}; five models, sole new Walk, old Walk removed, original training files, LB binding/duration, calibration, saved parameters and 50Hz verified.')
(verification / 'payload-upgrade146.log').write_text(install_log.getvalue())

archive = S / 'console/updates/Microduck-Robotd-FT6-R17.tar.gz'
with tarfile.open(archive, 'w:gz', compresslevel=9) as tar:
    tar.add(STAGE, arcname=STAGE.name, filter=lambda item: None if '__pycache__' in Path(item.name).parts else item)
console = S / 'console'
manifest = json.loads((OLD / 'console/BUILD_MANIFEST.json').read_text())
manifest.update(console_version=VERSION, service_build=BUILD, service_package_sha256=digest(archive),
                source_distribution=build['source_distribution'], tests_run_in_release=tests)
manifest.pop('build_status', None); manifest['files'] = records(console, ['BUILD_MANIFEST.json'])
write(console / 'BUILD_MANIFEST.json', manifest)
firmware_zip = OUT / f'Microduck-Firmware-R17-v{VERSION}.zip'
with zipfile.ZipFile(firmware_zip, 'w', zipfile.ZIP_DEFLATED) as package:
    for path in [archive, STAGE / 'README.zh-CN.md', STAGE / 'BUILD.json', STAGE / 'ELF-CHECK.json']:
        package.write(path, f'Microduck-Firmware-R17-v{VERSION}/' + path.name)
console_zip = OUT / f'Microduck-Console-R17-v{VERSION}.zip'
with zipfile.ZipFile(console_zip, 'w', zipfile.ZIP_DEFLATED) as package:
    for record in records(console): package.write(console / record['path'], f'Microduck-Console-R17-v{VERSION}/' + record['path'])
sys.path.insert(0, str(console))
from firmware_packages import bundle_info, PreparedFirmware
assert bundle_info()['console_version'] == VERSION
for package in [firmware_zip, console_zip]:
    with package.open('rb') as stream:
        prepared = PreparedFirmware(package.name, stream, package.stat().st_size, 'release146-check')
        try: assert digest(prepared.path) == digest(archive)
        finally: prepared.close()

changed = [r['path'] for r in records(STAGE) if not (OLD_STAGE / r['path']).is_file() or digest(OLD_STAGE / r['path']) != r['sha256']]
audit = dict(console_version=VERSION, service_build=BUILD, tests=tests, preserved=preserved,
    evidence=[dict(name=name, sha256=digest(B / name)) for name in log_names],
    changed_payload_files=changed, install_repeated_with_settings_preserved=True,
    preimported_model_receives_execution_profile=True,
    old_walk_removed_on_ordinary_upgrade=True, only_one_walk_slot=True, runtime_models=5,
    console_and_firmware_import_verified=True, payload_sha256=digest(archive),
    rebuilt_binaries=build['rebuilt_binaries'], hardware_tested=False,
    api_version=40, raw_schema='r17.raw.v1', raw_envelope_changed=False,
    additive_execution_metadata=True)
write(verification / 'release-audit146.json', audit)
(verification / 'REPRODUCE.txt').write_text('''Use Rust 1.99 and ONNX Runtime 1.28 via ORT_DYLIB_PATH.
PYTHONPATH="$PWD/packaging:$PWD/console" python3 -m unittest discover -s packaging -p 'test_*.py' -v
cargo test -p robotd --bin robotd --locked
cargo test -p duck-control --lib --locked
cargo test -p robotd-params -p duck-ipc-proto --lib --bins --locked
cargo test -p padd --bins --locked
Cross-build: cargo zigbuild -p robotd -p robotctl -p padd --release --target aarch64-unknown-linux-gnu.2.31 --locked
build_native146.py records exact versions, dependency paths and source/binary SHA256.
prepare_build_deps146.py unpacks real Debian host/ARM libudev and pkgconf locally;
it does not install system packages or change the firmware's runtime libraries.
See focused-verification146.json for frontend commands and original logs.
package146.py expects work-r17-145 as the preceding source/payload, work-r17-146
with model-input and the current logs; source files are hashed before/after build.
It installs the real payload twice over v145, with/without the same model already
imported, then imports both ZIP formats through the production PreparedFirmware.
The model audit's original paths describe this audit workspace. To reproduce
elsewhere point INPUT at policies/walk and BASE at this source (old walk teacher
fixture is retained only in test-data/walk-teacher14000), with its output ROOT
in a temporary working directory. checkpoint.pt is never deserialized.
No real Zero, Chromium rendering, systemd/uinput activation or live GameSir test.
Existing listener-dependent system integration is not claimed; this host has
previously denied AF_UNIX listener creation.
''')
summary = json.loads((OLD / 'R17-SOURCE-MANIFEST.json').read_text())
summary.update(console_version=VERSION, service_build=BUILD,
    release_changed_files=[r['path'] for r in records(S, ['R17-SOURCE-MANIFEST.json', 'SHA256SUMS'])
        if not (OLD / r['path']).is_file() or digest(OLD / r['path']) != r['sha256']],
    release_removed_files=[r['path'] for r in records(OLD) if not (S / r['path']).exists()],
    files=records(S, ['R17-SOURCE-MANIFEST.json', 'SHA256SUMS']))
write(S / 'R17-SOURCE-MANIFEST.json', summary)
(S / 'SHA256SUMS').write_text(''.join(f"{r['sha256']}  {r['path']}\n" for r in records(S, ['SHA256SUMS'])))
source_archive = OUT / build['source_distribution']
with tarfile.open(source_archive, 'w:gz', compresslevel=9) as tar:
    tar.add(S, arcname=S.name, filter=lambda item: None if '__pycache__' in Path(item.name).parts else item)

native_lines = '\n'.join(f"- {name}: {result['passed']}通过，{result['ignored']}默认忽略。" for name, result in suites.items())
report = OUT / f'Microduck-R17-v{VERSION}-Changes-and-Verification.txt'
report.write_text((S / 'README-R17.zh-CN.md').read_text() + '\n\n模型审计\n' + (B / 'joint-model-audit.txt').read_text() + f'''

本轮发布验证
- Python: {python_result['run']}项运行，{python_result['passed']}通过，{python_result['skipped']}跳过。
{native_lines}
- 定向界面验证详见源码 verification/focused-verification146.json 及原始日志，DOM测试没有运行Chromium。
- robotd、robotctl、padd 已配套交叉编译为API40的AArch64程序，GLIBC符号依赖不高于2.31。
- 实际v145→v146载荷在临时目录验证两种路径，各连续安装两次：原设备无新模型、原设备已导入相同模型但无执行配置。
- 唯一Walk替换为新联合，旧行走模型目录普通升级即删除，运行目录共五个模型；原训练数据、LB绑定/8秒测试时长、保存的全局参数和本机标定按字节或配置语义核对。
- 真实手柄桥、HAT固件、ONNX Runtime和v144遥测传输/记录运行代码按SHA256对照保留。padd源逻辑不变，本版因API40重新编译。
- 两个ZIP通过生产导入器，内含同一固件载荷。
- 本轮没有实机Zero、systemd/uinput激活、真实手柄或板温测试。合成ONNX输入和假硬件控制循环不证明闭环行走/起身成功。

联合模型SHA256: {JOINT_SHA}
执行配置SHA256: {digest(new_model / 'deployment-execution.json')}
固件载荷SHA256: {digest(archive)}
robotd SHA256: {digest(STAGE / 'robotd')}
robotctl SHA256: {digest(STAGE / 'robotctl')}
padd SHA256: {digest(STAGE / 'padd')}
源码、模型原文件、官方精确提交证据和发布审计包含在源码包中。
''')
artifacts = [console_zip, firmware_zip, source_archive, report]
(OUT / f'SHA256SUMS-v{VERSION}.txt').write_text(''.join(f'{digest(p)}  {p.name}\n' for p in artifacts))
print(json.dumps(dict(build=BUILD, artifacts=[dict(name=p.name, bytes=p.stat().st_size, sha256=digest(p)) for p in artifacts],
    changed_payload_files=changed, artifacts_verified=True, hardware_tested=False), ensure_ascii=False, indent=2))

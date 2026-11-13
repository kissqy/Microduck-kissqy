#!/usr/bin/env python3
"""Build the current V167/control.43 package from a verified V164 baseline."""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys
import tarfile
import tempfile
import zipfile

SRC = Path(__file__).resolve().parent
BUILD = '1fa8438-feetech-ft6-control.43'
VERSION = '1.0.167'
ARCHIVE = 'Microduck-Robotd-FT6-R17.tar.gz'
BASE_SHA = '5c9313b2aba04b89c5dc608644ba7d814771623597d11ddc6a10373528272d31'
SOURCE_NAME = 'Microduck-Source-R17-V167-control43-clean.tar.gz'
# Reuse the existing extraction, ELF and hash utilities, without invoking its
# previous-version release validation or build routine.
spec = importlib.util.spec_from_file_location('package_util', SRC/'package-utils.py')
util = importlib.util.module_from_spec(spec); spec.loader.exec_module(util)
digest, files_in, write_json = util.digest, util.files_in, util.write_json

def read_record(name):
    return json.loads((SRC/'verification/v167'/name).read_text())

def verify_native(path, previous, name):
    raw = path.read_bytes()
    if len(raw)<500000 or raw[:4]!=b'\x7fELF' or raw[4:6]!=b'\x02\x01' or int.from_bytes(raw[18:20],'little')!=183:
        raise ValueError(name+': expected a real Linux AArch64 release program')
    if name=='robotd' and digest(path)==digest(previous):
        raise ValueError(name+': old binary cannot be issued as a new build')
    if name=='padd' and digest(path)!=digest(previous):
        raise ValueError('padd must remain byte-identical to V164')
    if name=='robotd' and BUILD.encode() not in raw:
        raise ValueError('robotd build identity is not control.43')

def build(args):
    if digest(args.base)!=BASE_SHA:
        raise ValueError('Use the specified V164 baseline; calibration and console fixes must be preserved')
    source = read_record('source-diff.json')
    for name, expected in source['sha256'].items():
        if digest(SRC/name)!=expected: raise ValueError('Source changed after verification: '+name)
    rust = read_record('release-tests.json')
    python = read_record('python-tests.json')
    models = read_record('arm64-models.json')
    if rust['failed'] or rust['passed']<236 or python['failed'] or python['passed']<1:
        raise ValueError('Current test scope has not passed')
    if len(models['results'])!=10 or any(r['exit_code'] for r in models['results']) or models['deployment_info']['build']!=BUILD or models['robotd_sha256']!=digest(args.robotd):
        raise ValueError('Current native model validation does not match the shipped binary')
    if not re.search(r'Finished `release` profile', (SRC/'verification/v167/arm64-build.log').read_text()):
        raise ValueError('Missing successful ARM64 build log')
    with tempfile.TemporaryDirectory(prefix='microduck-v167-') as temp:
        temp = Path(temp)
        with zipfile.ZipFile(args.base) as z:
            root = z.namelist()[0].split('/')[0]
            manifest = json.loads(z.read(root+'/BUILD_MANIFEST.json'))
            raw = z.read(root+'/updates/'+ARCHIVE)
            if manifest['service_build']!='1fa8438-feetech-ft6-control.40' or util.content_hash(raw)!=manifest['service_package_sha256']:
                raise ValueError('Baseline firmware identity or digest mismatch')
        util.extract_trusted_zip(args.base, temp)
        console = temp/root
        nested = temp/'native'; nested.mkdir()
        util.extract_trusted_tar(raw,nested)
        fw = nested/'Microduck-Robotd-FT6-R17'
        for name, path in (('robotd',args.robotd),('padd',args.padd)):
            verify_native(path, fw/name, name)
            shutil.copy2(path,fw/name); (fw/name).chmod(0o755)
        for name in ('release_identity.py','README.zh-CN.md'):
            shutil.copy2(SRC/'packaging'/name,fw/name)
        now = datetime.now(timezone.utc).isoformat()
        metadata = json.loads((fw/'BUILD.json').read_text())
        metadata.update(build=BUILD, console_version=VERSION, source_distribution=SOURCE_NAME,
            release_changes='V164 control flow with only explicit RAM D=0 and address48=1000 writes; model-contract P unchanged',
            native_production_changes=['duck-control/src/hd1910.rs','robotd/src/feetech_commissioning.rs: build identity'],
            hardware_verified=False, firmware_reinstall_required=True,
            release_status='compiled-unverified-hardware',
            package_baseline={'name':args.base.name,'sha256':BASE_SHA,'calibration':'authorized calibration preserved byte-for-byte'},
            release_scope_tests={'passed':rust['passed'],'failed':rust['failed'],'scope':rust['selected_scope']},
            generated_at_utc=now)
        metadata['toolchain']='Rust 1.99.0 / cargo-zigbuild 0.23.4 / Zig 0.15.1; aarch64-unknown-linux-gnu.2.31'
        # Earlier diagnostics remain available, explicitly identified by source
        # record. They are not the current release's test results.
        metadata.pop('regression_tests',None)
        metadata['historical_diagnostics_record']='source distribution: verification/v160/rust-tests.json'
        metadata['tests']={'robot_hardware_tested':False,'windows_native_tested':False,'browser_pixel_rendered':False,
            'rust_release_scope_passed':rust['passed'],'rust_release_scope_failed':0,'python_current_scope_passed':python['passed'],
            'arm64_qemu_models_passed':10,'full_workspace_regression_run':False,'source_records':'verification/v167/'}
        metadata['baseline_verification_report']=metadata.pop('verification_report',metadata.get('baseline_verification_report'))
        metadata['roller_standup']={'path':'roller/standup/policy.onnx',
            'sha256':'2575b5894bcd8e3fdbe005b1a7b90d9491085726df32000c26cf5b92b7a10ebb',
            'checkpoint':11000, 'trigger_bound':True, 'trigger':'physical_L3',
            'route':'manual_skill', 'duration_seconds':5.0, 'duration_source':'local manual test window; export unchanged',
            'guards':['roller mode','motion already enabled','not limp','fresh healthy IMU','debounced fallen and consistent quaternion'],
            'automatic_stand':False}
        metadata['rebuilt_binaries']=['robotd']
        metadata['unchanged_binaries']=['padd','robotctl','mediad','sounds','gamepad-r7/gamesir-xboxd']
        metadata['hd1910_runtime_settings']={'p':{'source':'model_contract','address':50,'bytes':1,'restore_on_relax':True,'existing_readback_preserved':True},'d':{'value':0,'address':51,'bytes':1},'torque_limit':{'value':1000,'address':48,'bytes':2,'byte_order':'little'},'write_trigger':'V164 explicit arm flow','fixed_settings_readback_added':False,'eeprom_changed':False}
        binaries = metadata['built_binaries']
        elf = json.loads((fw/'ELF-CHECK.json').read_text())
        for name in ('robotd','padd'):
            binaries[name]=util.read_elf(fw/name,binaries[name])
            elf[name]=util.read_elf(fw/name,elf[name])
        metadata['padd_source_sha256']=digest(SRC/'padd/src/main.rs')
        metadata['padd_roller_test_sha256']=digest(SRC/'padd/src/roller_test.rs')
        write_json(fw/'BUILD.json',metadata); write_json(fw/'ELF-CHECK.json',elf)
        inventory = json.loads((fw/'install-files.json').read_text())
        recognized = set(inventory)|{'install-files.json','SHA256SUMS'}
        actual = {p.relative_to(fw).as_posix() for p in files_in(fw)}
        if actual!=recognized or len(inventory)!=len(set(inventory)):
            raise ValueError('Firmware inventory mismatch')
        (fw/'SHA256SUMS').write_text(''.join(f'{digest(fw/name)}  {name}\n' for name in sorted(set(inventory)|{'install-files.json'})))
        check_spec = importlib.util.spec_from_file_location('elf_check',fw/'elf_integrity.py')
        check = importlib.util.module_from_spec(check_spec); check_spec.loader.exec_module(check)
        checked = check.validate_bundle(fw)
        assert checked['robotd']['machine']=='AArch64' and checked['padd']['machine']=='AArch64'
        for line in (fw/'SHA256SUMS').read_text().splitlines():
            sha,name = line.split('  ',1); assert digest(fw/name)==sha, name
        # Make the compiled source distribution carry exactly the same binaries,
        # manifests and integrity list as the released firmware.
        for name in ('robotd','padd','BUILD.json','ELF-CHECK.json','SHA256SUMS','install-files.json'):
            shutil.copy2(fw/name,SRC/'packaging'/name)
        arch = console/'updates'/ARCHIVE
        with tarfile.open(arch,'w:gz',compresslevel=9) as tar:
            for path in files_in(fw):
                tar.add(path,arcname='Microduck-Robotd-FT6-R17/'+path.relative_to(fw).as_posix(),recursive=False)
        shutil.copy2(arch,SRC/'console/updates'/ARCHIVE)
        if arch.stat().st_size>40*1024*1024:
            raise ValueError('Firmware exceeds the existing upload gate')
        for name in ('release_identity.py','README.zh-CN.md','THIRD_PARTY_NOTICES.md','verification/README.md'):
            shutil.copy2(SRC/'console'/name,console/name)
        logs = []
        for name in ('arm64-build.log','release-tests.json','release-tests.log','python-tests.json','python-tests.log','arm64-models.json','source-diff.json'):
            source = SRC/'verification/v167'/name
            if not source.is_file(): raise ValueError('Missing release evidence '+name)
            relative = 'verification/v167/'+name
            destination = console/relative; destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,destination)
            native_destination = SRC/'console'/relative; native_destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,native_destination)
            logs.append({'path':relative,'sha256':digest(source)})
        manifest.update(console_version=VERSION,service_build=BUILD,service_package_sha256=digest(arch),
            source_distribution=SOURCE_NAME,generated_at_utc=now,
            release_changes='Keep model-contract P; explicitly write RAM D=0 and 48=1000 in the existing arm flow',
            release_status='compiled-unverified-hardware',hardware_verified=False,firmware_reinstall_required=True,
            package_baseline=metadata['package_baseline'],
            roller_experiment={'installed':True,'active':'physical-gamepad-only','models':['swizzle','crouch','spin','standup'],'installed_models':['swizzle','crouch','spin','standup'],'unbound_models':[],
                'standup_trigger':'physical_L3_guarded_manual_test','standup_test_duration_s':5.0})
        manifest['hd1910_runtime_settings']=metadata['hd1910_runtime_settings']
        manifest['toolchain']=metadata['toolchain']
        manifest['tests_run_in_release']={'robot_hardware_tested':False,'rust_passed':rust['passed'],'rust_failed':0,'rust_ignored':rust['ignored'],
            'full_regression_run':False,'release_scope_passed':True,'release_scope_description':rust['selected_scope'],
            'python_passed':python['passed'],'arm64_model_loads_passed':10,'arm64_release_compiled':True,'logs':logs}
        manifest['files']=[{'path':p.relative_to(console).as_posix(),'bytes':p.stat().st_size,'sha256':digest(p)} for p in files_in(console) if p.name!='BUILD_MANIFEST.json']
        write_json(console/'BUILD_MANIFEST.json',manifest)
        shutil.copy2(console/'BUILD_MANIFEST.json',SRC/'console/BUILD_MANIFEST.json')
        output = args.output.resolve(); output.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for path in files_in(console):
                z.write(path,arcname='Microduck-Console-R17-V167/'+path.relative_to(console).as_posix())
        with zipfile.ZipFile(output) as z: assert z.testzip() is None
        print(f'V167/control.43: {output} ({output.stat().st_size} bytes)')

if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',type=Path,default=SRC.parents[1]/'release-assets/build-baselines/Microduck-Console-R17-V164.zip')
    parser.add_argument('--robotd',type=Path,default=SRC/'packaging/robotd')
    parser.add_argument('--padd',type=Path,default=SRC/'packaging/padd')
    parser.add_argument('--output',type=Path,default=SRC/'Microduck-Console-R17-V167.zip')
    args = parser.parse_args()
    try: build(args)
    except Exception as error:
        print('V167 packaging rejected: '+str(error),file=sys.stderr); sys.exit(1)

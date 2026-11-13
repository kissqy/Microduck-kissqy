#!/usr/bin/env python3
"""Verify current binaries, inventory, assets and all preserved baseline bytes."""
import hashlib,io,json,sys,tarfile,zipfile,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ARCHIVE='updates/Microduck-Robotd-FT6-R17.tar.gz'
sha=lambda b:hashlib.sha256(b).hexdigest()
def package(path):
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        root=z.namelist()[0].split('/')[0]
        data={n[len(root)+1:]:z.read(n) for n in z.namelist() if not n.endswith('/')}
    with tarfile.open(fileobj=io.BytesIO(data[ARCHIVE])) as t:
        native={m.name.split('/',1)[1]:t.extractfile(m).read() for m in t if m.isfile()}
    return data,native
new,native=package(Path(sys.argv[1]))
old,baseline=package(ROOT.parents[1]/'release-assets/build-baselines/Microduck-Console-R17-V164.zip')
manifest=json.loads(new['BUILD_MANIFEST.json'])
assert manifest['console_version']=='1.0.167'
assert manifest['service_build']=='1fa8438-feetech-ft6-control.43'
assert manifest['service_package_sha256']==sha(new[ARCHIVE])
for row in manifest['files']:assert sha(new[row['path']])==row['sha256'],row['path']
metadata=json.loads(native['BUILD.json'])
assert metadata['tests']['rust_release_scope_failed']==0
inventory=json.loads(native['install-files.json'])
assert set(native)==set(inventory)|{'install-files.json','SHA256SUMS'}
for line in native['SHA256SUMS'].decode().splitlines():
    digest,name=line.split('  ',1);assert sha(native[name])==digest,name
changed_native={'robotd','release_identity.py','README.zh-CN.md',
                'BUILD.json','ELF-CHECK.json','SHA256SUMS','install-files.json'}
for name,data in baseline.items():
    if name not in changed_native:assert native[name]==data, 'baseline firmware changed: '+name
new_files=set(native)-set(baseline)
assert not new_files
assert native['robotd']!=baseline['robotd']
assert native['robotd']==(ROOT/'packaging/robotd').read_bytes()
assert native['padd']==baseline['padd']
settings=metadata['hd1910_runtime_settings']
assert settings['p']['source']=='model_contract' and settings['p']['restore_on_relax']
assert settings['d']=={'value':0,'address':51,'bytes':1}
assert settings['torque_limit']=={'value':1000,'address':48,'bytes':2,'byte_order':'little'}
assert settings['fixed_settings_readback_added'] is False
assert b'1fa8438-feetech-ft6-control.43' in native['robotd']
allowed_console={'BUILD_MANIFEST.json','README.zh-CN.md','release_identity.py',ARCHIVE,'verification/README.md'}
for name,data in old.items():
    if name not in allowed_console: assert new[name]==data, 'baseline console changed: '+name
assert set(old)<=set(new)
assert all(n.startswith('verification/v167/') for n in set(new)-set(old))
for name in ['static/control.js','static/index.html','service_control.py','socket_transport.py']:
    assert new[name]==old[name],name
assert '本版包含新编译的 robotd' in new['README.zh-CN.md'].decode()
import tempfile
with tempfile.TemporaryDirectory() as d:
    directory=Path(d)
    for name,data in new.items():
        if name.endswith(('.py','.json')) and '/' not in name:(directory/name).write_bytes(data)
    run=subprocess.run([sys.executable,'-c',"import console,service_control,telemetry,release_identity; assert telemetry.VERSION=='1.0.167'; assert release_identity.BUILD.endswith('control.43')"],cwd=directory,capture_output=True,text=True)
    assert run.returncode==0,run.stderr
record={'console_version':'1.0.167','build':manifest['service_build'],
        'console_sha256':sha(Path(sys.argv[1]).read_bytes()),'firmware_sha256':sha(new[ARCHIVE]),
        'models_calibration_and_unrelated_services_byte_identical':True,
        'transport_and_control_js_byte_identical':True,'current_console_imported':True,
        'padd_byte_identical_to_v164':True,
        'runtime_settings':settings,
        'native_files':{n:sha(native[n]) for n in ['robotd','padd']},
        'hardware_tested':False}
(ROOT/'verification/v167/package-verification.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))

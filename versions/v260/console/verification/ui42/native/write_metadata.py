from pathlib import Path
import hashlib,json,subprocess,re,datetime
root=Path('/workspace/scratch/0587ce872ec5');src=root/'native_work/Microduck-Source-R17-V186-control57';ev=root/'ui42_native_evidence';binary=root/'native_work/target-arm-ui42/aarch64-unknown-linux-gnu/release/padd'
def command(args):return subprocess.run(args,check=True,text=True,capture_output=True).stdout.strip()
versions={label:command(args) for label,args in {'rustc':['rustc','-Vv'],'cargo':['cargo','--version'],'zig':['zig','version'],'rustfmt':['rustfmt','--version']}.items()}
versions['cargo-zigbuild']=re.search(r'^Version: (.+)$',next((root/'native_toolchain/python').glob('cargo_zigbuild-*.dist-info/METADATA')).read_text(),re.M).group(1)
(ev/'toolchain.json').write_text(json.dumps(versions,indent=2)+'\n')
elf=command(['file',str(binary)])+'\n\n'+command(['readelf','-h','-l','-d','-V',str(binary)])+'\n';(ev/'padd-elf.txt').write_text(elf)
log=(ev/'padd-tests.log').read_text();test=re.search(r'test result: ok\. (\d+) passed; (\d+) failed;',log);assert test and test.group(1)=='89' and test.group(2)=='0'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
meta={
 'release':'Microduck-UI42','component':'padd','status':'built; host tests passed; not run on physical robot','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'source_base':'UI41 padd (native_work/ui41_padd_before_ui42), original frozen V186/control57 plus documented UI37/UI40/UI41 padd patches; robotd remains packaged control73 unchanged',
 'changed_files':['padd/src/main.rs','padd/src/recorder.rs'],
 'source_sha256':{p:sha(src/p) for p in ['padd/src/main.rs','padd/src/recorder.rs','padd/Cargo.toml','Cargo.lock']},
 'unchanged_ui41_modules_sha256':json.loads((ev/'unchanged-ui41-modules.json').read_text()),
 'target':'aarch64-unknown-linux-gnu.2.31','binary_path':str(binary),'binary_sha256':sha(binary),'binary_size':binary.stat().st_size,
 'host_tests':{'command':'cargo test --locked -p padd -j4 -- --test-threads=1','passed':89,'failed':0,'log':'padd-tests.log'},
 'arm_build':{'command':'cargo zigbuild --locked --release -p padd -j4 --target aarch64-unknown-linux-gnu.2.31','passed':True,'log':'padd-arm-build.log','warning':'linker ignores deprecated optimization setting 1'},
 'elf':{'machine':'AArch64','class':'ELF64','type':'PIE','interpreter':'/lib/ld-linux-aarch64.so.1','max_glibc_required':'2.30','needed':['libudev.so.1','libm.so.6','libpthread.so.0','libc.so.6','libdl.so.2']},
 'patch_replay':'native-source.patch applied to UI41 backup; all changed files byte-identical; see patch-replay.json',
 'checks':{'new_module_rustfmt':True,'main_formatting':'restored unchanged UI41 lexical-token spans; no unrelated module formatting retained'},
 'test_boundary':'Real AF_UNIX socket-pair end-to-end test covers monitor subscribe/response/state interleaving. UnixListener::bind is EPERM in this environment; no bind-based or hardware result claimed.',
 'limitations':['Intent timing replay, not physical trajectory or arrival verification.','Identity compares mode, loaded model paths and skill catalog; same-path model file hash is not verified.','Finite native models have no general cancel API: later frames stop and manual safety follows the existing paths.','Accepted skill requests use the existing synchronous intent socket, bounded by its existing timeout; new events wait for the next drain.','No automatic torque enable, HOME, recovery, or mode switch.','No robotd, model, mediad, or daemon protocol changes.']}
(ev/'native-build.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n');(ev/'padd.sha256').write_text(f'{sha(binary)}  padd\n')
print(json.dumps({'binary_sha256':meta['binary_sha256'],'size':meta['binary_size'],'passed':89}))

#!/usr/bin/env bash
set -euo pipefail
V167_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$V167_DIR"
for program in cargo rustc zig cargo-zigbuild pkg-config python3; do
    command -v "$program" >/dev/null || { echo "Missing build dependency: $program" >&2; exit 1; }
done
rustc --version
test "$(zig version)" = "0.15.1"
test -n "${ORT_DYLIB_PATH:-}" || { echo 'Set ORT_DYLIB_PATH to host ONNX Runtime 1.28.0' >&2; exit 1; }
test -n "${QEMU_AARCH64:-}" && test -n "${ARM64_RUNTIME_PREFIX:-}" || {
    echo 'Set QEMU_AARCH64 and ARM64_RUNTIME_PREFIX to the ARM64 validation environment' >&2; exit 1;
}
export CARGO_INCREMENTAL=0
python3 prepare-V167.py
mkdir -p verification/v167
python3 verification/verify-V167-source.py
python3 verification/run-V167-tests.py --release-scope
python3 - <<'PY'
import json,re,subprocess
from pathlib import Path
run=subprocess.run(['python3','-m','unittest','-v','test_model_packages_execution','test_atomic_install'],cwd='packaging',capture_output=True,text=True)
output=run.stdout+run.stderr
Path('verification/v167/python-tests.log').write_text(output)
match=re.search(r'Ran (\d+) tests',output)
passed=int(match.group(1)) if match and not run.returncode else 0
Path('verification/v167/python-tests.json').write_text(json.dumps({'passed':passed,'failed':int(bool(run.returncode)),'hardware_tested':False,'scope':'model execution contracts and atomic installation'},indent=2)+'\n')
print(output);raise SystemExit(run.returncode)
PY
cargo zigbuild --locked --release --config profile.release.package.pet-detect.codegen-units=1 \
    --config profile.release.package.robotd.codegen-units=1 -p robotd \
    --target aarch64-unknown-linux-gnu.2.31 2>&1 | tee verification/v167/arm64-build.log
V167_TARGET_DIR=${CARGO_TARGET_DIR:-$V167_DIR/target}
python3 verification/run-V167-models.py --binary "$V167_TARGET_DIR/aarch64-unknown-linux-gnu/release/robotd"
python3 package-V167.py --robotd "$V167_TARGET_DIR/aarch64-unknown-linux-gnu/release/robotd" --padd packaging/padd
python3 verification/verify-V167-package.py Microduck-Console-R17-V167.zip

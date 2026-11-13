#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
test $# -eq 1 || { echo 'Usage: bash BUILD-V260.sh /path/Microduck-Firmware-V260-control102.zip' >&2; exit 1; }
python3 prepare-resources.py "$1"
export CARGO_INCREMENTAL=0
cargo zigbuild --locked --release --target aarch64-unknown-linux-gnu.2.31 \
  --config profile.release.package.pet-detect.codegen-units=1 \
  --config profile.release.package.robotd.codegen-units=1 \
  -p robotd -p padd -p robotctl -p sounds -p mediad
echo 'Native build completed. Output: target/aarch64-unknown-linux-gnu/release/'
echo 'This command does not install to a robot or replace the published V260 payload.'

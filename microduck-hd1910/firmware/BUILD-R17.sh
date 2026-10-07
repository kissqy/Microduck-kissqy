#!/usr/bin/env bash
set -euo pipefail
export CARGO_TARGET_AARCH64_UNKNOWN_LINUX_GNU_LINKER=${CARGO_TARGET_AARCH64_UNKNOWN_LINUX_GNU_LINKER:-aarch64-linux-gnu-gcc}
export PKG_CONFIG_ALLOW_CROSS=1
# Supply an AArch64 libudev sysroot through PKG_CONFIG_SYSROOT_DIR/PATH.
cargo build --locked --release -p robotd -p padd -p robotctl -p sounds --target aarch64-unknown-linux-gnu --config profile.release.codegen-units=1
"$CARGO_TARGET_AARCH64_UNKNOWN_LINUX_GNU_LINKER" -O2 -Wall -Wextra -Werror -std=gnu11 gamepad-r7/gamesir-xboxd.c -o gamepad-r7/gamesir-xboxd

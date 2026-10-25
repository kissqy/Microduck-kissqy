[简体中文](BUILDING-V167.md) | **English** | [Русский](BUILDING-V167.ru.md)

# R17 V167 / control.43 build guide

Console: `1.0.167`. Robot firmware: `1fa8438-feetech-ft6-control.43`. Official system baseline: `0.15.1`.

**Update: Fixed body jitter.**

## Source and compiled downloads

This directory keeps source, configuration, tests, licenses and interface assets. Complete console ZIPs are in the repository's `release-assets/`. The standalone firmware stays in `console/updates/` for the existing console installer.

Compiled programs, ONNX shared libraries and duplicate packaged model binaries are restored from the verified firmware instead of being stored twice. Before building or running package-dependent tests:

```bash
python3 prepare-V167.py
```

The script verifies pinned SHA256 values and restores the required resources. Git ignores generated copies. `--check` only checks archive hashes; `--download` retrieves missing pinned archives and verifies their hashes.

The V164 ZIP is kept once as a reproducible build baseline at `../../release-assets/build-baselines/Microduck-Console-R17-V164.zip`. Packaging and verification use that location.

## Build

Requirements: Linux/WSL, Rust 1.99, the AArch64 GNU target, cargo-zigbuild 0.23.4, Zig 0.15.1, Python 3, pkg-config and libudev development files. See [BUILD.en.md](../docs/BUILD.en.md) for ordinary source compilation. Full release reproduction additionally needs host ONNX Runtime 1.28.0, QEMU and an ARM64 userland.

```bash
export ORT_DYLIB_PATH=/absolute/path/to/host/libonnxruntime.so.1.28.0
export QEMU_AARCH64=/absolute/path/to/qemu-aarch64
export ARM64_RUNTIME_PREFIX=/absolute/path/to/arm64-userland
bash build-V167.sh
```

The script restores resources, checks source, runs the original release tests, builds robotd, validates bundled models and creates the complete V167 installer from the original V164 baseline. Generated resources and build outputs are not committed.

## Records

`verification/v167/` contains the prior compilation records: 237 Rust tests, 18 Python tests and ten ARM64/QEMU model loads and first inferences. These are historical release results, not tests rerun during directory cleanup. This cleanup compares source, release archives and restored resource bytes without rebuilding firmware or operating a physical robot.

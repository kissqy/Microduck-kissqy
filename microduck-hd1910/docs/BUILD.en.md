[简体中文](BUILD.md) | **English** | [Русский](BUILD.ru.md)

# Build control.43 from source

For daily use, download the system image and V167 console; compilation is unnecessary. This page covers rebuilding ZERO programs after changing the source. Current firmware is **control.43**, distributed with V167.

On Windows, use a WSL / Linux terminal in VS Code. After cloning this repository, enter `microduck-hd1910` first.

## Install the build environment

```bash
sudo apt-get update
sudo apt-get install -y build-essential pkg-config libudev-dev python3-venv curl ca-certificates xz-utils binutils dpkg
```

If rustup is missing, install the official Rust tools; otherwise skip this step:

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain none
source "$HOME/.cargo/env"
```

Install the pinned toolchain from the release records:

```bash
rustup toolchain install 1.99.0 --profile minimal --target aarch64-unknown-linux-gnu
python3 -m venv .build/firmware-tools
.build/firmware-tools/bin/python -m pip install cargo-zigbuild==0.23.4 ziglang==0.15.1
```

## Build ZERO programs

```bash
bash tools/build-firmware.sh --check
bash tools/build-firmware.sh
```

`--check` checks installed tools and pinned dependency records without downloading or compiling. The build uses `Cargo.lock`, Rust **1.99.0**, cargo-zigbuild **0.23.4**, and Zig **0.15.1**, targeting `aarch64-unknown-linux-gnu.2.31`. It matches the control.43 records and sets release codegen-units to 1 for `robotd` and `pet-detect`.

Output is in **`.build/firmware/bin/`**:

| File | Purpose |
| --- | --- |
| `robotd` | Robot control service |
| `robotctl` | Robot CLI |
| `padd` | Gamepad input service |
| `sounds` | Sound synthesis |
| `gamesir-xboxd` | GameSir → Xbox input bridge |
| `BUILD-LOCAL.json`, `SHA256SUMS` | Build identity and checksums |

These programs target ARM64 Linux / ZERO. This entry point only builds programs: it does not connect to a robot, install services, or create a complete importable firmware ZIP. Running services also requires their configuration, models, helpers, and ARM64 ONNX Runtime. `mediad` source is in the workspace but is not included in this five-program build. Its Linux build requires GStreamer; see [workspace development](../firmware/CONTRIBUTING.md).

### libudev dependency

The gamepad program requires libudev. Host `libudev-dev` supports host-side build stages. ARM64 dependencies are downloaded according to [`build-environment150-libudev-sysroot.json`](../firmware/verification/build-environment150-libudev-sysroot.json), pinned to Debian Trixie **257.13-1~deb 13 u 1** `libudev-dev` and `libudev1`. The script checks pinned URLs and SHA256, then extracts them into `.build/firmware/sysroot/arm64`; it does not install ARM libraries on the host. The record retains its original 150 filename and is still the current cross-build dependency source.

### Relationship to delivered programs

Current build identity and binary hashes are in [`firmware/BUILD.json`](../firmware/BUILD.json). Release reproduction and prior test records are in [BUILDING-V167.en.md](../firmware/BUILDING-V167.en.md) and [`verification/v167/`](../firmware/verification/v167/): 237 Rust tests, 18 Python tests and ten ARM64/QEMU models.

Unused V160/V162/V163 build and packaging scripts were removed. Reproduce the current release with `firmware/build-V167.sh` and `package-V167.py`; see [the V167 guide](../firmware/BUILDING-V167.en.md). Ordinary source compilation still uses `tools/build-firmware.sh`.

Source synchronization did not download the build environment again or rebuild firmware. The added entry point was checked for shell syntax, help output, and pinned records; this is not a claim of a new successful build or byte-for-byte identity with original binaries. A build records output ELF architecture, maximum GLIBC symbol version, and SHA256.

## Windows SSH ASKPASS

The Robot Console includes `ssh-askpass.exe`; source is [`firmware/scripts/ssh-askpass-windows.c`](../firmware/scripts/ssh-askpass-windows.c). This Windows OpenSSH callback is separate from ARM64 firmware. Rebuild instructions are in the C file header. The Linux console uses the `firmware/console/ssh-askpass` Python file and needs no compilation.

## IMU (STM32)

The independent IMU STM32 firmware uses Arm GNU Toolchain **14.3.Rel1**. The build entry is [`Makefile.feetech`](../firmware/firmware/imu-source/Makefile.feetech), currently **FT6_SYNC15_UART_IRQ_v1**. Prepare STM32 CubeG0 and set `TOOLCHAIN` and `CUBE` as required by the Makefile.

| Dependency | Pinned source version |
| --- | --- |
| STM32 CubeG0 / CMSIS Core | `446ebe396489ca75679caa80887d7257efe92e3d` |
| STM32 G0 device submodule | `f576c24e123edf3332988ecd49512c0f35f85186` |

```bash
make -C firmware/firmware/imu-source -f Makefile.feetech \
  TOOLCHAIN=/path/to/your/toolchain/bin/arm-none-eabi- \
  CUBE=/path/to/your/STM32CubeG0
```

Output is in `firmware/firmware/imu-source/build-feetech-ft6/`. Compilation does not flash the board. For the compiled binary and flashing procedure, see [IMU firmware FT6](../../hardware/IMU-FIRMWARE.en.md).

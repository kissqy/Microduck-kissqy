# 编译源码

日常使用直接下载 Releases 的固件和中控包。修改程序后需要重新编译时，使用下列入口。Windows 用户在 VS Code 的 **WSL / Linux 终端**运行这些命令。

## 1. 一次安装编译环境

以下以 Ubuntu 24.04 / Debian 的 Linux 环境为例。Windows 可在 VS Code 安装微软 **WSL** 扩展，再执行命令面板的 **WSL: Reopen Folder in WSL**。所有后续命令均在仓库根目录 `microduck-hd1910` 执行。

```bash
sudo apt-get update
sudo apt-get install -y build-essential pkg-config libudev-dev python3-venv curl ca-certificates xz-utils binutils dpkg
```

没有 Rust 时，先安装官方 rustup；已有 rustup 则跳过这两行：

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain none
source "$HOME/.cargo/env"
```

安装本次源码使用的固定版本，不要用系统仓库里的旧版 `rustc` 替代：

```bash
rustup toolchain install 1.99.0 --profile minimal --target aarch64-unknown-linux-gnu
python3 -m venv .build/firmware-tools
.build/firmware-tools/bin/python -m pip install cargo-zigbuild==0.23.4 ziglang==0.14.1
```

构建脚本会自动使用这份 Python 环境，不必每次激活。首次构建需要联网下载 Cargo 依赖和两份 ARM64 libudev 开发依赖。构建脚本本身不会调用 `sudo`。

## 2. 检查并编译 Zero 程序

```bash
bash tools/build-firmware.sh --check
bash tools/build-firmware.sh
```

`--check` 只检查工具和依赖记录，不下载、不编译。正式构建执行与 v146 一致的 `cargo zigbuild` 工具链及 `aarch64-unknown-linux-gnu.2.31` 目标，使用 `Cargo.lock` 锁定依赖；这次同时从当前源码构建声音程序和手柄桥。

成功后，文件在 **`.build/firmware/bin/`**：

| 文件 | 用途 |
|---|---|
| `robotd` | 机器人控制服务 |
| `robotctl` | 机器人命令行工具 |
| `padd` | 手柄输入服务 |
| `sounds` | 声音生成程序 |
| `gamesir-xboxd` | GameSir → Xbox 输入桥 |
| `BUILD-LOCAL.json`、`SHA256SUMS` | 本次构建记录与程序校验值 |

这些程序供 ARM64 Linux / Zero 使用。此入口只生成程序，不会连接机器人、安装服务或生成可导入固件 ZIP。运行服务还需要原固件包中的配置、模型、Python 辅助程序和目标平台的 ONNX Runtime。

### 为什么还需要 libudev

`padd` 的手柄库依赖 libudev。宿主机的 `libudev-dev` 用于本机编译阶段；目标依赖则是独立解包到 `.build/firmware/sysroot/arm64` 的 Debian Bullseye ARM64 `libudev-dev`、`libudev1`，均固定为 **247.3-7+deb11u5**。脚本核对 `firmware/verification/native-dependencies146.json` 的固定 URL 和 SHA256，下载后再次校验，再设置 `PKG_CONFIG_SYSROOT_DIR`、`PKG_CONFIG_LIBDIR`，不会把 ARM 库安装进宿主系统。

下载地址失效或 SHA256 不符时构建立刻停止；不要随意换成最新版 libudev 继续构建。单纯编译这五个程序不需要 GStreamer，也不需要设置 `ORT_DYLIB_PATH`。本机运行涉及 ONNX 推理的测试时，才需要本机架构的 ONNX Runtime 1.28.0；机器人运行需要 ARM64 版本。

### 与原发布包的关系

原 v146 发布记录使用 Rust **1.99.0**、cargo-zigbuild **0.23.4**、Zig **0.14.1**，重新编译了 `robotd`、`robotctl`、`padd`；`sounds` 和 `gamesir-xboxd` 沿用前一版二进制。本入口从当前源码重建全部五个程序，**不声称与已发布文件逐字节相同**。

`firmware/BUILD-R17.sh` 和 `firmware/verification/` 保留历史原文。旧 `BUILD-R17.sh` 使用 GNU 交叉链接器且额外指定 `codegen-units=1`，与 v146 的实际发布命令不同；`verification/build_native146.py`、`package146.py` 仍引用当时的临时目录和前一版载荷，不能直接作为新机器的一键构建入口。

本新增入口在整理发布包时只做了 shell 语法、帮助输出及静态核对，没有重新下载工具链或实际编译验证。运行后的脚本会检查输出 ELF 架构、GLIBC 符号上限和 SHA256；这些检查不代表实机测试通过。

## 3. Windows SSH ASKPASS 小程序

原中控已包含 `ssh-askpass.exe`，其源码为 [`firmware/scripts/ssh-askpass-windows.c`](../firmware/scripts/ssh-askpass-windows.c)。它是 OpenSSH 的密码输入回调，源码不存放用户密码。它不属于 ARM64 固件，需要单独编译为 Windows x86_64 程序。

在上述工具安装完成后，从仓库根目录执行以下命令，可把重建结果保存到 `.build/askpass/ssh-askpass.exe`：

```bash
mkdir -p .build/askpass
ZIG_BIN="$(.build/firmware-tools/bin/python -c 'import pathlib,ziglang; print(pathlib.Path(ziglang.__file__).parent / "zig")')"
ZIG_LIB="$(dirname "$ZIG_BIN")/lib"
"$ZIG_BIN" cc -target x86_64-windows-gnu -Os -s -nostdlib \
  -isystem "$ZIG_LIB/libc/include/any-windows-any" \
  -Wl,--entry=start -Wl,--subsystem=windows \
  firmware/scripts/ssh-askpass-windows.c -lkernel32 \
  -o .build/askpass/ssh-askpass.exe
```

Linux 中控使用的 `firmware/console/ssh-askpass` 是 Python 文件，无需编译。ASKPASS 编译命令来自随包 C 源文件头部，本次没有执行重建。

## 4. HAT / IMU 固件是另一套编译入口

源码入口为 [`firmware/firmware/imu-source/Makefile.feetech`](../firmware/firmware/imu-source/Makefile.feetech)，当前版本为 **FT6_SYNC15_UART_IRQ_v1**。它使用 **Arm GNU Toolchain 14.3.Rel1**，不是上面的 Rust / Zig 工具链。

原源码包没有包含 Makefile 默认引用的 `../third_party/STM32CubeG0`。编译前需要另外准备官方 [STM32CubeG0](https://github.com/STMicroelectronics/STM32CubeG0) 的这些固定源码，并将 `CUBE` 指向该目录：

| 依赖 | 固定版本 |
|---|---|
| STM32CubeG0 / CMSIS Core | `446ebe396489ca75679caa80887d7257efe92e3d` |
| STM32G0 设备子模块 | `f576c24e123edf3332988ecd49512c0f35f85186` |

依赖准备完成后：

```bash
make -C firmware/firmware/imu-source -f Makefile.feetech \
  TOOLCHAIN=/你的工具链目录/bin/arm-none-eabi- \
  CUBE=/你的STM32CubeG0目录
```

输出为 `firmware/firmware/imu-source/build-feetech-ft6/imu_to_feetech_ReVA_FT6_SYNC15_UART_IRQ_v1.bin`，另有 ELF、MAP 文件。Makefile 会先运行自带的宿主协议测试；以上入口不执行烧录。本次没有重建 HAT 固件，发布包提供原有已编译文件。

## 参考

- [VS Code 使用 WSL](https://code.visualstudio.com/docs/remote/wsl)
- [Rustup 官方安装说明](https://rust-lang.github.io/rustup/installation/index.html)
- [cargo-zigbuild 0.23.4 官方包说明](https://docs.rs/crate/cargo-zigbuild/0.23.4)
- [Zig 官方下载](https://ziglang.org/download/)
- 随包证据：`firmware/verification/native-build-environment146.json`、`native-dependencies146.json`、`firmware/BUILD.json`。

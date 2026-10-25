**简体中文** | [English](BUILD.en.md) | [Русский](BUILD.ru.md)

# 从源码编译 control.43

日常使用可直接下载系统镜像及 V167 中控，无需编译。本页用于修改源码后重新构建 Zero 程序。当前固件为 **control.43**，已随 V167 中控分发。

Windows 用户在 VS Code 的 WSL / Linux 终端执行以下命令。克隆本仓库后，先进入 `microduck-hd1910` 目录。

## 安装编译环境

```bash
sudo apt-get update
sudo apt-get install -y build-essential pkg-config libudev-dev python3-venv curl ca-certificates xz-utils binutils dpkg
```

没有 rustup 时安装官方 Rust 工具；已有则跳过：

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain none
source "$HOME/.cargo/env"
```

按发布记录安装固定工具链：

```bash
rustup toolchain install 1.99.0 --profile minimal --target aarch64-unknown-linux-gnu
python3 -m venv .build/firmware-tools
.build/firmware-tools/bin/python -m pip install cargo-zigbuild==0.23.4 ziglang==0.15.1
```

## 构建 Zero 程序

```bash
bash tools/build-firmware.sh --check
bash tools/build-firmware.sh
```

`--check` 检查已安装工具和固定依赖记录，不下载或编译。正式构建使用 `Cargo.lock`、Rust **1.99.0**、cargo-zigbuild **0.23.4**、Zig **0.15.1**，目标为 `aarch64-unknown-linux-gnu.2.31`；与 control.43 的记录一致，为 `robotd` 和 `pet-detect` 指定 release codegen-units 为 1。

输出在 **`.build/firmware/bin/`**：

| 文件 | 用途 |
| --- | --- |
| `robotd` | 机器人控制服务 |
| `robotctl` | 机器人命令行工具 |
| `padd` | 手柄输入服务 |
| `sounds` | 声音生成程序 |
| `gamesir-xboxd` | GameSir → Xbox 输入桥 |
| `BUILD-LOCAL.json`、`SHA256SUMS` | 本次构建身份与校验值 |

这些程序供 ARM64 Linux / Zero 使用。构建入口只生成程序，不连接机器人，不安装服务，也不生成可导入的完整固件 ZIP。运行服务仍需对应配置、模型、辅助程序及 ARM64 ONNX Runtime。`mediad` 的源码也在工作区，但上述五程序构建入口不包含它；其 Linux 构建依赖 GStreamer，参考 [工作区开发说明](../firmware/CONTRIBUTING.md)。

### libudev 依赖

手柄程序依赖 libudev。宿主机 `libudev-dev` 用于本机阶段；ARM64 依赖按照 [`build-environment150-libudev-sysroot.json`](../firmware/verification/build-environment150-libudev-sysroot.json) 下载，固定为 Debian Trixie **257.13-1~deb13u1** 的 `libudev-dev` 与 `libudev1`。脚本检查固定地址及 SHA256，解包到 `.build/firmware/sysroot/arm64`，不会将 ARM 库安装到宿主系统。记录虽然保留了原环境建立时的 150 文件名，也是当前交叉构建所用的依赖来源。

### 与交付程序的关系

当前编译身份及原生程序哈希见 [`firmware/BUILD.json`](../firmware/BUILD.json)。V167 发布复现说明与此前测试记录见 [BUILDING-V167.md](../firmware/BUILDING-V167.md) 和 [`verification/v167/`](../firmware/verification/v167/)。测试记录包含 237 项 Rust 测试、18 项 Python 测试及十个 ARM64/QEMU 模型。

旧版 V160/V162/V163 构建与打包脚本已删除，当前完整发布复现使用 `firmware/build-V167.sh` 和 `package-V167.py`，见 [V167 构建指南](../firmware/BUILDING-V167.md)。普通源码编译仍使用本页的 `tools/build-firmware.sh`。

本次同步没有重新下载编译环境或重建固件；新增入口更新已检查 shell 语法、帮助输出及固定记录，不声称重新编译通过或与原程序逐字节相同。运行构建后会记录输出 ELF 架构、GLIBC 符号上限和 SHA256。

## Windows SSH ASKPASS

机器人中控已经包含 `ssh-askpass.exe`；源码为 [`firmware/scripts/ssh-askpass-windows.c`](../firmware/scripts/ssh-askpass-windows.c)。它供 Windows OpenSSH 回调使用，不属于 ARM64 固件。重建命令见该 C 文件头部；Linux 中控使用 `firmware/console/ssh-askpass` Python 文件，无需编译。

## IMU (STM32)

独立 IMU 的 STM32 固件使用 Arm GNU Toolchain **14.3.Rel1**，源码入口为 [`Makefile.feetech`](../firmware/firmware/imu-source/Makefile.feetech)，当前版本为 **FT6_SYNC15_UART_IRQ_v1**。另外准备 STM32CubeG0，并按 Makefile 设置 `TOOLCHAIN` 和 `CUBE`。

| 依赖 | 固定源码版本 |
| --- | --- |
| STM32CubeG0 / CMSIS Core | `446ebe396489ca75679caa80887d7257efe92e3d` |
| STM32G0 设备子模块 | `f576c24e123edf3332988ecd49512c0f35f85186` |

```bash
make -C firmware/firmware/imu-source -f Makefile.feetech \
  TOOLCHAIN=/你的工具链目录/bin/arm-none-eabi- \
  CUBE=/你的STM32CubeG0目录
```

输出在 `firmware/firmware/imu-source/build-feetech-ft6/`，编译不执行烧录。直接下载已编译文件及烧录说明见 [IMU 固件 FT6](../../hardware/IMU-FIRMWARE.md)。

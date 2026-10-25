**简体中文** | [English](BUILDING-V167.en.md) | [Русский](BUILDING-V167.ru.md)

# R17 V167 / control.43 构建说明

当前中控为 `1.0.167`，机器人固件为 `1fa8438-feetech-ft6-control.43`，官方系统基线为 `0.15.1`。

**更新：修复鸭身抖动的问题。**

## 源码与成品

本目录保存源码、配置、测试、许可证和界面资源。完整中控 ZIP 在仓库根目录 `release-assets/`；独立固件保留在 `console/updates/`，供中控原有安装流程直接使用。

编译程序、ONNX 动态库及打包目录中的重复模型不再保存第二份。构建前执行：

```bash
python3 prepare-V167.py
```

脚本核对固定 SHA256，从已有固件载荷恢复需要的资源；这些生成文件已加入 Git 忽略清单。`--check` 只检查归档校验值；`--download` 可下载缺失的固定归档并核对校验值。

V164 ZIP 仅作为复现构建基线保留一份，位置为 `../../release-assets/build-baselines/Microduck-Console-R17-V164.zip`。`package-V167.py` 和验证脚本已使用这个位置。

## 编译

环境需要 Linux/WSL、Rust 1.99、AArch64 GNU target、cargo-zigbuild 0.23.4、Zig 0.15.1、Python 3、pkg-config 和 libudev 开发库。普通源码编译见 [BUILD.md](../docs/BUILD.md)。原发布复现还需要主机 ONNX Runtime 1.28.0、QEMU 和 ARM64 用户态环境。

```bash
export ORT_DYLIB_PATH=/absolute/path/to/host/libonnxruntime.so.1.28.0
export QEMU_AARCH64=/absolute/path/to/qemu-aarch64
export ARM64_RUNTIME_PREFIX=/absolute/path/to/arm64-userland
bash build-V167.sh
```

脚本恢复资源、检查源码、执行原发布测试、编译 robotd、验证随包模型，再按原 V164 基线生成 V167 完整安装包。生成资源与构建输出不加入 Git。

## 记录

`verification/v167/` 保存此前 V167 编译阶段的记录：237 项 Rust 测试、18 项 Python 测试，以及 10 个 ARM64/QEMU 模型加载与首次推理。它们不是本次目录整理重新运行的结果。本次整理核对源码、发布包及恢复资源的字节和校验值，没有重新编译固件或连接实机。

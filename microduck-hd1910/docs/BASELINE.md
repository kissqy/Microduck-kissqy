**简体中文** | [English](BASELINE.en.md) | [Русский](BASELINE.ru.md)

# 发布基线与验证范围

当前公开版本为 **R17 V167 / control.43 + Training R1.5.27**，官方基线为 **0.15.1**。身份与哈希见 [PUBLICATION-MANIFEST.json](../PUBLICATION-MANIFEST.json)。

**V167 更新：修复鸭身抖动的问题。**

| 组件 | 当前版本 |
| --- | --- |
| 官方固件 | daemon-v0.15.1，`1fa84386f07884e27866411bc1ba166977bced95` |
| HD1910 固件 | `1fa8438-feetech-ft6-control.43`，API40 |
| 机器人中控 | R17 V167，`1.0.167` |
| 训练中控 | R1.5.27；14 类动作、35 种配方 |
| 训练引擎 | microduck_rl `8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec` |
| 系统镜像 | Public Image R1，首次配网 R5；镜像仍预装 control.40 |

## 文件位置

- `firmware/`：固件源码、安装脚本、模型、测试和许可证。
- `firmware/console/`：V167 中控源码及随包固件载荷。
- `training-console/`：R1.5.27 训练中控，保持原发布内容。
- `release-assets/`：V167 中控和 R1.5.27 训练中控完整 ZIP。
- `release-assets/build-baselines/`：一份 V164 ZIP，仅用于复现构建基线。
- 系统镜像：已有 `public-image-r1` Release；刷卡后通过 V167 中控安装随包固件，升级到 control.43。

源码目录不再内嵌旧版完整 ZIP，也不保存已编译程序、ONNX 动态库及打包模型的第二份二进制。构建所需资源由 `firmware/prepare-V167.py` 校验并恢复，生成文件已加入 Git 忽略规则。说明见 [V167 构建指南](../firmware/BUILDING-V167.md)。

## 验证范围

公开镜像此前已通过重刷卡、首次配网、SSH、机器人通信和 R17 识别。作者提供的当前实机运行标识为 `1fa8438-feetech-ft6-control.43`。

`firmware/verification/v167/` 保存此前编译阶段的 237 项 Rust 测试、18 项 Python 测试及十个 ARM64/QEMU 模型加载与首次推理记录。本次整理只核对交付包、源码、资源恢复和校验清单，没有重新编译或操作机器人。

## Known-Good 与下一步

当前软件发布参考为 **0.15.1 + R17 V167 / control.43 + Training R1.5.27**；系统镜像仍使用已重刷验证的 **Public Image R1**，不同动作的验收范围按各自实测记录执行。

**下一步唯一主任务：按公开下载复现 V167 安装与本机标定。** 一次只验证一个变量。

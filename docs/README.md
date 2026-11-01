**简体中文** | [English](README.en.md)

# Microduck 飞特版复刻教程与说明文档

首页、使用指南、硬件记录与技术说明的中英文入口。当前软件界面仍为中文；英文指南保留必要的中文按钮名称。原始测试日志、源代码与正式许可保持原文。

## 从预算到第一次行走

正常复刻只需前三步，使用配套现成动作模型和机器人中控，**无需训练**。第④项为可选进阶，仅供想自训新动作或学习训练流程时探索。按当前进度进入：

| 步骤 | 直接入口 |
| --- | --- |
| **01 · 预算与采购** | [方案总额与采购入口](https://kissqy.github.io/Microduck-kissqy/build/budget.html) · [详细采购清单](https://kissqy.github.io/Microduck-kissqy/build/shopping.html) |
| **02 · 我要怎么装？** | [分步装配、接线与 3D 参考](https://kissqy.github.io/Microduck-kissqy/build/assembly.html) |
| **03 · 我要让鸭子走起来** | [刷机、配网、标定、HOME 与行走](https://kissqy.github.io/Microduck-kissqy/build/start.html) |
| **04 · 进阶玩法（可选）** | [仅在想自训新动作或学习训练流程时进入](https://kissqy.github.io/Microduck-kissqy/build/advanced.html) |

[新手路线总入口](https://kissqy.github.io/Microduck-kissqy/build/) · [中控图文使用教程](https://kissqy.github.io/Microduck-kissqy/console-guide.html)

采购参考已含忆捷 32GB TF 卡 ¥39.90 与[山泽双头高速读卡器（SD／TF 卡同读）](https://3.cn/393kj-8k?jkl=@I2cIJ7xKJzv@)1 个 ¥22.90；成品板路线基础小计 ¥2936.62；[缝合怪版整套代打](../hardware/3d-print-frankenduck/README.md)标价 ¥199，合计 **¥3135.62**。已含 HUB ¥69，电池接入配件与运费另计。已有读卡器可复用；HUB 已带总电源缓冲电容，用于缓冲舵机瞬时负载，防止瞬时压降导致 ZERO 重启，无需单独购买。

**HAT、IMU、HUB 为三块独立板卡，均在[同一商品页](https://item.taobao.com/item.htm?id=1095121548583)选择对应款式。HUB ¥69 已含总电源缓冲电容，用于缓冲舵机瞬时负载，防止瞬时压降导致 ZERO 重启。**

电池取电可使用香蕉板（暂未上架），也可以使用仓库配套电池仓，加 M2.6 螺丝作为取电触点；取出的正极接 HUB 电源输入 VIN（+），负极接 GND（−），按实板丝印核对极性。

## Start here / 入门

| 说明 | 中文 | English |
| --- | --- | --- |
| 🚀 Microduck HD1910 从零复刻 / Complete replica build guide | [中文](MICRODUCK-BUILD-GUIDE.md) | [English](MICRODUCK-BUILD-GUIDE.en.md) |
| ❓ 刷机、标定、IMU、断网与重启 / FAQ | [中文](MICRODUCK-FAQ.md) | [English](MICRODUCK-FAQ.en.md) |
| 🔧 装机与使用注意事项 / Assembly: 5 GHz Wi-Fi & 1000 µF input capacitor | [中文](ASSEMBLY-NOTES.md) | [English](ASSEMBLY-NOTES.en.md) |
| 仓库目录与重复资源 | [中文](REPOSITORY-LAYOUT.md) | [English](REPOSITORY-LAYOUT.en.md) |
| 飞特已编译固件 control.43 — 下载与安装 | [中文](../release-assets/README.md) | [English](../release-assets/README.en.md) |
| 🎬 看看鸭鸭的真实表现（7 段视频） | [中文](../README.md) | [English](../README.en.md) |
| 🌱 作者如何从新手进阶 — 学习时间线与完整提问回顾 | [中文](AUTHOR-JOURNEY.md) | [English](AUTHOR-JOURNEY.en.md) |
| START-HERE | [中文](../START-HERE.txt) | [English](../START-HERE.en.md) |
| 🦆 Microduck 一键系统镜像 R1 | [中文](releases/public-image-r1.md) | [English](releases/public-image-r1.en.md) |
| Microduck HD1910 | [中文](../microduck-hd1910/README.md) | [English](../microduck-hd1910/README.en.md) |
| 发布基线与验证范围 | [中文](../microduck-hd1910/docs/BASELINE.md) | [English](../microduck-hd1910/docs/BASELINE.en.md) |
| V167 构建与源码资源准备 | [中文](../microduck-hd1910/firmware/BUILDING-V167.md) | [English](../microduck-hd1910/firmware/BUILDING-V167.en.md) |
| 从源码编译 control.43 | [中文](../microduck-hd1910/docs/BUILD.md) | [English](../microduck-hd1910/docs/BUILD.en.md) |
| 当前仓库的发布方式 | [中文](../microduck-hd1910/docs/PUBLISH.md) | [English](../microduck-hd1910/docs/PUBLISH.en.md) |
| 第三方来源与授权范围 | [中文](../microduck-hd1910/docs/THIRD-PARTY.md) | [English](../microduck-hd1910/docs/THIRD-PARTY.en.md) |

## Hardware / 硬件

| 说明 | 中文 | English |
| --- | --- | --- |
| 鸭子全套打印件与摆盘 · 缝合怪版 | [中文](../hardware/3d-print-frankenduck/README.md) | [English](../hardware/3d-print-frankenduck/README.en.md) |
| HAT 制作时间线 | [中文](../hardware/HAT-TIMELINE.md) | [English](../hardware/HAT-TIMELINE.en.md) |
| IMU 制作全过程视频与时间线 | [中文](../hardware/IMU-TIMELINE.md) | [English](../hardware/IMU-TIMELINE.en.md) |
| HAT、IMU 与 HUB 板卡 | [中文](../hardware/README.md) | [English](../hardware/README.en.md) |
| HAT / IMU AMP2.0 版：HP1.25 音频与新增 LED | [中文](../hardware/AMP2.0-VERSION.md) | [English](../hardware/AMP2.0-VERSION.en.md) |
| IMU 固件 FT6 — 下载、接线、烧录与检查 | [中文](../hardware/IMU-FIRMWARE.md) | [English](../hardware/IMU-FIRMWARE.en.md) |
| 当前 IMU FT6：协议与兼容 | [中文](../microduck-hd1910/firmware/firmware/imu-source/README_FT6_SYNC15.md) | [English](../microduck-hd1910/firmware/firmware/imu-source/README_FT6_SYNC15.en.md) |

## Robot Console / 机器人中控

| 说明 | 中文 | English |
| --- | --- | --- |
| PUBLICATION-NOTE | [中文](../microduck-hd1910/firmware/console/PUBLICATION-NOTE.txt) | [English](../microduck-hd1910/firmware/console/PUBLICATION-NOTE.en.md) |
| 🎮 Microduck 机器人中控 · R17 V167 | [中文](../microduck-hd1910/firmware/console/README.md) | [English](../microduck-hd1910/firmware/console/README.en.md) |
| Microduck R17 V167 / control.43 使用说明 | [中文](../microduck-hd1910/firmware/console/README.zh-CN.md) | [English](../microduck-hd1910/firmware/console/USER-GUIDE.en.md) |
| 本次音源与手柄来源 | [中文](../microduck-hd1910/firmware/console/THIRD_PARTY_NOTICES.md) | [English](../microduck-hd1910/firmware/console/THIRD_PARTY_NOTICES.en.md) |
| R17 中控参数来源 | [中文](../microduck-hd1910/firmware/console/docs/joint-scale-design148.md) | [English](../microduck-hd1910/firmware/console/docs/joint-scale-design148.en.md) |
| R147 验证记录 | [中文](../microduck-hd1910/firmware/console/verification/README.md) | [English](../microduck-hd1910/firmware/console/verification/README.en.md) |

## Advanced / 进阶：训练自己的动作

**正常复刻与日常使用无需训练。** 只有想自己训练新动作或学习训练流程时，再进入可选的进阶玩法。

| 说明 | 中文 | English |
| --- | --- | --- |
| PUBLICATION-NOTE | [中文](../microduck-hd1910/training-console/PUBLICATION-NOTE.txt) | [English](../microduck-hd1910/training-console/PUBLICATION-NOTE.en.md) |
| 🧠 Microduck Training Studio · R1.5.27 | [中文](../microduck-hd1910/training-console/README.md) | [English](../microduck-hd1910/training-console/README.en.md) |
| Microduck Training Studio R1.5.27 | [中文](../microduck-hd1910/training-console/README.zh-CN.md) | [English](../microduck-hd1910/training-console/USER-GUIDE.en.md) |
| 飞特舵机、官方配置与联合训练核对 | [中文](../microduck-hd1910/training-console/docs/Servo-training-audit.zh-CN.md) | [English](../microduck-hd1910/training-console/docs/Servo-training-audit.en.md) |
| 11000 轮倒地老师：翻身补课方案 | [中文](../microduck-hd1910/training-console/docs/StandUp-11000-rollover-plan.zh-CN.md) | [English](../microduck-hd1910/training-console/docs/StandUp-11000-rollover-plan.en.md) |
| R1.5.15 远程训练增量验证 | [中文](../microduck-hd1910/training-console/docs/Verification.md) | [English](../microduck-hd1910/training-console/docs/Verification.en.md) |
| R1.5.17 — 倒地老师评估与翻身检查 | [中文](../microduck-hd1910/training-console/docs/Version-history.zh-CN.md) | [English](../microduck-hd1910/training-console/docs/Version-history.en.md) |
| 官方动作逐任务参数核验（2026-10-07） | [中文](../microduck-hd1910/training-console/docs/audit-0151/official-task-parameter-audit.zh-CN.md) | [English](../microduck-hd1910/training-console/docs/audit-0151/official-task-parameter-audit.en.md) |
| 官方轮滑六族参数审计（2026-10-07） | [中文](../microduck-hd1910/training-console/docs/audit-0151/roller-audit/official-roller-audit.zh-CN.md) | [English](../microduck-hd1910/training-console/docs/audit-0151/roller-audit/official-roller-audit.en.md) |

## Firmware and models / 固件与模型

| 说明 | 中文 | English |
| --- | --- | --- |
| OFFICIAL-CHANGES.zh-CN | [中文](../microduck-hd1910/firmware/OFFICIAL-CHANGES.zh-CN.md) | [English](../microduck-hd1910/firmware/OFFICIAL-CHANGES.en.md) |
| OFFICIAL-GAMEPAD.zh-CN | [中文](../microduck-hd1910/firmware/OFFICIAL-GAMEPAD.zh-CN.md) | [English](../microduck-hd1910/firmware/OFFICIAL-GAMEPAD.en.md) |
| R17-CHANGES.zh-CN | [中文](../microduck-hd1910/firmware/R17-CHANGES.zh-CN.md) | [English](../microduck-hd1910/firmware/R17-CHANGES.en.md) |
| Microduck control.43 固件与 R17 V167 中控 | [中文](../microduck-hd1910/firmware/README-R17.zh-CN.md) | [English](../microduck-hd1910/firmware/README-R17.en.md) |
| It does things | [中文](../microduck-hd1910/firmware/README.md) | [English](../microduck-hd1910/firmware/README.en.md) |
| SELF-TRAINED.zh-CN | [中文](../microduck-hd1910/firmware/SELF-TRAINED.zh-CN.md) | [English](../microduck-hd1910/firmware/SELF-TRAINED.en.md) |
| 当前 R17 v1.0.157-Fix9 / control.36 | [中文](../microduck-hd1910/firmware/docs/design/r17-connection-design.md) | [English](../microduck-hd1910/firmware/docs/design/r17-connection-design.en.md) |
| R17 中控参数来源 | [中文](../microduck-hd1910/firmware/docs/design/r17-settings-design.md) | [English](../microduck-hd1910/firmware/docs/design/r17-settings-design.en.md) |
| WebRTC: sessions, signalling, and the control channel | [中文](../microduck-hd1910/firmware/docs/design/remote-webrtc.md) | [English](../microduck-hd1910/firmware/docs/design/remote-webrtc.en.md) |
| 当前 R17 v1.0.157-Fix6 / control.36 | [中文](../microduck-hd1910/firmware/docs/design/robotd-design.md) | [English](../microduck-hd1910/firmware/docs/design/robotd-design.en.md) |
| Microduck R17 V167 / control.43 随包固件 | [中文](../microduck-hd1910/firmware/packaging/README.zh-CN.md) | [English](../microduck-hd1910/firmware/packaging/README.en.md) |
| HD1910 自训模型 · 目标固件 0.15.1 · 1cbf8730eadd75a5704332c9f3c10f60 | [中文](../microduck-hd1910/firmware/packaging/models/1cbf8730eadd75a5704332c9f3c10f60/使用说明.md) | [English](../microduck-hd1910/firmware/packaging/models/1cbf8730eadd75a5704332c9f3c10f60/README.en.md) |
| HD1910 自训模型 · 目标固件 0.15.1 · 59e15d7b04d0c40e9b11b8a70bdecae6 | [中文](../microduck-hd1910/firmware/packaging/models/59e15d7b04d0c40e9b11b8a70bdecae6/使用说明.md) | [English](../microduck-hd1910/firmware/packaging/models/59e15d7b04d0c40e9b11b8a70bdecae6/README.en.md) |
| HD1910 自训模型 · 目标固件 0.15.1 · 67ad09d82f4865d222a7ae06f250cf9f | [中文](../microduck-hd1910/firmware/packaging/models/67ad09d82f4865d222a7ae06f250cf9f/使用说明.md) | [English](../microduck-hd1910/firmware/packaging/models/67ad09d82f4865d222a7ae06f250cf9f/README.en.md) |
| HD1910 自训模型 · 目标固件 0.15.1 · a481d9f211f31d9476ab1a319fe362a2 | [中文](../microduck-hd1910/firmware/packaging/models/a481d9f211f31d9476ab1a319fe362a2/使用说明.md) | [English](../microduck-hd1910/firmware/packaging/models/a481d9f211f31d9476ab1a319fe362a2/README.en.md) |
| HD1910 自训模型 · 目标固件 0.15.1 · b14e3a8b56ddbb8d2d831e727774a168 | [中文](../microduck-hd1910/firmware/packaging/models/b14e3a8b56ddbb8d2d831e727774a168/使用说明.md) | [English](../microduck-hd1910/firmware/packaging/models/b14e3a8b56ddbb8d2d831e727774a168/README.en.md) |
| HD1910 自训模型 · 目标固件 0.15.1 · ee0376c927044cdece056ba1d3e6eac7 | [中文](../microduck-hd1910/firmware/packaging/models/ee0376c927044cdece056ba1d3e6eac7/使用说明.md) | [English](../microduck-hd1910/firmware/packaging/models/ee0376c927044cdece056ba1d3e6eac7/README.en.md) |
| HD1910 自训模型 · 目标固件 0.15.1 · standup | [中文](../microduck-hd1910/firmware/packaging/roller/standup/使用说明.md) | [English](../microduck-hd1910/firmware/packaging/roller/standup/README.en.md) |
| README | [中文](../microduck-hd1910/firmware/policies/README.md) | [English](../microduck-hd1910/firmware/policies/README.en.md) |
| HD1910 自训模型 · 目标固件 0.15.1 · ground_pick | [中文](../microduck-hd1910/firmware/policies/ground_pick/使用说明.md) | [English](../microduck-hd1910/firmware/policies/ground_pick/README.en.md) |
| HD1910 自训模型 · 目标固件 0.15.1 · kick_left | [中文](../microduck-hd1910/firmware/policies/kick_left/使用说明.md) | [English](../microduck-hd1910/firmware/policies/kick_left/README.en.md) |
| HD1910 自训模型 · 目标固件 0.15.1 · roulade | [中文](../microduck-hd1910/firmware/policies/roulade/使用说明.md) | [English](../microduck-hd1910/firmware/policies/roulade/README.en.md) |
| HD1910 自训模型 · 目标固件 0.15.1 · stand | [中文](../microduck-hd1910/firmware/policies/stand/使用说明.md) | [English](../microduck-hd1910/firmware/policies/stand/README.en.md) |
| HD1910 自训模型 · 目标固件 0.15.1 · walk | [中文](../microduck-hd1910/firmware/policies/walk/使用说明.md) | [English](../microduck-hd1910/firmware/policies/walk/README.en.md) |
| HD1910 自训模型 · 目标固件 0.15.1 · walk-teacher14000 | [中文](../microduck-hd1910/firmware/test-data/walk-teacher14000/使用说明.md) | [English](../microduck-hd1910/firmware/test-data/walk-teacher14000/README.en.md) |
| v153 验证记录 | [中文](../microduck-hd1910/firmware/verification/README153.md) | [English](../microduck-hd1910/firmware/verification/README153.en.md) |
| 官方滑轮起身路由核对 | [中文](../microduck-hd1910/firmware/verification/v162/official-roller-route.md) | [English](../microduck-hd1910/firmware/verification/v162/official-roller-route.en.md) |

## 原有英文技术文档

- [Firmware architecture and design](../microduck-hd1910/firmware/docs/README.md)
- [Firmware development](../microduck-hd1910/firmware/CONTRIBUTING.md)
- [Training tests](../microduck-hd1910/training-console/tests/README.md)
- [Licenses and sources](../microduck-hd1910/training-console/NOTICE.md)

[🦆 项目首页](../README.md)

## 许可与原创归属

- [软件与自训模型：原创归属、个人使用与商业授权](../microduck-hd1910/docs/SOFTWARE-MODEL-RIGHTS.md) · [English](../microduck-hd1910/docs/SOFTWARE-MODEL-RIGHTS.en.md)
- [逐模型来源：十个随包动作、六份源码权重及历史样本](../microduck-hd1910/docs/MODEL-PROVENANCE.md) · [English](../microduck-hd1910/docs/MODEL-PROVENANCE.en.md)
- [分项许可索引](../LICENSE) · [第三方来源](../microduck-hd1910/docs/THIRD-PARTY.md)

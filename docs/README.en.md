[简体中文](README.md) | **English**

# Microduck replica documentation

English editions of the homepage, user guides, hardware records, and technical notes. Current application interfaces remain Chinese; English guides include button labels for reference. Raw test logs, source code, and formal licenses retain their original text.

## Current downloads · November 13, 2026

Default setup: **System Image R2 + Console Studio V260 / control.102, Wi-Fi setup R10**. [R2 image](https://github.com/kissqy/Microduck-kissqy/releases/download/console-studio-v260/microduck-kissqy-zero3w-R2.img.xz) · [release downloads](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v260) · [runtime and source guide](https://github.com/kissqy/Microduck-kissqy/blob/main/versions/v260/README.md) · [independent V260 source](https://github.com/kissqy/Microduck-kissqy/tree/main/versions/v260).

Both Robot Console versions are grouped on main; no branch switching is needed.

| Version directory | Firmware and image | Entry |
| --- | --- | --- |
| V260 · current | control.102 · R2 / R10 | [V260 source and downloads](../versions/v260/) |
| V167 · historical | control.43 · R1 includes control.40 | [V167 source and downloads](../versions/v167/README.en.md) |

The original root source and package paths remain for compatibility. Training Studio R1.5.27 is independent. This directory organization does not add real-robot Known-Good results.

## From budget to first walking

Normal replication takes the first three steps and uses the supplied motion models and Robot Console. **No training is required.** Entry ④ is optional, only for training new movements or learning the process. The guided pages below are in **Chinese**.

| Step | Direct entry |
| --- | --- |
| 01 · Budget and shopping | [Scheme totals and purchasing entry](https://kissqy.github.io/Microduck-kissqy/build/budget.html) · [Detailed checklist](https://kissqy.github.io/Microduck-kissqy/build/shopping.html) |
| 02 · Assembly and wiring | [Assembly steps, wiring and 3D reference](https://kissqy.github.io/Microduck-kissqy/build/assembly.html) |
| 03 · Make it walk | [Ready-made models: imaging, network, calibration and walking](https://kissqy.github.io/Microduck-kissqy/build/start.html) |
| 04 · Advanced play (optional) | [Only for training new movements or learning the training process](https://kissqy.github.io/Microduck-kissqy/build/advanced.html) |

[Build-route overview (Chinese)](https://kissqy.github.io/Microduck-kissqy/build/) · [Illustrated console guide (Chinese)](https://kissqy.github.io/Microduck-kissqy/console-guide.html)

The priced purchase reference includes an EAGET 32GB microSD card at CNY 39.90 and one [SAMZHE dual-head high-speed card reader with simultaneous SD / TF card reading](https://3.cn/393kj-8k?jkl=@I2cIJ7xKJzv@) at CNY 22.90. The assembled-board base reference subtotal is CNY 2937.80. See the [FrankenDuck printing improvements and instructions](../hardware/3d-print-frankenduck/README.en.md); printing costs are additional. The HUB is included at CNY 69; battery-connection parts and shipping are extra. Reuse an existing card reader if available. The HUB includes the main-power buffer capacitor; no separate purchase is needed.

**HAT, IMU and HUB are three separate boards. Select each board on the [same product page](https://item.taobao.com/item.htm?id=1095121548583). The HUB costs CNY 69 and includes the main-power buffer capacitor to buffer transient servo loads and help prevent ZERO restarts caused by supply voltage dips.**

**All HUB V3 connectors use AMP2.0 and matching premade cables. The matching banana power board also uses AMP2.0; it is not yet listed for sale and is expected around November 16, 2026. With the assembled boards, cables and banana board in hand, assembly can use plug-in connections without soldering.**

Legacy power reference: the repository's battery holder can use M2.6 screws as power contacts. Connect positive to the legacy HUB's VIN (+) and negative to GND (−), following its markings. XH2.54 connectors and soldered leads belong to the legacy instructions; follow the V3 board's connectors and markings for V3.

## Start here / 入门

| Guide | 中文 | English |
| --- | --- | --- |
| 🚀 Microduck HD1910 从零复刻 / Complete replica build guide | [中文](MICRODUCK-BUILD-GUIDE.md) | [English](MICRODUCK-BUILD-GUIDE.en.md) |
| ❓ 刷机、标定、IMU、断网与重启 / FAQ | [中文](MICRODUCK-FAQ.md) | [English](MICRODUCK-FAQ.en.md) |
| 🔧 装机与使用注意事项 / Assembly: 5 GHz Wi-Fi & 1000 µF input capacitor | [中文](ASSEMBLY-NOTES.md) | [English](ASSEMBLY-NOTES.en.md) |
| Repository layout and repeated resources | [中文](REPOSITORY-LAYOUT.md) | [English](REPOSITORY-LAYOUT.en.md) |
| Historical V167 / control.43 downloads and installation | [中文](../versions/v167/release-assets/README.md) | [English](../versions/v167/release-assets/README.en.md) |
| 🎬 See the duck in action — 7 real-robot videos | [中文](../README.md) | [English](../README.en.md) |
| 🌱 The author's learning journey — timeline and complete question recap | [中文](AUTHOR-JOURNEY.md) | [English](AUTHOR-JOURNEY.en.md) |
| Current public Microduck release | [中文](../START-HERE.txt) | [English](../START-HERE.en.md) |
| Historical: Microduck integrated system image R1 | [中文](releases/public-image-r1.md) | [English](releases/public-image-r1.en.md) |
| Microduck HD1910 | [中文](../microduck-hd1910/README.md) | [English](../microduck-hd1910/README.en.md) |
| Release baseline and validation scope | [中文](../microduck-hd1910/docs/BASELINE.md) | [English](../microduck-hd1910/docs/BASELINE.en.md) |
| V167 build and source preparation | [中文](../versions/v167/microduck-hd1910/firmware/BUILDING-V167.md) | [English](../versions/v167/microduck-hd1910/firmware/BUILDING-V167.en.md) |
| Build control.43 from source | [中文](../microduck-hd1910/docs/BUILD.md) | [English](../microduck-hd1910/docs/BUILD.en.md) |
| Publishing this repository | [中文](../microduck-hd1910/docs/PUBLISH.md) | [English](../microduck-hd1910/docs/PUBLISH.en.md) |
| Third-party sources and licensing scope | [中文](../microduck-hd1910/docs/THIRD-PARTY.md) | [English](../microduck-hd1910/docs/THIRD-PARTY.en.md) |

## Hardware / 硬件

**[MakerWorld model and print profile](https://makerworld.com.cn/zh/models/3258815-microduck-kissqykai-yuan-feng-he-guai-ban#profileId-3849553)**

| Guide | 中文 | English |
| --- | --- | --- |
| Complete printing set and plates · FrankenDuck | [中文](../hardware/3d-print-frankenduck/README.md) | [English](../hardware/3d-print-frankenduck/README.en.md) |
| HAT build timeline | [中文](../hardware/HAT-TIMELINE.md) | [English](../hardware/HAT-TIMELINE.en.md) |
| IMU full build video and timeline | [中文](../hardware/IMU-TIMELINE.md) | [English](../hardware/IMU-TIMELINE.en.md) |
| HAT, IMU and HUB boards | [中文](../hardware/README.md) | [English](../hardware/README.en.md) |
| HUB V3 with all AMP2.0 connectors | [EasyEDA Pro 工程](../hardware/ProPrj_DXL_HUB_V3_2026-11-14.epro2) | [PCB project](../hardware/ProPrj_DXL_HUB_V3_2026-11-14.epro2) |
| HAT / IMU AMP2.0 variant: HP1.25 audio and added LED | [中文](../hardware/AMP2.0-VERSION.md) | [English](../hardware/AMP2.0-VERSION.en.md) |
| IMU firmware FT6 — download, wiring, flash, and checks | [中文](../hardware/IMU-FIRMWARE.md) | [English](../hardware/IMU-FIRMWARE.en.md) |
| Current IMU FT6: protocol and compatibility | [中文](../versions/v167/microduck-hd1910/firmware/firmware/imu-source/README_FT6_SYNC15.md) | [English](../versions/v167/microduck-hd1910/firmware/firmware/imu-source/README_FT6_SYNC15.en.md) |

## Robot Console / 机器人中控

Current V260: [download and package guide](https://github.com/kissqy/Microduck-kissqy/blob/main/versions/v260/README.md) · [console source](https://github.com/kissqy/Microduck-kissqy/tree/main/versions/v260/console). The table below documents the retained V167 line.

| Guide | 中文 | English |
| --- | --- | --- |
| Microduck Robot Console R17 V167 publication note | [中文](../versions/v167/microduck-hd1910/firmware/console/PUBLICATION-NOTE.txt) | [English](../versions/v167/microduck-hd1910/firmware/console/PUBLICATION-NOTE.en.md) |
| 🎮 Microduck Robot Console · R17 V167 | [中文](../versions/v167/microduck-hd1910/firmware/console/README.md) | [English](../versions/v167/microduck-hd1910/firmware/console/README.en.md) |
| Microduck R17 V167 / control.43 user guide | [中文](../versions/v167/microduck-hd1910/firmware/console/README.zh-CN.md) | [English](../versions/v167/microduck-hd1910/firmware/console/USER-GUIDE.en.md) |
| Sound and gamepad sources | [中文](../versions/v167/microduck-hd1910/firmware/console/THIRD_PARTY_NOTICES.md) | [English](../versions/v167/microduck-hd1910/firmware/console/THIRD_PARTY_NOTICES.en.md) |
| R17 console parameter provenance — v148 design record | [中文](../versions/v167/microduck-hd1910/firmware/console/docs/joint-scale-design148.md) | [English](../versions/v167/microduck-hd1910/firmware/console/docs/joint-scale-design148.en.md) |
| R147 verification records | [中文](../versions/v167/microduck-hd1910/firmware/console/verification/README.md) | [English](../versions/v167/microduck-hd1910/firmware/console/verification/README.en.md) |

## Advanced / 进阶：训练自己的动作

Training Studio is optional after first walking. Everyday operation uses the released models and Robot Console.

| Guide | 中文 | English |
| --- | --- | --- |
| Microduck Training Studio R1.5.27 publication note | [中文](../microduck-hd1910/training-console/PUBLICATION-NOTE.txt) | [English](../microduck-hd1910/training-console/PUBLICATION-NOTE.en.md) |
| 🧠 Microduck Training Studio · R1.5.27 | [中文](../microduck-hd1910/training-console/README.md) | [English](../microduck-hd1910/training-console/README.en.md) |
| Microduck Training Studio R1.5.27 | [中文](../microduck-hd1910/training-console/README.zh-CN.md) | [English](../microduck-hd1910/training-console/USER-GUIDE.en.md) |
| Feetech servos, upstream configuration, and joint-training review | [中文](../microduck-hd1910/training-console/docs/Servo-training-audit.zh-CN.md) | [English](../microduck-hd1910/training-console/docs/Servo-training-audit.en.md) |
| 11000-iteration recovery teacher: rollover curriculum proposal | [中文](../microduck-hd1910/training-console/docs/StandUp-11000-rollover-plan.zh-CN.md) | [English](../microduck-hd1910/training-console/docs/StandUp-11000-rollover-plan.en.md) |
| R1.5.15 remote-training verification record | [中文](../microduck-hd1910/training-console/docs/Verification.md) | [English](../microduck-hd1910/training-console/docs/Verification.en.md) |
| Training Studio version history | [中文](../microduck-hd1910/training-console/docs/Version-history.zh-CN.md) | [English](../microduck-hd1910/training-console/docs/Version-history.en.md) |
| Official per-task parameter audit (October 7, 2026) | [中文](../microduck-hd1910/training-console/docs/audit-0151/official-task-parameter-audit.zh-CN.md) | [English](../microduck-hd1910/training-console/docs/audit-0151/official-task-parameter-audit.en.md) |
| Official six-family roller parameter audit (October 7, 2026) | [中文](../microduck-hd1910/training-console/docs/audit-0151/roller-audit/official-roller-audit.zh-CN.md) | [English](../microduck-hd1910/training-console/docs/audit-0151/roller-audit/official-roller-audit.en.md) |

## Firmware and models / 固件与模型

Current control.102: [firmware source](https://github.com/kissqy/Microduck-kissqy/tree/main/versions/v260/firmware) · [release guide](https://github.com/kissqy/Microduck-kissqy/blob/main/versions/v260/README.md). The table below retains historical firmware and model records.

| Guide | 中文 | English |
| --- | --- | --- |
| R17 v1.0.137 / official 0.15.1 changes | [中文](../versions/v167/microduck-hd1910/firmware/OFFICIAL-CHANGES.zh-CN.md) | [English](../versions/v167/microduck-hd1910/firmware/OFFICIAL-CHANGES.en.md) |
| R17 v1.0.97 / official 0.15.1 gamepad | [中文](../versions/v167/microduck-hd1910/firmware/OFFICIAL-GAMEPAD.zh-CN.md) | [English](../versions/v167/microduck-hd1910/firmware/OFFICIAL-GAMEPAD.en.md) |
| R17 modification history | [中文](../versions/v167/microduck-hd1910/firmware/R17-CHANGES.zh-CN.md) | [English](../versions/v167/microduck-hd1910/firmware/R17-CHANGES.en.md) |
| Microduck control.43 firmware and R17 V167 console | [中文](../versions/v167/microduck-hd1910/firmware/README-R17.zh-CN.md) | [English](../versions/v167/microduck-hd1910/firmware/README-R17.en.md) |
| It does things | [中文](../versions/v167/microduck-hd1910/firmware/README.md) | [English](../versions/v167/microduck-hd1910/firmware/README.en.md) |
| R17 v1.0.137 / official 0.15.1 self-trained models | [中文](../versions/v167/microduck-hd1910/firmware/SELF-TRAINED.zh-CN.md) | [English](../versions/v167/microduck-hd1910/firmware/SELF-TRAINED.en.md) |
| R17 v1.0.157-Fix 9 / control.36 baseline | [中文](../versions/v167/microduck-hd1910/firmware/docs/design/r17-connection-design.md) | [English](../versions/v167/microduck-hd1910/firmware/docs/design/r17-connection-design.en.md) |
| R17 console parameter provenance | [中文](../versions/v167/microduck-hd1910/firmware/docs/design/r17-settings-design.md) | [English](../versions/v167/microduck-hd1910/firmware/docs/design/r17-settings-design.en.md) |
| WebRTC: sessions, signalling, and the control channel | [中文](../versions/v167/microduck-hd1910/firmware/docs/design/remote-webrtc.md) | [English](../versions/v167/microduck-hd1910/firmware/docs/design/remote-webrtc.en.md) |
| R17 v1.0.157-Fix 6 / control.36 baseline | [中文](../versions/v167/microduck-hd1910/firmware/docs/design/robotd-design.md) | [English](../versions/v167/microduck-hd1910/firmware/docs/design/robotd-design.en.md) |
| Microduck R17 V167 / control.43 bundled firmware | [中文](../versions/v167/microduck-hd1910/firmware/packaging/README.zh-CN.md) | [English](../versions/v167/microduck-hd1910/firmware/packaging/README.en.md) |
| HD1910 self-trained model · Target firmware 0.15.1 · 1cbf8730eadd75a5704332c9f3c10f60 | [中文](../versions/v167/microduck-hd1910/docs/MODEL-PROVENANCE.md) | [English](../versions/v167/microduck-hd1910/docs/MODEL-PROVENANCE.en.md) |
| HD1910 self-trained model · Target firmware 0.15.1 · 59e15d7b04d0c40e9b11b8a70bdecae6 | [中文](../versions/v167/microduck-hd1910/docs/MODEL-PROVENANCE.md) | [English](../versions/v167/microduck-hd1910/docs/MODEL-PROVENANCE.en.md) |
| HD1910 self-trained model · Target firmware 0.15.1 · 67ad09d82f4865d222a7ae06f250cf9f | [中文](../versions/v167/microduck-hd1910/firmware/packaging/models/67ad09d82f4865d222a7ae06f250cf9f/使用说明.md) | [English](../versions/v167/microduck-hd1910/firmware/packaging/models/67ad09d82f4865d222a7ae06f250cf9f/README.en.md) |
| HD1910 self-trained model · Target firmware 0.15.1 · a481d9f211f31d9476ab1a319fe362a2 | [中文](../versions/v167/microduck-hd1910/docs/MODEL-PROVENANCE.md) | [English](../versions/v167/microduck-hd1910/docs/MODEL-PROVENANCE.en.md) |
| HD1910 self-trained model · Target firmware 0.15.1 · b14e3a8b56ddbb8d2d831e727774a168 | [中文](../versions/v167/microduck-hd1910/docs/MODEL-PROVENANCE.md) | [English](../versions/v167/microduck-hd1910/docs/MODEL-PROVENANCE.en.md) |
| HD1910 self-trained model · Target firmware 0.15.1 · ee0376c927044cdece056ba1d3e6eac7 | [中文](../versions/v167/microduck-hd1910/docs/MODEL-PROVENANCE.md) | [English](../versions/v167/microduck-hd1910/docs/MODEL-PROVENANCE.en.md) |
| HD1910 self-trained model · Target firmware 0.15.1 · standup | [中文](../versions/v167/microduck-hd1910/firmware/packaging/roller/standup/使用说明.md) | [English](../versions/v167/microduck-hd1910/firmware/packaging/roller/standup/README.en.md) |
| Policy baseline — R17 v1.0.146 / official 0.15.1 | [中文](../versions/v167/microduck-hd1910/firmware/policies/README.md) | [English](../versions/v167/microduck-hd1910/firmware/policies/README.en.md) |
| HD1910 self-trained model · Target firmware 0.15.1 · ground_pick | [中文](../versions/v167/microduck-hd1910/firmware/policies/ground_pick/使用说明.md) | [English](../versions/v167/microduck-hd1910/firmware/policies/ground_pick/README.en.md) |
| HD1910 self-trained model · Target firmware 0.15.1 · kick_left | [中文](../versions/v167/microduck-hd1910/firmware/policies/kick_left/使用说明.md) | [English](../versions/v167/microduck-hd1910/firmware/policies/kick_left/README.en.md) |
| HD1910 self-trained model · Target firmware 0.15.1 · roulade | [中文](../versions/v167/microduck-hd1910/firmware/policies/roulade/使用说明.md) | [English](../versions/v167/microduck-hd1910/firmware/policies/roulade/README.en.md) |
| HD1910 self-trained model · Target firmware 0.15.1 · stand | [中文](../versions/v167/microduck-hd1910/firmware/policies/stand/使用说明.md) | [English](../versions/v167/microduck-hd1910/firmware/policies/stand/README.en.md) |
| HD1910 self-trained model · Target firmware 0.15.1 · walk | [中文](../versions/v167/microduck-hd1910/firmware/policies/walk/使用说明.md) | [English](../versions/v167/microduck-hd1910/firmware/policies/walk/README.en.md) |
| HD1910 self-trained model · Target firmware 0.15.1 · walk-teacher14000 | [中文](../versions/v167/microduck-hd1910/firmware/test-data/walk-teacher14000/使用说明.md) | [English](../versions/v167/microduck-hd1910/firmware/test-data/walk-teacher14000/README.en.md) |
| v153 verification records | [中文](../versions/v167/microduck-hd1910/firmware/verification/README153.md) | [English](../versions/v167/microduck-hd1910/firmware/verification/README153.en.md) |
| Official roller recovery route review | [中文](../versions/v167/microduck-hd1910/firmware/verification/v162/official-roller-route.md) | [English](../versions/v167/microduck-hd1910/firmware/verification/v162/official-roller-route.en.md) |

## Existing English technical documentation

- [Firmware architecture and design](../versions/v167/microduck-hd1910/firmware/docs/README.md)
- [Firmware development](../versions/v167/microduck-hd1910/firmware/CONTRIBUTING.md)
- [Training tests](../microduck-hd1910/training-console/tests/README.md)
- [Licenses and sources](../microduck-hd1910/training-console/NOTICE.md)

[🦆 Project homepage](../README.en.md)

## Licensing and attribution

- [Software and model ownership, personal use and commercial permission](../microduck-hd1910/docs/SOFTWARE-MODEL-RIGHTS.en.md) · [简体中文](../microduck-hd1910/docs/SOFTWARE-MODEL-RIGHTS.md)
- [Model provenance: ten bundled policies, six source weights and historical samples](../microduck-hd1910/docs/MODEL-PROVENANCE.en.md) · [简体中文](../microduck-hd1910/docs/MODEL-PROVENANCE.md)
- [Component license index](../LICENSE) · [Third-party sources](../microduck-hd1910/docs/THIRD-PARTY.en.md)


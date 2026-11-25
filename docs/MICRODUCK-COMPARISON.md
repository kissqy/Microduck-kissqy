**简体中文** | [English](MICRODUCK-COMPARISON.en.md) · [网页版 / Web edition](https://kissqy.github.io/Microduck-kissqy/compare/?v=20261118-short)

# 为什么选择 Microduck-kissqy：我们的优势与其他仓库的缺项

**从 0 到进阶，一套完整的鸭鸭复刻方案。**

面向使用中文流程、ZERO 3W 与飞特 HD1910 完成个人复刻的用户。

> **资料核查截至 2026 年 11 月 18 日。** 外部仓库对比仅对应当日核查的公开版本；本仓库中控入口于 2026-11-24 更新至 R3／V315，其他项目后续更新以各自最新说明为准。

## 我们的优势

### 1. 从零制作到进阶，资料与工具完整配套

**软件、硬件、现成运动模型、飞特 HD1910 适配打印件、各类教程和训练中控集中提供。**

按采购、打印装配、刷机配网和本机标定开始，再继续日常玩法、中文 AI 与自训新动作。 [完整制作路线](https://kissqy.github.io/Microduck-kissqy/build/)

### 2. 配套现成动作，正常复刻无需训练

**行走、坐下站起、捡取、前滚翻、左右踢球，以及滑轮滑行、蹲下、原地转和倒地起身。**

本项目是社区 HD1910 动作资源的主要来源。外部镜像将其中 10 个模型作者标为 kissqy；具体模型按发布包使用。 [动作模型与来源](https://github.com/kissqy/Microduck-kissqy/blob/main/microduck-hd1910/docs/MODEL-PROVENANCE.md)

### 3. 中文中控与 AI，装好后继续玩

**舵机与 IMU 标定、3D 姿态、关节反馈、摄像头、手柄和固件维护，都有中文操作入口。**

R3 / V315 提供中文对话、拍照识别、音色角色与动作调用；AI 需配置服务凭据并联网。 [中控与 AI 用法](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v313)

### 4. HAT、IMU、HUB，软硬件对应起来

**板卡电路工程、材料清单、接线、系统镜像与固件集中提供，可自行制作，也可选择成品板。**

V315 支持通过 HAT 直接给舵机编号和校准中位，无需 URT2。 [配套硬件资料](https://github.com/kissqy/Microduck-kissqy/blob/main/hardware/README.md)

### 5. 飞特适配打印件与分步教程

**提供面向 HD1910 复刻的 STL / 3MF 打印资料，以及预算采购、装配接线、刷机标定与常见问题教程。**

围绕 ZERO 3W 与 15 个 HD1910，按同一套参考配置制作，减少自行拼接不同方案的工作。 [打印与装配资料](https://github.com/kissqy/Microduck-kissqy/blob/main/hardware/3d-print-frankenduck/README.md)

### 6. 独立训练中控，从使用走向自训

**公开训练中控提供 14 类动作、35 种任务配方，支持训练队列、SSH 训练端、奖励曲线、仿真评估与 ONNX 导出。**

先用现成模型完成自己的鸭子，再按需要训练；具体动作的长训练与实机结果按各自记录核对。 [训练中控教程](https://github.com/kissqy/Microduck-kissqy/blob/main/microduck-hd1910/training-console/README.zh-CN.md)

## 这些仓库还缺什么？

### [fanhao375](https://github.com/fanhao375/microduck-replica)

- **镜像中的 10 个动作模型来自 kissqy，沿用原始权重。**
- 未接入自由 AI 语音对话。
- 训练台缺少 SSH 环境部署、顺序队列、交互式策略评估及每次导出验证。
- 自训新策略仍待长训练与真机验收，所列轮滑动作尚未实机测试。

资料截至 **2026-11-18** · [镜像模型署名](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/image/overlay/usr/share/doc/microduck/模型说明.txt) · [项目说明](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/README.md) · [训练功能差距记录](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/docs/reference-comparison-2026-10-23.md) · [训练台说明](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/README.md)

### [OpenMicroDuck](https://github.com/JoyandAI/OpenMicroDuck)

- 缺少新动作训练中控；动作实验室用于现成模型回放与仿真。
- 未公开 HAT、总线 IMU、HUB / 取电板的完整制造工程。
- 未提供中文自由 AI 对话与视觉动作联动流程。
- OpenMD 配套清单缺少左踢及轮滑系列模型。
- 完整中英教程仍在整理。

资料截至 **2026-11-18** · [动作实验室说明](https://github.com/JoyandAI/OpenMicroDuck/blob/379e1919541041f23d816a01c0c9755c7b12a3c9/motion-lab/README.md) · [板卡集成状态](https://github.com/JoyandAI/OpenMicroDuck/blob/379e1919541041f23d816a01c0c9755c7b12a3c9/docs/bom.md) · [OpenMD 策略配置](https://github.com/JoyandAI/OpenMicroDuck/blob/379e1919541041f23d816a01c0c9755c7b12a3c9/policies/README.md) · [项目进展与路线图](https://github.com/JoyandAI/OpenMicroDuck/blob/379e1919541041f23d816a01c0c9755c7b12a3c9/README.md)

### [Pollen Robotics](https://github.com/pollen-robotics/microduck)

- 未提供 HD1910 可直接使用的整套镜像、配置与模型。
- 未提供 HD1910 专用打印改件。
- 未完整公开整机机械与电子制造设计。
- 未提供独立的中文图形训练中控。
- 未提供完整中文 HD1910 从零复刻教程。

资料截至 **2026-11-18** · [官方运行时](https://github.com/pollen-robotics/microduck/blob/56424efe58b7de40efcf3b2d3a5cd169ee83a182/README.md) · [官方训练工程](https://github.com/pollen-robotics/microduck_rl/blob/0daab160d3fb1c2cbaba16a4a19052f36709dd9e/README.md) · [官方硬件公开范围](https://pollen-robotics.com/microduck/press-kit/)

### [AI-FanGe](https://github.com/AI-FanGe/Microduck-build-tutorial)

- 未提供 ZERO 3W + HD1910 配套运行包及打印改件。
- 未提供 HD1910 HAT / IMU / HUB 三板工程包。
- 缺少完整机器人图形中控和独立训练中控。
- 未提供中文 AI 语音、视觉理解与动作联动。
- 随包只有 walk.onnx，缺少多动作和轮滑配套模型。

资料截至 **2026-11-18** · [硬件与运行教程](https://github.com/AI-FanGe/Microduck-build-tutorial/blob/49678215d0b40529522772a40c06c216390449dd/README.md) · [公开项目目录](https://github.com/AI-FanGe/Microduck-build-tutorial/tree/49678215d0b40529522772a40c06c216390449dd) · [训练与导出源码](https://github.com/AI-FanGe/Microduck-build-tutorial/tree/49678215d0b40529522772a40c06c216390449dd/mjlab_microduck) · [随包模型目录](https://github.com/AI-FanGe/Microduck-build-tutorial/tree/49678215d0b40529522772a40c06c216390449dd/microduck/src/agents)

### [Luwu XGO-Duck](https://github.com/LuwuDynamics/xgoduck_hardware)

- 未提供含 SSH 环境部署和任务队列的图形训练中控。
- 未提供 ZERO 3W / HAT / IMU / HUB 的即用兼容方案。
- 模型、打印结构和运行时须按其 UNO Q 方案配套，不能直接混用。

资料截至 **2026-11-18** · [训练与模型接口](https://github.com/LuwuDynamics/xgoduck_rl/blob/a4c78aacd5eaa724cf246fe12d24bfe1e837fa50/README.md) · [硬件及装配说明](https://github.com/LuwuDynamics/xgoduck_hardware/blob/21501676e4413f81480d36b591aedd729412c959/README_CN.md) · [配套运行时与安装](https://github.com/LuwuDynamics/xgoduck_runtime_arduino/blob/3f9db11c376030d234c5b1299862211e87b590f1/README_CN.md)

## 关于动作来源

fanhao 的[镜像模型说明](https://github.com/fanhao375/microduck-replica/blob/master/software/image/overlay/usr/share/doc/microduck/%E6%A8%A1%E5%9E%8B%E8%AF%B4%E6%98%8E.txt)将列出的 **10 个模型作者标为 kissqy**，并记载保留权重与部署元数据。这说明本项目是这批社区 HD1910 动作资源的来源之一；不能外推为对方所有内容都来自本项目。

作者自训与适配建立在官方训练框架、任务和社区工作之上，不把上游内容写成作者原创。[具体模型来源](https://github.com/kissqy/Microduck-kissqy/blob/main/microduck-hd1910/docs/MODEL-PROVENANCE.md)。

## 使用与验证范围

- 本项目保证的适配范围是公布版本的 HAT／IMU／HUB；第三方板卡、不同舵机和机械改动需要重新确认兼容性。新手先按配套参考配置跑通，再一次验证一个改动。
- [R3 / V315](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v313) 为当前正式版。三张新 TF 卡分别写入 R3，三张均在第一次上电时启动并开启配网热点。
- 实机展示、仿真结果与随包权重分别说明。单脚平衡已有实机演示；模型来源页尚未将该演示与独立发布权重一一对应，不能据视频承诺当前包已包含该模型。
- 普通使用无需训练；训练工具中的任务与配方不等于全部已经完成长训练和实机验收。不同动作按各自记录核对。
- 本项目及官方、第三方内容按各自许可使用。部分原创内容限个人非商业用途，见[分项许可](../LICENSE)与[软件及模型权利说明](../microduck-hd1910/docs/SOFTWARE-MODEL-RIGHTS.md)。
- 本页只整理复刻选择与公开证据，不建立新的硬件、固件或模型 Known-Good。

## 开始制作

[① 预算采购](https://kissqy.github.io/Microduck-kissqy/build/budget.html) → [② 装配接线](https://kissqy.github.io/Microduck-kissqy/build/assembly.html) → [③ 刷机与行走](https://kissqy.github.io/Microduck-kissqy/build/start.html)

<details>
<summary>核查快照与来源</summary>

## 核查快照与来源

| 核查仓库 | 固定版本 |
| --- | --- |
| JoyandAI/OpenMicroDuck | [379e19195410](https://github.com/JoyandAI/OpenMicroDuck/tree/379e1919541041f23d816a01c0c9755c7b12a3c9) |
| fanhao375/microduck-replica | [de8b67ddcd24](https://github.com/fanhao375/microduck-replica/tree/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e) |
| pollen-robotics/microduck | [56424efe58b7](https://github.com/pollen-robotics/microduck/tree/56424efe58b7de40efcf3b2d3a5cd169ee83a182) |
| AI-FanGe/Microduck-build-tutorial | [49678215d0b4](https://github.com/AI-FanGe/Microduck-build-tutorial/tree/49678215d0b40529522772a40c06c216390449dd) |
| LuwuDynamics/xgoduck_hardware | [21501676e441](https://github.com/LuwuDynamics/xgoduck_hardware/tree/21501676e4413f81480d36b591aedd729412c959) |
| JoyandAI/microduck | [71c6303be7f7](https://github.com/JoyandAI/microduck/tree/71c6303be7f7e139d9f079cbdc34ef085a372e3f) |
| JoyandAI/microduck_rl | [22916b9d82f2](https://github.com/JoyandAI/microduck_rl/tree/22916b9d82f250caa563ed9a56976eb33243fb91) |
| LuwuDynamics/xgoduck_runtime_arduino | [3f9db11c3760](https://github.com/LuwuDynamics/xgoduck_runtime_arduino/tree/3f9db11c376030d234c5b1299862211e87b590f1) |
| LuwuDynamics/xgoduck_rl | [a4c78aacd5ea](https://github.com/LuwuDynamics/xgoduck_rl/tree/a4c78aacd5eaa724cf246fe12d24bfe1e837fa50) |
| pollen-robotics/microduck_rl | [0daab160d3fb](https://github.com/pollen-robotics/microduck_rl/tree/0daab160d3fb1c2cbaba16a4a19052f36709dd9e) |

- [项目说明](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/README.md)
- [训练台说明](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/README.md)
- [训练功能差距记录](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/docs/reference-comparison-2026-10-23.md)
- [训练服务源码](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/training_studio/service.py)
- [公开配方列表](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/training_studio/config.py)
- [训练验收记录](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/docs/verification.md)
- [单脚平衡验收](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/docs/action-lab-verification.md)
- [镜像模型署名](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/image/overlay/usr/share/doc/microduck/模型说明.txt)
- [项目进展与路线图](https://github.com/JoyandAI/OpenMicroDuck/blob/379e1919541041f23d816a01c0c9755c7b12a3c9/README.md)
- [动作实验室说明](https://github.com/JoyandAI/OpenMicroDuck/blob/379e1919541041f23d816a01c0c9755c7b12a3c9/motion-lab/README.md)
- [关联训练工程](https://github.com/JoyandAI/microduck_rl/blob/22916b9d82f250caa563ed9a56976eb33243fb91/README.md)
- [板卡集成状态](https://github.com/JoyandAI/OpenMicroDuck/blob/379e1919541041f23d816a01c0c9755c7b12a3c9/docs/bom.md)
- [硬件规划](https://github.com/JoyandAI/OpenMicroDuck/blob/379e1919541041f23d816a01c0c9755c7b12a3c9/docs/architecture.md)
- [公开文件目录](https://github.com/JoyandAI/OpenMicroDuck/tree/379e1919541041f23d816a01c0c9755c7b12a3c9)
- [OpenMD 策略配置](https://github.com/JoyandAI/OpenMicroDuck/blob/379e1919541041f23d816a01c0c9755c7b12a3c9/policies/README.md)
- [关联运行时权重来源](https://github.com/JoyandAI/microduck/blob/71c6303be7f7e139d9f079cbdc34ef085a372e3f/policies/README.md)
- [关联网页控制入口](https://github.com/JoyandAI/microduck/blob/71c6303be7f7e139d9f079cbdc34ef085a372e3f/webd/web/index.html)
- [官方运行时](https://github.com/pollen-robotics/microduck/blob/56424efe58b7de40efcf3b2d3a5cd169ee83a182/README.md)
- [官方训练工程](https://github.com/pollen-robotics/microduck_rl/blob/0daab160d3fb1c2cbaba16a4a19052f36709dd9e/README.md)
- [官方训练文件目录](https://github.com/pollen-robotics/microduck_rl/tree/0daab160d3fb1c2cbaba16a4a19052f36709dd9e)
- [官方部署配置](https://github.com/pollen-robotics/microduck/blob/56424efe58b7de40efcf3b2d3a5cd169ee83a182/deploy/robotd.toml)
- [官方硬件公开范围](https://pollen-robotics.com/microduck/press-kit/)
- [硬件与运行教程](https://github.com/AI-FanGe/Microduck-build-tutorial/blob/49678215d0b40529522772a40c06c216390449dd/README.md)
- [公开项目目录](https://github.com/AI-FanGe/Microduck-build-tutorial/tree/49678215d0b40529522772a40c06c216390449dd)
- [训练与导出源码](https://github.com/AI-FanGe/Microduck-build-tutorial/tree/49678215d0b40529522772a40c06c216390449dd/mjlab_microduck)
- [随包模型目录](https://github.com/AI-FanGe/Microduck-build-tutorial/tree/49678215d0b40529522772a40c06c216390449dd/microduck/src/agents)
- [硬件及装配说明](https://github.com/LuwuDynamics/xgoduck_hardware/blob/21501676e4413f81480d36b591aedd729412c959/README_CN.md)
- [配套运行时与安装](https://github.com/LuwuDynamics/xgoduck_runtime_arduino/blob/3f9db11c376030d234c5b1299862211e87b590f1/README_CN.md)
- [训练与模型接口](https://github.com/LuwuDynamics/xgoduck_rl/blob/a4c78aacd5eaa724cf246fe12d24bfe1e837fa50/README.md)
- [训练仓库目录](https://github.com/LuwuDynamics/xgoduck_rl/tree/a4c78aacd5eaa724cf246fe12d24bfe1e837fa50)

</details>

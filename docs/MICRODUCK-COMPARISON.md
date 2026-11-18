**简体中文** | [English](MICRODUCK-COMPARISON.en.md) · [网页版 / Web edition](https://kissqy.github.io/Microduck-kissqy/compare/?v=20261118-advantages-first)

# 为什么选择 Microduck-kissqy：我们的优势与其他仓库的缺项

**从 0 到进阶，一套完整的鸭鸭复刻方案。**

面向使用中文流程、ZERO 3W 与飞特 HD1910 完成个人复刻的用户。

## 我们的优势

### 1. 从零制作到进阶，资料与工具完整配套

**软件、硬件、现成运动模型、飞特 HD1910 适配打印件、各类教程和训练中控集中提供。**

按采购、打印装配、刷机配网和本机标定开始，再继续日常玩法、中文 AI 与自训新动作。 [完整制作路线](https://kissqy.github.io/Microduck-kissqy/build/)

### 2. 配套现成动作，正常复刻无需训练

**行走、坐下站起、捡取、前滚翻、左右踢球，以及滑轮滑行、蹲下、原地转和倒地起身。**

本项目是社区 HD1910 动作资源的主要来源。外部镜像将其中 10 个模型作者标为 kissqy；具体模型按发布包使用。 [动作模型与来源](https://github.com/kissqy/Microduck-kissqy/blob/main/microduck-hd1910/docs/MODEL-PROVENANCE.md)

### 3. 中文中控与 AI，装好后继续玩

**舵机与 IMU 标定、3D 姿态、关节反馈、摄像头、手柄和固件维护，都有中文操作入口。**

R2 / V260 提供中文对话、拍照识别、音色角色与动作调用；AI 需配置服务凭据并联网。 [中控与 AI 用法](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v260)

### 4. HAT、IMU、HUB，软硬件对应起来

**板卡电路工程、材料清单、接线、系统镜像与固件集中提供，可自行制作，也可选择成品板。**

V297 BATE 另提供 HAT 直接编号与中位校准，无需 URT2；该测试版实机验收待完成。 [配套硬件资料](https://github.com/kissqy/Microduck-kissqy/blob/main/hardware/README.md)

### 5. 飞特适配打印件与分步教程

**提供面向 HD1910 复刻的 STL / 3MF 打印资料，以及预算采购、装配接线、刷机标定与常见问题教程。**

围绕 ZERO 3W 与 15 个 HD1910，按同一套参考配置制作，减少自行拼接不同方案的工作。 [打印与装配资料](https://github.com/kissqy/Microduck-kissqy/blob/main/hardware/3d-print-frankenduck/README.md)

### 6. 独立训练中控，从使用走向自训

**任务与配方选择、训练队列、奖励曲线、仿真评估和 ONNX 导出，形成研究新动作的操作流程。**

先用现成模型完成自己的鸭子，再按需要训练；具体动作的长训练与实机结果按各自记录核对。 [训练中控教程](https://github.com/kissqy/Microduck-kissqy/blob/main/microduck-hd1910/training-console/README.zh-CN.md)

## 这些仓库还缺什么？

### [fanhao375](https://github.com/fanhao375/microduck-replica)

ZERO 3W + HD1910

- **所列 10 个现成模型来自 kissqy**  
  其镜像说明将 10 个模型署名给 kissqy，并记录保留原始权重。

- **没有接入自由 AI 对话**  
  公开说明中的本地固定指令识别，不能等同于自由对话、视觉识别与 AI 动作调用。

- **自训动作尚未完成长训与实机验收**  
  GPU 短试跑、评估和导出已验证，不代表新动作已经在实机训成。

资料依据：[模型署名](https://github.com/fanhao375/microduck-replica/blob/master/software/image/overlay/usr/share/doc/microduck/%E6%A8%A1%E5%9E%8B%E8%AF%B4%E6%98%8E.txt) · [项目说明](https://github.com/fanhao375/microduck-replica) · [训练验证](https://github.com/fanhao375/microduck-replica/blob/master/software/training-studio/docs/verification.md)

### [OpenMicroDuck](https://github.com/JoyandAI/OpenMicroDuck)

ZERO 3W + HD1910

- **没有提供左踢模型，清单未列滑轮动作**  
  策略说明明确写出 kick_left = none；所列 6 个 ONNX 中也未列滑轮动作。

- **部署仍需遵循特定运行时与按键配置**  
  这份说明按 robotd 0.13.3 编写，按键映射位于 padd 二进制中；不能直接当作与其他镜像、中控通用的配置。

资料依据：[策略配置](https://github.com/JoyandAI/OpenMicroDuck/blob/main/policies/README.md)

### [Pollen Robotics](https://github.com/pollen-robotics/microduck)

Official / XL330

- **没有面向飞特 HD1910 的直接安装方案**  
  原版 XL330 路线与飞特舵机不同；改用 HD1910，通信、执行器参数和策略适配还要另行完成。

- **原版权重不能直接作为飞特配套步态**  
  仅替换舵机名称或复制 ONNX，不等于完成硬件与策略匹配。

资料依据：[官方运行时](https://github.com/pollen-robotics/microduck) · [HD1910 适配](https://github.com/kissqy/Microduck-kissqy)

### [AI-FanGe](https://github.com/AI-FanGe/Microduck-build-tutorial)

Pi Zero 2 W + XL330

- **没有 ZERO 3W + HD1910 的配套硬件路线**  
  该路线使用 Pi Zero 2 W、OpenRB-150 与 XL330；ZERO 3W / HD1910 需要另一套电控与部署配置。

- **所读教程未给出这套中文 AI 与多动作流程**  
  所读指南通过 SSH、终端命令和手柄完成部署；未给出本项目这套中文 AI 与多动作操作流程。

资料依据：[部署教程](https://github.com/AI-FanGe/Microduck-build-tutorial)

### [Luwu XGO-Duck](https://github.com/LuwuDynamics/xgoduck_hardware)

UNO Q + 1910 / QMI8658A

- **不能直接沿用 ZERO 3W 与本项目板卡**  
  主控为 Arduino UNO Q，配定制扩展板与 QMI8658A；已有 ZERO 3W 和本项目板卡时，主控、IMU、接线与软件都需重新核对。

- **现成界面与策略依赖 UNO Q 配套运行环境**  
  浏览器界面和策略服务于 UNO Q 配套环境，不能直接代替本项目镜像和中控。

资料依据：[硬件配置](https://github.com/LuwuDynamics/xgoduck_hardware/blob/master/README_CN.md)

核查日期：**2026-11-18**。缺项与限制针对所链接的公开版本和具体配置，未列出的功能不据此认定整个项目都没有。

## 关于动作来源

fanhao 的[镜像模型说明](https://github.com/fanhao375/microduck-replica/blob/master/software/image/overlay/usr/share/doc/microduck/%E6%A8%A1%E5%9E%8B%E8%AF%B4%E6%98%8E.txt)将列出的 **10 个模型作者标为 kissqy**，并记载保留权重与部署元数据。这说明本项目是这批社区 HD1910 动作资源的来源之一；不能外推为对方所有内容都来自本项目。

作者自训与适配建立在官方训练框架、任务和社区工作之上，不把上游内容写成作者原创。[具体模型来源](https://github.com/kissqy/Microduck-kissqy/blob/main/microduck-hd1910/docs/MODEL-PROVENANCE.md)。

## 使用与验证范围

- 本项目保证的适配范围是公布版本的 HAT／IMU／HUB；第三方板卡、不同舵机和机械改动需要重新确认兼容性。新手先按配套参考配置跑通，再一次验证一个改动。
- V260／R2 是当前正式发布入口。[V297 BATE](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v297-bate)另提供 HAT 舵机编号、中位校准和独立硬件测试；该版实机验收待完成，不能据受控回归直接扩大 Known-Good。
- 实机展示、仿真结果与随包权重分别说明。单脚平衡已有实机演示；模型来源页尚未将该演示与独立发布权重一一对应，不能据视频承诺当前包已包含该模型。
- 普通使用无需训练；训练工具中的任务与配方不等于全部已经完成长训练和实机验收。不同动作按各自记录核对。
- 本项目及官方、第三方内容按各自许可使用。部分原创内容限个人非商业用途，见[分项许可](../LICENSE)与[软件及模型权利说明](../microduck-hd1910/docs/SOFTWARE-MODEL-RIGHTS.md)。
- 本页只整理复刻选择与公开证据，不建立新的硬件、固件或模型 Known-Good。

## 开始制作

[① 预算采购](https://kissqy.github.io/Microduck-kissqy/build/budget.html) → [② 装配接线](https://kissqy.github.io/Microduck-kissqy/build/assembly.html) → [③ 刷机与行走](https://kissqy.github.io/Microduck-kissqy/build/start.html)

## 主要依据

- [fanhao375 · 模型署名](https://github.com/fanhao375/microduck-replica/blob/master/software/image/overlay/usr/share/doc/microduck/%E6%A8%A1%E5%9E%8B%E8%AF%B4%E6%98%8E.txt)
- [fanhao375 · 项目说明](https://github.com/fanhao375/microduck-replica)
- [fanhao375 · 训练验证](https://github.com/fanhao375/microduck-replica/blob/master/software/training-studio/docs/verification.md)
- [OpenMicroDuck · 策略配置](https://github.com/JoyandAI/OpenMicroDuck/blob/main/policies/README.md)
- [Pollen Robotics · 官方运行时](https://github.com/pollen-robotics/microduck)
- [Pollen Robotics · HD1910 适配](https://github.com/kissqy/Microduck-kissqy)
- [AI-FanGe · 部署教程](https://github.com/AI-FanGe/Microduck-build-tutorial)
- [Luwu XGO-Duck · 硬件配置](https://github.com/LuwuDynamics/xgoduck_hardware/blob/master/README_CN.md)
- [Microduck-kissqy · R2 / V260](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v260)
- [Microduck-kissqy · V297 BATE](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v297-bate)
- [Microduck-kissqy · 模型来源](https://github.com/kissqy/Microduck-kissqy/blob/main/microduck-hd1910/docs/MODEL-PROVENANCE.md)


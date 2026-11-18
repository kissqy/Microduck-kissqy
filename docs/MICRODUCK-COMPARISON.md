**简体中文** | [English](MICRODUCK-COMPARISON.en.md) · [网页版 / Web edition](https://kissqy.github.io/Microduck-kissqy/compare/)

# 为什么选择 Microduck-kissqy：优势与方案差距

**面向使用中文流程、ZERO 3W 与飞特 HD1910 完成个人复刻的用户。先看差距，再看本项目的具体优势。**

## 与五个代表项目直接比较

### Microduck-kissqy VS [fanhao375](https://github.com/fanhao375/microduck-replica)

ZERO 3W + HD1910

| **Microduck-kissqy · 我们的优势** | **fanhao375 · 对照方案的差距** |
| --- | --- |
| **从 0 到进阶，一套完整方案**<br>软件、硬件、现成运动模型、飞特 HD1910 适配打印件、教程和独立训练中控集中提供，覆盖制作、使用与进阶。<br><br>**动作直接看作者发布，中文 AI 有配套流程**<br>本项目提供自训适配模型、来源与部署记录；中文对话、拍照识别和动作调用已有 R2 / V260 发布入口。 | **这批现成模型不是另一套新增动作**<br>其镜像说明将 10 个模型署名给 kissqy，并记录保留原始权重。<br><br>**自由 AI 对话仍被列为未接入**<br>公开说明中的本地固定指令识别，不能等同于自由对话、视觉识别与 AI 动作调用。<br><br>**自建训练台仍待长训与自训真机验收**<br>GPU 短试跑、评估和导出已验证，不代表新动作已经在实机训成。 |

该项目资料依据：[模型署名](https://github.com/fanhao375/microduck-replica/blob/master/software/image/overlay/usr/share/doc/microduck/%E6%A8%A1%E5%9E%8B%E8%AF%B4%E6%98%8E.txt) · [项目说明](https://github.com/fanhao375/microduck-replica) · [训练验证](https://github.com/fanhao375/microduck-replica/blob/master/software/training-studio/docs/verification.md)


### Microduck-kissqy VS [OpenMicroDuck](https://github.com/JoyandAI/OpenMicroDuck)

ZERO 3W + HD1910

| **Microduck-kissqy · 我们的优势** | **OpenMicroDuck · 对照方案的差距** |
| --- | --- |
| **左右踢球和滑轮动作，都有配套资源**<br>普通脚掌动作之外，还提供滑轮滑行、蹲下、原地转和倒地起身的模型资源。 | **公开配置只有右踢，左踢为空**<br>策略说明明确写出 kick_left = none；所列 6 个 ONNX 中也未列滑轮动作。<br><br>**部署和操作存在明确版本限制**<br>这份说明按 robotd 0.13.3 编写，按键映射位于 padd 二进制中；不能直接当作与其他镜像、中控通用的配置。 |

该项目资料依据：[策略配置](https://github.com/JoyandAI/OpenMicroDuck/blob/main/policies/README.md)


### Microduck-kissqy VS [Pollen Robotics](https://github.com/pollen-robotics/microduck)

Official / XL330

| **Microduck-kissqy · 我们的优势** | **Pollen Robotics · 对照方案的差距** |
| --- | --- |
| **HD1910 适配已经组织成配套方案**<br>ZERO 3W 镜像、舵机通信、对应动作模型与中文中控集中提供，按步骤制作即可开始验证。 | **官方原版不是 HD1910 的直接安装包**<br>原版 XL330 路线与飞特舵机不同；改用 HD1910，通信、执行器参数和策略适配还要另行完成。<br><br>**官方权重不能直接当作飞特现成步态**<br>仅替换舵机名称或复制 ONNX，不等于完成硬件与策略匹配。 |

该项目资料依据：[官方运行时](https://github.com/pollen-robotics/microduck) · [HD1910 适配](https://github.com/kissqy/Microduck-kissqy)


### Microduck-kissqy VS [AI-FanGe](https://github.com/AI-FanGe/Microduck-build-tutorial)

Pi Zero 2 W + XL330

| **Microduck-kissqy · 我们的优势** | **AI-FanGe · 对照方案的差距** |
| --- | --- |
| **中文界面维护，继续体验多动作和 AI**<br>关节与 IMU 标定、反馈、摄像头和固件维护有图形入口，动作与 AI 按配套发布使用。 | **硬件不是同一套，不能照抄到飞特鸭**<br>该路线使用 Pi Zero 2 W、OpenRB-150 与 XL330；ZERO 3W / HD1910 需要另一套电控与部署配置。<br><br>**公开上手主线集中在 walk.onnx 行走**<br>所读指南通过 SSH、终端命令和手柄完成部署；未给出本项目这套中文 AI 与多动作操作流程。 |

该项目资料依据：[部署教程](https://github.com/AI-FanGe/Microduck-build-tutorial)


### Microduck-kissqy VS [Luwu XGO-Duck](https://github.com/LuwuDynamics/xgoduck_hardware)

UNO Q + 1910 / QMI8658A

| **Microduck-kissqy · 我们的优势** | **Luwu XGO-Duck · 对照方案的差距** |
| --- | --- |
| **沿用 ZERO 3W 和本项目板卡继续制作**<br>已有或准备购买 ZERO 3W、HAT / IMU / HUB 时，围绕同一套参考配置制作和维护。 | **不是换个镜像就能切过去**<br>主控为 Arduino UNO Q，配定制扩展板与 QMI8658A；已有 ZERO 3W 和本项目板卡时，主控、IMU、接线与软件都需重新核对。<br><br>**其现成策略仍要使用匹配的运行时**<br>浏览器界面和策略服务于 UNO Q 配套环境，不能直接代替本项目镜像和中控。 |

该项目资料依据：[硬件配置](https://github.com/LuwuDynamics/xgoduck_hardware/blob/master/README_CN.md)


核查日期：**2026-11-18**。差距针对所链接的具体配置与说明。本次未做同条件实机横测，不据此宣称步态更稳、故障更少或性能第一。

## 选择我们，具体得到什么

### 1. 从 0 到进阶的完整鸭鸭复刻方案

**软件、硬件、运动模型、飞特 HD1910 适配打印件、各类教程与训练中控集中提供。**

从采购、打印装配、刷机配网与本机标定开始，再继续体验现成动作、中文 AI、训练评估和 ONNX 导出。[完整制作与进阶路线](https://kissqy.github.io/Microduck-kissqy/build/)

### 2. 现成动作直接找作者

**普通脚掌与滑轮动作，来源和部署记录一起看。**

外部镜像明确署名的 10 个模型可追溯到 kissqy；具体权重以发布包为准。 [看模型来源](https://github.com/kissqy/Microduck-kissqy/blob/main/microduck-hd1910/docs/MODEL-PROVENANCE.md)

### 3. 中文 AI 有配套发布流程

**中文对话、拍照识别、音色角色与动作调用。**

R2 / V260 已发布对应流程；需配置服务凭据并联网。 [看 AI 功能与用法](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v260)

### 4. HAT 直接编号与中位校准

**无需 URT2 调试板，编号和标定在同一中控中衔接。**

该功能在 V297 BATE 测试版；已有 R2 / control.102 用户只需更换中控，实机验收待完成。 [看 HAT 编号方法](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v297-bate)

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


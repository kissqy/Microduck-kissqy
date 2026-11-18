**简体中文** | [English](MICRODUCK-COMPARISON.en.md) · [返回项目首页](../README.md) · [打开网页版](https://kissqy.github.io/Microduck-kissqy/compare/)

# Microduck 代表项目对比与复刻路线选择

**准备使用飞特 HD1910，希望按中文教程完成个人复刻，先体验现成动作，再探索 AI 与训练？推荐从 Microduck-kissqy 的配套方案开始。**

本项目将自制 HAT／IMU／HUB、打印与装配资料、系统镜像、中文中控、作者训练适配的动作模型和独立训练工具放在同一条制作与使用路线中。正常复刻无需先训练；从采购、装配、刷机和本机标定开始，再使用配套模型。

[开始三步复刻](https://kissqy.github.io/Microduck-kissqy/build/) · [R2／V260 下载](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v260) · [实机展示](https://kissqy.github.io/Microduck-kissqy/one-leg-balance.html)

## 六个代表项目怎么选

选取关注度较高的官方与社区路线，并纳入同为 ZERO 3W＋HD1910 的 OpenMicroDuck。核查日期为 **2026 年 11 月 18 日**；依据是各项目公开资料与验证记录，本次未进行统一条件下的实机横测。

| 项目 | 主要硬件路线 | 已公开的突出价值 | 更适合的需求 |
| --- | --- | --- | --- |
| **[Microduck-kissqy](https://github.com/kissqy/Microduck-kissqy)** | **ZERO 3W＋15 个 HD1910；本项目 HAT／IMU／HUB** | **作者自训动作、现成 ONNX、中文中控、中文 AI、独立训练工具与配套板卡工程** | **希望沿配套方案完成个人复刻，体验多种动作，并继续探索 AI 和训练的中文用户** |
| [Pollen Robotics 官方 Microduck](https://github.com/pollen-robotics/microduck) | 官方硬件与 Dynamixel XL330 | Microduck 的运行时、训练生态、架构和更新机制的技术来源 | 还原官方配置、研究官方软件及底层开发 |
| [陆吾 XGO-Duck](https://github.com/LuwuDynamics/xgoduck_hardware) | Arduino UNO Q＋飞特 1910＋QMI8658A | 硬件生产资料、装配手册、3MF、配套运行时、现成策略和训练仓库 | 已选择 UNO Q，希望围绕 Arduino 生态制作与开发 |
| [AI-FanGe Microduck-build-tutorial](https://github.com/AI-FanGe/Microduck-build-tutorial) | 树莓派 Zero 2 W＋OpenRB-150＋XL330＋BNO08x | BOM、接线、镜像、SSH、键盘与手柄教程，以及行走策略和训练工程 | 使用树莓派与 XL330，按清楚的首次运行教程制作 |
| [fanhao375 microduck-replica](https://github.com/fanhao375/microduck-replica) | 主线 ZERO 3W＋HD1910；另有 A7Z 预览适配和 XL330 CAD | CAD、BOM、装配视频与社区贡献丰富；已有站立、行走、前滚翻起身记录，也有镜像、中控和训练台 | 深入研究机械装配、社区改进与其他硬件适配 |
| [JoyandAI OpenMicroDuck](https://github.com/JoyandAI/OpenMicroDuck) | ZERO 3W＋HD1910，自有 HAT／IMU | 预部署镜像、BOM、硬件与训练资料；策略目录列出 6 个 ONNX 及部署参数 | 希望采用其板卡、策略和部署方案，研究该项目的 HD1910 训练路线 |

关注度快照：官方 **13,888**、XGO-Duck 硬件仓 **1,970**、AI-FanGe **1,833**、fanhao375 **1,735**、本项目 **521**、OpenMicroDuck **287** Star。数值随时间变化，关联仓库不相加。具体复刻应按硬件、可用资源和验证范围选择。

## 选择 kissqy 能得到什么

| 你关心的问题 | 本项目已有支持 | 直接入口 |
| --- | --- | --- |
| 不懂强化学习，能先做起来吗？ | 正常复刻无需训练；按采购、装配、刷机与标定步骤使用配套模型 | [从零复刻教程](MICRODUCK-BUILD-GUIDE.md) · [首次行走](https://kissqy.github.io/Microduck-kissqy/build/start.html) |
| 装好以后有哪些动作可以研究？ | 提供行走、坐站、捡取、前滚翻、左右踢球与滑轮动作资源，并记录模型来源和部署信息 | [模型来源与范围](../microduck-hd1910/docs/MODEL-PROVENANCE.md) · [实机展示](https://kissqy.github.io/Microduck-kissqy/one-leg-balance.html) |
| 电路和软件怎么配套？ | HAT、独立躯干 IMU、HUB 工程及制作记录，与对应镜像、固件、中控和接线说明集中提供；成品 IMU 已预烧录 FT6 | [硬件工程](../hardware/README.md) · [IMU 固件](../hardware/IMU-FIRMWARE.md) |
| 能否用图形界面操作和排查？ | 中文中控支持关节与 IMU 标定、实时 3D 姿态、关节反馈、摄像头、手柄及固件维护 | [中控教程](https://kissqy.github.io/Microduck-kissqy/console-guide.html) |
| 能否继续体验中文 AI？ | R2／V260 提供豆包中文语音、拍照识别、音色与角色配置和动作调用；需配置服务凭据并联网 | [R2／V260 功能与使用说明](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v260) |
| 想训练自己的新动作怎么办？ | 独立训练中控提供任务选择、训练队列、奖励曲线、仿真评估与 ONNX 导出 | [训练中控指南](../microduck-hd1910/training-console/README.zh-CN.md) |

本项目的推荐价值在于这些资源之间的配套关系：先使用现成成果完成自己的机器，再选择是否深入 AI、训练和硬件制作。它们也应按各自的发布版本与验收范围使用。

## 有其他项目确认的动作模型贡献

**Microduck-kissqy 是社区 HD1910 动作资源的来源之一。**

fanhao375 镜像构建树中的[《模型说明.txt》](https://github.com/fanhao375/microduck-replica/blob/master/software/image/overlay/usr/share/doc/microduck/%E6%A8%A1%E5%9E%8B%E8%AF%B4%E6%98%8E.txt)明确将列出的 **10 个普通脚掌和滑轮模型的作者标为 kissqy**。说明记载保留了 `policy.onnx` 及随附部署元数据，并记录了精简训练归档和调整部分运行参数的情况。

对于这批模型，直接从原始发布项目查阅来源、导出记录和配套参数，是选择本仓库的一个具体理由。该证据只覆盖说明列出的模型范围。

本项目的自训成果建立在官方训练框架、任务、机器人几何与社区工作之上。[模型来源页](../microduck-hd1910/docs/MODEL-PROVENANCE.md)区分作者训练适配、官方参考、历史权重和已发布副本。

## 与两条相近 HD1910 路线的具体区别

| 比较项 | Microduck-kissqy | fanhao375 | OpenMicroDuck |
| --- | --- | --- | --- |
| 现成策略 | 提供普通脚掌和滑轮动作资源，附作者自训与来源说明 | 镜像模型说明列出采用 kissqy 的 10 个模型 | 策略目录列出行走、站立、捡取、右踢、翻滚、坐站 6 个 ONNX |
| 实机与训练记录 | 有作者自训实机展示，以及独立训练中控；具体动作范围见来源页 | 已有整机运动记录；自身训练台有 GPU 短试跑、评估和导出记录，长训练与自训真机仍待验收 | 有实机视频、关联训练仓库，以及具体模型槽位和参数说明 |
| 配套硬件 | 本项目 HAT／IMU／HUB 工程、制作记录和成品板入口 | 官方 HAT 与自制总线 IMU／HUB／电池接口资料 | 自有 HAT／IMU 等硬件与 BOM |
| 上手与扩展重点 | 中文图形操作、配套板卡、现成多动作、中文 AI 与训练工具 | CAD、装配、社区资料和多硬件适配 | 自有硬件、模型和部署配置的整机路线 |

三者都提供现成策略与整机资料，正常使用不必先从零训练。OpenMicroDuck 首页仍列 5 个模型，较具体的[策略目录说明](https://github.com/JoyandAI/OpenMicroDuck/blob/main/policies/README.md)已列 6 个，本页按该目录记录。模型数量与动作能力并非一一对应，不以数量代替实机效果比较。

## 从这里开始制作

1. **选配套方案。** 按[预算与采购](https://kissqy.github.io/Microduck-kissqy/build/budget.html)准备材料，选择制作板卡或使用成品板。
2. **完成装配与标定。** 按[装配接线](https://kissqy.github.io/Microduck-kissqy/build/assembly.html)和[首次行走](https://kissqy.github.io/Microduck-kissqy/build/start.html)完成打印、刷机、配网及本机标定。
3. **先体验现成动作，再选择进阶。** 需要中文交互时配置 AI；希望研究新动作时，再使用[独立训练中控](../microduck-hd1910/training-console/README.zh-CN.md)。

## 使用与验证范围

- 本项目保证的适配范围是公布版本的 HAT／IMU／HUB；第三方板卡、不同舵机和机械改动需要重新确认兼容性。新手先按配套参考配置跑通，再一次验证一个改动。
- V260／R2 是当前正式发布入口。[V297 BATE](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v297-bate)另提供 HAT 舵机编号、中位校准和独立硬件测试；该版实机验收待完成，不能据受控回归直接扩大 Known-Good。
- 实机展示、仿真结果与随包权重分别说明。单脚平衡已有实机演示；模型来源页尚未将该演示与独立发布权重一一对应，不能据视频承诺当前包已包含该模型。
- 普通使用无需训练；训练工具中的任务与配方不等于全部已经完成长训练和实机验收。不同动作按各自记录核对。
- 本项目及官方、第三方内容按各自许可使用。部分原创内容限个人非商业用途，见[分项许可](../LICENSE)与[软件及模型权利说明](../microduck-hd1910/docs/SOFTWARE-MODEL-RIGHTS.md)。
- 本页只整理复刻选择与公开证据，不建立新的硬件、固件或模型 Known-Good。

## 主要依据

| 依据 | 核查内容 |
| --- | --- |
| [官方 Microduck](https://github.com/pollen-robotics/microduck) · [官方训练生态](https://github.com/pollen-robotics/microduck_rl) | 上游软件、硬件路线与训练来源 |
| [XGO-Duck 硬件](https://github.com/LuwuDynamics/xgoduck_hardware) | UNO Q 配置、板件生产资料、装配与配套运行时／训练项目 |
| [AI-FanGe 教程](https://github.com/AI-FanGe/Microduck-build-tutorial) | 树莓派、XL330、镜像、操作及训练工程 |
| [fanhao 项目](https://github.com/fanhao375/microduck-replica) · [训练台验证](https://github.com/fanhao375/microduck-replica/blob/master/software/training-studio/docs/verification.md) | 整机、装配、社区成果与训练验证范围 |
| [fanhao 镜像模型说明](https://github.com/fanhao375/microduck-replica/blob/master/software/image/overlay/usr/share/doc/microduck/%E6%A8%A1%E5%9E%8B%E8%AF%B4%E6%98%8E.txt) | kissqy 模型署名、保留内容和参数变化 |
| [OpenMicroDuck](https://github.com/JoyandAI/OpenMicroDuck) · [策略目录](https://github.com/JoyandAI/OpenMicroDuck/blob/main/policies/README.md) | ZERO 3W／HD1910 配置、镜像、策略与部署说明 |
| [本项目 R2／V260](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v260) · [模型来源](../microduck-hd1910/docs/MODEL-PROVENANCE.md) · [硬件工程](../hardware/README.md) · [训练中控](../microduck-hd1910/training-console/README.zh-CN.md) | 本项目资源与功能的发布、来源及验证范围 |

[返回项目首页](../README.md) · [开始复刻](https://kissqy.github.io/Microduck-kissqy/build/) · [English](MICRODUCK-COMPARISON.en.md)

**简体中文** | [English](MICRODUCK-COMPARISON.en.md) · [网页版 / Web edition](https://kissqy.github.io/Microduck-kissqy/compare/?v=20261118-full-audit)

# 为什么选择 Microduck-kissqy：我们的优势与其他仓库的缺项

**从 0 到进阶，一套完整的鸭鸭复刻方案。**

面向使用中文流程、ZERO 3W 与飞特 HD1910 完成个人复刻的用户。

> **资料核查截至 2026 年 11 月 18 日。** 已核查主仓库与关联运行时、训练仓库。以下只对应列出的固定版本；未提供、尚未完成与需另行适配分别标记，不包含未公开内容、未核查分支及此后新增功能。

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

**公开训练中控提供 14 类动作、35 种任务配方，支持训练队列、SSH 训练端、奖励曲线、仿真评估与 ONNX 导出。**

先用现成模型完成自己的鸭子，再按需要训练；具体动作的长训练与实机结果按各自记录核对。 [训练中控教程](https://github.com/kissqy/Microduck-kissqy/blob/main/microduck-hd1910/training-console/README.zh-CN.md)

## 这些仓库还缺什么？

### [fanhao375](https://github.com/fanhao375/microduck-replica)

ZERO 3W + HD1910

**资料截至 2026-11-18 · 13 项缺项与限制。**

核查版本：[microduck-replica @ de8b67d](https://github.com/fanhao375/microduck-replica/tree/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e)

#### 训练中控与训练流程

- **未提供图形化 SSH 连接与训练环境部署**（公开版未提供）  
  训练服务器的依赖、服务启动和端口转发仍需手工准备；公开说明仍将远端连接管理与自动安装列为待实现。  
  依据：[训练功能差距记录](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/docs/reference-comparison-2026-10-23.md) · [训练台说明](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/README.md)

- **训练未脱离中控服务独立保活**（现有流程限制）  
  关闭网页可以继续，但关闭训练台服务会停止其拥有的训练子进程；还需自行用终端会话或系统服务保持训练台运行。  
  依据：[训练台说明](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/README.md) · [训练功能差距记录](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/docs/reference-comparison-2026-10-23.md)

- **缺少交互式 PT / ONNX 物理评估入口**（公开版未提供）  
  训练区三维显示为 CAD 预览；文档中的策略效果通过停止训练后的有限步数视频评估查看，尚未提供同类交互式策略观察流程。  
  依据：[训练功能差距记录](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/docs/reference-comparison-2026-10-23.md) · [训练台说明](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/README.md)

- **没有顺序执行的多任务训练队列**（公开版未提供）  
  服务只允许一个活动任务，占用时拒绝新任务；公开状态和接口未提供排队、按参数快照顺序执行多项训练的流程。  
  依据：[训练服务源码](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/training_studio/service.py) · [训练功能差距记录](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/docs/reference-comparison-2026-10-23.md)

- **缺少分项奖励与课程进度诊断**（公开版未提供）  
  后续更新虽补了执行端资源读数，但文档仍明确列出分项奖励、课程信息、预计完成时间和历史资源曲线尚未实现。  
  依据：[训练功能差距记录](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/docs/reference-comparison-2026-10-23.md)

- **导出后缺少每次自动推理与完整部署兼容检查**（公开版未提供）  
  现有样本做过独立 PT / ONNX 核对；验收记录仍说明这项核对未自动纳入每次导出，完整部署兼容检查也待补齐。  
  依据：[训练功能差距记录](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/docs/reference-comparison-2026-10-23.md) · [训练验收记录](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/docs/verification.md)

- **图形配方未覆盖坐站、踢球、翻滚和轮滑等动作**（公开版未提供）  
  当前配方注册表只有平地行走、起伏地形、单脚平衡三项；上述其他动作没有相应的图形训练配方入口。  
  依据：[公开配方列表](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/training_studio/config.py)

#### 自训与验收

- **自训新策略仍缺长训练与真机验收**（尚未完成）  
  公开训练台记录主要覆盖短试跑、评估和导出。单脚平衡记录的 5 轮短训为 0/8 成功，并注明尚未完成真机验证；这不等于已交付成熟自训动作。  
  依据：[训练台说明](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/README.md) · [单脚平衡验收](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/docs/action-lab-verification.md) · [训练验收记录](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/docs/verification.md)

- **镜像所列四个轮滑动作尚未完成真机测试**（尚未完成）  
  模型说明对轮滑滑行、蹲下、原地转和倒地起身明确标注尚未在真机上试过；不能仅按文件已随包提供认定这四项已完成整机验收。  
  依据：[镜像模型署名](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/image/overlay/usr/share/doc/microduck/模型说明.txt)

- **所列新镜像与升级流程仍有实物验收缺口**（尚未完成）  
  README 对 20261027 镜像列出新卡首用、旧卡升级/回退及真人声学待验收，对 20261028 更新列出 Qinmo 实物与整机升级待验收。结论仅对应这些明确列出的版本。  
  依据：[项目说明](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/README.md)

#### AI 交互

- **自由 AI 人声对话仍未接入**（公开版未提供）  
  项目说明仍标明自由 AI 人声对话未解决。固定语音指令和电脑 AI 助手的 SSH 入口，未形成中文自由对话、看图理解与 AI 动作调用的同套发布流程。  
  依据：[项目说明](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/README.md)

#### 动作模型

- **镜像所列 10 个模型不是另一套新增自训成果**（模型来源）  
  镜像模型说明将这 10 个模型作者标为 kissqy，并记载保留原始权重；选择该镜像不会因此额外获得这批动作之外的一套独立新模型。  
  依据：[镜像模型署名](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/image/overlay/usr/share/doc/microduck/模型说明.txt)

- **镜像模型包未保留完整训练归档与导出说明**（公开版未提供）  
  模型说明列出已删除 export-data.zip、训练配置、训练请求、upstream-params 和使用说明等文件；要查原始训练与导出细节，还需回原发布方补取资料。  
  依据：[镜像模型署名](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/image/overlay/usr/share/doc/microduck/模型说明.txt)

### [OpenMicroDuck](https://github.com/JoyandAI/OpenMicroDuck)

ZERO 3W + HD1910

**资料截至 2026-11-18 · 10 项缺项与限制。**

核查版本：[OpenMicroDuck @ 379e191](https://github.com/JoyandAI/OpenMicroDuck/tree/379e1919541041f23d816a01c0c9755c7b12a3c9) · [microduck @ 71c6303](https://github.com/JoyandAI/microduck/tree/71c6303be7f7e139d9f079cbdc34ef085a372e3f) · [microduck_rl @ 22916b9](https://github.com/JoyandAI/microduck_rl/tree/22916b9d82f250caa563ed9a56976eb33243fb91)

#### 训练中控与训练流程

- **没有独立的新动作训练中控**（公开版未提供）  
  Motion Lab 使用 CPU 加载六个现成 ONNX 做回放和物理仿真；公开功能未提供新建 PPO 训练、训练队列、奖励曲线与训练成果导出的完整图形流程。  
  依据：[动作实验室说明](https://github.com/JoyandAI/OpenMicroDuck/blob/379e1919541041f23d816a01c0c9755c7b12a3c9/motion-lab/README.md) · [关联训练工程](https://github.com/JoyandAI/microduck_rl/blob/22916b9d82f250caa563ed9a56976eb33243fb91/README.md)

- **没有图形化训练服务器连接与环境准备**（公开版未提供）  
  关联训练仓库以 uv、train、play、export 等命令组织任务；所核查文件未提供 SSH 服务器配置、远端环境部署与队列管理的一体界面。  
  依据：[关联训练工程](https://github.com/JoyandAI/microduck_rl/blob/22916b9d82f250caa563ed9a56976eb33243fb91/README.md)

#### 硬件工程与配套

- **未公开完整自制 HAT 工程与制造资料**（公开版未提供）  
  公开 BOM 仍写 HAT 回片后替换外置驱动板，架构文档列为规划；核查目录未见该自制 HAT 的 PCB、制造 BOM 与生产文件整套交付。  
  依据：[板卡集成状态](https://github.com/JoyandAI/OpenMicroDuck/blob/379e1919541041f23d816a01c0c9755c7b12a3c9/docs/bom.md) · [硬件规划](https://github.com/JoyandAI/OpenMicroDuck/blob/379e1919541041f23d816a01c0c9755c7b12a3c9/docs/architecture.md) · [公开文件目录](https://github.com/JoyandAI/OpenMicroDuck/tree/379e1919541041f23d816a01c0c9755c7b12a3c9)

- **未公开总线 IMU 板的完整工程、固件与烧录流程**（公开版未提供）  
  BOM 将 IMU_to_servo 自制板标为尚未就绪；未找到与这块规划板对应的电路工程、从机固件和烧录教程的完整发布。  
  依据：[板卡集成状态](https://github.com/JoyandAI/OpenMicroDuck/blob/379e1919541041f23d816a01c0c9755c7b12a3c9/docs/bom.md) · [公开文件目录](https://github.com/JoyandAI/OpenMicroDuck/tree/379e1919541041f23d816a01c0c9755c7b12a3c9)

- **未提供 HUB / 取电小板的配套制造工程**（公开版未提供）  
  所核查目录未见舵机分线 HUB、取电小板对应的 PCB 源文件、制造 BOM 和生产文件；这部分配套电路资料没有随该公开版本提供。  
  依据：[公开文件目录](https://github.com/JoyandAI/OpenMicroDuck/tree/379e1919541041f23d816a01c0c9755c7b12a3c9) · [板卡集成状态](https://github.com/JoyandAI/OpenMicroDuck/blob/379e1919541041f23d816a01c0c9755c7b12a3c9/docs/bom.md)

#### AI 交互

- **未提供中文自由 AI 对话与视觉动作联动流程**（公开版未提供）  
  动作实验室的中文互动为确定性指令解析；关联控制页也未给出自由语音对话、拍照理解、角色音色和 AI 动作调用的成套配置入口。  
  依据：[动作实验室说明](https://github.com/JoyandAI/OpenMicroDuck/blob/379e1919541041f23d816a01c0c9755c7b12a3c9/motion-lab/README.md) · [关联网页控制入口](https://github.com/JoyandAI/microduck/blob/71c6303be7f7e139d9f079cbdc34ef085a372e3f/webd/web/index.html)

#### 动作模型

- **OpenMD 配套清单没有左踢模型**（公开版未提供）  
  专用策略部署说明明确将 kick_left 设为 none。此结论针对 OpenMD 发布配置；关联运行时保留的上游权重，不能只凭文件名当作该 HD1910 配置的已验收策略。  
  依据：[OpenMD 策略配置](https://github.com/JoyandAI/OpenMicroDuck/blob/379e1919541041f23d816a01c0c9755c7b12a3c9/policies/README.md) · [关联运行时权重来源](https://github.com/JoyandAI/microduck/blob/71c6303be7f7e139d9f079cbdc34ef085a372e3f/policies/README.md)

- **OpenMD 清单未发布匹配的轮滑系列模型**（公开版未提供）  
  专用目录列出的六个 ONNX 未含轮滑滑行、轮滑蹲下、轮滑起身或原地旋转的配套发布；演示和关联仓库文件需另外核对权重与配置。  
  依据：[OpenMD 策略配置](https://github.com/JoyandAI/OpenMicroDuck/blob/379e1919541041f23d816a01c0c9755c7b12a3c9/policies/README.md) · [公开文件目录](https://github.com/JoyandAI/OpenMicroDuck/tree/379e1919541041f23d816a01c0c9755c7b12a3c9)

#### 部署与使用

- **所列策略部署仍受特定运行时与按键实现约束**（现有流程限制）  
  策略说明以 robotd 0.13.3 配置为准，并指出按键映射在 padd 二进制中；没有在这份部署流程中提供页面化按键编辑与跨版本迁移步骤。  
  依据：[OpenMD 策略配置](https://github.com/JoyandAI/OpenMicroDuck/blob/379e1919541041f23d816a01c0c9755c7b12a3c9/policies/README.md)

#### 教程与资料

- **完整中英教程交付尚未标记为完成**（尚未完成）  
  项目路线图的 M2 条目仍写教程整理中；从采购、装配到进阶训练的整套双语教程交付尚未标为完成。  
  依据：[项目进展与路线图](https://github.com/JoyandAI/OpenMicroDuck/blob/379e1919541041f23d816a01c0c9755c7b12a3c9/README.md)

### [Pollen Robotics](https://github.com/pollen-robotics/microduck)

Official / XL330

**资料截至 2026-11-18 · 6 项缺项与限制。**

核查版本：[microduck @ 56424ef](https://github.com/pollen-robotics/microduck/tree/56424efe58b7de40efcf3b2d3a5cd169ee83a182) · [microduck_rl @ 0daab16](https://github.com/pollen-robotics/microduck_rl/tree/0daab160d3fb1c2cbaba16a4a19052f36709dd9e)

#### 训练中控与训练流程

- **未提供面向中文新手的独立图形训练中控**（公开版未提供）  
  官方训练主线使用命令创建训练、回放与导出；所核查运行时和训练仓库未提供本项目这类中文配方选择、队列、SSH 环境准备和模型管理工作台。  
  依据：[官方训练工程](https://github.com/pollen-robotics/microduck_rl/blob/0daab160d3fb1c2cbaba16a4a19052f36709dd9e/README.md) · [官方训练文件目录](https://github.com/pollen-robotics/microduck_rl/tree/0daab160d3fb1c2cbaba16a4a19052f36709dd9e)

#### 部署与使用

- **没有面向 HD1910 的直接复刻安装方案**（需要另行适配）  
  公开原版的执行器与部署配置围绕 XL330 路线；改用飞特时，协议、寄存器、舵机参数、标定与控制配置仍需完成对应适配。  
  依据：[官方部署配置](https://github.com/pollen-robotics/microduck/blob/56424efe58b7de40efcf3b2d3a5cd169ee83a182/deploy/robotd.toml) · [官方训练工程](https://github.com/pollen-robotics/microduck_rl/blob/0daab160d3fb1c2cbaba16a4a19052f36709dd9e/README.md)

#### 动作模型

- **原版权重没有直接变成飞特成品步态**（需要另行适配）  
  官方训练说明的执行器模型为 XL330 BAM M6；复制 ONNX 或改舵机名称，不会完成 HD1910 动力学与部署参数的匹配。  
  依据：[官方训练工程](https://github.com/pollen-robotics/microduck_rl/blob/0daab160d3fb1c2cbaba16a4a19052f36709dd9e/README.md)

#### 打印与结构适配

- **未提供 HD1910 舵机结构差异的专用打印改版**（需要另行适配）  
  所核查训练模型和外观资源沿用原版结构；未列出处理 HD1910 舵盘突起、装配干涉及对应板卡固定的飞特专用改件包。  
  依据：[官方训练文件目录](https://github.com/pollen-robotics/microduck_rl/tree/0daab160d3fb1c2cbaba16a4a19052f36709dd9e) · [官方训练工程](https://github.com/pollen-robotics/microduck_rl/blob/0daab160d3fb1c2cbaba16a4a19052f36709dd9e/README.md)

#### 硬件工程与配套

- **没有按整机开源硬件交付全部机械与电控制造资料**（公开版未提供）  
  官方 press kit 将开源范围限定为软件，未把整机机械与电子设计作为开源硬件交付。单独公开的 HAT 项目也不等于整机所有板卡与可编辑机械制造资料均已公开。  
  依据：[官方硬件公开范围](https://pollen-robotics.com/microduck/press-kit/)

#### 教程与资料

- **未提供完整中文 HD1910 个人复刻教程体系**（公开版未提供）  
  所核查官方入口未形成面向飞特版本的中文预算采购、打印装配、板卡接线、镜像中控、本机标定、AI 与自训进阶的一套配套说明。  
  依据：[官方运行时](https://github.com/pollen-robotics/microduck/blob/56424efe58b7de40efcf3b2d3a5cd169ee83a182/README.md) · [官方训练工程](https://github.com/pollen-robotics/microduck_rl/blob/0daab160d3fb1c2cbaba16a4a19052f36709dd9e/README.md)

### [AI-FanGe](https://github.com/AI-FanGe/Microduck-build-tutorial)

Pi Zero 2 W + XL330

**资料截至 2026-11-18 · 9 项缺项与限制。**

核查版本：[Microduck-build-tutorial @ 4967821](https://github.com/AI-FanGe/Microduck-build-tutorial/tree/49678215d0b40529522772a40c06c216390449dd)

#### 训练中控与训练流程

- **没有独立图形训练中控**（公开版未提供）  
  公开的是 MjLab 训练环境和 ONNX 导出脚本；未提供集中管理任务配方、队列、SSH 环境准备、训练曲线和交互评估的独立训练界面。  
  依据：[训练与导出源码](https://github.com/AI-FanGe/Microduck-build-tutorial/tree/49678215d0b40529522772a40c06c216390449dd/mjlab_microduck) · [公开项目目录](https://github.com/AI-FanGe/Microduck-build-tutorial/tree/49678215d0b40529522772a40c06c216390449dd)

#### 机器人中控

- **没有完整机器人图形维护中控**（公开版未提供）  
  首次运行、停机和常用维护以 SSH / 终端命令为主；独立 BNO08x 校准工具未覆盖舵机、模型、相机、固件维护与 AI 的整套中控流程。  
  依据：[硬件与运行教程](https://github.com/AI-FanGe/Microduck-build-tutorial/blob/49678215d0b40529522772a40c06c216390449dd/README.md) · [公开项目目录](https://github.com/AI-FanGe/Microduck-build-tutorial/tree/49678215d0b40529522772a40c06c216390449dd)

#### AI 交互

- **未提供中文语音、视觉理解与 AI 动作调用**（公开版未提供）  
  所读镜像和部署说明围绕 IMU、手柄与 walk.onnx；公开文件未提供自由语音对话、拍照理解、角色音色及 AI 动作调度的集成入口。  
  依据：[硬件与运行教程](https://github.com/AI-FanGe/Microduck-build-tutorial/blob/49678215d0b40529522772a40c06c216390449dd/README.md) · [公开项目目录](https://github.com/AI-FanGe/Microduck-build-tutorial/tree/49678215d0b40529522772a40c06c216390449dd)

#### 部署与使用

- **没有 ZERO 3W + HD1910 的直接运行包**（需要另行适配）  
  该路线使用 Raspberry Pi Zero 2 W、OpenRB-150 和 XL330；其镜像、总线驱动与参数不能直接作为 ZERO 3W 飞特鸭的配套运行包。  
  依据：[硬件与运行教程](https://github.com/AI-FanGe/Microduck-build-tutorial/blob/49678215d0b40529522772a40c06c216390449dd/README.md)

- **舵机编号依赖外部配置工具**（现有流程限制）  
  BOM 将 U2D2 与供电 Hub 列为舵机 ID、波特率和参数配置工具；未给出集成在机器人中控内的直接编号流程。  
  依据：[硬件与运行教程](https://github.com/AI-FanGe/Microduck-build-tutorial/blob/49678215d0b40529522772a40c06c216390449dd/README.md)

- **连接手柄后会主动关闭 Wi-Fi**（现有流程限制）  
  所述无头手柄服务为提高蓝牙稳定性会关闭 Wi-Fi；需要 SSH 时要先关闭手柄再恢复网络，无法按该默认流程同时保留两者。  
  依据：[硬件与运行教程](https://github.com/AI-FanGe/Microduck-build-tutorial/blob/49678215d0b40529522772a40c06c216390449dd/README.md)

#### 打印与结构适配

- **没有 HD1910 配套打印改件**（需要另行适配）  
  其 CAD / 3MF 对应所列 XL330 组装路线；未提供针对 HD1910 舵机形状、安装干涉和本项目板卡布置的配套改件。  
  依据：[硬件与运行教程](https://github.com/AI-FanGe/Microduck-build-tutorial/blob/49678215d0b40529522772a40c06c216390449dd/README.md) · [公开项目目录](https://github.com/AI-FanGe/Microduck-build-tutorial/tree/49678215d0b40529522772a40c06c216390449dd)

#### 硬件工程与配套

- **没有 HD1910 HAT / IMU / HUB 三板工程包**（需要另行适配）  
  电子方案使用 OpenRB-150 与 BNO08x 模块；公开目录没有该飞特三板方案的电路工程、板载固件和整机接线配套包。  
  依据：[硬件与运行教程](https://github.com/AI-FanGe/Microduck-build-tutorial/blob/49678215d0b40529522772a40c06c216390449dd/README.md) · [公开项目目录](https://github.com/AI-FanGe/Microduck-build-tutorial/tree/49678215d0b40529522772a40c06c216390449dd)

#### 动作模型

- **随包模型只有 walk.onnx，缺少多动作配套**（公开版未提供）  
  公开 agents 目录仅有行走模型；未随该运行包提供坐站、捡取、左右踢球、前滚翻和滑轮系列的对应模型及操作流程。  
  依据：[随包模型目录](https://github.com/AI-FanGe/Microduck-build-tutorial/tree/49678215d0b40529522772a40c06c216390449dd/microduck/src/agents) · [硬件与运行教程](https://github.com/AI-FanGe/Microduck-build-tutorial/blob/49678215d0b40529522772a40c06c216390449dd/README.md)

### [Luwu XGO-Duck](https://github.com/LuwuDynamics/xgoduck_hardware)

UNO Q + 1910 / QMI8658A

**资料截至 2026-11-18 · 5 项缺项与限制。**

核查版本：[xgoduck_hardware @ 2150167](https://github.com/LuwuDynamics/xgoduck_hardware/tree/21501676e4413f81480d36b591aedd729412c959) · [xgoduck_runtime_arduino @ 3f9db11](https://github.com/LuwuDynamics/xgoduck_runtime_arduino/tree/3f9db11c376030d234c5b1299862211e87b590f1) · [xgoduck_rl @ a4c78aa](https://github.com/LuwuDynamics/xgoduck_rl/tree/a4c78aacd5eaa724cf246fe12d24bfe1e837fa50)

#### 训练中控与训练流程

- **没有独立的图形训练工作台**（公开版未提供）  
  关联 RL 仓库通过 uv run train、play 和导出命令完成训练链路；公开训练目录未提供独立图形工作台。  
  依据：[训练与模型接口](https://github.com/LuwuDynamics/xgoduck_rl/blob/a4c78aacd5eaa724cf246fe12d24bfe1e837fa50/README.md) · [训练仓库目录](https://github.com/LuwuDynamics/xgoduck_rl/tree/a4c78aacd5eaa724cf246fe12d24bfe1e837fa50)

- **未提供图形化训练服务器与环境部署管理**（公开版未提供）  
  训练说明要求自行准备 CUDA、Python 3.12 与 uv，再手工安装依赖和运行命令；没有页面化 SSH 训练端配置与环境准备入口。  
  依据：[训练与模型接口](https://github.com/LuwuDynamics/xgoduck_rl/blob/a4c78aacd5eaa724cf246fe12d24bfe1e837fa50/README.md)

- **未提供多任务队列和训练成果的一体管理界面**（公开版未提供）  
  任务、检查点、TensorBoard 日志和导出路径在命令及目录中管理；所核查版本没有将配方入队、顺序训练、模型选择与导出收在一套训练界面中。  
  依据：[训练与模型接口](https://github.com/LuwuDynamics/xgoduck_rl/blob/a4c78aacd5eaa724cf246fe12d24bfe1e837fa50/README.md) · [训练仓库目录](https://github.com/LuwuDynamics/xgoduck_rl/tree/a4c78aacd5eaa724cf246fe12d24bfe1e837fa50)

#### 硬件工程与配套

- **不能直接沿用 ZERO 3W 与本项目板卡**（需要另行适配）  
  该方案依赖 Arduino UNO Q、STM32 Bridge、定制扩展板与 QMI8658A。已有 ZERO 3W / HAT / IMU / HUB 时，主控、传感器、接线与安装流程需要重新适配。  
  依据：[硬件及装配说明](https://github.com/LuwuDynamics/xgoduck_hardware/blob/21501676e4413f81480d36b591aedd729412c959/README_CN.md) · [配套运行时与安装](https://github.com/LuwuDynamics/xgoduck_runtime_arduino/blob/3f9db11c376030d234c5b1299862211e87b590f1/README_CN.md)

#### 动作模型

- **模型与打印结构不能直接混用为本项目配套**（需要另行适配）  
  其训练模型使用 XGO-Duck 几何、惯量和 HLS1910 BAM 参数。权重、标定、命令约定与运行时需整套匹配，不能只因舵机名称相近或张量维数相同而替换。  
  依据：[训练与模型接口](https://github.com/LuwuDynamics/xgoduck_rl/blob/a4c78aacd5eaa724cf246fe12d24bfe1e837fa50/README.md) · [硬件及装配说明](https://github.com/LuwuDynamics/xgoduck_hardware/blob/21501676e4413f81480d36b591aedd729412c959/README_CN.md)

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

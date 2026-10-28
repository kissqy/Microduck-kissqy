**简体中文** | [English](MICRODUCK-BUILD-GUIDE.en.md)

# Microduck 飞特版从零复刻：从预算到第一次行走

> [!WARNING]
> **硬件兼容性与商业授权提示**
>
> **非本仓库开源版本的 HAT、IMU、HUB 无法适配本仓库系统，可能导致系统无法正常运行。**
>
> **本仓库未授权任何商业组织。**如发现盗版、冒用或未经授权的商业使用，请联系作者。开源不易，请勿盗用。
>
> [联系作者](https://github.com/kissqy/Microduck-kissqy/blob/main/docs/assets/purchase-wechat-qr.jpg) · [查看分项许可](https://github.com/kissqy/Microduck-kissqy/blob/main/LICENSE)。授权范围以本仓库现有分项许可为准。

Microduck-kissqy 是 kissqy 基于 Pollen Robotics Microduck 0.15.1、已完成实机复刻的个人项目，面向 **Radxa ZERO 3W + 15 个飞特 HD1910 舵机 + 本仓库 HAT / IMU**。这里提供系统镜像、中文机器人中控、配套现成动作模型、自制电路板工程，以及全套打印件和摆盘。**日常使用直接用发布包里的模型，无须自己训练。**

**当前稳定公开版本：机器人中控 R17 V167 / 固件 control.43。** 新手路线按预算、采购、装配和首次行走展开。版本及验证依据见[发布基线](../microduck-hd1910/docs/BASELINE.md)。源码可获取；作者原创部分采用个人非商业许可，官方和第三方部分保留各自许可，见[分项许可](../microduck-hd1910/LICENSE)。

## 按这四个问题开始

| 现在要解决的问题 | 直接入口 |
| --- | --- |
| **我要花多少钱？** | [先看各种方案合计，再看费用明细](https://kissqy.github.io/Microduck-kissqy/build/budget.html) |
| **我要买什么？** | [按型号、数量与购买链接备齐零件](https://kissqy.github.io/Microduck-kissqy/build/shopping.html) |
| **我要怎么装？** | [按部位完成打印、装配与接线](https://kissqy.github.io/Microduck-kissqy/build/assembly.html) |
| **我要让鸭子走起来** | [使用现成模型完成刷机、配网、标定与行走](https://kissqy.github.io/Microduck-kissqy/build/start.html) |

已经装好可直接从第 4 步开始；刷好系统后不知道 IP，先看[配网与查 IP 图文教程](https://kissqy.github.io/Microduck-kissqy/console-guide.html#network)。

## 1. 我要花多少钱？

**成品板路线已列价参考合计为 ¥2823.80**：本体参考采购 ¥2605.80（含忆捷 32GB TF 卡 ¥39.90、山泽双头高速读卡器 ¥22.90）＋HAT ¥119＋IMU ¥99。自焊并预留基础工具的已列价参考区间为 ¥3500.02～3740.02。

TF 卡 32GB 即可；[山泽双头高速读卡器（SD／TF 卡同读）](https://3.cn/393kj-8k?jkl=@I2cIJ7xKJzv@)按 1 个、作者参考价 ¥22.90 计入，已有可复用。缝合怪版整套代打标价 ¥199；成品板＋代打参考合计 **¥3022.80**，无需购买打印机。HUB 与电池接入等待报价项目、运费另计；历史采购数量含备料。[打开预算页，先看总额并补充自己的费用 →](https://kissqy.github.io/Microduck-kissqy/build/budget.html)

## 2. 我要买什么？

先看[在线采购清单](https://kissqy.github.io/Microduck-kissqy/build/shopping.html)，按默认成品板路线准备物品；[历史采购明细](../DUCK-SHOPPING-LIST.md)保留原订单规格和价格依据。参考硬件是 ZERO 3W、15 个 HD1910、摄像头、ToF、扬声器、电池、HAT 与独立躯干 IMU。价格是历史订单参考，预算范围和未计入项目以采购表说明为准。

购买成品 IMU 时不需要准备烧录工具；自己焊板所需的焊接、回流和烧录工具见[工具清单](BUILD-TOOLS.md)。使用其他主控或舵机时，不要默认当前镜像和结构已经适配。

## 3. 我要怎么装？

**[按步骤装配与接线 →](https://kissqy.github.io/Microduck-kissqy/build/assembly.html)** · **[打开 3D 装配参考 →](https://kissqy.github.io/Microduck-kissqy/assembly.html)** 旋转、放大模型，按部位查看关节位置、编号与安装朝向，无须连接机器人。模型用于结构参考；飞特改件与螺丝、走线细节以打印件及硬件说明为准。

下载[全套打印件 · 缝合怪版](../hardware/3d-print-frankenduck/README.md)：36 个 STL、1 个 3MF 项目、5 盘参考摆盘。根据实际打印机与耗材调整配置，TPU 部件使用对应材料配置。整套代打标价 **¥199**；打印方向、电池仓、IMU 安装、滑轮换装、散热和装配细节的优化见上述版本说明。

电池仓有 HUB 组合版和官方式加厚卡扣版；IMU 安装位适配本仓库 IMU。2026-10-21 版增加腿部支撑斜面、去除腿外壳外侧沉孔，并整合无需拆舵机即可换装的脚掌与滑轮结构。滑轮使用 623ZZ 轴承。

本页是装配流程导航，零件说明见打印件页；不把文件数量当成实际装配数量。

### 板卡与供电装配

[HAT / IMU 硬件页](../hardware/README.md)提供工程、采购表和两种接口版本。制作过程分别见[HAT 制作记录](../hardware/HAT-TIMELINE.md)和[IMU 制作记录及视频](../hardware/IMU-TIMELINE.md)。

**作者提供的成品 IMU 已烧录 FT6 固件，到手无需另行烧录；装配后仍需完成本机标定。** 只有自己焊制新板、换芯片或维护升级时，才按[IMU 烧录指南](../hardware/IMU-FIRMWARE.md)操作。给 ZERO 刷系统镜像或升级机器人服务不会烧录外置 IMU。

按[装机注意事项](ASSEMBLY-NOTES.md)配置 5 GHz Wi-Fi，并核对供电连接。HUB 已带 1000 µF 总电源缓冲电容，无需另购；装配时核对电容极性、耐压和安装位置。

## 4. 我要让鸭子走起来

**[打开首次行走六步路线 →](https://kissqy.github.io/Microduck-kissqy/build/start.html)** · [中控图文教程](https://kissqy.github.io/Microduck-kissqy/console-guide.html)

1. 在[系统镜像 R1 页面](releases/public-image-r1.md)下载镜像，用 Armbian Imager 将压缩镜像直接刷入 TF 卡。
2. ZERO 首次启动后，连接 `Microduck-kissqy` 热点，按提示配置家庭 Wi-Fi 和新的登录密码；未自动弹出页面时访问 `http://10.42.0.1:8088`。
3. 从[下载区](../README.md#下载与版本)取得机器人中控 V167，完整解压后运行 `start.cmd`；macOS 使用 `start.command`。
4. 填入本机 ZERO 的 SSH 地址和登录信息。**R1 镜像预装 control.40；通过 V167 中控安装随包固件，更新到 control.43。**

软件包安装、日志与按键说明见[V167 使用指南](../microduck-hd1910/firmware/console/README.zh-CN.md)。网页在线演示使用模拟数据，实际连接需要本地运行中控。

### 标定自己的机器人，再进行运动

逐一核对 **15 个关节的零位、方向、限位，以及 IMU 安装姿态**。参考样机的标定不能直接替代你的机械装配标定。

先检查中控的关节与姿态反馈，再按使用指南完成 HOME、保持和行走。实体手柄的模式切换、轮滑动作及条件，以[V167 按键说明](../microduck-hd1910/firmware/console/README.zh-CN.md)为准。遇到异常先确认发生在哪一环，见[标定与运行问题](MICRODUCK-FAQ.md)。

## 进阶玩法：训练自己的动作

完成现成模型的行走与日常操作后，想探索自己的动作时，再按需安装训练中控。[训练中控 R1.5.27 指南](../microduck-hd1910/training-console/README.zh-CN.md)包含环境准备、训练队列、奖励曲线、仿真评估和模型导出，公开版本提供 14 类动作、35 种任务配方。

训练流程是：准备环境 → 选择任务与参数 → 加入队列并开始 → 仿真评估 → 导出模型 → 核对固件和策略合同后进行实机验证。训练中控和机器人中控是两个独立工具；仿真成功不等于所有装配都能获得相同实机结果。

## 实机演示、验证与反馈

[仓库首页](../README.md)保留作者的 7 段实机演示；具体动作效果以对应实机记录为依据，不将某一视频直接视为所有动作的通用验收。软件发布验证范围见[发布基线](../microduck-hd1910/docs/BASELINE.md)。

遇到问题可在 [GitHub Issues](https://github.com/kissqy/Microduck-kissqy/issues) 提供：硬件配置、中控版本、实际固件标识、发生步骤、日志或视频。若这些资料帮助你完成搭建，欢迎 Star 收藏仓库，后续按同一入口查看更新。

作者：kissqy · [项目原始仓库](https://github.com/kissqy/Microduck-kissqy) · [常见问题](MICRODUCK-FAQ.md) · [完整文档目录](README.md)

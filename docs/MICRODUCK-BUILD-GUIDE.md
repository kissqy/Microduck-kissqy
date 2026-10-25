**简体中文** | [English](MICRODUCK-BUILD-GUIDE.en.md) | [Русский](MICRODUCK-BUILD-GUIDE.ru.md)

# Microduck 飞特版从零复刻教程：材料清单、3D 打印、刷机、标定与训练

Microduck-kissqy 是 kissqy 基于 Pollen Robotics Microduck 0.15.1、已完成实机复刻的个人项目，面向 **Radxa ZERO 3W + 15 个飞特 HD1910 舵机 + 本仓库 HAT / IMU**。这里提供系统镜像、中文机器人中控、独立强化学习训练中控、自制电路板工程，以及全套打印件和摆盘。

**当前稳定公开版本：机器人中控 R17 V167 / 固件 control.43 / 训练中控 R1.5.27。** 本指南更新于 2026-10-23。版本及验证依据见[发布基线](../microduck-hd1910/docs/BASELINE.md)。源码可获取；作者原创部分采用个人非商业许可，官方和第三方部分保留各自许可，见[分项许可](../microduck-hd1910/LICENSE)。

## 先选你的起点

| 现在的情况 | 从哪里开始 |
| --- | --- |
| 从视频看到机器鸭，想自己做一只 | 按下面的采购、打印、硬件、软件顺序开始 |
| 机械和电路已经装好 | 从刷写镜像和标定开始 |
| 已能控制鸭子，想训练自己的动作 | 直接看第 6 步训练 |
| 断网、重启、IMU 或手柄出问题 | [Microduck 常见问题](MICRODUCK-FAQ.md) |

## 1. 准备材料与工具

先看[鸭子采购总清单](../DUCK-SHOPPING-LIST.md)，分别准备鸭子本体、PCB 与工具。参考硬件是 ZERO 3W、15 个 HD1910、摄像头、ToF、扬声器、电池、HAT 与独立躯干 IMU。价格是历史订单参考，预算范围和未计入项目以采购表说明为准。

焊接、回流和烧录工具见[工具清单](BUILD-TOOLS.md)。使用其他主控或舵机时，不要默认当前镜像和结构已经适配。

## 2. 打印零件并装配机械结构

下载[全套打印件 · 缝合怪版](../hardware/3d-print-frankenduck/README.md)：36 个 STL、1 个 3MF 项目、5 盘参考摆盘。根据实际打印机与耗材调整配置，TPU 部件使用对应材料配置。

电池仓有 HUB 组合版和官方式加厚卡扣版；IMU 安装位适配本仓库 IMU。2026-10-21 版增加腿部支撑斜面、去除腿外壳外侧沉孔，并整合无需拆舵机即可换装的脚掌与滑轮结构。滑轮使用 623ZZ 轴承。

本页是装配流程导航，零件说明见打印件页；不把文件数量当成实际装配数量。

## 3. 准备 HAT、IMU 与供电

[HAT / IMU 硬件页](../hardware/README.md)提供工程、采购表和两种接口版本。制作过程分别见[HAT 制作记录](../hardware/HAT-TIMELINE.md)和[IMU 制作记录及视频](../hardware/IMU-TIMELINE.md)。

**自制 IMU 需要单独烧录 STM32 FT6 固件。** 给 ZERO 刷系统镜像或升级机器人服务不会烧录 IMU；接线、固件下载与步骤统一见[IMU 烧录指南](../hardware/IMU-FIRMWARE.md)。

按[装机注意事项](ASSEMBLY-NOTES.md)配置 5 GHz Wi-Fi，并在总进电口并联 1000 µF 缓冲电容；电容极性、耐压和安装位置以该页说明为准。

## 4. 刷写系统镜像并连接中文中控

1. 在[系统镜像 R1 页面](releases/public-image-r1.md)下载镜像，用 Armbian Imager 将压缩镜像直接刷入 TF 卡。
2. ZERO 首次启动后，连接 `Microduck-kissqy` 热点，按提示配置家庭 Wi-Fi 和新的登录密码；未自动弹出页面时访问 `http://10.42.0.1:8088`。
3. 从[下载区](../README.md#下载与版本)取得机器人中控 V167，完整解压后运行 `start.cmd`；macOS 使用 `start.command`。
4. 填入本机 ZERO 的 SSH 地址和登录信息。**R1 镜像预装 control.40；通过 V167 中控安装随包固件，更新到 control.43。**

软件包安装、日志与按键说明见[V167 使用指南](../microduck-hd1910/firmware/console/README.zh-CN.md)。网页在线演示使用模拟数据，实际连接需要本地运行中控。

## 5. 标定自己的机器人，再进行运动

逐一核对 **15 个关节的零位、方向、限位，以及 IMU 安装姿态**。参考样机的标定不能直接替代你的机械装配标定。

先检查中控的关节与姿态反馈，再按使用指南完成 HOME、保持和行走。实体手柄的模式切换、轮滑动作及条件，以[V167 按键说明](../microduck-hd1910/firmware/console/README.zh-CN.md)为准。遇到异常先确认发生在哪一环，见[标定与运行问题](MICRODUCK-FAQ.md)。

## 6. 训练自己的动作并部署到实机

普通使用可以直接使用发布包里的模型，训练中控按需安装。[训练中控 R1.5.27 指南](../microduck-hd1910/training-console/README.zh-CN.md)包含环境准备、训练队列、奖励曲线、仿真评估和模型导出，公开版本提供 14 类动作、35 种任务配方。

训练流程是：准备环境 → 选择任务与参数 → 加入队列并开始 → 仿真评估 → 导出模型 → 核对固件和策略合同后进行实机验证。训练中控和机器人中控是两个独立工具；仿真成功不等于所有装配都能获得相同实机结果。

## 实机演示、验证与反馈

[仓库首页](../README.md)保留作者的 7 段实机演示；具体动作效果以对应实机记录为依据，不将某一视频直接视为所有动作的通用验收。软件发布验证范围见[发布基线](../microduck-hd1910/docs/BASELINE.md)。

遇到问题可在 [GitHub Issues](https://github.com/kissqy/Microduck-kissqy/issues) 提供：硬件配置、中控版本、实际固件标识、发生步骤、日志或视频。若这些资料帮助你完成搭建，欢迎 Star 收藏仓库，后续按同一入口查看更新。

作者：kissqy · [项目原始仓库](https://github.com/kissqy/Microduck-kissqy) · [常见问题](MICRODUCK-FAQ.md) · [完整文档目录](README.md)

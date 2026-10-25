**简体中文** | [English](public-image-r1.en.md) | [Русский](public-image-r1.ru.md)

# 🦆 Microduck 一键系统镜像 R1

**刷入镜像，连接 Wi-Fi，打开中控，让你的小鸭动起来！**

这是基于 Pollen Robotics 官方 Microduck 0.15.1 制作的 Radxa ZERO 3W 整合系统镜像，已经预装本项目的飞特 HD1910 适配固件、机器人服务和运动模型。**用户不需要从源码编译或逐项安装 Zero 端软件。**

> ✅ **已完成一次实体 Zero 重刷验收**：镜像启动、首次热点配网、连接家庭 Wi-Fi、SSH、机器人总线通信及 R17 中控识别正常。不同硬件的实际运动与各模型效果仍需自行验证。

## 🚀 三步上手

**① 刷入系统**

下载本 Release 的 `microduck-zero3w-0.15.1-R1.img.xz`。

推荐 **[Armbian Imager 官方下载](https://imager.armbian.com/)**（也可查看 [GitHub 安装包](https://github.com/armbian/imager/releases)）。打开软件，选择自定义镜像和 TF 卡，直接刷写即可；**不需要手动解压 `.img.xz`，Armbian Imager 会自动解压。**

**② 手机连接热点，配置家庭 Wi-Fi**

将 TF 卡插入 Radxa ZERO 3W 开机，连接热点：

- 名称：`Microduck-kissqy`
- 密码：`12345678`

手机出现配网提示后，填写家庭 Wi-Fi 与新的系统登录密码；若没有自动弹出，请打开 `http://10.42.0.1:8088`。

**③ 打开中文中控**

电脑运行 Microduck R17 中控，连接 Zero，查看摄像头、3D 姿态、关节和 IMU 状态。使用实体手柄前，**先核对自己装配的 15 个关节零位、方向、限位与 IMU 安装，再执行 HOME、保持和运动。**

## 📦 版本

| 项目 | 版本 |
| --- | --- |
| 官方软件基线 | Microduck 0.15.1 |
| 机器人适配固件 | V164 · control.40 |
| 机器人中控 | R17 V164（独立软件包单独提供） |
| 训练中控 | R1.5.27（独立软件包单独提供） |
| 首次 Wi-Fi 配网 | R5 |
| 硬件 | Radxa ZERO 3W + 适配的 HD1910 / IMU 装配 |

系统镜像自带 Zero 端固件与模型；**Windows 上的中控、训练中控是独立工具**，不等于已经安装在 Windows 上。仓库在线演示是旧版模拟数据页面，不能用于控制实体机器。

## 📥 镜像校验

```text
microduck-zero3w-0.15.1-R1.img.xz
SHA256: 75da978b5d56acd9e4146256431732381de84523bb683e4ab7ac9f0580a7bce5
```

## ❤️ 从电阻开始的个人机器人项目

项目包含硬件电路与 PCB、HD1910 适配、R17 中控、训练中控和自训练动作模型。代码由作者借助 ChatGPT 协作完成，期待它能降低新手了解机器人开发的门槛。

仓库地址：<https://github.com/kissqy/Microduck-kissqy>

**授权提示：** 作者拥有并有权单独授权的原创部分仅供个人学习、研究和非商业使用；商业使用前请取得作者书面授权。原官方固件的 Apache-2.0、第三方程序及几何/模型素材各自遵守原许可证，个人限制不覆盖第三方权利。详细范围见仓库 [分项许可证](../../microduck-hd1910/LICENSE) 和 [第三方说明](../../microduck-hd1910/docs/THIRD-PARTY.md)。

**发布前提：** 软件镜像是已验证的参考环境，不代表其他装配机械限位与电机方向可直接照搬；运动风险由操作者现场确认。

# Microduck 一键系统镜像 R2

当前公开发布线为 **R2 / Microduck Console Studio V260 / control.102 / 配网 R10**，官方软件基线为 **Microduck 0.15.1**，适用 Radxa ZERO 3W，内置 11 个运行模型。

[下载 R2 镜像与查看发布说明](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v260) · [直接下载镜像 .img.xz](https://github.com/kissqy/Microduck-kissqy/releases/download/console-studio-v260/microduck-kissqy-zero3w-R2.img.xz) · [V260 中控、固件与源码说明](https://github.com/kissqy/Microduck-kissqy/blob/main/versions/v260/README.md)

镜像文件名：`microduck-kissqy-zero3w-R2.img.xz`。SHA256：`dc300280ea4407679ce480fcc0ae58b3ffab6684785ab17582a9e3caa9685314`。

**从 V167 升级到 V260 不需要重刷系统或 TF 卡。** 下载并完整解压 V260 中控，连接 ZERO 后，直接在 V260 中控内安装随包固件即可。R2 镜像用于新装系统或需要重刷时。

使用 Armbian Imager 选择自定义镜像，可直接写入 `.img.xz`，无需手动解压。R2 已预装 V260 / control.102，电脑端使用配套 V260 中控；无需先通过 V167 安装旧固件。

开机会等待网卡与网络服务就绪，再尝试已保存的 Wi-Fi；没有可连接网络或连接失败时开启配网热点。运行中断网不会自动切换热点，可通过中控手动开启。

- 热点：`Microduck-kissqy`
- 热点密码：`12345678`
- 配网页面：`http://10.42.0.1:8088/`

连接后核对实际固件版本、本机关节零位、方向、限位和 IMU 标定。普通使用不需要下载训练中控或重新训练动作。

本次仅同步发布与教程入口，没有新增实机验收；原 Known-Good 记录不变。V260 实机功能验收仍按独立版本说明进行。

[保留的 R1 历史说明](public-image-r1.md) · [R1 历史发布页](https://github.com/kissqy/Microduck-kissqy/releases/tag/public-image-r1) · [回到首次行走教程](../build/start.html)

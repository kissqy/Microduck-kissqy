**简体中文** | [English](README.en.md)

# Microduck HD1910 · 原路径兼容目录

从 [versions/](../versions/) 选择当前及历史版本。本目录保留原 V167 源码与配套文档。

基于 Microduck 官方 **0.15.1** 的飞特 HD1910 适配，包含机器人固件、R17 机器人中控和独立训练中控。参考硬件：Radxa ZERO 3W、官方骨架、15 个 HD1910。社区个人项目，与 Pollen Robotics 无官方隶属关系。

**源码公开、分项许可；明确适用个人非商业条款的原创部分限个人非商业使用，商业及组织用途须书面授权。其余内容保留各自许可，范围见 [LICENSE](LICENSE)。**

**R3 系统镜像 · V315 电脑中控 · 机器人固件 `control.127`** · [下载 R3 镜像（.img.xz）](https://github.com/kissqy/Microduck-kissqy/releases/download/console-studio-v313/microduck-kissqy-zero3w-R3.img.xz) · [百度网盘](https://pan.baidu.com/s/1mGu_SiBGiYlzmvqPsVpfxw?pwd=km52)（提取码 `km52`） · [下载 V315 中控（.zip）](https://github.com/kissqy/Microduck-kissqy/releases/download/console-studio-v313/Microduck-Console-Studio-V315.zip) · [累计更新与安装图解](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v313)

**作者成品 IMU 已预烧录 FT6，到手无需另行烧录，安装后仍需本机标定。** 自焊新板、换芯片或维护升级再看 [STM32 FT6 下载与烧录指南](../hardware/IMU-FIRMWARE.md)；ZERO 机器人服务固件不会烧录外置 IMU。


> **R3 系统镜像 · V315 电脑中控 · 机器人固件 `control.127`**
>
> 可通过 HAT 直接编号和设置中位，逐设备通信卡片会显示最近一次超时耗时。
>
> [V315 中控专页](https://kissqy.github.io/Microduck-kissqy/console-v315/) · [更新说明与下载](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v313)


## 当前发布与独立源码

| 内容 | 版本 | 源码或发布位置 |
| --- | --- | --- |
| 机器人固件与设备服务 | Microduck 0.15.1 · control.127 | [随包固件与原生源码](../versions/v315/README.md) |
| 机器人中控 | Studio V315 | [下载中控 ZIP](https://github.com/kissqy/Microduck-kissqy/releases/download/console-studio-v313/Microduck-Console-Studio-V315.zip) |
| 公开系统镜像 | R3 · 配网 R10 | [下载系统镜像](https://github.com/kissqy/Microduck-kissqy/releases/download/console-studio-v313/microduck-kissqy-zero3w-R3.img.xz) |
| 训练中控 | R1.5.27 | [training-console/](training-console/) |
| 历史机器人固件与中控 | V167 / control.43 | [V167 固件](../versions/v167/microduck-hd1910/firmware/) · [V167 中控](../versions/v167/microduck-hd1910/firmware/console/) |

V260 源码归入 `versions/v260/`；V167 源码与构建资源归入 `versions/v167/`，保留原有内部相对路径。本兼容目录仍保留 V167／control.43。最新与历史验收分别记录在[发布基线](docs/BASELINE.md)。

## 下载与使用

1. [下载系统镜像 R3](https://github.com/kissqy/Microduck-kissqy/releases/download/console-studio-v313/microduck-kissqy-zero3w-R3.img.xz)，用 [Armbian Imager](https://imager.armbian.com/) 刷入 TF 卡。
2. 开机未能连接已保存 Wi-Fi 时，连接 `Microduck-kissqy` 热点（密码 `12345678`），设置家庭 Wi-Fi 和新的系统登录密码。未自动弹出页面时访问 `http://10.42.0.1:8088`。
3. [下载 V315 中控 ZIP](https://github.com/kissqy/Microduck-kissqy/releases/download/console-studio-v313/Microduck-Console-Studio-V315.zip)，完整解压后运行 `start.cmd`；macOS/Linux 运行 `bash start.command`。页面地址为 `http://127.0.0.1:8090`。
4. 填写自己的 `用户名@机器人IP` 和 SSH 登录信息，连接后核对本机标定，按 **HOME → 保持 → 行走** 使用。镜像已预装机器人服务；已有系统需要升级时，可在中控“系统维护”安装随包固件。
5. 需要训练时，[下载训练中控 R1.5.27](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/versions/v167/release-assets/Microduck-Training-Studio-R1.5.27.zip)，运行 `start-training.cmd` 或 `bash start-training.command`，打开 `http://127.0.0.1:8092`。

训练使用 NVIDIA GPU + Linux/WSL2，先安装 git 和 [uv](https://docs.astral.sh/uv/getting-started/installation/)。首次准备环境会下载固定版本的训练引擎和依赖。当前提供 14 类动作、35 种任务配方；具体使用见 [训练中控说明](training-console/README.zh-CN.md)。

## 从源码使用

- V315 · [中控与原生固件源码](../versions/v315/README.md)
- V260 中控与固件：[独立源码](https://github.com/kissqy/Microduck-kissqy/tree/main/versions/v260)，资源恢复与构建见[版本说明](https://github.com/kissqy/Microduck-kissqy/blob/main/versions/v260/README.md)。
- 历史 V167 中控启动入口（从仓库根目录）：`versions/v167/microduck-hd1910/firmware/console/start.cmd` 或 `start.command`。
- 训练中控启动入口：`training-console/start-training.cmd` 或 `start-training.command`。
- 历史 V167 固件编译：[BUILD.md](../versions/v167/microduck-hd1910/docs/BUILD.md)。编译不是日常使用的前置要求。
- 发布版本与验证范围：[BASELINE.md](docs/BASELINE.md)。完整来源及校验记录：[PUBLICATION-MANIFEST.json](PUBLICATION-MANIFEST.json)。
- 原创归属与使用：[软件与自训模型权利说明](docs/SOFTWARE-MODEL-RIGHTS.md) · [逐模型来源](docs/MODEL-PROVENANCE.md)。
- 许可与第三方来源：[LICENSE](LICENSE) · [THIRD-PARTY.md](docs/THIRD-PARTY.md)。

[历史 R1 镜像](https://github.com/kissqy/Microduck-kissqy/releases/tag/public-image-r1) · [V167 中控 ZIP](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/versions/v167/release-assets/Microduck-Console-R17-V167.zip) · [control.43 固件说明](../versions/v167/release-assets/README.md)。每台机器人都需要核对自己的关节零位、方向、限位和 IMU；本次源码公开不扩大原有模型的实机验收范围。

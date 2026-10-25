**简体中文** | [English](README.en.md) | [Русский](README.ru.md)

# Microduck HD1910

基于 Microduck 官方 **0.15.1** 的飞特 HD1910 适配，包含机器人固件、R17 机器人中控和独立训练中控。参考硬件：Radxa ZERO 3W、官方骨架、15 个 HD1910。社区个人项目，与 Pollen Robotics 无官方隶属关系。

**源码公开；作者原创部分仅供个人非商业使用。第三方内容保留原许可证，范围见 [LICENSE](LICENSE)。**

**已有编译好的固件。** control.43 已随 V167 中控提供；系统镜像 R1 仍预装 control.40；单独使用见[固件安装与下载说明](../release-assets/README.md)。

**自制 IMU 板单独刷 STM32 FT6：** [下载与烧录指南](../hardware/IMU-FIRMWARE.md)；control.43 安装到 ZERO，不会烧录外置 IMU。

## 当前版本与源码

| 内容 | 当前版本 | 源码位置 |
| --- | --- | --- |
| 机器人固件与设备服务 | 官方 0.15.1 · control.43 · API40 | [firmware/](firmware/) |
| 机器人中控 | R17 V167（1.0.167） | [firmware/console/](firmware/console/) |
| 训练中控 | R1.5.27 | [training-console/](training-console/) |
| 公开系统镜像 | Public Image R1 · 首次配网 R5 | [镜像发布页](https://github.com/kissqy/Microduck-kissqy/releases/tag/public-image-r1) |

V167 中控配套已编译的 **control.43** 固件。更新：**修复鸭身抖动的问题**。当前 `firmware/BUILD.json` 与 V167 随包固件的 BUILD 记录一致，两个中控的程序源码与各自 ZIP 同步。

## 下载与使用

1. [下载系统镜像 R1](https://github.com/kissqy/Microduck-kissqy/releases/download/public-image-r1/microduck-zero3w-0.15.1-R1.img.xz)，用 [Armbian Imager](https://imager.armbian.com/) 刷入 TF 卡。
2. 首次开机连接 `Microduck-kissqy` 热点（密码 `12345678`），设置家庭 Wi-Fi 和新的系统登录密码。未自动弹出页面时访问 `http://10.42.0.1:8088`。
3. [下载机器人中控 V167](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/release-assets/Microduck-Console-R17-V167.zip)，完整解压后运行 `start.cmd`；macOS/Linux 运行 `bash start.command`。页面地址为 `http://127.0.0.1:8090`。
4. 填写自己的 `用户名@机器人IP` 和 SSH 登录信息，连接后核对本机标定，按 **HOME → 保持 → 行走** 使用。镜像已预装机器人服务；已有系统需要升级时，可在中控“系统维护”安装随包固件。
5. 需要训练时，[下载训练中控 R1.5.27](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/release-assets/Microduck-Training-Studio-R1.5.27.zip)，运行 `start-training.cmd` 或 `bash start-training.command`，打开 `http://127.0.0.1:8092`。

训练使用 NVIDIA GPU + Linux/WSL2，先安装 git 和 [uv](https://docs.astral.sh/uv/getting-started/installation/)。首次准备环境会下载固定版本的训练引擎和依赖。当前提供 14 类动作、35 种任务配方；具体使用见 [训练中控说明](training-console/README.zh-CN.md)。

## 从源码使用

- 机器人中控启动入口：`firmware/console/start.cmd` 或 `start.command`。
- 训练中控启动入口：`training-console/start-training.cmd` 或 `start-training.command`。
- 固件编译：[BUILD.md](docs/BUILD.md)。编译不是日常使用的前置要求。
- 发布版本与验证范围：[BASELINE.md](docs/BASELINE.md)。完整来源及校验记录：[PUBLICATION-MANIFEST.json](PUBLICATION-MANIFEST.json)。
- 许可与第三方来源：[LICENSE](LICENSE) · [THIRD-PARTY.md](docs/THIRD-PARTY.md)。

每台机器人都需要核对自己的关节零位、方向、限位和 IMU。程序、模型和原有控制实现按交付包同步；本次源码公开不扩大原有模型的实机验收范围。

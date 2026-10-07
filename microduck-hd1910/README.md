# Microduck HD1910

基于 Microduck 官方 0.15.1 的飞特 HD1910 适配，包含机器人固件、R17 机器人中控和训练中控。适用参考硬件：Radxa ZERO 3W、官方骨架、15 个 HD1910。社区个人项目，与 Pollen Robotics 无官方隶属关系。

**源码公开；作者原创部分仅供个人非商业使用。第三方内容保留原许可证，范围见 [LICENSE](LICENSE)。**

## 当前版本

| 内容 | 版本 / 源码位置 |
| --- | --- |
| 固件与设备服务 | R17 v1.0.146 · control.29 · API40；`firmware/` |
| 机器人中控 | R17 v1.0.146；`firmware/console/` |
| 训练中控 | R1.5.17；`training-console/` |

## 使用

1. 电脑安装 Python 3.10+ 和系统 OpenSSH 客户端；Windows 推荐 Python 3.12。
2. 下载本仓库 Releases 中的机器人中控 ZIP，解压后运行 `start.cmd`；macOS/Linux 运行 `bash start.command`。页面地址：`http://127.0.0.1:8090`。
3. 填写自己的 `用户名@机器人IP` 和 SSH 登录信息，连接后在“系统维护”安装随包固件。中控已经带固件，独立固件 ZIP 是同一载荷。
4. 使用本机标定，按 **HOME → 保持 → 行走** 操作。包内标定为样机参考，每台机器人需核对自己的标定。
5. 训练中控：Windows 运行 `start-training.cmd`；Linux 运行 `bash start-training.command`，打开 `http://127.0.0.1:8092`。
6. 本机训练使用 NVIDIA GPU + Linux/WSL2，先安装 git 和 [uv](https://docs.astral.sh/uv/getting-started/installation/)。首次“安装训练环境”下载固定版本引擎和依赖；SSH 服务器可用“部署并准备环境”。选择任务后“加入队列 → 开始训练”，完成后导出 ONNX/ZIP。

直接从源码运行时，以上入口分别位于 `firmware/console/` 和 `training-console/`。固件是机器人服务升级包，使用前机器人需已有可启动的 Linux、SSH 和对应硬件环境；本包不包含整盘系统镜像。

## 说明

- 新联合 Walk 为 9600 轮，统一基础缩放 0.9、头滤波 0.5、腿滤波 0.7；LB 独立起身老师保留。详见 [当前固件说明](firmware/README-R17.zh-CN.md)。
- 本次是发布资料整理；已交付程序和模型保持原版本。真实步态、背部起身效果以实机记录为准。
- [VS Code 上传 GitHub](docs/PUBLISH.md) · [从源码编译](docs/BUILD.md) · [版本与验证范围](docs/BASELINE.md) · [第三方来源](docs/THIRD-PARTY.md)

上游：[Microduck](https://github.com/pollen-robotics/microduck) · [microduck_rl](https://github.com/pollen-robotics/microduck_rl)

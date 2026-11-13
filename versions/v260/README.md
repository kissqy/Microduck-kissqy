# Microduck Console Studio V260 · 独立发布线

配套机器人固件为 **control.102**，官方软件基线为 **0.15.1**，开机配网为 **R10**，运行模型为 **11 个 ONNX**。

本目录和 `release/v260` 分支独立保存 V260。仓库原有 **V167/control.43** 源码、运行包和系统镜像 R1 保留原样。公共入口优先展示 R2 / V260，旧版历史入口仍可访问；本次发布不触发旧线自动升级。

## 四类文件分开下载

请在发布页的 **Assets** 中按下表文件名选择。若未列出对应 ZIP，表示该附件尚未提供；下表入口统一打开发布页，避免跳转到不存在的附件。中控与固件源码也可直接浏览下方目录。

| 内容 | 下载 | 用途 |
| --- | --- | --- |
| 中控运行包 | [Microduck-Console-Studio-V260.zip](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v260) | 电脑端完整解压运行；已含配套固件 |
| 中控源码 | [Microduck-Console-Source-V260.zip](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v260) · [浏览源码](console/) | Python、网页、启动工具和验证代码；资源按清单恢复 |
| ZERO 固件运行包 | [Microduck-Firmware-V260-control102.zip](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v260) | 内部 tar.gz 与 V260 随包固件逐字节一致，可由 V260 中控导入 |
| ZERO 固件源码 | [Microduck-Firmware-Source-V260-control102.zip](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v260) · [浏览源码](firmware/) | Rust 工作区、安装与配网源码、模型配置及构建说明 |

[文件 SHA256](SHA256SUMS.txt) · [完整发布页](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v260)

这四项均为 V260 配套软件，不是 TF 卡系统镜像，也不是 STM32 IMU 固件。不要将 V260 固件交给 V167 中控导入。普通使用者下载完整中控即可，无须另下源码或自行训练。

## 使用

完整解压中控运行包。Windows 运行 `start.cmd`；macOS/Linux 运行 `bash start.command`，通过 SSH 连接自己的 Zero。需要使用本版本功能时，在 V260 中控中安装本版随包固件；安装会清理已撤下的火烈鸟动作与对应旧模型，按原策略保留其他用户模型和有效本机标定。

开机等待网卡与网络服务就绪，尝试已保存 Wi-Fi；未能连接时开启配网热点。运行中断网不自动切换热点。热点为 `Microduck-kissqy`，密码 `12345678`，配网页面 `http://10.42.0.1:8088`。

## 源码与验证

- [中控源码说明](console/README-SOURCE.md)：先按资源清单恢复大型运行资源，再运行源码。
- [固件源码说明](firmware/README-V260.md)：说明源码冻结点、原生补丁、交叉编译和资源恢复方式。
- 发布运行包沿用已交付 V260 的原始字节；源码归档为独立交付，不把旧 V167 源码改名冒充新版。
- 核对了核心源码哈希和资源恢复。GameSir 桥接源码交叉重编译与随包程序逐字节一致。
- V260 原有 109 项 Python、5 组前端回归记录保留。本次没有新的整机运动、热点或全 Rust 工作区验收，不据此更新实机 Known-Good。

## 许可

沿用仓库分项许可，见 [许可范围原文](LICENSE-SCOPE.txt)。原文的 `firmware/console/` 对应此独立版本的 `console/`；固件 Rust 工作区保留 [Apache-2.0](firmware/LICENSE)，原创部分与第三方内容各自遵循原有声明，不撤销此前有效授权。

## 项目状态

本次完成 V260 独立源码保存及公共入口同步，运行包是否已发布以 Assets 实际附件为准。原 V167 Known-Good 与历史入口保留；没有新增实机验收。下一步唯一主任务：补齐并确认四类发布附件可下载，再进行参考卡上的 V260 功能验收。

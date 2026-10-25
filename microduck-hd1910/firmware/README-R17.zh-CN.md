**简体中文** | [English](README-R17.en.md) | [Русский](README-R17.ru.md)

# Microduck control.43 固件与 R17 V167 中控

本目录是 **control.43** 固件源码，基于官方 Microduck **0.15.1**，IPC API 为 **40**。配套机器人中控为 **R17 V167**。

V167 更新：修复鸭身抖动的问题。当前顶层 [BUILD.json](BUILD.json) 来自真实安装载荷，与 V167 随包 BUILD 逐字节一致。

- [已编译 control.43 下载与安装](../../release-assets/README.md)
- [机器人中控启动与使用](console/README.zh-CN.md)
- [固件配置、模型与设备安装说明](packaging/README.zh-CN.md)
- [新机器从源码编译](../docs/BUILD.md)
- [当前发布版本与验收范围](../docs/BASELINE.md)
- [V167 构建与测试记录](BUILDING-V167.md)
- [无需升级系统的 Armbian 启动配置修复](docs/robot/armbian-boot-config.md)
- [上游工作区开发说明](CONTRIBUTING.md)

Rust、Python、网页、模型与原生程序按对应交付文件同步；本次只整理源码公开和版本索引。每台机器人仍需使用并核对自己的关节、方向、限位和 IMU 标定。

**简体中文** | [English](README153.en.md) | [Русский](README153.ru.md)

# v153 验证记录

本次原生 Rust 代码未改变，复用已构建并核对全部源码 SHA 的 control.32 二进制。v152 的原生构建与 29 项启动测试记录保留为历史证据，不将旧包的启动成功视为已验证。

新增发布验证：

- `python-integrity153.log`：23 项 ELF、复制完整性与安装次序测试。
- `python-diagnostic153.log`：5 项只读诊断测试。
- `python-connection153.log`：4 项中控连接恢复、5 项诊断，以及 20 项原始遥测与 SSH 转发回归；诊断与前一份日志为相同测试，不重复计数。
- `frontend-startup153.log`、`frontend-gamepad153.log`：启动错误、诊断下载与手柄修复界面回归。
- `reproduction153.json`：新旧 ARM 程序各五个模型使用完整库通过，截断库两个 SIGBUS 对照。
- `baseline-restored153.json`：原始归档 SHA、127 个文件原始 SHA 和恢复后读回核对。
- `release-audit153.json`：最终固件、Console ZIP 与源码 tar 的内容回读及生产固件导入检查。

QEMU 验证包含加载及首次推理，不包含真机 UART 或运动。真机断电重启、温度与实际行走尚未测试。

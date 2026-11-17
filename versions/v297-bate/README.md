**简体中文** | [English](README.en.md)

# Microduck Console Studio V297 BATE

独立中控测试版，配套 **control.102 / R2 / R10**。本目录用于本版说明与文件入口。

| 内容 | 入口 |
| --- | --- |
| 独立中控介绍与编号方法 | [V297 BATE 专页](https://kissqy.github.io/Microduck-kissqy/console-bate/) |
| 完整更新说明 | [新增功能、修复与使用方法](../../docs/releases/console-studio-v297-bate.md) |
| 中控运行包 · 42.2 MB | [Microduck-Console-Studio-V297-BATE.zip](https://github.com/kissqy/Microduck-kissqy/releases/download/console-studio-v297-bate/Microduck-Console-Studio-V297-BATE.zip) · [发布说明](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v297-bate) |
| 本版文件目录 | [release-assets/](release-assets/) |
| 中控源码 | 中控运行包包含 Python 与前端源码；完整解压后即可查看。独立源码附件以 Release 实际上传内容为准 |
| control.102 固件与源码 | [V260 固件说明](../v260/README.md) · [固件源码](../v260/firmware/) |
| V260 稳定发布 | [V260 / R2](../v260/) |

已有 R2 / control.102 用户只需更换电脑端中控。完整解压后，Windows 运行 `start.cmd`，macOS / Linux 运行 `bash start.command`，浏览器打开 `http://127.0.0.1:8090`。

未编号或疑似重号舵机一次只接一颗；确认编号不同后可串联。右腿 10–14、左腿 20–24、颈头 30–34，ID 200 为 IMU。单颗中位校准后重新标定相应关节。

GitHub 自动生成的 Source code 仅是仓库快照，不等于完整中控运行包。

本版已有 35 项本地受控回归通过记录，实机验收尚未完成；既有实机 Known-Good 记录不变。下一步唯一主任务：参考卡上的 V297 BATE 实机验收，重点检查测试、编号和缺设备时的模式切换。

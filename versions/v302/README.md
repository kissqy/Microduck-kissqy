**简体中文** | [English](README.en.md)

# Microduck Console Studio V302 Beta

**只更新中控，直接复用 control.102 固件与原有 11 个 ONNX；R2 / R10 不变。** 已有 control.102 用户无需重装固件或重刷 TF 卡。

| 内容 | 入口 |
| --- | --- |
| 中控功能、更新与编号方法 | [V302 专页](https://kissqy.github.io/Microduck-kissqy/console-v302/) |
| 运行包 · 42.3 MB | [Microduck-Console-Studio-V302.zip](https://github.com/kissqy/Microduck-kissqy/releases/download/console-studio-v302/Microduck-Console-Studio-V302.zip) |
| 发布说明 | [V302 Release](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v302) · [仓库内更新说明](../../docs/releases/console-studio-v302.md) |
| 文件大小与 SHA256 | [release-assets/](release-assets/) |
| 中控源码 | 运行包内含完整 Python / JavaScript 源码与本地验证记录 |
| 原生固件与源码 | [control.102 说明](../v260/README.md) · [V260 固件源码](../v260/firmware/) |
| 新装系统镜像 | [R2 镜像与稳定固件](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v260) |

关闭旧中控，完整解压；Windows 运行 `start.cmd`，macOS / Linux 运行 `bash start.command`，打开 `http://127.0.0.1:8090`。首次进入编号或硬件测试时会准备独立维护组件，不替换原生动作固件。

V302 优化有效扫描复用、中位校准等待、维护通信会话与进入检查；保留四模式工作台、3D 零位 / HOME 参考、左右标签避让和 IMU 双列布局。

先手动扫描再改号；改变接线、增减设备或重新上电后重新扫描。未编号或可能重号的舵机一次只接一颗。右腿 10–14，左腿 20–24，颈头 30–34；ID 200 是 IMU。中位校准后重新标定相应关节。

本版为 Pre-release，本地回归不等于实机验收，不扩大已有 Known-Good。下一步唯一主任务：Reference Duck / control.102 上验收编号、中位校准与模式切换，并记录实际结果与延迟。

GitHub 自动生成的 Source code 是仓库快照，不能代替完整运行包。

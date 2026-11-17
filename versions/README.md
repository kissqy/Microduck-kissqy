# Microduck 软件版本

在主分支按版本选择中控、固件、源码与运行包，不需要切换分支。

| 版本 | 固件 | 配套镜像 | 版本目录 |
| --- | --- | --- | --- |
| **V297 BATE · 独立测试版** | control.102 | R2 / 配网 R10 | [进入 V297 BATE](v297-bate/) |
| **V260 · 当前发布** | control.102 | R2 / 配网 R10 | [进入 V260](v260/) |
| **V167 · 历史保留** | control.43 | R1（镜像预装 control.40，安装 V167 随包固件后为 control.43） | [进入 V167](v167/) |

V297 BATE 的更新、编号方法和文件入口独立保存在 `v297-bate/`，运行包附件由本版 Release 的 Assets 提供，以实际上传文件为准。已有 R2 / control.102 用户只需更换中控。

V167、V260 的源码与配套说明分别保存在各自目录。运行包从相应版本页下载；V260 的两个运行 ZIP 与 R2 镜像保存在 [Releases](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v260)。源码无需重复下载或上传 ZIP。

独立训练中控 **R1.5.27** 不随机器人中控版本升级，入口见 [训练中控说明](../microduck-hd1910/training-console/README.md)。根目录 `microduck-hd1910/` 仍作为源码兼容位置；旧根 `release-assets/` 已归并到 `versions/v167/release-assets/`，版本选择与下载以本目录为准。

V297 BATE 已有 35 项本地受控回归通过记录，实机验收尚未完成。官方软件基线 Microduck 0.15.1、机器人固件 control.102、R2 / R10 与既有实机 Known-Good 记录保持不变。下一步唯一主任务：参考卡上的 V297 BATE 实机验收，重点检查硬件测试、逐颗编号，以及缺 IMU / 缺舵机时的模式切换。

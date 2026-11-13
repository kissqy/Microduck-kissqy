# Microduck 软件版本

在主分支按版本选择中控、固件、源码与运行包，不需要切换分支。

| 版本 | 固件 | 配套镜像 | 版本目录 |
| --- | --- | --- | --- |
| **V260 · 当前发布** | control.102 | R2 / 配网 R10 | [进入 V260](v260/) |
| **V167 · 历史保留** | control.43 | R1（镜像预装 control.40，安装 V167 随包固件后为 control.43） | [进入 V167](v167/) |

V167、V260 的源码与配套说明分别保存在各自目录。运行包从相应版本页下载；V260 的两个运行 ZIP 与 R2 镜像保存在 [Releases](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v260)。源码无需重复下载或上传 ZIP。

独立训练中控 **R1.5.27** 不随机器人中控版本升级，入口见 [训练中控说明](../microduck-hd1910/training-console/README.md)。根目录原有 `microduck-hd1910/`、`release-assets/` 保留兼容历史链接，新的版本选择以本目录为准。

这次只整理仓库目录与导航，保持发布包、固件、模型和既有实机 Known-Good 记录不变。下一步唯一主任务：参考卡上的 V260 功能验收。

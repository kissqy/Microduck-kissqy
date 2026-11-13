**简体中文** | [English](REPOSITORY-LAYOUT.en.md)

# 仓库目录与版本

## 从版本目录进入

机器人中控、固件及配套下载统一放在 main 的 [versions/](../versions/) 入口下，按 **V167** 与 **V260** 区分，无需切换分支。

| 目录 | 版本与内容 |
| --- | --- |
| [versions/v260/](../versions/v260/) | 当前发布：Studio V260 / control.102 / 系统镜像 R2 / 配网 R10；中控源码在 `console/`，固件源码在 `firmware/`。 |
| [versions/v167/](../versions/v167/) | 历史发布：R17 V167 / control.43；保留 `microduck-hd1910/` 源码和 `release-assets/` 构建资源的原相对结构。R1 镜像原预装 control.40。 |
| `microduck-hd1910/`、`release-assets/` | 原路径兼容位置，供已有文档、下载地址和历史构建使用。新入口统一从版本目录进入。 |
| `microduck-hd1910/training-console/` | 独立训练中控 R1.5.27，版本号不与机器人中控混用。 |
| `hardware/` | 共享的板卡、3D 打印件和硬件资料。 |
| `docs/` | 共享教程与 GitHub Pages 在线演示，演示仍使用其原有版本和模拟数据。 |

V167 的中控源码位于 [microduck-hd1910/firmware/console/](../versions/v167/microduck-hd1910/firmware/console/)，固件位于 [microduck-hd1910/firmware/](../versions/v167/microduck-hd1910/firmware/)。构建说明见 [BUILD.md](../versions/v167/microduck-hd1910/docs/BUILD.md)。保留内部目录深度，是为了让打包脚本和固定基线继续按原相对路径定位。

本次只整理目录与入口，运行包和核心源码沿用原字节，不增加实机 Known-Good 验收结论。下一步唯一主任务仍为参考卡上的 V260 功能验收。

## 为什么还会看到较大的文件

| 内容 | 位置与用途 |
| --- | --- |
| 成品下载 | V260 两个运行 ZIP 与 R2 镜像在 [发布页](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v260)；V167 从 [版本目录](../versions/v167/) 下载。旧根目录下载地址保留兼容。 |
| 训练配置与参考数据 | `microduck-hd1910/training-console/data/`，供独立训练中控查看参数；V167 冻结源码也保留原训练资料。 |
| 在线演示资源 | `docs/`，GitHub Pages 从此目录发布；3D 资源和训练参数副本为演示独立运行所需。 |
| 构建基线 | `versions/v167/release-assets/build-baselines/`，一份固定 V164 ZIP，用于复现 V167 安装包；旧位置继续兼容。 |
| 历史参考证据 | `versions/v167/microduck-hd1910/firmware/verification/official-reference/`，固定上游来源、模型和原始抓取记录。 |

Git 对完全相同内容使用相同文件对象；兼容路径与版本目录引用同一份已有文件对象，不需要重新上传。完整目录 ZIP 与本地检出则会分别收录两个路径。

## 2026-11-12 源码清理

公开 V167/control.43 源码移除了 41 个旧版一次性工具和 1 个未编译的试验模块；59 份完全相同的模型资料改由 `prepare-V167.py` 从 `policies/` 按哈希恢复。受控源码树共移除 101 个文件、约 3.99 MiB；这不缩减已发布运行包，也不清除 Git 历史。

完整清单、验证和原有测试失配见[源码清理审计](../versions/v167/microduck-hd1910/docs/SOURCE-CLEANUP-20261112.md)。已发布中控与固件包继续保持原版本和字节。

## 此前整理

- 合并两套完全相同的官方参考快照，保留原始文件与来源记录；旧路径的 SHA256 对照保留在 `REFERENCE-LAYOUT.json`。
- 删除左脚踢球模型的重复别名目录，文档索引指向实际使用的目录。
- 删除未参与当前发布的 V160/V162/V163 构建脚本、V147 打包脚本和过时的独立站起测试；当前构建只保留 V167 入口。
- 历史站立模型的两个重复二进制改由 `prepare-V167.py` 从 `policies/stand/` 校验恢复，旧测试入口保持可用。
- 在线演示版本标识同步为 V167 / control.43；演示读数仍是模拟值。
- 补齐原始参考文档的相对链接入口，保持原文快照字节不变。

完整固件、中控 ZIP、运动模型和训练参数内容保持原发布版本。本次整理不清除 Git 历史，已经提交的旧大文件仍可能出现在历史对象中。

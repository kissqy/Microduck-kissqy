**简体中文** | [English](REPOSITORY-LAYOUT.en.md) | [Русский](REPOSITORY-LAYOUT.ru.md)

# 仓库目录与重复资源

## 固件源码已经公开

当前版本为 **R17 V167 / control.43**。Rust 固件与飞特适配源码位于 [firmware/](../microduck-hd1910/firmware/)，中控源码位于其 `console/`；普通源码编译见 [BUILD.md](../microduck-hd1910/docs/BUILD.md)。

## 为什么还会看到较大的文件

| 内容 | 位置与用途 |
| --- | --- |
| 成品下载 | `release-assets/` 中控 ZIP，以及 `firmware/console/updates/` 独立固件；供用户直接安装。 |
| 训练配置与参考数据 | `microduck-hd1910/training-console/data/`，供本地训练中控查看参数。 |
| 在线演示资源 | `docs/`，GitHub Pages 从此目录发布；3D 资源和训练参数副本为演示独立运行所需。 |
| 构建基线 | `release-assets/build-baselines/`，一份固定 V164 ZIP，用于复现 V167 安装包。 |
| 历史参考证据 | `firmware/verification/official-reference/`，固定上游来源、模型和原始抓取记录。 |

Git 对完全相同内容使用相同文件对象；两个路径指向相同内容，不会在 Git 对象库中重复存储该对象。完整目录 ZIP 则会分别收录两个路径。

## 本次整理

- 合并两套完全相同的官方参考快照，保留原始文件与来源记录；旧路径的 SHA256 对照保留在 `REFERENCE-LAYOUT.json`。
- 删除左脚踢球模型的重复别名目录，文档索引指向实际使用的目录。
- 删除未参与当前发布的 V160/V162/V163 构建脚本、V147 打包脚本和过时的独立站起测试；当前构建只保留 V167 入口。
- 历史站立模型的两个重复二进制改由 `prepare-V167.py` 从 `policies/stand/` 校验恢复，旧测试入口保持可用。
- 在线演示版本标识同步为 V167 / control.43；演示读数仍是模拟值。
- 补齐原始参考文档的相对链接入口，保持原文快照字节不变。

完整固件、中控 ZIP、运动模型和训练参数内容保持原发布版本。本次整理不清除 Git 历史，已经提交的旧大文件仍可能出现在历史对象中。

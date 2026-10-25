**简体中文** | [English](PUBLISH.en.md) | [Русский](PUBLISH.ru.md)

# 当前仓库的发布方式

项目地址：[kissqy/Microduck-kissqy](https://github.com/kissqy/Microduck-kissqy)。用 VS Code 打开**包含根目录 README.md、microduck-hd1910 和 release-assets 的整个仓库目录**。

## 已发布内容

- `public-image-r1` Release：公开系统镜像 `microduck-zero3w-0.15.1-R1.img.xz`。
- 根目录 `release-assets/`：机器人中控 `Microduck-Console-R17-V167.zip`、训练中控 `Microduck-Training-Studio-R1.5.27.zip`。
- `microduck-hd1910/firmware/`：control.43 固件源码；其中 `console/` 是 V167 中控源码。
- `microduck-hd1910/training-console/`：R1.5.27 训练中控源码。

首页的两个 ZIP 入口直接下载仓库中的文件，不依赖它们是否另行放进 Release 附件。当前源码位于 main 分支；旧镜像标签的自动 Source code 附件不会随 main 更新。

## 以后同步

无本地待提交改动时，先拉取远端，再替换需要更新的程序和源码：

```powershell
git pull --ff-only
git status -sb
```

在 VS Code“源代码管理”中 **暂存 → 输入提交说明 → 提交 → 推送**。暂存或本地提交都不会自动更新 GitHub；只有推送成功后远端才会变化。已有待提交改动时，先完成提交或妥善保存，再拉取远端，不要使用丢弃改动或强制推送。

更新时同时核对首页下载名、固件 BUILD、源码和运行 ZIP。保留既有分项 LICENSE，不另选 MIT 或 Apache 覆盖本仓库授权。

新增运行包可继续上传 `release-assets/`，也可在 GitHub **Releases → 编辑发布 → 附件**中上传。大体积系统镜像通过 Releases 提供下载。发布标签固定对应一次提交，不移动旧标签来替换源码。

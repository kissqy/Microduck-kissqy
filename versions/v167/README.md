# Microduck V167 / control.43

这是独立保留的 **R17 V167（1.0.167） / control.43 / IPC API40** 版本，官方基线为 Microduck 0.15.1。此目录保存实际源码及已有运行包，内容取自原 V167 发布线，与 V260 分开。

| 内容 | 本目录入口 |
| --- | --- |
| 中控运行包（含配套固件） | [下载 Microduck-Console-R17-V167.zip](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/versions/v167/release-assets/Microduck-Console-R17-V167.zip) |
| 中控源码 | [浏览源码](microduck-hd1910/firmware/console/) |
| ZERO 固件运行包 | [下载 Microduck-Robotd-FT6-R17.tar.gz](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/versions/v167/microduck-hd1910/firmware/console/updates/Microduck-Robotd-FT6-R17.tar.gz) · [安装说明](release-assets/README.md) |
| ZERO 固件源码 | [浏览源码](microduck-hd1910/firmware/) · [V167 构建说明](microduck-hd1910/firmware/BUILDING-V167.md) |
| 历史系统镜像 R1 | [下载与说明](https://github.com/kissqy/Microduck-kissqy/releases/tag/public-image-r1) |

R1 镜像预装 control.40，使用 V167 中控安装本版随包固件后为 control.43。需要 V260 功能时请进入 [V260 目录](../v260/)，使用相应中控及固件。

## 目录与构建

为保持原打包脚本的相对路径，V167 保留 `microduck-hd1910/firmware/console/` 内部结构；`release-assets/build-baselines/` 也保留在本版本内。源码文件、已编译固件与模型未改动。

复用的源码树与资产树冻结自提交 [a192f3b](https://github.com/kissqy/Microduck-kissqy/commit/a192f3ba54d1921383afbd790fa7d94ea859a3c4)。构建时以本版本目录作为原仓库根目录，按对应构建说明操作；历史源码内部记录保留原样，公共搭建教程以项目 [当前教程](https://github.com/kissqy/Microduck-kissqy/tree/main/docs) 为准。

## 验证与许可

本次核对目录对象与原冻结源码、运行包相同；没有重新编译或新增实机运动验收。原 V167 Known-Good、标定要求及验证边界继续保留。分项许可见 [原许可](microduck-hd1910/LICENSE)。

[全部版本](../) · [项目首页](../../README.md)

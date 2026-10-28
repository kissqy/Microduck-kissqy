**简体中文** | [English](README.en.md)

# 飞特 HD1910 已编译固件 · control.43

> [!WARNING]
> **硬件兼容性与商业授权提示**
>
> **非本仓库开源版本的 HAT、IMU、HUB 无法适配本仓库系统，可能导致系统无法正常运行。**
>
> **本仓库未授权任何商业组织。** 如发现盗版、冒用或未经授权的商业使用，请联系作者。开源不易，请勿盗用。
>
> **防骗提醒：不要相信除群主以外任何人的私聊推销，已有群友遭受损失。**
>
> [联系作者](https://github.com/kissqy/Microduck-kissqy/blob/main/docs/assets/purchase-wechat-qr.jpg) · [查看分项许可](https://github.com/kissqy/Microduck-kissqy/blob/main/LICENSE)。授权范围以本仓库现有分项许可为准。

这是用于 **Radxa ZERO 3W 的 ARM64 机器人服务安装包**，基于官方 Microduck 0.15.1，配套 R17 V167 中控，IPC API40。包内已包含编译好的 `robotd`、`padd`、`robotctl`、摄像头服务、推理库、10 个运动模型及安装脚本，**普通使用不需要从源码编译**。

[⬇️ 下载已编译固件 .tar.gz](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/microduck-hd1910/firmware/console/updates/Microduck-Robotd-FT6-R17.tar.gz) · [SHA256 校验文件](Microduck-Robotd-FT6-R17.sha256) · [包身份与核验记录](firmware-control43.json) · [项目首页](../README.md)

**更新：修复鸭身抖动的问题。**

**作者成品 IMU 已烧录 FT6，无需为首次装机另行烧录。** 自焊新板、换芯片或维护升级时使用 [IMU 下载与烧录指南](../hardware/IMU-FIRMWARE.md)；control.43 安装到 ZERO，不会烧录外置 IMU。成品安装后仍需完成本机标定。

## 和镜像、中控是什么关系

| 文件 | 用途 |
| --- | --- |
| 系统镜像 `.img.xz` | 新装 TF 卡；已预装 control.40 和机器人环境；通过 V167 随包固件升级到 control.43。 |
| 机器人中控 V167 `.zip` | 电脑端操作工具；`updates/` 中包含同一个已编译固件包。 |
| 本页独立固件 `.tar.gz` | 与 V167 随包固件逐字节一致，供已有系统单独升级服务。 |

**普通用户用「系统镜像＋机器人中控」即可。** 镜像 R1 仍预装 control.40；刷好镜像后，通过 V167 中控安装随包固件，升级到 control.43。本包是 ZERO 的 Linux 服务包；需要自行烧录或维护 IMU 时使用单独的 `.bin`（作者成品已预刷 FT6）；`.tar.gz` 不能作为 TF 卡系统镜像刷写。

## 用中控安装

完整解压 [机器人中控 V167](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/release-assets/Microduck-Console-R17-V167.zip)，运行 `start.cmd`（macOS/Linux 用 `bash start.command`），通过 SSH 连接 ZERO，在 **系统维护 → 随包固件** 安装。中控已自带本页的固件，因此走此流程不用另外下载 `.tar.gz`。

中控的本地固件导入接受 ZIP，不直接接受 `.tar.gz`。如果已经下载本页固件，可在 Windows PowerShell 将它原样放入 ZIP：

```powershell
Compress-Archive -Path .\Microduck-Robotd-FT6-R17.tar.gz -DestinationPath .\Microduck-Firmware-control43.zip
```

然后在 V167 中控的固件导入处选择这个 ZIP。保留内部文件名 `Microduck-Robotd-FT6-R17.tar.gz`；中控会核对其 SHA256 是否与本版随包固件一致。

## 用 SSH 单独安装

用于已经具备官方 Microduck 0.15.1 或本项目 Public Image R1 环境的 ZERO。**以下命令在 ZERO 的 SSH 终端执行**；空白 TF 卡首次安装请使用系统镜像。

```bash
(
  set -e
  microduck_fw_dir=$(mktemp -d "$HOME/microduck-control43.XXXXXX")
  curl -fL --progress-bar \
    -o "$microduck_fw_dir/Microduck-Robotd-FT6-R17.tar.gz" \
    "https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/microduck-hd1910/firmware/console/updates/Microduck-Robotd-FT6-R17.tar.gz"
  printf '%s  %s\n' \
    'bcfd5c183c697b9c4e0fdbd563d995eda6a48331a7c49b9e76d20bd156c65cce' \
    "$microduck_fw_dir/Microduck-Robotd-FT6-R17.tar.gz" | sha256sum -c -
  tar -xzf "$microduck_fw_dir/Microduck-Robotd-FT6-R17.tar.gz" -C "$microduck_fw_dir"
  sudo bash "$microduck_fw_dir/Microduck-Robotd-FT6-R17/service.sh" upgrade
)
```

下载显示进度；校验失败会停止。安装使用现有 `service.sh upgrade` 流程，读取并优先保留有效本机标定及已保存参数。完成后等待机器人服务 1/4～4/4 就绪，再按这台机器的装配核对关节和 IMU；完成 HOME 后启用运动。

## 版本与校验

| 项目 | 值 |
| --- | --- |
| 构建标识 | `1fa8438-feetech-ft6-control.43` |
| 官方基线 / API | `0.15.1` / `40` |
| 配套中控 | `R17 V167` |
| 架构 | Linux AArch64 / ARM64 |
| 文件大小 | 34138802 字节（约 32.56 MiB） |
| SHA256 | `bcfd5c183c697b9c4e0fdbd563d995eda6a48331a7c49b9e76d20bd156c65cce` |

本次整理确认独立固件与 V167 随包载荷一致，160 项包内校验通过。此前构建与测试记录见 [V167 构建说明](../microduck-hd1910/firmware/BUILDING-V167.md)。

[固件源码及版本说明](../microduck-hd1910/firmware/README-R17.zh-CN.md) · [从源码编译](../microduck-hd1910/docs/BUILD.md) · [分项许可](../microduck-hd1910/LICENSE)

## 软件与动作模型许可

明确适用本项目个人非商业条款的原创中控、工具及自训模型，限个人非商业使用；商业／组织用途须事先书面授权。运行固件与第三方依赖保留其原有许可，不能把整份固件统称为禁止商用。详见 [软件与自训模型权利说明](../microduck-hd1910/docs/SOFTWARE-MODEL-RIGHTS.md) 与 [逐模型来源表](../microduck-hd1910/docs/MODEL-PROVENANCE.md)。

本次更新仓库与下载页说明，未重新打包上述 ZIP、固件载荷或镜像，未改变程序／权重字节；旧包内许可按其实际内容查验，此前已有效授予的许可继续有效。

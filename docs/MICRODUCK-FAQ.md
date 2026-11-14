**简体中文** | [English](MICRODUCK-FAQ.en.md)

# Microduck 飞特版复刻常见问题：刷机、标定、IMU、手柄断网与供电重启

> [!WARNING]
> 仅适配本仓库开源版本的 **HAT、IMU、HUB**。
>
> 本仓库未授权任何商业组织。商业使用请[联系作者](https://github.com/kissqy/Microduck-kissqy/blob/main/docs/assets/purchase-wechat-qr.jpg)，并遵守[分项许可](https://github.com/kissqy/Microduck-kissqy/blob/main/LICENSE)。

适用：Microduck-kissqy，Radxa ZERO 3W、飞特 HD1910、系统镜像 R2、机器人中控 V260 / control.102、配网 R10。作者：kissqy；更新：2026-11-14。[从零复刻总指南](MICRODUCK-BUILD-GUIDE.md)。

## Microduck 复刻需要多少钱？材料清单在哪里？

本仓库提供按实际订单整理的[复刻材料清单与成本明细](../DUCK-SHOPPING-LIST.md)，分别列出本体、HAT、IMU 与工具。表中价格是历史采购记录，打印件、设备、耗材、手工时间及未列价项目的计价范围以该页说明为准，不能把已列材料合计当成所有人的最终复刻总成本。

## Microduck 复刻的 3D 打印 STL 和摆盘在哪里？

[缝合怪打印件页](../hardware/3d-print-frankenduck/README.md)提供全套 STL、5 盘 3MF、预览和校验值。按自己的打印机与材料调整切片设置，电池仓和 IMU 安装位的适配范围见该页。

## Microduck 飞特 HD1910 版需要下载什么？

首次安装系统时，下载[系统镜像 R2](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v260)和[机器人中控 V260](https://github.com/kissqy/Microduck-kissqy/blob/main/versions/v260/README.md)。训练自己的动作时，再下载训练中控 R1.5.27。下载统一见[首页下载区](../README.md#下载与版本)。

R2 镜像已预装 V260 / control.102，使用配套 V260 中控。**从 V167 升级到 V260 不需要重刷系统或 TF 卡。** 下载并完整解压 V260 中控，连接 ZERO 后，直接在 V260 中控内安装随包固件即可。R2 镜像用于新装系统或需要重刷时。 不要将 V260 固件交给 V167 中控导入。[R1 历史镜像](releases/public-image-r1.md)与 V167 / control.43 已验证基线保留，新版发布不替代原有实机 Known-Good 记录。

R2 开机先等待网卡和网络服务就绪，再尝试已保存的 Wi-Fi；无网络可连接或连接失败时开启配网热点。运行中断网不会自动切换热点，可在中控手动开启。

## 在线中控演示能连接我的鸭子吗？

不能。GitHub Pages 上的机器人中控和训练中控是模拟数据演示，用于预览界面。控制实机需要完整解压机器人中控并在本地启动，再填写 ZERO 的 SSH 地址与登录信息。见[V260 发布与使用说明](https://github.com/kissqy/Microduck-kissqy/blob/main/versions/v260/README.md)。

<a id="linux-ssh-askpass"></a>

## Linux 中控提示 ssh-askpass 权限不足，无法连接怎么办？

**错误表现：** 中控提示“SSH 或 sudo 登录验证失败”“SSH 接口转发失败”，详细日志中包含：

```text
ssh_askpass: exec(.../Microduck-Console-Studio-V260/ssh-askpass): Permission denied
Permission denied (publickey,password).
```

**原因：** 运行中控的 Linux 电脑无法执行本地 `ssh-askpass` 密码辅助脚本，常见原因是解压后缺少执行权限。这条报错不能直接说明 ZERO 的登录密码错误。

**解决方法：**

1. 在**运行中控的 Linux 电脑上**，打开完整解压后的中控文件夹，并在该文件夹中打开终端。
2. 执行以下命令，为辅助脚本补上执行权限：

   ```bash
   chmod u+x ./ssh-askpass
   ```

3. 返回中控，点击“重连”。

如果仍然出现同一条 `ssh_askpass: exec(...): Permission denied`，继续检查文件及目录访问权限、所在文件系统是否禁止执行（`noexec`）。如果这条错误消失，但仍提示认证失败，再核对 ZERO 的 SSH 地址、用户名和密码。

## 刷了 ZERO 镜像，为什么 IMU 还需要烧录？

ZERO 系统和 IMU 上的 STM32 是不同设备。镜像与机器人服务安装在 ZERO，自制 IMU 需要单独烧录 FT6。下载、SWD 接线、烧录与通信检查统一见[IMU FT6 指南](../hardware/IMU-FIRMWARE.md)。

## 接入无线手柄后，为什么 ZERO 断网或 SSH 超时？

作者实机遇到过 2.4 GHz Wi-Fi 与手柄无线通信干扰。按本项目配置，将 ZERO 连接到路由器的 **5 GHz Wi-Fi**，并确认实际频段，不只看网络名称。查询命令与说明见[联网注意事项](ASSEMBLY-NOTES.md#zero-使用-5-ghz-wi-fi)。

SSH 超时本身不能证明一定是无线干扰；仍需结合 ZERO 是否重启、网络是否保持连接和实际频段判断。

## 舵机大负载运动时，为什么 ZERO 重启？

作者实机经验是总进电口缺少缓冲电容时，大负载瞬态容易导致 ZERO 重启。本项目装机要求在总电源输入两端**并联 1000 µF 电容**，接线、耐压与极性见[供电注意事项](ASSEMBLY-NOTES.md#总电源入口并联-1000-µf-电容)。若仍重启，继续检查电池、电源、线材、接头与负载压降，电容不能替代足够的供电能力。

## 舵机动作方向或姿势不对，可以直接复制作者标定吗？

不能直接照搬。每只机器人都要核对零位、方向、限位和 IMU 安装。先比较中控关节反馈、机械实际运动与标定，再启用模型；不要用增大力度来掩盖方向或机械装配错误。以[V260 发布说明](https://github.com/kissqy/Microduck-kissqy/blob/main/versions/v260/README.md)、随包使用说明和本机提示为操作依据；[V167 历史指南](../microduck-hd1910/firmware/console/README.zh-CN.md)用于旧版对照。

## HAT 和 IMU 有哪些接口版本？

仓库保留 EH2.5 原版和 AMP2.0 版。AMP2.0 版的舵机接口为飞特 AMP2.0，音频接口及新增 LED 见[版本说明](../hardware/AMP2.0-VERSION.md)。工程和购买入口见[硬件页](../hardware/README.md)，制作过程见 [HAT](../hardware/HAT-TIMELINE.md) / [IMU](../hardware/IMU-TIMELINE.md)。

## 换脚掌和滑轮一定要拆舵机吗？

当前[缝合怪打印件](../hardware/3d-print-frankenduck/README.md)包含方便换装的脚部结构，支持装滑轮时不拆舵机；滚轮轴承为 623ZZ，尺寸 3 × 10 × 4 mm。使用配套零件并核对摆盘材料，两种电池仓的 IMU 位适配本仓库 IMU。

## 训练需要连着 ZERO 吗？仿真成功就能上实机吗？

训练中控独立运行，训练本身不要求连接 ZERO；读取当前标定时才需要按指南连接或导入。仿真与实机存在装配、标定、动力学和供电差异，仿真结果不能替代实机验证。环境、任务、评估和模型导出见[训练指南](../microduck-hd1910/training-console/README.zh-CN.md)。

## 问题解决不了，反馈时需要什么？

在 [Issues](https://github.com/kissqy/Microduck-kissqy/issues) 写清：硬件与接口版本、机器人中控版本、实际固件标识、操作步骤、异常现象及日志或视频。先区分连接失败、服务启动失败、通信异常和运动异常，有助于复现。

[复刻总指南](MICRODUCK-BUILD-GUIDE.md) · [文档目录](README.md) · [仓库首页](../README.md)

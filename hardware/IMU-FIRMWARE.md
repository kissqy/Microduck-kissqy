**简体中文** | [English](IMU-FIRMWARE.en.md) | [Русский](IMU-FIRMWARE.ru.md)

# IMU 固件 FT6：下载、烧录与检查

**自制躯干 IMU 板需要单独烧录 STM32 固件。当前飞特 HD1910 方案使用 FT6；成品已烧好且工作正常的 IMU 无需重复烧录。** 固件读取 LSM6DSV16X 的真实角速度与融合姿态，通过飞特总线供 ZERO 上的控制服务读取。

**IMU 工程有 EH2.5 与 AMP2.0 两种接口版本。** [查看两版工程](README.md) · [AMP2.0 版](AMP2.0-VERSION.md)。两版 J2 的 SWD 针序相同。

## 先选对文件

| 内容 | 写入哪里 | 本项目当前版本 |
| --- | --- | --- |
| **IMU 固件 `.bin`** | 独立 IMU 板的 **STM32G031F8P6**，使用 ST-LINK / SWD | **FT6_SYNC15_UART_IRQ_v1** |
| ZERO 机器人服务 `.tar.gz` | Radxa ZERO 3W 的 Linux 系统，通过中控或 SSH 安装 | control.43，配套 R17 V167 |
| 系统镜像 `.img.xz` | ZERO 的 TF 卡 | Public Image R1，预装 control.40 |

**刷系统镜像或在中控升级 ZERO 服务，都不会替你烧录外置 IMU。** 当前 PCB 工程仍叫 `imu_to_dxl_RevA_V1`，这是沿用的硬件名称；接飞特 HD1910 时选择下面的 **Feetech FT6** 固件。

## 下载当前 IMU 固件

**[⬇️ 下载 IMU FT6 `.bin`（8.2 KiB）](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/microduck-hd1910/firmware/console/updates/imu_to_feetech_ReVA_FT6_SYNC15_UART_IRQ_v1.bin)** · [SHA256 校验文件](../release-assets/imu-ft6.sha256) · [完整源码](../microduck-hd1910/firmware/firmware/imu-source/)

| 项目 | 值 |
| --- | --- |
| 文件名 | `imu_to_feetech_ReVA_FT6_SYNC15_UART_IRQ_v1.bin` |
| 适用硬件 | 本仓库 [IMU RevA 工程](ProPrj_imu_to_dxl_RevA_V1_2026-10-07.epro2)：STM32G031F8P6 + LSM6DSV16X |
| 通信 | 飞特协议，**1 Mbps，固定 ID 200**；与 15 个 HD1910 共用总线 |
| 配套主控 | 当前 R17 V167 / control.43 的飞特后端 |
| 烧录起始地址 | **`0x08000000`**，依据源码 [链接脚本](../microduck-hd1910/firmware/firmware/imu-source/linker/STM32G031F8PX_FLASH.ld) |
| 大小 | **8,428 字节**（约 8.23 KiB） |
| SHA256 | `d7bd2f37a6a4e0e15d1f9650a3959bcf4d8c704524d8ec319d72d8bdf104ab6d` |

下载直接指向仓库中 V167 已随包提供的同一文件，无需下载几十 MB 的中控 ZIP，也没有另存一份重复固件。此页整理不修改或重新编译固件。

Windows 可在文件所在目录用 PowerShell 检查：

```powershell
Get-FileHash .\imu_to_feetech_ReVA_FT6_SYNC15_UART_IRQ_v1.bin -Algorithm SHA256
```

Linux 用 `sha256sum 文件名`，macOS 用 `shasum -a 256 文件名`，结果应与上表相同。

## 用 ST-LINK 烧录

准备 ST-LINK、连接线及 ST 官方 [STM32CubeProgrammer](https://www.st.com/en/development-tools/stm32cubeprog.html)。以下步骤适用于上面链接的 RevA 板。

### 1. 接 IMU 板的 J2（SWD 1×5）

针号依据 **2026-10-07 工程的 PCB 网络**；按焊盘 1 标记辨认方向，不按照片左右猜针号。

| J2 针号 | 板上信号 | ST-LINK 对应信号 |
| --- | --- | --- |
| **1** | **3V3** | 目标电压参考 VTref / VAPP；板子需要稳定 3.3V 供电 |
| **2** | **SWDIO** | SWDIO |
| **3** | **GND** | GND |
| **4** | **SWCLK** | SWCLK |
| **5** | **NRST** | NRST / RESET |

**VTref 是电压参考，并不一定给板子供电。** 按所用 ST-LINK 型号的说明区分参考输入和电源输出；J2 的 3V3 接 MCU 电源，不能接 5V。接线时断电，烧录时使用明确的单一供电来源；烧录期间先不连接舵机总线。

### 2. 连接并写入

1. ST-LINK 接电脑，给 IMU 板供电；打开 STM32CubeProgrammer，选择 **ST-LINK → SWD → Connect**，确认识别到 STM32G031。
2. 打开烧录面板，选择下载的 `imu_to_feetech_ReVA_FT6_SYNC15_UART_IRQ_v1.bin`。
3. 将 **Start address / Address 设为 `0x08000000`**，勾选 **Verify after programming**，点击 **Start Programming**。`.bin` 不携带地址，必须填写。
4. 确认写入与校验都成功；断开连接、断电并移除 ST-LINK，再重新上电运行。

步骤依据 ST 官方 [内置 Flash 烧录说明](https://dev.st.com/stm32cube-docs/prog/2.23.0/en/docs/markup/CubeProg_UserManual/Memory_programming_and_erasing.html)。也可在已安装并加入 PATH 的命令行工具中执行写入与校验，再按第 4 步重新上电：

```sh
STM32_Programmer_CLI -c port=SWD -w imu_to_feetech_ReVA_FT6_SYNC15_UART_IRQ_v1.bin 0x08000000 -v
```

Windows 工具名为 `STM32_Programmer_CLI.exe`。参数见 ST 官方 [命令行说明](https://dev.st.com/stm32cube-docs/prog/2.23.0/en/docs/markup/CubeProg_Command_Lines.html)。

## 烧好后怎么确认

先保持机器人停扭矩，通过 HAT 接入飞特总线，使用配套 ZERO 服务和 V167 中控查看 IMU 数据。检查时先不启用站立或行走。

| 检查 | 预期 |
| --- | --- |
| 烧录校验 | STM32CubeProgrammer 写入与 Verify 均成功 |
| 总线身份 | ID 200、1 Mbps；协议身份主版本为 6 |
| 姿态数据 | 缓慢转动或倾斜 IMU，角速度和姿态随实物变化；静止后数据仍持续更新 |
| 通信状态 | 预热后 IMU 就绪，没有持续通信错误或数据过期 |
| LED | 启动有两次闪烁；健康空闲可熄灭，成功响应新鲜数据时是很短的活动脉冲；初始化失败或长时间无新姿态时常亮 |

FT6 的 LED 行为以当前 [`main.c`](../microduck-hd1910/firmware/firmware/imu-source/src/main.c) 和 [`ft_led_status.c`](../microduck-hd1910/firmware/firmware/imu-source/src/ft_led_status.c) 为准。LED 只能辅助诊断，最终看真实数据、就绪状态和通信状态。

| 遇到的问题 | 先检查 |
| --- | --- |
| 识别不到 STM32 | 板子 3.3V、共地、J2 针号、SWDIO / SWCLK、NRST 和 ST-LINK 驱动 |
| 烧录成功但主控读不到 | 是否刷了 FT6、总线接线和供电、1 Mbps、ID 200 是否被其他设备占用 |
| 有回包但姿态不更新 / LED 常亮 | LSM6DSV16X 焊接、供电、SPI 连接和实际姿态数据；回包不等于传感器工作正常 |
| 看到 `feetech-ft5` 配置名 | 这是保留的兼容路径名，不单凭它判断运行旧固件；当前固件说明见下方 FT6 协议页 |

## 当前源码与编译

普通制作直接刷上面的 `.bin`，无需自己编译。开发入口为 [`Makefile.feetech`](../microduck-hd1910/firmware/firmware/imu-source/Makefile.feetech)；工具链和固定依赖见 [IMU 源码编译](../microduck-hd1910/docs/BUILD.md#imu-stm32)，协议细节见 [FT6 协议与兼容](../microduck-hd1910/firmware/firmware/imu-source/README_FT6_SYNC15.md)。快速读区为地址 56、15 字节，ID 200 在 Sync Read 列表首位；地址 124 的诊断区保留 20 字节。

[IMU 制作视频与时间线](IMU-TIMELINE.md) · [硬件与采购](README.md) · [项目首页](../README.md)

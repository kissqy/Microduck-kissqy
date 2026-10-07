# Microduck 原生飞特 FT1：通信与 IMU 测试版

2026-09-20。基于已冻结的 daemon 0.10.0，基线提交
`590b986bd8c0d50ae02cb3ea2f59c463b6828168`。不是升级官方主分支，也不是正式行走版本。

## 到底编译什么

| 对象 | 本次工作 | 安装位置／当前状态 |
| --- | --- | --- |
| Radxa 主机程序 | 新增独立 Feetech 原生后端，配置二选一 | 已完成开发环境 x86_64 编译和离线测试；未部署 ARM64 robotd |
| 自制 RevA IMU 板 | 新增原生飞特 FT1 固件 | STM32G031F8P6，已生成 ARM `.bin`；未刷板 |
| HD1910 舵机 | 使用出厂原生飞特协议 | 不编译、不刷舵机内部固件 |
| Dynamixel 后端与 A5 IMU | 保留 | 旧代码保留；A5 重编译的 `.bin` 与原文件 SHA-256 一致 |

不是协议转换。选择 Feetech 时，线路上只发送飞特报文，不尝试 DXL、不自动回退。
保留旧安装的兼容默认值 `dynamixel`；新测试配置显式写 `protocol = "feetech"`。
没有改 Radxa 服务、既有配置或已安装程序；本包也没有自动安装／刷写脚本。

## 你现在只做这一项

先不刷 IMU，先不替换 robotd。保留已经设置好的 runtime `--fake` 模式。
把包根目录的 `feetech_probe.py` 放到 Radxa 的 `/home/radxa/feetech_probe.py`，执行：

```bash
/home/radxa/dxl-venv/bin/python /home/radxa/feetech_probe.py --id 1
```

只读 ID 1 一次，不读 ID 2、不搜索整条总线、不改变扭矩／ID／增益／波特率。
使用 Python 标准库，不需要安装 pyserial，也不安装服务。
脚本先读取现有 robotd 状态：若它在运行却不带准确的 `--fake` 参数，就在打开串口前退出。
若显示权限或端口占用错误，先解决已有访问条件，不用 sudo 强行抢端口。
默认端口 `/dev/ttyS2`、1 Mbps。预期能看到 position_raw、电压、温度与原始报文。

把这一次输出发回来后再进入下一项。不要为了测试插拔带电舵机；接线变更先断电。
临时 systemd drop-in 位于 `/run`，重启机器后不保证仍在 fake 模式，脚本会重新检查。

## 已实现的边界

- Rust 原生包编码、校验和、流式收包、回显过滤、ID/长度/错误位检查、超时。
- HD1910 地址 56 的 11 字节实测反馈；位置写、扭矩写、15 颗同步写原生 API。
- 15 颗位置 SyncWrite 是 128 字节；这是离线编码验证，不是 15 颗实机通过。
- 同步写没有 ACK。发送成功不等于执行成功；关扭矩必须再读寄存器 40 确认。
- IMU 原生身份和 20 字节数据；序号、采样年龄、就绪检查；主机解算继续复用原 SFLP decoder。
- IMU 和舵机使用各自的原生寄存器地址，完整采样周期内分别读，不伪装成同一时刻采样。
- HD1910 的 0x82 SyncRead 尚未实机验证，主机诊断路径使用已验证的逐 ID Read。
- 两颗台架舵机保持 ID 1、2，不自动改成机器人关节 ID。旧机器人有 15 个关节，映射另行标定。

首版是“通信与诊断后端”，不是“可直接运行旧行走策略”的完成版：

1. `RobotIo::write`、策略增益写、策略扭矩开启和 Feetech `robotd init` 明确拒绝。
2. 原生 `Bus` 提供台架位置／扭矩／同步写 API；本次交付的操作入口只开放读取。
3. `robotd` 全机器人诊断要求完整 15 关节映射及确认过的速度／电流单位。
4. 不把未知电流显示成 0 mA，不照搬 XL330 的 Kp，也不猜 HD1910 电流比例。
5. 不自动写 EEPROM、恢复出厂、改 ID、改波特率或做开机归位。

`config/hd1910-calibration.template.toml` 故意不能直接启用。
测量前先用单颗 probe，不必伪造校准参数让 daemon 启动。
`config/robotd-feetech-bench.toml` 同时关闭策略、电压自适应和旧 2S 电池低压关机判断；
这是示例，当前两颗台架阶段不要替换已安装的配置文件。

## IMU FT1 与旧 A5

自制板的 MCU、SPI、UART、电气方向控制、传感器 ODR、SFLP、安装轴变换均沿用验证过的 RevA/A5。
只在 Feetech 编译分支换通信解析和寄存器入口，扩充 RX 环形缓冲到 256 字节。
原 Makefile 构建 DXL；独立 `Makefile.feetech` 只构建 FT，没有 DXL 对象混入。

| 项目 | FT1 定义 |
| --- | --- |
| 串口 | 1 Mbps，8N1，HAT 原有 TTL 半双工 |
| IMU ID | 200，固定，只读 |
| 模型号 | 自定义 0xF200；地址 3、4，小端 |
| 包格式 | `FF FF ID LENGTH INSTRUCTION PARAMS CHECKSUM` |
| 校验和 | ID 至最后参数的 8 位和取反 |
| Ping | 原生飞特空参数状态回应；型号用 Read 读取 |
| 数据读取 | 地址 124，20 字节；也可只读原前 12 字节用于诊断 |
| 写／重置／改 ID | 不支持；单播错误回应，广播不回应 |
| IMU SyncRead | 0x82，仅当 ID 200 列在第一个位置时回应；主机首版不用此路径 |

| 地址 | 长度 | 内容 |
| --- | --- | --- |
| 124–129 | 6 | 原始 gyro XYZ，i16 小端；与 A5 相同 |
| 130–135 | 6 | SFLP 四元数 XYZ，IEEE float16 小端；与 A5 相同 |
| 136–139 | 4 | quaternion 更新序号 u32 小端；新四元数才递增，可回绕 |
| 140–141 | 2 | 最后四元数距当前的年龄，毫秒，饱和 65535 |
| 142 | 1 | bit0 曾收到有效四元数，其他位为 0 |
| 143 | 1 | 数据格式版本，固定 1 |

读 IMU 的原生请求：`FF FF C8 04 02 7C 14 A1`。
IMU 对舵机的广播 SyncWrite 保持静默，不占用回应时间槽。
host 拒绝超过 50 ms 的数据，或连续 3 次同序号；整个读取周期耗时也计入年龄预算。
这些检查通过伪串口与固件 C 函数的联调，不代表上板 UART 时序已经验证。

新固件：`firmware/imu_to_feetech_ReVA_FT1_UART_IRQ_v1.bin`，7144 字节。
SHA-256：`84c4d5dd488433585b262accd4a69971e3eec11b10d4bd8b424340ea9564035e`。
flash 链接基址 `0x08000000`，仅用于已确认的自制 RevA STM32G031F8P6 板。
这不是舵机固件，不可用 FE-URT2 舵机固件升级入口写入 HD1910。

旧 A5 回退文件：`rollback/imu_to_dxl_ReVA_M8A5_UART_IRQ_v1.bin`，7432 字节。
SHA-256：`85ee561cced17025a94be1b469a9b393578a16edc49bd90d101d2786aec79bac`。
以后切回 XL330，要同时选择 Dynamixel 后端和 A5 IMU 固件；不是只改一个主机开关就能让 FT1 说 DXL。
实际刷写沿用先前已验证的 SWD 流程，待单颗读取通过后单独做，不在本步骤混做。

## XL330 已保存基线与 HD1910 现状

来源是 2026-09-03 原始 benchmark JSON 和采集器，不是产品标称值。
原始 CSV、JSON 原样保留在 `baseline/`，无新增 HD1910 曲线冒充实测。

| 条目 | XL330-M288-T 原始基线 | HD1910 当前证据 |
| --- | --- | --- |
| 供电读数 | 5.3 V | 已读到 5.9 V；条件不同 |
| 通信链路 | FTDI USB 转接，ttyUSB0，1 Mbps | HAT ttyS2，1 Mbps |
| 通信统计 | 300/300；均值 1.933 ms，P95 2.159 ms | 单读、单动、两颗同步通过；暂无同口径统计 |
| 动作幅度 | 57 ticks，约 5.016°；5 轮共 20 段 | 已测试 +100 ticks 后返回 |
| 速度限制 | profile raw10 = 2.29 rpm；加速度 raw1；goal PWM raw100 | speed raw100、ACC raw5；不能按数值直接比 |
| 到位时间 | 均值 0.818 s，P95 0.8212 s | 尚无带时间戳的轨迹，不能比较 |
| 最终误差 | 平均绝对 1.75 ticks，最大 3 | 两颗同步报告目标各差 -1；返回各差 +1，仅单次结果 |
| 超调 | 本组采样观察为 0 | 未测时间序列，未知 |
| 电流 | 本组峰值 13 mA | 尚未确认该型号电流寄存器比例，不能按 load 换算 |
| 温度 | 27→27 °C | 曾读到 30 °C；室温、时长不一致，不能比较温升 |

0.818 s 的定义是“从目标写入前计时到第一次进入 ±8 ticks”，随后继续观察 0.4 s。
采样间隔 0.05 s，计时含通信；这不是舵机无负载最高速度，也不是精确测出的纯电机延迟。

## 尽量不重新训练：可以尝试，但现在不能保证

优先保持策略的关节顺序、角度正方向、零位、观测单位及 IMU 安装变换。
然后在确认允许的相同电压、相近速度限制、相同惯量／负载下，逐项记录两款舵机的轨迹。
先对齐到位时间、误差、延迟、死区；之后才拟合执行器补偿，不动策略权重。

候选补偿可包括关节零位／方向映射、有限幅度的前馈和速度／加速度限制。
这些需要负载下的带时间戳数据验证，补偿输出还要经过关节范围、速度、扭矩及跌倒保护限制。
较慢的硬件不能靠无限前馈变成较快的硬件；增益量纲、可用扭矩及机械差异也可能使旧策略不适配。
因此不在首版写入猜出来的系数，不自动启用动作；比较结果通过后再决定是否能保留原训练权重。

## 开发侧复现（不是让 Radxa 现在执行）

源码补丁基于以上冻结提交；先在对应的独立工作树 `git apply --check`，再应用。
补丁包含新增文件；没有提交／推送远端，没有修改正式部署。

```bash
git apply --check /path/to/robotd-feetech-ft1.patch
git apply /path/to/robotd-feetech-ft1.patch
cargo test --locked -p duck-control -p robotd-params -p robotd --lib --bins
cargo build --locked -p robotd -p duck-control --examples --bins
python3 scripts/feetech_probe.py --self-test
python3 scripts/test_feetech_native.py --imu-source /path/to/imu-source
```

Rust 1.90.0；锁文件保留。构建产物是开发机 x86_64，不能拿这个 robotd 二进制直接运行在 Radxa。
因此包内不给一个架构错误的 robotd 可执行文件；正式 ARM64 部署留到对应阶段。

固件使用 Arm GNU 14.3.Rel1（arm-none-eabi）、CMSIS Core 5.9.0，
ST cmsis-device-g0 提交 `f576c24e123edf3332988ecd49512c0f35f85186`：

```bash
make -f Makefile.feetech feetech \
  TOOLCHAIN=/path/to/bin/arm-none-eabi- \
  CMSIS_CORE=/path/to/CMSIS_5/CMSIS/Core/Include \
  CMSIS_DEVICE=/path/to/cmsis-device-g0
```

使用独立工具链，不需要重装服务；本包不捆绑编译器。
链接器沿用 A5 脚本，会输出 bare-metal nosys 系统调用桩和 RWX LOAD segment 的原有警告；未把它们隐藏。
FT1 生成 ELF 与 BIN，无 DXL 解析符号；A5 的编译、协议 fuzz 测试及旧 bin 一致性验证通过。
全目标严格 Clippy 会被原冻结源码 `robotd/src/chorale.rs` 连续两行 `#[cfg(test)]` 阻断；
这是已存在的问题，本次不顺便改无关模块。新通信模块的检查另行运行。

原生包和 SMS_STS 基本寄存器交叉核对来自
[飞特官方 SDK](https://github.com/FTservo/FTServo_Python/blob/54e86a7a28824999f254d9a4f5364cdc17379583/scservo_sdk/sms_sts.py)，
该通用表不等于 HD1910 的完整型号数据表。
XL330 单位和控制表参考 [ROBOTIS 官方手册](https://emanual.robotis.com/docs/en/dxl/x/xl330-m288/)；
本表的测试数值来自用户保存的 baseline JSON，不是手册额定值。

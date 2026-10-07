## 协议与兼容

地址 56–70：角速度 XYZ i16 小端 6 字节，四元数 XYZ binary16 小端 6 字节，u8 采样计数、状态、保留 0，各 1 字节。
状态 bit0=未就绪，bit1=数据过期，bit3=上次读取后新样本至少 5 次；主控还拒绝 bit2 错误，bit4–7 必须为 0。bit3 是采样/读取节奏信息，不据此误报传感器故障。
计数只随真实新四元数更新，255→0 为正常回绕。固件在发送前从缓存时间戳检查年龄，超过 30 ms 置 bit1；即使采样主循环停住而串口仍在回包，也不能继续报新鲜。
主控检查状态、连续 3 次相同计数、四元数合法性，并将 30 ms 上限与整轮耗时相加检查 50 ms。保留官方安装方向变换和就绪判据。
地址 124–143 保留 FT5 的完整 20 字节诊断格式：12 核心字节、u32 序号、u16 年龄、ready、schema=1。正常控制循环不轮询此区。
这与社区的 15 字节快速布局对齐；诊断区、固件身份和低层实现仍为本项目定义。ID200 必须在 Sync Read 列表首位，不移植社区未经本 HAT 实测的其他位次排队逻辑。

保留 FT5 的 USART 中断接收、ISR 快速响应、双缓冲发布、等待 TC 完成后释放总线、RX 先恢复再释放驱动、原 GPIO/SPI/IMU 初始化、120 Hz SFLP、LED 行为。
只改已有飞特后端与配套服务入口，不改官方关节顺序、标定文件、训练策略。现有配置键和安装路径继续沿用 `feetech-ft5` / `feetech-ft5-r5`，它们是兼容路径，不代表运行旧固件。
启动仍停扭矩，不自动运行 XL330 原策略。


## 构建

使用 Arm GNU Toolchain 14.3.Rel1，执行 `make -f Makefile.feetech TOOLCHAIN=/工具链/bin/arm-none-eabi-`。
配套 third_party 为 STM32CubeG0 固定提交 446ebe396489ca75679caa80887d7257efe92e3d 的 CMSIS Core，以及其设备子模块 f576c24e123edf3332988ecd49512c0f35f85186。
`README_FT1/FT2/FT4` 与 A5 文档是历史记录；当前固件为 FT6。
参照社区接口：
https://github.com/fanhao375/microduck-replica/blob/master/hardware/imu_to_dxl/总线协议.md
https://github.com/fanhao375/microduck-replica/blob/master/hardware/imu_to_dxl/firmware/Core/Src/control_table.c
当前实现基于本项目 FT5，未直接烧录社区 HEX。

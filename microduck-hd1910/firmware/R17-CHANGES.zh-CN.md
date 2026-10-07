R17 v1.0.143：复用原生诊断 JSON 和状态快照，避免 Zero 采集器重复编码已解析的遥测，并修复客户端或被拒启动进程覆盖 daemon 身份的问题。控制与遥测频率、UI、记录格式、模型和参数保持 v142。机制见 [诊断与状态所有权](docs/design/r17-settings-design.md)、[SSH 遥测转发](docs/design/r17-connection-design.md) 和 [启动所有权](docs/design/robotd-design.md)，本轮验证及环境受限记录见 verification/。未测量新版实机 CPU 或温降。

R17 v1.0.129：中控策略调参仅保留动作缩放。头腿滤波及电压补偿交回原生默认，删除 R17 赋值和补偿修复完成标志。完整本次差异见 [本次官方差异](OFFICIAL-CHANGES.zh-CN.md)，参数机制见 [R17 参数来源](docs/design/r17-settings-design.md)。以下为历史改动记录。

R17 v1.0.124：默认值与保存值来源已统一；动作系数 0.70，头/腿滤波 0.50/0.70，沿用本机设置。参数机制见 [R17 中控参数来源](docs/design/r17-settings-design.md)。

R17 v1.0.123：官方动作缩放 policy.action_scale 默认改为0.70；头部0.50、腿部0.70滤波保持。升级时沿用旧默认0.90的设置改为0.70，其他已保存倍率保留；本版安装后手动选择0.90仍会保存。

默认值由固件 robotd-profile.toml 提供，中控读取保存配置及运行回读；未收到时显示等待，页面不另设倍率。


R17 v1.0.96 改动清单：对比官方 0.15.1
官方来源：pollen-robotics/microduck
完整提交：1fa84386f07884e27866411bc1ba166977bced95
本次沿用 R17 v1.0.95 的旧中控和硬件适配，未采用另一个聊天窗口的中控或 HAT 协议。

对官方原本代码的修改（文件级完整清单）
1. robotd/src/main.rs：接入原 R17 飞特后端、commissioning 标定、FT6 诊断与原 UART 初始化；增加自训合同与运行模型哈希/倍率回读；custom_only 模式禁止官方模型回退。保留官方 HOME、启停、策略选择、跌倒判定、坐起时序及电压补偿。
2. robotd/src/control.rs：按合同精确 HOME、训练倍率、命令填充与 EMA 解释模型；增加实际倍率和模型身份回读。最终动作继续通过官方全局缩放和头腿低通；没有旧原地倍率/启停渐变。
3. robotd/Cargo.toml：R17 硬件配置需要的 TOML 解析依赖。
4. duck-control/src/lib.rs：导出 R17 飞特、硬件、HD1910 和部署合同模块。
5. duck-control/src/io.rs：补 R17 单一总线所有者的诊断和保持位置接口。
6. duck-control/src/model.rs：支持自训合同中的精确 HOME 与关节映射。
7. duck-control/src/policy.rs：校验每个导出的合同、观测/输出和 P 参数；载入磁盘模型，计算实际权重身份，提供模型课程范围。官方异步换模、前馈/循环网络加载实现继续保留。
8. duck-control/src/obs.rs：合同明确要求身体命令零填充时执行零填充；61 维官方布局与上一帧原始动作反馈顺序保留。
9. duck-control/src/safety.rs：向 R17 诊断透出飞特状态和保持位置，仍只有一个电机写入者；不新增跌倒恢复策略。
10. duck-ipc-proto/src/lib.rs：在官方 0.15.1 类型上延续 R17 总线/标定诊断调用。HAT 的 FT6 报文不由这个文件改写。
11. robotd-params/src/lib.rs：增加飞特总线/标定配置以及 custom_only 参数。
12. robotd-params/src/registry.rs：登记上述三个参数。
13. docs/design/robotd-design.md：记录合同动作转换与官方全局处理的关系，仅文档。

新增或延续的 R17 代码
- duck-control/src/feetech.rs：从原 R17 延续舵机报文、地址 42/6 字节目标、速度 0、加速度寄存器和 FT6 读写。适配新 RobotIo 只补 reboot 不支持声明和 measures_load=false；格式化不改变报文。
- duck-control/src/{hardware,hd1910,deployment}.rs：HD1910 坐标/装配标定、硬件访问及严格部署合同适配。
- robotd/src/feetech_*、process_safety.rs、service_client.rs、selftrained_profile.rs：原 R17 硬件管理与诊断入口；本次对齐 0.15.1 类型与自训联合任务。
- packaging：R17 安装/配置恢复/模型管理；配套 ONNX Runtime 1.28.0；安装官方 padd、robotctl、sounds。
- packaging/webpad.py 和 microduck-webpad.service：新增网页 Xbox evdev 输入桥。只写标准手柄事件；读取官方 pad.input 确认接入，不向它写动作。真手柄出现或网页租约超时就销毁网页设备。
- console：修改旧 R17 页面为“实时鸭子 / 模拟手柄 / 摄像头”三列；删除文件/命令行卡片和通用远程文件、终端接口；仅保留模型包与安装包的内部暂存上传。其它原 R17 诊断、标定、曲线和回放继续使用。摄像头延续原 WebRTC 接收流程，补官方重复生产者列表的单会话保护，默认信令端口仍为 8443。

明确的官方行为边界
- padd/src/main.rs、padd/src/tap.rs 与官方 0.15.1 字节一致，未自写按键策略。
- 0.9、0.5、0.7 是官方处理链的配置值，未更换低通算法。模型切换不根据 ZIP 的“直通”建议改写这些全局参数。
- 坐起固定动作倍率 1，保留官方例外；官方电压补偿默认开启，0.9 是行走基础值，不是每一帧最终倍率。
- 本次仅提供 walk 联合网络和 sitstand；stand、ground_pick、kick_left、kick_right、roulade 均为 none。网页未配置的动作按钮灰显，官方 [pad] 对应技能解绑。
- 保留 R17 的 battery_empty_shutdown=false，电源由操作者控制；limp_fall=false 与官方默认一致。没有额外原地策略、跌倒动作或自主行走。
- 在上述 custom_only 部署下，坏模型不再按官方默认方式丢弃覆盖后回退官方模型。这是为执行“只用我们自己模型”的明确改动。
- 系统升级服务未被本包重装；只更新 R17 所需的 robotd / padd 客户端与配套工具和库。HAT/IMU 固件本次未刷写。

验证与限制
- robotd 单元检查：185 通过，1 项官方默认忽略；含真实 ONNX 40 帧参考及五项动作缩放/滤波/身份检查。
- duck-control：117 通过；8 个官方循环网络检查另行执行全部通过。
- robotd-params：96 通过；padd：23 通过；robotctl：197 通过，5 项默认忽略。
- Python：40 项通过，覆盖装配标定保留、倍率持久化、HOME 反馈、R17 Xbox 检测、物理接管、600ms 输入失联、首次 Start 缓冲和输入撤销。
- 浏览器：桌面三列 426×620，Start 按下/松开及真手柄接管通过；页面检查使用模拟后端，动作检查关闭了测试环境的软件 WebGL。摄像头按官方 0.15.1 逻辑避免重复生产者列表开启重复会话，重连检查通过。
- 测试环境禁止 AF_UNIX 系统调用：robotd 10 项单实例集成检查及 robotctl 2 项 Unix socket 检查无法执行通过，保留原检查，未削弱服务锁。
- 无实机测试。静态和推理检查不能证明现在装配后的实际行走、舵机动态或最终 HOME 到位。

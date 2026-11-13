# UI42 PADD 原生变更与验证

在 UI41 原生源的基础上，只修改 `padd/src/main.rs`，新增 `padd/src/recorder.rs`。没有修改或重新编译 robotd、模型、mediad、IPC 协议。`input_pause.rs`、`mouth_pause.rs`、`short_press.rs` 与 UI41 备份逐字节相同，哈希见 `unchanged-ui41-modules.json`。原有手动映射、运动频率和 100ms 零速心跳保留；只有录制期间 R3 改为可验证的明确表情名，X 按原 tick 请求 accepted 回执。

Logo 短单击释放后等待 350ms 判定，再开始记录；不预录。录制中再短单击提交保存，双击读取并播放唯一的 `last.json`。长按忽略。播放中 Logo 或普通输入、会话变化/断连、失去新鲜安全反馈、语音嘴部租约等中止播放。Start/Select 保留原有安全路径，停速与身体偏置清理先发，不为额外表情取消回执等待。手动恢复要回中，普通按键不回放。

开始前需要人工 HOME、原生处于 walk/stand/sit、homed/政策配置启用且非 held/off/limp，实际 IMU 与状态新鲜，普通 Drive、无 IMU 头跟随、摇杆扳机回中、无 AI 输入/嘴部租约。录放待定、录制、保存或回放期间拒绝新 AI 输入租约，Saving 不拥有运动输出，人工安全操作不会撤回已授权的后台文件提交。

记录成功写入的 Move/Head/Pose/Mouth/Sound 和 accepted 的明确技能，以发送时刻记录单调时间。查询、HOME、上力、卸力、关机、重启、模式切换及管理类 `stand_test` 等不会成为回放事件。R3 从固定清单第一项开始，只有 accepted 才递增，文件内是明确名称；表情按 request_id 对照同代 completed/cancelled，避免漏看短暂 playing 后一直无法保存。有限技能仍需原生进入/退出反馈；坐下允许以新鲜 sit 模式作为尾段，用户再次按保存决定实际停顿长度，不伪造物理到位回执。

回放在现有 PADD 线程和同一 intent socket 按绝对 deadline 排程。连续帧不追赶，实际发送或同步技能响应之后迟到达到 100ms 就终止。正常结束和中止各有一次 Move0/PoseFalse/WheeeFalse/Mouth0 清理；已有嘴部语音租约时不写 Mouth0。仅取消本次表情 generation；通用有限模型没有统一取消 API，停止后续指令不代表有限模型已经物理瞬停，Start/Select 仍按原生规则中止。不会为回放自动 HOME、上力或切模式。

文件上限 120 秒、4MiB、30,000 事件。达到上限取消本次记录并保留旧文件，不干预用户正在手动执行的运动。状态机先完整验证方法、参数、有限数值/范围、帧顺序、元数据，再允许播放。后台有界队列负责临时文件、fsync 和原子 rename，失败保留旧文件；读到损坏文件也不会播放。状态 `/run/padd/recorder.json` 在变化和至多每秒一次的周期更新，磁盘不在控制循环里写。

验证结果：完整 `cargo test --locked -p padd -j4 -- --test-threads=1` 为 **89 passed / 0 failed**。包括真实 AF_UNIX socket pair 整链：Monitor 查询回复与订阅状态混流、实际写入和 accepted 捕获、后台原子保存、磁盘重载、同 socket 回放、坐下尾段和不同初态拒播；状态年龄使用与 robotd 相同的精确 CLOCK_MONOTONIC 纳秒，测试固定同毫秒非零低位、真实未来和350ms过期边界，避免毫秒向下取整误判未来。另包括 110ms 慢技能回执后不发送陈旧 Move、异代表情终态不误清、保存失败恢复 Error、语音租约下收尾不抢嘴、长第二次按键不误录。

当前环境拒绝 UnixListener::bind（EPERM），因此整链用真实 UnixStream::pair，并直接走同一个 Monitor/Reader wire 实现。没有声称做过监听地址绑定或真机测试。ARM64 release 构建通过，ELF64 AArch64 PIE，解释器 `/lib/ld-linux-aarch64.so.1`，最高 GLIBC_2.30，目标 GNU2.31。工具链与命令、二进制 SHA、文件大小及 ELF 报告见 `native-build.json`、`toolchain.json`、`padd-elf.txt`、日志。

`native-source.patch` 已在 UI41 备份上重放并逐文件比对，见 `patch-replay.json`。运动兼容性只轻量核对 mode、已加载模型路径及技能清单；没有模型文件 SHA 校验，同路径替换模型后应重录。该功能重放控制意图和节奏，不保证物理轨迹完全重现。原有同步 accepted 请求仍可能短暂等待原 socket 超时边界，期间到来的输入由下次 drain 消费。

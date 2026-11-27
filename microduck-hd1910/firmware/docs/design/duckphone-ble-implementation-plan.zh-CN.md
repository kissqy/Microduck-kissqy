# duckphone-ble 实现计划与分工

> 2026-11-26 · 分支：`dev` · 状态：设计已审核，开始实现
> 本文件是执行清单；设计依据见 [实现设计](./duckphone-ble-implementation.zh-CN.md)。

---

## 0. 当前状态

| 项 | 状态 |
| --- | --- |
| 方案/功能/UI/实现设计 | ✅ 已完成并审核 |
| 文档与原型位置 | ✅ 已迁入 kissqy `dev` |
| 机器人端代码（proto/btd/robotd/configd/构建） | ✅ M0 代码完成，交叉编译通过 |
| 机器人端验收/部署脚本 | ✅ 已写；只读探针已在真机跑通（API 40 旧固件） |
| Android App 传输层 | ✅ 工程/桥接/单测完成；APK 已构建 |
| 驾驶 UI | ✅ 原页面 + 连接页 + 双链路条/链路卡；真机待测 |
| 手机装机 | ✅ 已装进华为 Mate 40 Pro（2026-11-26） |
| 固件部署 / 真机动作测试 | ⛔ 等用户确认 |
| Android SDK / Gradle | ✅ 已装，license 已接受 |

---

## 1. 全局约定

1. **只改 `Microduck-kissqy` 的 `dev` 分支**；不新开特性分支，不切旧分支。
2. 代码：`microduck-hd1910/firmware/duckphone-ble/`。
3. 设计文档：`microduck-hd1910/firmware/docs/design/duckphone-ble-*.zh-CN.md`。
4. 原型/截图：`firmware/duckphone-ble/design/`。
5. **不改** `firmware/duckphone/`、`firmware/console/`、`firmware/ducknet/`。
6. 构建产物：`microduck-hd1910/.build/`（不提交）。
7. 任何会动机器人的测试必须有人在现场扶稳；部署/重启 `robotd` 前先确认。

---

## 2. 阶段总览

| 阶段 | 内容 | 负责人 | 状态 |
| --- | --- | --- | --- |
| M0 | 机器人端：proto / btd / robotd / configd / 构建 / 验收脚本 | AI 为主 | ✅ 代码与构建完成；脚本/真机待做 |
| M1 | App 传输层：Android 工程 / BLE 会话 / JS 桥 / 假链路 | AI 为主 | ✅ APK 构建通过 |
| M2 | 驾驶 UI：页面副本 / 摇杆 / 动作 / 状态 | AI + 用户（动作测试） | ⛔ 等 M0/M1 |
| M3 | 网络与系统：Wi-Fi / 日志 / 重启 / 诊断 | AI + 用户（配网测试） | ⛔ |
| M4 | 加固交付：安全 / 华为 / 30 min / APK | AI + 用户 | ⛔ |

---

## 3. M0 · 机器人端（AI 现在可做）

### 3.1 `duck-ipc-proto`

- [x] `API_VERSION` 40 → 41。
- [x] `SubscribeParams` 增加 `profile: Option<StateProfile>`；`StateProfile::Phone`；`PhoneState` + `Request::notify_phone_state`。
- [x] 新增 `Call::RobotVolume(VolumeParams)`、`method::ROBOT_VOLUME`、`VolumeResult`。
- [x] 新增 `Call::SystemServiceAction(ServiceActionParams)`、`method::SYSTEM_SERVICE_ACTION`、`ServiceActionResult`。
- [x] 确认 `dev` 已有 `NetConnectParams.ipv4`（ducknet 固定 IP）。
- [x] 补 `method()` / `destination()` / `params()` / `as_call()` / `is_mutating()` 与 roundtrip 测试；新增 phone 帧 ≤400 B 与省略 `profile` 的测试。

验收：`cargo test -p duck-ipc-proto` — 56 项通过。

### 3.2 `btd` 路由

- [x] 允许 `RobotMove` / `RobotHead` / `RobotStop` / `RobotRelax` / `RobotSound` / `RobotVolume` / `SystemServiceAction`。
- [x] `RobotSubscribe` 仅 `profile=phone` 允许；全量帧仍拒绝。
- [x] 保持 `RobotPose/Mouth/Look/SetMode/Shutdown/Theremin/Chorale` 拒绝。
- [x] 更新 mutating 白名单测试 + profile 分支测试；`relax/stop` 的代价写在注释里。

验收：`cargo test -p btd` — 49 项通过。

### 3.3 `robotd`

- [x] `robot.subscribe` 按 `profile=phone` 输出精简帧（约 300–400 B，测试上限 400 B）：
      `t / move / head / policy / safety / loop / enabled / homed / sitting`。
- [x] `robot.volume`：读/写百分比、静音、`alsactl store`；曲线与控制名沿用 duckphone。
- [x] 测试：phone 帧字段与大小（proto）、音量命令序列（`volume.rs` 8 项）、全量帧不变。

验收：`cargo test -p robotd` — 231 项通过；44 项因本机缺 `libonnxruntime.so` 失败（与本次改动无关）。

### 3.4 `configd`

- [x] `system.serviceAction`：白名单仅 `padd` 的 `stop|start`，经 systemd D-Bus 执行并轮询到目标状态。
- [x] 非白名单拒绝并说明可用单元。
- [x] 测试：`permitted_unit` 白名单。

验收：`cargo test -p configd` — 64 项通过。

### 3.5 构建与打包

- [x] `tools/build-firmware.sh` 加入 `btd`、`configd`；产物清单加入两者。
- [x] 确认 `btd.service` / `sysusers.d/` / `configd.service --allow-user btd` 已随仓库安装（`scripts/install.sh` 已覆盖）。
- [x] 交叉编译（Zig 0.15.1 已安装）。

验收：`.build/firmware/bin/` 出现 7 个产物，`btd`/`configd`/`robotd` 均为 AArch64、GLIBC ≤2.31。

### 3.6 PC 验收/部署脚本

- [x] `duckphone-ble/tools/acceptance.py`（Bleak）：认证、phone 状态、零速控制写、stop、音量、可选停 padd、网络、日志、重连；运动相关不自动做。
- [x] `duckphone-ble/tools/probe_ble.py`：只读方法/延迟/吞吐/MTU/phone 帧大小。
- [x] `duckphone-ble/tools/duckble.py`：扫描（含广播 IPv4）与 JSON-RPC 传输。
- [x] `duckphone-ble/tools/deploy_robot.py`：备份、scp、systemd、检查、回滚；默认 dry-run。
- [x] `duckphone-ble/tools/setup_pc.sh`、`sync-web.sh`、`build_apk.sh`、`install_apk.sh`。

验收：只读探针可独立跑；部署脚本默认 dry-run；`--restart` 需显式给出。

### 3.7 部署与真机验收（需用户确认）

- [x] 机器人上电，PC 只读探针实测（2026-11-26）：扫描/连接/认证/`robot.health`/
      `system.info`/`system.services`/`net.status` 通过，MTU 517；机器人 API 40，
      `robot.subscribe{profile}` 被旧固件拒绝（预期）。
- [ ] 部署 API 41 固件（等用户指令）；部署后重跑探针与 acceptance。
- [ ] 手机开启 USB 调试后安装 APK。
- [ ] 运行 acceptance（只读部分 AI 可做；动作部分用户执行）。

> 实测发现：板上 `updaterd.service` 是 inactive、socket 不存在，所以 `update.status`
> 返回 "Updater is not answering"。这是部署前就有的板子状态，与本次改动无关，但部署脚本
> 升级 `updaterd` 之前它都会在探针里报红。

---

## 4. M1 · App 传输层

- [x] Android 工程：`applicationId com.microduck.phone`，minSdk 26，compile/target 35。
- [x] `MainActivity` + `WebViewAssetLoader` + 运行时权限 + 文档开始前注入桥。
- [x] `BleClient`：扫描/连接/MTU/订阅/有应答与无应答两种写/分块。
- [x] `RobotLink`：JSON-RPC id、超时、通知、错误、断链失败全部在等请求。
- [x] `JsBridge`：`call/notify/scan/connect/disconnect/info/keepScreen` 与四条回推。
- [x] `assets/duckphone/` 页面副本（单向同步）+ `ble-bridge.js`（WebSocket 替身）。
- [x] 假链路单元测试：`Framer` / `Limits` / `RobotLink` JVM 测试；`ble-bridge.js` 用无头 Chrome 跑 13 项断言。
- [x] APK 构建（`tools/build_apk.sh`，产物在 `.build/apk/`）。
- [x] 真机连接 → PIN 认证 → 版本检查（华为 NOH-AN00，2026-11-26）：扫描到 `duck-dillon`、
      MTU 517、`api=40`，连接页给出「需要 41」而不是跳进驾驶页。
- [ ] 真机 10 Hz phone 状态（等 API 41 固件部署）。

---

## 5. M2 · 驾驶 UI

- [x] 页面**不改**：`ble-bridge.js` 在文档开始前替换 `WebSocket`，原页面与副本都不动。
- [x] 连接页 `ble-connect.html`：扫描列表、PIN、进度/错误、记住上次机器人（视觉细节待真机打磨）。
- [x] 驾驶页顶栏双 chip（蓝牙 / 机器人 Wi-Fi）：桥接在 `#topbar` 下注入一条双链路状态条，不改页面文件。
- [x] 站立 / 接管 / 摇杆 20 Hz / 头部 / 停下 / 卸力 / 重启舵机（桥接已映射，原页面按钮直接可用）。
- [x] 状态详情「链路」卡（手机蓝牙 + 机器人 Wi-Fi）：改写原页面「连接」卡为两条真实链路 + API/MTU，页面文件不动。
- [x] 策略条、告警、只读/离线（原页面已有；桥接喂 `state/policies/ack`，只读固定为否）。
- [ ] 真机动作测试（用户在场）。

---

## 6. M3 · 网络与系统

- [x] 网络状态/扫描/连接/固定 IP/忘记/控制台地址：`ble-network.html`；`net.*` 已在真机验证。
- [ ] 系统身份/改名/服务/日志/重启/诊断。
- [x] 声音 7 个 + wheee 按住 + 音量/静音（原页面面板由桥接映射，`robot.volume` 已实现）。
- [ ] padd / 网页中控冲突提示（原来的提示卡仍在，停止按钮待系统页）。
- [x] 网络失败原因与回退：`connect_failure` 五种原因都映射成中文。

---

## 7. M4 · 加固交付

- [ ] 断链/切后台/杀进程/蓝牙开关零速测试。
- [ ] 华为 Mate 40 Pro 专项。
- [ ] 30 min 连续。
- [ ] 安全：PIN 默认警告、可选配对、密码脱敏。
- [ ] APK 签名/安装说明。
- [ ] 验收文档 `duckphone-ble-acceptance.zh-CN.md`。
- [ ] 回滚验证。

---

## 8. 需要你操作的事项

### 8.1 环境

- [x] **Android SDK 安装**：command-line tools、platform 35、build-tools 35、platform-tools 均已装。
- [x] **接受 SDK license 并装包**（2026-11-26 由用户执行）。
- [x] **Gradle 8.9**：`~/.local/opt/gradle-8.9`，wrapper 已生成。
- [x] **Zig 0.15.1**：本机 `/usr/local/bin/zig` 已是 0.15.1，交叉编译已通过。
- [x] 确认手机 USB 调试/侧载方式：已加 udev 规则、退出纯净模式后侧载成功（2026-11-26）。

### 8.2 机器人

- [ ] 指定可安全重启 `robotd` 的时间（会卸力）。
- [ ] 动作测试时在现场扶稳机器人；确认吊架/地面条件。
- [ ] 确认是否先改 PIN（建议改）；确认是否开启 BLE 配对。
- [ ] 提供测试 Wi-Fi SSID/密码（或确认用现有网络）。
- [ ] 确认 `system.serviceAction` 白名单：只 `padd`，还是也允许停 `duckphone`。

### 8.3 交付

- [ ] 确认 APK 只需调试侧载，还是需要正式签名（提供 keystore/密码）。
- [ ] 确认何时允许 push 到 `fork/dev`。
- [ ] 确认 30 min/华为专项的验收时间。

### 8.4 Android SDK：接受 license 并装包（2026-11-26 已完成）

已由用户执行，`~/Android/Sdk` 里现在是：

```text
cmdline-tools/latest   licenses   platform-tools
platforms/android-35   build-tools/35.0.0
```

---

## 9. AI 可以立即开始的事项

- [x] 文档迁入 `dev`、仓库布局、全局规则。
- [x] 机器人端 proto / btd / robotd / configd 代码与单元测试。
- [x] 机器人端交叉编译（`btd`/`configd` 已进构建脚本）。
- [x] acceptance/probe/deploy/build 脚本。
- [x] Android 工程骨架、`BleClient`、`RobotLink`、`JsBridge`、`ble-bridge.js`。
- [x] 页面副本（`sync-web.sh` 已同步一次）与桥接映射（13 项浏览器断言通过）；M2 的扫描/PIN 页未做。
- [ ] 只读 BLE 验收（需要机器人与你的时间窗）。
- [x] 文档更新（README / 实现计划 / 工具说明）。

## 10. 当前阻塞

| 阻塞 | 影响 | 解除方式 |
| --- | --- | --- |
| 手机未连接 | 不能装 APK / 真机验收 | ✅ 已解除（华为 Mate 40 Pro 已装机） |
| 机器人未确认可重启 | 不能部署/真机验收 | 用户给时间窗 |
| 动作测试需人在场 | 不能验证驾驶 | 用户在场 |
| 发布签名未提供 | 只能调试 APK | 用户提供 keystore |

---

## 11. 验收门槛（逐阶段）

| 阶段 | 门槛 |
| --- | --- |
| M0 | `cargo test` 全过；交叉编译成功；只读 acceptance 通过 |
| M1 | 真机连接/认证/10 Hz 状态；断链重连 |
| M2 | 吊架站立/接管/摇杆/头部/停下/卸力 |
| M3 | 网络扫描/连接/固定 IP；日志/重启；声音/音量 |
| M4 | 断链零速、30 min、华为专项、APK 可安装 |

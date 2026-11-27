# 手机控制 Microduck · 蓝牙版改造方案

> 2026-11-26 · 目标：把 kissqy 里的手机网页控制 App **duckphone** 改造成**手机蓝牙版**
> 决策已定：改造对象 = duckphone；形态 = Android APK + WebView 复用现有 UI；
> 允许改固件（btd 路由 + robotd 精简状态/音量/停手柄）；首版功能完整对齐 duckphone。
>
> 本文只做方案与实施拆解，**代码实现等指令后再开始**。
>
> **2026-11-26 补充**：首版范围增加「PC 蓝牙配网（ducknet）能力」——BLE 连接后可直接查看/配置 Wi-Fi（含固定 IP、忘记网络）、改名、看日志、重启；同时明确**原网页版一行不改，继续在 `:8001` 独立运行**。
> 完整功能清单见 [蓝牙版功能清单](./duckphone-ble-features.zh-CN.md)；
> 完整 UI 设计与可点击原型见 [蓝牙版 UI 设计](./duckphone-ble-ui.zh-CN.md)；
> 三端实现、通讯、仓库、部署与分工见 [蓝牙版实现设计](./duckphone-ble-implementation.zh-CN.md)；
> 执行清单见 [实现计划与分工](./duckphone-ble-implementation-plan.zh-CN.md)。

---

## 1. 结论先行

| 项 | 结论 |
| --- | --- |
| 改造对象 | [duckphone](../../duckphone)（板载 Python 桥 + 竖屏 PWA） |
| 手机端 | Android APK，Kotlin 原生 BLE + 独立页面文件（视觉沿用 duckphone，**不修改原版**） |
| 机器人端 | `btd` 放开驾驶/遥测/声音路由；`robotd` 增加约 300 B 的 phone 精简状态；`configd` 增加停/启 `padd`；`robotd` 增加音量 |
| 网络配置 | 合并 ducknet：`net.status/scan/connect/forget`、固定 IP、忘记网络、控制台地址 |
| 两条链路 | **手机蓝牙**（手机 ↔ 机器人）与**机器人 Wi-Fi**（机器人 ↔ 路由器）分开显示；蓝牙连上不代表机器人有网 |
| 共存 | 原网页版继续在 `:8001` 运行；蓝牙版是独立 APK；同时驾驶会互相覆盖，App 给出冲突提示 |
| 关键约束 | BLE 无应答写 3 ms/帧、有应答写 541 ms/帧 → **20 Hz 控制必须无应答写且一包发完**；全量 `robot.state` 3.9 KB/帧 → **必须精简状态** |
| 不改什么 | 不改原网页版；不做 R17 中控的 3D/摄像头/标定；不做 iOS（本机无 macOS）；不做云端/中继 |

---

## 2. 现状调研

### 2.1 duckphone 是什么

链路：

```text
手机浏览器 ──HTTP/WS :8001──> board 上的 duckphone (Python 标准库) ──unix socket──> robotd
```

- 板上只多一个 Python 进程，页面是离线 PWA，不改 robotd 配置。
- 前端协议很干净（[app.js](../../duckphone/static/app.js)）：
  - 下行：`hello`、`state`、`policies`、`ack`、`session`、`pong`
  - 上行：`hello`、`ping`、`drive`、`head`、`takeover`、`cmd`
- 服务端核心（[server.py](../../duckphone/server.py)）：
  - 订阅 `robot.subscribe` 20 Hz + 轮询 `robot.health` 1 Hz，合成页面状态；
  - 摇杆夹限 `vx ∈ [-0.25, 0.35]`、`vyaw ∈ [-0.8, 0.8]`；
  - 250 ms 看门狗；页面切后台/关闭发 `/stop`；
  - 策略条、声音面板、头部模式、维护页、告警分级。

### 2.2 板上已有的 BLE 能力

- GATT 契约：[duck-ble/src/gatt.rs](../../duck-ble/src/gatt.rs)
  - Service `6f5d2a10-3b47-4c8e-9a1f-2d7e8c4b6019`
  - RPC 特征 `6f5d2a11-…`：读一次取 API 版本，写 NDJSON 请求，订阅同一特征收回答；
  - 分块与重组：[framing.rs](../../duck-ble/src/framing.rs)。
- 机器人侧适配器：[btd](../../btd/src/route.rs)
  - 把 JSON-RPC 原样转发给 `updaterd` / `robotd` / `configd` 的 unix socket；
  - 路由是**显式白名单**，新增方法必须在这里加一行；
  - 已支持流式订阅（`update.subscribe` 的进度流走同一条通知通道）。
- 板上已部署：`btd`、`configd`、`robotd` 均 active（`duck-dillon`，Radxa ZERO 3W）。
- 参考实现：[ducknet](../../ducknet)（Bleak 桌面客户端，分支 `feat/desktop-ble-provisioning`）与上游 [mobile-app.md](./mobile-app.md)。

### 2.3 当前 BLE 真机实测（2026-11-26）

环境：笔记本 Intel BT 5.3（Linux/BlueZ）→ `duck-dillon`，API v40，PIN `000000`，`btd` 未强制配对。

| 项目 | 结果 |
| --- | --- |
| 扫描 / 连接 / 读版本 / PIN 认证 / 通知 / 分块 | 全部通过（链路偶发断开，重试后成功） |
| RTT（`robot.health`，20 次） | min 88.8 / p50 90.9 / p90 133.2 / max 134.6 ms |
| 串行请求吞吐 | 10.4 req/s（96.4 ms/req，等回包） |
| 大回包 `system.logs`（80 行） | **16 237 B / 681 ms ≈ 24 KB/s** |
| `robot.subscribe {hz:5}` 单帧 | **3 872–3 892 B**（约 3.9 KB），20 Hz 即 ≈78 KB/s |
| 20 Hz 控制写（有应答） | **541 ms/帧**（3 个 20 B 分块，每块等 ATT 应答）→ 不可用 |
| 20 Hz 控制写（无应答） | **3 ms/帧**（本地入队；实际空口按连接间隔发送）→ 可用 |
| 已放行 | `system.info`、`robot.health`、`robot.policies`、`robot.loadPolicy`、`robot.init/enable/do/rebootMotors`、`system.services/logs`、`pad.status` 等 |
| 被拒 | `robot.move`、`robot.head`、`robot.stop`、`robot.relax`、`robot.subscribe`、`robot.sound`、`robot.mode`、`robot.mouth` 等 |

> 实测命令与输出记录见 §11。为看清写路径曾临时打开 `btd` 的 debug 日志，已恢复原状，未改动机器人代码。

### 2.4 由此推出的硬约束

1. **控制必须无应答写**：`robot.move` / `robot.head` 用 JSON-RPC **notification（不带 id）**，20 Hz；请求必须一包发完，即使用协商后的 MTU（≥ 64），不能按默认 23 字节切。
2. **遥测必须精简**：全量 3.9 KB 帧在 BLE 上只能到 ~2 Hz，无法支撑摇杆「实际值」和倾角告警；需要 ~300 B 的 phone 状态，10 Hz。
3. **必须重连**：AIC8800 Wi-Fi/BT 共射频，实测会成串断开；客户端要按 8 次 × 1.5 s 重试，并在重连后重新认证、重新订阅。
4. **声音/音量/停手柄现有 API 不够**：`robot.sound` 被拒；音量只有主机 `amixer`；停 `padd` 只有 `sudo systemctl`。需要补固件接口。

---

## 3. 目标架构

```text
┌──────────────────────────── Android 手机 ────────────────────────────┐
│  WebView（复用 duckphone 的 index.html/style.css/app.js）             │
│      │  window.DuckTransport（把原来的 WebSocket 协议原样搬过来）      │
│      │  hello/state/policies/ack  ←→  drive/head/cmd/ping             │
│  JS 桥 ble-bridge.js（server.py 的会话/看门狗/状态映射/夹限逻辑）       │
│      │  DuckBLE.send(line) / onLine(line) / onLink(state)             │
│  Kotlin BLE（扫描、连接、MTU、订阅、无应答写、分块、重连、权限）        │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ BLE GATT（NDJSON + JSON-RPC）
┌───────────────────────────────▼──────────────────────────────────────┐
│  btd：白名单路由 + 会话（PIN 认证、尝试次数、断开即丢弃）              │
│      ├── robotd   ：intent / 策略 / 健康 / phone 精简状态 / 音量       │
│      ├── configd  ：系统信息、服务状态、停/启 padd                     │
│      └── updaterd ：（本方案不用）                                     │
└──────────────────────────────────────────────────────────────────────┘
```

要点：

- **不改 duckphone 的视觉与交互**。前端只把 `new WebSocket(...)` 换成 `createTransport()`；其余事件名、字段、CSS 全部保留。
- **服务端逻辑从 Python 搬到 JS**：`server.py` 的会话、状态合成、夹限、看门狗、策略条、声音、命令分发大约 400 行核心逻辑，端口到 `ble-bridge.js`。
- **协议不漂移**：JSON-RPC 方法名与 `duck-ipc-proto` 对齐；新增方法同步改 proto、btd、robotd、configd 与测试。

---

## 4. 机器人侧改造

### 4.1 btd 路由（`btd/src/route.rs`）

在 `permits()` 中新增/调整：

| 方法 | 现在 | 改为 | 理由 |
| --- | --- | --- | --- |
| `robot.move` | 拒绝 | **允许** | 20 Hz notification；实测无应答写 3 ms/帧，空口可承载 |
| `robot.head` | 拒绝 | **允许** | 同上；头部意图是 notification，本来无回包 |
| `robot.stop` | 拒绝 | **允许** | 只把速度归零，不卸力；不是假 e-stop，UI 文案写「停下」 |
| `robot.relax` | 拒绝 | **允许** | 完整对齐 duckphone 的「长按 1.5 s 卸力」；只在明确长按后发 |
| `robot.sound` | 拒绝 | **允许** | 声音面板 7 个叫声；单次请求，非流 |
| `robot.subscribe` | 拒绝 | **仅 `profile:"phone"` 允许** | 全量帧 3.9 KB 仍拒绝；phone 帧约 300 B |
| `robot.volume`（新增） | — | **允许** | 音量/静音，见 §4.3 |
| `system.serviceAction`（新增） | — | **允许** | 仅 `padd` 的 stop/start，见 §4.4 |
| `robot.init/enable/do/rebootMotors/loadPolicy/policies/health` | 允许 | 不变 | duckphone 已用 |
| `robot.pose/mouth/look/setMode/shutdown` | 拒绝 | 不变 | duckphone 不需要；保持最小攻击面 |
| `robot.theremin/chorale` | 拒绝 | 不变 | 本板无 ToF；合唱不在首版 |

实现注意：

- `route.rs` 的 `permits(&Call)` 可读到参数，`RobotSubscribe(p)` 按 `p.profile == Some(Phone)` 决定；
- 通知（无 id）被拒时保持静默（现有行为）；
- 更新 `only_these_mutating_calls_are_reachable_over_ble` 测试，把新增的每个变更方法逐条写出来；
- `RobotRelax` 的反转要在注释里写明代价：会让机器人立刻瘫下，因此 UI 必须保留长按确认；这是与原设计的有意偏离。

### 4.2 robotd：phone 精简状态

`robot.subscribe` 参数增加可选字段：

```rust
pub struct SubscribeParams {
    pub hz: Option<u32>,
    #[serde(default)]
    pub profile: Option<StateProfile>,   // None = full, Some(Phone) = compact
}

pub enum StateProfile { Phone }
```

`profile = "phone"` 时，`robot.state` 只发以下字段（约 250–350 B）：

```json
{
  "t": 123.45,
  "move": {"requested": [0.15, 0, 0.2], "applied": [0.14, 0, 0.19], "limited_by": []},
  "head": [0, 0, 0, 0],
  "policy": "walk",
  "safety": {"fallen": false, "limp": false, "gravity": [0, 0, -1]},
  "loop": {"hz": 50.0, "missed": 12},
  "enabled": true,
  "homed": true,
  "sitting": false
}
```

- 复用现有 `robot.state` 广播与 per-subscriber 抽取，不改全量帧；
- `enabled/homed/sitting` 来自 `robot.policies` 同一份状态，省掉每帧查策略；
- 客户端仍用 `robot.health` 1 Hz 取电量/电机温度/主控温度；
- `robot.policies` 仍按需调用（策略条、按钮门禁）。

> 备选：新增 `robot.phoneSubscribe` / `robot.phoneState` 方法。更显式，但要多一套 Call/route/handler/测试；本方案选 `profile`，改动面更小。

### 4.3 robotd：音量与静音

新增 `robot.volume`：

```json
// 请求
{"jsonrpc":"2.0","id":7,"method":"robot.volume","params":{"percent":60}}
{"jsonrpc":"2.0","id":8,"method":"robot.volume","params":{"muted":true}}
// 回答
{"jsonrpc":"2.0","id":7,"result":{"percent":60,"muted":false}}
```

- 复用 duckphone 已确认的控制名：`PCM Playback Volume`、`Line Playback Switch`；
- 实现用 `amixer -c <card>`，持久化用 `alsactl store <card>`（与 `server.py` 一致）；
- 声卡从 `/opt/robot/feetech-ft5-r5/voice-device.json` 读取，缺省 `0`；
- `robotd` 以 root 运行，具备权限；
- 读、写都走同一方法，便于 UI 回读。

### 4.4 configd：停/启 padd

新增 `system.serviceAction`：

```json
{"jsonrpc":"2.0","id":9,"method":"system.serviceAction",
 "params":{"unit":"padd","action":"stop"}}
{"jsonrpc":"2.0","id":9,"result":{"accepted":true,"state":"inactive"}}
```

- **严格白名单**：`unit` 只允许 `padd`；`action` 只允许 `stop|start`；
- 由 root 的 `configd` 执行 `systemctl`，避免 robotd 走 sudo；
- 语义低风险：停手柄服务不会让机器人动；UI 仍要说明「停掉后实体手柄不可用，需手动 start」；
- 若不想新增此方法，首版可只显示命令文本，但这会缺 duckphone 的「停止手柄服务」按钮。

### 4.5 协议与版本

- `duck-ipc-proto`：`API_VERSION` 40 → **41**；
- 新增：`SubscribeParams.profile`、`Call::RobotVolume`、`Call::SystemServiceAction` 及对应 `method::*`、params/result 类型；
- 所有新增 params 使用 `#[serde(default)]`，未知字段策略保持项目现有约定；
- `btd` 的 GATT 读会返回 41；App 握手时要求 `api_version >= 41`，低于则明确提示「请先升级机器人固件」。

### 4.6 构建与部署

现状：`tools/build-firmware.sh` 只构建 `robotd/robotctl/padd/sounds/gamesir-xboxd`，**不含 `btd`**；板上 `btd` 是手工部署的。

改造：

1. `tools/build-firmware.sh` 的 `-p` 列表加入 `btd`，产物列表加入 `btd`；
2. 打包/安装加入 `btd.service`、`sysusers.d/btd.conf`、`btd` 二进制；
3. 安装时确保 `configd --allow-user btd`；
4. 对 `btd` 做与 `robotd` 相同的 zigbuild 目标（`aarch64-unknown-linux-gnu.2.31`）；
5. 部署脚本沿用 `ducknet/deploy_ble_provisioning.sh` 的思路，合并成一条「构建 + 安装 + 重启」的固定流程。

---

## 5. 手机 App 设计

### 5.1 工程形态

- **Kotlin + 原生 Android**，不引入 Flutter/Node；只依赖 AndroidX 基础库与 `android.webkit.WebView`。
- 目录（放在 kissqy 仓库 **`dev` 分支**，代码与固件同仓）：

```text
microduck-hd1910/firmware/
├── docs/design/
│   ├── duckphone-ble-plan.zh-CN.md
│   ├── duckphone-ble-features.zh-CN.md
│   ├── duckphone-ble-ui.zh-CN.md
│   ├── duckphone-ble-implementation.zh-CN.md
│   └── duckphone-ble-implementation-plan.zh-CN.md
└── duckphone-ble/
    ├── android/
    │   ├── app/src/main/java/.../MainActivity.kt
    │   ├── app/src/main/java/.../BleClient.kt          # 扫描/连接/MTU/通知/写
    │   ├── app/src/main/java/.../RobotLink.kt          # 分块/重组/JSON-RPC/重连
    │   ├── app/src/main/java/.../JsBridge.kt           # @JavascriptInterface
    │   ├── app/src/main/assets/duckphone/              # 独立页面（从原版复制后演进）
    │   └── app/src/main/res/…
    ├── design/{prototype.html,screens/}
    ├── tools/{sync-web.sh,acceptance.py,probe_ble.py,deploy_robot.py,build_apk.sh,install_apk.sh,setup_pc.sh}
    └── README.zh-CN.md
```

> **原版目录 `firmware/duckphone/` 不动。** 蓝牙版以它为视觉与交互基线做一次性复制，之后在 `duckphone-ble/` 内独立演进（新增连接页、机器人中心、网络/系统页）。
> 设计文档放 `firmware/docs/design/`；App 说明放 `duckphone-ble/README.zh-CN.md`；不再往 `ops/` 写新文档/脚本。

### 5.2 BLE 客户端

| 步骤 | 做法 |
| --- | --- |
| 扫描 | `BluetoothLeScanner`，按 Service UUID 过滤；同时解析名字与广播 IPv4（可选） |
| 连接 | `connectGatt(..., TRANSPORT_LE)`；`requestConnectionPriority(HIGH)`；连接间隔目标 ≤ 30 ms |
| MTU | `requestMtu(517)`；`onMtuChanged` 后按 `mtu - 3` 分块（上限 512） |
| 订阅 | 读 RPC 特征拿 API 版本；写 CCCD `0x2902 = 01 00`；`onCharacteristicChanged` 累积、按 `\n` 切行 |
| 写 | `WRITE_TYPE_NO_RESPONSE`；控制请求一包发完；命令请求也尽量一包 |
| 重连 | 断开后指数退避（0.5/1/2/4 s），每轮 8 次；重连后重新认证、重新订阅，不重放动作 |
| 权限 | Android 12+：`BLUETOOTH_SCAN`（`neverForLocation`）+ `BLUETOOTH_CONNECT`；≤11：定位权限 |
| 生命周期 | 驾驶时 `FLAG_KEEP_SCREEN_ON`；`onPause` 先发零速/头部回正再断开；后台不保持控制 |

### 5.3 JS 桥（复用前端的核心）

- 在蓝牙版自己的 `app.js` 副本里把 `new WebSocket(wsURL())` 改成 `window.createDuckTransport()`（只改这一处）；**原版 `firmware/duckphone/static/app.js` 不动**；
- `ble-bridge.js` 实现与 `server.py` 相同的消息面：
  - 收到 `{t:"hello"}` → 回 `{t:"hello",ok:true,role:"driver",clamp:{...}}`；
  - 订阅 phone 状态 + 1 Hz health，合成 `{t:"state",...}`；
  - `{t:"drive"}` / `{t:"head"}` → `robot.move` / `robot.head`（无 id，20 Hz，夹限）；
  - `{t:"cmd"}` → 站立/接管/停下/卸力/重启舵机/策略/声音/音量/停手柄；
  - 250 ms 看门狗；`pagehide/visibilitychange` 发停止；
  - 策略条门禁、告警分级、只读状态，沿用 `server.py` 的规则。
- 原生侧只暴露最小接口：

```text
DuckBLE.scan() -> JSON 列表
DuckBLE.connect(address, pin)
DuckBLE.disconnect()
DuckBLE.send(line)                 // 一条完整 NDJSON（原生负责分块）
DuckBLE.onLine(line)               // 原生 → JS
DuckBLE.onLink({state, reason})    // connecting/ready/down
```

- PIN 存在 Android Keystore（EncryptedSharedPreferences 或自带 AES），不落明文日志。

### 5.4 界面与交互（保持原设计）

| 页面 | 变化 |
| --- | --- |
| 启动/连接 | 新增：扫描列表（名字、RSSI、可选 IPv4）+ PIN 输入 + 记住；原「离线」页保留 |
| 主界面 | 不变：策略条、摇杆/头部切换、2×2 动作、速度档、倾角、声音/维护入口 |
| 顶栏 | 第一行蓝牙 chip（手机↔机器人）+ 状态；第二行 Wi-Fi chip（机器人↔路由器）+ 状态；两者绝不合并 |
| 机器人中心 | 新增全屏页，3 个页签：连接 / 网络 / 系统 |
| 网络页 | 新增（来自 ducknet）：状态卡、Wi-Fi 扫描、连接（密码 + 固定 IP）、忘记网络、控制台地址 |
| 系统页 | 新增（来自 ducknet）：身份/改名、服务状态、日志、重启、高级诊断 |
| 状态页 | 「连接」卡片显示 BLE 名称/RSSI；「输入源」增加蓝牙/padd/网页中控 |
| 维护页 | 「停止手柄服务」改走 `system.serviceAction`；增加网络/系统入口；排障命令仍可复制 |
| 声音面板 | 7 个声音走 `robot.sound`；音量/静音走 `robot.volume`；`wheee` 按住 ~10 Hz 发 `hold:true` |
| 只读态 | 单中心连接：另一台手机占用时提示「另一台手机已连接」；标定模式显示只读 |
| 离线态 | 「蓝牙未连接」+ 重试 + 打开系统蓝牙设置 + 排障页 |
| 冲突提示 | padd / 网页中控运行时黄条提示；详情可停用（需确认），不改网页版代码 |

手势、竖屏、安全区、字体、颜色、按钮尺寸全部沿用现有视觉语言；新增页面只使用同一套 tokens，不引入第二套设计。

### 5.5 安全与状态机

- **只有一台手机能控制**：`btd` 同时只服务一个中心；第二台连接失败时明确提示。
- **驾驶权**：APK 内固定为 driver；不做多浏览器抢权（原 `takeover` 逻辑删除或置灰）。
- **停止路径**（必须全部成立）：
  1. 「停下」按钮 → `robot.stop`；
  2. 摇杆松手 → 250 ms 内发 `vx=vyaw=0`；
  3. 切后台/锁屏/关页面 → 先发零速再断开；
  4. 蓝牙断链 → `robotd` 500 ms deadman 自动归零；
  5. App 被杀 → 同上。
- **高危动作**：卸力保留「长按 1.5 s」；重启舵机保留二次确认；站立仍提示「会真的上力回 HOME」。
- **认证**：默认 PIN `000000` 不安全，App 首次连接提示先执行 `robotctl system set-pin`；PIN 错误显示剩余次数。
- **加密**：首版沿用 PIN 门禁；Android 真机验证通过后可开 `btd --require-pairing`（Just Works 加密绑定），并把「未加密」警告写进 README。

---

## 6. 接口契约汇总

### 6.1 新增/变更

| 层 | 变更 |
| --- | --- |
| GATT | 不变（Service/RPC UUID 冻结） |
| 分帧 | 不变（NDJSON，`\n` 结尾，双向分块） |
| JSON-RPC | 新增 `robot.volume`、`system.serviceAction`；`robot.subscribe` 增加 `profile:"phone"` |
| 通知 | `robot.state` 在 phone profile 下为精简帧；控制用无 id notification |
| 版本 | `API_VERSION` 41；App 要求 ≥41 |

### 6.2 方法/字段对照（duckphone → BLE）

| duckphone 动作 | 现有 RPC | BLE 后 |
| --- | --- | --- |
| 状态流 | `robot.subscribe {hz:20}` | `robot.subscribe {hz:10,profile:"phone"}` |
| 电量/温度/控制环 | `robot.health` 1 Hz | 不变 |
| 摇杆 | `robot.move` 20 Hz | 无 id notification，20 Hz，夹限 |
| 头部 | `robot.head` 20 Hz | 无 id notification，20 Hz，夹限 |
| 站立 | `robot.init` | 不变（已允许） |
| 接管/交还 | `robot.enable` | 不变（已允许） |
| 停下 | `robot.stop` | 新允许 |
| 卸力 | `robot.relax` | 新允许（长按） |
| 重启舵机 | `robot.rebootMotors` | 不变（已允许） |
| 策略条 | `robot.policies` / `robot.loadPolicy` / `robot.do` | 不变（已允许） |
| 声音 | `robot.sound` | 新允许 |
| 音量/静音 | 主机 `amixer` | `robot.volume`（新增） |
| 停手柄 | 主机 `sudo systemctl stop padd` | `system.serviceAction`（新增） |
| 版本/服务/日志 | `system.info/services/logs` | 不变（已允许） |

---

## 7. 实施顺序

### M0 · 机器人侧（先让 BLE 能做完整控制）

1. proto：`API_VERSION` 41、`profile`、`robot.volume`、`system.serviceAction`；
2. `btd`：路由白名单 + 测试；
3. `robotd`：phone 精简状态 + 音量；
4. `configd`：停/启 padd 白名单；
5. 构建脚本加入 `btd`；交叉编译；部署到 `duck-dillon`；
6. 用笔记本 Bleak 脚本做真机验收：认证、phone 状态 10 Hz、20 Hz 无应答写、音量、停 padd、重连。

**门槛**：BLE 链路能稳定跑 20 Hz 控制 + 10 Hz 精简状态 10 分钟。

### M1 · App 传输层

1. Android 工程与权限；
2. BLE 扫描/连接/MTU/订阅/写/重组；
3. JSON-RPC 会话、PIN 认证、重连；
4. 假机器人（本地 NDJSON 回环）跑单元测试；
5. 页面里显示原始状态，验证链路。

**门槛**：真机连接后能收到 10 Hz 状态，20 Hz 写不丢帧。

### M2 · 主界面复用

1. `ble-bridge.js` 端口 `server.py` 的状态合成/夹限/看门狗；
2. `app.js` 换传输层（一处）；
3. 站立/接管/摇杆/头部/停下/卸力；
4. 顶栏、状态页、离线/只读覆盖层。

**门槛**：吊架上完成 A1–A5（站立、接管、摇杆、卸力、重启舵机）。

### M3 · 完整对齐

1. 策略条（列表、切换、门禁）；
2. 声音面板（7 声 + 音量/静音）；
3. 维护页（停 padd、版本、排障）；
4. 告警分级与最近消息；
5. 连接页/PIN 记住/多机器人列表；
6. 机器人中心：网络页（状态/扫描/连接/固定 IP/忘记）与系统页（身份/改名/服务/日志/重启/诊断）；
7. 控制源冲突提示（padd / 网页中控）。

**门槛**：duckphone §6 验收表在 BLE 下重跑通过。

### M4 · 加固与交付

1. 断链/切后台/杀进程/蓝牙开关的停止路径测试；
2. 华为 Mate 40 Pro 专项；
3. APK 签名与安装说明；
4. 文档：`firmware/docs/design/duckphone-ble-acceptance.zh-CN.md`；
5. 回滚方案（关 `btd` 不影响 LAN duckphone）。

---

## 8. 测试与验收

### 8.1 机器人侧

- `cargo test -p btd`：路由白名单、拒绝通知静默、流式订阅；
- `cargo test -p robotd`：phone 帧大小/字段、音量、订阅解耦；
- `cargo test -p configd`：`serviceAction` 白名单；
- `cargo build --release --target aarch64-unknown-linux-gnu.2.31 -p btd -p robotd -p configd`；
- 真机：`systemctl restart btd robotd configd` 后，用 Bleak 脚本跑 §11 的探针。

### 8.2 App 侧

- JVM 单元测试：分块/重组、JSON-RPC id 匹配、超时、重连状态机、夹限、看门狗；
- 假链路回放：把真机录制的状态/回答做成 fixture，UI 不接蓝牙也能跑；
- 真机：Android 12+（华为）安装 APK。

### 8.3 真机验收表（沿用 duckphone 结构）

| # | 项目 | 通过条件 |
| --- | --- | --- |
| B1 | 扫描/连接/PIN | ≤10 s 连上；错误 PIN 显示剩余次数 |
| B2 | 站立 | 2 s 内回 HOME；状态页 policy 变化 |
| B3 | 接管 | 顶栏变「行走」，摇杆可用 |
| B4 | 摇杆 20 Hz | 松手 ≤250 ms 归零（App 侧）；≤500 ms（robotd deadman） |
| B5 | 头部 | 行走时可用；松手回正；非 walk 时禁用 |
| B6 | 停下 | 速度归零，不卸力 |
| B7 | 卸力 | 长按 1.5 s 一步生效；机器人瘫下 |
| B8 | 重启舵机 | 二次确认；先卸力再重启 |
| B9 | 策略条 | 6 个槽位正确；切换后门禁正确 |
| B10 | 声音/音量 | 7 个声音可播；音量/静音回读一致 |
| B11 | 停 padd | 一键停止，`padd: inactive` |
| B12 | 断链 | 关蓝牙/走远/杀 App → ≤500 ms 归零 |
| B13 | 重连 | 回范围后自动重连、重新认证、状态恢复；不重放动作 |
| B14 | 切后台 | 立即零速；回来可恢复 |
| B15 | 30 min | 控制环不掉、CPU <70 °C、无累积告警 |
| B16 | 华为专项 | 权限、锁屏、字体放大、全屏、振动、电池优化 |

---

## 9. 风险与缓解

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| AIC8800 共射频，BLE 偶发断开 | 驾驶中断 | 8 次重试 + 指数退避；断链即零速；README 说明；必要时换 USB 蓝牙适配器复测 |
| 手机连接间隔偏大（30–50 ms） | 20 Hz 控制偏紧 | 请求 MTU 517 + `CONNECTION_PRIORITY_HIGH`；控制一包；必要时降到 15 Hz |
| 全量状态帧过大 | 状态滞后/丢帧 | phone profile 300 B + 10 Hz；不上全量 |
| 固件改动引入回归 | 机器人异常 | 路由白名单最小化、逐项测试、灰度部署、可回滚 |
| 未加密链路 | PIN 可被旁听 | 首次使用改 PIN；Android 验证后开 `--require-pairing` |
| WebView 兼容/本地存储 | 页面异常 | 用 `WebViewAssetLoader` 或本地 assets；`domStorageEnabled`；保持原 PWA 结构 |
| 华为后台限制 | 切后台断连 | 明确「驾驶时保持前台」；断链零速；不追求后台驾驶 |
| `robot.loadPolicy` 重写配置 | 槽位 key 丢失 | 既有问题，不扩大；验收时复查 7 个槽位（沿用 duckphone §9.6 待办） |
| 无 macOS | iOS 不可交付 | 首版只做 Android；跨平台留到以后 |

---

## 10. 不做什么

- 不做 R17 中控的摄像头、3D 姿态、舵机标定、实体手柄映射；
- 不做 iOS（本机无 macOS/Xcode）；
- 不做云端/远程中继（BLE 10 m 内）；
- 不做固件升级、恢复出厂、改 PIN（这些仍走 `robotctl`/`ducknet`）；
- 不做多手机抢权（`btd` 同时只服务一个中心）。

---

## 11. 实测记录（2026-11-26）

环境：Ubuntu 24.04 / Intel BT 5.3 / BlueZ；机器人 `duck-dillon`（Radxa ZERO 3W，API 40，PIN 000000，`btd` 未强制配对）。

### 11.1 方法可用性

```text
[OK ] system.info       89.6 ms
[OK ] robot.health      94.3 ms
[OK ] robot.policies   137.2 ms
[REF] robot.mode        84.0 ms  code=14 not available over Bluetooth
[REF] robot.subscribe   89.9 ms  code=14 not available over Bluetooth
[REF] robot.move        87.6 ms  code=14 not available over Bluetooth
[REF] robot.head        87.4 ms  code=14 not available over Bluetooth
[REF] robot.stop        87.4 ms  code=14 not available over Bluetooth
[REF] robot.mouth       90.9 ms  code=14 not available over Bluetooth
[OK ] system.services  226.7 ms
[OK ] system.logs      681.2 ms  bytes=16237
```

### 11.2 延迟与吞吐

```text
RTT x20 robot.health: min=88.8 p50=90.9 p90=133.2 max=134.6 ms
串行 20 次：1.93 s（10.4 req/s，96.4 ms/req）
system.logs 80 行：16 237 B / 681 ms ≈ 24 KB/s
robot.subscribe {hz:5}：3872–3892 B/帧
```

### 11.3 20 Hz 写（40 帧无 id）

```text
有应答写：total 22.02 s / 40，p50 541 ms，p90 585 ms
无应答写：total  2.00 s / 40，p50   3 ms，p90   6 ms
```

### 11.4 链路稳定性

- 同一位置连续两次在「认证写入后」断开（`btd` 日志：`the central is gone; session discarded`）；
- 第三次及之后稳定；`btmon` 显示连接间隔约 37–42 ms；
- 结论：必须按 ducknet 的 8 轮重试处理，不能把一次连接失败当成机器人故障。

### 11.5 现场操作

- 为观察写路径临时给 `btd` 加过 `RUST_LOG=debug` drop-in，已删除并重启恢复；
- 未发送任何会移动机器人的命令；`robot.head` 参数错误测试发生在路由拒绝之前，未产生动作。

---

## 12. 参考

- duckphone：[README](../../duckphone/README.md)、[server.py](../../duckphone/server.py)、[app.js](../../duckphone/static/app.js)
- 功能清单：[蓝牙版功能清单](./duckphone-ble-features.zh-CN.md)
- UI 设计：[蓝牙版 UI 设计](./duckphone-ble-ui.zh-CN.md)
- 可点击原型：[prototype.html](../../duckphone-ble/design/prototype.html)
- 设计与验收：[原网页版设计 lan-phone-remote.md](./lan-phone-remote.md)、[duckphone README](./lan-phone-remote.md)
- ducknet（PC 蓝牙配网）：[ble-provisioning-app.md](./ble-provisioning-app.md)
- 声音/头部：[dynamic-sound.md](./dynamic-sound.md)
- BLE 基础设施：[ble-provisioning-app.md](./ble-provisioning-app.md)
- 协议与路由：[duck-ipc-proto/src/lib.rs](../../duck-ipc-proto/src/lib.rs)、[btd/src/route.rs](../../btd/src/route.rs)
- 状态帧：[robotd/src/main.rs](../../robotd/src/main.rs#L3987-L4060)
- 上游手机 App 设计：[mobile-app.md](./mobile-app.md)

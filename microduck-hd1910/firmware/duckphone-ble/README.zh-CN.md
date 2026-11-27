# duckphone-ble · 手机蓝牙版

> 状态：机器人端（API 42）、App 传输层与调试 APK 均已构建通过 · 分支：`dev`
> 原网页版 `firmware/duckphone/` 保持不动，继续在 `http://<机器人IP>:8001` 独立运行。

## 当前进度

| 层 | 内容 | 状态 |
| --- | --- | --- |
| 机器人 | `duck-ipc-proto` API 42、`btd` 路由、`robotd` 预设动作播放器 / phone 帧与音量、`configd` 服务动作 | ✅ 测试、交叉编译、真机部署通过 |
| PC 工具 | `probe_ble.py` / `acceptance.py` / `deploy_robot.py` / 构建安装脚本 | ✅ 构建安装可用（PC 直连 BLE 仍受 BlueZ 回收设备影响） |
| App | Android 工程、`BleClient` / `RobotLink` / `JsBridge`、`ble-bridge.js` | ✅ 20 项 JVM 测试 + 23 项桥接断言通过 |
| APK | `duckphone-ble-debug-*.apk`、`duckphone-ble-release-*.apk`（自签名） | ✅ 已装机，debug 与 release 均产出 |
| 网络页 | `ble-network.html`：状态 / 扫描 / 连接 / 固定 IP / 忘记 / 控制台地址 | ✅ 状态、扫描、刷新真机通过 |
| 真机 | 连接 / 认证 / API 42 | ✅ 手机侧通过 |
| 真机 | 主流程：站立→接管→摇杆→停下→卸力 | ✅ 全部通过（摇杆 0.05 m/s、松手即停） |
| 真机 | 页面：声音 / 详情抽屉 / 维护 / 网络 | ✅ 通过（右脚踢缺模型、前滚翻待冷却补测） |
| 真机 | 断链：强杀 App 后零速 + 自动重连 | ✅ 死手 500 ms 清零，8 s 内重连 |
| 真机 | 预设动作：抬头 / 左右看 / 画圈 / 张嘴 | ✅ 轨迹、声音、停止、摇杆打断全部通过（API 42） |
| 交付 | release 签名、验收记录 | ✅ 见 [验收记录](../docs/design/duckphone-ble-acceptance.zh-CN.md) |

## 这是什么

一个 Android App：通过 BLE 直连机器人，提供：

- 驾驶：站立 / 接管 / 摇杆 / 头部 / 停下 / 卸力 / 重启舵机；
- 策略条、声音与音量；
- 机器人 Wi-Fi 配置（状态 / 扫描 / 连接 / 固定 IP / 忘记）；
- 系统：身份 / 改名 / 服务 / 日志 / 重启 / 高级诊断。

**手机蓝牙 ≠ 机器人 Wi-Fi**：

| 链路 | 连接谁 | 断开影响 |
| --- | --- | --- |
| 手机蓝牙 | 手机 ↔ 机器人 | 不能驾驶；机器人 Wi-Fi 可能仍在线 |
| 机器人 Wi-Fi | 机器人 ↔ 路由器 | 蓝牙仍可驾驶和配网；网页版/SSH 不可达 |

## 文档

- [改造方案](../docs/design/duckphone-ble-plan.zh-CN.md)
- [功能清单](../docs/design/duckphone-ble-features.zh-CN.md)
- [UI 设计](../docs/design/duckphone-ble-ui.zh-CN.md)
- [实现设计](../docs/design/duckphone-ble-implementation.zh-CN.md)
- [实现计划与分工](../docs/design/duckphone-ble-implementation-plan.zh-CN.md)
- [真机验收 Spec](../docs/design/duckphone-ble-acceptance-spec.zh-CN.md)
- [真机验收记录](../docs/design/duckphone-ble-acceptance.zh-CN.md)
- [可点击原型](design/prototype.html)

## 目录

```text
duckphone-ble/
├── android/                    # Kotlin 工程
│   └── app/src/main/java/com/microduck/phone/
│       ├── MainActivity.kt     # WebView + 权限 + 注入桥
│       ├── ble/BleClient.kt    # 扫描/连接/MTU/通知/两种写
│       ├── ble/Framer.kt       # 分块与拼行（纯函数，可 JVM 测）
│       ├── ble/RobotLink.kt    # JSON-RPC id/超时/错误
│       ├── ble/Limits.kt       # 摇杆夹限
│       └── web/JsBridge.kt     # JS ↔ Kotlin 唯一接口
├── assets/
│   ├── ble-bridge.js           # 注入页面：WebSocket 替身 + 页面协议翻译 + 页面文案补丁
│   ├── ble-page.css            # App 专用补丁样式（网格等宽、长串换行）
│   ├── ble-help.html           # 蓝牙版排障页（替换网页版 help.html）
│   ├── ble-connect.html        # 连接页：扫描 / PIN / 进度（App 启动页）
│   ├── ble-network.html        # 机器人 Wi-Fi：状态 / 扫描 / 连接 / 固定 IP / 忘记
│   └── duckphone/              # 页面副本（tools/sync-web.sh 单向同步）
├── design/
│   ├── prototype.html
│   └── screens/
├── tools/
│   ├── duckble.py              # PC 侧 BLE 传输库
│   ├── probe_ble.py            # 只读探针
│   ├── acceptance.py           # 真机验收 A1–A10
│   ├── deploy_robot.py         # 备份/推送/安装/重启/回滚
│   ├── setup_pc.sh             # Python venv
│   ├── sync-web.sh             # 页面单向复制
│   ├── build_apk.sh / install_apk.sh
│   ├── test_bridge.sh          # 无头 Chrome 跑桥接自测
│   └── tests/bridge_test.html
└── README.zh-CN.md
```

## 依赖

- JDK 21（已具备）
- Android SDK：platform 35、build-tools 35、platform-tools（已装好，license 已接受）
- Gradle 8.9：`~/.local/opt/gradle-8.9`；`android/gradle/wrapper/` 已生成，可直接 `./gradlew`
- 机器人端 `btd` / `robotd` / `configd`（API 42）
- PC 验收：Python 3.12 + Bleak（`tools/setup_pc.sh` 建 venv）

## 构建与安装

```bash
# 机器人固件（btd/configd/robotd/robotctl/padd/sounds）
bash ../../tools/build-firmware.sh

# PC 验收环境
bash tools/setup_pc.sh

# 桥接自测（不碰蓝牙）
bash tools/test_bridge.sh

# APK（已可构建）
bash tools/build_apk.sh
bash tools/install_apk.sh     # 手机用 USB 连上、打开 USB 调试后
```

### 华为真机侧载的两个坑（2026-11-26 实测）

1. **`adb devices` 报 `no permissions`**：需要一条 udev 规则，只给 `plugdev` 组读写：

   ```bash
   echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="12d1", MODE="0660", GROUP="plugdev"' \
     | sudo tee /etc/udev/rules.d/51-android.rules
   sudo udevadm control --reload-rules && sudo udevadm trigger --subsystem-match=usb
   ```

2. **`INSTALL_FAILED_ABORTED: User rejected permissions`**：纯净模式的「增强防护」只允许安装
   过华为应用市场检测、有 ICP 备案的应用，我们自己的调试包永远过不了。先在
   设置 → 系统和更新（或 安全）→ 纯净模式 → 退出，再装。
   另外安装确认页需要**屏幕解锁且亮着**，锁屏状态下会直接失败。

3. **调试期间别让它锁屏**：`adb shell svc power stayon true`（充电时常亮），或开发者选项里
   打开「不锁定屏幕」。锁屏是调试时最常见的"卡住"来源，和权限/签名都没关系。
   蓝牙权限可以脚本预授权，不用每次点允许：

   ```bash
   adb shell pm grant com.microduck.phone android.permission.BLUETOOTH_SCAN
   adb shell pm grant com.microduck.phone android.permission.BLUETOOTH_CONNECT
   ```

### 真机日志

```bash
adb logcat -s DuckLink DuckWeb    # DuckLink：链路状态 + RPC 失败；DuckWeb：页面 console
```

## PC 验收

```bash
# 只读：扫描 / API 版本 / MTU / 认证 / 10 Hz phone 状态 / 网络 / 服务
tools/.venv-ble/bin/python tools/probe_ble.py --name duck-3f9c --pin 000000

# 验收：加 --allow-writes（20 Hz 零速写、stop、音量），再按需加 --allow-service-action
tools/.venv-ble/bin/python tools/acceptance.py --name duck-3f9c --pin 000000 --allow-writes
```

两个实测出来的协议细节（PC 客户端必须照做）：

1. **版本读回是一个字节**：`btd` 写的是 `API_VERSION as u8`（40 → `0x28`），不是 `"40"` 文本。
   `duckble._decode_version` 两种都认。
2. **MTU 要显式取**：bleak 3.1 的 BlueZ 后端不会自动协商，需要
   `await client._backend._acquire_mtu()`，否则永远读到 23、控制帧退化成 3 块写。
3. **先读版本再订阅**：BlueZ 会把这次读取的缓存值也推给已订阅的客户端，先订阅就会收到
   一个孤立的版本字节，和后面的 JSON 拼成一行导致解析失败。

2026-11-26 实测（API 40 旧固件）：扫描/连接/认证/`robot.health`/`system.info`/
`system.services`/`net.status` 全部通过，MTU 517；`robot.subscribe{profile}` 被旧固件
以 `unknown field profile` 拒绝——部署 API 41 后才会通过。

手机侧同日实测（华为 NOH-AN00，API 40）：扫描到 `duck-dillon`、广播 IPv4 与 `net.status`
一致、`connecting → connected → ready mtu=517`、PIN 认证通过；版本读回 40 后连接页停在
「连接失败：机器人固件是 API 40，需要 41」而不是跳进驾驶页。

2026-11-27 实测（API 42，预设动作）：`robot.action` 经桥转发到 `robotd`，四个动作的
`act` 均在状态帧中出现；点「停止」或推摇杆后 `act` 立即消失、头/嘴回中；从 `robotd`
侧取消时蓝牙页也会在一个状态帧内自行清掉“正在播放”，不再依赖本地计时器。

## App 如何连上机器人

页面本身不改，连接参数由 `ble-bridge.js` 读取，优先顺序：

1. `window.duckBle.connect(address, pin)`（M2 的扫描/配对页会用它）
2. URL 参数 `?bleAddress=..&blePin=..`（adb 侧载调试方便）
3. `localStorage` 的 `duckble.address` / `duckble.pin`

没有配置时页面会显示离线，原因写在 `window.duckBle.state().detail` 里。

### 断线与假连接

- **真断线**（走远、机器人断电）：原生回调 `down`，桥接关闭页面那条替身 WebSocket；原生自动重拨，重连成功后
  `ready` 会重新走认证/订阅。
- **假连接**（对端 `btd` 重启、适配器卡住）：GATT 还挂着，但所有 RPC 都超时。桥接对 1 Hz 的 `robot.health`
  连续 5 次失败即判定假连接，主动 `disconnect` 后重拨，约 15 s 内 RPC 恢复。
- **页面对不上**：页面在 `new WebSocket()` 之后才挂 `open` 监听，所以替身 socket 的 `open` 必须异步补发；
  重连成功 4 s 页面仍未 `hello` 就整页重载兜底。真机重启 `btd` 复测两次，约 25 s 自动回到驾驶页。

### 页面适配（不改页面副本）

`assets/duckphone/` 是 `firmware/duckphone/static/` 的单向副本，改副本会被 `tools/sync-web.sh` 覆盖，
所以 BLE 专属的文案与样式全部放在三处 App 自己的文件里，网页版不受影响：

- **`ble-bridge.js` 的 `patchPage()`**：页面脚本跑完后改写网页版文案，并用 `MutationObserver` 兜住
  页面 5 s 一次的覆盖写。
  - 离线浮层：删掉「手机与鸭子在同一 Wi-Fi」，改为蓝牙说法；补设备名 · 地址、
    上次连接（时间 · 策略 · 电量）和断开原因。`duck.last.policy` 存的是英文 id（`held`），
    这里翻成中文；`link.downReason` 单独记录，避免被 `connecting <地址>` 覆盖。
  - 连接卡 `#stConn` / `#stIp`：页面写的是 `WebSocket` 与 `location.host`，这里改为
    「手机蓝牙 已连接」和「机器人 IP · api · MTU」。
  - 维护页排障行换成蓝牙说法；排障按钮指向 `ble-help.html`。
- **`ble-page.css`**：状态抽屉两列等宽。原因是 `1fr 1fr` 的轨道最小尺寸是 min-content，
  `appassets.androidplatform.net`、`policy=held` 这类长串会把左列撑到 231 px、右列压到 132 px
  并伸出屏幕；改成 `repeat(2,minmax(0,1fr))` + `min-width:0` + `overflow-wrap:anywhere` 后
  实测 159/159 px、无横向滚动。窄屏（≤340 px）退回单列（273 px）。声音 / 维护抽屉、连接页、
  网络页在 360 与 320 px 下同样审计过，无横向溢出。
- **`ble-help.html`**：蓝牙版排障页（权限、扫不到、PIN、连不上、蓝牙与 Wi-Fi 的关系、重启服务）。

原型 [design/prototype.html](design/prototype.html) 已同步这两处 UI（离线浮层设备信息、状态抽屉等宽六卡）。
后续新页面按这个原型做。

### 应用图标与跨页状态

- **图标**：用用户提供的机器人插画（`design/app-icon-source.png`），品牌黄底 `#FFC53D`。
  前景 `drawable-xxxhdpi/ic_launcher_foreground.png` 为 432×432 透明图，主体按 62% 居中，
  四周留出圆形遮罩余量；背景 `ic_launcher_background.xml` 纯黄，由
  `mipmap-anydpi-v26/ic_launcher*.xml` 组成自适应图标。最小 SDK 26，不需要 PNG 兜底。
  选型预览留在 `design/app-icon-preview.png`。
- **App 内导航不断连**：`pagehide` 只关页面这一侧的替身 socket，不调 `DuckNative.disconnect()`；
  `BleClient.connect()` 遇到同地址且链路还活着时直接回报当前状态（日志 `ready 复用已有连接`）。
  「连接页 → 驾驶页」也不再先断开。
- **首帧快照**：桥接把最近一次可用状态写进 `sessionStorage`（`duckble.live`，30 秒有效），
  新页面先用它渲染链路条、状态卡和网络页，再被实时数据覆盖。真断线会清掉快照，
  不会出现「明明断着却显示已连接」。
- **不做整页重载**：认证完成时只有 socket 还关着才重置 `pageBound` 等下一次 `open`；
  已经由快照分支 open 过的页面直接算握手完成。否则 4 秒兜底会误判「没握手」并
  `location.reload()`，表现就是驾驶页每 4 秒闪一下。
- **排障页**：`window.open` / `<a href>` 里的 `help.html` 一律改走 `ble-help.html`（蓝牙优先文案）。

## 安全

- 默认 PIN `000000` 不安全；首次使用先 `robotctl system set-pin`。
- 未加密链路会显示警告；Wi-Fi 密码经过 BLE 时注意环境。
- 卸力长按、重启二次确认、站立提示、标定只读。
- 任何会动机器人的测试都需要有人在现场扶稳。

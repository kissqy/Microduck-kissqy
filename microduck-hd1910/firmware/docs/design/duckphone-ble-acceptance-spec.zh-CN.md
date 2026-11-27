# duckphone-ble 真机验收 Spec

> 设计依据：[duckphone-ble-implementation-plan.zh-CN.md](./duckphone-ble-implementation-plan.zh-CN.md)（M0–M4 任务表）、
> [duckphone-ble-plan/implementation/features/ui.zh-CN.md](./duckphone-ble-plan/implementation/features/ui.zh-CN.md)（页面契约）。
> 本文件只定「剩下的验收怎么做、改哪些文件、怎么算通过」，不重复设计理由。
> 日期：2026-11-26。范围外：原网页版 `firmware/duckphone/`、中控 `firmware/console/`、配网 `firmware/ducknet/` 一律不改。

## 1. 现状（截至 2026-11-26 21:32，真机 NOH-AN00 + duck-dillon）

| 能力                    | 结论         | 证据                                                                   |
| --------------------- | ---------- | -------------------------------------------------------------------- |
| 自动连接（记住 MAC + 固定 PIN） | ✅          | 启动零点击 → `DuckLink connected status=0`                                |
| 认证 / 订阅 / 41 版本       | ✅          | `system.authenticate ok`、`robot.subscribe{profile:phone} accepted`   |
| 主流程 站立→接管→摇杆→停下→卸力    | ✅          | `robot.init/enable/move/stop/relax` 全部 ok；摇杆时请求 +0.05 m/s、实际条跟随，松手归零 |
| 声音 / 音量               | ✅          | `robot.volume` 60/静音/取消静音、`robot.sound ok`                           |
| 详情抽屉（告警详情 + 最近消息）     | ✅          | 电机 52℃、阈值 50/60、倾斜 35°、已卸力、已交还策略                                     |
| 维护面板                  | ✅（等于网页版能力） | 重启舵机、输入源未运行、49.9 Hz、温度 85/52、排障                                      |
| 网络页                   | 部分 ✅       | 已连接/SSID/IP/39%/wlan0/MAC/中控地址正确；`net.scan` 已发出，**结果未取证**            |
| 技能台（坐下/站起/拾取/踢球/前滚翻）  | ⬜ 未测       | —                                                                    |

已知异常（不影响主流程判定，需决策）：主控温度 84–85℃ 持续告警（电机 51–52℃，阈值 50/60）；
页面间跳转（驾驶页 ↔ 网络页）会断开并重连 BLE 约 1 s。

## 2. 需求（decision-complete）

* **R1 技能台验收**：驾驶页策略条逐个点 `坐下/站起`、`拾取`、`左脚踢`、`右脚踢`、`前滚翻`。
  每项判据：`robot.do` 返回 ok；页面策略条回到「行走」；机器人无异常（不摔倒、不撞物）。
  前置：先 `站立` 且倾角 ≤10°，再 `接管`。危险项（前滚翻/踢球）在垫子上、留 1 m 净空。
* **R2 网络页全流程**：扫描 → 列表（SSID/信号/加密标记）→ 只读校验（不点「连接」「忘记」「固定 IP」）。
  判据：`net.scan` 返回的 AP 数量与页面列表一致；扫描结束后按钮恢复、无「扫描中」残留。
  写操作（连接/固定 IP/忘记）另立任务，需用户明确同意后才在真机执行，避免把机器人踢出当前热点。
* **R3 服务控制 UI**：**本期不做**。`system.serviceAction` 的 btd/configd 白名单与单测已就绪，UI 留到验收文档
  的 deferred 清单，避免为演示功能扩大改动面。
* **R4 正式版恢复**：`assets/ble-connect.html` 关掉 `AUTO_CONNECT`、删掉 `TEST_PIN`，改为「有已存地址则预填、
  用户点连接」；PIN 仍由连接页输入。改完重跑桥接自测 + 重装 APK 复验一次连接。
* **R5 稳定性**：30 min 连续 1 Hz 订阅 + 摇杆 10 Hz 遥测；过程中做一次「关手机蓝牙 5 s 再开」。
  判据：进程不崩、无 ANR、自动重连成功、断链期间 `robotd` 在 250 ms 内收到零速（`journalctl -u robotd` 看 move 归零）。
* **R6 交付**：`android/app/build.gradle.kts` 增加 release `signingConfig`（keystore 放 `android/keystore.properties`，
  不入库）；`tools/build-apk.sh` 支持 `--release`；版本号取自 `versionName`。
  产出验收文档 `duckphone-ble-acceptance.zh-CN.md`（表格化记录 R1/R2/R5 + 已知问题）。
* **R7 高温排查**：主控 85℃ 单独开条目，不阻塞验收；需要在真机上读 `sensors`/`thermal_zone` 与 robotd 采样是否自洽。

## 3. 涉及文件（改动点）

| 文件                                                           | 改动                                                 |
| ------------------------------------------------------------ | -------------------------------------------------- |
| `duckphone-ble/assets/ble-connect.html`                      | R4：`AUTO_CONNECT=false`；删除 `TEST_PIN`，改为空值 + 必填校验  |
| `duckphone-ble/android/app/build.gradle.kts`                 | R6：`signingConfigs.release` + `buildTypes.release` |
| `duckphone-ble/tools/build-apk.sh`                           | R6：透传 `--release`                                  |
| `duckphone-ble/tools/tests/bridge_test.html`                 | R4 后保持通过（页面参数驱动，不受开关影响）                            |
| `duckphone-ble/README.zh-CN.md`                              | 进度表补 R1/R2/R5 结果与已知问题                              |
| `firmware/docs/design/duckphone-ble-acceptance.zh-CN.md`（新建） | R6 验收记录                                            |

不改：`assets/duckphone/*`（网页版同步副本）、`ble-bridge.js` 的会话逻辑（跳转重连只记录不修）。

## 4. 验证步骤

1. `cd Microduck-kissqy/microduck-hd1910/firmware/duckphone-ble && ./tools/sync-web.sh`（如改了网页副本文档）
2. `cd android && ./gradlew testDebugUnitTest assembleDebug`
3. `cd ../tools/tests && google-chrome --headless=new --disable-gpu --no-sandbox --virtual-time-budget=8000 --dump-dom "file://$PWD/bridge_test.html?bleAddress=AA:BB:CC:DD:EE:FF&blePin=000000&strip=1" | grep -c FAIL` → 0
4. `adb install -r ../../.build/apk/duckphone-ble-debug-*.apk`
5. 真机：`adb logcat -c` 后按 R1/R2 操作，`adb logcat -d -s DuckRpc DuckLink DuckWeb` 核对；截图存 `duckphone-ble/design/` 以外（临时放 `/tmp`）
6. R5：`ssh duck@<实时确认的机器人IP> journalctl -u robotd -f` 观察零速与重连
7. 机器人 IP 每次用 ducknet 只读 `net.status` 或 `ping` 重新确认，不沿用记录值

## 5. 需要用户批准的点

1. 是否按 **R1 → R2 → R4 → R5 → R6** 顺序推进（R3 不做、R7 单列）。
2. R2 的写操作（连接其它 SSID / 固定 IP / 忘记）是否允许在真机执行；若不允许，只做只读核对。
3. 主控 85℃ 是否现在就排查，还是验收后再处理。
4. 正式版恢复（R4）在什么时候切——本轮验收完成后立刻切，还是保留测试简化到全部页面测完。

## 6. 非目标

* iOS/桌面端；云端中继；服务控制 UI；断链零速以外的新安全策略；上游页面同步以外的改动。

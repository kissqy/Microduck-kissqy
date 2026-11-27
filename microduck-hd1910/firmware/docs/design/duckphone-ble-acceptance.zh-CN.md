# duckphone-ble 真机验收记录

> 依据：[duckphone-ble-acceptance-spec.zh-CN.md](./duckphone-ble-acceptance-spec.zh-CN.md)、
> [duckphone-ble-acceptance-tasks.zh-CN.md](./duckphone-ble-acceptance-tasks.zh-CN.md)。
> 设备：手机 NOH-AN00（PQY0221203054372，HarmonyOS）、机器人 duck-dillon（R17 固件，API 41）。
> 日期：2026-11-26；2026-11-27 补测 UI 适配与断链自愈。机器人 IP 以 `net.status` / `ops/scripts/robot-ip.sh` 实时确认。

## 1. 结果总表

| 项 | 结论 | 证据 |
| --- | --- | --- |
| 自动连接（测试期简化） | ✅ | `DuckLink connecting/connected status=0`，零点击 |
| 认证 + phone 订阅 + API 41 | ✅ | `robot.subscribe ok {accepted:true}`，`api=41 mtu=517` |
| 站立 | ✅ | `robot.init ok`，提示「已回 HOME，请扶稳」，倾角 18.4°→5.2°→1.4° |
| 接管 | ✅ | `robot.enable ok {"accepted":true,"reason":"enabled — driving"}` |
| 摇杆前进 + 松手即停 | ✅ | 拖动中 请求 +0.05 m/s、实际条跟随；松手后双零 |
| 停下 | ✅ | `robot.stop ok` |
| 卸力（长按 1.5 s） | ✅ | `robot.relax ok`，提示「已卸力 · 机器人会瘫倒」 |
| 倾角/关节未就绪时的接管拦截 | ✅ | 拒绝并给出原因（未回 HOME / 未直立），属预期 |
| 声音（7 音效 + 动态开关） | ✅ | `robot.sound ok` |
| 音量 / 静音 | ✅ | 60% / `muted:true,percent:0` / 取消静音 60% |
| 详情抽屉 | ✅ | 电机 52℃、阈值 50 预警·60 危险、最近消息 3 条 |
| 维护面板 | ✅ | 重启舵机、输入源未运行、49.9–50.1 Hz、温度 85/52、排障 |
| 网络页状态 | ✅ | SSID、IP、信号、wlan0 MAC、网页中控地址 |
| 网络页扫描 | ✅ | 4 个 AP 与 `net.scan` 返回一致；按钮从「扫描中」恢复 |
| 网络页刷新 | ✅ | 数值刷新（信号 39%→100%），IP/MAC 不变 |
| 技能：坐下/站起 | ✅ | 两次 `robot.do ok`，状态 坐着 → 行走，倾角 1.4°→3.1° |
| 技能：地面拾取 | ✅ | `robot.do ok`，动作结束回「行走」 |
| 技能：左脚踢 | ✅ | `robot.do ok` |
| 技能：右脚踢 | ⛔ 未配置 | 展开列表显示「未配置 · 缺少 policy.onnx」（机器人侧缺模型，非 App 缺陷） |
| 技能：前滚翻 | ⚠️ 已触发但结果待查 | 09:48:34 `robot.do ok`；翻滚中倾角 105°，随后 BLE 反复断开、机器人停在倾角约 58°（`gravity_z≈-0.52`），09:50:56 出现 `Feetech Sync Read timeout; missing IDs [10, 32]`。需人工摆正后复测 |
| 断链零速 | ✅ | 行进中强杀 App：`intents went stale … deadman_ms=500`，速度被清零 |
| 断链自动重连 | ✅ | 强杀后重启 App 8 s 内 `connected → ready → subscribe accepted` |
| 正式版连接流程 | ✅ | `AUTO_CONNECT` 关闭、`TEST_PIN` 删除；连接页预选 duck-dillon、PIN 占位 `******`，点「连接」进入驾驶页 |
| release 签名 | ✅ | `apksigner verify`：`CN=microduck, O=microduck, C=CN`，SHA-256 `8a464107…c04fdf` |
| 30 min 稳定性 | ✅ | 2026-11-27 10:22–10:52 完成：断链/超时/ANR 全 0，PSS 184→173 MB（见 §3） |
| UI 适配 | ✅ | 2026-11-27 11:49 APK 真机复验：离线浮层改蓝牙文案并显示设备/上次连接/断开原因；状态抽屉两列各 159 px；维护页排障行与 `ble-help.html` 正常。无头 Chrome 360/320 px 审计：状态 / 声音 / 维护 / 连接 / 网络页均无横向溢出（长地址注入下补丁前 231+132 px 溢出、补丁后 159/159 或单列 273 px） |
| 应用图标 | ✅ | 用户提供的机器人插画 + 品牌黄底；前景 432×432 位图（主体 62% 居中），华为桌面实测白边完整、无裁切 |
| 页面切换 | ✅ | 2026-11-27 12:13 真机：驾驶页 ↔ 网络页 `ready 复用已有连接` 同毫秒，认证 60–250 ms，全程无 `down`；新页面先显示 `sessionStorage` 快照，电量/倾角/网络立即有值 |
| 驾驶页稳定性 | ✅ | 2026-11-27 12:37 真机停留 12 s，`页面没有完成握手` 计数 0，无整页重载/闪烁 |
| 告警详情布局 | ✅ | 360/320 px 均为单列，消息列表全宽可读；`ble-page.css` 的两栏规则已限定 `min-width:761px` |
| 排障页 | ✅ | 「未连接」浮层点「排障」打开 App 内蓝牙版 `ble-help.html`（不再进网页版 Wi-Fi 排障）；内容已按蓝牙优先重写 |

## 2. 已知问题

1. **主控 85℃ 是真实读数**：机器人 `/sys/class/thermal/thermal_zone0 soc-thermal = 85000`（=85.0℃），
   `thermal_zone1 gpu-thermal = 81666`。robotd 的 `cpu_temp_c` 与之一致，采样无误。
   属 50 Hz 策略推理的持续负载，需要散热（风扇/降频/降低推理频率），不是软件读数 bug。
   电机侧 51–65℃ 随站立/走动上升，静止卸力后可回落。
2. **页面跳转不再断开重连（2026-11-27 已修）**：以前驾驶页 `pagehide` 会 `DuckNative.disconnect()`，
   下一个页面再完整连一遍。现在 App 内导航保留 GATT（`BleClient.connect` 同地址直接复用），
   并用 `sessionStorage` 存一份 30 秒内的状态快照，新页面先渲染快照再被实时数据覆盖。
   实测驾驶页 ↔ 网络页：`ready 复用已有连接` 同毫秒返回，认证约 60–250 ms，无 `down`。
3. **右脚踢缺模型**：`robot.policies` 里 `kick_right` 槽位无 `policy.onnx`，页面正确显示「未配置」。
4. **电池读数随负载波动**：7.8 V/69% → 7.4 V/31% → 7.57 V/47%，站立时压降明显；属 2S 电池特性，电量百分比按电压换算。
5. **前滚翻后需要人工恢复（2026-11-27）**：翻滚触发了但机器人停在约 58° 的倾斜姿态，随后 BLE 反复断开（`DuckLink down 已断开 → connecting`），
   09:50:56 出现 `Feetech Sync Read timeout; missing IDs [10, 32]`。机器人在线（Wi-Fi 可 SSH、`robotd`/`btd` active），
   漂移期间页面按设计进入「未连接」浮层。需确认不是舵机卡死/线束被压在身下，再摆正复测。
6. **假连接已加监护，浮层已能自愈（2026-11-27）**：对端 `btd` 重启后 GATT 不断但 RPC 全超时。
   桥接现做三件事：`robot.health` 连续 5 次超时即主动断开重拨；替身 socket 的 `open` 改异步补发
   （页面在 `new WebSocket()` 之后才挂监听）；重连成功 4 s 页面仍未 `hello` 则整页重载兜底。
   真机 `sudo systemctl restart btd` 复测两次：约 25 s 自动回到驾驶页，无残留浮层。
7. **页面网格横向溢出（已修，2026-11-27）**：网页版状态抽屉是 `grid-template-columns:1fr 1fr`，
   轨道最小尺寸为 min-content，`appassets.androidplatform.net`、`policy=held` 这类长串把左列撑到
   231 px、右列压到 132 px 并伸出屏幕。App 侧以 `ble-page.css` 改为 `repeat(2,minmax(0,1fr))` +
   `min-width:0` + `overflow-wrap:anywhere`，实测 159/159 px、无横向滚动；≤340 px 退回单列。
   页面副本不改（`tools/sync-web.sh` 会覆盖），BLE 专属样式只放 App 资产。
8. **`robotd.toml` 曾被写坏（2026-11-27 11:39）**：机器人上 `/etc/robot/feetech-ft5/robotd.toml`
   整篇变成 `0xFF`，`robotd` 启动报 `stream did not contain valid UTF-8`、重启计数 176。
   已用同目录 `robotd.toml.bak-crouch-20261127-112807` 恢复，损坏文件留在
   `robotd.toml.corrupt-20261127-1139`；恢复后 `robotd active`、50 Hz 首个周期正常。
   疑与 11:28 的一次 crouch 配置编辑有关，该编辑是否还需重做待确认。
9. **告警详情被强行拉成两列（已修，2026-11-27）**：`ble-page.css` 里的 `.alert-layout`
   两栏规则没有带断点，把网页版 `max-width:760` 的单列覆盖掉了，手机上右栏「最近消息」
   被挤成一条（`指…`/`主…`）。现在两栏只用于 `min-width:761px`，360/320 px 恢复单列。
   同轮把设置抽屉底部按钮行也改成 ≤460 px 换行，避免说明被挤成 4 px。
10. **驾驶页每 4 秒整页重载（已修，2026-11-27）**：切页快照分支会在认证完成前先 `open`，
   页面已经 `hello`；认证完成后代码仍把 `pageBound` 清零等第二次 `open`，但那次 open
   不会再发生，4 s 兜底就误判并 `location.reload()`，表现为驾驶页不停闪。现在只有
   socket 仍关闭时才重置并等待 open；真机停留 12 s 重载计数 0。

## 3. 30 min 稳定性

- **2026-11-27 10:22:23–10:52:27 完成**（APK `duckphone-ble-debug-20261127-1015.apk`）：
  - 断链 0 次、RPC 超时 0 次、`robot.* err` 0 次、ANR/崩溃 0 次
  - 内存 PSS 184 → 173 MB（Native 无增长趋势），页面全程停在驾驶页
  - 机器人静止（策略「待命」），倾角 1.4° 稳定；电机 72→74℃、主控 76→82℃、电量 50%→30%
  - 每 1 Hz `robot.health`、1 Hz `pad.status`、5 s `net.status`、周期 `robot.policies`；请求编号连续（`#3270` @ 10:45）
- **覆盖范围说明**：本轮是链路长跑，10 Hz 摇杆帧未在其中持续发送（死区内按住摇杆未能产生帧）；
  10 Hz 通路由主流程 B3 与 D2 死手测试覆盖，若需长跑需另做主动版本。
- **上一轮（2026-11-26 21:48）**：跑 5 min 后按用户要求暂停，未发现异常。

## 4. 交付物

| 产物 | 路径 |
| --- | --- |
| 调试 APK | `microduck-hd1910/.build/apk/duckphone-ble-debug-20261126-2147.apk` |
| 发布 APK（已签名） | `microduck-hd1910/.build/apk/duckphone-ble-release-20261126-2141.apk` |
| 签名材料（不入库） | `duckphone-ble/android/keystore.properties`、`android/keystore/duckphone-release.jks` |
| 构建脚本 | `duckphone-ble/tools/build_apk.sh`（`--release` / `--check`） |

> 发布包与调试包签名不同，换装前先 `adb uninstall com.microduck.phone`，否则 `INSTALL_FAILED_UPDATE_INCOMPATIBLE`。

## 5. Deferred

- 前滚翻补测（冷却 + 净空确认后）。
- 服务控制 UI（`system.serviceAction` 后端已就绪，页面未做）。
- 主控散热措施（风扇/降频/推理频率）与电机预警阈值是否上调。

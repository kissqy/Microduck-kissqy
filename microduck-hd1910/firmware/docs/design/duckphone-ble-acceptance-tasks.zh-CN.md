# duckphone-ble 真机验收 Tasks

> 配套 spec：[duckphone-ble-acceptance-spec.zh-CN.md](./duckphone-ble-acceptance-spec.zh-CN.md)。
> 状态标记：✅ 已通过（附证据）｜🔧 待执行｜⛔ 阻塞（原因）。
> 每次执行前用实时查询确认机器人 IP（ducknet 只读 `net.status` 或 `ping`）。

## A. 基础链路（已完成）

| # | 任务 | 状态 | 证据 |
| --- | --- | --- | --- |
| A1 | 自动连接 + 固定 PIN | ✅ | `DuckLink connected status=0`，零点击 |
| A2 | 认证 + `robot.subscribe{profile:phone}` | ✅ | `system.authenticate ok`、`accepted` |
| A3 | API 41 版本校验 | ✅ | 单字节 0x29 → api=41 |
| A4 | 1 Hz 健康/状态帧 | ✅ | `robot.health/pad.status/net.status` 每分钟全 ok |

## B. 主流程（已完成）

| # | 任务 | 状态 | 证据 |
| --- | --- | --- | --- |
| B1 | 站立 `robot.init` | ✅ | `accepted:true`，提示「已回 HOME，请扶稳」，倾角 18.4°→5.2° |
| B2 | 接管 `robot.enable` | ✅ | `{"accepted":true,"reason":"enabled — driving"}`；策略条转「行走」 |
| B3 | 摇杆小幅前进 | ✅ | 请求 +0.05 m/s，实际条跟随；松手即停（死手生效） |
| B4 | 停下 `robot.stop` | ✅ | `accepted:true` |
| B5 | 卸力 `robot.relax`（长按 1.5 s） | ✅ | `accepted:true`，提示「已卸力 · 机器人会瘫倒」 |
| B6 | 倾角 >10° 时的接管拦截 | ✅ | 返回「不能进入保持：尚未完成回 HOME…」，属预期 |

## C. 页面（进行中）

| # | 任务 | 状态 | 判据 |
| --- | --- | --- | --- |
| C1 | 声音面板 7 个音效 + 音量 + 静音 | ✅ | `robot.sound`/`robot.volume` 全部 ok，UI 60% 一致 |
| C2 | 详情抽屉（告警详情 + 最近消息） | ✅ | 电机 52℃/阈值 50·60/建议、最近 3 条事件 |
| C3 | 维护面板 | ✅ | 重启舵机/输入源未运行/49.9 Hz/温度/排障 |
| C4 | 网络页加载与状态 | ✅ | SSID、192.168.43.203、39%、wlan0 MAC、中控地址 |
| C5 | 网络页扫描结果 | ✅ | 4 个 AP 与 `net.scan` 返回一致；按钮从「扫描中（约 5–10 秒）」恢复 |
| C6 | 网络页只读核对（刷新） | ✅ | 刷新后信号 39%→100%，IP/MAC 不变，无闪断 |
| C7 | 技能台：坐下/站起 | ✅ | 两次 `robot.do` ok，状态 坐着→行走 |
| C8 | 技能台：拾取 | ✅ | `robot.do` ok，回「行走」 |
| C9 | 技能台：左脚踢/右脚踢 | ✅/⛔ | 左脚踢 ok；右脚踢显示「未配置·缺少 policy.onnx」（机器人缺模型） |
| C10 | 技能台：前滚翻 | ⚠️ | 09:48:34 `robot.do ok`，但滚完停在 58°、BLE 反复断、舵机总线 `missing IDs [10,32]`；需人工摆正后复测 |

## D. 稳定性与交付

| # | 任务 | 状态 |
| --- | --- | --- |
| D1 | 30 min 连续订阅 + 遥测，无崩溃/ANR | ✅ 10:22:23–10:52:27：断链 0、超时 0、RPC 失败 0、ANR/崩溃 0；PSS 184→173 MB；倾角 1.4° 稳定；电机 72→74℃、主控 76→82℃。注：1 Hz 订阅，10 Hz 摇杆帧未在本轮长跑中覆盖 |
| D2 | 关蓝牙 5 s 再开：自动重连；断链期间零速 | ✅ `deadman_ms=500` 清零；强杀后 8 s 内重连 |
| D3 | 正式版恢复：关 `AUTO_CONNECT`、删 `TEST_PIN`、重测连接 | ✅ 手动点「连接」进入驾驶页 |
| D4 | release 签名 + `build-apk.sh --release` | ✅ `apksigner verify` 通过 |
| D5 | 验收文档 `duckphone-ble-acceptance.zh-CN.md` | ✅ 已生成 |
| D6 | 主控 85℃ 排查（单列，不阻塞） | ✅ 读数自洽：soc-thermal 85000、gpu-thermal 81666 |

## 执行顺序（已批准，执行中）

C5 ✅ → C6 ✅ → C7 ✅ → C8 ✅ → C9 ✅/⛔ → C10 ⚠️ → D1 ✅ → D2 ✅ → D3 ✅ → D4 ✅ → D5 ✅ → D6 ✅

## 每步验证命令

```bash
export ADB=/home/dillon/Android/Sdk/platform-tools/adb
$ADB logcat -c
# … 操作手机 …
$ADB logcat -d -s DuckRpc DuckLink DuckWeb | tail -40
$ADB exec-out screencap -p > /tmp/duck_step.png
ping -c2 <实时确认的机器人IP>
```

判定标准：RPC 返回 `ok` 且 payload 与 UI 一致；无 `DuckRpc ... err`；页面无残留加载态。

# 动态发声 · 需求方案（v1 已实现）

> Status: implemented · 2026-11-26 · v1 落在 duckphone 桥 + 手机面板 + 控制台 LB
> 目标机器人：Microduck（R17 / robotd 0.15.1）
> 本文定义“什么时候、因为什么、发什么声音”；v1 的实际落地见 §9。
> UI 设计见手机 App 声音抽屉（底部「动态声音」卡片）与控制台模拟手柄的 LB 键。

---

## 0. 一句话目标

让鸭子**自己根据机器人的状态和正在发生的事发声**，而不是只有手机声音面板里点一下才叫。

---

## 1. 现状与边界

### 1.1 现在已有哪些自动声音

| 场景 | 声音 | 实现位置 |
| --- | --- | --- |
| 开机 | greet | robotd |
| 行走模式切换 | chirp | robotd（`main.rs:2738`） |
| 被抚摸（ToF） | coo | robotd（需要 `audio.pet_detect` 和模型） |
| 关机 / 电量耗尽 | peck | robotd（关机前阻塞播放） |
| theremin / 合唱 | 实时合成 / 整曲 | robotd |

### 1.2 声音资源约束

- 只有 7 个 tag：`chirp / greet / inquire / coo / alarm / peck / wheee`，每个 tag 有多个随机变体。
- PCM **单客户端**，新声音会打断正在播的旧声音；不能叠音。
- `wheee` 是长叫，适合“按住”，不适合做事件提示。
- 音量是系统级（`amixer`），动态提示与手动声音共用同一个音量。
- 音色在安装时按种子渲染，运行期不能换。

### 1.3 本方案不重复已有功能

开机 greet、关机 peck、抚摸 coo 继续由 robotd 负责；动态发声层只补
**手机/桥接层能看到、而固件目前没有触发**的那些场景。若某场景 robotd 已经在响，
需求表里会标“已有”，不再叠加。

---

## 2. 声音词汇表（v1 不新增音频文件）

| tag | 听感 | 建议用途 |
| --- | --- | --- |
| `alarm` | 短促警戒 | 倒地、严重倾斜、危险电量、电机过温 |
| `inquire` | 尾音上扬 | 需要人注意、命令被拒绝、低电量提醒、长期没人理 |
| `chirp` | 短叫 | 确认类：接管、交还、动作开始/结束、连接成功 |
| `greet` | 打招呼 | 开机、手机接管、跌倒后重新站起 |
| `coo` | 慢、气声 | 休闲、空闲、安抚、告警解除 |
| `peck` | 低频 + 咔哒 | 关机、小事件（如停止/重启舵机） |
| `wheee` | 长叫 | 只保留给手动“按住”和现有手柄逻辑 |

> 如果评审后觉得“开心 / 委屈 / 困了”这类情绪需要独立音色，那就属于
> **v2 新增声音库**：要重新渲染 bank，工作量和风险都更大，v1 不建议做。

---

## 3. 场景清单（建议默认值，可直接改）

优先级：**P0 安全 > 手动点播 > P1 动作反馈 > P2 休闲/氛围**。
同一时刻只播一个；P0 可以打断低优先级，手动点播可以打断 P1/P2。

### 3.1 生命周期

| ID | 场景 | 触发条件 | 声音 | 优先级 | 默认 | 冷却 / 重复 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| L1 | 开机 | robotd 启动 | greet | P1 | 已有 | 一次 | 不重复 |
| L2 | 手机接管驾驶 | 会话从只读变 driver，或首个 hello | greet | P1 | 开 | 60 s | 第二台设备只读不响 |
| L3 | 驾驶会话结束 | driver 断开 / 超时 | coo | P2 | 开 | 30 s | 可选，避免频繁掉线时叫 |
| L4 | 关机 | 正常关机 / 电量耗尽 | peck | P1 | 已有 | 一次 | robotd 已在做 |
| L5 | robotd 失联 / 恢复 | bridge 链路 down → up | inquire / greet | P1 | 开 | 60 s | 失联超过 5 s 才提示 |

### 3.2 动作与状态切换

| ID | 场景 | 触发条件 | 声音 | 优先级 | 默认 | 冷却 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | 站立 / 回 HOME 完成 | `policy: homing → held` | chirp | P1 | 开 | 3 s | 与“开始站立”区分：开始不响，完成响 |
| A2 | 接管行走策略 | `robot.enable on:true` 被接受 | greet | P1 | 开 | 5 s | 用户明确获得控制权 |
| A3 | 交还策略 | `robot.enable on:false` 被接受 | coo | P1 | 开 | 5 s | 回到待命 |
| A4 | 执行技能开始 | 策略条点 `sit_toggle / ground_pick / kick_* / roulade` | chirp | P1 | 开 | 2 s | 动作开始确认 |
| A5 | 技能结束回到 walk | `policy` 从技能名回到 `walk` | coo | P2 | 开 | 2 s | 只对一次性技能；坐下/站起是开关，见 A6 |
| A6 | 坐下 / 站起切换 | `sit_toggle` 执行后状态变化 | chirp | P1 | 开 | 2 s | 与 A4/A5 去重，避免三连响 |
| A7 | 开始 / 停止行走 | twist 从 0 → 非 0 / 非 0 → 0 | chirp（很短） | P2 | **关** | 10 s | 可能很吵，建议默认关 |
| A8 | 命令被拒绝 | enable/policyDo/relax 等返回 `accepted:false` | inquire | P1 | 开 | 3 s | 给用户“为什么没动”的听觉反馈 |
| A9 | 标定模式 / 不可动 | 连接时 `ro=true` | inquire | P1 | 开 | 一次 | 与页面提示互补 |

### 3.3 告警（建议默认全开）

| ID | 场景 | 触发条件 | 声音 | 优先级 | 冷却 / 重复 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| E1 | 倒地 | `fallen=true` 进入 | alarm | P0 | 5 s，最多 6 次，然后 60 s | 不要无限叫 |
| E2 | 倾斜预警 | 倾角 ≥30° 进入；≥60° 按 E1 | alarm | P0 | 10 s | 机体正在倒比电量重要 |
| E3 | 电量低 | <25% 进入 | inquire | P1 | 10 min | 50%→25% 之间不响 |
| E4 | 电量危险 | <15% 进入 | alarm | P0 | 60 s | 与页面红色告警一致 |
| E5 | 电机温度高 | 最热 ≥60°C 进入 | alarm | P0 | 60 s | ≥50°C 可只发 inquire（可选） |
| E6 | 主控温度高 | ≥85°C 进入 | alarm | P1 | 5 min | 70–85°C 不响，避免打扰 |
| E7 | 控制环掉频 | <45 Hz 持续 3 s | alarm | P1 | 60 s | 45–48 Hz 不响 |
| E8 | 总线错误 | `consecutive_errors` 增加 / 启动失败 | alarm | P0 | 30 s | 需要定义阈值 |
| E9 | 告警解除 | 上述告警从有到无，且持续 >3 s | coo | P2 | 10 s | 安抚式收尾，可选 |
| E10 | 跌倒后重新站起 | `fallen: true → false`，且随后 homed | greet | P1 | 10 s | 与 A1 去重 |

### 3.4 休闲 / 空闲

| ID | 场景 | 触发条件 | 声音 | 优先级 | 默认 | 冷却 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| I1 | 一段时间没人操作 | 无摇杆/头部/命令输入 ≥30 s，且未 limp/fallen | coo | P2 | 开 | 一次 | “休闲”核心场景 |
| I2 | 长时间空闲 | 之后每 300 s | inquire | P2 | 开 | 每 5 min，最多 12 次/小时 | 像在找人 |
| I3 | 随机小叫 | 空闲状态，每 10–20 min 随机 | chirp | P2 | **关** | 每小时最多 3 次 | 更像宠物，但可能吵 |
| I4 | 空闲时抬头看人 | 与 I1/I2 同时，头部轻微抬起/转头 | 声音 + 头部动作 | P2 | 关 | 与声音同一次 | 属于“动态”，可选 |

空闲定义 v1 建议：
- 没有 `drive` / `head` / `cmd` 消息；
- `policy` 为 `walk` 或 `held`，不是 `limp/fallen/homing`；
- 机器人静止（twist 接近 0）；
- 默认只在一个驾驶会话在线时启用 I1/I2；没有手机连接时是否也叫，见 §7 问题 1。

### 3.5 不建议做 / 放到以后

| 场景 | 原因 |
| --- | --- |
| 充电开始/结束 | 目前没有可靠的充电检测 |
| 被拿起 | IMU 能看出运动，但和“被搬动/推走”难区分 |
| 语音说话 / TTS | 需要新音频链路和存储，完全不同的量级 |
| 按时间段问候（早上好/晚安） | 板子无 RTC，时间会跳 |
| 按情绪换音色 | 需要重渲染声音库 |
| 音乐/环境音 | 会和现有 chorale/Theremin 抢 PCM |

---

## 4. 优先级、去重与节奏（核心规则）

1. **一次只播一个声音**：所有动态声音走同一个播放队列；新声音按优先级决定是否打断。
2. **边沿触发**：告警/状态只在“进入”时响，不按 20 Hz 状态帧重复触发。
3. **滞回**：例如电量 25% 响过，要回到 28% 以上才重新武装；倾斜同理。
4. **全局最小间隔**：P1/P2 之间至少 1.5 s；P0 不受此限，但同一 P0 告警有自己的重复节奏。
5. **重复告警上限**：连续告警最多重复 N 次（默认 6），之后降为 60 s 一次，避免整晚叫。
6. **手动优先**：手机声音面板点播时，抑制 P1/P2 1.5 s；P0 仍可打断手动。
7. **静音/静默**：系统音量为 0 时所有动态声音都不发；`audio.enabled=false` 或 bank 为空时不发。
8. **不抢乐器**：`theremin` / `chorale` 活跃时跳过一次性动态声音（固件本身也会丢，但桥接层不该白发）。
9. **状态未知不触发**：健康数据缺失时不把 `null` 当 0，不因此报警。
10. **可观测**：每次动态播放写一条 duckphone 日志：`trigger=E1 tag=alarm reason=fallen`，方便排查“为什么叫了”。

---

## 5. 实现位置（建议）

### 方案 A：duckphone 桥接层（推荐 v1）

在 `server.py` 里加一个 `AudioDirector`：

- 订阅现有 20 Hz `robot.state` 和 1 Hz `robot.health`；
- 接收桥接层事件（会话接管、命令被拒、技能执行、链路断开）；
- 规则引擎按 §3 产生 `(tag, trigger_id, priority)`；
- 一个独立 worker 线程顺序调用 `robot.sound`，**不阻塞控制/状态线程**；
- 手动点播也通知 director“刚手动播过”，用于抑制；
- 配置放 `/etc/duckphone/audio.json`，改完 `systemctl restart duckphone` 生效。

优点：不改固件、可以随 duckphone 一起部署/回滚、能用到会话和手机侧事件。
缺点：duckphone 服务必须运行；robotd 自身已有的开机/关机/抚摸仍由固件负责。

### 方案 B：robotd 固件内实现

优点：不依赖 duckphone，最可靠，延迟最低。
缺点：要改固件、出新版本、走 release；和现有触发重复；调试成本高。

### 建议

**v1 用方案 A**；保留固件已有的 L1/L4/抚摸。若以后要求“不装 duckphone 也要有动态声音”，再把规则下沉到 robotd。

---

## 6. 配置草案（供评审，不一定全做）

`/etc/duckphone/audio.json`：

```json
{
  "enabled": true,
  "min_gap_s": 1.5,
  "quiet_hours": ["22:00", "08:00"],
  "manual_suppress_s": 1.5,
  "idle": {
    "enabled": true,
    "after_s": 300,
    "repeat_s": 900,
    "max_per_hour": 4,
    "require_client": true
  },
  "triggers": {
    "connect": true,
    "disconnect": true,
    "stand_done": true,
    "takeover": true,
    "handback": true,
    "skill_start": true,
    "skill_end": true,
    "refusal": true,
    "battery_low": true,
    "battery_critical": true,
    "motor_hot": true,
    "cpu_hot": true,
    "loop_slow": true,
    "bus_error": true,
    "fallen": true,
    "tilt": true,
    "recovered": true,
    "random_chirp": false
  }
}
```

`quiet_hours` 需要系统时间可信；板子没有 RTC，**v1 建议先不做**，或者只按“开机时长/最近手机时间”近似。

---

## 7. 需要你确认的问题

1. **没有手机连接时，动态声音要不要工作？**
   - 建议：安全告警（P0）要；休闲/随机叫声不要（家里没人时乱叫会烦）。
2. **空闲 “一段时间” 是多久？** 5 min / 10 min / 30 min？之后多久再叫一次？
3. **告警重复节奏**：倒地后每 5 s 叫一次、最多 6 次，是否可以？还是只叫一声？
4. **动作反馈**：技能开始/结束、坐下/站起、接管/交还，哪些需要声音？哪些太吵？
5. **命令被拒绝**要不要 `inquire`？（例如接管被 5° 门限拒绝时）
6. **静音是否连 P0 也静音？** 建议：系统音量 0 = 全部不响。
7. **休闲/氛围声音默认开还是关？** 随机小叫（I3）建议默认关。
8. **是否需要“声音 + 头部动作”组合**（空闲时抬头、告警时摇头）？还是 v1 只做声音？
9. **配置方式**：先用 `/etc/duckphone/audio.json`，以后要不要放进手机设置页？
10. **v1 是否只使用现有 7 个声音**，不新增音频文件？

---

## 8. 验收标准（需求确认后再细化）

- §3 表中每个“默认开”的场景都能在真机复现，且不会连续刷屏。
- P0 能打断 P1/P2；手动点播与动态声音不叠加。
- 系统静音、`audio.enabled=false`、标定模式下都不发声。
- 空闲只按设定节奏触发，超过每小时上限后不再叫。
- 掉线/重启后规则状态不产生重复告警（例如开机不要立刻补叫三次倒地）。
- duckphone 日志能查到最后一次动态声音的 trigger、tag、原因。
- 单测覆盖：规则边沿、滞回、优先级、冷却、静音、无数据。

---

## 9. v1 实现落地（2026-11-26）

### 9.1 代码位置

| 文件 | 作用 |
| --- | --- |
| `firmware/duckphone/audio_director.py` | 规则引擎：状态边沿、告警节奏、空闲、优先级、冷却 |
| `firmware/duckphone/server.py` | 总开关 `dynamic_sound`、`dyn` / `err` 状态字段、HTTP 与 WebSocket 接口 |
| `firmware/duckphone/static/` | 声音抽屉底部「动态声音」卡片（开关 + 说明） |
| `firmware/console/static/` | 模拟手柄 LB 键（读写同一个开关） |
| `firmware/console/console.py` | CSP 放行 `http://*:8001` |

### 9.2 开关与接口

- 桥接层全局一份开关，默认关闭；手机成为 driver（首次 hello 或 takeover）时自动开启。
  用户可在手机上关闭，本次会话保持关闭；重新接管会再次开启。
- 手机端：WebSocket `{"t":"cmd","name":"dynamicSound","on":true|false}`，回执带 `enabled`。
- 调试台：`GET /api/dynamic-sound` → `{"enabled":bool}`；
  `POST /api/dynamic-sound`，body 为 `{"enabled":bool}` 或 `{"toggle":true}`。
  两个接口都带 `Access-Control-Allow-Origin: *`，控制台才能跨端口读写。
- 控制台 LB 在官方映射里未绑定，选它便于以后映射到实体手柄；按钮每 5 s 轮询桥，
  桥不在线时禁用，且不受“手柄整体不可用”影响（动态声音与运动服务无关）。
- 状态帧新增 `dyn`（开关）与 `err`（`health.bus.consecutive_errors`），页面无需额外轮询。

### 9.3 v1 实际启用的规则

- 生命周期：L2 接管 greet、L3 会话结束 coo、A2/A3 enable greet/coo。
- 动作：A4 技能开始 chirp、A5 技能结束 coo、A8 命令被拒 inquire。
- 告警：E1 倒地 5 s × 6 → 60 s、E2 倾斜 ≥30° 每 10 s、E3 电量 <25%、
  E4 <15% 每 60 s、E5 电机 ≥60 °C / ≥50 °C、E6 CPU ≥85 °C、
  E7 掉频 <45 Hz 持续 3 s、E8 总线连续错误 ≥3、E9 告警解除 coo。
- 空闲：I1 30 s coo、I2 每 300 s inquire，每小时最多 12 次；
  只在有 driver、`walk` / `held`、未 limp / fallen、且 tilt < 30° 时生效。
- 手动点播抑制 P1/P2 1.5 s；P0 不受抑制。
- 真机抖动保护：技能运行期间（`roulade` / `sitstand` / `ground_pick` 等）不触发 E1/E2，
  避免翻滚被当成摔倒；`fall` 需连续 2 s 正常才算解除，短暂的 false 不会重置 5 s 节奏；
  `tilt` 的 10 s 冷却不会被瞬间回到 30° 以下重置。
- 调整节奏：设置页或 `POST /api/audio-config` 直接改 `idle.after_s` / `idle.repeat_s`；
  生产默认仍是 30 s / 300 s。

### 9.4 v1 不做（下一版）

- 手机设置页与 `/etc/duckphone/audio.json`：时间固定 30 s / 300 s。
- 声音 + 头部动作组合（I4）。
- 随机小叫（I3）、A6 起坐单独提示、A7 行走起停、A9 标定提示、
  L5 链路恢复、E10 站起问候——规则表保留，v1 未接。
- robotd 固件内的 L1/L4/抚摸声音保持不变，不重复叠加。

---

## 10. v2 设计（已实现，待真机验收）

> 2026-11-26 · 设置页开放“节奏 + 开关”；空闲动作 I1 抬头 / I2 左右看；
> 配置存桥上 `/etc/duckphone/audio.json`。UI 见
> [`duckphone-ui.zh-CN.md`](duckphone-ui.zh-CN.md) §19.3 / §20。
> 实现：`audio_settings.py`（配置）、`head_gesture.py`（动作）、
> `server.py`（WS/HTTP 接口）、`static/`（设置抽屉）；单测 136 项通过。
> **v3 起**空闲动作由 `actions.py` 的动作库与随机池接管，`head_gesture.py` 已删除；
> 本节保留为 v2 的设计记录，当前行为以 §11 为准。

### 10.1 参数分层

**手机设置页（常规）**

- 空闲：`after_s` 30、`repeat_s` 300、`max_per_hour` 12、`gesture` 开。
- 倒地节奏：`repeat_s` 5、`max_repeats` 6、`tail_s` 60。
- 倾斜：`deg` 30、`repeat_s` 10。
- 动作反馈：接管/交还、技能开始/结束、启用/关闭、命令被拒绝（4 组开关，底层 6 个布尔）。
- 告警类别：倒地、倾斜、电量、电机、主控、掉频、总线（7 个开关）。

**配置文件 / 高级（不进手机常规页）**

- `min_gap_s` 1.5、`manual_hold_s` 1.5。
- 电量低/危险 25/15 %、电机温热/高温 50/60 °C、主控 85 °C、
  掉频 <45 Hz 持续 3 s、总线连续错误 3。
- 各触发冷却沿用代码默认，暂不开放。

安全阈值留在文件里，避免在手机页误调。

### 10.2 配置文件

`/etc/duckphone/audio.json`，完整结构：

```json
{
  "version": 2,
  "idle": {"after_s": 30, "repeat_s": 300, "max_per_hour": 12, "gesture": true},
  "fall": {"repeat_s": 5, "max_repeats": 6, "tail_s": 60},
  "tilt": {"deg": 30, "repeat_s": 10},
  "actions": {"takeover": true, "handback": true, "skill_start": true,
              "skill_end": true, "enable": true, "refusal": true},
  "alerts": {"fall": true, "tilt": true, "battery": true, "motor": true,
             "cpu": true, "loop": true, "bus": true},
  "advanced": {"min_gap_s": 1.5, "manual_hold_s": 1.5,
               "battery_low_pct": 25, "battery_critical_pct": 15,
               "motor_warm_c": 50, "motor_hot_c": 60, "cpu_hot_c": 85,
               "loop_min_hz": 45, "loop_low_s": 3, "bus_error_count": 3}
}
```

- 文件缺失/损坏 → 默认值启动 + warning，不阻塞服务。
- 缺键补默认，未知键忽略，类型错误回退默认；数值越界夹紧；`repeat_s ≥ after_s`。
- 临时文件 + `os.replace` 原子写，`duck:duck 0600`；改完热生效，不重启。
- 总开关 `dynamicSound` 仍是会话状态，不写入文件。

### 10.3 接口

- 手机 WS：`audioConfig` 读、`setAudioConfig` 写、`resetAudioConfig` 恢复默认。
  读取允许所有会话；写入要求 driver。
- 调试台 HTTP：`GET/POST /api/audio-config`，与 `/api/dynamic-sound` 一样带 CORS。
- 保存后广播 `{"t":"audioConfig","config":{…}}`，所有设置页和声音抽屉同步。

### 10.4 空闲头部动作

**I1 第一次空闲（配 coo）**

```text
0.0 s  neck 0, pitch -0.30, yaw 0
1.2 s  回中/恢复动作前姿态
```

**I2 之后空闲（配 inquire）**

```text
0.0 s  neck 0, pitch -0.18, yaw +0.30
0.8 s  neck 0, pitch -0.18, yaw -0.30
1.6 s  回中/恢复动作前姿态
```

- 10 Hz 下发，持续刷新，避免 250 ms 头部看门狗归零。
- 只在声音真正被接受后触发；被手动点播/冷却/总开关拦下时不动作。
- 只在有 driver、在线、非只读、非 limp/fallen、倾斜 <30°、policy 为 walk/held 时执行。
- `drive` / `head` / `cmd` 输入、接管、关闭动态声音、会话结束、P0 告警都会取消动作。
- 动作层做成一个 `HeadGesture` worker（v3 起改为 `actions.py` 的 `ActionPlayer`）；
  规则层只传动作名，随机动作库只改动作层。

### 10.5 验收

- 设置保存后立即生效、重启保留；手机和调试台读到同一份。
- 非法/缺失/损坏配置不会让桥启动失败。
- I1 声音+抬头、I2 声音+左右看；关掉 `idle.gesture` 后只剩声音。
- 摇杆/头部输入、接管、P0 告警立刻取消动作；结束回中。
- 单测覆盖：配置合并/校验/原子写、两套动作时序、取消、只读/limp/fall/tilt 不动作。

## 11. v3 动作库与空闲随机（已实现，头/嘴/空闲已真机验收）

> 2026-11-27 · 已实现：头部画圈 3 圈、张嘴、空闲从库里随机、手机底部新增「动作」抽屉。
> 真机（duck-dillon）：抬头/左右看/画圈/张嘴逐个通过；空闲 `circle` 带 `actIdle=true`
> 播放并回中。**原地踏步已移除**：行走策略对短时交替速度不迈步，需要专门的步态训练/技能。
> 代码：`actions.py`（动作库/播放器）、`rpc.py`（mouth/pose）、`server.py`（action/cancelAction、
> `act` 状态、取消路径）、`audio_director.py`（空闲随机）、`audio_settings.py`（version 3）、
> `static/`（动作抽屉与随机池）。单测 150 项通过；浏览器已用假 robotd 跑通播放/停止/空闲徽标。
> UI 见 [`duckphone-ui.zh-CN.md`](duckphone-ui.zh-CN.md) §21。

### 11.1 硬件边界

- `head_yaw` 的机械/标定范围是 **±170°**（`robot_walk.xml` 的 `-2.967…+2.967`，
  标定手册同值），单圈模式不能跨越 ±180°。因此“连续转几周”无法用现有舵机实现；
  本版的“转圈”是**头部画圈**：yaw 与 pitch 相位差让鼻子在空中画圆，不是多圈旋转。
- `robot.mouth` 是独立关节，`open: 0..1`，只在 `homed && !falling && sensors && imu_warm`
  时生效；嘴部不在任何策略里，桥可以直接写。
- 没有“原地踏步”技能，行走策略对短时交替 `vx` 不产生真实步态；本版**不做踏步**，
  等有专门训练的动作/技能后再加。
- `robot.pose` 的训练范围：z −0.025…+0.010 m、roll/pitch ±0.26 rad；超出不报错，
  但策略会看到没训练过的输入，所以桥自己夹紧。

### 11.2 动作库

统一放在桥的 `actions.py`，每个动作声明：声音、时长、头部/嘴部/pose 帧、是否要求
`policy == walk`、是否允许空闲自动播放。

| 名称 | 界面 | 声音 | 动作 | 时长 | 空闲 |
| --- | --- | --- | --- | --- | --- |
| `look_up` | 抬头 | `coo` ×2（0 / 0.7 s） | pitch −0.30，回中 | 1.2 s | 是 |
| `look_around` | 左右看 | `inquire` ×3（0 / 0.6 / 1.2 s） | pitch −0.18，yaw ±0.30 | 1.6 s | 是 |
| `circle` | 画圈 | `greet` ×5（每 0.8 s） | yaw ±1.0，pitch −0.20±0.25，roll ±0.08，3 圈 | 3.9 s | 是 |
| `quack` | 张嘴 | `chirp` ×3（每次张嘴） | `mouth.open` 0 → 0.9 → 0，3 次 | 2.1 s | 是 |

- 画圈的 3 圈是 3 × 1.3 s；`greet` 每 0.8 s 补一声，避免短叫结束后整段静音。
- 张嘴的嘴部帧 0.35 s 张开、0.35 s 闭合；`chirp` 在每次张嘴时补一声。
- 每个动作用 `beats` 声明声音时间表：第一声由手动/空闲入口播放，其余由 `ActionPlayer`
  在动作线程按偏移补发；声音被拒绝或超时只记日志，不打断动作。
- 所有动作结束都回中/闭嘴/步态归零/pose 失活；异常退出也走同一收尾。

### 11.3 踏步（已移除）

试过左右换重心和前后小步两种桥合成方案：速度太小时行走策略直接当静止，
加大到 0.15 m/s 后虽然 `requested/applied` 都有值，但短时正反切换不产生真实迈步，
里程计几乎不动。结论是踏步需要专门训练的策略/技能，桥层拼不出来；本版从动作库、
UI 和空闲随机池中移除，等训练好后再加。

### 11.4 播放器与取消

`ActionPlayer` 单线程、同一时刻只跑一个：

- 头部/嘴部 10 Hz，pose 随帧更新；每帧检查 `allowed`，不满足立即退出。
- 最长时长保护（动作时长 + 0.5 s）；`finally` 统一回中、闭嘴、步态归零、pose 失活。
- 开始/结束时写桥的 `act`/`actIdle`，随 20 Hz state 下发，所有会话可见。
- 取消路径：`drive`/`head` 任意输入、`stop`/`relax`/`enable`/`init`/`policyDo`、
  接管、交还、会话结束、关闭动态声音、P0 告警。
- 头部幅度：`HEAD_ACTION_MAX = 1.2` rad（画圈用 1.0）；手机摇杆仍是 0.8 rad；
  robotd 再按标定限位夹一次。
- 声音：第一声由手动/空闲入口播放（手动 `note_manual`，空闲先确认接受）；
  其余 beat 由 `ActionPlayer` 用 `robot.sound` 通知补发，不等回包，避免阻塞动作循环。
- 声音被拒（无声卡/无音色）时：手动动作仍执行并回报 `sound.ok=false`；
  空闲动作按 v2 规则不动作；后续 beat 失败只记日志。

### 11.5 空闲随机

- 配置增加 `idle.library`（动作名数组），默认
  `["look_up", "look_around", "circle", "quack"]`。
  `idle.gesture` 仍是总开关：关掉后只发声、不动作。
- 每次空闲从 `library` 中随机挑一个，**不连续重复同一个**；若挑中的动作当前不满足
  条件，重新挑一个可用动作；都不可用则只发声。
- 开关、冷却、每小时上限、声音优先级（P2）、手动抑制沿用 v2。

### 11.6 配置 v3

`/etc/duckphone/audio.json` 版本升到 3；v2 文件缺 `idle.library` 时补默认，
未知动作名丢弃，空数组回退默认。其余结构与 v2 相同：

```json
{
  "version": 3,
  "idle": {
    "after_s": 30, "repeat_s": 300, "max_per_hour": 12, "gesture": true,
    "library": ["look_up", "look_around", "circle", "quack"]
  }
}
```

- `setAudioConfig` 的 `patch.idle.library` 支持整组替换；`resetAudioConfig` 恢复默认。
- 动作幅度、画圈半径属于代码常量，不进设置页，避免误调。

### 11.7 接口

- 手机 WS：`action {name}` 播放一个预设，要求 driver；`cancelAction` 停止当前动作。
- `action` 的 ack：`ok`、`name`、`reason`、`sound`（声音是否被接受）。
- `hello` 和 `state` 增加 `act`（动作名或 null）、`actIdle`（是否空闲触发）；
  只读会话能看到但不能播放。
- 条件不满足时返回可读原因，例如“机器人未站立”“策略不在行走”“还有动作在播放”。

### 11.8 验收

- 四个动作逐个真机播放：声音同步、结束回中/闭嘴、没有残留头部偏移。
- 摇杆/头部输入、停止、卸力、接管、P0 告警后 250 ms 内动作停止并回中。
- 张嘴不打架策略；踏步已移除，等专门训练后再验收。
- 空闲随机：不连续重复、空库只发声。
- 只读、未站立、倾斜/倒地/卸力时按钮置灰或返回原因。
- 单测覆盖：动作帧/时长、取消、`act` 状态、随机不重复、配置 v2→v3 迁移、协议权限。

**简体中文** | [English](README.en.md)

# 📱 duckphone · 局域网手机遥控

手机连同一个 Wi-Fi，浏览器打开 `http://<板子IP>:8001/` 就能驾驶。不用装 App，不用蓝牙配对，
不用数据线。竖屏单页：策略条在上、行走/头部切换和摇杆居中、四个动作按钮 2×2 在下。

零外部依赖：板子只要有 `python3` 标准库；页面不需要 CDN、不需要 `pip`、不需要外网。

设计说明（它凭什么这么设计、以及它在哪一层无权决定什么）在
[`docs/design/lan-phone-remote.md`](../docs/design/lan-phone-remote.md)。

## 为什么要它

仓库里已经有两条遥控路径，各自都要先付出一点什么：

| 想做的事 | 用什么 | 代价 |
| --- | --- | --- |
| 在外面、带视频、用 owner 的手机 | 官方 App（`docs/design/mobile-app.md`） | 装 App、登录 |
| 用笔记本上的实体手柄 | `microduck-webpad` + `padd` | 得有个手柄 |
| **用任何一台已经在同一 Wi-Fi 上的手机** | **本目录** | 得在同一 Wi-Fi 上 |

`duckphone` 是一个**普通的 socket 客户端**，和 `padd`、`console` 同一权限等级：不打开任何设备、
不申请 root、不替 `robotd` 做任何决定。

## 能做什么

| 功能 | 说明 |
| --- | --- |
| 驾驶 | 虚拟摇杆，`vx ∈ [-0.25, 0.35]`、`vyaw ∈ [-0.8, 0.8]`，比训练域更保守 |
| 头部控制 | 摇杆顶部切「头部」，同一个摇杆控制左右转头和上下抬头；松手回正，断线也会回正 |
| 声音面板 | 底栏扬声器按钮：7 个内置叫声，按住「长叫」持续 |
| 动态声音 | 接管后默认开启：动作、告警、空闲自动叫；声音抽屉底部可关；调试台 LB 是同一个开关 |
| 动态声音设置 | 空闲节奏与随机动作池、倒地/倾斜节奏、动作反馈、告警类别；保存到 `/etc/duckphone/audio.json`（version 3），热生效 |
| 预设动作 | 底栏「动作」抽屉：抬头、左右看、画圈、张嘴；站立静止时可用，摇杆/头部一有输入就取消 |
| 空闲动作 | 从配置的动作池（默认四个）里随机挑一个，配它自己的声音；不连续重复同一个 |
| 音量 / 静音 | 音量写声卡（`amixer`），有免密 sudo 时用 `alsactl` 持久化 |
| 策略条 | 列出本机装的策略，点一下执行一次；`行走` 是静止态，其余跑完自动回 `walk` |
| 接管 / 交还 | 同一时刻只有一个驾驶者，第二台设备进入只读；`policies` 只读也放行 |
| 卸力 | 长按 1.5 s 一步生效，不弹确认框 |
| 状态页 | 连接、策略、控制环、电源、双温度、输入源 |
| 警告详情 | 倒地/倾斜、温度、电量、控制环丢帧、`padd` 冲突，各带处理建议 |
| 维护页 | 重启舵机、输入源、版本、排障命令 |

## 声音与头部

- 头部模式只在 `policy == walk` 时可用；`held` / `limp` / 倒地时摇杆区会压暗。
- 摇杆头部意图夹在 ±0.8 rad；预设动作最多用 1.2 rad（画圈用 1.0），robotd 仍按策略/关节限位处理。真机约定 `head_pitch` 负值是抬头，
  页面已经把「向上」映射成负值，读数也反过来显示（向上为正）。
- robotd 对头部**没有** deadman，桥补了一个 250 ms 看门狗：页面松手、切后台、断线、
  `/stop`、会话结束都会把头部回正。
- 声音走 `robot.sound`；PCM 是单客户端，新声音会打断上一个。
- `wheee` 的 `hold` 是电平，按住期间前端约 10 Hz 重发，否则约 300 ms 会自然衰减落地。
- 只读会话不能发声、不能调音量；`robotd --commissioning` 时 `robot.sound` 会被拒。
- 动态声音在桥里由 `audio_director.py` 判定（不经过固件）：接管/交还、技能起止、命令被拒、
  倒地/倾斜/低电量/过温/掉频/总线错误、以及空闲（首次 30 s、之后每 300 s）。
  默认关闭，手机接管时自动开启；手机用 WebSocket `dynamicSound`，调试台用
  `GET/POST http://<板子IP>:8001/api/dynamic-sound`，两端共用同一状态。
- 设置页在声音抽屉底部「设置」：空闲（首次/重复/每小时上限/动作开关/随机池）、倒地与倾斜节奏、
  动作反馈、告警类别。保存到 `/etc/duckphone/audio.json`，校验/夹紧/原子写，改完热生效；
  只读会话可以看，输入和保存禁用。手机 WS 用 `audioConfig` / `setAudioConfig` /
  `resetAudioConfig`，调试台用 `GET/POST /api/audio-config`。
- 预设动作在 `actions.py`：抬头 1.2 s、左右看 1.6 s、画圈 3.9 s、张嘴 2.1 s。
  手机 WS：`action {action:"circle"}` / `cancelAction`；状态带 `act`/`actIdle`，
  ack 带 `sound`（没有声卡时动作照做）。任何驾驶/头部/命令输入、接管、停止、卸力、
  关闭动态声音、P0 告警都会取消；结束统一回中、闭嘴、步态归零、pose 失活。
- 声音贯穿整个动作：抬头 `coo` ×2、左右看 `inquire` ×3、画圈 `greet` ×5、
  张嘴 `chirp` ×3（每次张嘴一声）。第一声由手动/空闲入口播放，其余由动作线程补发，
  短叫结束后动作中段不再静音。
- 画圈不是连续 360° 旋转：`head_yaw` 只有 ±170° 行程，所以用 yaw ±1.0、
  pitch −0.20±0.25、roll ±0.08 让鼻子在空中画三圈。
- **原地踏步已移除**：行走策略对短时交替指令不产生真实步态，需要专门训练的动作/技能。
- 空闲从 `idle.library` 里随机挑一个动作（默认四个，不连续重复），动作自带声音；
  都不可用时仍只发声。`idle.gesture=false` 时只叫不动。
- 音量 0～100，`PCM Playback Volume` / `Line Playback Switch`；保存失败只提示，
  不影响本次已生效的音量。

## 安装

```bash
# 从电脑推到板子
./install.sh duck@<板子IP>

# 板子上直接装（当前用户就是 duck）
./install.sh
```

`install.sh` 只做三件事：同步到 `/opt/duckphone`、装 `systemd/duckphone.service`、重启并打印地址。
它不改 `robotd` 配置、不动固件。卸载：

```bash
sudo systemctl disable --now duckphone
sudo rm -rf /opt/duckphone /etc/duckphone
```

手动跑（排障用，不装服务）：

```bash
python3 server.py --static ./static
```

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `--port` | `8001` | 监听端口 |
| `--robot-socket` | `/run/robotd.sock` | `robotd` 的 unix socket |
| `--token-file` | `/etc/duckphone/token` | 配对码文件（只有 `--auth` 时读） |
| `--auth` | 关 | 启用 6 位配对码；**默认关闭**，页面也不再问配对码 |
| `--no-padd-control` | 关 | 页面不能一键停 `padd`，只能复制命令 |
| `--subscribe-hz` | `20` | 状态流频率 |

## 第一次使用

1. 手机连上和板子同一个 Wi-Fi。
2. 浏览器打开 `http://<板子IP>:8001/`。
3. 页面顶部显示「只读」时点**接管**；显示「已连接」说明你在驾驶。
4. 长按**卸力**可以随时让关节松掉。

策略条只在 `robot.state.policy == walk` 时可用方向盘；其余状态说明别的网络正在驱动，
此时摇杆的指令本来就没用。

## 测试

```bash
python3 -m unittest discover -s verification
```

不需要板子：`verification/helpers.py` 里有一个假的 `robotd`，在 unix socket 上说同一套
JSON-RPC，覆盖帧编解码、看门狗、角色门禁、策略条和端到端协议。

## 安全边界

- 只监听局域网；**没有 TLS、不要做端口映射**。要从外网用，见
  [`docs/design/remote-access-design.md`](../docs/design/remote-access-design.md)。
- 配对码默认**不启用**。启用后是 6 位数字、5 次错误锁 60 秒、存在 `/etc/duckphone/token`（`0600`）。
- `/stop` 永不校验配对码——唯一必须成功的命令是让机器人停下的那个。
- 四层看门狗：页面 250 ms 不发摇杆帧就归零、会话 5 s 无消息断开、`robotd` 自己 500 ms deadman、
  健康状态 1 Hz 回传。桥**不会**定时重发上一帧非零速度，因为那和「手指按住」无法区分。
- 单元**故意不设** `NoNewPrivileges=yes`：一键停 `padd` 要跑 `sudo -n systemctl stop padd`。
  想开硬化就用 `--no-padd-control` 启动，页面上会变成复制命令。

## 已知限制

- 竖屏专用。`manifest.webmanifest` 是 `orientation: portrait`，横屏不做。
- 页面用 Service Worker 缓存，`static/sw.js` 的 `VERSION` 是手动改的——改了 `app.js` 一定要跟着改，
  否则已经装过页面的手机永远拿到旧 bundle，看起来像服务端 bug。`index.html` 里的
  `app.js?v=7` / `style.css?v=7` 是第二道缓存破坏，改资源时和 `VERSION` 一起递增。
- 不跟随发布产物。`install.sh` 装到 `/opt/duckphone`，板上其他东西都不引用它。

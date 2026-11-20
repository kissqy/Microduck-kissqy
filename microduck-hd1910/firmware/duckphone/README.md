**简体中文** | [English](README.en.md)

# 📱 duckphone · 局域网手机遥控

手机连同一个 Wi-Fi，浏览器打开 `http://<板子IP>:8001/` 就能驾驶。不用装 App，不用蓝牙配对，
不用数据线。竖屏单页：策略条在上、摇杆居中、四个动作按钮 2×2 在下。

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
| 策略条 | 列出本机装的策略，点一下执行一次；`行走` 是静止态，其余跑完自动回 `walk` |
| 接管 / 交还 | 同一时刻只有一个驾驶者，第二台设备进入只读；`policies` 只读也放行 |
| 卸力 | 长按 1.5 s 一步生效，不弹确认框 |
| 状态页 | 连接、策略、控制环、电源、双温度、输入源 |
| 警告详情 | 倒地/倾斜、温度、电量、控制环丢帧、`padd` 冲突，各带处理建议 |
| 维护页 | 重启舵机、输入源、版本、排障命令 |

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
  否则已经装过页面的手机永远拿到旧 bundle，看起来像服务端 bug。
- 不跟随发布产物。`install.sh` 装到 `/opt/duckphone`，板上其他东西都不引用它。

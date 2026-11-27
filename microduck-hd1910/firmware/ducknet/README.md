**简体中文** | [English](README.en.md)

# 🦆 ducknet · 蓝牙配网（Linux 桌面）

机器人刚装好、或者换了地方连不上 Wi-Fi 的时候，**蓝牙是唯一的入口**：没有网络就没有 SSH，
也没有网页中控。`ducknet` 是一个 Linux 桌面程序，用 BLE 连上机器人、输 PIN、改它的网络配置。

它故意只做这一件事：

| 能做什么 | 说明 |
| --- | --- |
| 看网络 | SSID、信号、IPv4/IPv6、MAC、接口、地址来源（DHCP / 固定） |
| 换 Wi-Fi | 扫描附近网络，选一个加进去；密码**记一次**，之后点连接直接连 |
| 固定 IP | 给某个网络钉死一个地址，写进机器人的 NetworkManager 配置，重启后仍然有效 |
| 忘网络 | 让机器人删掉已保存的配置（本机记住的密码跟着删） |
| 其他 | 改机器人名称、读某个守护进程的日志、重启、手发诊断方法 |
| 不做 | 运动控制、固件升级、改 PIN（BLE 上固件明确拒绝） |

它不改变机器人源码，只是 `btd` 那个 GATT JSON-RPC 的一个客户端——和 `robotctl`、`duckctl`、
官方手机 App 同一权限等级。协议与设计见
[`docs/design/ble-provisioning-app.md`](../docs/design/ble-provisioning-app.md)；
`btd`/`configd` 那一侧归
[`docs/design/app-path-design.md`](../docs/design/app-path-design.md)。

## 前提：板上得有人在广播

客户端扫不到机器人，绝大多数时候不是客户端的问题，而是**板子上没有 `btd`**——没有它就没有
那个 GATT 服务在广播；`net.*` 还要求 `configd`，而 `configd` 的 Wi-Fi 后端是 NetworkManager。

```bash
sudo systemctl is-active btd configd NetworkManager     # 三个都要 active
```

缺的话用同目录的脚本补齐（默认只打印计划，`--apply` 才动板子）：

```bash
./deploy_ble_provisioning.sh duck@<板子IP>               # 看要做什么
./deploy_ble_provisioning.sh duck@<板子IP> --apply       # 交叉编译并装 btd + configd + robotctl
./deploy_ble_provisioning.sh duck@<板子IP> --apply --migrate-network   # 再把 wlan0 交给 NM（有掉线风险）
```

> 板上这份 `configd` 一定要是**本仓库构建的**：它比上游 0.15.1 多了 `net.connect` 的 `ipv4`
> 参数（固定 IP 靠它）。上游版会以 `unknown field ipv4` 拒绝整条请求；`ducknet` 认出这种情况后
> 会退回一次 DHCP 连接并说明原因，而不是让你以为密码打错了。

## 安装

```bash
./install.sh              # 装到 ~/.local：venv + 启动器 + 桌面入口
./install.sh --uninstall  # 卸载（保留源码）
```

脚本只写三处：`~/.local/share/ducknet/venv`、`~/.local/bin/ducknet`、
`~/.local/share/applications/ducknet.desktop`（应用菜单里叫「Microduck 蓝牙配网」）。

不想装也能直接跑：

```bash
./app.py --demo      # 进程内假机器人，不碰蓝牙、不需要 bleak
./app.py             # 真机
```

系统前提：Python ≥ 3.10、`python3-tk`、BlueZ 在跑、当前用户能访问 BlueZ 的 D-Bus
（桌面会话通常就行；报权限错就把用户加进 `bluetooth` 组）。

## 用

窗口左侧是机器人与连接，右侧四个页签，底部日志常驻。

1. **连接**：启动会自动扫描 8 秒 → 选中机器人 → 输 PIN（出厂 `000000`）→「连接」。
   连上后自动读 `system.info`、`net.status`、`net.scan`。
2. **网络状态**：状态、SSID、接口·MAC、IPv4/IPv6、地址来源；右侧信号强度与**控制台地址**
   `http://<IP>:8001`——直接点就开浏览器（手机/桌面中控都挂在那个端口上）。
3. **Wi-Fi**：
   - 「扫描附近网络」→ 列表（SSID / 信号 / 加密 / 是否已保存）；双击一行也能连。
   - WPA2/WPA3 **只在第一次**问密码；连成功后密码存在本机，之后点连接直接用。
     只有机器人回 `bad_key`（真的被拒）才重新问，并且会说明"机器人拒绝了这个密码"。
   - 卡片「固定 IP」：勾选 → 填 IP / 掩码 / 网关 / DNS →「保存」。
     掩码可以写 `255.255.255.0` 或 `24`；网关与 DNS 可留空。下次连这个网络时随
     `net.connect` 下发，写进 NM profile，**重启后仍然是这个地址**。「清除」回到 DHCP。
   - 「按 SSID 忘记」用于已保存但当前不在视野里的网络。
   - `WEP` 与企业网（802.1X）会被标「不支持」并直接说明原因，不发请求。
4. **机器人**：改名、读日志（选 unit 与行数）、重启（红色按钮，二次确认写明会断开并卸力）。
5. **诊断**：手发任意 BLE 允许的方法，参数是 JSON。

`psk` / `pin` 永远显示 `<已隐藏>`，既不打进日志、也不落盘到日志文件。

### 本机记住了什么

```text
~/.config/ducknet/profiles.json     # $XDG_CONFIG_HOME 存在时跟着它走；文件 0600、目录 0700
```

- 密码按 **SSID** 记（换台机器人同一个网络也不用再输）；
- 固定 IP 按 **机器人序列号 + SSID** 记（同一网段两台机器人不会抢一个地址）；
- **明文**，和 `~/.netrc` 一个量级。想换系统钥匙串，替换 `profiles.Store.password()` /
  `set_password()` 两个方法即可；
- 文件坏了不会让程序起不来：改名成 `profiles.json.broken` 留证，然后当空配置继续。

## 验收

```bash
python3 -m unittest discover -s tests      # 51 项：分帧、认证、net.*、ipv4、本地记忆
DISPLAY=:0 python3 tests/manual_gui_check.py   # 界面走真机分支（假蓝牙），22 项

./acceptance.py --demo                     # 假机器人跑完整流程
./acceptance.py --scan-time 8              # 真机只读（不动网络）
./acceptance.py --join '大树下' --psk '…' \
  --static-ip 192.168.110.240/23 --gateway 192.168.110.1 --dns 192.168.110.1
```

`--static-ip` 会写进机器人配置，**地址要选你留得住的那个**：写错就是"重启以后再也 ssh 不上"，
只能靠 BLE 或串口改回来。

## 排障

| 现象 | 处理 |
| --- | --- |
| 扫不到机器人 | 板上 `btd` 在跑吗（见「前提」）；机器人是否已被手机 App/另一台电脑连着（一台只服务一个中心）；走近一些 |
| 日志反复"上一条蓝牙操作还没结束" | 通常是另一个客户端正连着它。程序会点明；也可 `bluetoothctl disconnect <地址>` |
| 扫到但连不上（HCI `0x3E`） | 链路层抖动（Wi-Fi/蓝牙共射频），客户端自动重试 8 轮 |
| `net.status` 报 NM D-Bus 错误 | 板上没有 NetworkManager，见「前提」 |
| 固定 IP 设完后 `net.connect` 超时 | 板上 NM 1.52 的已知崩溃（换配置时旧 activation 未退干净）。本仓库的 `configd` 已先等网卡 `DISCONNECTED`；旧二进制重试一次即可 |
| 固定 IP 忘了写过什么 | 机器人不回读这个字段，看本机 `profiles.json`，或 `nmcli connection show <SSID> \| grep ipv4` |
| 打开第二个窗口 | 会提示"已经有一个在运行"并退出——单实例锁，避免两个窗口抢同一个 BLE 中心 |

## 目录

```text
ducknet/
  app.py         Tkinter 界面 + 后台 asyncio 线程桥
  protocol.py    UUID / 分帧 / 广播解析 / 脱敏（不依赖蓝牙）
  session.py     JSON-RPC 会话：认证、调用、超时、错误类型、net.*/system.* 封装
  ble.py         bleak 后端：扫描去重、连接、按需配对、按 MTU 分块
  agent.py       BlueZ Agent1（NoInputNoOutput），避免"没有 agent 导致配对失败"
  profiles.py    本机记住的密码与固定 IP
  fake.py        进程内假机器人（--demo 与测试）
  acceptance.py  自动验收（默认只读）
  install.sh     装启动器与桌面入口
  deploy_ble_provisioning.sh  给机器人补 btd/configd/NM
  tests/         单测 + 界面真机分支联调
```

Tk 主线程只做界面；蓝牙与 JSON-RPC 全在后台线程的 asyncio 循环里，结果经
`queue.Queue` + `root.after(50)` 回到主线程。

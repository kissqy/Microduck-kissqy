**简体中文** | [English](README.en.md)

# 验证记录

不需要板子。`helpers.py` 里有一个可编程的假 `robotd`（在临时 unix socket 上说同一套
换行分隔的 JSON-RPC）和一个最小 WebSocket 客户端，所以这些用例走的是页面用的同一条代码路径，
只是没有手机。

在本目录运行：

```bash
python3 -m unittest discover -s verification
```

| 文件 | 覆盖什么 |
| --- | --- |
| `test_ws_frames.py` | RFC 6455 帧编解码：掩码、分片、长度边界、控制帧。板子没有 `websockets` 包，这一段是自己写的，所以单独测 |
| `test_watchdog.py` | 四层看门狗里的前两层：摇杆 250 ms 不刷新就归零、会话 5 s 无消息断开 |
| `test_protocol.py` | 端到端：真实 HTTP 服务 + 真实 WebSocket + 假 daemon。覆盖角色门禁（第二台设备只读、接管、交还）、`relax` 确认、`/stop` beacon、策略条的纯函数与 `policyDo`、以及只读会话仍能读到 `policies` |

`test_protocol.py` 里的这些用例不是凑数，每一个都对应一次真机上真实发生过的故障：

- **只读会话读不到策略** —— 角色检查排在读数据之前，第二台设备的策略条永远空着。
- **`padd` 冲突不可见** —— 手柄服务在跑时手机指令被静默覆盖，页面看起来像卡住。
- **卸力没有确认** —— 误触一次就把站着的机器人放倒。

## 这些用例证明不了什么

- 不验证真机运动。摇杆范围、策略跑完回 `walk`、`init`/`enable` 能否被接受，都是 `robotd` 的事，
  这里只断言桥把什么发出去了。
- 不验证浏览器。`dvh` 回退、摇杆直径、Service Worker 换版，都要在华为浏览器上看。

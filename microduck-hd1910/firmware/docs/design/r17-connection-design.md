**原文 / Original** | [English](r17-connection-design.en.md) | [Русский](r17-connection-design.ru.md)

## 当前 R17 v1.0.157-Fix9 / control.36

当前安装和接入机制以 [本页的连接机制](#r17-desktop-connection) 为准：早期 IPC 仅接收四步状态，四步全部成功后订阅实时数据并接入输入。安装及开机等待均使用事件；原生控制流程保持 control.36。旧主服务钩子迁移/扫描和额外启动监听线程已删除。正常启动不复制配置；配置修改者在实际变更时备份并保存。独立 ToF 继续按原流程运行。

## GameSir 连接与按层修复（Fix9）

Linux `bluetooth.service` 负责无线连接；R7 `gamesir-xboxd` 将 GameSir 输入映射成虚拟 Xbox；官方 `padd` 发送意图到 robotd。安装与开机仍遵循 Fix6 的四步事件等待，不修改 robotd、官方 padd、网页输入长连接或实体／网页互斥机制。

修复 helper 只在用户点击时通过已有维护 SSH 执行，执行后退出，无常驻修复服务、定时查询或就绪文件。默认“连接／修复”先核对一次：完整链路已经正常则直接返回，不停止服务、卸力、改动配对或手机连接服务；蓝牙断开或蓝牙已连但实体输入缺失时，只尝试原有 HID 连接一次；未配对则提示明确选择配对。失败保留原配对。缺失服务只启动该服务；实体输入存在但虚拟 Xbox 缺失时只重启桥接；虚拟 Xbox 存在但 padd 没有打开它时只重启 padd。正在运行 startup_gate 等待程序的输入服务不重启，主服务故障不通过重新配对处理。

勾选“首次／重新配对”才允许暂停实体输入、执行已有卸力确认、删除目标旧配对、重置适配器一次并扫描、配对、信任和连接。目标名称必须是 A+HOME 的 GameSir-Nova 2 Lite；多只已记录手柄要求指定 MAC，其他设备的配对不删除。扫描最多 15 秒，发现目标可提前结束；配对、连接和整体事务都有上限，没有自动重试。适配器 power-off 报错时回读实际电源状态；已经关闭可以继续，未确认则报具体失败，不能由此自动重启 Zero。扫描 InProgress 单独报告占用。Fix9 在配对与信任完成后始终发送一次 HID ConnectProfile，即使 BlueZ 已报告 Connected:yes；配对时临时 ACL 连接不等于输入通道建立。AlreadyConnected 回执仅表示通道已连，仍由输入设备与 padd 打开状态确认就绪。连接失败保留目标配对与发现的 MAC，显示原始 BlueZ 失败原因；等待中蓝牙断开归蓝牙层，蓝牙正常但没有实体节点归 HID 接入。只有读取到 startup_gate 等待状态才提示主服务启动条件，其他失败不笼统归因 robotd。

`btd` 是手机／应用连接服务，不是手柄桥接。只在配对时临时停止原本运行的 btd，结束后恢复原运行状态；不改 enable/disable，不开启原本关闭的服务。恢复 btd 失败单独报告；已经确认的手柄连接不因此变为失败。配对失败时仅恢复操作前运行的输入服务，不启动原本停止的服务。操作后连接真实变化仍重新报告失败。

输入就绪检查等待 `/dev/input` 的创建、权限和打开事件，最多 8 秒，不做每 0.5 秒查询。核对虚拟 Xbox 设备和服务 active 之外，还核对 padd 进程已打开对应 event 节点；这不等同于策略已启用，也不证明无线延迟或多手柄优先级。面板区分上次核对和已有热插拔事件提供的当前输入状态，机器人 HOME／策略状态来自原遥测，没有追加查询。各步结果以名称、成功／失败和原因记录，进度 JSON 仅内部使用。

R7 桥接在启动枚举前建立 inotify 观察，之后只在输入设备热插拔／权限事件重新发现主设备或缺失的 Consumer Control 节点；数据读取使用阻塞 poll。缺失主设备和辅助节点的每秒扫描已移除。原按键、摇杆、扳机映射及辅助节点异常退出处理保持原件；辅助节点断开不销毁工作中的主设备和虚拟 Xbox。此修改需要安装 Fix8 随包固件一次以替换桥接二进制，robotd 原生版本仍为 control.36。


# R17 desktop connection

`start.cmd` and `start.command` launch `console.py --dashboard --feetech --open`.
The local page appears before SSH; the connection button selects the robot. The
existing address preference and `SudoCredential` serve both SSH and maintenance.
OpenSSH askpass carries a password in the child's environment, not in argv or
public status. The existing `StrictHostKeyChecking=accept-new` policy remains;
conflicting host keys are errors.

`console/connection.py` owns the selected target and connected session. Changing
it ends the old collector and input/maintenance transports before starting a new
generation. It does not send HOME, relax, or policy-enable commands. An active
maintenance operation finishes before the target can be replaced. Disconnect
preserves the current browser recording; a new connection clears the old session.
Disconnect/shutdown stop the SSH streams. Closing one browser tab only removes
that tab's WebSocket; it does not disconnect the PC session or other pages. A PC
session left connected continues receiving telemetry.

## Process ownership and exit (v1.0.156)

Windows `start.cmd` changes to the system temporary directory and launches
`console.py` by absolute path. The shared child-process factory gives all four
SSH launch paths a temporary working directory by default, so a live SSH process
does not keep the old extraction directory as its cwd. Script and asset paths
remain resolved from their original absolute locations.

On Windows each child has a private, children-only Job with kill-on-last-handle-close.
The console itself is not assigned to any Job; each Job contains that child and
its attached descendants. Children are created suspended, assigned, then resumed;
normal cleanup closes them explicitly, while terminal closure or termination of
the console lets the OS retire an already assigned subtree. There is no process
name scan and no termination of unrelated SSH, Python or browser processes.
Windows end-to-end closure/forced-exit behavior is not yet tested on a real
Windows host. The guarantee does not cover an abrupt kill in the narrow interval
between suspended child creation and Job assignment.

Connection teardown marks the old generation stopped and permanently closes its
transports before replacing them. Worker joins run outside the connection lock,
so a final event cannot deadlock against the thread being joined. Closed old
transports cannot reconnect themselves. Normal Ctrl+C follows a finally path that
independently closes service/control/connection ownership, the local server,
remaining owned processes and pipe handles, and the system log; failure of one
cleanup does not skip the rest. These are exit actions, without a new background
poller or native 50 Hz work.

Address preferences and Windows DPAPI-protected credentials remain in the user's
AppData locations. Their files are opened briefly for existing reads/writes, not
held as handles in the extraction directory. Closing a browser tab still closes
only that page; the Python console is a separate running process. v156 does not
find or kill orphaned processes already left behind by an older version.

The console release is 1.0.156, while its full firmware archive remains byte-for-byte
identical to v155/control.34. A robot already on that build needs no reinstall.
Native HOME and saved-direction semantics remain owned by their existing pages.

## Initial feedback and reconnection (v1.0.155)

Before the first complete robot frame, the dashboard displays a neutral connection
wait: establishing SSH, or SSH connected while waiting for initial feedback.
`startup-status.js` centralizes this distinction. An unfinished first control
cycle (`control loop has not completed a cycle yet`) is also startup progress,
not a sensor failure. It does not replace reported SSH/authentication, transport,
service-health or native startup errors. Once feedback has arrived, stale state
remains a warning rather than being relabeled an initial wait. A failed native
startup remains authoritative while its existing health heartbeat is live.

Disconnect and replacement connection generations reset browser reports,
channel timestamps and auxiliary connection state before new frames are shown.
Old errors and old ready states cannot enter the new session. Paused/offline
sessions do not inherit a failure banner from the previous robot. These changes
reuse existing transport events and render paths, without a new timer, SSH probe,
remote service or telemetry poller. Saved-direction rendering is owned by
[R17 settings](r17-settings-design.md#v10155-已保存方向显示); it is display metadata,
not a new telemetry source.

## Raw telemetry (v1.0.144)

Normal dashboard collection uses `console/raw_telemetry.py`, not a remote copy of
`console/agent.py`. `robot.rawSubscribe` negotiates on the existing robotd Unix
socket with a single JSON-RPC request. After its accepted reply, that connection
is exclusively the binary stream; another request or EOF ends it. `robot.subscribe`,
`robot.busStatus` and the commissioning/startup routes remain compatible. Old
collector helpers remain for explicit local/legacy tests, outside the normal v144
path. v144 requires its matched control.27 robotd; it reports the missing protocol
instead of silently restarting the old high-frequency collector on the Zero.

The wire is a little-endian u32 record length, one kind byte, and payload, bounded
at 8MiB per record. Kind1 carries JSON metadata with `schema: r17.raw.v1`; kind2
carries dynamic state/bus values; kind4 carries low-rate system/health facts. The
dynamic serializer consumes typed structs directly, without a per-tick JSON Value
tree. Its tags are null=0, false=1, true=2, i64=3, u64=4, f64=5, UTF-8=6, array=7,
object=8. Integers/floats are little-endian 64-bit; strings and collections have
u32 lengths. Object keys are length-prefixed UTF-8 strings. Original u64 and f64
bits stay on the network. The browser represents integers outside its exact range
as decimal strings. Nonfinite measurements become null in the display adapter,
matching the former native JSON encoding, without terminating unrelated data.

`console/socket_transport.py` runs `ssh -N -L 127.0.0.1:port:remote_socket`: no remote
shell or Python telemetry program. Streams to one endpoint share an SSH process,
and closing the final stream retires it. The original saved authentication is
used. Readiness requires both the requested port's debug line and entry into the
SSH client loop with ExitOnForwardFailure; the port line alone precedes bind and
is insufficient. An uncertain input is never automatically replayed.

The PC forwards complete records unchanged over an authenticated, same-origin
WebSocket. One Hub fans out a single source to multiple pages, bounds each queue,
and closes a slow subscriber instead of accumulating unlimited memory. It caches
only definitions and the ToF subscription descriptor, never replaying cached
measurements with a fresh arrival time. Generation checks prevent old SSH frames,
errors or auxiliary state from entering a replacement connection.

For existing maintenance/HOME predicates the PC decodes a 10Hz compatibility
mirror. Rendering, service interpretation, FK and recording use the browser's
`raw-telemetry.js`; `/api/snapshot` is not the dashboard's periodic main data path.
`raw-kinematics.js` derives frame and skeleton poses from static definitions emitted
by the robot's compiled kinematics model. No separate set of geometric constants
is maintained in the console; the native FK example supplies numerical regression
fixtures. Invalid joint measurements leave these derived poses unavailable rather
than manufacturing zero angles.

ToF uses a second direct SSH forward to its existing `tof.stream` IPC service.
The PC wraps the original bounded JSON line in kind3; no extra ToF hardware poller
or head-IMU subscriber is added. Camera/audio services keep their existing paths.
The robot's low-rate sender reads /proc, relevant sysfs values, public identities,
camera statistics, input capabilities, and saved pad settings about every2s while
an observer is connected. It opens neither evdev nor the motor port for telemetry.
Native snapshot ownership and the independent safety/communication statistics are
owned by [r17-settings-design.md](r17-settings-design.md).

Each browser page records at the existing roughly10Hz display cadence, retaining
at most1200 frames (about120s). Full JSON/CSV exports and imported JSON replay use
the original schemas. Records are browser memory, so exporting before a reload or
closing that page is required to keep them. Pausing display or entering replay does
not stop live collection. Raw transport does not compress the JSON export.

## Browser input and socket activation (v1.0.144)

Input follows browser → local control WebSocket → PC `Transport` → forwarded
`/run/microduck-webpad/input.sock` → virtual Xbox → official padd → robotd. The
browser sends standard controller state; official padd retains button/action
mapping and robotd remains the only motor executor. Current model/button bindings
are owned by [R17 settings](r17-settings-design.md).

`microduck-webpad.socket` owns a root:robot0660 listener. First actual browser
input activates `webpad.py`, which accepts the inherited systemd descriptor. A
page connect/status request only uses local/native-telemetry status; it does not
connect this socket or instantiate uinput. Idle exit closes the worker's own
descriptors without unlinking the systemd-owned socket. A later real input can
activate another worker. Installation disables the old service's independent
boot enablement and enables the socket; restart and status paths do not wake the
worker simply to prove it is alive.

Physical controllers take precedence. Kernel input uevents invalidate the device
cache; the adapter checks the actual physical devices before accepting each input.
Physical arrival closes the virtual Xbox and clears its owner. Physical removal
does not replay old inputs; a fresh browser action is required. All first input
frames, including skill buttons and their releases, use the same `padd`
Attached/generation handshake before delivery to the newly created virtual Xbox.
The adapter does not require an initial Start or HOME command. The600ms input
lease and stale-frame/sequence checks remain: expiry, physical takeover or an
owner-scoped close discards pending frames, so a later attachment cannot replay
an abandoned skill request. A slow first SSH connection may discard
an expired unsent frame, retaining the ready transport for the next fresh action.
Closing a dead stream does not reconnect it. A late close from an old page cannot
clear a replacement owner's controls. EOF of the owning stream releases it.

The adapter permits AF_UNIX and AF_NETLINK. While active, it retains its20ms input
wait and one-second fallback discovery; the idle worker exits. The actual GameSir
bridge remains an independent service. Its Consumer Control EOF/error handling
retires only the auxiliary descriptor, leaving the main controller and virtual
Xbox alive; Fix8 discovers its replacement on input hotplug events as described above.

Audio status/set requests run `packaging/audio-control.py` once through the
existing maintenance channel and use the same native ALSA implementation. They do
not start webpad, continuously poll audio, or block the input write lock. The
maintenance process may wait on its existing connection; it is not a telemetry
poller. The installer and both client packages must be updated together.

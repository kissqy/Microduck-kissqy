[Русский](r17-connection-design.ru.md)

[原文 / Original](r17-connection-design.md) | **English**

## R17 v1.0.157-Fix 9 / control.36 baseline

The historical Fix 6 installation / connection flow receives only four-step status through early IPC, subscribing to live data and input after all four succeed. Install / boot waits are event-driven and native control remains control.36. Old main-service hook migration / scanning and extra startup-listener threads are removed. Normal boot does not copy config; writers back up / save only actual changes. Independent ToF retains its flow. The former standalone Fix 6 release note was retired; the mechanism remains described here and in [robotd design](robotd-design.en.md).

## GameSir connection and layer-specific repair (Fix 9)

Linux `bluetooth.service` owns wireless connection; R7 `gamesir-xboxd` maps GameSir to virtual Xbox; official padd sends intents to robotd. Fix 6 four-step event startup remains, without changing native robotd / padd, persistent web input, or physical / web exclusion.

The repair helper runs through existing maintenance SSH only when clicked, then exits; no resident repair / timer / ready-file. Default Connect / Repair checks once and returns without stopping / unloading / re-pairing if the chain works. Disconnected Bluetooth or connected Bluetooth without physical input triggers one existing HID-connect attempt. Unpaired devices require explicit pairing selection; failure preserves pairing. Missing service starts only itself; physical input without virtual Xbox restarts only bridge; virtual Xbox not opened by padd restarts only padd. Input services waiting in startup_gate are not restarted; main-service failures are not repaired by pairing.

Only selecting “首次／重新配对” (First / Re-pair) permits pausing physical input, existing torque-release confirmation, deleting target pairing, one adapter reset, scan / pair / trust / connect. Target must be GameSir-Nova 2 Lite in A+HOME mode; multiple recorded controllers require a MAC, and other pairings remain. Scan≤15 seconds, ending early on discovery; pairing / connect / transaction are bounded, without retries. Power-off errors read actual state: confirmed off can continue; otherwise report failure, never auto-reboot ZERO. Scan InProgress reports occupancy. Fix 9 always sends one HID ConnectProfile after pairing / trust, even if Connected: yes; temporary ACL does not prove input establishment. AlreadyConnected still requires device / padd-open confirmation. Failures preserve pairing / MAC and original BlueZ cause; Bluetooth disconnect maps to Bluetooth, connected-without-input to HID. Only observed startup_gate waits implicate main startup.

btd connects phones / apps, not gamepads. Pairing temporarily stops only an already-running btd and restores its prior state without enable / disable or starting previously stopped services. Restoration failure is separate from a confirmed gamepad connection. Pairing failure restores only previously running input services; real post-operation disconnect is still reported.

Readiness waits≤8 seconds for /dev / input create / permission / open events, rather than 0.5-second queries. Beyond device / service-active, padd must have the correct event node open. This does not prove policy enabled, wireless latency, or multi-controller precedence. Panel separates last check from hotplug-derived live input; HOME / policy uses existing telemetry. Named step results include success / failure / reason; progress JSON is internal.

R7 installs inotify before enumeration, rediscovering main / missing Consumer Control only on hotplug / permission events, with blocking poll for data. One-second missing-device scans are removed. Mapping / auxiliary-error handling remains; auxiliary disconnect does not destroy the working main device / Xbox. Installing Fix 8's bundled firmware once replaces the bridge, while native robotd remains control.36.


# R17 desktop connection

`start.cmd` and `start.command` launch `console.py --dashboard --feetech --open`.
The local page appears before SSH; the connection button selects the robot. The
existing address preference and `SudoCredential` serve both SSH and maintenance.
OpenSSH askpass carries a password in the child's environment, not in argv or
public status. The existing `StrictHostKeyChecking=accept-new` policy remains;
conflicting host keys are errors.

`console/connection.py` owns the selected target and connected session. Changing
it ends the old collector and input / maintenance transports before starting a new
generation. It does not send HOME, relax, or policy-enable commands. An active
maintenance operation finishes before the target can be replaced. Disconnect
preserves the current browser recording; a new connection clears the old session.
Disconnect / shutdown stop the SSH streams. Closing one browser tab only removes
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
Windows end-to-end closure / forced-exit behavior is not yet tested on a real
Windows host. The guarantee does not cover an abrupt kill in the narrow interval
between suspended child creation and Job assignment.

Connection teardown marks the old generation stopped and permanently closes its
transports before replacing them. Worker joins run outside the connection lock,
so a final event cannot deadlock against the thread being joined. Closed old
transports cannot reconnect themselves. Normal Ctrl+C follows a finally path that
independently closes service / control / connection ownership, the local server,
remaining owned processes and pipe handles, and the system log; failure of one
cleanup does not skip the rest. These are exit actions, without a new background
poller or native 50 Hz work.

Address preferences and Windows DPAPI-protected credentials remain in the user's
AppData locations. Their files are opened briefly for existing reads / writes, not
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
not a sensor failure. It does not replace reported SSH / authentication, transport,
service-health or native startup errors. Once feedback has arrived, stale state
remains a warning rather than being relabeled an initial wait. A failed native
startup remains authoritative while its existing health heartbeat is live.

Disconnect and replacement connection generations reset browser reports,
channel timestamps and auxiliary connection state before new frames are shown.
Old errors and old ready states cannot enter the new session. Paused / offline
sessions do not inherit a failure banner from the previous robot. These changes
reuse existing transport events and render paths, without a new timer, SSH probe,
remote service or telemetry poller. Saved-direction rendering is owned by
[R17 settings](r17-settings-design.en.md#v10155-saved-direction-display); it is display metadata,
not a new telemetry source.

## Raw telemetry (v1.0.144)

Normal dashboard collection uses `console/raw_telemetry.py`, not a remote copy of
`console/agent.py`. `robot.rawSubscribe` negotiates on the existing robotd Unix
socket with a single JSON-RPC request. After its accepted reply, that connection
is exclusively the binary stream; another request or EOF ends it. `robot.subscribe`,
`robot.busStatus` and the commissioning / startup routes remain compatible. Old
collector helpers remain for explicit local / legacy tests, outside the normal v144
path. v144 requires its matched control.27 robotd; it reports the missing protocol
instead of silently restarting the old high-frequency collector on the Zero.

The wire is a little-endian u 32 record length, one kind byte, and payload, bounded
at 8 MiB per record. Kind 1 carries JSON metadata with `schema: r17.raw.v1`; kind 2
carries dynamic state / bus values; kind 4 carries low-rate system / health facts. The
dynamic serializer consumes typed structs directly, without a per-tick JSON Value
tree. Its tags are null=0, false=1, true=2, i 64=3, u 64=4, f 64=5, UTF-8=6, array=7,
object=8. Integers / floats are little-endian 64-bit; strings and collections have
u 32 lengths. Object keys are length-prefixed UTF-8 strings. Original u 64 and f 64
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

For existing maintenance / HOME predicates the PC decodes a 10 Hz compatibility
mirror. Rendering, service interpretation, FK and recording use the browser's
`raw-telemetry.js`; `/api/snapshot` is not the dashboard's periodic main data path.
`raw-kinematics.js` derives frame and skeleton poses from static definitions emitted
by the robot's compiled kinematics model. No separate set of geometric constants
is maintained in the console; the native FK example supplies numerical regression
fixtures. Invalid joint measurements leave these derived poses unavailable rather
than manufacturing zero angles.

ToF uses a second direct SSH forward to its existing `tof.stream` IPC service.
The PC wraps the original bounded JSON line in kind 3; no extra ToF hardware poller
or head-IMU subscriber is added. Camera / audio services keep their existing paths.
The robot's low-rate sender reads /proc, relevant sysfs values, public identities,
camera statistics, input capabilities, and saved pad settings about every 2 s while
an observer is connected. It opens neither evdev nor the motor port for telemetry.
Native snapshot ownership and the independent safety / communication statistics are
owned by [r 17-settings-design.md](r17-settings-design.en.md).

Each browser page records at the existing roughly 10 Hz display cadence, retaining
at most 1200 frames (about 120 s). Full JSON / CSV exports and imported JSON replay use
the original schemas. Records are browser memory, so exporting before a reload or
closing that page is required to keep them. Pausing display or entering replay does
not stop live collection. Raw transport does not compress the JSON export.

## Browser input and socket activation (v1.0.144)

Input follows browser → local control WebSocket → PC `Transport` → forwarded
`/run/microduck-webpad/input.sock` → virtual Xbox → official padd → robotd. The
browser sends standard controller state; official padd retains button / action
mapping and robotd remains the only motor executor. Current model / button bindings
are owned by [R17 settings](r17-settings-design.en.md).

`microduck-webpad.socket` owns a root: robot 0660 listener. First actual browser
input activates `webpad.py`, which accepts the inherited systemd descriptor. A
page connect / status request only uses local / native-telemetry status; it does not
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
Attached / generation handshake before delivery to the newly created virtual Xbox.
The adapter does not require an initial Start or HOME command. The 600 ms input
lease and stale-frame / sequence checks remain: expiry, physical takeover or an
owner-scoped close discards pending frames, so a later attachment cannot replay
an abandoned skill request. A slow first SSH connection may discard
an expired unsent frame, retaining the ready transport for the next fresh action.
Closing a dead stream does not reconnect it. A late close from an old page cannot
clear a replacement owner's controls. EOF of the owning stream releases it.

The adapter permits AF_UNIX and AF_NETLINK. While active, it retains its 20 ms input
wait and one-second fallback discovery; the idle worker exits. The actual GameSir
bridge remains an independent service. Its Consumer Control EOF / error handling
retires only the auxiliary descriptor, leaving the main controller and virtual
Xbox alive; Fix 8 discovers its replacement on input hotplug events as described above.

Audio status / set requests run `packaging/audio-control.py` once through the
existing maintenance channel and use the same native ALSA implementation. They do
not start webpad, continuously poll audio, or block the input write lock. The
maintenance process may wait on its existing connection; it is not a telemetry
poller. The installer and both client packages must be updated together.

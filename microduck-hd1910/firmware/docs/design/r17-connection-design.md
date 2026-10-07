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
mapping and robotd remains the only motor executor. UI layout and button mapping
are unchanged.

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
frames, including LB from limp and their button releases, use the same `padd`
Attached/generation handshake before delivery to the newly created virtual Xbox.
The adapter does not require an initial Start or HOME command. The600ms input
lease and stale-frame/sequence checks remain: expiry, physical takeover or an
owner-scoped close discards pending frames, so a later attachment cannot replay
an abandoned LB recovery request. A slow first SSH connection may discard
an expired unsent frame, retaining the ready transport for the next fresh action.
Closing a dead stream does not reconnect it. A late close from an old page cannot
clear a replacement owner's controls. EOF of the owning stream releases it.

The adapter permits AF_UNIX and AF_NETLINK. While active, it retains its20ms input
wait and one-second fallback discovery; the idle worker exits. The actual GameSir
bridge remains an independent service. Its v142 handling of Consumer Control EOF
and poll errors is preserved: retire only the auxiliary descriptor and retry it
at most once per second, leaving the main controller and virtual Xbox alive.

Audio status/set requests run `packaging/audio-control.py` once through the
existing maintenance channel and use the same native ALSA implementation. They do
not start webpad, continuously poll audio, or block the input write lock. The
maintenance process may wait on its existing connection; it is not a telemetry
poller. The installer and both client packages must be updated together.

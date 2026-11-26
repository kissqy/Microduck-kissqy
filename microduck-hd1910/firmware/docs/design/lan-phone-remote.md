# The LAN phone remote — a browser, an address, no app

Status: built · Date: 2026-11-20 · Owner: kissqy

`duckphone/` is the bridge that makes `http://<board>:8001/` on the robot's own network a working
remote: one WebSocket per phone, one unix socket to `robotd`, a single-page touch UI, and nothing to
install on the phone. It exists because the two paths that already existed both start with
something a person may not have.

Companion to [`mobile-app.md`](mobile-app.md), which owns the owner's app — BLE to pair and
configure, WebRTC to drive — and to [`remote-webrtc.md`](remote-webrtc.md), which owns that
transport. This page owns the third path: the one that is a browser tab on the LAN.

| you want to | you use | and it costs you |
|---|---|---|
| drive from the owner's phone, off the LAN, with video | the app — `mobile-app.md` | installing and signing in |
| drive from a laptop's gamepad | `microduck-webpad` + `padd` | a gamepad, and the gamepad stack |
| drive from any phone already on the wifi | **this** | being on the wifi |

## 1. What it is allowed to be

An **ordinary socket client**, in the same authority class as `padd` and `console`, and for the same
reason: it holds no privileged access, opens no device, and controls nothing `robotd` would not do
for any other client. It runs as `duck`, which is in the `robot` group; `/run/robotd.sock` is
`root:robot 0660`. Nothing about `duckphone` needs root, and the unit asks for none.

That is also the boundary. The bridge must never become a second control authority — it may not
keep its own copy of what the robot is doing, decide for itself whether a move is safe, or paper
over a `robotd` refusal. Every rule below is a place where the temptation existed.

**The one exception, deliberately taken**: the unit does not set `NoNewPrivileges=yes`, because the
one-tap gamepad interlock runs `sudo -n systemctl stop padd`. A robot whose `padd` is fighting the
phone for the same joints is worse than a bridge with a wider syscall surface. Start with
`--no-padd-control` and the hardening is free — the page then copies the command instead of
running it.

## 2. The shape

```
phone browser ──WebSocket──▶ duckphone/server.py ──unix socket──▶ robotd
   static/                        rpc.py · ws.py                 /run/robotd.sock
   (PWA, one page)                sessions · watchdog             JSON-RPC, 20 Hz state
```

`ws.py` is a minimal RFC 6455 implementation and `rpc.py` a minimal JSON-RPC client, both on the
standard library, both for one reason: the board has `python3` and no `pip` for anything else. The
alternative was a dependency tree on a robot that updates as a signed artifact, and this bridge is
not important enough to be in that artifact at all.

`server.py` keeps no database and no log file. It holds, per connection, a session with a role and
the last stick sample; everything it reports is either a `robotd` reply or a number it just
measured.

## 3. Layered watchdogs, and why four of them

A phone that goes out of range does not close its socket. Every layer below exists because the one
above it can fail silently.

| layer | timeout | what ends it |
|---|---|---|
| page → bridge | 250 ms | the page stops sending `move`; the bridge commands zero |
| bridge session | 5 s | no message of any kind; the session is dropped, the role released |
| `robotd` deadman | 500 ms | no new intent; the control loop holds and stops |
| relayed health | 1 Hz | the page learns the link is stale instead of showing a frozen last frame |

The bridge deliberately does **not** re-send the last non-zero stick sample on a timer. A repeated
command is indistinguishable from a held finger, which is the failure the deadman exists to catch.

## 4. One driver, and what "readonly" means

`robotd` accepts one driving session at a time. The bridge forwards that rule rather than inventing
its own: a second phone is shown as observing, and pressing take-over is a real take-over, not a
queue position.

The role check has exactly one hole, and it is on purpose: **reading is always allowed**. State and
health are broadcast to every session rather than requested, so an observer sees the same 20 Hz
stream the driver does; `policies` is the one command whose reply is served *before* the role check,
because a second tab with an empty policy bar is useless rather than safe. Writes are one branch
later, and everything else lands there.

## 5. The policy bar

The bar lists what `robot.policies` reports, filtered to the slots this robot actually has, and
each press is a `robot.do`. What it may not do is imply that these are equivalent modes.

`robot.loadPolicy` writes configuration and persists. `robot.do` runs a skill for a window and then
stops. The bar is the second one, so:

| slot | what a press does | afterwards |
|---|---|---|
| `walk` | nothing is sent | the robot is already there |
| `sitstand` | `robot.do sit_toggle` | **latched** — it stays seated until pressed again |
| `ground_pick` | `robot.do ground_pick` | ~2.8 s, then the cascade falls back to `walk` |
| `kick_left` / `kick_right` | `robot.do kick_left` | 0.5 s, then `walk` |
| `roulade` | `robot.do roulade` | 1.0 s, and `chain = true` — a second press extends it |

Two of those names are not in the `skill` table at all. `ground_pick` and `sit_toggle` are driven by
their own arm of the cascade; `do_names()` in `robotd` adds them ahead of the configured skills
precisely because a client validating against `skills` alone would reject two of the five names the
pad ships bound to. The bar reads `robot.policies` for the same reason: it is what `robot.do` will
accept, and a slot with no file behind it is shown as unavailable rather than offered and refused.

**The gate.** The directional stick is only live while `robot.state.policy` is `walk`. Everything
else — a skill window, `homing`, `held`, `limp_fall` — means something other than the walk network
is driving, and a twist sent then is at best ignored. The four action buttons stay live throughout:
repeating a press is how a person says "again", and the latch is how they say "sit".

`dur` in `duckphone/server.py` is display only. The bridge times nothing; `robotd` does.

## 6. Two things a browser does not do on this hardware

**`dvh` is not available.** The phone this was built against reports `100vh` as the *large*
viewport — address bar hidden — so `height: 100dvh` collapses to a page whose bottom is off screen.
The fix is three layers: `100vh`, then `100svh` where it parses, then a `--app-h` written from
`innerHeight`/`visualViewport.height` on resize. The stick diameter is derived the same way, from
the short side, so a small window shrinks the stick instead of scrolling the page.

**The service worker is versioned by hand.** `static/sw.js` carries a `VERSION` constant and the
cache name embeds it. Bumping it is how a changed `app.js` reaches a phone that has already
installed the page — an unversioned cache would keep serving the old bundle indefinitely, which
looks exactly like a server bug.

## 7. What it is not

- **Not authenticated by default.** `--auth` turns on a six-digit code from `/etc/duckphone/token`,
  five failures and a sixty-second lock. It is off because the page asking for a code it cannot
  explain is worse than the LAN being trusted; turn it on when the LAN is not yours. `/stop` never
  asks for a code: the one command that must not fail is the one that stops the robot.
- **Not encrypted, and not for the public internet.** No TLS, no port forwarding. Outside the LAN,
  `remote-access-design.md` is the answer.
- **Not a gamepad.** `microduck-webpad` is the path for a physical pad; this one is a touchscreen,
  and the two are not meant to converge.
- **Not shipped in the release artifact.** `install.sh` puts it in `/opt/duckphone` and installs the
  unit; uninstalling is `systemctl disable --now duckphone`, and `/opt/duckphone` and
  `/etc/duckphone` are then yours to delete. Nothing else on the board refers to it.

## 8. Where it lives

| | |
|---|---|
| `duckphone/server.py` | HTTP, the WebSocket, sessions, roles, watchdogs, the command table |
| `duckphone/rpc.py` | the `robotd` client: subscribe, request, reconnect |
| `duckphone/ws.py` | RFC 6455 framing |
| `duckphone/static/` | the page, its service worker, icons, the troubleshooting page |
| `duckphone/systemd/duckphone.service` | `User=duck`, `Restart=always`, `After=` not `Requires=` |
| `duckphone/install.sh` | sync, install the unit, restart, print the address |
| `duckphone/verification/` | frame codec, watchdog and end-to-end protocol tests against a fake `robotd` |
| `duckphone/design/prototype.html` | the mock, no robot, served at `/design/prototype.html` |

`After=robotd.service`, not `Requires=`: the bridge starting before `robotd` and reporting
"not connected" is the correct behaviour when someone restarts `robotd` mid-session, and a
`Requires=` there would turn a routine daemon restart into a phone that has to be reloaded.

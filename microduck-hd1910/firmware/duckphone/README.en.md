[简体中文](README.md) | **English**

# 📱 duckphone — driving the duck from a phone on the LAN

Same Wi-Fi, then `http://<board-ip>:8001/` in the browser and you are driving. No app to install, no
Bluetooth pairing, no cable. One portrait page: the policy bar at the top, the stick in the middle,
four action buttons 2×2 below.

No external dependencies: the board needs nothing but `python3` and its standard library, and the
page needs no CDN, no `pip` and no internet.

The reasoning — what it is allowed to decide and what it is not — is in
[`docs/design/lan-phone-remote.md`](../docs/design/lan-phone-remote.md).

## Why it exists

There are already two ways to drive a duck here, and each costs something up front:

| you want | you use | it costs |
| --- | --- | --- |
| the owner's phone, off the LAN, with video | the app — [`docs/design/mobile-app.md`](../docs/design/mobile-app.md) | installing it and signing in |
| a gamepad on a laptop | `microduck-webpad` + `padd` | owning a gamepad |
| **any phone already on the same wifi** | **this** | being on the wifi |

`duckphone` is an **ordinary socket client**, in the same authority class as `padd` and `console`: it
opens no device, asks for no root, and makes no decision `robotd` would not make for any other client.

## What it does

| | |
| --- | --- |
| Drive | virtual stick, `vx ∈ [-0.25, 0.35]`, `vyaw ∈ [-0.8, 0.8]` — narrower than the training envelope |
| Policy bar | lists the policies installed on this robot; one press runs one; `walk` is the resting state, everything else falls back to it |
| Take over / hand back | one driver at a time, a second device is read-only; `policies` is served to read-only too |
| Relax | long-press for 1.5 s, one step, no confirmation dialog |
| Status page | link, policy, control loop, power, both temperatures, input source |
| Alert detail | fallen/tilted, temperature, battery, control-loop drops, `padd` conflict — each with what to do |
| Maintenance | reboot motors, input source, versions, troubleshooting commands |

## Install

```bash
# from a laptop
./install.sh duck@<board-ip>

# on the board itself (already the duck user)
./install.sh
```

`install.sh` does three things: sync to `/opt/duckphone`, install `systemd/duckphone.service`, restart
and print the address. It does not touch `robotd`'s configuration or the firmware. To remove it:

```bash
sudo systemctl disable --now duckphone
sudo rm -rf /opt/duckphone /etc/duckphone
```

Run it by hand instead, without a unit:

```bash
python3 server.py --static ./static
```

| flag | default | |
| --- | --- | --- |
| `--port` | `8001` | |
| `--robot-socket` | `/run/robotd.sock` | `robotd`'s unix socket |
| `--token-file` | `/etc/duckphone/token` | read only under `--auth` |
| `--auth` | off | six-digit pairing code; **off by default**, and the page does not ask for one |
| `--no-padd-control` | off | the page cannot stop `padd` with one tap, only copy the command |
| `--subscribe-hz` | `20` | state stream rate |

## First use

1. Put the phone on the same wifi as the board.
2. Open `http://<board-ip>:8001/`.
3. If the bar says read-only, press **take over**; the driver's bar says connected.
4. Long-press **relax** at any time to let the joints go.

The stick is live only while `robot.state.policy == walk`. Any other value means some other network
is driving and a twist sent then would be ignored anyway.

## Tests

```bash
python3 -m unittest discover -s verification
```

No robot needed: `verification/helpers.py` is a fake `robotd` speaking the same JSON-RPC on a unix
socket, covering frame codec, watchdogs, the role gate, the policy bar and the end-to-end protocol.

## Boundaries

- Listens on the LAN only. **No TLS — do not port-forward it.** For outside access see
  [`docs/design/remote-access-design.md`](../docs/design/remote-access-design.md).
- The pairing code is **off by default**. When on it is six digits, five failures and a sixty-second
  lock, stored in `/etc/duckphone/token` (`0600`).
- `/stop` never asks for the code. The one command that must not fail is the one that stops the robot.
- Four watchdogs: the page stops refreshing the stick for 250 ms and the bridge commands zero; a
  session silent for 5 s is dropped; `robotd`'s own deadman is 500 ms; health is relayed at 1 Hz. The
  bridge **never** re-sends the last non-zero sample on a timer — a repeated command is
  indistinguishable from a held finger, which is the failure the deadman exists to catch.
- The unit **deliberately omits** `NoNewPrivileges=yes`, because the one-tap interlock runs
  `sudo -n systemctl stop padd`. Start with `--no-padd-control` and the hardening is free; the page
  then copies the command instead of running it.

## Known limits

- Portrait only. `manifest.webmanifest` declares `orientation: portrait`; there is no landscape layout.
- The service worker's cache is versioned by hand — `VERSION` in `static/sw.js`. Bump it with any
  change to `app.js`, or a phone that already installed the page keeps the old bundle forever and it
  looks like a server bug.
- Not part of the release artifact. `install.sh` puts it in `/opt/duckphone`; nothing else on the
  board refers to it.

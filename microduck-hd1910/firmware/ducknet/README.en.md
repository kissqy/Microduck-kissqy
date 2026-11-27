[简体中文](README.md) | **English**

# 🦆 ducknet · BLE provisioning, from a Linux desktop

When a robot is freshly assembled, or has moved somewhere its saved Wi-Fi does not reach, **Bluetooth
is the only way in**: with no network there is no ssh and no web console. `ducknet` is a Linux desktop
app that connects over BLE, takes the PIN, and changes the robot's network settings.

| What it does | |
| --- | --- |
| See the network | SSID, signal, IPv4/IPv6, MAC, interface, and where the address came from (DHCP / pinned) |
| Join a network | Scan, pick one, type the passphrase **once** — later connections reuse it |
| Pin an address | Give a network a fixed IPv4; it goes into the robot's NetworkManager profile and survives a reboot |
| Forget | Delete a saved profile on the robot (the locally remembered passphrase goes with it) |
| Also | Rename the robot, read a daemon's journal, reboot, send an arbitrary allowed method |
| Not | Motion, firmware updates, changing the PIN (the firmware refuses that over BLE) |

It is a client of the `btd` GATT JSON-RPC — the same privilege level as `robotctl`, `duckctl` and the
official phone app. The protocol and the reasoning live in
[`docs/design/ble-provisioning-app.md`](../docs/design/ble-provisioning-app.md); the `btd`/`configd`
side belongs to [`docs/design/app-path-design.md`](../docs/design/app-path-design.md).

## A robot that is not advertising cannot be found

An empty scan is almost always the board's fault, not the client's: with no `btd` nothing advertises
the GATT service, and `net.*` needs `configd`, whose Wi-Fi backend is NetworkManager.

```bash
sudo systemctl is-active btd configd NetworkManager     # all three must say active
```

The script beside this README fills the gap (dry-run unless `--apply`):

```bash
./deploy_ble_provisioning.sh duck@<board-ip>             # show the plan
./deploy_ble_provisioning.sh duck@<board-ip> --apply     # cross-compile and install btd + configd + robotctl
./deploy_ble_provisioning.sh duck@<board-ip> --apply --migrate-network   # hand wlan0 to NM (can drop the link)
```

> The board's `configd` has to be **built from this repository**: it adds the `ipv4` argument to
> `net.connect`, which is what pinned addresses use. Upstream 0.15.1 rejects the whole request with
> `unknown field ipv4`; `ducknet` recognises that, falls back to DHCP once and says so, rather than
> leaving you to think you mistyped the passphrase.

## Install

```bash
./install.sh              # venv + launcher + desktop entry, under ~/.local
./install.sh --uninstall  # remove them, keep the source
```

Or run it in place: `./app.py --demo` (in-process fake robot, no Bluetooth, no bleak) /
`./app.py` (real).

Requirements: Python ≥ 3.10, `python3-tk`, a running BlueZ, and D-Bus access for your user (a desktop
session is enough; otherwise add yourself to the `bluetooth` group).

## Using it

Left column: robot and connection. Right: four tabs. The log is always at the bottom.

1. **Connect** — launch, wait for the 8-second scan, pick the robot, type the PIN (factory `000000`).
2. **Status** — state, SSID, interface·MAC, addresses, where the address came from; signal and the
   **console address** `http://<ip>:8001`, which opens in your browser when clicked.
3. **Wi-Fi** — scan, pick, connect (double-click also works). A WPA2/WPA3 passphrase is asked for
   **once**; after that the remembered one is reused, and only a `bad_key` answer asks again. The
   **fixed IP** card pins IP/mask/gateway/DNS for the selected network (mask may be written
   `255.255.255.0` or `24`), applied on the next connection and stored in the NM profile. `WEP` and
   802.1X are labelled unsupported without a request being sent.
4. **Robot** — rename, read a daemon's journal, reboot (confirmed, and it says joints go limp).
5. **Diagnostics** — send any method BLE allows, with JSON parameters.

`psk` and `pin` are always shown as `<hidden>`; they never reach the log.

### What is remembered locally

`~/.config/ducknet/profiles.json` (0600, directory 0700; follows `$XDG_CONFIG_HOME`). Passphrases are
keyed by SSID, pinned addresses by **robot serial + SSID**. It is **plain text**, the same order of
secrecy as `~/.netrc`; to move it to a keyring, replace `profiles.Store.password()` and
`set_password()`. A corrupt file is moved aside as `profiles.json.broken` instead of stopping the app.

## Verification

```bash
python3 -m unittest discover -s tests          # 51 cases: framing, auth, net.*, ipv4, local store
DISPLAY=:0 python3 tests/manual_gui_check.py   # the GUI through the real branch (fake radio), 22 checks

./acceptance.py --demo
./acceptance.py --scan-time 8                  # real robot, read-only
./acceptance.py --join 'SSID' --psk '…' --static-ip 192.168.110.240/23 --gateway 192.168.110.1
```

`--static-ip` writes the robot's configuration: pick an address you can keep, or the next boot is
unreachable over ssh.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| Empty scan | is `btd` running (above)? is the robot already connected to another central? move closer |
| "上一条蓝牙操作还没结束" / InProgress | another client holds the robot; the app names it. `bluetoothctl disconnect <mac>` and retry |
| Scanned, will not connect (HCI `0x3E`) | radio jitter (Wi-Fi and BT share the antenna); the client retries eight times |
| `net.status` fails with an NM D-Bus error | no NetworkManager on the board — see above |
| Pinned address, then `net.connect` times out | a known NM 1.52 abort when a profile is replaced while the old activation is still tearing down; this repo's `configd` waits for `DISCONNECTED` first |
| Forgot the pinned address | the robot does not read it back; see `profiles.json`, or `nmcli connection show <SSID>` |
| Second window | single-instance lock: two windows would fight over one BLE central |

Tk runs the interface; every BLE and JSON-RPC call runs on an asyncio loop in a worker thread, and
results come back through `queue.Queue` + `root.after(50)`.

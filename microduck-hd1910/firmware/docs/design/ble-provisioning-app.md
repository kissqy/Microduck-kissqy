# The desktop app — a laptop, Bluetooth, and a robot with no network

Status: built · Date: 2026-11-22 · Owner: kissqy

`ducknet/` is a Linux desktop client for the BLE provisioning path that
[`app-path-design.md`](app-path-design.md) owns: it connects, takes the PIN, and reads or changes the
robot's network. This page is the client's half — what it sends, what it deliberately keeps on the
laptop, and the two places where NetworkManager's own contract is not what it looks like.

The code is [`ducknet/`](../../ducknet/); the usage is its [README](../../ducknet/README.md).

## 1. Where it sits

```text
  ducknet (laptop)  ──BLE GATT──▸  btd  ──unix socket──▸  configd  ──D-Bus──▸  NetworkManager
        │                            │                        │
        │  NDJSON JSON-RPC           │  routes the subset      │  owns the credentials
        └────────────────────────────┴────────────────────────┴─▸ the robot's journal
```

Same privilege level as `padd`, `console`, `duckctl` and the phone app: a client of an API that
already exists. It opens no device, needs no root on the robot, and decides nothing about motion. The
only thing special about it is *where it runs*: a laptop is the device somebody has when the robot has
never been on a network, which is the situation the whole BLE path exists for.

## 2. The contract it uses · **measured**

Everything here is read from `duck-ble/`, `btd/` and `duckctl/`, then exercised against a board.

| | |
| --- | --- |
| Service | `6f5d2a10-3b47-4c8e-9a1f-2d7e8c4b6019` |
| RPC characteristic | `6f5d2a11-3b47-4c8e-9a1f-2d7e8c4b6019` |
| Framing | NDJSON, one request per line, both ways |
| Chunking | write `MTU-3` bytes, floor 20, single value at most 512 |
| Read | returns the API version *and* is the step that triggers pairing |
| Auth | just-works pairing, then `system.authenticate{pin}`; three attempts |
| Advertisement | manufacturer data company id `0xFFFF` = 4-byte IPv4; extended advertisements add `0x01` |

Methods and budgets: `net.status` 15 s, `net.scan` 60 s, `net.connect` 60 s, `net.forget` 15 s,
`system.info` / `setName` / `reboot` 15 s, `system.logs` 60 s.

Two client-side rules that came out of the board rather than the source:

- **`BleakScanner.find_device_by_filter` is a class method** that scans on its own. Wrapping it in
  `async with BleakScanner(...)` runs two discoveries at once, and BlueZ answers every one of them
  with `org.bluez.Error.InProgress`. The first symptom is "上一条蓝牙操作还没结束", which reads like a
  bug in this app and is a bug in how the app called the library.
- **A robot serves one central.** Before connecting, the app asks BlueZ's `GetManagedObjects` for a
  device with the robot's name or service UUID and reports `Connected: yes` as "another client holds
  it". Looking that up by address misses, because the robot's two advertisements (public and random)
  do not share one.

## 3. `net.connect` grew a fixed address

Upstream 0.15.1's `net.connect` is `{ssid, psk?}` and `configd` always asks NetworkManager for a DHCP
lease. A robot that must be *found* at a known address — a fleet, a port forward, a bookmarked console
URL — had no way to say so, so this repository adds one optional field to both sides:

```json
{"ssid": "大树下", "psk": "…",
 "ipv4": {"address": "192.168.110.240", "prefix": 23,
          "gateway": "192.168.110.1", "dns": ["192.168.110.1"]}}
```

- `duck-ipc-proto`: `NetConnectParams.ipv4: Option<Ipv4Config>`, `skip_serializing_if`, so a request
  without it is byte-for-byte what upstream sent.
- `configd/src/nm.rs`: turns it into the NM `ipv4` setting (`method=manual`, `address-data`,
  `gateway`, `dns`), and **validates it before the profile is written**. A typo that NM stores
  survives the reboot, and after that reboot BLE is the only way back in.
- The reply's `ip4` is the pinned address, which is how the client tells "applied" from "DHCP answered
  something".
- `robotctl net connect <ssid> --ipv4 … --prefix … --gateway … --dns …` is the same thing from a
  shell, which is what support has when the app is not the tool at hand.

### 3.1 Three ways this went wrong · **measured**

1. **`address-data` is `aa{sv}`, not `aau`.** Each entry is `{address: s, prefix: u}`. Send the older
   `aau` shape and NM does not reject *that property*: it fails to parse the whole settings
   dictionary, `802-11-wireless` included, and the device answers
   `A 'wireless' setting is required if no AP path was given`. That reads like a bug in the wifi half
   and is in the ipv4 half. Found on a board, after the profile it replaced had already been deleted.
2. **`ipv4.dns` is native-endian.** NM stores the address bytes in a `guint32` and prints them through
   `nm_inet4_ntop`, so the value has to have those bytes in memory. Sending `0xC0A86E01` for
   `192.168.110.1` lands in the profile as `1.110.168.192`.
3. **NetworkManager 1.52 aborts on its own.** Deleting the profile in use and immediately starting a
   new activation hits `nm-l3cfg.c:459` (`_l3_acd_defend_type_to_nacd`'s default assertion) while the
   old activation is still tearing down; NM is killed by its own `nm_assert`, systemd restarts it, and
   the client sees nothing but a 45-second timeout. `configd` now waits for the device to reach
   `DISCONNECTED` (bounded at 10 s) before activating. Five consecutive re-provisionings afterwards:
   `NRestarts 1 → 1`, `ipv4.method=manual`, `valid_lft forever`.

## 4. Two things the robot cannot be asked, so the laptop remembers them

`net.scan` reports a `saved` boolean and nothing else, and `net.connect` refuses a secured network
without a passphrase — the robot's own copy is not reused when the field is absent. So "connect to the
network I configured yesterday" cannot be done from the robot's answer alone: **the client has to keep
the passphrase**, or ask for it every time.

The pinned address has the same shape of problem: `net.connect` writes it and never reads it back.

`profiles.py` keeps both in `~/.config/ducknet/profiles.json` (0600, directory 0700, written to a
temporary file and renamed so there is no half-written state to read):

```json
{"version": 1,
 "passwords": {"大树下": "…"},
 "static": {"f0d0c3d72c1c40be": {"大树下": {"address": "192.168.110.240", "prefix": 23,
                                            "gateway": "192.168.110.1", "dns": ["192.168.110.1"]}}}}
```

- Passphrases are keyed by **SSID** — the same key works on another robot on the same network.
  Addresses are keyed by **robot serial + SSID**, because two robots on one subnet holding one address
  is the hardest failure here to diagnose.
- Plain text, the same order of secrecy as `~/.netrc`. What can read it is one local user, who can
  also read NetworkManager's root-only keyfiles and the system keyring. Moving it to a keyring means
  replacing `Store.password()` / `set_password()` and nothing else.
- `forget` on the robot drops the local copy too: a passphrase the robot no longer accepts must not be
  replayed by the next click.
- Only `bad_key` asks again, and it asks once. `not_found` and `timeout` are not password problems, and
  re-prompting on them teaches people to retype a key that was already right.

## 5. Concurrency

Tk owns the main thread; every BLE and JSON-RPC call runs on an asyncio loop in a worker thread, and
results come back through `queue.Queue` + `root.after(50)`. A single-instance lock exists for a reason
that is not cosmetic: two windows are two BLE centrals, and the robot serves one — the second window
would spend its life collecting `InProgress`.

The client also refuses to scan with a service filter, and stops discovery before connecting, both for
reasons `app-path-design.md` §3.3 and §3.8 already measured.

## 6. What has actually run · **measured**

On `duck-dillon` (radxa-zero3, NetworkManager 1.52.1, Armbian Trixie):

```text
$ acceptance.py --scan-time 8 --join '大树下' --psk '…' \
      --static-ip 192.168.110.240/23 --gateway 192.168.110.1 --dns 192.168.110.1
通过 13 / 13，失败 0
```

plus, in the same session: `nmcli -g ipv4.method,ipv4.addresses,ipv4.gateway,ipv4.dns` →
`manual / 192.168.110.240/23 / 192.168.110.1 / 192.168.110.1`, `ip -4 addr` showing
`valid_lft forever`, and five pin/unpin cycles with no NM restart. The GUI's real branch (fake radio)
passes 22 checks including the clickable console address and a pinned join, and the unit suite is 51
cases.

## 7. Costs accepted

- The robot needs a `configd` from this repository for pinned addresses. An upstream one answers
  `unknown field ipv4`; the client detects that, connects over DHCP once and says so. It is a
  degradation, not a failure, but it is a version dependency the README has to keep saying.
- The passphrase is on disk in plain text. Documented, permissions-tightened, and one method away from
  a keyring.
- The link itself still carries no encryption over a peer that never paired — that is
  `app-path-design.md` §5.5, and it is not this client's to fix.
- One robot, one central. Provisioning while somebody else is connected is refused with an
  explanation rather than queued.

## 8. Next

- A "forget the pinned address" path that does not require re-provisioning would mean a method on the
  robot; today the way back to DHCP is one more `net.connect` without `ipv4` (which is what the app's
  「清除」 leaves for the next connect).
- `net.connect` still cannot join a hidden SSID, so a pinned robot that also hides its network would
  have to be migrated by hand. Out of scope until the API has a shape for it.

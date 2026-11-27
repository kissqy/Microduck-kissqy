[简体中文](README.md) | **English**

# Verification

No robot needed. `helpers.py` holds a scriptable fake `robotd` — the same newline-delimited JSON-RPC
on a temporary unix socket — and a minimal WebSocket client, so these cases run through the same code
path the phone uses, minus the phone.

From this directory:

```bash
python3 -m unittest discover -s verification
```

| file | covers |
| --- | --- |
| `test_ws_frames.py` | RFC 6455 framing: masking, fragmentation, length boundaries, control frames. The board has no `websockets` package, so this is hand-written and therefore tested on its own |
| `test_watchdog.py` | the first two of the four watchdogs: the stick going stale after 250 ms, and a session dropped after 5 s of silence |
| `test_protocol.py` | end to end: a real HTTP server, a real WebSocket, a fake daemon. The role gate (second device read-only, take over, hand back), the `relax` confirmation, the `/stop` beacon, the policy bar's pure functions and `policyDo`, and a read-only session still being able to read `policies` |

The cases in `test_protocol.py` are not filler — each one is a fault that happened on a real board:

- **a read-only session could not see the policies** — the role check ran before the read, so a second
  device's policy bar was permanently empty.
- **a `padd` conflict was invisible** — with the gamepad service running, phone commands were silently
  overridden and the page looked stuck.
- **relax had no confirmation** — one mistap laid a standing robot down.

## What these do not prove

- Nothing about motion on a real robot. The stick envelope, skills returning to `walk`, whether
  `init`/`enable` are accepted — that is `robotd`'s business; these assert only what the bridge sends.
- Nothing about a browser. The `dvh` fallback, the stick diameter and the service-worker version bump
  all have to be seen on the phone.

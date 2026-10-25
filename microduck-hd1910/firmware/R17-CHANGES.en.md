[简体中文](R17-CHANGES.zh-CN.md) | **English** | [Русский](R17-CHANGES.ru.md)

# R17 modification history

**R17 v1.0.143:** reuses native diagnostic JSON and state snapshots to avoid re-encoding parsed telemetry in the ZERO collector, and prevents clients or rejected startup processes from overwriting daemon identity. Control / telemetry frequency, UI, recording format, models, and parameters remain v142. See [diagnostic / state ownership](docs/design/r17-settings-design.en.md), [SSH telemetry forwarding](docs/design/r17-connection-design.en.md), and [startup ownership](docs/design/robotd-design.en.md); verification and environment limits are in `verification/`. New physical CPU usage or temperature reduction was not measured.

**R17 v1.0.129:** console policy tuning retains only action scale. Head / leg filtering and voltage compensation return to native defaults; R17 assignments and compensation-repair completion markers are removed. See [upstream differences](OFFICIAL-CHANGES.en.md) and [parameter provenance](docs/design/r17-settings-design.en.md). Entries below are historical.

**R17 v1.0.124:** default / saved-value sources are unified. Action scale 0.70, head / leg filters 0.50/0.70, preserving local settings. See [settings design](docs/design/r17-settings-design.en.md).

**R17 v1.0.123:** official `policy.action_scale` default becomes 0.70; head 0.50 and legs 0.70 remain. Upgrades change values retaining the old 0.90 default to 0.70 while preserving other saved multipliers. Manually selecting 0.90 after installation still saves it.

Defaults come from firmware `robotd-profile.toml`; the console reads saved configuration and runtime readback. Without data it shows waiting, rather than supplying a page-side multiplier.

## R17 v1.0.96 differences from official 0.15.1

Upstream: `pollen-robotics/microduck`, commit `1fa84386f07884e27866411bc1ba166977bced95`. This version carries over the v1.0.95 console and hardware adaptation, rather than another conversation's console or HAT protocol.

### Complete file-level changes to upstream code

1. `robotd/src/main.rs`: original R17 Feetech backend, commissioning, FT6 diagnostics, and UART initialization; self-trained contracts and runtime model hash / scale readback; no upstream-model fallback in `custom_only`. Official HOME, start / stop, policy selection, fall detection, sit / stand timing, and voltage compensation remain.
2. `robotd/src/control.rs`: interprets exact HOME, training scale, command filling, and EMA from contracts; actual-scale / model-identity readback. Final actions still use official global scale and head / leg low-pass. No old stationary multiplier or start / stop ramp.
3. `robotd/Cargo.toml`: TOML parsing required by R17 hardware configuration.
4. `duck-control/src/lib.rs`: exports R17 Feetech, hardware, HD1910, and deployment modules.
5. `duck-control/src/io.rs`: diagnostics and hold-position interface for R17's single bus owner.
6. `duck-control/src/model.rs`: exact HOME and joint mapping from self-trained contracts.
7. `duck-control/src/policy.rs`: validates export contracts, observations / outputs, and P; loads disk models, computes actual weight identity, and provides curriculum ranges. Official asynchronous switching and feedforward / recurrent loading remain.
8. `duck-control/src/obs.rs`: zero-fills body commands when the contract explicitly requires it; retains the official 61-dimensional layout and previous raw-action feedback order.
9. `duck-control/src/safety.rs`: exposes Feetech state and held positions in R17 diagnostics, retaining one motor writer without a new fall-recovery policy.
10. `duck-ipc-proto/src/lib.rs`: continues R17 bus / calibration diagnostics on official 0.15.1 types; does not rewrite HAT FT6 packets.
11. `robotd-params/src/lib.rs`: Feetech bus / calibration and `custom_only` parameters.
12. `robotd-params/src/registry.rs`: registers those three parameters.
13. `docs/design/robotd-design.md`: documents contract action conversion versus official global processing; documentation only.

### Added or retained R17 code

- `duck-control/src/feetech.rs`: original R17 servo packets, address 42/six-byte targets, speed 0, acceleration register, and FT6 read / write. New RobotIo adaptation only declares unsupported reboot and `measures_load=false`; formatting does not change packets.
- `duck-control/src/{hardware,hd1910,deployment}.rs`: HD1910 coordinates, assembly calibration, hardware access, and strict deployment contracts.
- `robotd/src/feetech_*`, `process_safety.rs`, `service_client.rs`, `selftrained_profile.rs`: original hardware management / diagnostics aligned to 0.15.1 types and self-trained joint tasks.
- `packaging`: R17 installation, config restoration, model management, ONNX Runtime 1.28.0, and official padd / robotctl / sounds installation.
- `packaging/webpad.py`, `microduck-webpad.service`: web Xbox evdev bridge writing standard events only. It reads official `pad.input` to confirm attachment; it does not write actions to that interface. Physical-controller arrival or web-lease timeout destroys the virtual device.
- `console`: original page becomes three columns, “Live Duck / Simulated Gamepad / Camera.” File / CLI cards and generic remote-file / terminal APIs are removed; only internal model / install-package staging remains. Original diagnostics, calibration, curves, and replay continue. Camera retains WebRTC reception with one-session protection against duplicate upstream producer listings; signaling defaults to 8443.

### Official behavior boundaries for this historical version

- `padd/src/main.rs` and `tap.rs` are byte-identical to official 0.15.1; no custom button policy.
- 0.9/0.5/0.7 are official processing-chain configuration values, with the original low-pass algorithm. Switching models does not replace globals based on a ZIP's passthrough suggestions.
- Sit / stand retains the official fixed scale 1 exception. Official voltage compensation defaults on; 0.9 is walking base scale, not every frame's final multiplier.
- This delivery supplies only joint walk and sitstand. stand, ground_pick, kick_left, kick_right, and roulade are none; missing web actions are disabled and corresponding `[pad]` skills unbound.
- R17 `battery_empty_shutdown=false` remains under operator power control; `limp_fall=false` matches upstream. No additional stationary policy, falling action, or autonomous walking.
- `custom_only` rejects bad models without the normal upstream fallback. This explicitly implements use of the project's own models only.
- System updater service is not reinstalled. Only required robotd / padd clients and tools / libraries are updated. HAT / IMU is not flashed in this step.

### Verification and limits

- robotd: 185 passed, one upstream default-ignore; includes real ONNX40-frame reference and five scale / filter / identity checks.
- duck-control: 117 passed; eight upstream recurrent-network checks separately all passed.
- robotd-params: 96 passed; padd: 23 passed; robotctl: 197 passed, five default-ignore.
- Python: 40 passed covering calibration preservation, scale persistence, HOME feedback, Xbox detection, physical takeover, 600 ms input loss, first-Start buffering, and input revocation.
- Browser: 426×620 desktop columns, Start press / release, and physical takeover passed. UI used a simulated backend; action checks disabled software WebGL. Camera followed official 0.15.1 duplicate-producer protection; reconnection passed.
- Environment prohibited AF_UNIX calls: ten robotd single-instance integration checks and two robotctl Unix-socket checks could not pass. Original tests and service locks were retained.
- No physical-robot test in this record. Static / inference checks do not establish actual assembled walking, servo dynamics, or final HOME arrival.

[简体中文](r17-settings-design.md) | **English** | [Русский](r17-settings-design.ru.md)

# R17 console parameter provenance

This page owns defaults, storage, bundled models, and upgrade migration. Its current rules describe v1.0.155/control.34, retaining v154's parameter / model rules. Later sections record behavior at the time. Current V164 usage is in [the console guide](../../console/USER-GUIDE.en.md).

## v1.0.154 retirement of servo overrides

The only adjustable global policy parameter is official `policy.action_scale`: default 0.70, range 0.10–1.00, step 0.01. `config/r17-management.json` defines `defaults.policy`; release generation copies it into console / service packages. User values persist in ZERO's `robotd.toml` and `robotd.saved.toml`. Joint Walk uses a separate SHA-bound execution profile; the UI distinguishes global saved values from actual active-model values.

Advanced parameters submit only action scale, no P50/D51/address 48 torque limit. `defaults.servo`, the test module, and production calls are removed; upgrades delete `/etc/robot/feetech-ft5/servo-test-parameters.json` and old modules. Contract P applies to all 15 servos. Addresses 48/51 retain device values, with no explicit write or fabricated zero restoration. [robotd design](robotd-design.en.md#r17-hd1910-contract-p-control33) owns torque-enable / restore packets. v131–153 override instructions are retired.

Draft defaults are not reported as actual values. Saved / runtime values remain separate; unknown values show waiting or real errors. Configuration reads reuse maintenance requests without new SSH timers / pollers.

## v1.0.155 saved direction display

All 15 feedback rows, including the separate beak, show direction from saved local calibration, not model / geometry / defaults. +1 is “正向 +1” (forward);−1 “反向 −1” (reverse). Increasing encoder counts respectively increases / decreases joint angle.

`console/static/joint-direction.js` finds a unique calibration entry by ID and validates name, calibrated flag, and direction. Unready, disconnected / paused, missing / duplicate IDs, name mismatch, or invalid values show “—”. Older recordings with row metadata are supported, but fallback cannot replace missing / corrupt entries in a current snapshot.

This renders saved state only; it does not write calibration or change conversion, targets, limits, or raw feedback. Existing telemetry / metadata are reused. Waiting / reconnection is owned by [connection design](r17-connection-design.en.md#initial-feedback-and-reconnection-v10155); HOME fixes by [robotd](robotd-design.en.md#r17-explicit-policy-off-returns-home-control34).

## Five bundled models and right-kick migration

| Slot | Model ID | Base scale | Head / leg coefficients |
| --- | --- | ---: | --- |
| Walk / hold / joint recovery |`1cbf8730eadd75a5704332c9f3c10f60`|1.00|0.50/0.70|
| Sit / stand |`1c94934c6421ec72ed48079cea749668`|1.00|Original sit / stand path|
| Ground pick |`b14e3a8b56ddbb8d2d831e727774a168`|1.00|1.00/1.00|
| Forward roll |`59e15d7b04d0c40e9b11b8a70bdecae6`|1.00|1.00/1.00|
| Right-foot kick |`67ad09d82f4865d222a7ae06f250cf9f`|1.00|1.00/1.00|

Right kick is original `Mjlab-BallKick-Flat-MicroDuck`, 10000 iterations/4096 environments, ONNX SHA256 `67ad09d82f4865d222a7ae06f250cf9f77f08c27e4f019ee3f7e431a764419fd`. ONNX, manifest, contract, and training metadata remain byte-identical. Checkpoint stays only in the original archive; runtime never reads / deserializes it. Existing `kick_right`/named skill uses 0.5 seconds, `[0,0,0]`, one shot, no return phase. Existing voltage compensation still affects actual scaling; base 1 does not mean final 1 at every voltage.

`requested_action_replacements` adds right kick. Configuration generation compares the previous profile; initial migration binds the original and sets skill scale 1. Reinstalling the same profile preserves later valid skill settings. Roll / pick migrations only change paths / base scale when the bundled model changes; global parameters, local calibration, and other actions remain.

Default buttons: LB=`kick_left`, RB=`kick_right`. At this v154/155 baseline left kick is `none`, so LB does nothing. `retire_standalone_recovery` removes `stand_test`, keeps Stand=`none`, changes only old LB=`stand_test` to left kick and old empty / missing RB to right kick; other custom mappings remain. Teacher `a481d9f211f31d9476ab1a319fe362a2` is excluded from runtime; source assets are regression fixtures and existing device directories need not be forcibly deleted.

Joint Walk includes its own recovery. Catalog lists five bundled models, removing `manual_recovery`/separate recovery display; binding and actual native runtime remain distinct. The right-kick button reuses `robot.do`, requesting once only with fresh feedback, movement mode, IMU, HOME, policy, and actual torque readiness. It does not automatically torque-enable / HOME / enable a policy or replay failed requests.

## Joint Walk execution profile

The single Walk is the 9600-iteration joint model. Original artifacts remain unchanged. Separate `deployment-execution.json` retains v153 scale 1.0/head 0.5/legs 0.7; original 1/1/1 remains training provenance. The profile binds the complete ONNX SHA256 and cannot apply to other models. [robotd design](robotd-design.en.md#r17-v10154-combined-walk-execution) owns loading, raw action history, and absolute output generation.

Management records profile SHA. First migration adds only this profile, atomically replacing it before writing its descriptor; repeat installation does not overwrite later valid choices. Global scale still saves but neither overwrites nor multiplies the joint profile. Catalog reads small metadata without new ONNX hashing, YAML parsing, inference, or polling. Historical v146 0.9/0.5/0.7 is not this baseline's execution value.

## Retired model import and complete-package installation

v154 removes model-import buttons, upload / API / CLI, and temporary validation. Startup still validates every bundled contract / compatibility. Firmware ZIP import and bundled installation remain.

Complete service packages install into fixed paths. Non-model code / libraries update atomically; local calibration, volume, gamepad range, and valid settings remain. Valid models follow existing preservation; corrupt contracts recover from complete bundled directories. Explicitly retired IDs / references migrate from management definitions. Bridge / padd / webpad configuration and startup order retain the existing flow.

Integrity is checked first. The bundled label uses only verified `bundle_info().build`; missing / failed reads clear old labels and show unknown rather than hardcoded control.18. Actual runtime identity comes from native readback.

Ordinary restart restarts only robotd, without pairing or rewriting models. `Restart=no` preserves the first startup error rather than rebuilding / retrying. [robotd design](robotd-design.en.md#r17-uart-startup-recovery-control32) owns bounded UART startup / read-only diagnostics; [connection design](r17-connection-design.en.md) owns SSH / input.

## Global parameters and storage

Official `PolicyParams` in `robotd-params/src/lib.rs` owns global head / leg filters and voltage compensation. R17 definitions / templates do not own them or offer mutation. Explicit no-filter contracts select per-model passthrough; joint Walk uses its execution profile.

| Parameter | Default source | Default | Console role |
| --- | --- | --- | --- |
| Official action scale |R17 management|0.70|Adjust / save / actual readback|
| Head filter |`PolicyParams::resolved`|0.50|Fixed; actual readback|
| Leg filter |`PolicyParams::resolved`|0.70|Fixed; actual readback|
| Voltage compensation |`PolicyParams::default`|On, 7.4 V reference|Actual flag / multiplier only|
| Maximum beak opening |R17`defaults.pad`|100%|`/etc/robot/feetech-ft5/pad-settings.json`, shared web / physical|
| Gamepad head range |R17`defaults.pad`|2.5 rad|Same file; unrelated to policy filtering|
| Volume |R17`defaults.audio`|50%|Native ALSA; `alsactl store`|

Upgrades remove override fields owned by the old definition but retired by the new one, preserving later explicitly saved native settings through normal merge. Runtime / restart copies update together; omitted fields resolve natively. No periodic repair or extra restoration request.

`packaging/voice_preferences.py` solely converts percentage / ALSA. Native `PCM Playback Volume` and `Line Playback Switch` control level / mute; robotd uses `plughw:aic3104`. A setting request runs `alsactl store aic3104` into `/var/lib/alsa/asound.state`; system ALSA restores after official card initialization. Connecting asynchronously reads volume without setting it or blocking input. Original sound seed / version rules remain.

Calibration prefers current assembly data, then saved local copies. Training encoder values are provenance, not replacements for physical zeros.

## Historical recovery and servo testing

v131–153 servo overrides and v135–153 LB `stand_test` teachers are retired in v154. Historical native branches / fixtures remain in [robotd's historical section](robotd-design.en.md#r17-manual-lb-recovery-v10145). Those defaults / interfaces / bindings do not describe this baseline.

## v1.0.141 raw positions and fixed calibration targets

At the user's request, v139 modulo readings and v140 target-turn offsets were removed. Feedback decodes Feetech 15-bit sign-magnitude: `position_raw`/`position_signed_raw` retain signed native values; `position_wire_raw` retains bytes. Angles / observations use `(native-zero_raw)*direction*2π/4096`, without modulo, nearest-turn, or moving zero. The console accepts the full signed range.

Before torque enablement, fresh actual native positions are preloaded. Afterwards HOME / policy targets use `JointCalibration.target_raw` with local zeros / directions / limits, without±4096. Calibration zeros / targets remain 0–4095. The workbench linearly moves from signed position to requested positive target with signed intermediate packets; arrival compares the actual target, not equivalent-turn coordinates. Loose-servo centering is the same.

HOME pose / two-second ramp, limits, torque confirmation, P / D/48, speed / current, acceleration 41, UART timing, EEPROM, calibration, models, and input remain. Tests cover ID12−1→1500, ID22−1670→2276, and unchanged targets after restart / rearming. Recorded ID22 displacement 3946 counts≈346.8° follows explicitly requested absolute coordinates; it does not guarantee a shortest path or prove real circling eliminated.

## v1.0.142 diagnostic ownership and refresh

Control stays 50 Hz. Pre-inference HOME checks retain feedback, IMU mounting / readiness, torque tri-state, and freezing. Lightweight `FeetechControlStatus` avoids complete diagnostic copies for a boolean check, preserving `joint_holding` and timeout / missing-frame thresholds.

Complete diagnostics are generated after `safety.apply`, including actual torque confirmation / limit counters. Communication observe, bus JSON, and subscriber limp use that snapshot. Dynamic feedback / counts / errors refresh every 20 ms, with no lower publishing frequency or intervening safety writes.

Register inspections are shared immutable arrays, replaced whole after successful inspect; old snapshots retain old arrays. Dynamic torque / freeze / gain / communication fields remain live; JSON order / content remains. Loaded SHA / path / task identity is cached at model / controller creation; active identity references the active policy. Hot reload creates a new cache before carry_over of motion; HOME clears active selection but retains loaded-model list. Weights / tensors / threads / frequency / action / state transitions remain.

Tests cover fresh / lost / frozen / recovered fake-serial feedback, torque, snapshot isolation, and real-ONNX hot-reload identity with continuous actions. Connection design owns device / disconnect listeners.

## v1.0.143 diagnostic JSON and shared subscription snapshots

After safety at 50 Hz, the native Value moves directly into the full report without a second json! deep copy. Timing, dynamic fields, counts, and errors remain; diagnostics remain in control and refresh even without subscribers.

Motion `robot.busStatus` borrows immutable JSON under Arc; replacement does not prevent the current reply finishing. The next request gets new data. JSON-RPC IDs / structure, preferred commissioning typed snapshot, and missing-report errors remain. Only Response:: ok's extra deep copy is removed.

Broadcast uses `Arc<proto::RobotState>` shared across subscribers, with existing frequency / field selection, 256-frame queue, and lag behavior. State / skeleton remain generated in control only when subscribed. Console requests remain at most 20 Hz; control 50 Hz.

Production IPC tests cover caches, missing reports, typed priority, shared snapshots, notifications, and queue bounds. SSH forwarding belongs to connection design. Code reuse is not physical CPU / temperature evidence; pre-v143 disconnected-console measurements describe the old version.

## v1.0.144 raw snapshots and on-request reports

This supersedes per-cycle full JSON. Hardware, inference, and safety keep 50 Hz timing; after application, fixed-size dynamic diagnostics / state enter a shared latest snapshot. HOME uses existing lightweight status; limp comes from applied torque confirmation. IPC builds full JSON only on actual requests, retaining commissioning / startup responses.

Communication observe remains independent of JSON and tracks real success / failure, consecutive errors, and last failure without subscribers. Disconnect does not clear safety / model / fault state or affect control. Register / calibration / model identity is shared metadata, sent when changed rather than copied each frame.

A sender encodes the latest typed snapshot once for all raw subscribers; without consumers it sleeps, avoiding encoding / system reads. Official `robot.subscribe` retains state / skeleton behavior. Raw streams send numbers; browsers derive display / export skeletons from the same static model. Native FK / inference / safety remain.

Parameters, P / D / torque, calibration, multi-turn positions, HOME / LB, UART / HAT, and models were not changed to lower temperature. Duplicate telemetry work was removed, without a claimed physical CPU / temperature reduction. Connection design owns frames, lifetime, on-demand web input, and recordings.

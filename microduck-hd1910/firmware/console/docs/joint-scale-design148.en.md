[简体中文](joint-scale-design148.md) | **English** | [Русский](joint-scale-design148.ru.md)

# R17 console parameter provenance — v148 design record

This historical page owns adjustable defaults, storage, and readback for the v148 design. Ordinary global `policy.action_scale` defaults 0.70, range 0.10–1.00, step 0.01. Edit only `config/r17-management.json` `defaults.policy`; generation copies it to console / service. User values persist in ZERO `robotd.toml`/`robotd.saved.toml`. Joint models use separate execution settings; v148's same slider edits their base scale, default 1.00. For later rules see [current settings design](../../docs/design/r17-settings-design.en.md).

## v1.0.148 joint scale slider

For a bound joint Walk with an execution profile, the slider says “联合模型动作缩放” (Joint Model Action Scale), with “应用联合缩放” (Apply Joint Scale). Default:`defaults.joint_action_scale=1.0`; range 0.10–1.00, step 0.01. Dragging edits only a draft. Apply reuses `set-action-scale`, torque release, save, restart, and fresh HOME; P / D / torque values are saved from the same form.

The service routes by bound model: joint models update only `deployment-execution.json.action_scale`, retaining globals, filters, LB, original training data, and local calibration; ordinary models update global `policy.action_scale`. Native loading uses joint scale without multiplying the old global scale, as [robotd design](../../docs/design/robotd-design.en.md) explains. Existing native binaries are reused.

Catalog advertises `joint-action-scale` and `default_joint_action_scale`. Editing uses saved model configuration; live display uses controller readback. Success requires matching model SHA and `runtime_execution_profile`, not merely the same ONNX with an old multiplier. Old services lacking the capability disable the joint slider and request upgrade; their P / D / torque apply still submits the saved global scale.

Untouched 0.9/0.5/0.7 migrates once to 1.0/0.5/0.7 only when file SHA matches the old descriptor and all other fields match the new configuration. Custom scale / filters are preserved. Regeneration, restart, reinstall, and reimport preserve saved scale. Valid local calibration / saved copies take priority over bundled snapshots. This section governs joint editing / defaults / preservation over the historical sections below.

## v1.0.146 unique joint Walk and separate execution profile

`requested_model_replacement` makes the 9600-iteration joint `1cbf8730eadd75a5704332c9f3c10f60` the only Walk. Old 14000 teacher `9e3ff8bde021be28a728c02dbd8e7aaf` enters `retired_model_ids`; upgrades remove its directory / migrate references. Five production models are joint Walk, LB teacher, sit / stand, pick, and roll. Old teacher remains only in source `test-data/walk-teacher14000` for regression.

The user authorized whole-run 0.9/head 0.5/legs 0.7. Original ONNX / manifest / contract / training remain 1/1/1 byte for byte. Separate `deployment-execution.json` stays outside `export-data.zip`. Import validates task, full SHA, strict fields / ranges. Reimporting the same original ZIP without execution settings preserves validated matching local settings; without a profile original training parameters apply. robotd design owns loading / raw history / output.

Upgrade descriptors record profile SHA. Initial migration adds only this profile even if the existing same-model directory is retained. Atomically replace profile before descriptor, allowing interruption recovery; repeats preserve later user choices. Corrupt contracts use complete model recovery.

Global scale / filters / voltage, calibration, other bindings, LB duration, and saved P / D/48 are not reset. UI shows joint fixed parameters; global editing is disabled for that model, while P / D/48 uses the existing request with saved global value. Active scale / filter proof comes from native readback, not a disk profile. Catalog reads small JSON without extra ONNX hashing, YAML, inference, or polling. v148 supersedes these historical editing rules.

## Global parameters and storage

Official `PolicyParams` owns global filters / voltage compensation. R17 definitions / templates no longer contain or control those fields or write globals from contracts. v137 adds per-model passthrough for explicit no-filter contracts.

| Parameter | Default source | Default | Console role |
| --- | --- | --- | --- |
| Official action scale |R17 management|0.70|Adjust / save / actual readback|
| Head filter |`PolicyParams::resolved`|0.50|Fixed actual readback|
| Leg filter |`PolicyParams::resolved`|0.70|Fixed actual readback|
| Voltage compensation |`PolicyParams::default`|On; 7.4 V reference|Actual flag / multiplier|
| Beak maximum |R17`defaults.pad`|100%|Shared `/etc/robot/feetech-ft5/pad-settings.json`|
| Head range |R17`defaults.pad`|2.5 rad|Same storage; not filtering|
| Volume |R17`defaults.audio`|50%|Native ALSA, `alsactl store`|

Upgrades remove fields owned by old definitions but absent from new ones, including old R17 filter / compensation overrides, from runtime and restart copies. Omission resolves upstream defaults. No repair request / marker / timer. Later explicitly written native configuration is preserved through normal merge.

Saved scale, volume, pad range, bindings, and calibration remain. v123's 0.9→0.7 old-default migration remains. Walk contractv 2 may refresh the same ID's old contract; other imports / bindings remain. Import / binding only manages slots, not scale / filter / voltage / gains; explicit model reset retains its existing flow. UI submits user settings and displays actual readback, showing waiting for unknowns instead of defaults.

`packaging/voice_preferences.py` solely converts volume; release generation and SSH use the same module / definition. v136 uses native `PCM Playback Volume`/`Line Playback Switch`, robotd`plughw:aic3104`, removing software PCM / ALSA_CONFIG_PATH. Setting runs `alsactl store aic3104` to `/var/lib/alsa/asound.state` through limited sudo. System `alsa-restore.service`/`alsa-state.service` keep mutual-exclusion conditions and run after official `aic3104-init.service`, before robotd, preventing maximum initialization from overwriting saved volume. No sound startup hook. Old software volume converts once; sounds regenerate only when missing or seed / version changes. Connection asynchronously reads volume without setting / blocking input.

Calibration prefers current assembly, then local saved copies; training encoder values are provenance. Without temporary test configuration, existing HD1910 loading applies contract P; this historical Walk used P5/D20 and beakP10. HOME / order / conversions and official UART / action / pad / HOME flow remain.

## v1.0.131 temporary servo parameters

“Scale and Filtering” becomes “Advanced Parameters,” adding P(address 50/Kp), D(51/Kd), and torque limit(48–49). Draft 3/0/681 is defined solely in `defaults.servo`; upgrade / edit does not activate it. Three fields share Apply with scale. P / D integers 0–255; torque 0–1000. Contracts / training / calibration remain.

Independent `console/static/advanced-parameters.js`/CSS owns draft / saved / applied rendering; `packaging/advanced_parameters.py` saves. Validate, unload torque, stop robotd; save global scale in existing TOML / copy and servo values separately at `/etc/robot/feetech-ft5/servo-test-parameters.json`; restart. No new timed SSH, service, or input protocol.

At startup `duck-control/src/hd1910_test.rs` reads JSON beside calibration. Absent JSON leaves the original path; present JSON applies four bytes 48–51 (little-endian torque limit+P+D) with original bus.sync_write to all 15 servos at next HOME torque enable, then confirms readback. No second UART owner. I52, acceleration 41, EEPROM, position packets, and sampling remain. Models / official gain requests do not override. Torque release restores pre-enable P / D / limit; reenable reapplies saved tests. Originals are saved before first write for partial-failure recovery.

UI distinguishes pending / saved / confirmed; only `native.hd1910.temporary_gains_applied=true` confirms hardware. Drafts are not actual values. Tests persist across restart / ordinary upgrade; model import does not alter them.

v132 separates stdout / stderr in persistent SSH subprocesses: both log live, JSON parses stdout only. Only complete catalog responses replace settings. Real errors / retries remain; operations, runtime identity, and target changes cancel old reads so delayed responses cannot overwrite a new service. Read failures and missing support differ. control.18, defaults, and register path are reused.

v134 catalog reads installed contracts / manifests / names / existence and declared hashes only; no YAML, runtime derivation, or inference. Import / bind / start keep validation; actual hashes come from `bus.loaded_models`. Numeric apply skips model-check / repeated verify_directory.

Maintenance preserves gamepad SSH; existing socket-inode detection finds the new service. One confirmation uses existing ensure only if dead. `input.status=recovering` suspends actions; ready reuses connected state / reopens the web socket. Old socket / actions / owner do not carry over. Real errors and existing recovery remain.

### Removing temporary testing

Unload torque, remove test JSON, restart; original gain / limit handling returns while saved scale remains. Remove independent modules, `defaults.servo`, and calls in ServiceManagement, runtime / service.sh / console.service_control, FeetechIo.configure_servo_test, and hd 1910:: State. Keep scale in normal management. Models / filter / UART / input need no rollback. Address 48–49 reference:[official HLSCL.h](https://github.com/ftservo/FTServo_Arduino/blob/main/src/HLSCL.h); P / D retain HD1910 50/51 mapping.

## v1.0.135 independent recovery scale

Stand / LB stand_test use base 1.0; walking / zero-speed hold use saved global(default 0.7), sit / stand 1.0. Filtering / voltage compensation remain. Training 0.7 is provenance, not multiplied again. Base 1 does not disable voltage compensation.

`Contract.uses_global_action_scale` marks rough walk only. Stand uses official standing_action_scale 1; LB named skill params.action_scale 1. Upgrade changes only those scales, preserving paths / duration / others / bindings. `bus.model_action_scales` adds readback. No auto-Stand rebind / contract / pose change. v136 changes LB to flat 10000 teacher at explicit request, keeping duration / base 1 and adding task recognition; recommendations do not overwrite global filtering / voltage.

## Complete-package installation and restart

v136 uploads full package into fixed installation paths. Existing models skip copying; non-model code / libs replace fully by rename to avoid Text file busy. Staging / extraction uses maintenance SSH, byte upload its existing transport. Bridge / padd / webpad configuration is centralized with one daemon-reload and one start each. Restart touches robotd only, reusing SSH / config; webpad / socket is reused or recovered once through existing status.

Default regeneration after parameter errors, startup retries, and ExecStopPost model rebuild are removed; robotd`Restart=no`. First errors / journal remain without auto-change / retry. Existing UART / HOME / packets / contracts remain. Timing has no hardware guarantee; use ZERO logs.

## v1.0.137 no-filter LB teacher

LB becomes rough 11000 teacher, SHA256 `a481d9f211f31d9476ab1a319fe362a21ef0879d9fa59442a122845af598268c`. Contract`action_filter.enabled=false`, head / leg alpha 1, training scale 1. Python / native accept it; no-filter cannot claim alpha<1. Encoder-side backlash and raw prior actions remain.

`Contract.target_filter_passthrough` only applies to explicit no-filter contracts. Controller bypasses head / leg target low-pass for this model, computing Home+base×raw with official voltage compensation. Globals / TOML / algorithm remain; no UI toggle. Leaving LB restores Walk scale / filters. `bus.active_target_filters` reports actual model filters; without inference UI shows globals. Actual hash readback remains.

`requested_skill_replacement` updates path / LB only on the migration to this source, scale 1, preserving duration / others. Initial duration 6 seconds. Auto Stand remains unbound; hold uses Walk; originals / local calibration remain.

## v1.0.138 contract recovery and retired models

Existence of a contract is insufficient: empty / truncated / non-object JSON recovers from the full bundled directory. Walk revision migration remains; valid same-ID imports skip recopying and unknown imports remain. Contract renames last to allow interrupted recovery. Original corruption cause was unconfirmed.

`retired_model_ids` explicitly lists 7000 recovery, flat 10000 recovery, and 18000 joint. Upgrade removes those directories and migrates references or removes skills lacking replacement. Current Walk / LB / valid models remain.

Catalog `active` means bound policy slot; `skill_bindings`/`manual_recovery` report named skills / LB even with contract errors. UI shows LB name / ID / base / availability without claiming binding proves execution. Stand empty and LB bound can coexist. Existing catalog requests are reused.

## Manual LB entry and completion

v145 adds fallen limp / HOME-ramp recovery to existing HOME / running LB. [robotd historical recovery](../../docs/design/robotd-design.en.md#r17-manual-lb-recovery-v10145) owns sensor rechecks, torque transaction, HOME / Walk return, and Start / Select cancellation. This page owns models / contracts / scales / migration.

## v1.0.141 raw positions and fixed targets

Requested removal of v139 modulo / v140 turn offsets retains Feetech 15-bit signed feedback and wire bytes. Angles use `(native-zero_raw)*direction*2π/4096`, without modulo / nearest-turn / dynamic-zero. Console accepts negatives. Fresh positions preload before torque; later targets use JointCalibration.target_raw without±4096. Calibration remains 0–4095; workbench / loose-servo centering linearly move through signed native coordinates and compare actual target.

Existing HOME / two-second ramp / limits / torque / gains / speed / current / acceleration / UART / EEPROM / calibration / models / input remain. Tests ID12−1→1500, ID22−1670→2276 and restart targets. ID22 travels 3946 counts≈346.8°; absolute coordinates are not a shortest-path guarantee or physical circling acceptance.

## v1.0.142 diagnostic ownership and refresh

Control 50 Hz / pre-inference HOME timing remains. Lightweight FeetechControlStatus checks feedback, IMU mount / readiness, torque tri-state, and unchanged freezing thresholds instead of copying diagnostics. Full diagnostics after safety.apply include applied torque / limit counts and feed communication / bus / limp every 20 ms.

Inspection arrays are immutable shared snapshots replaced on successful inspect; old snapshots retain old data, dynamic fields remain live. Model SHA / path / task caches are created on load / controller construction; hot reload replaces cache before carrying motion state, HOME retains loaded identities. Weights / inference / action / state flow remain. Tests cover virtual-serial loss / freezing / recovery / torque and register isolation, real-ONNX reload identity / action continuity. Connection design owns device listeners.

## v1.0.143 JSON and subscription reuse

Native JSON after 50 Hz safety moves into reports without an extra deep copy. Immutable bus JSON borrowed under Arc survives cache replacement; next request reads fresh cache. RPC / typed commissioning / missing errors remain. Arc state broadcasts share references with original fields / frequency, 256-frame queue, lag handling, and no-subscriber state avoidance. Console≤20 Hz / control 50 Hz remain. Production IPC verifies cache / priority / notifications / queues; SSH belongs to connection design. No physical CPU / temperature claim follows from reuse.

## v1.0.144 raw snapshots and on-request reporting

Supersedes per-tick full JSON: existing 50 Hz hardware / inference / safety publishes fixed dynamic snapshots after application; HOME / limp timing remains. IPC assembles JSON only when requested. Communication counters update without subscribers and survive transport disconnect alongside safety / models / errors. Static register / calibration / model metadata is shared and resent only on change.

Subscribed raw streams encode typed snapshots once for multiple connections; no consumers means sleeping / no low-rate reads. Official robot.subscribe keeps state / skeleton; raw numbers derive browser skeletons from the same model. Native FK / inference / safety remain. No gain / parameter / calibration / position / HOME / LB / UART / HAT / model changes for temperature; physical CPU / temperature reduction is unmeasured. Connection design owns frames / lifecycle / on-demand input / recordings.

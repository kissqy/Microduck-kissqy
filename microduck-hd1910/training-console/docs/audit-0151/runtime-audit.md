[Русский](runtime-audit.ru.md)

# Frozen robotd 0.15.1 action compatibility audit

Date: 2026-10-07. This audit uses official runtime commit **1fa84386f07884e27866411bc1ba166977bced95**, not current main. Training configuration is the studio's frozen **8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec** source. The separate task audit compares 273afe0b31c4ab365b9ff806a927b63ac92b5ddd; it does not extend the frozen daemon's capabilities. R148 is separately inspected as an HD1910 adaptation. No hardware was connected and no runtime/firmware was changed.

## Result and route matrix

The catalog has **35 training choices**, including two local left-kick aliases built with the official `kick_foot="left"` factory. A registered task, a matching ONNX shape, a native runtime route and acceptance by the installed R148 importer are four separate checks. None of the new actions is advertised as a verified physical deployment or an official finished checkpoint.

| Family / catalog role | Choices | Frozen native route | Runtime command meaning | Timing / chain | Compatibility limit |
|---|---:|---|---|---|---|
| Velocity / walk | 4 | walk slot | velocity twist + trained head/body commands | continuous | Exact 61/14 layout and HOME required |
| VelStand / joint | 4 | walk slot | velocity twist + head/body; recovery learned in same policy | continuous | Does not need a separate Stand policy |
| StandUp / stand | 4 | exported teacher only | training recovery task | no automatic deployment window | Do not relabel as idle-hold Stand; remains teacher/evaluation input |
| SitStand / sitstand | 4 | dedicated sitstand | twist[0] = sit 1 / stand 0; head live, body zero in task | scripted; training ramp read back; runtime rise default 1 s | Native branch scale fixed 1; body must remain zero for this task |
| GroundPick / ground_pick | 4 | dedicated ground_pick | [cos(2πφ), sin(2πφ), 0], head/body zero | actual period 4 s; cutoff .7 → 2.8 s; no chain | Runtime starts φ=0 although training may randomize initial phase |
| BallKick right / kick_right | 2 | named skill / kick_right slot | zero twist/head/body | .5 s; chain false | Skill scale must use params.action_scale; generic standing scale is not reliable without Stand |
| BallKick left / kick_left | 2 | named skill / kick_left slot | zero twist/head/body | .5 s; chain false | Independently train left factory or mirror whole ONNX correctly; filename does not mirror policy |
| Roulade / roulade | 1 | named skill / roulade slot | zero twist/head/body | 1 s; chain true | Flat only; no registered backlash variant; no `roulade_action_scale` policy key in this commit |
| VelocityRollers / roller | 2 | walk slot, mode roller | x=push/coast/brake [-.5,.6]; y,z=0; head/body=0 | continuous | Passive wheels required; existing velocity control labels do not change this protocol |
| RollerCrouch / crouch | 2 | ground_pick slot, mode roller | phase encoding; head/body=0 | **actual period 5 s**, cutoff .7 → 3.5 s; no chain | Stale source docstring says 4 s; actual cfg wins. Not a constant-command skill |
| VelocitySwizzle / swizzle | 2 | walk slot, mode roller, restricted protocol | x=forward/backward push [-.6,.6]; y=0; z=clipped heading error ±.5; head=HOME deltas; body=0 | continuous | Existing yaw-rate UI is not heading control. Only zero-yaw straight subset is established; full turns need an explicit heading-error caller and validation |
| RollerSlope / slope | 2 | walk slot, mode roller, all-zero commands | zero twist/head/body | continuous; no invented duration | Actual terrain is **Slope**, despite `Flat` in registered ID. Passive slope balance, not general remote-controlled gait |
| RollerStandUp / roller_stand | 1 | possible manually configured zero-command skill | zero twist/head/body | **no official runtime window** | Frozen Roller mode disables automatic Stand selection. 6 s training episode is not a justified deployment duration; export has no slot or executable skill definition |
| Spin / spin | 1 | ground_pick slot, mode roller | GroundPickPhaseCommand, head/body=0 | actual period 4 s; cutoff .7 → 2.8 s; no chain | Not a generic constant-command skill; same slot conflicts with crouch/pick |

Flat/Rough and backlash variants change simulation physics, not native runtime tensor sizes. All roller families require the corresponding passive wheel assembly. Passive wheel velocities are critic information, not added actor observations. The backlash wrapper provides 14 output-side position/velocity observations by summing servo and associated passive backlash state (plus encoder bias for position); it does not append passive joints to actions. Physical encoder placement and mechanical assembly still need to match that meaning.

## Frozen runtime evidence

All official links below pin the audited commit:

- [duck-control/src/obs.rs](https://github.com/pollen-robotics/microduck/blob/1fa84386f07884e27866411bc1ba166977bced95/duck-control/src/obs.rs), lines 7–54, 180–243: fixed 61-element actor vector, 14 actions; gyro 0:3, gravity 3:6, q−HOME 6:20, qdot 20:34, previous raw action 34:48, twist 48:51, head 51:55, body 55:61. Body x/y/yaw are zero. Head commands are observations, not extra post-inference joint offsets.
- [duck-control/src/model.rs](https://github.com/pollen-robotics/microduck/blob/1fa84386f07884e27866411bc1ba166977bced95/duck-control/src/model.rs), lines 39–55, and control.rs 547/609: common static HOME, not a per-model imported HOME. Exporter checks exact 14-joint order/HOME and Home + scale × raw-output mapping.
- [duck-control/src/policy.rs](https://github.com/pollen-robotics/microduck/blob/1fa84386f07884e27866411bc1ba166977bced95/duck-control/src/policy.rs), lines 583–664: float32 feedforward obs→actions, or exact recurrent obs,h_in,c_in→actions,h_out,c_out interface. The studio export/import workflow is narrower (MLP obs[1,61]→actions[1,14]); this audit does not claim it exports LSTM. Normalization is baked into ONNX once. Runtime has no left/right policy mirror transformation.
- [robotd/src/control.rs](https://github.com/pollen-robotics/microduck/blob/1fa84386f07884e27866411bc1ba166977bced95/robotd/src/control.rs), lines 480–535: generic SkillDef supplies constant command or unwind; head/body forced zero. GroundPick alone supplies a phase pair. SitStand supplies its flag. Walk/Stand forward live commands.
- Same control.rs 554–630: generic skill action_scale/gain_ratio override existing state-dependent defaults; global head/legs filters apply after HOME+scale×action. Voltage adaptation can further scale actions. No per-skill head/legs filter knobs. Export does not infer or change gain/voltage policy from training randomization.
- [robotd-params/src/lib.rs](https://github.com/pollen-robotics/microduck/blob/1fa84386f07884e27866411bc1ba166977bced95/robotd-params/src/lib.rs), lines 831–900: `[policy]` schema; **no roulade_action_scale / roulade_gain_ratio**. Lines 921–1006: SkillDef and SkillOverrides, with only action_scale/gain_ratio parameter overrides. 1311–1340: fallback kicks .5 s and roulade 1 s, with chain only for roulade.
- Same params.rs 1097–1109, 1156–1219: SetCommand supports constant, phase, posture_flag; generic set manifests have no nonzero active-command field. First phase entry for a mode provides timing; multiple phase policies in one mode are not selected by file identity. 1256–1262: default end_phase .7, SitStand rise 1 s/ramp 2 s.
- Same params.rs 1489–1514: configured skill replaces the entire named entry; slot path override is applied afterward. A generated `[[policy.skill]]` fragment must be merged while retaining configured path/gain_ratio and must be bound to the actual model. Copying a whole fragment over an existing configuration is not an automatic safe merge.
- Same params.rs 1580–1599, 1640–1667: mode-specific default files/scales and phase timing. Roller fallback period 3 s is not the actual trained crouch period 5 s; exported timing must be applied explicitly.
- [robotd/src/main.rs](https://github.com/pollen-robotics/microduck/blob/1fa84386f07884e27866411bc1ba166977bced95/robotd/src/main.rs), lines 1658–1662: Roller mode explicitly disables Stand selection. Lines 2652/3753: twist slew and direct `robot.move` vx/vy/vyaw forwarding; no task-aware heading-target conversion.

Raw source copies are in `analysis/pinned-runtime/`; `provenance.json` records pinned raw URLs, hashes and byte counts. Current main was not substituted for any compatibility conclusion.

## Training-specific command evidence

Pinned training sources: [tasks directory](https://github.com/pollen-robotics/microduck_rl/tree/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks).

- `tasks/__init__.py`: right BallKick registration; rollers, swizzle, crouch, slope, roller standup, spin; backlash variants of kick/roller/swizzle/crouch/slope. No registered backlash roulade/spin/roller standup.
- `microduck_ball_kick_env_cfg.py:132–143`: official factory accepts left/right. Ball position is critic-only; actor remains 61. Renaming a right checkpoint is not left training or ONNX mirroring.
- `microduck_velocity_rollers_env_cfg.py:533–552`: head/body padding; throttle range and zero yaw-error clip.
- `microduck_velocity_swizzle_env_cfg.py:57–78,110–130`: negative throttle becomes backward, z is heading error, actual head pose command and zero body. `mdp.py:4819–4828` implementation computes **target_yaw − current_yaw**, wraps and clips. The earlier class docstring's sign is stale and must not be copied into a controller. A constant nonzero input is a turning intent, not a guaranteed rad/s command.
- `microduck_roller_slope_env_cfg.py:70–107`: slope generator and all-zero commands; ID spelling does not imply flat physical terrain.
- `microduck_roller_standup_env_cfg.py`: 6 s episode, tiny near-zero sampled twist, no head/body command. Its older prototype advice about automatically selecting a standing model is contradicted by this frozen robotd implementation.
- `microduck_spin_env_cfg.py:374–386`, `mdp.py:6070`: GroundPickPhaseCommand period 4, deterministic initial phase. Crouch actual serialized cfg period 5. Frozen runtime phase cutoff .7 is recorded, not confused with training episode termination or automatic success detection.

## Installed R148 is a separate, narrower gate

Read-only source inspected at `joint-scale-update/work/Microduck-Source-R17-v1.0.148`:

- `packaging/model_packages.py:148–196` official-adapter task whitelist accepts only VelStand-Flat, GroundPick-Flat, Roulade-Flat, StandUp-Flat, Velocity-Rough-Backlash, StandUp-Rough-Backlash, VelStand-Rough-Backlash. Existing installed SitStand may use the separate legacy HD1910 adapter; that is not proof that a new official-adapter SitStand export is accepted.
- `duck-control/src/deployment.rs:210–237` repeats the official-task gate.
- `packaging/model_packages.py:132–145` requires single-input/single-output feedforward exact 61/14, with a restricted operation list. Native recurrent support or a mirrored graph containing Gather does not bypass this gate.
- Current kick import slots are separately disabled in the management configuration.

Consequently **all six roller families and both kick aliases are not directly importable into the user's current R148**, although specified native runtime routes exist. No whitelist was loosened and no installed model was replaced as part of this training-console update.

## Training exporter changes and verification

Product edits are limited to `training/deployment.py`. Added `tests/test_extended_deployment.py` and, after explicit parent authorization, updated the old default/scale expectations in `tests/test_action_filter.py` and catalog expectations in `tests/test_current_actions.py` while retaining legacy filtered-model and physical-history tests. Export adds:

- `command_contract`, with actual semantics, phase period/start/cutoff and original training initial-phase randomization.
- `required_skill_settings` for frozen native named-skill action scales; no invalid old per-roulade key and no dependence on a missing Stand policy for kick scale.
- `runtime_compatibility`, separating native route/support limits, R148 task gate, passive-wheel requirement, and explicit false values for automatic deployment / official finished weights / verified direct import.
- Correct Roller mode and existing slot mappings, plus no invented RollerStand slot or execution window.
- Readable restrictions in generated TOML/manifest/instructions. Native skill TOML is a merge fragment, not a complete robot configuration or installer.

`python -m unittest tests.test_extended_deployment -v`: **10 tests passed**, including all 35 then-materialized readbacks and preservation of input snapshots. `python -m unittest tests.test_export_contract tests.test_extended_deployment -q`: **16 passed**. `python -m unittest tests.test_action_filter -v`: **9 passed**. `python -m unittest tests.test_current_actions.CurrentActionTests tests.test_servo_p_trial -v`: **8 passed**; servo-P tests required no edits. Three pre-existing deployment-focused CatalogAndContractTests (slot semantics, incompatible obs/frequency rejection, sidecar repack) also passed. Final regenerated catalog/readbacks are included in the parent task's integrated verification. These are offline interface/configuration tests, not simulated policy performance or physical deployment validation.

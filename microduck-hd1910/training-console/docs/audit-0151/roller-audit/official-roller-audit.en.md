[简体中文](official-roller-audit.zh-CN.md) | **English** | [Русский](official-roller-audit.ru.md)

# Official six-family roller parameter audit (October 7, 2026)

Read-only comparison of frozen `8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec` and develop-at-audit `273afe0b31c4ab365b9ff806a927b63ac92b5ddd`. Six env_cfg, registry, backlash wrapper, constants, and two roller XMLs are byte-identical. Shared mdp changes do not alter enabled behavior here. JSON contains actual factory train / play configuration; short tests are in smoke-frozen.json.

## Registrations and action interface

| Family | Base registration | Backlash registration | Rough | Actual command |
|---|---|---|---|---|
| RollersVelocity | `Mjlab-Velocity-Flat-MicroDuck-Rollers` | `Mjlab-Velocity-Flat-Backlash-MicroDuck-Rollers` | None | twist x positive=push, zero=coast, negative=brake; x[-0.5, 0.6], y=0; z heading error clipped to 0 so no steering trained. Head 4/body 6 exact zero padding. |
| Swizzle | `Mjlab-Velocity-Swizzle-MicroDuck` | `Mjlab-Velocity-Swizzle-Backlash-MicroDuck` | None | twist x[-.6,.6] positive=forward push, negative=backward push (NOT brake), y=0, z heading error±.5. Head 4 live HOME deltas, body 6 exact zero padding. |
| RollerCrouch | `Mjlab-RollerCrouch-Flat-MicroDuck` | `Mjlab-RollerCrouch-Flat-Backlash-MicroDuck` | None | twist=[cos(2πphase), sin(2πphase), 0], period 5 s, reset phase 0; head 4/body 6 exact zero padding. |
| RollerSlope | `Mjlab-RollerSlope-Flat-MicroDuck` | `Mjlab-RollerSlope-Flat-Backlash-MicroDuck` | None | all twist=0, standing fraction 1; head 4/body 6 exact zero padding. |
| RollerStandUp | `Mjlab-RollerStandUp-Flat-MicroDuck` | None | None | VelocityCommandCommandOnly twist x, y±.01, z±.05; resample 6–12 s; head 4/body 6 exact zero padding. |
| Spin | `Mjlab-Spin-Flat-MicroDuck` | None | None | twist=[cos(2πphase), sin(2πphase), 0], period 4 s, resetphase 0; head 4/body 6 exactzero. |

## Shared physics and sampling

-50 Hz control, MuJoCo timestep 0.005 s, decimation 4; 14 D JointPositionAction, scale 1, HOMEoffset, no EMA / explicit action clip. Upstream XL330 BAM M6/P200 differs from XMLkp 0.55 and userHD1910.
-Actuation delay 3–6 physics steps=15–30 ms; IMU0–1 control step, updates 64 steps; jointvelocity 1 step. actor 61=gyro 3+gravity 3+jointpos 14+jointvel 14+lastaction 14+twist 3+head 4+body 6.
-Four passive wheels interleave 14 servos without wheel actions. Four tire meshes retain XML defaults; entity collisions=(). Compiled condim 3/friction[1, 0.005, 0.0001] supports normal / sliding constraints, not evidence of trained torsional / rolling friction.
-All six remove foot_friction with no geom_friction DR. Axle dof_frictionloss is bearing drag, distinct from ground coefficients. Most wheel curriculum ranges have identical bounds, deterministic per stage.
-Voltage startup 6.5–8.2 V, dropgain 0–0.2, min 6 V; BAMfriction / armature reset 0.9–1.1; encoderstartup±0.015 rad; fixed per-env IMU mount≤6°; trunk pseudo-inertia alpha[log(.95)/2, log(1.05)/2].CoM±3→±5→±10 mm; Slope removes that curriculum and stays±3 mm.
-Default episode 20 s, RollerStandUp 6 s.Ordinary roller tilt 70°termination; Slope 1 rad plusvoid; RollerStandUp removesfell_over.All retain NaN termination.

## Family curricula, reset, and play

### RollersVelocity

Source evidence:`/workspace/scratch/9f94b8b8f4de/training-actions-update/analysis/official-sources/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_velocity_rollers_env_cfg.py`: 85

- terrain: plane
- key_rewards: wheel_speed 10, glide 4, single_support 3, skating_air_time 1.5, heading_hold 1; upright 2/pose 2; action_rate initial−1→−1.5@250→−2@500.
- play: play argument is not used by factory; all training noise / DR / curricula retained.
- Wheel axle friction curriculum (iteration, value)：[[0, 0.0], [2000, 0.0005], [3500, 0.001], [5000, 0.0015]]

### Swizzle

Source evidence:`/workspace/scratch/9f94b8b8f4de/training-actions-update/analysis/official-sources/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_velocity_swizzle_env_cfg.py`: 34

- terrain: plane
- key_rewards: drop stride single_support / glide / skating_air_time / gait_symmetry / hip_roll_neutral; add leg_symmetry 2 and grounded 1; remove braking and neck HOME penalty; pose legs only; heading_hold 1→0 while heading_tracking 0→3 by 2500; head_tracking 0→4 by 3000.
- play: no special play branch; retained training noise / DR / curricula.

### RollerCrouch

Source evidence:`/workspace/scratch/9f94b8b8f4de/training-actions-update/analysis/official-sources/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_roller_crouch_env_cfg.py`: 116

- terrain: plane
- reset: HOME joints and base forward velocity .2–.5 m / s; reset base z offset .1335–.1435 relative default root. Does NOT synchronize initial wheel speeds with forward velocity.
- key_rewards: named measured stand / crouch joint targets: gaussian 6 std.4 + self-negating L1 weight+2; preserve forward speed 1; crouch forward lean 1 at.08 rad; upright 2; smoothness schedule−.5/−.8/−1.
- play: play argument unused; noise / DR / curricula retained.
- static_issue: No explicit expand_bam_friction_fields startup event. Actual 2 worldreset+2 step passed: wheel friction event expands dof_frictionloss; damping is constant scalar in BAM write. This is not a demonstrated runtime failure.
- Wheel axle friction curriculum (iteration, value)：[[0, 0]]

### RollerSlope

Source evidence:`/workspace/scratch/9f94b8b8f4de/training-actions-update/analysis/official-sources/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_roller_slope_env_cfg.py`: 66

- terrain: generator despite Flat registry name: 10 rows×1 column, 15 m×4 mtiles; 2 mflat+3–8 mrandom horizontal downhill+4 mrunout; angle 2°→20° bylevel; spawn.3 monto ramp.
- reset: yaw 0; clear inherited base velocity; reset_rolling_entry applies coherent base+wheel rolling speed .25–.45 m / s.
- key_rewards: upright 3(std.2), alive 1, wheel_glide 2(cap.35 m / s), heading_hold 1.5, feet_flat−2, neck_action_rate−.5, neck_joint_pos−.75, torques−.001, action_rate−1.
- curriculum: deletes ALL inherited curricula, including wheel-friction and CoM ramps; retains only terrain_levels_slope. Promote distance>0.4×15=6 m; demote<0.2×15=3 m.
- play: default max_init_terrain_level=None permits all rows; optional SLOPE_PLAY_DIFFICULTY fixes difficulty 0–1; inherited noise / DR remain; terrain curriculum remains.
- Wheel axle friction curriculum (iteration, value)：[[0, 0]]

### RollerStandUp

Source evidence:`/workspace/scratch/9f94b8b8f4de/training-actions-update/analysis/official-sources/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_roller_standup_env_cfg.py`: 135

- terrain: plane
- reset: ground-state event runs last; prone / supine z.076–.09, standing.134–.144; standing tilt±10°; no seated bucket.
- key_rewards: HOMElegs 8+L1 weight 5; height target.138 m gaussian 4(std.04)+4(std.015)+L1 weight 30; upward velocity 3; upright linear 6/sharp 6; multiplicative composite 15; gentle_rise+.02(self-negative); torque_rate−.2. action_rate configured−.6, curriculum−.4/−.8/−1 afterstage applies.
- play: optional STANDUP_PLAY_FACE_UP fixes supine probability and removes only ground_state_mix; unset defaults to curriculum step 0 (0% supine). Other DR / noise / curricula remain, including high initial wheel drag.
- static_issue: _LEG_JOINTS=[0, 1, 2, 3, 4, 11, 12, 13, 14, 15] are raw 18 slot indices, but pose_target_match, pose_l 1_penalty, standing_composite_score now index 14 Dservo views.14/15 are out ofbounds.
- Wheel axle friction curriculum (iteration, value)：[[0, 0.05], [1000, 0.02], [2000, 0.008], [3000, 0.003], [4000, 0.0015]]

### Spin

Source evidence:`/workspace/scratch/9f94b8b8f4de/training-actions-update/analysis/official-sources/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_spin_env_cfg.py`: 87

- terrain: plane
- reset: HOME joints; base forward velocity 0–.3 m / s; initial wheel speeds not coherently updated.
- key_rewards: yaw rate gaussian 6(std 1.5)+L1 weight+.5; position drift−3 with launch factor.2; differential wheel 1; legantisym 1→.5@1500→.25@3000; grounded.5; keeps upright 2 androll / pitch angular penalty−.05; deliberately removes angular_momentum; head_yaw not held to HOME.
- play: play argument unused; training noise / DR / curricula retained.
- static_issue: No explicit expand_bam_friction_fields startup event; actual 2 worldreset+2 step passed. Passive wheel selector ^passive_.* is broad but no SpinBacklash registry currently exists.
- Wheel axle friction curriculum (iteration, value)：[[0, 0]]

## Source issues requiring short-step checks

1.RollerStandUp _LEG_JOINTS uses 18 slots including 14/15, but pose_target_match / pose_l 1_penalty / standing_composite_score first select 14 Dservos. Independent 2 worlds fail first pose_target_match with index 14/size 14 at both commits.
2.Crouch / Spin lack Rollers' expand_bam_friction_fields, but both pass 2 world reset+2 steps: wheel events expanddof_frictionloss andBAM damping writes a scalar. No demonstrated runtime failure.
3.Do not copy comments: Crouch docstring says 4 s, constant 5 s; RelativeHeadingVelocityCommand docstring sayspositiveCW, but target_yaw−current_yaw gives positive CCW.
4.Default play is not final curriculum evaluation: four factories ignoreplay; RollerStandUp starts 0%supine / wheeldrag 0.05 unlessSTANDUP_PLAY_FACE_UP changes onlysupine probability, not wheel curriculum.

## Files

-official-roller-audit.json: machine-readable shared conclusions, family summaries, actualtrain / play factory configuration, source hashes / evidence.
-smoke-frozen.json / smoke-frozen.log: read-only upstream factory, 2 worldreset+2 steps, zeroactions, no training / hardware.

## Local adapter repair and readback (R1.5.21)

Authorized local training / official_adapter.py remaps three RollerStandUp pose rewards 18→14 slots by actual names, including joint_indices / optionaltarget_overrides: rightleg 11–15→9–13, neck / head 7–10→5–8. Reset / events / weights remain. Describe / train / export share the adapter and correction receipt. Original upstream failure evidence does not mean the repaired local task still fails.

Six targeted tests passed: actualHD1910, 2 envs / reset+10 steps, finite actor 61/rewards; correct leg / neck targets for three rewards; idempotence, no partial corruption, consistent describe / train / export; foot / tirefriction / axledrag readback without state change. Fulladapter-tests.log.First-step friction_readback is one post-DR readback, not long-term coverage or task success.

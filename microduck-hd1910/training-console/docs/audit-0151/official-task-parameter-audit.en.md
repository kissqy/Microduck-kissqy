[简体中文](official-task-parameter-audit.zh-CN.md) | **English** | [Русский](official-task-parameter-audit.ru.md)

# Official per-task parameter audit (October 7, 2026)

Training stays pinned to `8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec`, compared with develop `273afe0b31c4ab365b9ff806a927b63ac92b5ddd` at audit time. Importing both registries yields the same 33 upstream tasks. Two local left-kick aliases call the official parameterized factory, giving 35 console tasks. Unregistered combinations were not invented from README summaries.

Evidence: `official-task-parameter-matrix.json` records each task's events, parameters, rewards, curricula, terminations, actions, observations, optimizer, and train / play differences. `official-resolved-*.json` are full actual factory outputs. `official-compiled-physics.json` compiles nine original upstream robot Entities, without HD1910 or active randomization.

## Actual registered combinations

| Family | Count | Rough | Backlash | Terrain / notes |
|---|---:|---|---|---|
| BallKick | 2 | None | Yes | Plane only |
| GroundPick | 4 | Yes | Yes | Plane / Rough generator |
| RollerCrouch | 2 | None | Yes | Plane; roller hardware |
| RollerSlope | 2 | None | Yes | Flat in ID, actual slope generator |
| RollerStandUp | 1 | None | None | Plane; roller hardware |
| Roulade | 1 | None | None | Plane only |
| SitStand | 4 | Yes | Yes | Plane / Rough generator |
| Spin | 1 | None | None | Plane; roller hardware |
| StandUp | 4 | Yes | Yes | Plane / Rough generator |
| VelStand | 4 | Yes | Yes | Plane / Rough generator |
| Velocity | 4 | Yes | Yes | Plane / Rough generator |
| RollersVelocity | 2 | None | Yes | Plane; roller hardware |
| Swizzle | 2 | None | Yes | Plane; roller hardware |

Roulade, RollerStandUp, and Spin have no Backlash registrations. No roller family has Rough. Forward roll has neither Rough nor Backlash. Six roller families' commands, axle curricula, and short-step results are in [the roller audit](roller-audit/official-roller-audit.en.md).

## Physical distinctions

- All control 50 Hz: physics 5 ms / decimation 4; 14 active joints, 61 actor dimensions. Actions are Home+scale×raw policy, official scale 1, no target EMA. head_pose_bias reward memory is not action filtering.
- Upstream is XL330 BAM M6/P200, console is HD1910/P5; numbers are not directly comparable. Built upstream Entity: kt 0.3660134969, R2.8113923539, armature 0.0018077433, max_pwm 1,**BAM default max_current 1.75 A**. Missing explicit config does not mean unlimited current. Gross static motor torque bound≈0.64052 N·m excludes friction and is not measured continuous torque.
- Voltage startup 6.5–8.2 V, load-drop gain 0–0.2, min 6 V; actuation delay 3–6 physics steps=15–30 ms. IMU normally 0–1 control step; GroundPick 0–3=0–60 ms; joint velocity 1 step. Noise / hold / update settings are in JSON.
- Upstream ordinary mass 737.24318 g, roller 736.82962 g, not the user's 820 g. studio_inspection_summary separately compiles 35 HD1910 P5/scale 1/no-EMA tasks: ordinary 820.000 g, roller 819.58644 g. Record the 0.41356 g difference rather than exact equality.
- Nonroller foot_friction is startup uniform absolute[0.7, 1.3], shared between feet; mjlab axes=[0] randomizes sliding only, not every reset. Official play retains it.
- Torsional / rolling slots commonly[0.005, 0.0001] have no randomization; foot condim 3 enables sliding. After FULL_COLLISION, most nonfoot named geoms usecondim 1. Final dimensions also depend on both geoms' priority, so one slot does not establish trained friction for every collision.
- Roller tires are **mesh, MuJoCo type 7**; four passive wheel hinges interleave active joints. Tires condim 3/friction[1, 0.005, 0.0001]. Six families have no geom_friction randomization. randomize_wheel_friction changes axle dof_frictionloss, bearing resistance; most curriculum interval bounds are identical.
- BAM internal friction and armature usually randomize on reset[0.9, 1.1], independently of foot friction. Actual events / selectors are listed rather than assuming comment toggles.
- Collision specs differ: Velocity=walk; StandUp / SitStand / GroundPick / BallKick / Roulade=groundcontact; VelStand=allcollisions. The “No task uses it yet” comment is outdated. Backlash chooses matching specs, 14 axes±1°each.

## Hidden Rough and play differences

Rough declares 10×20 but actual registry import yields 5×5: train / play share the generator and play mutates dimensions. generator.curriculum was never declared True; mjlab defaults False, so play did not disable True and no silent True change is justified. terrain_levels is a separate curriculum. This audit retains mature actual 5×5/random-difficulty behavior.
play=True is not a universal no-randomization switch. Noise, BAM / ground DR, and curricula often remain; some tasks increase pushes. Rollers / Swizzle / Crouch / Spin have no play branch. JSON records differences; “evaluation” does not establish noiseless / stable behavior.

## Original upstream failure and minimal local repair

Original RollerStandUp fails on its first step: reward functions use 14 servo views while configuration retains 18 slot indices including 14. Both commits exhibit it. The local adapter remaps joint_indices / target_overrides for the three affected rewards by actual joint names, without changing raw reset indices, weights, or curricula. Five independent tests, including 2 environments/10 steps, passed; original failure logs remain. Registration alone is not runtime acceptance.
Crouch / Spin omit explicit expand_bam_friction_fields, but both pass 2 environment reset+2 steps: wheel resistance expands needed fields. Static absence does not prove broken training; audit warnings still require actual stepping.

## Frozen version versus develop at audit time

Registry, Backlash wrapper, robot constants, all non-VelStand env_cfg, six roller families, and symmetry files are byte-identical. Changes concentrate on VelStand, body-command mdp, and distill. Enabled standing body commands add roll / pitch≈±12°, z−2.5 to+1 cm, and change rewards / BC routes; ENABLE_YAW_FIX remainsFalse. Adding actions does not require upgrading mature behavior; keep 8 d 0 pinned.

## Per-task quick index

| Task ID | Seconds | Contact friction train / play | Initial training IMU delay | Robot spec |
|---|---:|---|---|---|
| `Mjlab-BallKick-Flat-Backlash-MicroDuck` | 5 | startup 0.7–1.3 / Retained | 0–1 steps | `get_backlash_spec` |
| `Mjlab-BallKick-Flat-MicroDuck` | 5 | startup 0.7–1.3 / Retained | 0–1 steps | `get_standup_spec` |
| `Mjlab-GroundPick-Flat-Backlash-MicroDuck` | 20 | startup 0.7–1.3 / Retained | 0–3 steps | `get_backlash_spec` |
| `Mjlab-GroundPick-Flat-MicroDuck` | 20 | startup 0.7–1.3 / Retained | 0–3 steps | `get_ground_pick_spec` |
| `Mjlab-GroundPick-Rough-Backlash-MicroDuck` | 20 | startup 0.7–1.3 / Retained | 0–3 steps | `get_backlash_spec` |
| `Mjlab-GroundPick-Rough-MicroDuck` | 20 | startup 0.7–1.3 / Retained | 0–3 steps | `get_ground_pick_spec` |
| `Mjlab-RollerCrouch-Flat-Backlash-MicroDuck` | 20 | No geom DR / none | 0–1 steps | `get_rollers_backlash_spec` |
| `Mjlab-RollerCrouch-Flat-MicroDuck` | 20 | No geom DR / none | 0–1 steps | `get_walk_rollers_spec` |
| `Mjlab-RollerSlope-Flat-Backlash-MicroDuck` | 20 | No geom DR / none | 0–1 steps | `get_rollers_backlash_spec` |
| `Mjlab-RollerSlope-Flat-MicroDuck` | 20 | No geom DR / none | 0–1 steps | `get_walk_rollers_spec` |
| `Mjlab-RollerStandUp-Flat-MicroDuck` | 6 | No geom DR / none | 0–1 steps | `get_walk_rollers_spec` |
| `Mjlab-Roulade-Flat-MicroDuck` | 5 | startup 0.7–1.3 / Retained | 0–1 steps | `get_standup_spec` |
| `Mjlab-SitStand-Flat-Backlash-MicroDuck` | 12 | startup 0.7–1.3 / Retained | 0–1 steps | `get_backlash_spec` |
| `Mjlab-SitStand-Flat-MicroDuck` | 12 | startup 0.7–1.3 / Retained | 0–1 steps | `get_standup_spec` |
| `Mjlab-SitStand-Rough-Backlash-MicroDuck` | 12 | startup 0.7–1.3 / Retained | 0–1 steps | `get_backlash_spec` |
| `Mjlab-SitStand-Rough-MicroDuck` | 12 | startup 0.7–1.3 / Retained | 0–1 steps | `get_standup_spec` |
| `Mjlab-Spin-Flat-MicroDuck` | 20 | No geom DR / none | 0–1 steps | `get_walk_rollers_spec` |
| `Mjlab-StandUp-Flat-Backlash-MicroDuck` | 6 | startup 0.7–1.3 / Retained | 0–1 steps | `get_backlash_spec` |
| `Mjlab-StandUp-Flat-MicroDuck` | 6 | startup 0.7–1.3 / Retained | 0–1 steps | `get_standup_spec` |
| `Mjlab-StandUp-Rough-Backlash-MicroDuck` | 6 | startup 0.7–1.3 / Retained | 0–1 steps | `get_backlash_spec` |
| `Mjlab-StandUp-Rough-MicroDuck` | 6 | startup 0.7–1.3 / Retained | 0–1 steps | `get_standup_spec` |
| `Mjlab-VelStand-Flat-Backlash-MicroDuck` | 20 | startup 0.7–1.3 / Retained | 0–1 steps | `get_allcollisions_backlash_spec` |
| `Mjlab-VelStand-Flat-MicroDuck` | 20 | startup 0.7–1.3 / Retained | 0–1 steps | `get_allcollisions_spec` |
| `Mjlab-VelStand-Rough-Backlash-MicroDuck` | 20 | startup 0.7–1.3 / Retained | 0–1 steps | `get_allcollisions_backlash_spec` |
| `Mjlab-VelStand-Rough-MicroDuck` | 20 | startup 0.7–1.3 / Retained | 0–1 steps | `get_allcollisions_spec` |
| `Mjlab-Velocity-Flat-Backlash-MicroDuck` | 20 | startup 0.7–1.3 / Retained | 0–1 steps | `get_walk_backlash_spec` |
| `Mjlab-Velocity-Flat-Backlash-MicroDuck-Rollers` | 20 | No geom DR / none | 0–1 steps | `get_rollers_backlash_spec` |
| `Mjlab-Velocity-Flat-MicroDuck` | 20 | startup 0.7–1.3 / Retained | 0–1 steps | `get_walk_spec` |
| `Mjlab-Velocity-Flat-MicroDuck-Rollers` | 20 | No geom DR / none | 0–1 steps | `get_walk_rollers_spec` |
| `Mjlab-Velocity-Rough-Backlash-MicroDuck` | 20 | startup 0.7–1.3 / Retained | 0–1 steps | `get_walk_backlash_spec` |
| `Mjlab-Velocity-Rough-MicroDuck` | 20 | startup 0.7–1.3 / Retained | 0–1 steps | `get_walk_spec` |
| `Mjlab-Velocity-Swizzle-Backlash-MicroDuck` | 20 | No geom DR / none | 0–1 steps | `get_rollers_backlash_spec` |
| `Mjlab-Velocity-Swizzle-MicroDuck` | 20 | No geom DR / none | 0–1 steps | `get_walk_rollers_spec` |

## Primary source locations

- BallKick：[Factory source](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_ball_kick_env_cfg.py#L132).
- GroundPick：[Factory source](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_ground_pick_env_cfg.py#L114).
- RollerCrouch：[Factory source](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_roller_crouch_env_cfg.py#L116).
- RollerSlope：[Factory source](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_roller_slope_env_cfg.py#L66).
- RollerStandUp：[Factory source](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_roller_standup_env_cfg.py#L135).
- Roulade：[Factory source](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_roulade_env_cfg.py#L147).
- SitStand：[Factory source](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_sitstand_env_cfg.py#L195).
- Spin：[Factory source](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_spin_env_cfg.py#L87).
- StandUp：[Factory source](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_standup_env_cfg.py#L152).
- VelStand：[Factory source](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_velstand_env_cfg.py#L377).
- Velocity：[Factory source](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_velocity_env_cfg.py#L193).
- RollersVelocity：[Factory source](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_velocity_rollers_env_cfg.py#L85).
- Swizzle：[Factory source](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_velocity_swizzle_env_cfg.py#L34).
- `src/mjlab_microduck/tasks/__init__.py`：[Line 78](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/__init__.py#L78).
- `src/mjlab_microduck/robot/microduck_constants.py`：[Line 142](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/robot/microduck_constants.py#L142).
- `src/mjlab_microduck/tasks/backlash.py`：[Line 42](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/backlash.py#L42).
- `src/mjlab_microduck/tasks/microduck_velocity_env_cfg.py`：[Line 130](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_velocity_env_cfg.py#L130).

mjlab 1.3.0 dependency references: envs / mdp / dr / geom.py: 117–145(default friction axes), terrains / terrain_generator.py: 92(default curriculum False). Full versions are in JSON. This audit establishes configuration and short-step executability, not convergence or physical-robot usability.

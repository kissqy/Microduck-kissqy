**简体中文** | [English](official-roller-audit.en.md) | [Русский](official-roller-audit.ru.md)

# 官方轮滑六族参数审计（2026-10-07）

只读比对 frozen `8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec` 与 current `273afe0b31c4ab365b9ff806a927b63ac92b5ddd`。六族 env_cfg、registry、backlash 包装器、机器人常量及两个轮滑 XML 字节相同。共享 mdp 修改未改变这六族启用的行为。JSON 含实际 factory 的 train / play 完整关键配置；短步结果另存 smoke-frozen.json。

## 真实注册与动作接口

| 家族 | base 注册 | Backlash 注册 | Rough | 实际命令 |
|---|---|---|---|---|
| RollersVelocity | `Mjlab-Velocity-Flat-MicroDuck-Rollers` | `Mjlab-Velocity-Flat-Backlash-MicroDuck-Rollers` | 无 | twist x positive=push, zero=coast, negative=brake; x[-0.5,0.6], y=0; z heading error clipped to0 so no steering trained. Head4/body6 exact zero padding. |
| Swizzle | `Mjlab-Velocity-Swizzle-MicroDuck` | `Mjlab-Velocity-Swizzle-Backlash-MicroDuck` | 无 | twist x[-.6,.6] positive=forward push, negative=backward push (NOT brake), y=0, z heading error±.5. Head4 live HOME deltas, body6 exact zero padding. |
| RollerCrouch | `Mjlab-RollerCrouch-Flat-MicroDuck` | `Mjlab-RollerCrouch-Flat-Backlash-MicroDuck` | 无 | twist=[cos(2πphase),sin(2πphase),0], period5s, reset phase0; head4/body6 exact zero padding. |
| RollerSlope | `Mjlab-RollerSlope-Flat-MicroDuck` | `Mjlab-RollerSlope-Flat-Backlash-MicroDuck` | 无 | all twist=0, standing fraction1; head4/body6 exact zero padding. |
| RollerStandUp | `Mjlab-RollerStandUp-Flat-MicroDuck` | 无 | 无 | VelocityCommandCommandOnly twist x,y±.01,z±.05; resample6–12s; head4/body6 exact zero padding. |
| Spin | `Mjlab-Spin-Flat-MicroDuck` | 无 | 无 | twist=[cos(2πphase),sin(2πphase),0],period4s,resetphase0; head4/body6exactzero. |

## 共享真实物理 / 采样

- 50 Hz 控制；MuJoCo timestep=0.005 s，decimation=4。动作是14维 JointPositionAction，scale=1.0，以默认 HOME 为 offset；无 action EMA、未设 action clip。官方默认是 XL330 BAM M6、firmware P=200，不能把 XML kp=0.55 当最终驱动器，也不能当用户 HD1910 配置。
- actuator 延迟3–6个 **物理步**，即15–30 ms；IMU 延迟0–1个控制步，64步更新；joint velocity固定1个控制步延迟。actor61=gyro3+gravity3+jointpos14+jointvel14+lastaction14+twist3+head4+body6。
- 四个被动轮铰链，与14伺服关节交错；轮子无驱动动作。四个 tire 碰撞mesh保留 XML 默认，轮滑 entity 的 collisions=()。实编译 wheel condim=3、geom_friction=[1,0.005,0.0001]；condim3只启用法向和切向滑动摩擦约束，不能把后两槽写成已训练扭转/滚动摩擦。
- 六族均删除 foot_friction，未新增任何 geom_friction 随机化。轮轴的 dof_frictionloss 是轴承阻力，与地面滑动/扭转/滚动摩擦系数不是同一参数。所谓 wheel randomization 的各课程区间多数上下限相等，是阶段确定值。
- 电压startup6.5–8.2V，负载压降gain0–0.2，最低6V；BAM摩擦倍率reset0.9–1.1，armature倍率0.9–1.1；编码器startup±0.015rad；IMU每环境固定安装误差最大6°；trunk伪惯性alpha区间=[log(.95)/2,log(1.05)/2]。CoM通常±3mm→±5mm→±10mm，Slope移除了该课程所以保持±3mm。
- 默认20s episode；RollerStandUp是6s。普通轮滑 tilt70°结束；Slope改1rad并增void；RollerStandUp移除fell_over。各族保留NaN终止。

## 各族实际课程、reset及 play差别

### RollersVelocity

来源：`/workspace/scratch/9f94b8b8f4de/training-actions-update/analysis/official-sources/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_velocity_rollers_env_cfg.py`:85

- terrain: plane
- key_rewards: wheel_speed10, glide4, single_support3, skating_air_time1.5, heading_hold1; upright2/pose2; action_rate initial−1→−1.5@250→−2@500.
- play: play argument is not used by factory; all training noise/DR/curricula retained.
- 轮轴摩擦课程（iteration,value）：[[0, 0.0], [2000, 0.0005], [3500, 0.001], [5000, 0.0015]]

### Swizzle

来源：`/workspace/scratch/9f94b8b8f4de/training-actions-update/analysis/official-sources/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_velocity_swizzle_env_cfg.py`:34

- terrain: plane
- key_rewards: drop stride single_support/glide/skating_air_time/gait_symmetry/hip_roll_neutral; add leg_symmetry2 and grounded1; remove braking and neck HOME penalty; pose legs only; heading_hold1→0 while heading_tracking0→3 by2500; head_tracking0→4 by3000.
- play: no special play branch; retained training noise/DR/curricula.

### RollerCrouch

来源：`/workspace/scratch/9f94b8b8f4de/training-actions-update/analysis/official-sources/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_roller_crouch_env_cfg.py`:116

- terrain: plane
- reset: HOME joints and base forward velocity .2–.5m/s; reset base z offset .1335–.1435 relative default root. Does NOT synchronize initial wheel speeds with forward velocity.
- key_rewards: named measured stand/crouch joint targets: gaussian6 std.4 + self-negating L1 weight+2; preserve forward speed1; crouch forward lean1 at.08rad; upright2; smoothness schedule−.5/−.8/−1.
- play: play argument unused; noise/DR/curricula retained.
- static_issue: No explicit expand_bam_friction_fields startup event. Actual2worldreset+2step passed: wheel friction event expands dof_frictionloss; damping is constant scalar in BAM write. This is not a demonstrated runtime failure.
- 轮轴摩擦课程（iteration,value）：[[0, 0]]

### RollerSlope

来源：`/workspace/scratch/9f94b8b8f4de/training-actions-update/analysis/official-sources/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_roller_slope_env_cfg.py`:66

- terrain: generator despite Flat registry name:10rows×1column,15m×4mtiles;2mflat+3–8mrandom horizontal downhill+4mrunout;angle2°→20° bylevel;spawn.3monto ramp.
- reset: yaw0; clear inherited base velocity; reset_rolling_entry applies coherent base+wheel rolling speed .25–.45m/s.
- key_rewards: upright3(std.2),alive1,wheel_glide2(cap.35m/s),heading_hold1.5,feet_flat−2,neck_action_rate−.5,neck_joint_pos−.75,torques−.001,action_rate−1.
- curriculum: deletes ALL inherited curricula, including wheel-friction and CoM ramps; retains only terrain_levels_slope. Promote distance>0.4×15=6m; demote<0.2×15=3m.
- play: default max_init_terrain_level=None permits all rows; optional SLOPE_PLAY_DIFFICULTY fixes difficulty0–1; inherited noise/DR remain; terrain curriculum remains.
- 轮轴摩擦课程（iteration,value）：[[0, 0]]

### RollerStandUp

来源：`/workspace/scratch/9f94b8b8f4de/training-actions-update/analysis/official-sources/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_roller_standup_env_cfg.py`:135

- terrain: plane
- reset: ground-state event runs last; prone/supine z.076–.09,standing.134–.144;standing tilt±10°; no seated bucket.
- key_rewards: HOMElegs8+L1weight5; height target.138m gaussian4(std.04)+4(std.015)+L1weight30; upward velocity3; upright linear6/sharp6; multiplicative composite15; gentle_rise+.02(self-negative); torque_rate−.2. action_rate configured−.6, curriculum−.4/−.8/−1 afterstage applies.
- play: optional STANDUP_PLAY_FACE_UP fixes supine probability and removes only ground_state_mix; unset defaults to curriculum step0 (0% supine). Other DR/noise/curricula remain, including high initial wheel drag.
- static_issue: _LEG_JOINTS=[0,1,2,3,4,11,12,13,14,15] are raw18slot indices, but pose_target_match,pose_l1_penalty,standing_composite_score now index14Dservo views.14/15 are out ofbounds.
- 轮轴摩擦课程（iteration,value）：[[0, 0.05], [1000, 0.02], [2000, 0.008], [3000, 0.003], [4000, 0.0015]]

### Spin

来源：`/workspace/scratch/9f94b8b8f4de/training-actions-update/analysis/official-sources/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_spin_env_cfg.py`:87

- terrain: plane
- reset: HOME joints; base forward velocity0–.3m/s; initial wheel speeds not coherently updated.
- key_rewards: yaw rate gaussian6(std1.5)+L1weight+.5; position drift−3 withlaunchfactor.2; differential wheel1; legantisym1→.5@1500→.25@3000; grounded.5; keeps upright2 androll/pitch angular penalty−.05; deliberately removes angular_momentum; head_yaw not held to HOME.
- play: play argument unused; training noise/DR/curricula retained.
- static_issue: No explicit expand_bam_friction_fields startup event; actual2worldreset+2step passed. Passive wheel selector ^passive_.* is broad but no SpinBacklash registry currently exists.
- 轮轴摩擦课程（iteration,value）：[[0, 0]]

## 需要短步核验的明确源码问题

1. RollerStandUp 的 _LEG_JOINTS 仍按含轮子的18槽编号，包含14、15。但被调的pose_target_match / pose_l1_penalty / standing_composite_score先抽成14维servo视图再索引，独立2world测试已在首步pose_target_match确认IndexError: index14越界size14。该问题在两个SHA都存在，不是这次新增变化。
2. RollerCrouch与Spin从mjlab基础直接构造，没有Rollers的expand_bam_friction_fields startup事件。实际2world reset+2step两者都通过：wheel_friction事件已展开dof_frictionloss，BAM阻尼写入是相同标量，因此未证实运行故障。
3. 不可照抄注释：Crouch顶部docstring写4s，但实际常量=5s；RelativeHeadingVelocityCommand的docstring说正=CW，但实际_update_command是target_yaw−current_yaw，正=CCW。
4. 默认play不是最终课程评估：Rollers/Swizzle/Crouch/Spin的play参数没有任何分支；RollerStandUp默认依旧0%背躺且初始轮阻0.05，只有设STANDUP_PLAY_FACE_UP才覆盖背躺比例，但不覆盖轮阻课程。

## 文件

- official-roller-audit.json：可机读的共享结论、六族摘要与实际train/play factory配置、源文件hash及证据位置。
- smoke-frozen.json / smoke-frozen.log：只读官方factory，两环境reset+2step短测，零动作，不训练、不接硬件。

## 本地中控适配修复与读回（R1.5.21）

已按root授权在工作副本的 `training/official_adapter.py` 修复 RollerStandUp 三个姿态奖励的18槽→14槽索引；按实际关节名同时映射 `joint_indices` 与可选 `target_overrides`，右腿11–15→9–13、颈头7–10→5–8，不改reset/events或奖励权重。describe/train/export共用适配路径并记录校正receipt。上面的官方原源码失败记录继续保留，不代表本地修后仍失败。

专用测试6项通过：实际HD1910 2环境reset+10step，actor61与reward均有限；三种reward的腿/颈目标向量正确；幂等、原配置不被部分写坏、describe/train/export一致；真实脚面与轮胎摩擦/轮轴阻力读回不改变状态。完整日志 `adapter-tests.log`。first-step `friction_readback` 是单次post-DR参数读回，不是长期随机化覆盖证明或任务成功率。

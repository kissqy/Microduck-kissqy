**简体中文** | [English](official-task-parameter-audit.en.md) | [Русский](official-task-parameter-audit.ru.md)

# 官方动作逐任务参数核验（2026-10-07）

训练保持 `8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec`，对照当前 develop `273afe0b31c4ab365b9ff806a927b63ac92b5ddd`。实际导入两版注册器得到同样33个上游任务；本地左脚踢球2个别名调用官方参数化工厂，因此中控共35项。不是按 README 概述拼接不存在的组合。

证据：`official-task-parameter-matrix.json` 逐任务保留事件、参数、奖励、课程、终止、动作、观测、优化器和 train/play 差别；`official-resolved-*.json` 是未精简的实际工厂输出；`official-compiled-physics.json` 是原官方9种机器人 Entity 实编译（未套 HD1910，未启动随机化）。

## 实际注册组合

| 族 | 数量 | Rough | Backlash | 实际地形 / 备注 |
|---|---:|---|---|---|
| BallKick | 2 | 无 | 有 | 仅平面 |
| GroundPick | 4 | 有 | 有 | 平面 / Rough generator |
| RollerCrouch | 2 | 无 | 有 | 平面；轮滑硬件 |
| RollerSlope | 2 | 无 | 有 | ID 含 Flat，实际为坡面 generator |
| RollerStandUp | 1 | 无 | 无 | 平面；轮滑硬件 |
| Roulade | 1 | 无 | 无 | 仅平面 |
| SitStand | 4 | 有 | 有 | 平面 / Rough generator |
| Spin | 1 | 无 | 无 | 平面；轮滑硬件 |
| StandUp | 4 | 有 | 有 | 平面 / Rough generator |
| VelStand | 4 | 有 | 有 | 平面 / Rough generator |
| Velocity | 4 | 有 | 有 | 平面 / Rough generator |
| RollersVelocity | 2 | 无 | 有 | 平面；轮滑硬件 |
| Swizzle | 2 | 无 | 有 | 平面；轮滑硬件 |

Roulade、RollerStandUp、Spin 没有注册 Backlash；任何轮滑族都没有 Rough 注册。前滚翻当前既无 Rough 也无 Backlash。六轮滑族完整命令、轮轴课程和短步结果见 `roller-audit/official-roller-audit.zh-CN.md`。

## 不能混淆的真实物理

- 全部50 Hz：物理步5 ms、decimation4；14主动关节，actor61维。动作 Home + scale×原始策略输出，官方scale1；无动作目标EMA。head_pose_bias 的奖励记忆不是动作滤波。
- 官方原件是 XL330 BAM M6、P200；用户中控是 HD1910 P5，两者数值不可直接互比。原件 Entity 实建读回：kt=0.3660134969、R=2.8113923539、armature=0.0018077433、max_pwm=1、**BAM默认max_current=1.75 A**。即使 env cfg 未显式写电流上限，不能说没有限流。原件静止电机毛扭矩上界约0.64052 N·m，未扣摩擦、不是实测连续扭矩。
- 官方电压startup6.5–8.2 V、负载压降gain0–0.2、最低6 V；动作执行延迟3–6物理步即15–30 ms。IMU通常0–1控制步；GroundPick为0–3，即0–60 ms；joint velocity固定1控制步。具体噪声、保持概率和更新周期逐项在JSON。
- 原件机器人体质量737.24318 g，轮滑模型736.82962 g；不能将原件标成用户820 g。中控当次35项实编译另列studio_inspection_summary：全部默认HD1910 P5/scale1，无动作EMA；普通脚底820.000 g，轮滑同一质量适配后819.58644 g，应如实记录0.41356 g差别而不是伪称精确相同。
- 足地摩擦：所有非轮滑任务的 foot_friction 是 startup、uniform、绝对范围[0.7,1.3]、左右共享采样；mjlab默认axes=[0]，只随机滑动摩擦。不会每次reset重抽。官方play仍保留该事件。
- 扭转/滚动摩擦槽常见[0.005,0.0001]，没有相应随机化；脚的condim3仅启用滑动。普通地面接触模型经FULL_COLLISION后非足named collision多为condim1。最终接触维度还受双方priority等影响，不能只凭一个geom槽说所有碰撞都训练摩擦。
- 轮滑碰撞轮胎为 **mesh（MuJoCo type7）**，四个被动wheel铰链交错在主动关节之间；轮胎condim3、friction[1,0.005,0.0001]。六族没有geom_friction随机化。randomize_wheel_friction改轮轴dof_frictionloss，是轴承阻力；多数课程每一阶段范围上下限相同。
- BAM friction_scale通常reset[0.9,1.1]，作用于电机内部摩擦，与足地摩擦独立。armature通常reset[0.9,1.1]。逐任务实际事件和选择器已列出，未把注释中的开关默认当作实际事件。
- 碰撞模型不能一概而论：Velocity用walk；StandUp/SitStand/GroundPick/BallKick/Roulade用groundcontact；VelStand实际用allcollisions。constants里“No task uses it yet”的注释已落后于注册执行。Backlash选相应模型，14轴每轴±1°。

## Rough 与 play 的隐藏差别

粗糙地形声明10×20，实际导入注册器后变成5×5：train/play共享generator，play改动行列。generator.curriculum从未声明True，mjlab默认就是False，因此不能说play把True关掉，也不应静默改成True。terrain_levels是另一层环境课程。此次保留成熟训练实际5×5配置和随机难度行为。
play=True不是统一的关闭随机化开关。各类噪声、BAM/地面随机化与课程多仍存在，部分任务反而提高推扰频率；Rollers/Swizzle/Crouch/Spin工厂甚至没有play分支。JSON逐项记录差别，不能以文档“评估”二字断言稳定、无噪声。

## 原官方故障与本地最小修复

RollerStandUp 原件首步确实因索引14超出14维崩溃：奖励已用servo-only视图，配置仍用包含4轮的18槽旧编号。两版本同样存在。中控adapter只将三个受影响reward的joint_indices和target_overrides按真实关节名映射到14槽；不改reset原始关节编号，不改奖励权重或课程。独立5项测试含2环境10步通过。原件失败日志保留，不能将已注册直接等同可运行。
Crouch/Spin缺显式expand_bam_friction_fields事件，但官方2环境reset+2step均通过；轮阻事件已展开所需field，不能仅凭静态缺事件断言训练必坏。仍在audit警告中明确需要实际步进。

## 冻结版本与当前 develop

注册器、Backlash包装器、机器人常量、全部非VelStand env cfg、轮滑六族和symmetry文件字节相同。变化集中VelStand、mdp新增body控制支持与distill。当前开启站立时body命令，roll/pitch约±12°、z−2.5至+1cm，相关奖励/BC路由改变；ENABLE_YAW_FIX仍False。为了补动作无需升级这些成熟训练行为，继续固定8d0。

## 逐任务快速索引

| 任务ID | 秒 | 接触摩擦训练 / play | 初始训练IMU延迟 | robot spec |
|---|---:|---|---|---|
| `Mjlab-BallKick-Flat-Backlash-MicroDuck` | 5 | startup0.7–1.3 / 保留 | 0–1步 | `get_backlash_spec` |
| `Mjlab-BallKick-Flat-MicroDuck` | 5 | startup0.7–1.3 / 保留 | 0–1步 | `get_standup_spec` |
| `Mjlab-GroundPick-Flat-Backlash-MicroDuck` | 20 | startup0.7–1.3 / 保留 | 0–3步 | `get_backlash_spec` |
| `Mjlab-GroundPick-Flat-MicroDuck` | 20 | startup0.7–1.3 / 保留 | 0–3步 | `get_ground_pick_spec` |
| `Mjlab-GroundPick-Rough-Backlash-MicroDuck` | 20 | startup0.7–1.3 / 保留 | 0–3步 | `get_backlash_spec` |
| `Mjlab-GroundPick-Rough-MicroDuck` | 20 | startup0.7–1.3 / 保留 | 0–3步 | `get_ground_pick_spec` |
| `Mjlab-RollerCrouch-Flat-Backlash-MicroDuck` | 20 | 无geom DR / 无 | 0–1步 | `get_rollers_backlash_spec` |
| `Mjlab-RollerCrouch-Flat-MicroDuck` | 20 | 无geom DR / 无 | 0–1步 | `get_walk_rollers_spec` |
| `Mjlab-RollerSlope-Flat-Backlash-MicroDuck` | 20 | 无geom DR / 无 | 0–1步 | `get_rollers_backlash_spec` |
| `Mjlab-RollerSlope-Flat-MicroDuck` | 20 | 无geom DR / 无 | 0–1步 | `get_walk_rollers_spec` |
| `Mjlab-RollerStandUp-Flat-MicroDuck` | 6 | 无geom DR / 无 | 0–1步 | `get_walk_rollers_spec` |
| `Mjlab-Roulade-Flat-MicroDuck` | 5 | startup0.7–1.3 / 保留 | 0–1步 | `get_standup_spec` |
| `Mjlab-SitStand-Flat-Backlash-MicroDuck` | 12 | startup0.7–1.3 / 保留 | 0–1步 | `get_backlash_spec` |
| `Mjlab-SitStand-Flat-MicroDuck` | 12 | startup0.7–1.3 / 保留 | 0–1步 | `get_standup_spec` |
| `Mjlab-SitStand-Rough-Backlash-MicroDuck` | 12 | startup0.7–1.3 / 保留 | 0–1步 | `get_backlash_spec` |
| `Mjlab-SitStand-Rough-MicroDuck` | 12 | startup0.7–1.3 / 保留 | 0–1步 | `get_standup_spec` |
| `Mjlab-Spin-Flat-MicroDuck` | 20 | 无geom DR / 无 | 0–1步 | `get_walk_rollers_spec` |
| `Mjlab-StandUp-Flat-Backlash-MicroDuck` | 6 | startup0.7–1.3 / 保留 | 0–1步 | `get_backlash_spec` |
| `Mjlab-StandUp-Flat-MicroDuck` | 6 | startup0.7–1.3 / 保留 | 0–1步 | `get_standup_spec` |
| `Mjlab-StandUp-Rough-Backlash-MicroDuck` | 6 | startup0.7–1.3 / 保留 | 0–1步 | `get_backlash_spec` |
| `Mjlab-StandUp-Rough-MicroDuck` | 6 | startup0.7–1.3 / 保留 | 0–1步 | `get_standup_spec` |
| `Mjlab-VelStand-Flat-Backlash-MicroDuck` | 20 | startup0.7–1.3 / 保留 | 0–1步 | `get_allcollisions_backlash_spec` |
| `Mjlab-VelStand-Flat-MicroDuck` | 20 | startup0.7–1.3 / 保留 | 0–1步 | `get_allcollisions_spec` |
| `Mjlab-VelStand-Rough-Backlash-MicroDuck` | 20 | startup0.7–1.3 / 保留 | 0–1步 | `get_allcollisions_backlash_spec` |
| `Mjlab-VelStand-Rough-MicroDuck` | 20 | startup0.7–1.3 / 保留 | 0–1步 | `get_allcollisions_spec` |
| `Mjlab-Velocity-Flat-Backlash-MicroDuck` | 20 | startup0.7–1.3 / 保留 | 0–1步 | `get_walk_backlash_spec` |
| `Mjlab-Velocity-Flat-Backlash-MicroDuck-Rollers` | 20 | 无geom DR / 无 | 0–1步 | `get_rollers_backlash_spec` |
| `Mjlab-Velocity-Flat-MicroDuck` | 20 | startup0.7–1.3 / 保留 | 0–1步 | `get_walk_spec` |
| `Mjlab-Velocity-Flat-MicroDuck-Rollers` | 20 | 无geom DR / 无 | 0–1步 | `get_walk_rollers_spec` |
| `Mjlab-Velocity-Rough-Backlash-MicroDuck` | 20 | startup0.7–1.3 / 保留 | 0–1步 | `get_walk_backlash_spec` |
| `Mjlab-Velocity-Rough-MicroDuck` | 20 | startup0.7–1.3 / 保留 | 0–1步 | `get_walk_spec` |
| `Mjlab-Velocity-Swizzle-Backlash-MicroDuck` | 20 | 无geom DR / 无 | 0–1步 | `get_rollers_backlash_spec` |
| `Mjlab-Velocity-Swizzle-MicroDuck` | 20 | 无geom DR / 无 | 0–1步 | `get_walk_rollers_spec` |

## 主源定位

- BallKick：[工厂源码](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_ball_kick_env_cfg.py#L132)。
- GroundPick：[工厂源码](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_ground_pick_env_cfg.py#L114)。
- RollerCrouch：[工厂源码](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_roller_crouch_env_cfg.py#L116)。
- RollerSlope：[工厂源码](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_roller_slope_env_cfg.py#L66)。
- RollerStandUp：[工厂源码](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_roller_standup_env_cfg.py#L135)。
- Roulade：[工厂源码](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_roulade_env_cfg.py#L147)。
- SitStand：[工厂源码](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_sitstand_env_cfg.py#L195)。
- Spin：[工厂源码](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_spin_env_cfg.py#L87)。
- StandUp：[工厂源码](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_standup_env_cfg.py#L152)。
- VelStand：[工厂源码](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_velstand_env_cfg.py#L377)。
- Velocity：[工厂源码](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_velocity_env_cfg.py#L193)。
- RollersVelocity：[工厂源码](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_velocity_rollers_env_cfg.py#L85)。
- Swizzle：[工厂源码](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_velocity_swizzle_env_cfg.py#L34)。
- `src/mjlab_microduck/tasks/__init__.py`：[第78行](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/__init__.py#L78)。
- `src/mjlab_microduck/robot/microduck_constants.py`：[第142行](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/robot/microduck_constants.py#L142)。
- `src/mjlab_microduck/tasks/backlash.py`：[第42行](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/backlash.py#L42)。
- `src/mjlab_microduck/tasks/microduck_velocity_env_cfg.py`：[第130行](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_velocity_env_cfg.py#L130)。

mjlab1.3.0依赖源码：`envs/mdp/dr/geom.py:117–145`（geom_friction默认轴）；`terrains/terrain_generator.py:92`（curriculum默认False）；依赖完整版本记录在JSON。报告只证明配置与短步可执行，不证明新任务已训练收敛或真机可用。

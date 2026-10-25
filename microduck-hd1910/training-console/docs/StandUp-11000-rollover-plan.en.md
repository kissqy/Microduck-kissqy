[简体中文](StandUp-11000-rollover-plan.zh-CN.md) | **English** | [Русский](StandUp-11000-rollover-plan.ru.md)

# 11000-iteration recovery teacher: rollover curriculum proposal

**Research archive, October 6, 2026:** analysis / proposed experiments for a separate recovery model. This does not imply the current console includes those special buttons or implements these training changes. Use [the current guide](../USER-GUIDE.en.md). At R1.5.17 only evaluation fixes were completed; this plan was not added to recipes or started.

## 1. Assessment

The user observed reliable prone recovery but no autonomous rollover when supine; lifting a foot / helping a little let it continue and stand. Investigate the transition from stuck supine contact to states the policy can handle. This does not identify geometry, neck support, or exploration cost without trajectories / contact records.

**A real short simulation replay narrows the claim: original 11000 succeeds from one sampled fully supine state with default joints.** It cannot be described as failing every supine start. Reproduce actual failures before remediation; repeatedly training a successful default supine state could miss them.

Branch the original checkpoint to preserve skills. Record stuck and slightly assisted successful states, find their boundary, and first vary initial-state distribution / difficulty. Only if the boundary fails to expand, reduce one penalty in the recorded upstream order.

### Two original-model replays

| Start | Initial gravity projection | Total time including 1 second maintained success | Final height / tilt |
| --- | --- | ---: | --- |
| Fully supine, default joints |`[-1,0,0]`|1.48 s|115.60 mm/0.983°|
| Prone, default joints |Approximately`[1,0,0]`|1.36 s|116.08 mm/0.387°|

Original verified ONNX / robot / action / observation contracts, P5, scale 1, no filtering, flat specialized evaluation, zero commands / initial velocity; lowest collidable geom 1 mmabove ground. Success: height≥105 mm / tilt≤15°for 1 second. Counting begins at first post-reset step, without prior policy action or pre-success episode reset.

One unseeded episode per category retains yaw / physics randomization. It proves at least one successful supine initial state, not success rate, settled physical contacts, real stuck feet, or foot contact. No videos / full trajectories were saved; no specific rollover maneuver can be inferred. Evidence:`recovery-teacher11000-check.json`.

## 2. Actual model and training readback

Source: user's `倒地老师_4096_11000_无缩放滤波.zip`, including training-config / request, env / agent YAML, checkpoint, and ONNX.

| Item | Actual value |
| --- | --- |
| Task |`Mjlab-StandUp-Rough-Backlash-MicroDuck`|
| Upstream |microduck_rl`8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec`|
| Environments / rollout |4096/24 policy steps|
| Control / episode |50 Hz/6 s|
| Checkpoint |11000|
| Accumulated environment steps |264024|
| Samples |1, 081, 442, 304;≈11001 reference iterations due to zero-based saving|
| Provenance |training_run_readback; request snapshot matches|
| Actions |scale 1.0, head / legalpha 1.0, P5|
| Robot |820 gHD1910, official chassis, Backlash|
| Saved Adam learning rate |0.000170859375|
|14 Dstandard deviation |0.14477–0.21971, mean≈0.16939|
| Symmetry |null|
| ONNX SHA256 |`a481d9f211f31d9476ab1a319fe362a21ef0879d9fa59442a122845af598268c`|

ZIP / pickle opcodes / tensor storage were statically inspected; no training ran. Nonzero standard deviation does not rule out inadequate coordinated multistep exploration; do not reset it directly to a new model's 1.0.

### Original curriculum coverage

|4096-reference stage|Standing|Sitting|Prone|Supine / side|
|---|---:|---:|---:|---:|
|0–599|40%|40%|20%|0%|
|600–1499|25%|30%|35%|10%|
|1500–2499|20%|25%|30%|25%|
|2500+|15%|20%|30%|35%|

Supine was present, but face_up_roll_max=π/2 samples−90°to+90°around body axis, including near-side states, without a distinct fully flat category. Within±15°of flat, the theoretical reset probability is 35%×30°/180°=5.83%. This is orientation sampling, not measured settled back contact or proof of insufficient total samples.

Joint position / velocity offsets are(0, 0); sitting separately overrides joints, but back starts largely HOMElegs / neck. Height≈0.05–0.09 m is assigned without passive settling. Body orientation alone does not reproduce stuck joint / contact combinations.

## 3. Upstream / community evidence

### Official StandUp acknowledges back-recovery freezing and seed differences

Frozen configuration records seed-dependent back recovery and±90°roll starts as a reverse curriculum from near-completed rollover. Smoothness / angular-velocity costs can block discovery; on freezing, first relax body_ang_vel−0.05→−0.025, then consider final action-rate−0.6. Existing user training already has side-roll randomization; re-enabling it is not a new fix or a seed-independent guarantee.

Sources:[StandUp](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_standup_env_cfg.py), lines 489–494, 720–726, 853–873, 961–968;[mdp](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/mdp.py), 4363–4470. Actual pinned Git sources were read.

### More supine samples alone can fail

The [duckman-microduck author](https://github.com/nyle-prosal/duckman-microduck) reported 4096 environments/7000 iterations: sitting 4/4, prone 6/6, supine 0/8. Raising final supine to 60%and training≈1100 more still gave 0/8. Near-side reverse starts remained proposed, not completed. Different hardware / model / protocol means these are not this model's measurements, only evidence against proportion alone being sufficient. [Training record](https://github.com/nyle-prosal/duckman-microduck/blob/main/training/standup/README.md).

### Train actual stuck joints with orientation

[Summer Roh](https://www.linkedin.com/posts/summer-roh-a687b1142_nvidia-activity-7504149415503249408-UQm_) reported stuck raised hips / folded neck, then saved failed joints and combined tilt / head-neck initial curricula without reward changes, reporting prone / supine 0%→100%. Both converged on the same stuck state. This supports actual-failure-state curricula, but sample count, seeds, and code were not published there; self-reported 100%does not promise this model's result. The post did not explicitly claim earlier reward / PPO changes had failed.

### VelStand and PR54 boundaries

Official VelStand records a walking warm start, std≈0.2, still failing to discover recovery after lower falling costs until a recovery teacher helped. An open PR leaves rapidly rotating fallen frames to PPO and imitates teachers only when calmer, reporting better supine recovery. Lower penalties do not guarantee discovery, and failed teacher states should not force imitation. This separate teacher should not directly copy joint BC masks. PR54 was open / unmerged when reviewed. [Pinned VelStand](https://github.com/pollen-robotics/microduck_rl/blob/cb70b792312d559a4da09064d92009079671815f/src/mjlab_microduck/tasks/microduck_velstand_env_cfg.py),[PR54](https://github.com/pollen-robotics/microduck_rl/pull/54).

### Papers support mechanisms, not transferred parameters

[Reverse Curriculum Generation, CoRL2017](https://proceedings.mlr.press/v78/florensa17a.html) expands from successful starts toward harder ones, matching slight assistance enabling continuation. [HumanUP](https://arxiv.org/html/2502.12152v2) discovers recovery trajectories before strengthening smoothness / execution constraints and separately learns rollover / rising. It is not the original reverse-curriculum paper; G1 joints, drop heights, actions, budgets cannot be copied to Microduck.

## 4. Proposed first experiment

### 4.1 Comparable baseline

Evaluate original 11000 with fixed supine, left / right side, andprone. R1.5.17 fixes roll, zeros velocity, and places the lowest collidable geom 1 mmabove ground. This is geometric initialization, not proof of settled contacts or foot contact from height / tilt.

**First reproduce the user's actual stuck state in ordinary viewing; record joints, gravity, velocity, commands, terrain, contacts.** Record the slightly lifted / rolled state that succeeds. If HOME-joint 0°supine keeps succeeding, it is not the principal remediation target.

Vary tilt or small leg configurations around the reproduced failure to find reachable success boundaries. Candidate 90°, 60°, 45°, 30°, 15°, 0°means 0°flat; these are search points, not measured results. Record left / right separately; search joint / contact configurations if those dominate. Collect leg / neck / head states and generate bounded physically plausible contacts. Never assume 14 servos are contiguous qpos[7+j]; Backlash interleaves passive joints, use upstream servo mapping.

### 4.2 Branch original PT and vary initial states first

Proposed, untested first distribution:

| Reset category | Share | Purpose |
| --- | ---: | --- |
|Successful boundary near actual stuck state|40%|Complete recovery after slight lift / tilt; allocate sides / joints by measured boundary|
|Reproduced fully supine failure|20%|Actual stuck leg / neck / contact, not repeatedly successful HOME|
|Known prone recovery|20%|Preserve post-rollover rising|
|Sit-to-stand|10%|Preserve existing recovery|
|Standing|10%|Preserve endpoint stability|

This 60%back budget combines actual boundaries / failures, unlike only face_up_prob 0.6. Implement only after reliable reproduction; otherwise align state / terrain / commands / contacts. Conservative comparison can keep total 35%and redistribute within it; do not launch two large runs simultaneously.

Do not assume 30°is the starting boundary. Use observed successful states; one side can begin easier than the other. Assistance constructs initial states, without hidden forces during policy execution. Train an initial 500 extra iterations at 4096 then evaluate; continue if improving.500 is an observation window, not convergence promise. Do not prequeue 10000 more before improvement.

### 4.3 Advance by success boundaries

With sustained complete recovery and retained prone / standing skills, reduce tilt / help toward the failed state: for angle-driven cases 5–10°steps, or validated joint / contact changes. Results determine advancement, not an unconditional 500-iteration schedule. Increase target failures once autonomous recovery emerges, retaining boundary / old-skill practice.

Measure leaving the stuck supine contact and final maintained standing separately. Rolling to one side or rising reward is not full success. First milestone: at least one reproducibly autonomous recovery+stand in 10 checks of formerly failed states; 1/10 only establishes emerging behavior. Passing default HOME supine does not replace the target set. Then 20/50 checks and prone retests, with counts / thresholds fixed beforehand rather than selected attractive replays.

Fixed categories retain yaw / position / physics variation but mainly HOME joints. Repeating identical deterministic starts is not independent physical-fall evidence. Use saved distinct feasible joints / contacts and explicit seeds; compare original / new models on the same set.

### 4.4 Conditions to retain

Keep P5, scale 1, head / legalpha 1, HD1910 mass / motor / friction / backlash, network, normalization, PPO, 6-second episodes, and original Rough / Backlash. Flat evaluation isolates observation without also changing training terrain. Verify contact / actual tilt on the appropriate ground; out-of-category states cannot be labeled strict flat supine. Preserve actor / critic / normalizer / optimizer / std and original 11000 files.

## 5. If the new curriculum still stalls

Check actual runtime event updates, boundary rewards, and loaded learning-rate continuity first. If correct but no expansion, change only:

```text
body_ang_vel: -0.05 → -0.025
```

This is upstream's recorded back-freezing recommendation. Keep other rewards / PPO. If action-change cost still blocks discovery, independently relax final action_rate_l 2−1.0→−0.6; change the curriculum final value, not an initial value it overwrites.

Do not simultaneously remove penalties, increase P, reset std, change gamma, extend rollout / episode. Change episode length only after valid rollover is truncated at 6 seconds. If feasible boundary curricula / modest penalty reduction still yield no connecting trajectory, consider explicit rollover exploration / progress rewards and test for permanent-side / rest / repeated-score exploits. Teachers can preserve prone / standing but should not force imitation where they fail.

## 6. Resume implementation requirements

1. **Separate total clock and rollover-stage progress.** Old checkpoint is at final old curricula. Save a separate stage origin / progress; zeroing total time would restart standing / sitting / prone / randomization. Changing initial events alone is overwritten at first old-curriculum reset.
2. **Update live event managers.** mjlab 1.3.0 manager terms are not interchangeable with env.cfg.events. Evaluation fixed this; training needs independent stage logic.
3. **Synchronize loaded learning rate.** rsl-rl-lib 5.0.1 loads optimizer without updating algorithm learning_rate. Saved≈0.00017086 versus config 0.001 can be overwritten upward by first KL adaptation. Synchronize actual saved optimizer / algorithm rate.
4. **Do not borrow joint warm-start flags.** Sampling alignment restores cumulative clock; MICRODUCK_WARM_START=1 alone can mix iteration 0/final curricula. Define explicit StandUp remediation stages.
5. **Evaluate by pose.** Record initial pose / joints / contacts, resets, rollover / rise timing; compare original / new. Exclude computational-error trials with explanations; normal timeout is failure.

## 7. Delivery and next boundary

R1.5.17 fixed inaccurate evaluation and supplied fixed-pose checks. Short original-model replays show at least one successful supine start. Next, save / reproduce actual failure and slightly assisted success, define their curriculum, then branch 11000 PT for one short block. Continue only according to autonomous recovery in the original failure set.

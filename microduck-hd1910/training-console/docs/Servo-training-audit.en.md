[简体中文](Servo-training-audit.zh-CN.md) | **English** | [Русский](Servo-training-audit.ru.md)

# Feetech servos, upstream configuration, and joint-training review

**Technical research archive, October 3, 2026:** this records a historical hardware / training-source review, not current operating instructions. Use [the current user guide](../USER-GUIDE.en.md) for features and parameters. Reviewed console R1.5.3, target runtime contract 0.15.1.

The review found substantive console defects and another detailed HD1910 identification dataset. The user's joint-run records and both teacher PTs were unavailable, so a source defect cannot be identified as the cause of that run's swaying.

## 1. Training provenance

The baseline combines frozen Pollen tasks, Luwu Feetech actuator parameters, and an 820 g local-robot adaptation. It neither copies the complete Luwu robot nor retains original XL330 dynamics.

| Component | Baseline at review |
| --- | --- |
| Tasks / rewards / reset / termination / observations / PPO |`microduck_rl@8d0db749`; all 12 ordinary-foot tasks compared |
| Joint training |Official protected-fall VelStand, walking warm start, walking / recovery dual-teacher BC; user-selected local teachers |
| Curriculum time |Since R1.5.2, sample-equivalent `4096×24`; 2048 environments double thresholds, 1024 quadruple. Equal samples do not guarantee equal optimization |
| Save / logs |Every 1000 iterations; local TensorBoard; independently surviving backend |
| Actuator |Original Luwu `1910_m6.json`, P5, 7.4–8.0 V, min 7 V, 3–6×5 ms command delay |
| Feetech reset |fanhao 375 per-environment target-history reset correction; upstream friction randomization retained |
| Robot |Official chassis, 15×23 g servos, 3 g head addition / remainder torso, total 820 g. Existing mass-recipe inertia scaling, not measured full local inertia |
| Actions |Training scale 1.0, no additional 0.7; deployment follows contract |
| Calibration |Imported zeros / directions / IMU mount retained |

Static differences across 12 loaded defaults are actuator, robot / mass construction, and save interval; `data/official-studio-config-diff.json` records them. This precedes local teacher binding / sample-time conversion and is not a live run snapshot.

## 2. Additional public sources

| Source | Evidence | Transfer limits |
| --- | --- | --- |
| [Luwu XgoDuck](https://github.com/LuwuDynamics/xgoduck_rl/tree/326d77a1122870bdefa2c36403937502c958e69c) |Complete training, M6, geometry / inertia, task adaptation |Different chassis; do not copy geometry, HOME, height |
| [fanhao 375 baseline](https://github.com/fanhao375/microduck-replica/blob/master/software/training/docs/hd1910-baseline.md) |Luwu provenance, history initialization / reset, tests |Relevant fix adopted; author had not completed local physical gait acceptance |
| [JoyandAI HD1910](https://github.com/JoyandAI/microduck_rl/tree/22916b9d82f250caa563ed9a56976eb33243fb91/vendor/bam/bam/params/hd1910) |M1–M6, alternate fits, characterization separating measurement / readback / spec / fit / assumptions |Supply / controller / gains / model differ; cannot just swap JSON |
| [JoyandAI actuator](https://github.com/JoyandAI/microduck_rl/blob/22916b9d82f250caa563ed9a56976eb33243fb91/vendor/bam/bam/feetech/actuator.py) |HD1910 control, P / D conversion, current / target-rate options |D-strength assumptions remain unverified; not accepted local parameters |
| [OptiDuck](https://github.com/sim336/OptiDuck) |HD1910 training, ONNX deployment, geometry / failure records |Recorded jitter / falls during recovery / walk switching, not claimed stable walking |

Search also covered upstream issues / community reproductions. No complete public benchmark was found matching official chassis, 820 g, same HD1910 firmware / supply, this dual-teacher version, with weights / logs / extended physical validation. Video / community successes require actual configuration for reproduction.

### Luwu provides more than 20 BAM fields

XgoDuck includes its own 0.8 kg geometry / inertia,±24°hip-pitch HOME, standing / sitting heights, foot friction 0.4–1.5, noise, and rewards. Recovery drops from air, freezes 2 seconds, then acts in 8-second episodes. This robot retains frozen official-chassis tasks rather than those geometry changes.

That commit does not register a new XgoDuck dual-teacher VelStand. Older MicroDuck VelStand is not the current protected-fall version; other Luwu results are not a benchmark for this joint task. Local BAM matches original SHA256 `ef2d51adfb1cc0831b9b02ca19aa9176fceecdf725148d084378d7d9a64afceb`.

### Another HD1910 identification route

| Item | Luwu route | JoyandAI pinned 22916 b 9 d |
| --- | --- | --- |
| Controller |STS3215 Actuator|Custom HD1910 Actuator|
| Model |M6|M5, with M1–M6 comparisons|
| Supply |7.4–8.0 V, min 7 V|Regulated bench / robot 5 V; training 4.75–5.25 V, min 4 V|
| Firmware P |5|32, reported servo readback|
| Queue delay |15–30 ms|20–35 ms|
| kt |0.623761 N·m / A|0.692 N·m / A|
| R |4.910192Ω|3.75Ω|
| Evidence |Published identification|72 pendulum records: 2 arms×3 weights×4 trajectories×3 repeats; 48 fit/24 validation|

This is not multiplying all Feetech parameters by 0.7. Raw P cannot compare across controllers; voltage and gain conversion must match. JoyandAI marks D strength, thermal derating, unit consistency as pending, with corrected validation-error descriptions. The review adds attribution / comparison without changing defaults or claiming superiority.

## 3. Fields used and unused

| Field | Actual path |
| --- | --- |
| kt / R / armature / friction |Model computation plus voltage, delay, gains |
| error_gain_ratio |PWM response with P / error conversion, not angle scaling |
| max_velocity 100 |Internal target-angle rate limit, not measured unloaded / walking speed |
| q_offset |Identification record; unused by this bam.mjlab path, not robot zero_raw |
| command_delay≈0.006 s |Unused; actual queue 3–6 physics steps; do not add 6 ms |
| Friction 0.9–1.1 |BAM velocity-independent budget, not foot friction / all dynamics |
| Foot friction |Official 0.7–1.3, independent |
| Armature 0.9–1.1/CoM / mass / inertia / noise |Task-specific upstream events retained |
| XL330 ratings / registers / thermal limits |Hardware reference, not full firmware simulation or Feetech transfer |
| Hardware D / I |STS3215 path does not fully reproduce PID; kd_scale is back-EMF multiplier, not hardware D |
| Backlash / thermal / unit differences |Ordinary-foot tasks at this review lacked independent backlash joints / local thermal / per-servo identification |

XL330 also has non-JSON constants: controller error conversion, PWM ceiling, current limit. R1.5.3 adds post-build readback: XL330 limit 1.75 A, Feetech model lacks the same limit, which does not imply no physical protection. Gross torque bounds are not continuous ratings.

## 4. Three console defects fixed

1. **BAM titles / units:** array indexing on a dictionary dropped Chinese descriptions. Named fields expose all 20, and two unused fields are marked.
2. **Override path not loaded:** R1.5.0–1.5.2 changed public json_path without refreshing cached parsed path. Reproduction: pagekt 0.7, actual 0.623761. Rebuilding the config object makes loading / compiled inertia follow edits. Only manual overrides are affected; this does not establish wrong default training.
3. **BC hidden in description:** describe / evaluation both cleared bc_cfg, hiding 17 teacher parameters; actual training retained BC. Describe now retains / explains them; evaluate / export still load students only.

Old records affected by BAM caching replay / resume / teacher contracts with original actually loaded parameters and explanatory provenance. Original PT / run records are not rewritten; new overrides work.

## 5. Joint training requires its own checks

Official gating uses walking anchoring at tilt≤25°, recovery teacher above 35°, and PPO between. Recovery-teacher velocity commands are zero; each teacher retains normalization. Walking warm start immediately sets inherited walking curricula to final stages, progressing only new fall / push curricula. An early walking checkpoint may fail those initial commands / randomization despite walking in simple evaluation.

Upstream records recovery imitation damaging walking, then adds walking anchoring, lower BC learning rate, and bounded minibatches. This console uses the corrected dual-teacher version; selecting two teachers does not prove compatible actions / normalization / environment distribution.

R1.5.3 shows walking / recovery gate proportions, imitation loss, velocity reward, and sway penalty. Gate proportion is not success rate; too few fallen frames skip recovery BC. Review actual teacher hashes, warm-start source, 17 BC values, reward components, termination, curriculum clock, BAM readback. Compare teachers and early / current joint checkpoints under identical upright / prone / supine / side / pushed evaluation. Training includes exploration / disturbances; one live duck view is not deployment evidence.

Official thresholds such as stalled torque 0.4 N·m / speed 0.5 rad / s are reward definitions, not measured HD1910 acceptance. Change one only after controlled evidence.

## 6. Is a single-digit average reward good or bad?

It cannot decide alone. Mean reward is rsl-rl's mean cumulative reward over the latest 100 completed episodes. Episode_Reward components divide by maximum episode duration, so the statistics cannot be directly summed. Task, length, curriculum, penalties, dynamics matter. It is neither a percentage nor the parallel total; 1024→4096 does not multiply the mean by 4.

Public examples have no universal passing score:

- [Official SitStand](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/docs/sitstand_policy.md): 140→125 and 131→116 on harder curricula, then recovery; different task.
- [Official joint source](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_velstand_env_cfg.py), run 6 op 8 a 8 u 8: simulation push recovery 88–95% across three seeds, median 2.7 s, not mean reward 88–95. No comparable final mean was obtained.
- [Datawhale 256-environment reproduction](https://github.com/datawhalechina/dive-into-embodied-ai/blob/master/docs/practices/amd/microduck-rl/index.md): 500 iterations mean 5.3664/peak 5.5925, but requested 0.15 m / s yielded≈0.0052 m / s. At 1500, mean 59.0012/peak 62.2754, last checkpoint≈0.0454 m / s, best sampled checkpoint model_750. Rising rewards / last iteration do not mean best gait. Different hardware / task and 4-second playback are not extended robot acceptance.

For falling reward with sway, inspect tracking, early terminations, recovery success, and teacher deviations. Curriculum difficulty alone does not explain away the observation.

## 7. Parameter page and validation scope

Robot / Servo Parameters→Actuator shows 19 training fields, 10 control-model readbacks, 20 BAM fields, 28 specifications, three voltage points each for XL330/HD1910, XL330 shell CoM / inertia, and 110 control-table entries including indirect address / data. Firmware differences / inconsistent source ranges retain notes. Fields:`data/servo_references.json`.

ROBOTIS:[XL330 manual](https://docs.robotis.com/docs/dxl/model_reference/x_series/xl_series/xl330-m288/),[US store](https://robotis.us/products/dynamixel-xl330-m288-t),[inertia](https://www.robotis.com/service/download.php?no=2136). Shell inertia needs coordinate conversion and is not BAM rotor armature. Missing / unmeasured values are not guessed.

Feetech:[HD-1910-C001 specification A/0, September 7, 2026, JoyandAI archive](https://github.com/JoyandAI/OpenMicroDuck/blob/main/hardware_spec/servo/HD-1910-C001%E4%B8%B2%E5%9E%8B%E8%A7%84%E6%A0%BC%E4%B9%A6-20260907.pdf).4.8/6/7.4 V torque / speed / current / rated-load values and factory protections are not local live registers. Spec mass 21±2 g does not replace user-measured 23 g or total 820 g.

Fixes did not change default BAM, supply / P, rewards, or firmware; no ZERO connection or stopped WSL training. See [Verification](Verification.en.md) for executed checks and limits.

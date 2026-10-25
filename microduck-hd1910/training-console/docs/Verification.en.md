[简体中文](Verification.md) | **English** | [Русский](Verification.ru.md)

# R1.5.15 remote-training verification record

The separate R1.5.15, R1.5.10, and R1.5.9 incremental guides were retired during cleanup. Use [the console guide](../README.en.md) for remote training and queues, and [the task audit](audit-0151/official-task-parameter-audit.en.md) for actions. Historical checks remain below. Long server training was not executed for this record.

# R1.5.9 actions and backlash

The [task audit](audit-0151/official-task-parameter-audit.en.md) records combinations and short-step evidence. The following records describe their original versions.

# R1.5.4 · PT / ONNX simulation startup and exit

Reviewed October 3, 2026. `MLPModel has no attribute scale` occurred in an obsolete log in `ConsoleViewer.__init__`, before Viser creation. The line performed no multiplication and was outside training/live observation.

## Fix and executed checks

- Removed `policy.scale` reads without adding attributes or wrappers. Removed unused fixed `inference_scale` fields; old submitted 0.7 is ignored. Models retain source mappings.
- Three actual frozen-upstream CPU/Viser integrations passed. Generated test weights use real saved/loaded MLPModel; generated ONNX runs actual ONNX Runtime. Both lack scale, start ConsoleViewer and the official view, report viewer_ready, advance two physics steps, read pose, and close repeatedly. Objects remain unwrapped and identical observations produce unchanged outputs. Log: `Viewer-policy-upstream.txt`.
- Tests reproduced `Event loop is closed` during exit. Cleanup now releases Viewer before stopping the created Viser server, retaining parent timeouts and training isolation.
- New training ignores old 0.7 and uses scale 1; evaluation/export preserve original 0.7 or 1 without another multiplier.
- Regression batch: 133 tests, 124 passed, 9 optional upstream/viewer integrations not enabled. The three new integrations passed separately. Coverage includes V2 PT/export, original/re-exported ONNX, ignored inference_scale, preserved source scale, liveness, switching, timeouts, and calibration. `Viewer-fix-tests.txt`.
- Two changed scripts passed JavaScript syntax checks. Layout was unchanged, so 4K appearance was not repeated.

Generated weights are not the user's PT or evidence of convergence/physical gait. No ZERO/WSL connection, changes to BAM/calibration/rewards/curricula/weights, or required retraining.

# R1.5.3 · Actuator provenance and joint-training readback

Reviewed October 3, 2026. Adds bilingual/specification information and fixes manual BAM loading and joint descriptions. Defaults, dynamics, rewards, scale 1, 0.15.1 contracts, and calibration remain.

## Executed checks

- Python batch: 130 tests, 124 passed, 6 optional upstream skips. Prior liveness, downloads, simulation, models, and calibration remain. `Servo-audit-tests.txt`.
- Five separate integrations passed with frozen source, locked BAM, and actual mjlab. Manual kt=0.7/armature=0.0022 read back from real objects, changing compiled inertia/torque bounds. Describe retains 17 BC fields; evaluation/export load students only. Bilingual completeness and known ineffective old overrides also pass. `Servo-audit-upstream.txt`.
- All 12 tasks have complete explanations; both joint recipes retain 17 BC fields. Static comparisons in `data/official-studio-config-diff.json` precede teacher binding and sample-clock conversion.
- Actual HTTP Chromium at 3840×2160 checks bilingual actuator/BAM fields, 110-register search, save/restore, joint diagnostics, 12 tasks, 2048/1024 budgets/curricula, V2 teachers, and submission. No automatic probe/preflight/describe/setup or JS errors. Records/checkpoints are explicit doubles; no long GPU training. `Servo-audit-browser.txt`, `R1.5.3-4K.png`, `R1.5.3-servo-4K.png`.
- Pinned Luwu, fanhao375, JoyandAI, and OptiDuck sources/hashes were compared with ROBOTIS/Feetech manuals, inertia, and specifications. Specifications, identification, model constants, and local measurements remain distinct; specs do not automatically enter training.

## Limits

BAM caching affected manual overrides only. Missing BC descriptions did not disable imitation during training. Old models replay actual original dynamics without rewriting PT or records. No current user logs, actual teachers, physical feedback, ZERO register changes, stopped WSL tasks, or long GPU training were obtained. This does not identify a unique swaying cause or establish convergence. See [the detailed review](Servo-training-audit.en.md). These corrections supersede earlier manual-override/BC-description claims.

# R1.5.2 · 4096-reference sampling alignment

Reviewed October 3, 2026. Keeps R1.5.1 source, dependencies, scale, and firmware. Adds timing/budget conversion, resume clock, and display without touching running WSL tasks.

## Executed checks

- Python batch of 122 completed successfully, with one optional-source skip. Checks all 12 recipes at 1024/2048/4096/8192/3000 parallelism, strict/nonstrict boundaries, no shared mutation or repeated multiplication, budgets, and resume records. Prior liveness/download/viewer/V2 checks remain. `Sample-alignment-tests.txt`.
- Three real CPU integrations passed: frozen source, mjlab 1.3.0, rsl-rl 5.0.1, MuJoCo 3.10.0, mujoco-warp 3.8.1, locked BAM, Torch 2.9.1 CPU. Delivered uv.lock is unchanged. `Sample-alignment-upstream.txt`.
- Twelve actual tasks with HD1910 and 2048 conversion retain everything except time thresholds. Performance curricula remain; rollout is 24 steps.
- An actual joint environment uses the 2048 curriculum with two CPU worlds. CurriculumManager/EventManager readbacks: iteration 300 → 20% half-squat; 1400 → 15% fallen; 2000 → 30%; 2800 → 45%; 1399/1999 retain the preceding stage. Actual stepping yields finite rewards. This tests boundaries, not long training in 2048 worlds.
- A real runner saves generated test PT and loads two environments into one: samples unchanged, curriculum steps doubled, PPO numbering unchanged, actor weights identical. No user PT is modified.
- Actual 4K browser checks 12 tasks, default/manual budget conversion, 1400–1999/2800–3999 displays, alignment version, 1000-actual-iteration saving, immutable started parameters, V2/viewer options, and no extra requests/errors. Test backend, no GPU run. `R1.5.2-4K.png`, `Sample-alignment-browser.txt`.

## Conversion and limits

Thresholds scale by `4096 / current parallelism`, retaining each upstream `>`/`>=`. Probabilities, rewards, and physics do not scale. Rollout is 24; budgets round up by sample count. `infos.studio_sample_clock` stores cumulative samples; upstream owns PPO numbering. New teacher warm starts reset joint curricula; ordinary resume continues samples.

Old training is not rewritten and earlier exposure cannot disappear. Parallelism changes updates and correlations; equal samples do not guarantee equal convergence or physical behavior. No user GPU long run, physical motion, or peak CUDA-memory acceptance. Earlier “same curriculum” claims describe earlier versions.

# R1.5.1 · Existing V2 compatibility

The new compatibility path retains R1.5.0 source, dependencies, and firmware.

## Executed checks

- Actual V2 walking `model_9999.pt`, request, YAML, and contract from `cb70b792312d559a4da09064d92009079671815f`, scale 1. Compared joints, HOME, actions, observations, BAM, bodies, and network; only equivalent actuator-selector notation is normalized.
- Strict actor/critic load on frozen current source, two CPU worlds and 24 control steps, finite outputs/rewards. Friction reads 1.0; not gait/physical acceptance.
- Actual walking teacher warm-starts joint training: two CPU worlds, four samples, one PPO+BC update. Curriculum resets to zero; PT saves BC optimizer and teacher hashes. Recovery uses explicit placeholder weights, not the user's recovery capability. New friction 0.9895–1.0451 is within 0.9–1.1.
- Official re-export matches original ONNX on three random observation batches at rtol=1e-5/atol=1e-6. PT hash is unchanged. Manifest validates; training remains cb70b792 and export uses 8d0db749, without claiming new training.
- All 115 Python regressions passed: actual configurations, liveness, viewer closure, downloads, V2 walking/recovery/joint display, PT/ONNX/re-export evaluation, teachers, source isolation, calibration, and rejection of actual mismatches.
- Actual 4K HTTP browser selects V2 PT/evaluation and teachers without automatic checks/errors. Browser checkpoints are doubles; actual PT physics is verified separately above.

# R1.5.0 · Official alignment baseline

Reviewed October 3, 2026. Actual execution, test doubles, and unverified scope are distinct.

## Pinned sources

- Firmware: `pollen-robotics/microduck`, daemon-v0.15.1, `1fa84386f07884e27866411bc1ba166977bced95`.
- Training: `pollen-robotics/microduck_rl`, `8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec`.
- BAM: locked `62bd8ce12154340be97e06f7f41a0ca8f116d967`.
- HD1910: `fanhao375/microduck-replica@25791f0bd260fd869ed841578785fa8d7e14396d`, `1910_m6.json`.
- Evidence hashes: `data/source-evidence.json`.

## Configuration and physical adaptation

Imported all 12 ordinary-foot tasks and compiled each robot: 14 active joints, 61 observations, 50 Hz, and HOME matching 0.15.1 DEFAULT_POSITION. Rewards, curriculum content, commands, termination, and contacts compare with upstream. Chinese explanations are complete; scale defaults to 1. HD1910 changes only actuator/local robot parameters; each is 0.820kg including battery.

Official PpoWithExpertBc remains. The adapter binds teachers, validates contracts, records hashes, and saves/restores BC optimizer. MICRODUCK_WARM_START resets curricula only for a new teacher warm start, not ordinary resume.

## Actual CPU simulation and optimization

Python 3.12, mjlab 1.3.0, MuJoCo 3.10.0, mujoco-warp 3.8.1, rsl-rl 5.0.1, locked BAM, and Torch 2.9.1 CPU. Delivery retains official uv.lock rather than CPU Torch.

1. Four real walking worlds reset/step with finite observations/rewards.
2. HD1910 inherits official FrictionDRBamActuator. Reset friction ≈0.9311–1.0013 is within 0.9–1.1 rather than all 1.
3. Real walking PPO collects/updates once and saves PT.
4. Small-sample placeholder teachers exercise real warm-start/joint PPO+BC and checkpoint extensions with optimizer state. This proves pipeline connectivity, not learned walking/recovery.
5. Console export calls the upstream exporter. Actual ONNX Runtime input is `obs[1,61]`, output `[1,14]`.
6. Joint export needs no teachers or W&B download and generates a walk-slot manifest.
7. PT/ONNX outputs match for identical observations at rtol=1e-5/atol=1e-6, with embedded normalization and no extra 0.7.

These pipeline checks use four worlds × four steps and one update, without changing delivered default budgets/curricula.

## Backend and browser

- All 105 Python tests passed: engine/defaults, calibration migration, reward editing without remote reads, cache, history/provenance, manifest/profile, download byte checks, liveness, simulation stop, message coalescing, and timeouts. R1.5.1 later opens V2 compatibility.
- Liveness tests launch real children across console closure, forced monitor termination, reconnection, and explicit stopping; page status is not substituted for process evidence.
- Actual 4K Chromium HTTP checks all 12 tasks, bundled defaults, then-current-only teachers, direct submission, and no automatic probe/preflight/describe/setup or JS errors. PT/progress are explicit doubles, not GPU training. Later V2 checks supersede teacher filtering.
- Layout remains; renamed joint-teacher static routes were fixed and retested.

## Export/runtime contracts

All schema 2 manifests validate upstream. Walking, recovery teachers, sit/stand, ground pick, right kick, and roll remain distinct. A recovery teacher is not automatic Stand; no left-foot model is fabricated without a left task.

Filter 1 means passthrough in 0.15.1. This historical training had no additional EMA, with scale 1 and the then-current deployment settings. R1.5.13 later corrects forced voltage/gain export; current rules take precedence. Released XL330 presets cannot apply unconditionally to self-trained HD1910.

Contracts record HOME, joint order, raw previous actions, 50 Hz, normalization, and HD1910 commands. Changed stacking, observation/action scaling/clipping, HOME, or frequency are not exported as directly compatible.

## Not executed

No ZERO connection, calibration writes, servo-register changes, firmware flashing, or physical motion. No user's long GPU convergence training or physical gait acceptance. 0.15.1 still requires HD1910/IMU adaptation and the export contract.

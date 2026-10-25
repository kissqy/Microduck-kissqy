[简体中文](Version-history.zh-CN.md) | **English** | [Русский](Version-history.ru.md)

# Training Studio version history

This archive records earlier versions and experiments. Use [the current user guide](../USER-GUIDE.en.md) for R1.5.27, which provides 14 action categories and 35 recipes. Historical 12-task lists and experimental parameters below are not current defaults.

## R1.5.17 — Recovery evaluation and rollover checks

- Ordinary StandUp PT / ONNX evaluation uses the original recipe's final curriculum, avoiding an ONNX counter starting the easy curriculum again. Ordinary terrain is retained.
- Separate flat-ground, zero-command checks cover fully supine, left / right side, prone, and final mixed starts.
- The original event manager resets fixed poses. Height and tilt must remain within criteria; timeout fails and manual reset cancels. Standing in a new episode is not success for the previous trial.
- Both viewers log actual joints, root pose, commands, and contacts to reproduce stuck states.
- Evaluation changes only; the 11000-iteration teacher's remediation remains a separate, unstarted proposal.

## R1.5.16 supplement — Password SSH

Password authentication and existing system keys are supported. One authenticated connection handles deployment, API calls, model transfers, and viewer forwarding. First host identity requires confirmation; passwords stay only in console memory. Bad passwords and changed host keys produce explicit errors. Service version remains R1.5.16; existing backends can reconnect. WSL GPU-tool path fixes and training configuration are retained.

## R1.5.16 — Local WSL SSH testing

Existing local WSL continues using `wsl.exe`; one-click testing exercises the server SSH path through dedicated loopback SSH, keys, host keys, and backend records. It reuses actual upload / forwarding code and checks the existing environment without installing or changing engines or starting training. Saved external connections can be restored. Scale, filters, P, and physics remain; failure retains the SSH target and blocks unintended local execution.

## R1.5.15 — Remote SSH training

- Adds local / SSH selection, locally saved connections, custom ports, system keys, ssh-agent, and explicit key paths.
- OpenSSH uploads the same console into an independent server directory. A loopback-only backend uses the existing pinned environment preparation.
- Queue, training, simulation, curves, logs, stop, and downloads pass through SSH tunnels. Server queues survive desktop disconnection.
- Complete ZIP uploads preserve scale, filtering, P, contracts, and provenance. Older exports read actual mappings from `policy_parameters`; missing original parallelism can permit teacher use, but resume requires the complete original training snapshot.
- Retains R1.5.14 training / P behavior. Remote failures block submission without local fallback. ZERO calibration is read locally and transferred to the server.

## R1.5.13 · Export contracts and original training snapshots

Export stops forcing voltage compensation off or gain multipliers to 1. Scale / EMA follow original training; normalization follows actual actor configuration. Original startup readback records supply / friction randomization, backlash, rewards, curricula, BC, and hardware. Missing history is labeled reconstructed. Manifest, contract, and snapshot agree. Physics and layout remain unchanged. Update the export backend and re-export existing PT files; no retraining or environment installation is required. See [verification](Verification.en.md).

## R1.5.12 · Unified queue and contact parameters

Single and sequential runs both use Add to Queue, then Start Training. Extra queue-start / pause controls and duplicate plan bars are removed. Stop first persists the decision to stop later scheduling, then stops the current task; waiting tasks remain. Plans join the queue header and show actual running parameters. Add uses the theme's green.

Contact surfaces, physics buffers, randomization, and terrain show bilingual names, official defaults, drafts, running values, and purposes. Existing supported overrides remain editable. Defaults are unchanged; 3072 environments can be entered directly, with sample-based curriculum / budget conversion.

Static-only refresh is supported. Older queue backends pause scheduling before stopping the current task. Add moves beside training parameters; Start / Stop / Cancel move into the queue toolbar without changing submission logic. The 4096 default, physics, and R1.5.10 scheduling remain.

## R1.5.10 — Sequential queue

Tasks wait for their predecessors. Parameter snapshots and future teacher-checkpoint references are fixed at insertion.

## R1.5.9 — Tasks and backlash

Completes actual official action / terrain / backlash combinations and HD1910 encoder feedback. See [the task audit](audit-0151/official-task-parameter-audit.en.md).

## R1.5.8 · Walking scale 0.9 and filtering experiment

The 0.1–1.0 action-scale selector sits beside head / leg filters. The walking chain defaults to 0.9; other skills use 1.0. Manual choices survive task changes and status refresh. Resume uses saved values; returning to new training restores the draft. The displayed version comes from the backend, avoiding a new page hiding an old script. Start the updated script and refresh with Ctrl+F5; active training retains its initial configuration.

New walking teachers, recovery teachers for joint training, and joint models use scale 0.9, head filter 0.5, and leg filter 0.7 throughout UI, training, simulation, ONNX checks, and export. Upstream's original scale remains 1.0; 0.9 is a local deployment-alignment experiment. Sit / stand, pick, kick, and roll default to 1.0. Recovery teachers match the joint walk contract and are not stationary Stand models.

Older resume, evaluation, and export retain each model's own scale / filter, including R1.5.7 models trained at 1.0. Export writes only the relevant action settings rather than changing other slots. Deployment applies one target filter and one action mapping, without another 0.9 multiplication.

Experiment sequence: train a new walking teacher, a new recovery teacher, then their joint model. No environment reinstall / check is needed. Calibration, BAM, mass, curricula, and layout remain. See [verification](Verification.en.md).

## R1.5.7 · Joint-target filtering experiment

New training defaults to head / neck α=0.5 and legs α=0.7 with action scale 1.0. Filtering can be disabled for comparison. This is a local experiment rather than an assertion that upstream training already uses EMA.

- Raw output → `Home + 1.0 × raw output` → target EMA → existing BAM. New target weight is α, previous target weight 1−α. Update once per 50 Hz cycle, not each of four physics substeps.
- Names select four head / neck and ten leg joints, excluding beak / passive joints. Each environment has independent history; its first target after reset passes through. Previous-action observations and action-rate rewards still use raw outputs.
- Resume, evaluation, and export retain the model's saved filtering. Older models without filter records use passthrough. Page edits affect new runs only.
- Both teachers and the joint task require matching filters. Train new matching teachers rather than treating unfiltered teachers as equivalent.
- Contracts, ONNX metadata, and `deployment-profile.toml` record settings. ONNX outputs raw actions; runtime filters once. R1.5.13 later corrects the historical forced voltage / gain export behavior.
- Existing environment cache, BAM, 820 g mass, calibration, rewards, and sampling alignment remain. No extra 0.9 scaling or voltage compensation is introduced.

Launch from the extracted directory using `start-training.cmd`, or `python3 training_console.py` on Linux, without reinstalling the engine. Keep an active training window open until completion before changing directories. This release did not guarantee Windows / WSL terminal-close survival. CPU functional validation is not physical stability acceptance.

## R1.5.6 · Two-column parameters and themed dropdowns

The left column contains task, name, parallelism, iterations, start mode, teachers, and network; the right contains rewards / disturbances with independent scrolling. At 4 K, approximately 12 walking / recovery rewards or 14 joint rewards fit. Left-side controls grow naturally without clipping teachers / network; parameter and curriculum cards remain equal height.

R17 gray / green dropdowns were checked in Chrome 154, retaining keyboard selection, values, and dynamic choices. The ZIP is `Microduck-Training-Studio-R1.5.6.zip`. This is a layout-only change retaining R1.5.5 configuration, calibration, BAM, interfaces, and startup conditions.

While training, keep the existing launcher open, replace only `training/static`, and Ctrl+F5 without stopping training or rechecking the environment. When idle, launch the new package normally.

## R1.5.5 · R17 colors and parameter height

Matches R17 v1.0.95 gray backgrounds / cards and green actions. Blue gradients, gold calibration controls, and mixed card backgrounds are removed. Red remains for stop / delete / errors; curves use green, blue, and warm colors. Equal-height parameter / curriculum cards use remaining space for lists rather than a 140 px reward limit. Compact bilingual editable rows remain.

Three-column simulation, robot / calibration, curricula, models, and status are retained without changing scale, dynamics, rewards, or gates. Static-only updates are supported; idle users can launch the new package.

The earlier guarantee that closing the launcher always preserves WSL training was withdrawn. Actual Windows / WSL closure remained unverified; keep the launcher open. This UI release did not fix that process issue.

## R1.5.4 · Trained-model simulation error

Removes the nonexistent `policy.scale` initialization log. MLP and ONNX policies enter the official Viewer without extra scaling. Unused `inference_scale` requests are removed / ignored; saved `training_action_scale` remains. Viewer cleanup precedes Viser shutdown to avoid `Event loop is closed`, retaining timeout recovery and training isolation. New training still uses 1.0. PT, BAM, calibration, rewards, and curricula are unchanged. No retraining, re-export, or environment reinstall is required for this viewer fix.

## R1.5.3 · Actuator and joint-training review

Adds bilingual names, units, purposes, sources, and register search for 19 configuration fields, 20 BAM fields, 10 model readbacks, 28 XL330 specifications, and 110 registers. Fixes manual BAM cache loading without changing defaults. Keeps 17 BC fields in descriptions and shows teacher gating, imitation loss, tracking, and sway; evaluation / export load only students.

Adds Luwu, fanhao 375, and JoyandAI comparisons without replacing current supply / PID settings. Sampling alignment, cache, background liveness, calibration, and models remain. Edits apply to the next run. See [the detailed review](Servo-training-audit.en.md).

## R1.5.2 · Align samples to 4096 environments

Target: official 0.15.1, official chassis + HD1910, 820 g including battery. R1.5.0/1.5.1 environments need no reinstall. Launch the new directory when idle; records stay in the same data directory.

- Reference: 4096 environments × 24 steps per iteration. At 2048, time thresholds / budgets double; at 1024, quadruple. Other parallelism scales proportionally.
- Time-based fallen / half-squat, pushes, smoothness, command-range, and pose curricula convert. Probabilities, parameter values, and performance-based terrain promotion remain unchanged.
- Changing parallelism converts the current default / manual budget; editing iterations afterwards sets the actual budget. Tables / logs / readbacks show reference and local values. Task changes read bundled data without an environment probe.
- Save every 1000 actual iterations without scaling that interval. PT stores cumulative samples; PPO iteration numbering remains upstream. New joint warm starts begin their curriculum at zero.
- Active runs retain their startup configuration. Old resume uses recorded parallelism / rollout; prior curriculum exposure cannot be undone. A complete fresh comparison needs new training.

| 4096 reference | 2048 actual | 1024 actual | Fallen / half-squat reset |
| ---: | ---: | ---: | --- |
| 0–149 | 0–299 | 0–599 | 0% / 0% |
| 150–699 | 300–1399 | 600–2799 | 0% / 20% |
| 700–999 | 1400–1999 | 2800–3999 | 15% / 20% |
| 1000–1399 | 2000–2799 | 4000–5599 | 30% / 20% |
| 1400+ | 2800+ | 5600+ | 45% / 20% |

Equal samples do not promise equal PPO results. This console scheduling addition is not automatic upstream behavior. Rewards, physics, PPO / BC, and scale are unchanged.

## Retained R1.5.1 V2 compatibility

- Select “既有 V2” (Existing V2) PT / ONNX under Models and Validation. Walking, recovery, and joint models are available.
- VelStand accepts previous walking / recovery PT teachers; missing old friction randomization alone does not require retraining teachers.
- Training source `cb70b792…` loads with current `8d0db749…`, without installing the old engine. PT, robot parameters, and calibration provenance remain; exports state the actual training version.
- Fixed-friction models use their original BAM multiplier 1.0; randomized R1.4.23 models retain their settings. New joint training still randomizes 0.9–1.1.
- Only equivalent selector notation is normalized. Actual action, order, HOME, BAM, mass, or inertia mismatches are explicitly rejected. Old V2 joint optimizer checkpoints are not migrated; use old teachers for a new joint run.

Compatibility establishes loading, evaluation, and participation in training, rather than guaranteeing no physical effect from missing randomization.

## Historical startup instructions

1. Extract a new directory and run `start-training.cmd`; Windows needs Python ≥3.10. Linux: `python3 training_console.py --open`. Page: `http://localhost:8092`.
2. On first use, choose “执行环境 → 安装训练环境” (Execution Environment → Install Training Environment). R1.5.0/1.5.1 reuse cache. Later task / calibration / model / training / viewer changes do not trigger checks.
3. Select task, parallelism, and iterations. Blank algorithm fields use official defaults. Robot edits save automatically. Use “从 ZERO 获取” (Fetch from ZERO) or import complete calibration.
4. This historical version started directly; later queue versions require Add first. The current guide governs. Training could display nine actual environments; separate evaluation does not stop training.
5. Evaluate PT and export ONNX, PT, schema 2 manifest, deployment fragment, actual parameters, and calibration provenance.

Engine: `~/microduck-training-studio/engines/official_0151`. WSL installs with `uv sync --frozen --python 3.12`; desktop Python 3.10 does not need changing. If Git / uv are missing:

```bash
sudo apt-get update
sudo apt-get install -y git curl
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then install the environment through the page. Training requires NVIDIA CUDA; a new host is checked once.

## Tasks retained in this historical version

| Task | Terrain | Official max_iterations | Use |
| --- | --- | ---: | --- |
| Velocity | Flat / Rough | 50000 | Walking, turning, pose; walk slot |
| StandUp | Flat / Rough | 15000 | Recovery teacher, not stationary Stand |
| VelStand | Flat / Rough | 6000 | Current / compatible V2 teachers; walk slot |
| SitStand | Flat / Rough | 15000 | sitstand; vx=1 sit, vx=0 stand |
| GroundPick | Flat / Rough | 20000 | ground_pick; 4-second phase |
| BallKick | Flat | 10000 | kick_right |
| Roulade | Flat | 10000 | roulade |

Twelve tasks here, versus the current 35 recipes. Budgets are not convergence guarantees: joint 6000 becomes 12000 at 2048 or 24000 at 1024. Stop or edit anytime. Save every 1000; no `model_0.pt`, so runs under 1000 have no automatic PT. Latest ten run records are shown; models remain until explicit deletion / cleanup.

## Alignment with 0.15.1

Training is pinned to `8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec`; firmware to daemon-v0.15.1 / `1fa84386f07884e27866411bc1ba166977bced95`. Training has no matching firmware version label; the pairing comes from protocol review.

Actual IDs, rewards, curriculum content, termination, contacts, PPO, and joint algorithms remain, with R1.5.2 time alignment. At that stage old Luwu engines, HD1910/V2 aliases, roller entries, and ledgers were removed; later releases add verified roller recipes.

Local HD1910 BAM, 15-servo mass differences, 820 g ballast, calibration, speed command zero, and no acceleration-register 41 writes remain. Original training uses scale 1 without extra 0.7. XL330 reference parameters do not apply to HD1910. Official hardware drivers need HD1910/IMU adaptation; model compatibility alone cannot drive Feetech.

Upstream has no extra head / leg EMA. R1.5.7 experiments export 0.5/0.7 when enabled, otherwise 1. R1.5.8 uses walking-chain 0.9; other models retain original records, without additional multiplication. Merge `deployment-profile.toml` and contracts into existing configuration; the fragment is neither a full robotd.toml nor firmware ZIP. Distinguish walking velocity, pick phase, sit flag, and roll / kick windows. PT resumes training; ONNX runs inference. Export checks do not add pretraining checks. R1.5.13 supersedes forced voltage / gain export.

## Existing data

Calibration / robot edits retain current assembly and back up earlier recipes. Compatible V2 models enter evaluation / export / teacher lists; other history remains downloadable / deletable. Old WSL source and PT files are preserved.

Browser closure, log parsing errors, and viewer disconnection do not request Stop. Explicit Stop does. Windows / WSL launcher-close survival remained unverified in this historical record, so keep the window open. Actual training errors stay visible.

Calibration does not change official HOME / curricula. Bundled provenance comes from a user export; reassembled robots use current ZERO calibration. This console reads calibration without writing ZERO or driving servos. [Verification](Verification.en.md) and `data/source-evidence.json` cover CPU configuration, real PPO / BC, ONNX, and workflows, not the user's long GPU training or physical gait acceptance.

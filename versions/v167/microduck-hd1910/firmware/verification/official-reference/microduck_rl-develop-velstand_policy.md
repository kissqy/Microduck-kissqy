# VelStand policy — how the current one was trained

One policy that walks, stands still at zero command, falls protectively and gets back up, with
the head steerable and (from v7) the body steerable while standing. Task
`Mjlab-VelStand-Rough-Backlash-MicroDuck`, cfg
`src/mjlab_microduck/tasks/microduck_velstand_env_cfg.py` (its module docstring and the comments
on each `ENABLE_*` toggle hold the design and lesson arc), BC machinery in
`src/mjlab_microduck/tasks/distill.py`.

**Current policy: wandb `pollen-robotics/mjlab_microduck/j4i6yoq2` @ `model_1250.pt`** —
`velstand.onnx` in Hub `pollen-robotics/microduck-policies`, tag **v7** (2026-10-05), validated
on the real robot (body roll/pitch, walking, pickup detector unchanged).

## Lineage

Every stage is a **warm start** (`MICRODUCK_WARM_START=1` + `--agent.resume True` on another
run's checkpoint): weights, obs normalizer and optimizer are kept, `common_step_counter` and the
iteration restart at 0 so velstand's own curricula (fall-over disable, prone/crouch spawns,
recovery economics, protection costs, topple pushes) run again from stage 0. Inherited
velocity-recipe curricula are collapsed to their final stage (`WARM_START = True`).

| stage | run @ ckpt | code | what it added |
|---|---|---|---|
| walk teacher | `441tzs6d` @ 3750 | velocity recipe | `alpha_walking.onnx` — the walk the student starts from and the walk BC anchor |
| stand teacher | `69u48n8l` @ 9750 | standup env | `alpha_stand.onnx` — the get-up BC expert (and, from v7, the body-tilt teacher) |
| velstand v1 | `6op8a8u8` @ 5999 | `d3edc1f` (tag `velstand-best-6op8a8u8`) | protective fall + get-up via expert BC + walk anchor, flat |
| v5/v6 prod | `fhathosb` @ 3750 | `e40fbda`, branch `protective_fall` | same recipe on Rough + Backlash, rough-terrain spawn fix |
| **v7 prod** | **`j4i6yoq2` @ 1250** | **`53fb7d1`, branch `improve_velstand2`** | standing body control (below) |

## Stage v7 — `j4i6yoq2` (standing body control)

| | |
|---|---|
| host | COACH2, RTX 5090 |
| start | `fhathosb` @ `model_3750.pt`, warm start |
| checkpoint used | **`model_1250.pt`** (run ended at 1499; see checkpoint choice) |

```bash
MICRODUCK_WARM_START=1 uv run train Mjlab-VelStand-Rough-Backlash-MicroDuck --env.scene.num-envs 4096 \
  --agent.resume True --wandb-run-path pollen-robotics/mjlab_microduck/fhathosb \
  --wandb-checkpoint-name model_3750.pt --agent.max_iterations 1500
```

### Why

The v5/v6 velstand ignored body commands completely (0 mm / 0° response, measured with
`claude_experiments/velstand_body_probe.py`): the velocity recipe keeps `body_pose` at reward
weight 0 with ±5 mm / ±0.05 rad "alive" ranges, and the walk anchor pins standing to
`alpha_walking`, which never learned it. The old pipeline's `alpha_stand` tracks roll/pitch
(9.2–9.5° for 10°) but not z.

### What changed (all behind `ENABLE_BODY_CONTROL`)

| piece | what |
|---|---|
| `StandingGatedPoseCommand` (mdp.py) | body command = sampled value × `twist.is_standing_env` → exact zero while walking / turning, as the runtime sends; 30 % all-zero bucket (plain standing stays trained); z zeroed on half the resamples so tilt-only commands exist |
| ranges | roll/pitch ±6° → **±12°** at iter 300 (≈ `alpha_stand`'s trained range), z −2.5 / +1 cm, x/y/yaw tiny (inside `alpha_stand`'s normalizer) |
| distill body routing (`body_slice`) | standing frames with an active body command leave the walk anchor; **tilt-only → `alpha_stand` BC**, z frames → PPO only (`alpha_stand` cannot crouch). The command is in the obs, so these frames are separable (no teacher leak) |
| `body_pose_tracking` | standing-gated z/roll/pitch Gaussians (z std 1 cm, angle 5°, weight 2, nominal z 0.116 = measured standing trunk height) |
| `upright_body_cmd_relative` | stock `upright` measured against the commanded tilt (identical at zero command) |
| `variable_posture_body_relaxed` | looser leg-pose stds while a body command is active (hip_roll 0.05 → 0.25 etc.; the tight stand std priced a 10° roll at −0.85/step) |

Reward check before training (per step, standing, same env): tracking a 10° tilt beats ignoring it
by +1.35 (pitch), +1.57 (roll), +2.1 (both); zero command unchanged.

### Sim eval at the chosen checkpoint (flat + backlash, vs v6 `fhathosb@3750`)

| | v7 `j4i6yoq2@1250` | v6 `fhathosb@3750` |
|---|---|---|
| body roll ±10° / pitch ±10° | +8.4 / −8.2° · +9.8 / −7.0° | 0 (ignored) |
| body z −2 cm | ≈ 0 (not learned) | 0 |
| turn in place +1.0 / −1.0 rad/s | 0.45 / −0.37 | 0.12 / −0.19 |
| straight-walk yaw drift (0.3 / 0.4 m/s) | 0.05 / 0.03 rad/s | −0.03 / −0.07 |
| push falls, 0.3 m/s (fwd 0.35 / backward / turning) | 0 / 9 / 4 % | 1 / 12 / 9 % |
| get-up after push fall (1.0 / 1.2 m/s) | 93 / 95 % | 91 / 85 % |

Tools: `velstand_body_probe.py`, `velstand_walk_stability.py`, `velstand_improve_bench.py`
(`--only walk|rise`), `velstand_ckpt_eval.sh <run> <ckpt> <ref.onnx>` (all in `claude_experiments/`,
local, gitignored).

### Checkpoint choice

Checkpoints differ a lot in yaw behaviour although the training metrics do not: `500` turns
right when asked to walk straight (−0.20 rad/s at 0.4 m/s), `1499` turns left (+0.27). `1250`
has neither drift. Always run the walk sweep before picking a checkpoint.

## Known limits

- **Body z (crouch)** is not learned (≤ 1 mm for −2 cm): the axis has no teacher and 1500
  iterations of PPO did not find it.
- **Slow yaw.** In-place turning has a dead zone: 0.3 / 0.6 rad/s commands → ≈ 0, 1.0 → ~0.4.
  Root cause (counterfactual scoring — policy fed a larger yaw so it really turns, reward at the
  true command): standing still is the reward optimum at 0.3 rad/s and turning wins only ~4 % at
  0.6; the stock yaw std (0.71) is loose and mjlab's term folds the roll/pitch rates stepping
  creates into the yaw error. Two reward fixes that also took turn-in-place off the walk anchor
  (`ENABLE_YAW_FIX`, runs `sape62zb`, `brkpcnn8`) **lost** turning — kept OFF.
  **What works:** the policy turns monotonically when fed a larger command
  (fed 1.0 / 1.5 / 2.0 → 0.40 / 0.80 / 1.09 rad/s in place, no falls). A runtime remap
  `wz_obs = sign(c)·(0.33 + |c|/0.6)` for `|c| > 0.05` makes v7 track 0.5–1.0 rad/s in sim
  (in place and while walking); 0.3 rad/s stays bursty (~0.2). Not tried on the robot yet.
  Training-side equivalent (anchor turn frames to the walk teacher fed the remapped command) is
  the next step if the remap holds on hardware.

## Reproduce / deploy

```bash
uv run scripts/export.py Mjlab-VelStand-Rough-Backlash-MicroDuck \
  --wandb-run-path pollen-robotics/mjlab_microduck/j4i6yoq2 --checkpoint 1250
uv run python claude_experiments/velstand_body_probe.py output.onnx --stand-expert
```

Always export through `scripts/export.py` (obs normalizer is baked into the ONNX). The official
set on the Hub is updated by hand (replace `velstand.onnx`, edit only its manifest entry, commit,
`create_tag vN`); `uv run publish` is for single-policy repos.

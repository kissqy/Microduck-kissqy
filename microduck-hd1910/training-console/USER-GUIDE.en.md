[简体中文](README.zh-CN.md) | **English** | [Русский](USER-GUIDE.ru.md)

# Microduck Training Studio R1.5.27

Independent Training Studio for **Microduck firmware 0.15.1, official chassis + HD1910**. It currently provides **14 action categories and 35 task recipes**, covering ordinary walking, recovery, sit / stand, joint training, picking, kicking, forward rolls, and six roller action categories.

- **Console:** <http://127.0.0.1:8092>
- **Project:** <https://github.com/kissqy/Microduck-kissqy>, linked at the top of the page.
- **Environment:** local Windows / WSL or an SSH training server. Training does not require Radxa ZERO; connect only to retrieve current joint calibration, or import a calibration file.

## Startup and training

1. Extract the entire package. On Windows run `start-training.cmd`; on Linux run `start-training.command`, then open the console URL. The launch window shows only version, console URL, and project URL.
2. On first use, follow the page to prepare the training computer once. Later sessions share the detection cache. Changing a task or opening the page does not automatically install dependencies or start training.
3. Choose action, parallel environments, iterations, model, or teacher checkpoint and confirm parameters. **Add the task to the queue before starting training.**
4. Follow the queue, reward curves, logs, and simulation. Saved checkpoints can be resumed, evaluated as PT / ONNX, or exported as complete packages.

Training, history, and models are stored in the execution host's data directory. Current 35-task models and records remain in their existing training directories. Local records for retired tasks are no longer retained. Old PT / ONNX files on remote servers are not directly cleaned by the desktop console. Use matching complete versions of the backend and page.

## Current training and model rules

| Item | Rule |
| --- | --- |
| Firmware and policy interface | Microduck `0.15.1`; models follow their observation, action, and joint-order contracts. |
| Robot dynamics | Official chassis + HD1910 adaptation; existing BAM M6 and mass configuration remain frozen. |
| New-task defaults | Servo **P=5**, training action scale **1.0**, no additional head / leg target EMA filtering. |
| Curriculum | Registered rewards, disturbances, terrain, backlash, and curriculum are retained; relevant progress is adjusted for parallelism using sampling amount. |
| Checkpoints | Default interval: 1, 000 actual training iterations. Historical evaluation / export follows the saved original configuration. |
| Export | Records the model, original training information, deployment parameters, and required compatibility information. Deployment settings do not retrain the model. |

**Roller actions:** official roller walking and crouch use PPO training action scale **1.0**. Deployment presets corresponding to official released models are inference multiplier **0.8**, head filter **0.5**, and leg filter **0.7**. Roller-walk simulation X input is a **propulsion / glide / braking command** (−0.5 to +0.6), not ordinary walking speed. This straight-line task sends no lateral or turn commands. Swizzle, downhill, roller recovery, and spin follow their own training / export rules; do not apply unconfirmed released-model multipliers to them.

## Scope and references

- This package **is not robot firmware**, does not flash ZERO, and does not automatically drive servos or start physical movement.
- The page displays only the current 14 actions and 35 recipes. Historical results may remain, but experiment entries outside the current registry are not automatically restored.
- Pinned upstreams: training `pollen-robotics/microduck_rl@8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec`; runtime `pollen-robotics/microduck@1fa84386f07884e27866411bc1ba166977bced95`.
- Technical evidence: [official task audit](docs/audit-0151/official-task-parameter-audit.en.md), [roller audit](docs/audit-0151/roller-audit/official-roller-audit.en.md), and [runtime audit](docs/audit-0151/runtime-audit.md). These are targeted technical audits, not changelogs.
- Automated test methods are in [tests / README.md](tests/README.md). Passing tests does not establish long GPU training or real-robot deployment acceptance.

Licensing and third-party sources: [NOTICE.md](NOTICE.md) and `docs/licenses/`.

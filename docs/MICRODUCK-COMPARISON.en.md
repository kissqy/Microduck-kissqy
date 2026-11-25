[简体中文](MICRODUCK-COMPARISON.md) | **English** · [网页版 / Web edition](https://kissqy.github.io/Microduck-kissqy/compare/en.html?v=20261118-short)

# Why Microduck-kissqy: our advantages and gaps in other repositories

**A complete route from your first duck build to advanced skills.**

For personal builds using ZERO 3W, Feetech HD1910 and the Chinese workflow.

> **Evidence cutoff: 18 November 2026.** External comparisons cover the reviewed public versions on that date. Our console entry was updated to R3 / V315 on November 24, 2026; other later project changes remain outside this snapshot.

## What Microduck-kissqy provides

### 1. A complete route from first build to advanced play

**Software, hardware, supplied policies, HD1910-adapted print files, tutorials and a separate Training Studio are provided together.**

Start with purchasing, printing, assembly, flashing, networking and local calibration; continue with everyday play, Chinese AI and new-skill training. [Full build route](https://kissqy.github.io/Microduck-kissqy/build/)

### 2. Supplied motions: no self-training for a normal build

**Walking, sit/stand, picking, forward roll, both kicks, plus roller gliding, crouching, spinning and get-up resources.**

This project is a major source of HD1910 motion resources in the community. Another image project credits 10 models to kissqy; use the models in each release package. [Policies and provenance](https://github.com/kissqy/Microduck-kissqy/blob/main/microduck-hd1910/docs/MODEL-PROVENANCE.md)

### 3. A Chinese console with a published AI workflow

**Graphical entry points for servo/IMU calibration, 3D pose, joint feedback, camera, gamepad and firmware maintenance.**

R3 / V315 supports conversation, image recognition, voices/personas and action calling. AI needs service credentials and connectivity. [Console and AI setup](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v313)

### 4. Matching HAT, IMU and HUB hardware

**Board designs, bills of materials, wiring, system image and firmware are provided together; build the boards or choose assembled ones.**

V315 supports servo numbering and midpoint calibration through the HAT without a URT2. [Matching hardware](https://github.com/kissqy/Microduck-kissqy/blob/main/hardware/README.en.md)

### 5. HD1910 print files and step-by-step tutorials

**STL / 3MF files adapted for the HD1910 build, with purchasing, assembly, wiring, flashing, calibration and troubleshooting guides.**

Follow one reference configuration around ZERO 3W and 15 HD1910 servos, reducing the work of joining unrelated build routes. [Printing and assembly](https://github.com/kissqy/Microduck-kissqy/blob/main/hardware/3d-print-frankenduck/README.en.md)

### 6. A separate Training Studio for new skills

**The public Training Studio provides 14 motion families and 35 task recipes, with queues, SSH execution hosts, reward curves, simulation evaluation and ONNX export.**

Finish your duck with supplied policies first. Long-training and hardware results remain specific to each task and its records. [Training Studio guide](https://github.com/kissqy/Microduck-kissqy/blob/main/microduck-hd1910/training-console/README.md)

## What is missing in these repositories?

### [fanhao375](https://github.com/fanhao375/microduck-replica)

- **The 10 motion models in its image come from kissqy, with the original weights retained.**
- Free-form AI voice conversation is not connected.
- Its training console lacks SSH environment setup, sequential queues, interactive policy evaluation and per-export validation.
- Newly trained policies still await long-run and robot acceptance; the listed roller motions remain untested on hardware.

Evidence cutoff: **2026-11-18** · [Image model attribution](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/image/overlay/usr/share/doc/microduck/模型说明.txt) · [Project README](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/README.md) · [Training feature record](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/docs/reference-comparison-2026-10-23.md) · [Training Studio](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/README.md)

### [OpenMicroDuck](https://github.com/JoyandAI/OpenMicroDuck)

- No new-skill training console; Motion Lab replays and simulates supplied policies.
- Complete fabrication projects for the HAT, bus IMU and HUB/power-pickup boards are not published.
- No published Chinese conversational and visual AI-action workflow.
- The matching OpenMD list lacks left-kick and roller-series policies.
- The complete bilingual tutorials are still being prepared.

Evidence cutoff: **2026-11-18** · [Motion Lab guide](https://github.com/JoyandAI/OpenMicroDuck/blob/379e1919541041f23d816a01c0c9755c7b12a3c9/motion-lab/README.md) · [Board integration status](https://github.com/JoyandAI/OpenMicroDuck/blob/379e1919541041f23d816a01c0c9755c7b12a3c9/docs/bom.md) · [OpenMD policy configuration](https://github.com/JoyandAI/OpenMicroDuck/blob/379e1919541041f23d816a01c0c9755c7b12a3c9/policies/README.md) · [Progress and roadmap](https://github.com/JoyandAI/OpenMicroDuck/blob/379e1919541041f23d816a01c0c9755c7b12a3c9/README.md)

### [Pollen Robotics](https://github.com/pollen-robotics/microduck)

- No ready-to-use HD1910 image, configuration and policy package.
- No dedicated HD1910 print adaptation.
- Whole-robot mechanical and electronic manufacturing designs are not fully published as open hardware.
- No separate Chinese graphical training console.
- No complete Chinese from-zero HD1910 build guide.

Evidence cutoff: **2026-11-18** · [Official runtime](https://github.com/pollen-robotics/microduck/blob/56424efe58b7de40efcf3b2d3a5cd169ee83a182/README.md) · [Official RL project](https://github.com/pollen-robotics/microduck_rl/blob/0daab160d3fb1c2cbaba16a4a19052f36709dd9e/README.md) · [Official hardware publication scope](https://pollen-robotics.com/microduck/press-kit/)

### [AI-FanGe](https://github.com/AI-FanGe/Microduck-build-tutorial)

- No matching ZERO 3W + HD1910 runtime package or print adaptation.
- No HD1910 HAT / IMU / HUB board-project package.
- No integrated graphical robot console or separate Training Studio.
- No integrated Chinese AI voice, visual understanding and action workflow.
- Only walk.onnx is supplied, without matching multi-motion or roller policies.

Evidence cutoff: **2026-11-18** · [Hardware and runtime guide](https://github.com/AI-FanGe/Microduck-build-tutorial/blob/49678215d0b40529522772a40c06c216390449dd/README.md) · [Published project tree](https://github.com/AI-FanGe/Microduck-build-tutorial/tree/49678215d0b40529522772a40c06c216390449dd) · [Training/export source](https://github.com/AI-FanGe/Microduck-build-tutorial/tree/49678215d0b40529522772a40c06c216390449dd/mjlab_microduck) · [Supplied policy directory](https://github.com/AI-FanGe/Microduck-build-tutorial/tree/49678215d0b40529522772a40c06c216390449dd/microduck/src/agents)

### [Luwu XGO-Duck](https://github.com/LuwuDynamics/xgoduck_hardware)

- No graphical Training Studio with integrated SSH setup and multi-run queues.
- No ready-to-use compatibility route for ZERO 3W / HAT / IMU / HUB.
- Policies, printed geometry and runtime must match its UNO Q build and are not directly interchangeable.

Evidence cutoff: **2026-11-18** · [Training and policy interface](https://github.com/LuwuDynamics/xgoduck_rl/blob/a4c78aacd5eaa724cf246fe12d24bfe1e837fa50/README.md) · [Hardware and assembly](https://github.com/LuwuDynamics/xgoduck_hardware/blob/21501676e4413f81480d36b591aedd729412c959/README_CN.md) · [Runtime and installation](https://github.com/LuwuDynamics/xgoduck_runtime_arduino/blob/3f9db11c376030d234c5b1299862211e87b590f1/README_CN.md)

## Policy provenance

The [fanhao image notice](https://github.com/fanhao375/microduck-replica/blob/master/software/image/overlay/usr/share/doc/microduck/%E6%A8%A1%E5%9E%8B%E8%AF%B4%E6%98%8E.txt) credits **10 listed models to kissqy** and records retaining weights and deployment metadata. This establishes the contribution for those models, not for everything in the other repository.

The author’s training/adaptation builds on upstream frameworks, tasks and community work; those components are not claimed as original. [Per-model provenance](https://github.com/kissqy/Microduck-kissqy/blob/main/microduck-hd1910/docs/MODEL-PROVENANCE.md).

## Usage and verification scope

- Supported hardware is the published HAT / IMU / HUB configuration. Other boards, servos and mechanical changes require compatibility checks. Establish the reference configuration first, then verify one change at a time.
- [R3 / V315](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v313) is the current release. All three freshly flashed TF cards booted and opened the setup hotspot on first power-on.
- Physical demonstrations, simulation results and shipped weights have separate scopes. One-legged balance has been demonstrated physically; the provenance page has not matched that demonstration to a separately identified published weight. The video is not a promise that the current package contains it.
- Normal operation needs no training. Listed recipes are not proof that every task has completed long training and physical acceptance.
- Project, upstream and third-party material retain their component licenses. Some original material is restricted to personal noncommercial use; see [licenses](../LICENSE) and [software/model rights](../microduck-hd1910/docs/SOFTWARE-MODEL-RIGHTS.en.md).
- This page documents choices and evidence. It establishes no new hardware, firmware or policy Known-Good.

## Start building

[① Shopping](https://kissqy.github.io/Microduck-kissqy/build/budget.html) → [② Assembly](https://kissqy.github.io/Microduck-kissqy/build/assembly.html) → [③ First walk](https://kissqy.github.io/Microduck-kissqy/build/start.html)

<details>
<summary>Reviewed snapshots and sources</summary>

## Reviewed snapshots and sources

| Reviewed repository | Fixed revision |
| --- | --- |
| JoyandAI/OpenMicroDuck | [379e19195410](https://github.com/JoyandAI/OpenMicroDuck/tree/379e1919541041f23d816a01c0c9755c7b12a3c9) |
| fanhao375/microduck-replica | [de8b67ddcd24](https://github.com/fanhao375/microduck-replica/tree/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e) |
| pollen-robotics/microduck | [56424efe58b7](https://github.com/pollen-robotics/microduck/tree/56424efe58b7de40efcf3b2d3a5cd169ee83a182) |
| AI-FanGe/Microduck-build-tutorial | [49678215d0b4](https://github.com/AI-FanGe/Microduck-build-tutorial/tree/49678215d0b40529522772a40c06c216390449dd) |
| LuwuDynamics/xgoduck_hardware | [21501676e441](https://github.com/LuwuDynamics/xgoduck_hardware/tree/21501676e4413f81480d36b591aedd729412c959) |
| JoyandAI/microduck | [71c6303be7f7](https://github.com/JoyandAI/microduck/tree/71c6303be7f7e139d9f079cbdc34ef085a372e3f) |
| JoyandAI/microduck_rl | [22916b9d82f2](https://github.com/JoyandAI/microduck_rl/tree/22916b9d82f250caa563ed9a56976eb33243fb91) |
| LuwuDynamics/xgoduck_runtime_arduino | [3f9db11c3760](https://github.com/LuwuDynamics/xgoduck_runtime_arduino/tree/3f9db11c376030d234c5b1299862211e87b590f1) |
| LuwuDynamics/xgoduck_rl | [a4c78aacd5ea](https://github.com/LuwuDynamics/xgoduck_rl/tree/a4c78aacd5eaa724cf246fe12d24bfe1e837fa50) |
| pollen-robotics/microduck_rl | [0daab160d3fb](https://github.com/pollen-robotics/microduck_rl/tree/0daab160d3fb1c2cbaba16a4a19052f36709dd9e) |

- [Project README](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/README.md)
- [Training Studio](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/README.md)
- [Training feature record](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/docs/reference-comparison-2026-10-23.md)
- [Training service](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/training_studio/service.py)
- [Recipe registry](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/training_studio/config.py)
- [Training verification](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/docs/verification.md)
- [Balance verification](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/docs/action-lab-verification.md)
- [Image model attribution](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/image/overlay/usr/share/doc/microduck/模型说明.txt)
- [Progress and roadmap](https://github.com/JoyandAI/OpenMicroDuck/blob/379e1919541041f23d816a01c0c9755c7b12a3c9/README.md)
- [Motion Lab guide](https://github.com/JoyandAI/OpenMicroDuck/blob/379e1919541041f23d816a01c0c9755c7b12a3c9/motion-lab/README.md)
- [Companion RL project](https://github.com/JoyandAI/microduck_rl/blob/22916b9d82f250caa563ed9a56976eb33243fb91/README.md)
- [Board integration status](https://github.com/JoyandAI/OpenMicroDuck/blob/379e1919541041f23d816a01c0c9755c7b12a3c9/docs/bom.md)
- [Hardware plans](https://github.com/JoyandAI/OpenMicroDuck/blob/379e1919541041f23d816a01c0c9755c7b12a3c9/docs/architecture.md)
- [Published file tree](https://github.com/JoyandAI/OpenMicroDuck/tree/379e1919541041f23d816a01c0c9755c7b12a3c9)
- [OpenMD policy configuration](https://github.com/JoyandAI/OpenMicroDuck/blob/379e1919541041f23d816a01c0c9755c7b12a3c9/policies/README.md)
- [Runtime weight provenance](https://github.com/JoyandAI/microduck/blob/71c6303be7f7e139d9f079cbdc34ef085a372e3f/policies/README.md)
- [Companion control UI](https://github.com/JoyandAI/microduck/blob/71c6303be7f7e139d9f079cbdc34ef085a372e3f/webd/web/index.html)
- [Official runtime](https://github.com/pollen-robotics/microduck/blob/56424efe58b7de40efcf3b2d3a5cd169ee83a182/README.md)
- [Official RL project](https://github.com/pollen-robotics/microduck_rl/blob/0daab160d3fb1c2cbaba16a4a19052f36709dd9e/README.md)
- [Official RL tree](https://github.com/pollen-robotics/microduck_rl/tree/0daab160d3fb1c2cbaba16a4a19052f36709dd9e)
- [Official deployment configuration](https://github.com/pollen-robotics/microduck/blob/56424efe58b7de40efcf3b2d3a5cd169ee83a182/deploy/robotd.toml)
- [Official hardware publication scope](https://pollen-robotics.com/microduck/press-kit/)
- [Hardware and runtime guide](https://github.com/AI-FanGe/Microduck-build-tutorial/blob/49678215d0b40529522772a40c06c216390449dd/README.md)
- [Published project tree](https://github.com/AI-FanGe/Microduck-build-tutorial/tree/49678215d0b40529522772a40c06c216390449dd)
- [Training/export source](https://github.com/AI-FanGe/Microduck-build-tutorial/tree/49678215d0b40529522772a40c06c216390449dd/mjlab_microduck)
- [Supplied policy directory](https://github.com/AI-FanGe/Microduck-build-tutorial/tree/49678215d0b40529522772a40c06c216390449dd/microduck/src/agents)
- [Hardware and assembly](https://github.com/LuwuDynamics/xgoduck_hardware/blob/21501676e4413f81480d36b591aedd729412c959/README_CN.md)
- [Runtime and installation](https://github.com/LuwuDynamics/xgoduck_runtime_arduino/blob/3f9db11c376030d234c5b1299862211e87b590f1/README_CN.md)
- [Training and policy interface](https://github.com/LuwuDynamics/xgoduck_rl/blob/a4c78aacd5eaa724cf246fe12d24bfe1e837fa50/README.md)
- [Training repository tree](https://github.com/LuwuDynamics/xgoduck_rl/tree/a4c78aacd5eaa724cf246fe12d24bfe1e837fa50)

</details>

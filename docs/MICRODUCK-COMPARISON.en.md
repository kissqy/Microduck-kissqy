[简体中文](MICRODUCK-COMPARISON.md) | **English** · [网页版 / Web edition](https://kissqy.github.io/Microduck-kissqy/compare/en.html?v=20261118-advantages-first)

# Why Microduck-kissqy: our advantages and gaps in other repositories

**A complete route from your first duck build to advanced skills.**

For personal builds using ZERO 3W, Feetech HD1910 and the Chinese workflow.

## What Microduck-kissqy provides

### 1. A complete route from first build to advanced play

**Software, hardware, supplied policies, HD1910-adapted print files, tutorials and a separate Training Studio are provided together.**

Start with purchasing, printing, assembly, flashing, networking and local calibration; continue with everyday play, Chinese AI and new-skill training. [Full build route](https://kissqy.github.io/Microduck-kissqy/build/)

### 2. Supplied motions: no self-training for a normal build

**Walking, sit/stand, picking, forward roll, both kicks, plus roller gliding, crouching, spinning and get-up resources.**

This project is a major source of HD1910 motion resources in the community. Another image project credits 10 models to kissqy; use the models in each release package. [Policies and provenance](https://github.com/kissqy/Microduck-kissqy/blob/main/microduck-hd1910/docs/MODEL-PROVENANCE.md)

### 3. A Chinese console with a published AI workflow

**Graphical entry points for servo/IMU calibration, 3D pose, joint feedback, camera, gamepad and firmware maintenance.**

R2 / V260 documents conversation, image recognition, voices/personas and action calling. AI needs service credentials and connectivity. [Console and AI setup](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v260)

### 4. Matching HAT, IMU and HUB hardware

**Board designs, bills of materials, wiring, system image and firmware are provided together; build the boards or choose assembled ones.**

V297 BATE also adds HAT servo numbering and midpoint calibration without URT2. Hardware acceptance of that test release remains pending. [Matching hardware](https://github.com/kissqy/Microduck-kissqy/blob/main/hardware/README.en.md)

### 5. HD1910 print files and step-by-step tutorials

**STL / 3MF files adapted for the HD1910 build, with purchasing, assembly, wiring, flashing, calibration and troubleshooting guides.**

Follow one reference configuration around ZERO 3W and 15 HD1910 servos, reducing the work of joining unrelated build routes. [Printing and assembly](https://github.com/kissqy/Microduck-kissqy/blob/main/hardware/3d-print-frankenduck/README.en.md)

### 6. A separate Training Studio for new skills

**Task/recipe selection, training queues, reward curves, simulation evaluation and ONNX export form a workflow for exploring new movements.**

Finish your duck with supplied policies first. Long-training and hardware results remain specific to each task and its records. [Training Studio guide](https://github.com/kissqy/Microduck-kissqy/blob/main/microduck-hd1910/training-console/README.md)

## What is missing in these repositories?

### [fanhao375](https://github.com/fanhao375/microduck-replica)

ZERO 3W + HD1910

- **The 10 listed supplied models come from kissqy**  
  Its image notice credits 10 models to kissqy and says the original weights were retained.

- **Free-form AI conversation is not connected**  
  Documented local fixed-command recognition does not establish conversation, image recognition or AI action calling.

- **New-skill long-training and hardware acceptance remain unfinished**  
  GPU checks cover short training, evaluation and export, not completed robot deployment of a newly trained skill.

Sources: [Model notice](https://github.com/fanhao375/microduck-replica/blob/master/software/image/overlay/usr/share/doc/microduck/%E6%A8%A1%E5%9E%8B%E8%AF%B4%E6%98%8E.txt) · [README](https://github.com/fanhao375/microduck-replica) · [Training](https://github.com/fanhao375/microduck-replica/blob/master/software/training-studio/docs/verification.md)

### [OpenMicroDuck](https://github.com/JoyandAI/OpenMicroDuck)

ZERO 3W + HD1910

- **No left-kick policy; no roller tasks in the published list**  
  The policy guide explicitly sets kick_left = none; the six listed ONNX files do not include roller tasks.

- **Deployment still depends on a specific runtime and control setup**  
  It targets robotd 0.13.3 and locates button mappings in the padd binary. It is not an interchangeable configuration for another image or console.

Sources: [Policies](https://github.com/JoyandAI/OpenMicroDuck/blob/main/policies/README.md)

### [Pollen Robotics](https://github.com/pollen-robotics/microduck)

Official / XL330

- **No direct HD1910 installation route**  
  An HD1910 conversion still needs matching communication, actuator parameters and policies.

- **Upstream weights are not automatically HD1910-ready gaits**  
  Renaming the servo or copying an ONNX file does not complete the hardware/policy adaptation.

Sources: [Runtime](https://github.com/pollen-robotics/microduck) · [Adaptation](https://github.com/kissqy/Microduck-kissqy)

### [AI-FanGe](https://github.com/AI-FanGe/Microduck-build-tutorial)

Pi Zero 2 W + XL330

- **No matching ZERO 3W + HD1910 hardware route**  
  The route uses Pi Zero 2 W, OpenRB-150 and XL330, rather than the ZERO 3W / HD1910 electronics and deployment.

- **The reviewed tutorial does not provide this Chinese AI and multi-motion workflow**  
  The reviewed guide uses SSH, terminal commands and a gamepad; it does not document this project’s integrated Chinese AI and multi-motion workflow.

Sources: [Deployment](https://github.com/AI-FanGe/Microduck-build-tutorial)

### [Luwu XGO-Duck](https://github.com/LuwuDynamics/xgoduck_hardware)

UNO Q + 1910 / QMI8658A

- **Existing ZERO 3W and matching boards cannot transfer directly**  
  It uses Arduino UNO Q, a custom expansion board and QMI8658A; an existing ZERO 3W build needs controller, IMU, wiring and software reconsidered.

- **Its supplied policies still require its matching runtime**  
  Its browser interface and policies target the UNO Q environment, not this project’s image and console.

Sources: [Hardware](https://github.com/LuwuDynamics/xgoduck_hardware/blob/master/README_CN.md)

Reviewed **2026-11-18**. Gaps refer to linked public versions and specific configurations, not claims that unlisted features cannot exist elsewhere in a project.

## Policy provenance

The [fanhao image notice](https://github.com/fanhao375/microduck-replica/blob/master/software/image/overlay/usr/share/doc/microduck/%E6%A8%A1%E5%9E%8B%E8%AF%B4%E6%98%8E.txt) credits **10 listed models to kissqy** and records retaining weights and deployment metadata. This establishes the contribution for those models, not for everything in the other repository.

The author’s training/adaptation builds on upstream frameworks, tasks and community work; those components are not claimed as original. [Per-model provenance](https://github.com/kissqy/Microduck-kissqy/blob/main/microduck-hd1910/docs/MODEL-PROVENANCE.md).

## Usage and verification scope

- Supported hardware is the published HAT / IMU / HUB configuration. Other boards, servos and mechanical changes require compatibility checks. Establish the reference configuration first, then verify one change at a time.
- V260 / R2 is the current stable publication entry. The [V297 BATE pre-release](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v297-bate) adds HAT servo numbering, midpoint calibration and separate hardware tests; physical acceptance is pending and controlled regressions do not extend Known-Good.
- Physical demonstrations, simulation results and shipped weights have separate scopes. One-legged balance has been demonstrated physically; the provenance page has not matched that demonstration to a separately identified published weight. The video is not a promise that the current package contains it.
- Normal operation needs no training. Listed recipes are not proof that every task has completed long training and physical acceptance.
- Project, upstream and third-party material retain their component licenses. Some original material is restricted to personal noncommercial use; see [licenses](../LICENSE) and [software/model rights](../microduck-hd1910/docs/SOFTWARE-MODEL-RIGHTS.en.md).
- This page documents choices and evidence. It establishes no new hardware, firmware or policy Known-Good.

## Start building

[① Shopping](https://kissqy.github.io/Microduck-kissqy/build/budget.html) → [② Assembly](https://kissqy.github.io/Microduck-kissqy/build/assembly.html) → [③ First walk](https://kissqy.github.io/Microduck-kissqy/build/start.html)

## Primary sources

- [fanhao375 · Model notice](https://github.com/fanhao375/microduck-replica/blob/master/software/image/overlay/usr/share/doc/microduck/%E6%A8%A1%E5%9E%8B%E8%AF%B4%E6%98%8E.txt)
- [fanhao375 · README](https://github.com/fanhao375/microduck-replica)
- [fanhao375 · Training](https://github.com/fanhao375/microduck-replica/blob/master/software/training-studio/docs/verification.md)
- [OpenMicroDuck · Policies](https://github.com/JoyandAI/OpenMicroDuck/blob/main/policies/README.md)
- [Pollen Robotics · Runtime](https://github.com/pollen-robotics/microduck)
- [Pollen Robotics · Adaptation](https://github.com/kissqy/Microduck-kissqy)
- [AI-FanGe · Deployment](https://github.com/AI-FanGe/Microduck-build-tutorial)
- [Luwu XGO-Duck · Hardware](https://github.com/LuwuDynamics/xgoduck_hardware/blob/master/README_CN.md)
- [Microduck-kissqy · R2 / V260](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v260)
- [Microduck-kissqy · V297 BATE](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v297-bate)
- [Microduck-kissqy · Provenance](https://github.com/kissqy/Microduck-kissqy/blob/main/microduck-hd1910/docs/MODEL-PROVENANCE.md)


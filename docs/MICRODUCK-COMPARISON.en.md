[简体中文](MICRODUCK-COMPARISON.md) | **English** · [网页版 / Web edition](https://kissqy.github.io/Microduck-kissqy/compare/en.html)

# Why choose Microduck-kissqy: benefits and route differences

**For a personal ZERO 3W / HD1910 build using a Chinese console. Compare the gaps first, then the concrete reasons to choose this project.**

## Five direct comparisons

### Microduck-kissqy VS [fanhao375](https://github.com/fanhao375/microduck-replica)

ZERO 3W + HD1910

| **Microduck-kissqy · Our advantages** | **fanhao375 · Gaps in this other route** |
| --- | --- |
| **Use the policy author’s publication and matching Chinese AI workflow**<br>This project provides trained/adapted policies, provenance and deployment records, plus an R2 / V260 flow for conversation, image recognition and action calls. | **These supplied models are not an additional independent motion set**<br>Its image notice credits 10 models to kissqy and says the original weights were retained.<br><br>**Free-form AI conversation remains listed as unconnected**<br>Documented local fixed-command recognition does not establish conversation, image recognition or AI action calling.<br><br>**Its training workbench still needs long-training and hardware acceptance**<br>GPU checks cover short training, evaluation and export, not completed robot deployment of a newly trained skill. |

Sources for this project: [Model notice](https://github.com/fanhao375/microduck-replica/blob/master/software/image/overlay/usr/share/doc/microduck/%E6%A8%A1%E5%9E%8B%E8%AF%B4%E6%98%8E.txt) · [README](https://github.com/fanhao375/microduck-replica) · [Training](https://github.com/fanhao375/microduck-replica/blob/master/software/training-studio/docs/verification.md)


### Microduck-kissqy VS [OpenMicroDuck](https://github.com/JoyandAI/OpenMicroDuck)

ZERO 3W + HD1910

| **Microduck-kissqy · Our advantages** | **OpenMicroDuck · Gaps in this other route** |
| --- | --- |
| **Matching resources for both kicks and roller tasks**<br>Alongside ordinary-foot movements, this project publishes roller swizzle, crouch, spin and get-up resources. | **Its published configuration has right kick but no left kick**<br>The policy guide explicitly sets kick_left = none; the six listed ONNX files do not include roller tasks.<br><br>**The deployment guide has version and control constraints**<br>It targets robotd 0.13.3 and locates button mappings in the padd binary. It is not an interchangeable configuration for another image or console. |

Sources for this project: [Policies](https://github.com/JoyandAI/OpenMicroDuck/blob/main/policies/README.md)


### Microduck-kissqy VS [Pollen Robotics](https://github.com/pollen-robotics/microduck)

Official / XL330

| **Microduck-kissqy · Our advantages** | **Pollen Robotics · Gaps in this other route** |
| --- | --- |
| **The HD1910 adaptation is already a coordinated build route**<br>The ZERO 3W image, servo communication, policies and Chinese console have matching build instructions. | **The original XL330 route is not a ready-made HD1910 installation**<br>An HD1910 conversion still needs matching communication, actuator parameters and policies.<br><br>**Upstream weights are not automatically HD1910-ready gaits**<br>Renaming the servo or copying an ONNX file does not complete the hardware/policy adaptation. |

Sources for this project: [Runtime](https://github.com/pollen-robotics/microduck) · [Adaptation](https://github.com/kissqy/Microduck-kissqy)


### Microduck-kissqy VS [AI-FanGe](https://github.com/AI-FanGe/Microduck-build-tutorial)

Pi Zero 2 W + XL330

| **Microduck-kissqy · Our advantages** | **AI-FanGe · Gaps in this other route** |
| --- | --- |
| **Chinese graphical maintenance, then movements and AI**<br>Calibration, feedback, camera and firmware maintenance have console entry points, alongside matching motion and AI releases. | **Its hardware instructions do not transfer directly to HD1910**<br>The route uses Pi Zero 2 W, OpenRB-150 and XL330, rather than the ZERO 3W / HD1910 electronics and deployment.<br><br>**Its documented first-run path focuses on walk.onnx**<br>The reviewed guide uses SSH, terminal commands and a gamepad; it does not document this project’s integrated Chinese AI and multi-motion workflow. |

Sources for this project: [Deployment](https://github.com/AI-FanGe/Microduck-build-tutorial)


### Microduck-kissqy VS [Luwu XGO-Duck](https://github.com/LuwuDynamics/xgoduck_hardware)

UNO Q + 1910 / QMI8658A

| **Microduck-kissqy · Our advantages** | **Luwu XGO-Duck · Gaps in this other route** |
| --- | --- |
| **Keep the ZERO 3W and this project’s matching boards**<br>Owners or buyers of ZERO 3W and HAT / IMU / HUB can follow one reference configuration for construction and maintenance. | **Changing to this route needs more than another image**<br>It uses Arduino UNO Q, a custom expansion board and QMI8658A; an existing ZERO 3W build needs controller, IMU, wiring and software reconsidered.<br><br>**Its supplied policies still require its matching runtime**<br>Its browser interface and policies target the UNO Q environment, not this project’s image and console. |

Sources for this project: [Hardware](https://github.com/LuwuDynamics/xgoduck_hardware/blob/master/README_CN.md)


Checked **November 18, 2026**. Gaps concern the linked configurations and documents. No same-condition robot benchmark supports a claim of better gait, fewer failures or first-place performance.

## Concrete reasons to choose this project

### 1. Go directly to the policy author

**Ordinary-foot and roller movements with provenance and deployment records.**

Ten models credited by another image project can be traced to kissqy; use each actual release package. [Model provenance](https://github.com/kissqy/Microduck-kissqy/blob/main/microduck-hd1910/docs/MODEL-PROVENANCE.md)

### 2. A published Chinese AI workflow

**Conversation, image recognition, voices/personas and action calling.**

Documented in R2 / V260; requires service credentials and connectivity. [AI features and setup](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v260)

### 3. HAT numbering and midpoint calibration

**No URT2 board required; numbering connects to calibration in one console.**

Available in V297 BATE. Existing R2 / control.102 users replace the console; hardware acceptance is pending. [HAT numbering guide](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v297-bate)

### 4. Matching build and research resources

**Board designs, image, printing/wiring, Chinese console and training tools.**

Finish a reference duck with supplied policies, then explore new skills in the separate Training Studio. [Matching resources](https://github.com/kissqy/Microduck-kissqy/blob/main/hardware/README.en.md)

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


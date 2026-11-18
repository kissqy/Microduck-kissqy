[简体中文](MICRODUCK-COMPARISON.md) | **English** · [网页版 / Web edition](https://kissqy.github.io/Microduck-kissqy/compare/en.html?v=20261118-full-audit)

# Why Microduck-kissqy: our advantages and gaps in other repositories

**A complete route from your first duck build to advanced skills.**

For personal builds using ZERO 3W, Feetech HD1910 and the Chinese workflow.

> **Evidence cutoff: 18 November 2026.** Main repositories and companion runtime/RL projects were reviewed at the fixed revisions listed below. Missing publication, unfinished work and adaptation requirements are distinct; unpublished work, unreviewed branches and later additions are outside this snapshot.

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

**The public Training Studio provides 14 motion families and 35 task recipes, with queues, SSH execution hosts, reward curves, simulation evaluation and ONNX export.**

Finish your duck with supplied policies first. Long-training and hardware results remain specific to each task and its records. [Training Studio guide](https://github.com/kissqy/Microduck-kissqy/blob/main/microduck-hd1910/training-console/README.md)

## What is missing in these repositories?

### [fanhao375](https://github.com/fanhao375/microduck-replica)

ZERO 3W + HD1910

**Evidence cutoff: 2026-11-18 · 13 reviewed gaps/constraints.**

Reviewed revisions: [microduck-replica @ de8b67d](https://github.com/fanhao375/microduck-replica/tree/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e)

#### Training console and workflow

- **No graphical SSH connection and environment deployment**（Not provided in reviewed publication）  
  Dependencies, service startup and port forwarding still need manual preparation; remote connection management and automatic setup remain listed as unimplemented.  
  Evidence: [Training feature record](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/docs/reference-comparison-2026-10-23.md) · [Training Studio](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/README.md)

- **Training does not survive shutdown of its owning Studio service**（Documented workflow constraint）  
  Closing the browser can leave a run active, but shutting down the training service stops its owned child processes; keeping that service alive requires separate session/service management.  
  Evidence: [Training Studio](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/README.md) · [Training feature record](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/docs/reference-comparison-2026-10-23.md)

- **No interactive PT / ONNX physics-evaluation workflow**（Not provided in reviewed publication）  
  The training-area 3D display is a CAD preview. The documented policy view uses bounded video evaluation after training stops, rather than an equivalent interactive policy workflow.  
  Evidence: [Training feature record](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/docs/reference-comparison-2026-10-23.md) · [Training Studio](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/README.md)

- **No sequential multi-run training queue**（Not provided in reviewed publication）  
  The service admits one active job and rejects another while resources are occupied; the reviewed state/API provides no parameter-snapshot queue that executes several runs in sequence.  
  Evidence: [Training service](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/training_studio/service.py) · [Training feature record](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/docs/reference-comparison-2026-10-23.md)

- **Missing reward-component and curriculum diagnostics**（Not provided in reviewed publication）  
  The later update adds execution-host resource readings, but still lists reward components, curriculum information, completion estimates and historical resource curves as unimplemented.  
  Evidence: [Training feature record](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/docs/reference-comparison-2026-10-23.md)

- **No automatic per-export inference and full deployment-compatibility checks**（Not provided in reviewed publication）  
  An independently checked PT/ONNX sample exists, but the verification record says this is not yet built into every export and that complete deployment-compatibility checking remains to be added.  
  Evidence: [Training feature record](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/docs/reference-comparison-2026-10-23.md) · [Training verification](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/docs/verification.md)

- **No graphical recipes for sit/stand, kicks, rolls or roller tasks**（Not provided in reviewed publication）  
  The reviewed recipe registry contains flat walking, rough-terrain walking and one-leg balance; the other listed motion families have no matching graphical recipe entries.  
  Evidence: [Recipe registry](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/training_studio/config.py)

#### Training acceptance

- **Newly trained policies still lack long-run and robot acceptance**（Not completed）  
  The public records cover smoke training, evaluation and export. The recorded five-iteration balance smoke policies score 0/8 and remain untested on the robot; these records do not establish a finished new skill.  
  Evidence: [Training Studio](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/README.md) · [Balance verification](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/docs/action-lab-verification.md) · [Training verification](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/training-studio/docs/verification.md)

- **The four listed roller motions still lack robot testing**（Not completed）  
  The model notice explicitly marks roller locomotion, crouch, spin and get-up as not yet tried on hardware. Bundling their files does not establish whole-robot acceptance of those four motions.  
  Evidence: [Image model attribution](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/image/overlay/usr/share/doc/microduck/模型说明.txt)

- **The listed image/update flows still have hardware-acceptance gaps**（Not completed）  
  The README leaves first use, old-card upgrade/rollback and live acoustic acceptance pending for 20261027, and Qinmo hardware/whole-robot update acceptance pending for 20261028. This item is limited to those named versions.  
  Evidence: [Project README](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/README.md)

#### AI interaction

- **Free-form AI voice conversation is still unconnected**（Not provided in reviewed publication）  
  The project README still marks free-form AI voice conversation unresolved. Fixed voice commands and SSH access for a computer assistant do not establish the combined conversation, visual-understanding and AI-action workflow.  
  Evidence: [Project README](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/README.md)

#### Motion policies

- **The 10 credited image models are not another new independent set**（Model provenance）  
  The image notice credits those 10 models to kissqy and records preservation of their weights; using that image does not by itself add another independently trained set of those motions.  
  Evidence: [Image model attribution](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/image/overlay/usr/share/doc/microduck/模型说明.txt)

- **The image model packages omit original training/export records**（Not provided in reviewed publication）  
  The notice lists removed export-data.zip, training configuration/request files, upstream-params and usage instructions. Recovering the original training/export details requires returning to the original publication.  
  Evidence: [Image model attribution](https://github.com/fanhao375/microduck-replica/blob/de8b67ddcd24e4b01069a174417ce9f8a7ae2c0e/software/image/overlay/usr/share/doc/microduck/模型说明.txt)

### [OpenMicroDuck](https://github.com/JoyandAI/OpenMicroDuck)

ZERO 3W + HD1910

**Evidence cutoff: 2026-11-18 · 10 reviewed gaps/constraints.**

Reviewed revisions: [OpenMicroDuck @ 379e191](https://github.com/JoyandAI/OpenMicroDuck/tree/379e1919541041f23d816a01c0c9755c7b12a3c9) · [microduck @ 71c6303](https://github.com/JoyandAI/microduck/tree/71c6303be7f7e139d9f079cbdc34ef085a372e3f) · [microduck_rl @ 22916b9](https://github.com/JoyandAI/microduck_rl/tree/22916b9d82f250caa563ed9a56976eb33243fb91)

#### Training console and workflow

- **No separate console for training new skills**（Not provided in reviewed publication）  
  Motion Lab runs six supplied ONNX policies on CPU for replay and physics simulation. Its published features do not provide the complete graphical PPO-run, queue, reward-curve and training-export workflow.  
  Evidence: [Motion Lab guide](https://github.com/JoyandAI/OpenMicroDuck/blob/379e1919541041f23d816a01c0c9755c7b12a3c9/motion-lab/README.md) · [Companion RL project](https://github.com/JoyandAI/microduck_rl/blob/22916b9d82f250caa563ed9a56976eb33243fb91/README.md)

- **No graphical training-server connection and setup**（Not provided in reviewed publication）  
  The companion RL project uses uv/train/play/export commands. The reviewed files provide no integrated SSH-server configuration, remote environment deployment and queue-management interface.  
  Evidence: [Companion RL project](https://github.com/JoyandAI/microduck_rl/blob/22916b9d82f250caa563ed9a56976eb33243fb91/README.md)

#### Hardware engineering and matching parts

- **No complete published fabrication package for its custom HAT**（Not provided in reviewed publication）  
  The BOM still describes replacing the external adapter after the HAT arrives, and the architecture labels it planned. The reviewed tree contains no complete custom-HAT PCB, manufacturing BOM and production-file package.  
  Evidence: [Board integration status](https://github.com/JoyandAI/OpenMicroDuck/blob/379e1919541041f23d816a01c0c9755c7b12a3c9/docs/bom.md) · [Hardware plans](https://github.com/JoyandAI/OpenMicroDuck/blob/379e1919541041f23d816a01c0c9755c7b12a3c9/docs/architecture.md) · [Published file tree](https://github.com/JoyandAI/OpenMicroDuck/tree/379e1919541041f23d816a01c0c9755c7b12a3c9)

- **No complete bus-IMU board, firmware and flashing package**（Not provided in reviewed publication）  
  The BOM marks the custom IMU_to_servo board not yet ready. The reviewed publication does not supply its matching circuit project, slave firmware and complete flashing guide.  
  Evidence: [Board integration status](https://github.com/JoyandAI/OpenMicroDuck/blob/379e1919541041f23d816a01c0c9755c7b12a3c9/docs/bom.md) · [Published file tree](https://github.com/JoyandAI/OpenMicroDuck/tree/379e1919541041f23d816a01c0c9755c7b12a3c9)

- **No matching HUB/power-pickup fabrication projects**（Not provided in reviewed publication）  
  The reviewed tree contains no matching servo-distribution HUB or power-pickup PCB sources, manufacturing BOMs and production files; those supporting circuit projects are not supplied in this publication.  
  Evidence: [Published file tree](https://github.com/JoyandAI/OpenMicroDuck/tree/379e1919541041f23d816a01c0c9755c7b12a3c9) · [Board integration status](https://github.com/JoyandAI/OpenMicroDuck/blob/379e1919541041f23d816a01c0c9755c7b12a3c9/docs/bom.md)

#### AI interaction

- **No published Chinese conversational/visual AI-action workflow**（Not provided in reviewed publication）  
  Motion Lab documents deterministic Chinese command parsing; the companion control page provides no combined setup workflow for free-form voice conversation, visual understanding, personas/voices and AI action calls.  
  Evidence: [Motion Lab guide](https://github.com/JoyandAI/OpenMicroDuck/blob/379e1919541041f23d816a01c0c9755c7b12a3c9/motion-lab/README.md) · [Companion control UI](https://github.com/JoyandAI/microduck/blob/71c6303be7f7e139d9f079cbdc34ef085a372e3f/webd/web/index.html)

#### Motion policies

- **No left-kick model in the matching OpenMD configuration**（Not provided in reviewed publication）  
  The dedicated deployment guide sets kick_left to none. This applies to the OpenMD configuration; upstream weights retained in the companion runtime do not establish acceptance for that HD1910 setup merely by their filenames.  
  Evidence: [OpenMD policy configuration](https://github.com/JoyandAI/OpenMicroDuck/blob/379e1919541041f23d816a01c0c9755c7b12a3c9/policies/README.md) · [Runtime weight provenance](https://github.com/JoyandAI/microduck/blob/71c6303be7f7e139d9f079cbdc34ef085a372e3f/policies/README.md)

- **No matching roller-series release in the OpenMD policy list**（Not provided in reviewed publication）  
  The six ONNX files in the dedicated list do not include matching roller locomotion, roller crouch, roller get-up or spin releases; demonstrations and companion files still need separate weight/configuration checks.  
  Evidence: [OpenMD policy configuration](https://github.com/JoyandAI/OpenMicroDuck/blob/379e1919541041f23d816a01c0c9755c7b12a3c9/policies/README.md) · [Published file tree](https://github.com/JoyandAI/OpenMicroDuck/tree/379e1919541041f23d816a01c0c9755c7b12a3c9)

#### Deployment and use

- **The listed policy setup still depends on a specific runtime and control implementation**（Documented workflow constraint）  
  The policy guide targets robotd 0.13.3 and identifies mappings in the padd binary. That deployment flow provides no graphical remapping or cross-version migration procedure.  
  Evidence: [OpenMD policy configuration](https://github.com/JoyandAI/OpenMicroDuck/blob/379e1919541041f23d816a01c0c9755c7b12a3c9/policies/README.md)

#### Tutorials and documentation

- **The complete bilingual tutorial delivery is not marked finished**（Not completed）  
  The M2 roadmap entry still says tutorials are being written; the complete bilingual purchasing-to-assembly-to-advanced-training guide delivery is not marked complete.  
  Evidence: [Progress and roadmap](https://github.com/JoyandAI/OpenMicroDuck/blob/379e1919541041f23d816a01c0c9755c7b12a3c9/README.md)

### [Pollen Robotics](https://github.com/pollen-robotics/microduck)

Official / XL330

**Evidence cutoff: 2026-11-18 · 6 reviewed gaps/constraints.**

Reviewed revisions: [microduck @ 56424ef](https://github.com/pollen-robotics/microduck/tree/56424efe58b7de40efcf3b2d3a5cd169ee83a182) · [microduck_rl @ 0daab16](https://github.com/pollen-robotics/microduck_rl/tree/0daab160d3fb1c2cbaba16a4a19052f36709dd9e)

#### Training console and workflow

- **No separate Chinese graphical training workbench for beginners**（Not provided in reviewed publication）  
  The documented training path uses commands for training, playback and export. The reviewed runtime/RL repositories provide no equivalent Chinese recipe, queue, SSH-setup and model-management workbench.  
  Evidence: [Official RL project](https://github.com/pollen-robotics/microduck_rl/blob/0daab160d3fb1c2cbaba16a4a19052f36709dd9e/README.md) · [Official RL tree](https://github.com/pollen-robotics/microduck_rl/tree/0daab160d3fb1c2cbaba16a4a19052f36709dd9e)

#### Deployment and use

- **No direct HD1910 replica installation route**（Separate adaptation needed）  
  The original actuator and deployment configuration follows the XL330 route. A Feetech build still needs matching protocol/register handling, actuator parameters, calibration and control configuration.  
  Evidence: [Official deployment configuration](https://github.com/pollen-robotics/microduck/blob/56424efe58b7de40efcf3b2d3a5cd169ee83a182/deploy/robotd.toml) · [Official RL project](https://github.com/pollen-robotics/microduck_rl/blob/0daab160d3fb1c2cbaba16a4a19052f36709dd9e/README.md)

#### Motion policies

- **Upstream weights are not ready-made HD1910 gaits**（Separate adaptation needed）  
  The documented actuator model is XL330 BAM M6. Copying an ONNX file or changing a servo name does not match HD1910 dynamics and deployment parameters.  
  Evidence: [Official RL project](https://github.com/pollen-robotics/microduck_rl/blob/0daab160d3fb1c2cbaba16a4a19052f36709dd9e/README.md)

#### Printing and mechanical adaptation

- **No dedicated HD1910 mechanical print adaptation**（Separate adaptation needed）  
  The reviewed model/assets retain the original structure and do not list a dedicated package for HD1910 horn protrusions, assembly interference and matching board mounts.  
  Evidence: [Official RL tree](https://github.com/pollen-robotics/microduck_rl/tree/0daab160d3fb1c2cbaba16a4a19052f36709dd9e) · [Official RL project](https://github.com/pollen-robotics/microduck_rl/blob/0daab160d3fb1c2cbaba16a4a19052f36709dd9e/README.md)

#### Hardware engineering and matching parts

- **No complete open-hardware manufacturing delivery for the whole robot**（Not provided in reviewed publication）  
  The official press kit limits its open-source statement to software, excluding the whole robot’s mechanical/electronic design files. A separately published HAT does not establish publication of every board and editable mechanical manufacturing file.  
  Evidence: [Official hardware publication scope](https://pollen-robotics.com/microduck/press-kit/)

#### Tutorials and documentation

- **No complete Chinese personal-build guide for the HD1910 variant**（Not provided in reviewed publication）  
  The reviewed official entry points do not provide one matching Chinese HD1910 route through budget/purchasing, printing, wiring, image/console setup, calibration, AI and advanced training.  
  Evidence: [Official runtime](https://github.com/pollen-robotics/microduck/blob/56424efe58b7de40efcf3b2d3a5cd169ee83a182/README.md) · [Official RL project](https://github.com/pollen-robotics/microduck_rl/blob/0daab160d3fb1c2cbaba16a4a19052f36709dd9e/README.md)

### [AI-FanGe](https://github.com/AI-FanGe/Microduck-build-tutorial)

Pi Zero 2 W + XL330

**Evidence cutoff: 2026-11-18 · 9 reviewed gaps/constraints.**

Reviewed revisions: [Microduck-build-tutorial @ 4967821](https://github.com/AI-FanGe/Microduck-build-tutorial/tree/49678215d0b40529522772a40c06c216390449dd)

#### Training console and workflow

- **No separate graphical Training Studio**（Not provided in reviewed publication）  
  The publication supplies an MjLab training environment and an ONNX export script, but no separate interface combining recipes, queues, SSH setup, training curves and interactive evaluation.  
  Evidence: [Training/export source](https://github.com/AI-FanGe/Microduck-build-tutorial/tree/49678215d0b40529522772a40c06c216390449dd/mjlab_microduck) · [Published project tree](https://github.com/AI-FanGe/Microduck-build-tutorial/tree/49678215d0b40529522772a40c06c216390449dd)

#### Robot console

- **No integrated graphical robot-maintenance console**（Not provided in reviewed publication）  
  First run, stopping and routine maintenance follow SSH/terminal commands. The separate BNO08x calibration tool does not provide the combined servo, policy, camera, firmware and AI console workflow.  
  Evidence: [Hardware and runtime guide](https://github.com/AI-FanGe/Microduck-build-tutorial/blob/49678215d0b40529522772a40c06c216390449dd/README.md) · [Published project tree](https://github.com/AI-FanGe/Microduck-build-tutorial/tree/49678215d0b40529522772a40c06c216390449dd)

#### AI interaction

- **No integrated Chinese voice, visual-understanding and AI-action workflow**（Not provided in reviewed publication）  
  The reviewed image/deployment guide centers on IMU, gamepad and walk.onnx; its public files supply no integrated free-form voice, image understanding, persona/voice and AI-action entry point.  
  Evidence: [Hardware and runtime guide](https://github.com/AI-FanGe/Microduck-build-tutorial/blob/49678215d0b40529522772a40c06c216390449dd/README.md) · [Published project tree](https://github.com/AI-FanGe/Microduck-build-tutorial/tree/49678215d0b40529522772a40c06c216390449dd)

#### Deployment and use

- **No direct ZERO 3W + HD1910 runtime package**（Separate adaptation needed）  
  This route uses Raspberry Pi Zero 2 W, OpenRB-150 and XL330. Its image, bus driver and parameters do not directly form a matching ZERO 3W/HD1910 package.  
  Evidence: [Hardware and runtime guide](https://github.com/AI-FanGe/Microduck-build-tutorial/blob/49678215d0b40529522772a40c06c216390449dd/README.md)

- **Servo numbering relies on an external setup tool**（Documented workflow constraint）  
  The BOM lists U2D2 and its Power Hub for servo IDs, baud rate and parameters, with no direct numbering workflow integrated into a robot console.  
  Evidence: [Hardware and runtime guide](https://github.com/AI-FanGe/Microduck-build-tutorial/blob/49678215d0b40529522772a40c06c216390449dd/README.md)

- **The documented gamepad service disables Wi-Fi**（Documented workflow constraint）  
  The headless service turns Wi-Fi off for Bluetooth stability. The guide requires turning the controller off to regain SSH/network access under that default flow.  
  Evidence: [Hardware and runtime guide](https://github.com/AI-FanGe/Microduck-build-tutorial/blob/49678215d0b40529522772a40c06c216390449dd/README.md)

#### Printing and mechanical adaptation

- **No matching HD1910 print adaptation**（Separate adaptation needed）  
  Its CAD/3MF follows the documented XL330 build, without a matching HD1910 adaptation for servo geometry, interference and this project’s board layout.  
  Evidence: [Hardware and runtime guide](https://github.com/AI-FanGe/Microduck-build-tutorial/blob/49678215d0b40529522772a40c06c216390449dd/README.md) · [Published project tree](https://github.com/AI-FanGe/Microduck-build-tutorial/tree/49678215d0b40529522772a40c06c216390449dd)

#### Hardware engineering and matching parts

- **No HD1910 HAT / IMU / HUB board package**（Separate adaptation needed）  
  The electronic route uses OpenRB-150 and a BNO08x module. The reviewed tree has no matching Feetech three-board circuit, firmware and whole-robot wiring package.  
  Evidence: [Hardware and runtime guide](https://github.com/AI-FanGe/Microduck-build-tutorial/blob/49678215d0b40529522772a40c06c216390449dd/README.md) · [Published project tree](https://github.com/AI-FanGe/Microduck-build-tutorial/tree/49678215d0b40529522772a40c06c216390449dd)

#### Motion policies

- **Only walk.onnx is supplied in its policy directory**（Not provided in reviewed publication）  
  The reviewed agents directory contains the walking policy only, without matching sit/stand, pick, both kicks, roll and roller-series models/workflows in that package.  
  Evidence: [Supplied policy directory](https://github.com/AI-FanGe/Microduck-build-tutorial/tree/49678215d0b40529522772a40c06c216390449dd/microduck/src/agents) · [Hardware and runtime guide](https://github.com/AI-FanGe/Microduck-build-tutorial/blob/49678215d0b40529522772a40c06c216390449dd/README.md)

### [Luwu XGO-Duck](https://github.com/LuwuDynamics/xgoduck_hardware)

UNO Q + 1910 / QMI8658A

**Evidence cutoff: 2026-11-18 · 5 reviewed gaps/constraints.**

Reviewed revisions: [xgoduck_hardware @ 2150167](https://github.com/LuwuDynamics/xgoduck_hardware/tree/21501676e4413f81480d36b591aedd729412c959) · [xgoduck_runtime_arduino @ 3f9db11](https://github.com/LuwuDynamics/xgoduck_runtime_arduino/tree/3f9db11c376030d234c5b1299862211e87b590f1) · [xgoduck_rl @ a4c78aa](https://github.com/LuwuDynamics/xgoduck_rl/tree/a4c78aacd5eaa724cf246fe12d24bfe1e837fa50)

#### Training console and workflow

- **No separate graphical training workbench**（Not provided in reviewed publication）  
  The companion RL project uses uv run train, play and export commands; the reviewed training tree provides no separate graphical workbench.  
  Evidence: [Training and policy interface](https://github.com/LuwuDynamics/xgoduck_rl/blob/a4c78aacd5eaa724cf246fe12d24bfe1e837fa50/README.md) · [Training repository tree](https://github.com/LuwuDynamics/xgoduck_rl/tree/a4c78aacd5eaa724cf246fe12d24bfe1e837fa50)

- **No graphical training-server and environment deployment manager**（Not provided in reviewed publication）  
  The guide asks users to prepare CUDA, Python 3.12 and uv and run setup/commands themselves; it provides no graphical SSH execution-host configuration and environment-preparation entry point.  
  Evidence: [Training and policy interface](https://github.com/LuwuDynamics/xgoduck_rl/blob/a4c78aacd5eaa724cf246fe12d24bfe1e837fa50/README.md)

- **No combined multi-run queue and training-artifact interface**（Not provided in reviewed publication）  
  Tasks, checkpoints, TensorBoard logs and export paths are managed through commands and directories; the reviewed version does not combine recipe queueing, sequential runs, model selection and export in one training UI.  
  Evidence: [Training and policy interface](https://github.com/LuwuDynamics/xgoduck_rl/blob/a4c78aacd5eaa724cf246fe12d24bfe1e837fa50/README.md) · [Training repository tree](https://github.com/LuwuDynamics/xgoduck_rl/tree/a4c78aacd5eaa724cf246fe12d24bfe1e837fa50)

#### Hardware engineering and matching parts

- **Existing ZERO 3W and matching boards cannot transfer directly**（Separate adaptation needed）  
  This route depends on UNO Q, an STM32 Bridge, its expansion board and QMI8658A. Existing ZERO 3W/HAT/IMU/HUB builds need controller, sensor, wiring and installation adaptation.  
  Evidence: [Hardware and assembly](https://github.com/LuwuDynamics/xgoduck_hardware/blob/21501676e4413f81480d36b591aedd729412c959/README_CN.md) · [Runtime and installation](https://github.com/LuwuDynamics/xgoduck_runtime_arduino/blob/3f9db11c376030d234c5b1299862211e87b590f1/README_CN.md)

#### Motion policies

- **Its policies and printed geometry are not interchangeable with this build**（Separate adaptation needed）  
  Its model uses XGO-Duck geometry/inertias and HLS1910 BAM parameters. Weights, calibration, commands and runtime must match; similar servo names or tensor dimensions do not establish compatibility.  
  Evidence: [Training and policy interface](https://github.com/LuwuDynamics/xgoduck_rl/blob/a4c78aacd5eaa724cf246fe12d24bfe1e837fa50/README.md) · [Hardware and assembly](https://github.com/LuwuDynamics/xgoduck_hardware/blob/21501676e4413f81480d36b591aedd729412c959/README_CN.md)

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

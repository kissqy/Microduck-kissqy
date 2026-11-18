[简体中文](MICRODUCK-COMPARISON.md) | **English** · [Project homepage](../README.en.md)

# Microduck project comparison and build route selection

**Planning a personal Feetech HD1910 build, comfortable with a Chinese console, and interested in supplied movements before AI and training? We recommend starting with Microduck-kissqy's coordinated configuration.**

The project brings together DIY HAT / IMU / HUB boards, printing and assembly resources, a system image, the Chinese Robot Console, author-trained motion policies and a separate Training Studio. A normal build does not require training: source the matching parts, assemble, flash and calibrate your own robot, then use its supplied policies.

[Build guide (中文)](https://kissqy.github.io/Microduck-kissqy/build/) · [R2 / V260 downloads](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v260) · [Physical-robot demonstrations](https://kissqy.github.io/Microduck-kissqy/one-leg-balance.html)

## Choosing among six projects

The selection covers prominent official and community routes, plus OpenMicroDuck as another ZERO 3W + HD1910 configuration. Checked **November 18, 2026**, against public project material and verification records. No physical comparison under identical conditions was performed.

| Project | Main hardware route | Published strengths | Particularly useful for |
| --- | --- | --- | --- |
| **[Microduck-kissqy](https://github.com/kissqy/Microduck-kissqy)** | **ZERO 3W + 15 HD1910 servos; this project's HAT / IMU / HUB** | **Author-trained policies, supplied ONNX models, Chinese console and AI, independent training tools and matching board projects** | **A personal build following a coordinated configuration, then exploring movements, Chinese AI and training** |
| [Official Pollen Robotics Microduck](https://github.com/pollen-robotics/microduck) | Official hardware and Dynamixel XL330 | The source runtime, training ecosystem, architecture and update design | Reproducing the official configuration and developing the upstream stack |
| [Luwu XGO-Duck](https://github.com/LuwuDynamics/xgoduck_hardware) | Arduino UNO Q + Feetech 1910 + QMI8658A | Board production files, assembly manual, 3MF, matching runtime, supplied policies and training repository | Builders choosing UNO Q and the Arduino ecosystem |
| [AI-FanGe Microduck-build-tutorial](https://github.com/AI-FanGe/Microduck-build-tutorial) | Raspberry Pi Zero 2 W + OpenRB-150 + XL330 + BNO08x | BOM, wiring, image, SSH, keyboard/gamepad instructions, walking policy and training project | A Raspberry Pi / XL330 build with a practical first-run guide |
| [fanhao375 microduck-replica](https://github.com/fanhao375/microduck-replica) | Mainly ZERO 3W + HD1910; A7Z preview adaptation and XL330 CAD | CAD, BOM, assembly videos and community contributions; physical motion records, image, robot console and training workbench | Mechanical reconstruction, assembly research and community hardware adaptations |
| [JoyandAI OpenMicroDuck](https://github.com/JoyandAI/OpenMicroDuck) | ZERO 3W + HD1910, its own HAT / IMU | Preconfigured image, BOM, hardware/training resources and a policy directory documenting six ONNX models | Its matching board, policy and deployment configuration |

GitHub Star snapshot: official **13,888**, XGO-Duck hardware **1,970**, AI-FanGe **1,833**, fanhao375 **1,735**, this project **521**, OpenMicroDuck **287**. Counts change; companion repositories are not added together. Choose a build by hardware, available resources and verification scope.

## What kissqy provides

| Your question | Published support | Entry point |
| --- | --- | --- |
| Can I build one before learning reinforcement learning? | Supplied policies and a purchasing, assembly, flashing and calibration sequence; no initial training required | [English build guide](MICRODUCK-BUILD-GUIDE.en.md) |
| Which movements can I explore? | Walking, sit/stand, picking, rolling, left/right kicks and roller resources, with provenance and deployment notes | [Model provenance](../microduck-hd1910/docs/MODEL-PROVENANCE.en.md) · [Demonstrations](https://kissqy.github.io/Microduck-kissqy/one-leg-balance.html) |
| How do hardware and software fit together? | HAT, torso IMU and HUB projects and build records, matching image, firmware, console and wiring guides; assembled IMUs are preflashed with FT6 | [Hardware](../hardware/README.en.md) · [IMU firmware](../hardware/IMU-FIRMWARE.en.md) |
| Is there a graphical interface for operation and diagnosis? | Chinese console for servo/IMU calibration, live 3D pose, feedback, camera, gamepad and firmware maintenance | [Console tutorial (中文)](https://kissqy.github.io/Microduck-kissqy/console-guide.html) |
| Can I add Chinese AI interaction? | R2 / V260 provides Doubao voice, image recognition, voices/personas and action calls; requires service credentials and connectivity | [R2 / V260 release](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v260) |
| How do I train a new movement? | Separate Training Studio with task selection, queues, reward curves, simulation evaluation and ONNX export | [Training Studio guide](../microduck-hd1910/training-console/USER-GUIDE.en.md) |

The recommendation is based on how these resources fit together: complete your robot using existing results, then choose whether to explore AI, training or board fabrication. Follow the release and verification scope of each component.

## Motion contributions credited by another project

**Microduck-kissqy supplies HD1910 motion resources used elsewhere in the community.**

The [model notice in fanhao375's image build tree](https://github.com/fanhao375/microduck-replica/blob/master/software/image/overlay/usr/share/doc/microduck/%E6%A8%A1%E5%9E%8B%E8%AF%B4%E6%98%8E.txt) credits **10 ordinary-foot and roller models to kissqy**. It records retaining `policy.onnx` and deployment metadata, reducing archived training material and changing some runtime parameters.

For these models, the original publication project is a direct place to consult provenance, export records and matching parameters. This evidence concerns only the models listed in that notice.

The author's training work builds on the upstream framework, tasks, robot geometry and community contributions. The [provenance page](../microduck-hd1910/docs/MODEL-PROVENANCE.en.md) distinguishes author training/adaptation, upstream references, historical weights and published copies.

## Comparing the closest HD1910 routes

| Item | Microduck-kissqy | fanhao375 | OpenMicroDuck |
| --- | --- | --- | --- |
| Supplied policies | Ordinary-foot and roller resources, with author training and provenance notes | Image notice lists 10 models adopted from kissqy | Policy directory lists walk, stand, ground pick, right kick, roll and sit/stand |
| Robot and training evidence | Author-trained physical demonstrations and a separate Training Studio; per-model scope is documented | Physical motion records; its training workbench has GPU smoke-training, evaluation and export records, with long training and self-trained hardware deployment pending | Physical videos, associated training repository, policy slots and deployment parameters |
| Hardware resources | This project's HAT / IMU / HUB designs, fabrication records and assembled-board entry | Official HAT and custom bus IMU / HUB / battery-interface resources | Its own HAT / IMU resources and BOM |
| Main emphasis | Chinese graphical operation, coordinated boards, supplied movements, Chinese AI and training tools | CAD, assembly, community material and hardware adaptations | Its hardware, policy and deployment configuration |

All three supply policies and whole-robot material, so a normal build need not begin with training from scratch. OpenMicroDuck's homepage still lists five models, while its more specific [policy directory guide](https://github.com/JoyandAI/OpenMicroDuck/blob/main/policies/README.md) lists six; this page follows the directory. A model count is not an equivalent count of physical skills or a measure of motion quality.

## Start your build

1. **Choose the matching configuration.** Use the [shopping list](../DUCK-SHOPPING-LIST.en.md), and choose board fabrication or assembled boards.
2. **Assemble and calibrate.** Follow the [English build guide](MICRODUCK-BUILD-GUIDE.en.md) for printing, flashing, networking and robot-specific calibration.
3. **Try supplied movements, then choose an extension.** Configure AI for Chinese interaction, or use the [separate Training Studio](../microduck-hd1910/training-console/USER-GUIDE.en.md) for motion research.

## Usage and verification scope

- Supported hardware is the published HAT / IMU / HUB configuration. Other boards, servos and mechanical changes require compatibility checks. Establish the reference configuration first, then verify one change at a time.
- V260 / R2 is the current stable publication entry. The [V297 BATE pre-release](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v297-bate) adds HAT servo numbering, midpoint calibration and separate hardware tests; physical acceptance is pending and controlled regressions do not extend Known-Good.
- Physical demonstrations, simulation results and shipped weights have separate scopes. One-legged balance has been demonstrated physically; the provenance page has not matched that demonstration to a separately identified published weight. The video is not a promise that the current package contains it.
- Normal operation needs no training. Listed recipes are not proof that every task has completed long training and physical acceptance.
- Project, upstream and third-party material retain their component licenses. Some original material is restricted to personal noncommercial use; see [licenses](../LICENSE) and [software/model rights](../microduck-hd1910/docs/SOFTWARE-MODEL-RIGHTS.en.md).
- This page documents choices and evidence. It establishes no new hardware, firmware or policy Known-Good.

## Primary sources

| Source | Used for |
| --- | --- |
| [Official Microduck](https://github.com/pollen-robotics/microduck) · [Training](https://github.com/pollen-robotics/microduck_rl) | Upstream software, hardware route and training ecosystem |
| [XGO-Duck hardware](https://github.com/LuwuDynamics/xgoduck_hardware) | UNO Q, production files, assembly and runtime/training repositories |
| [AI-FanGe tutorial](https://github.com/AI-FanGe/Microduck-build-tutorial) | Raspberry Pi / XL330, image, operation and training |
| [fanhao375](https://github.com/fanhao375/microduck-replica) · [Training verification](https://github.com/fanhao375/microduck-replica/blob/master/software/training-studio/docs/verification.md) | Robot, CAD, community and training scope |
| [fanhao image model notice](https://github.com/fanhao375/microduck-replica/blob/master/software/image/overlay/usr/share/doc/microduck/%E6%A8%A1%E5%9E%8B%E8%AF%B4%E6%98%8E.txt) | Attribution to kissqy, retained artifacts and parameter changes |
| [OpenMicroDuck](https://github.com/JoyandAI/OpenMicroDuck) · [Policies](https://github.com/JoyandAI/OpenMicroDuck/blob/main/policies/README.md) | ZERO 3W / HD1910, image and deployment configuration |
| [R2 / V260](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v260) · [Provenance](../microduck-hd1910/docs/MODEL-PROVENANCE.en.md) · [Hardware](../hardware/README.en.md) · [Training Studio](../microduck-hd1910/training-console/USER-GUIDE.en.md) | This project's published resources and verification scope |

[Project homepage](../README.en.md) · [English build guide](MICRODUCK-BUILD-GUIDE.en.md) · [简体中文](MICRODUCK-COMPARISON.md)

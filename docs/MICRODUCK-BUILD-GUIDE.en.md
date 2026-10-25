[简体中文](MICRODUCK-BUILD-GUIDE.md) | **English** | [Русский](MICRODUCK-BUILD-GUIDE.ru.md)

# Microduck Feetech HD1910 replica guide: parts, 3D printing, firmware, calibration and training

Microduck-kissqy is kissqy's working physical replica project based on Pollen Robotics Microduck 0.15.1, for **Radxa ZERO 3W, 15 Feetech HD1910 servos and this repository's HAT / torso IMU**. It includes a system image, a Chinese-language Robot Console, a separate reinforcement-learning Training Studio, PCB projects and printing files.

**Stable public baseline: Robot Console R17 V167 / control.43 / Training Studio R1.5.27.** Updated October 23, 2026. See the [release baseline and validation scope](../microduck-hd1910/docs/BASELINE.en.md). Source is available; the author's original additions carry personal noncommercial terms, while upstream and third-party components retain their respective licenses. See [component licensing](../microduck-hd1910/LICENSE).

## Choose your starting point

| Your situation | Start here |
| --- | --- |
| You saw a robot video and want to build one | Follow parts, printing, electronics and software below |
| Mechanical and electrical assembly is ready | Start with imaging and calibration |
| Your robot works and you want your own movements | Go to step 6 |
| Network, reboot, IMU or gamepad trouble | [Frequently asked questions](MICRODUCK-FAQ.en.md) |

## 1. Prepare parts and tools

Use the [duck shopping guide](../DUCK-SHOPPING-LIST.en.md) for body parts, PCBs and tools. The reference build uses ZERO 3W, 15 HD1910 servos, a camera, ToF, speaker, battery, HAT and a separate torso IMU. Prices are historical order references; check the included and excluded costs.

See the [tool list](BUILD-TOOLS.en.md) for soldering, reflow and flashing tools. Other controllers and servos are not automatically supported by this image or mechanical layout.

## 2. Print and assemble the mechanical parts

The [FrankenDuck printing set](../hardware/3d-print-frankenduck/README.en.md) contains 36 STLs and one 3MF project with five plates. Adapt printer and material profiles, including TPU parts.

Choose the HUB battery-holder variant or the official-style holder with thicker latches; both IMU mounts fit this repository's IMU. The October 21 update adds leg support ramps, removes outer leg-shell counterbores and integrates interchangeable feet and roller assemblies without servo removal. Rollers use 623ZZ bearings.

This page links the build stages; individual part instructions are on the printing page. File counts are not assembly quantities.

## 3. Prepare HAT, IMU and power

The [hardware guide](../hardware/README.en.md) contains PCB projects, parts tables and two connector versions. See the [HAT build record](../hardware/HAT-TIMELINE.en.md) and [IMU build record and video](../hardware/IMU-TIMELINE.en.md).

**A newly built STM32 IMU needs its separate FT6 firmware.** Imaging ZERO or upgrading robot services does not flash the IMU. Use the [IMU flashing guide](../hardware/IMU-FIRMWARE.en.md) for downloads, SWD wiring and checks.

Follow the [assembly notes](ASSEMBLY-NOTES.en.md) for 5 GHz Wi-Fi and a 1000 µF capacitor across the main power input, including polarity, voltage rating and placement.

## 4. Flash the image and connect Robot Console

1. Download [System Image R1](releases/public-image-r1.en.md) and write the compressed image directly to a microSD card using Armbian Imager.
2. On first boot, join the `Microduck-kissqy` hotspot and configure your home Wi-Fi and a new login password. If the setup does not open automatically, visit `http://10.42.0.1:8088`.
3. Download Robot Console V167 from [Downloads](../README.en.md#downloads-and-versions), extract the complete archive and run `start.cmd` on Windows or `start.command` on macOS.
4. Enter your ZERO's SSH address and credentials. **Image R1 includes control.40; install V167's bundled firmware through the console to reach control.43.**

See the [V167 user guide](../microduck-hd1910/firmware/console/USER-GUIDE.en.md) for installation, logs and controls. The online demos use simulated data; actual control requires the locally running console.

## 5. Calibrate your own robot before movement

Check **zero position, direction and limits for all 15 joints, plus IMU mounting orientation**. A reference robot's calibration cannot replace calibration of your own assembly.

Inspect joint and pose feedback before HOME, hold and walking. Use the [V167 control guide](../microduck-hd1910/firmware/console/USER-GUIDE.en.md) for gamepad modes, roller movements and their conditions. The [FAQ](MICRODUCK-FAQ.en.md) helps distinguish connection, service, communication and movement problems.

## 6. Train movements and deploy them

Ordinary use can start with the released models. Install Training Studio only when needed. The [R1.5.27 training guide](../microduck-hd1910/training-console/USER-GUIDE.en.md) covers environment preparation, queues, reward curves, simulation evaluation and model export. The public version provides 14 movement categories and 35 task recipes.

Workflow: prepare environment → choose task and parameters → queue and start → evaluate in simulation → export → check firmware and policy contracts → validate on the real robot. Robot Console and Training Studio are separate tools. Simulation success does not guarantee identical performance on every assembly.

## Demonstrations, validation and feedback

The [repository homepage](../README.en.md) retains seven separate real-robot clips. Treat each demonstrated result within its recorded conditions, rather than as validation of every action. See the [published validation scope](../microduck-hd1910/docs/BASELINE.en.md).

Report issues with hardware configuration, console version, running firmware identifier, reproduction steps and logs or video in [GitHub Issues](https://github.com/kissqy/Microduck-kissqy/issues). If these resources help your build, Star the repository to keep its update entry point handy.

Author: kissqy · [Original repository](https://github.com/kissqy/Microduck-kissqy) · [FAQ](MICRODUCK-FAQ.en.md) · [Documentation index](README.en.md)

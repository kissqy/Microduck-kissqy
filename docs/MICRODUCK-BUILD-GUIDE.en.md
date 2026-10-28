[简体中文](MICRODUCK-BUILD-GUIDE.md) | **English**

# Microduck Feetech HD1910 replica: from budget to first walking

> [!WARNING]
> **Hardware compatibility and commercial authorization**
>
> **HAT, IMU and HUB versions outside the designs published in this repository are incompatible with this repository’s system and may prevent it from operating normally.**
>
> **This repository has not authorized any commercial organization.** If you find pirated copies, impersonation or unauthorized commercial use, please contact the author. Sharing this work takes effort; please do not misappropriate it.
>
> **Scam warning: Do not trust private sales messages from anyone other than the group owner. Group members have already suffered losses.**
>
> [Contact the author](https://github.com/kissqy/Microduck-kissqy/blob/main/docs/assets/purchase-wechat-qr.jpg) · [License scope](https://github.com/kissqy/Microduck-kissqy/blob/main/LICENSE). The repository’s existing licenses determine the scope of this notice.

Microduck-kissqy is kissqy's working physical replica project based on Pollen Robotics Microduck 0.15.1, for **Radxa ZERO 3W, 15 Feetech HD1910 servos and this repository's HAT / torso IMU**. It includes a system image, a Chinese-language Robot Console, ready-made motion models, PCB projects and printing files. **Ordinary use starts with the released models; training your own is optional.**

**Stable public baseline: Robot Console R17 V167 / control.43.** Follow budget, shopping, assembly and first walking below. See the [release baseline and validation scope](../microduck-hd1910/docs/BASELINE.en.md). Source is available; the author's original additions carry personal noncommercial terms, while upstream and third-party components retain their respective licenses. See [component licensing](../microduck-hd1910/LICENSE).

## Start with these four questions

The interactive build pages below are in **Chinese**. This English guide retains the supporting instructions and reference links.

| Your question | Direct entry |
| --- | --- |
| **How much will it cost?** | [Scheme totals and cost breakdown (Chinese)](https://kissqy.github.io/Microduck-kissqy/build/budget.html) |
| **What should I buy?** | [Specifications, quantities and purchase links (Chinese)](https://kissqy.github.io/Microduck-kissqy/build/shopping.html) |
| **How do I assemble it?** | [Printing, mechanical assembly and wiring (Chinese)](https://kissqy.github.io/Microduck-kissqy/build/assembly.html) |
| **How do I make it walk?** | [Image, network, calibration and first walking (Chinese)](https://kissqy.github.io/Microduck-kissqy/build/start.html) |

An assembled robot can start at step 4. For finding the robot's IP after imaging, see the [illustrated network guide (Chinese)](https://kissqy.github.io/Microduck-kissqy/console-guide.html#network).

## 1. How much will it cost?

**The assembled-board option has a priced reference subtotal of CNY 2823.80**: CNY 2605.80 for the reference body purchases (including the EAGET 32GB microSD card at CNY 39.90 and SAMZHE dual-head high-speed card reader at CNY 22.90), HAT CNY 119 and IMU CNY 99. DIY board materials plus a basic tool allowance produce a reference range of CNY 3500.02–3740.02.

A 32GB microSD card is sufficient. One [SAMZHE dual-head high-speed card reader with simultaneous SD / TF card reading](https://3.cn/393kj-8k?jkl=@I2cIJ7xKJzv@) is included at the author's reference price of CNY 22.90; reuse an existing reader if available. The complete FrankenDuck printing service is listed at CNY 199; the assembled-board plus printing reference subtotal is **CNY 3022.80**, without buying a printer. HUB / battery-connection parts and other unpriced items still need quotes; shipping is extra. Historical quantities include spare stock. [Open the budget page to add your costs (Chinese) →](https://kissqy.github.io/Microduck-kissqy/build/budget.html)

## 2. What should I buy?

Use the [interactive shopping list (Chinese)](https://kissqy.github.io/Microduck-kissqy/build/shopping.html) for the default assembled-board route. The [historical shopping details](../DUCK-SHOPPING-LIST.en.md) retain order specifications and price references. The reference build uses ZERO 3W, 15 HD1910 servos, a camera, ToF, speaker, battery, HAT and a separate torso IMU. Prices are historical order references; check the included and excluded costs.

An assembled IMU needs no programming tools. For DIY boards, see the [tool list](BUILD-TOOLS.en.md) for soldering, reflow and flashing tools. Other controllers and servos are not automatically supported by this image or mechanical layout.

## 3. How do I assemble it?

**[Follow the assembly and wiring steps (Chinese) →](https://kissqy.github.io/Microduck-kissqy/build/assembly.html)** · **[Open the 3D assembly reference (Chinese) →](https://kissqy.github.io/Microduck-kissqy/assembly.html)** Rotate and zoom the model to inspect joint positions, IDs and orientation without connecting a robot. The model is a structural reference; use the printing and hardware guides for Feetech-specific parts, fasteners and wiring.

The [FrankenDuck printing set](../hardware/3d-print-frankenduck/README.en.md) contains 36 STLs and one 3MF project with five plates. Adapt printer and material profiles, including TPU parts. The complete printing service is listed at **CNY 199**. That edition page explains the print-orientation, battery-holder, IMU-mount, roller-change, cooling, and assembly improvements.

Choose the HUB battery-holder variant or the official-style holder with thicker latches; both IMU mounts fit this repository's IMU. The October 21 update adds leg support ramps, removes outer leg-shell counterbores and integrates interchangeable feet and roller assemblies without servo removal. Rollers use 623ZZ bearings.

This page links the build stages; individual part instructions are on the printing page. File counts are not assembly quantities.

### Boards and power assembly

The [hardware guide](../hardware/README.en.md) contains PCB projects, parts tables and two connector versions. See the [HAT build record](../hardware/HAT-TIMELINE.en.md) and [IMU build record and video](../hardware/IMU-TIMELINE.en.md).

**The author's assembled IMU comes with FT6 preflashed and needs no initial flashing; calibrate it for your robot after assembly.** Use the [IMU flashing guide](../hardware/IMU-FIRMWARE.en.md) for self-soldered boards, replacement MCUs, maintenance or upgrades. Imaging ZERO or upgrading robot services does not program the external IMU.

Follow the [assembly notes](ASSEMBLY-NOTES.en.md) for 5 GHz Wi-Fi and power connections. The HUB already includes the 1000 µF main-power buffer capacitor; no separate purchase is needed. Check its polarity, voltage rating and placement during assembly.

## 4. How do I make it walk?

**[Open the six-step first-walking route (Chinese) →](https://kissqy.github.io/Microduck-kissqy/build/start.html)** · [Illustrated console guide (Chinese)](https://kissqy.github.io/Microduck-kissqy/console-guide.html)

1. Download [System Image R1](releases/public-image-r1.en.md) and write the compressed image directly to a microSD card using Armbian Imager.
2. On first boot, join the `Microduck-kissqy` hotspot and configure your home Wi-Fi and a new login password. If the setup does not open automatically, visit `http://10.42.0.1:8088`.
3. Download Robot Console V167 from [Downloads](../README.en.md#downloads-and-versions), extract the complete archive and run `start.cmd` on Windows or `start.command` on macOS.
4. Enter your ZERO's SSH address and credentials. **Image R1 includes control.40; install V167's bundled firmware through the console to reach control.43.**

See the [V167 user guide](../microduck-hd1910/firmware/console/USER-GUIDE.en.md) for installation, logs and controls. The online demos use simulated data; actual control requires the locally running console.

### Calibrate your own robot before movement

Check **zero position, direction and limits for all 15 joints, plus IMU mounting orientation**. A reference robot's calibration cannot replace calibration of your own assembly.

Inspect joint and pose feedback before HOME, hold and walking. Use the [V167 control guide](../microduck-hd1910/firmware/console/USER-GUIDE.en.md) for gamepad modes, roller movements and their conditions. The [FAQ](MICRODUCK-FAQ.en.md) helps distinguish connection, service, communication and movement problems.

## Advanced: train your own movements

After first walking and everyday control with the released models, install Training Studio if you want to explore your own movements. The [R1.5.27 training guide](../microduck-hd1910/training-console/USER-GUIDE.en.md) covers environment preparation, queues, reward curves, simulation evaluation and model export. The public version provides 14 movement categories and 35 task recipes.

Workflow: prepare environment → choose task and parameters → queue and start → evaluate in simulation → export → check firmware and policy contracts → validate on the real robot. Robot Console and Training Studio are separate tools. Simulation success does not guarantee identical performance on every assembly.

## Demonstrations, validation and feedback

The [repository homepage](../README.en.md) retains seven separate real-robot clips. Treat each demonstrated result within its recorded conditions, rather than as validation of every action. See the [published validation scope](../microduck-hd1910/docs/BASELINE.en.md).

Report issues with hardware configuration, console version, running firmware identifier, reproduction steps and logs or video in [GitHub Issues](https://github.com/kissqy/Microduck-kissqy/issues). If these resources help your build, Star the repository to keep its update entry point handy.

Author: kissqy · [Original repository](https://github.com/kissqy/Microduck-kissqy) · [FAQ](MICRODUCK-FAQ.en.md) · [Documentation index](README.en.md)

[简体中文](MICRODUCK-FAQ.md) | **English**

# Microduck Feetech replica FAQ: setup, calibration, IMU, gamepad Wi-Fi interference and power reboots

> [!WARNING]
> **Hardware compatibility and commercial authorization**
>
> **HAT, IMU and HUB versions outside the designs published in this repository are incompatible with this repository’s system and may prevent it from operating normally.**
>
> **This repository has not authorized any commercial organization.** If you find pirated copies, impersonation or unauthorized commercial use, please contact the author. Sharing this work takes effort; please do not misappropriate it.
>
> [Contact the author](https://github.com/kissqy/Microduck-kissqy/blob/main/docs/assets/purchase-wechat-qr.jpg) · [License scope](https://github.com/kissqy/Microduck-kissqy/blob/main/LICENSE). The repository’s existing licenses determine the scope of this notice.

Scope: Microduck-kissqy, Radxa ZERO 3W, Feetech HD1910, Robot Console V167 / control.43. Author: kissqy. Updated October 23, 2026. [Complete replica build guide](MICRODUCK-BUILD-GUIDE.en.md).

## What does a Microduck replica cost, and where is the BOM?

The [shopping guide and cost breakdown](../DUCK-SHOPPING-LIST.en.md) separate body parts, HAT, IMU and tools using historical orders. Check the stated scope for printing, equipment, consumables, labor and unpriced items; the priced-material subtotal is not everyone's final build cost.

## Where are the replica STL files and 3MF plates?

The [FrankenDuck printing page](../hardware/3d-print-frankenduck/README.en.md) provides STLs, a five-plate 3MF project, previews and checksums. Adapt slicing to your printer and materials, and check the battery-holder and IMU mounting scope.

## What do I download for the HD1910 build?

For normal operation, download System Image R1 and Robot Console V167. Add Training Studio R1.5.27 when training your own movements. Use the [Downloads table](../README.en.md#downloads-and-versions).

R1 includes control.40; install V167's bundled firmware to update to control.43. These identifiers distinguish the image contents from the current stable runtime.

## Can the online demo connect to my robot?

No. The GitHub Pages consoles demonstrate the interfaces with simulated data. Extract and run the local Robot Console, then enter ZERO's SSH connection details. See the [V167 user guide](../microduck-hd1910/firmware/console/USER-GUIDE.en.md).

## Why flash the IMU separately after imaging ZERO?

ZERO and the IMU's STM32 are separate devices. The system image and robot services run on ZERO; a newly built IMU needs FT6 firmware. Downloads, SWD wiring and checks are in the [IMU guide](../hardware/IMU-FIRMWARE.en.md).

## Why does ZERO lose Wi-Fi or SSH when the gamepad connects?

The author encountered interference between 2.4 GHz Wi-Fi and the wireless gamepad. Configure ZERO to use **5 GHz Wi-Fi** and verify the actual frequency, not just the SSID. Commands and details are in the [assembly notes](ASSEMBLY-NOTES.en.md).

An SSH timeout alone does not establish interference. Also check whether ZERO rebooted and whether Wi-Fi stayed connected.

## Why does ZERO reboot during high-load servo movements?

In the author's build, missing main-input buffering made servo transients prone to triggering reboots. This project's assembly notes call for **1000 µF across the main power input**. Follow the [power notes](ASSEMBLY-NOTES.en.md) for placement, polarity and voltage rating. If reboots persist, inspect the battery, supply, wiring, connectors and voltage drop under load; a capacitor does not replace sufficient supply capability.

## Can I copy the author's calibration if directions or posture look wrong?

Do not copy it blindly. Verify your robot's joint zero positions, directions, limits and IMU mounting. Compare console feedback with physical movement before enabling policies. Increasing force does not correct wrong directions or mechanical assembly. Follow the [Robot Console guide](../microduck-hd1910/firmware/console/USER-GUIDE.en.md).

## Which HAT and IMU connector versions exist?

The repository retains original EH2.5 and AMP2.0 variants. The latter uses Feetech AMP2.0 servo connectors; audio connectors and the added LED are detailed in the [variant guide](../hardware/AMP2.0-VERSION.en.md). Projects and purchase links are on the [hardware page](../hardware/README.en.md); see the [HAT](../hardware/HAT-TIMELINE.en.md) and [IMU](../hardware/IMU-TIMELINE.en.md) build records.

## Must I remove servos to swap feet and rollers?

The current [FrankenDuck kit](../hardware/3d-print-frankenduck/README.en.md) includes a foot structure that accepts rollers without servo removal. Bearings are 623ZZ, 3 × 10 × 4 mm. Use the matching parts and material profiles. Both battery-holder IMU mounts fit this repository's IMU.

## Does training need ZERO? Does simulation prove real-robot performance?

Training Studio runs independently; training itself does not require ZERO. Read or import calibration when needed according to the guide. Assembly, calibration, dynamics and power differ between simulation and hardware, so simulation cannot replace physical validation. See the [training guide](../microduck-hd1910/training-console/USER-GUIDE.en.md).

## What should an issue report include?

Provide hardware and connector variants, console version, running firmware identifier, reproduction steps, symptoms and logs or video in [Issues](https://github.com/kissqy/Microduck-kissqy/issues). Distinguish connection failure, service startup failure, bus communication errors and movement problems.

[Build guide](MICRODUCK-BUILD-GUIDE.en.md) · [Documentation index](README.en.md) · [Repository](../README.en.md)

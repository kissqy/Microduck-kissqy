[简体中文](MICRODUCK-FAQ.md) | **English**

# Microduck Feetech replica FAQ: setup, calibration, IMU, gamepad Wi-Fi interference and power reboots

> [!WARNING]
> Only the **HAT, IMU and HUB** versions published in this repository are supported.
>
> No commercial organization has been authorized. For commercial use, [contact the author](https://github.com/kissqy/Microduck-kissqy/blob/main/docs/assets/purchase-wechat-qr.jpg) and follow the [license terms](https://github.com/kissqy/Microduck-kissqy/blob/main/LICENSE).

Scope: Microduck-kissqy, Radxa ZERO 3W, Feetech HD1910, System Image R2, Robot Console V260 / control.102 and Wi-Fi setup R10. Author: kissqy. Updated November 14, 2026. [Complete replica build guide](MICRODUCK-BUILD-GUIDE.en.md).

## What does a Microduck replica cost, and where is the BOM?

The [shopping guide and cost breakdown](../DUCK-SHOPPING-LIST.en.md) separate body parts, HAT, IMU and tools using historical orders. Check the stated scope for printing, equipment, consumables, labor and unpriced items; the priced-material subtotal is not everyone's final build cost.

## Where are the replica STL files and 3MF plates?

The [FrankenDuck printing page](../hardware/3d-print-frankenduck/README.en.md) provides STLs, a five-plate 3MF project, previews and checksums. Adapt slicing to your printer and materials, and check the battery-holder and IMU mounting scope.

## What do I download for the HD1910 build?

For a fresh installation, download [System Image R2](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v260) and [Robot Console V260](https://github.com/kissqy/Microduck-kissqy/blob/main/versions/v260/README.md). Add Training Studio R1.5.27 when training your own movements. Use the [Downloads table](../README.en.md#downloads-and-versions).

R2 includes V260 / control.102 and pairs with Robot Console V260. **Upgrading from V167 to V260 does not require reflashing the system or microSD card.** Download and fully extract Console V260, connect to ZERO, then install its bundled firmware directly through Console V260. Use the R2 image for a fresh installation or when reflashing is needed. Do not import V260 firmware through V167. [Historical Image R1](releases/public-image-r1.en.md) and the verified V167 / control.43 baseline remain available. This release does not replace existing real-robot Known-Good records.

At boot, R2 waits for the Wi-Fi adapter and network service, then tries saved networks. If none connects, it opens the setup hotspot. A later disconnection does not automatically enable the hotspot; use the console to enable it manually.

## Can the online demo connect to my robot?

No. The GitHub Pages consoles demonstrate the interfaces with simulated data. Extract and run the local Robot Console, then enter ZERO's SSH connection details. See the [V260 release and usage guide](https://github.com/kissqy/Microduck-kissqy/blob/main/versions/v260/README.md).

<a id="linux-ssh-askpass"></a>

## Why does the Linux console fail to connect with ssh-askpass permission denied?

**Symptoms:** The console reports SSH/sudo authentication or SSH port-forwarding failure, and the detailed log contains:

```text
ssh_askpass: exec(.../Microduck-Console-Studio-V260/ssh-askpass): Permission denied
Permission denied (publickey,password).
```

**Cause:** The Linux computer running the console cannot execute its local `ssh-askpass` password helper. A common cause is a missing execute permission after extraction. This error alone does not establish that ZERO's login password is wrong.

**Solution:**

1. On **the Linux computer running the console**, open the fully extracted console folder and open a terminal in that folder.
2. Restore execute permission for the helper:

   ```bash
   chmod u+x ./ssh-askpass
   ```

3. Return to the console and click **Reconnect**.

If the same `ssh_askpass: exec(...): Permission denied` error persists, check file and directory access permissions and whether the filesystem prohibits execution (`noexec`). If the helper error disappears but authentication still fails, verify ZERO's SSH address, username and password.

## Why flash the IMU separately after imaging ZERO?

ZERO and the IMU's STM32 are separate devices. The system image and robot services run on ZERO; a newly built IMU needs FT6 firmware. Downloads, SWD wiring and checks are in the [IMU guide](../hardware/IMU-FIRMWARE.en.md).

## Why does ZERO lose Wi-Fi or SSH when the gamepad connects?

The author encountered interference between 2.4 GHz Wi-Fi and the wireless gamepad. Configure ZERO to use **5 GHz Wi-Fi** and verify the actual frequency, not just the SSID. Commands and details are in the [assembly notes](ASSEMBLY-NOTES.en.md).

An SSH timeout alone does not establish interference. Also check whether ZERO rebooted and whether Wi-Fi stayed connected.

## Why does ZERO reboot during high-load servo movements?

In the author's build, missing main-input buffering made servo transients prone to triggering reboots. This project's assembly notes call for **1000 µF across the main power input**. Follow the [power notes](ASSEMBLY-NOTES.en.md) for placement, polarity and voltage rating. If reboots persist, inspect the battery, supply, wiring, connectors and voltage drop under load; a capacitor does not replace sufficient supply capability.

## Can I copy the author's calibration if directions or posture look wrong?

Do not copy it blindly. Verify your robot's joint zero positions, directions, limits and IMU mounting. Compare console feedback with physical movement before enabling policies. Increasing force does not correct wrong directions or mechanical assembly. Follow the [V260 release guide](https://github.com/kissqy/Microduck-kissqy/blob/main/versions/v260/README.md), bundled instructions and runtime prompts. The [V167 guide](../microduck-hd1910/firmware/console/USER-GUIDE.en.md) remains a historical reference.

## Which HAT and IMU connector versions exist?

The repository retains original EH2.5 and AMP2.0 variants. The latter uses Feetech AMP2.0 servo connectors; audio connectors and the added LED are detailed in the [variant guide](../hardware/AMP2.0-VERSION.en.md). Projects and purchase links are on the [hardware page](../hardware/README.en.md); see the [HAT](../hardware/HAT-TIMELINE.en.md) and [IMU](../hardware/IMU-TIMELINE.en.md) build records.

## Must I remove servos to swap feet and rollers?

The current [FrankenDuck kit](../hardware/3d-print-frankenduck/README.en.md) includes a foot structure that accepts rollers without servo removal. Bearings are 623ZZ, 3 × 10 × 4 mm. Use the matching parts and material profiles. Both battery-holder IMU mounts fit this repository's IMU.

## Does training need ZERO? Does simulation prove real-robot performance?

Training Studio runs independently; training itself does not require ZERO. Read or import calibration when needed according to the guide. Assembly, calibration, dynamics and power differ between simulation and hardware, so simulation cannot replace physical validation. See the [training guide](../microduck-hd1910/training-console/USER-GUIDE.en.md).

## What should an issue report include?

Provide hardware and connector variants, console version, running firmware identifier, reproduction steps, symptoms and logs or video in [Issues](https://github.com/kissqy/Microduck-kissqy/issues). Distinguish connection failure, service startup failure, bus communication errors and movement problems.

[Build guide](MICRODUCK-BUILD-GUIDE.en.md) · [Documentation index](README.en.md) · [Repository](../README.en.md)

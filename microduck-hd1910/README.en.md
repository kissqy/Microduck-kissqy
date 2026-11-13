[简体中文](README.md) | **English**

# Microduck HD1910 · compatibility directory

Version navigation is now grouped under [versions/](../versions/): [V260](../versions/v260/) and [V167](../versions/v167/README.en.md). This original directory remains available for existing source, documentation and download links; no branch switching is needed.

A Feetech HD1910 adaptation based on official Microduck **0.15.1**, including robot firmware, the R17 Robot Console, and an independent Training Studio. Reference hardware: Radxa ZERO 3W, official chassis, and 15 HD1910 servos. This is a personal community project with no official affiliation to Pollen Robotics.

**Source-available under component licenses. Original material explicitly covered by personal noncommercial terms requires written permission for commercial or organizational use. Other material retains its applicable license. See [LICENSE](LICENSE).**

**Current downloads: System Image R2 + Console Studio V260 / control.102, Wi-Fi setup R10.** Updated November 13, 2026. [Release downloads](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v260) · [package guide](https://github.com/kissqy/Microduck-kissqy/blob/main/versions/v260/README.md). The original V167 / control.43 source in this directory is retained.

**The author's assembled IMU is pre-flashed with FT6; no initial flashing is needed. Calibrate it after installation.** For a new self-soldered board, replacement MCU or maintenance, see the [FT6 guide](../hardware/IMU-FIRMWARE.en.md); installing robot-service firmware on ZERO does not program the external IMU.

## Current release and separate source

| Component | Version | Source or release |
| --- | --- | --- |
| Robot firmware and device services | Official 0.15.1 · control.102 | [V260 firmware source](https://github.com/kissqy/Microduck-kissqy/tree/main/versions/v260/firmware) |
| Robot Console | Studio V260 (R17) | [V260 console source](https://github.com/kissqy/Microduck-kissqy/tree/main/versions/v260/console) |
| Public system image | R2 · first-boot Wi-Fi R10 | [Image release](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v260) |
| Training Studio | R1.5.27 | [Training Studio guide](training-console/README.en.md) |
| Historical robot firmware and console | V167 / control.43 | [V167 firmware](../versions/v167/microduck-hd1910/firmware/) · [V167 console](../versions/v167/microduck-hd1910/firmware/console/) |

V260 source is grouped under `versions/v260/`; V167 source and build assets are grouped under `versions/v167/`, preserving their original internal paths. This compatibility directory retains V167 / control.43. R1 and V167 packages and their validation records remain available; this release does not change the recorded real-robot Known-Good scope.

## Download and use

1. [Download Image R2](https://github.com/kissqy/Microduck-kissqy/releases/download/console-studio-v260/microduck-kissqy-zero3w-R2.img.xz) and flash it to a microSD card with [Armbian Imager](https://imager.armbian.com/).
2. If the system cannot connect to saved Wi-Fi on boot, join `Microduck-kissqy` (password `12345678`), then configure home Wi-Fi and a new system login password. If the page does not open automatically, visit `http://10.42.0.1:8088`.
3. [Open V260 release downloads](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v260) and download the complete Console Studio V260 package, extract everything, and run `start.cmd`; on macOS / Linux run `bash start.command`. The local page is `http://127.0.0.1:8090`.
4. Enter your own `username@robot-IP` and SSH details. Check your robot's calibration, then follow **HOME → hold → walk**. The image preinstalls robot services; upgrade an existing system using “系统维护 → 随包固件” (System Maintenance → Bundled Firmware).
5. For training, [download Training Studio R1.5.27](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/versions/v167/release-assets/Microduck-Training-Studio-R1.5.27.zip), run `start-training.cmd` or `bash start-training.command`, and open `http://127.0.0.1:8092`.

Training uses an NVIDIA GPU and Linux / WSL2. Install Git and [uv](https://docs.astral.sh/uv/getting-started/installation/) first. Initial environment preparation downloads a pinned training engine and dependencies. There are currently 14 action categories and 35 task recipes; see the [training user guide](training-console/USER-GUIDE.en.md).

## Using the source

- V260 console and firmware: [independent source tree](https://github.com/kissqy/Microduck-kissqy/tree/main/versions/v260) and [resource restoration / build guide](https://github.com/kissqy/Microduck-kissqy/blob/main/versions/v260/README.md).
- Historical V167 Robot Console launcher: `versions/v167/microduck-hd1910/firmware/console/start.cmd` or `start.command` from the repository root.
- Training Studio launcher: `training-console/start-training.cmd` or `start-training.command`.
- Historical V167 firmware compilation: [BUILD.md](../versions/v167/microduck-hd1910/docs/BUILD.en.md). Compilation is not required for daily use.
- Release versions and validation scope: [BASELINE.md](docs/BASELINE.en.md). Provenance and checksums: [PUBLICATION-MANIFEST.json](PUBLICATION-MANIFEST.json).
- Licensing and third-party sources: [LICENSE](LICENSE) · [THIRD-PARTY.md](docs/THIRD-PARTY.en.md).

[Historical R1 image](https://github.com/kissqy/Microduck-kissqy/releases/tag/public-image-r1) · [V167 console ZIP](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/versions/v167/release-assets/Microduck-Console-R17-V167.zip) · [control.43 firmware guide](../versions/v167/release-assets/README.en.md). Each robot needs its own joint zero, direction, limit, and IMU checks; publication of source does not expand the original real-robot acceptance scope.

Licensing details: [software and self-trained model rights](docs/SOFTWARE-MODEL-RIGHTS.en.md) · [model provenance](docs/MODEL-PROVENANCE.en.md) · [component licenses](LICENSE).

[简体中文](README.md) | **English** | [Русский](README.ru.md)

# Microduck HD1910

A Feetech HD1910 adaptation based on official Microduck **0.15.1**, including robot firmware, the R17 Robot Console, and an independent Training Studio. Reference hardware: Radxa ZERO 3W, official chassis, and 15 HD1910 servos. This is a personal community project with no official affiliation to Pollen Robotics.

**Source is published; the author's original work is licensed for personal noncommercial use only. Third-party content retains its original licenses. See [LICENSE](LICENSE).**

**Compiled firmware is available.** control.43 is already supplied in Public Image R1 and Robot Console V167; see the [standalone package and installation guide](../release-assets/README.en.md).

**Flash STM32 FT6 separately on a newly built IMU:** [download and flashing guide](../hardware/IMU-FIRMWARE.en.md); installing control.43 on ZERO does not program the external IMU.

## Current versions and source

| Component | Current version | Source |
| --- | --- | --- |
| Robot firmware and device services | Official 0.15.1 · control.43 · API40 | [firmware/](firmware/README.en.md) |
| Robot Console | R17 V167 (1.0.167) | [Robot Console guide](firmware/console/README.en.md) |
| Training Studio | R1.5.27 | [Training Studio guide](training-console/README.en.md) |
| Public system image | Public Image R1 · first-boot setup R5 | [Image release](https://github.com/kissqy/Microduck-kissqy/releases/tag/public-image-r1) |

V167 includes compiled **control.43** firmware. Update: **Fixed body jitter.** Current `firmware/BUILD.json` matches the BUILD record in the V167 payload. Both consoles' program sources match their respective ZIPs.

## Download and use

1. [Download Image R1](https://github.com/kissqy/Microduck-kissqy/releases/download/public-image-r1/microduck-zero3w-0.15.1-R1.img.xz) and flash it to a microSD card with [Armbian Imager](https://imager.armbian.com/).
2. On first boot, join `Microduck-kissqy` (password `12345678`), then configure home Wi-Fi and a new system login password. If the page does not open automatically, visit `http://10.42.0.1:8088`.
3. [Download Robot Console V167](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/release-assets/Microduck-Console-R17-V167.zip), extract everything, and run `start.cmd`; on macOS / Linux run `bash start.command`. The local page is `http://127.0.0.1:8090`.
4. Enter your own `username@robot-IP` and SSH details. Check your robot's calibration, then follow **HOME → hold → walk**. The image preinstalls robot services; upgrade an existing system using “系统维护 → 随包固件” (System Maintenance → Bundled Firmware).
5. For training, [download Training Studio R1.5.27](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/release-assets/Microduck-Training-Studio-R1.5.27.zip), run `start-training.cmd` or `bash start-training.command`, and open `http://127.0.0.1:8092`.

Training uses an NVIDIA GPU and Linux / WSL2. Install Git and [uv](https://docs.astral.sh/uv/getting-started/installation/) first. Initial environment preparation downloads a pinned training engine and dependencies. There are currently 14 action categories and 35 task recipes; see the [training user guide](training-console/USER-GUIDE.en.md).

## Using the source

- Robot Console launcher: `firmware/console/start.cmd` or `start.command`.
- Training Studio launcher: `training-console/start-training.cmd` or `start-training.command`.
- Firmware compilation: [BUILD.md](docs/BUILD.en.md). Compilation is not required for daily use.
- Release versions and validation scope: [BASELINE.md](docs/BASELINE.en.md). Provenance and checksums: [PUBLICATION-MANIFEST.json](PUBLICATION-MANIFEST.json).
- Licensing and third-party sources: [LICENSE](LICENSE) · [THIRD-PARTY.md](docs/THIRD-PARTY.en.md).

Each robot needs its own joint zero, direction, limit, and IMU checks. Programs, models, and existing control implementation were synchronized from the delivery packages; publication of source does not expand the original real-robot acceptance scope.

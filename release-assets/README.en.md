[简体中文](README.md) | **English**

# Compiled Feetech HD1910 firmware · control.43

> [!WARNING]
> **Hardware compatibility and commercial authorization**
>
> **HAT, IMU and HUB versions outside the designs published in this repository are incompatible with this repository’s system and may prevent it from operating normally.**
>
> **This repository has not authorized any commercial organization.** If you find pirated copies, impersonation or unauthorized commercial use, please contact the author. Sharing this work takes effort; please do not misappropriate it.
>
> **Scam warning: Do not trust private sales messages from anyone other than the group owner. Group members have already been scammed.**
>
> [Contact the author](https://github.com/kissqy/Microduck-kissqy/blob/main/docs/assets/purchase-wechat-qr.jpg) · [License scope](https://github.com/kissqy/Microduck-kissqy/blob/main/LICENSE). The repository’s existing licenses determine the scope of this notice.

An **ARM64 robot-service installation package for Radxa ZERO 3W**, based on official Microduck 0.15.1 and paired with Robot Console R17 V167, IPC API40. It includes compiled `robotd`, `padd`, `robotctl`, camera services, inference libraries, 10 movement models, and installation scripts. **No source compilation is required for ordinary use.**

[⬇️ Download compiled firmware .tar.gz](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/microduck-hd1910/firmware/console/updates/Microduck-Robotd-FT6-R17.tar.gz) · [SHA256 file](Microduck-Robotd-FT6-R17.sha256) · [Identity and verification record](firmware-control43.json) · [Project homepage](../README.en.md)

**Update: Fixed body jitter.**

**The author's assembled IMU already has FT6 firmware and needs no initial flashing.** Use the [IMU download and flashing guide](../hardware/IMU-FIRMWARE.en.md) for self-soldered boards, replacement MCUs, maintenance or upgrades. Installing control.43 on ZERO does not program the external IMU. Calibrate each robot after installation.

## Image, console, and standalone firmware

| Package | Purpose |
| --- | --- |
| System image `.img.xz` | Fresh microSD installation with control.40 and the robot environment preinstalled; upgrade to control.43 using V167 bundled firmware. |
| Robot Console V167 `.zip` | Computer-side control tool; `updates/` contains this same compiled firmware. |
| Standalone `.tar.gz` here | The exact V167 firmware payload, offered separately for existing-system upgrades. |

**Ordinary users need the system image and Robot Console.** Image R1 still includes control.40. After flashing, install V167 bundled firmware to upgrade to control.43. This package updates ZERO Linux services. IMU DIY programming or maintenance uses a separate `.bin`; the author's assembled IMU is already preflashed with FT6. This `.tar.gz` is not a microSD system image.

## Install with the console

Extract the complete [Robot Console V167](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/release-assets/Microduck-Console-R17-V167.zip), run `start.cmd` (macOS/Linux: `bash start.command`), connect to ZERO over SSH, and use **系统维护 → 随包固件** (System Maintenance → Bundled Firmware). The console already includes this payload; no separate `.tar.gz` download is needed for that flow.

Local firmware import accepts ZIP rather than a bare `.tar.gz`. If you downloaded this standalone package, wrap the unchanged archive in ZIP using Windows PowerShell:

```powershell
Compress-Archive -Path .\Microduck-Robotd-FT6-R17.tar.gz -DestinationPath .\Microduck-Firmware-control43.zip
```

Select that ZIP in V167's firmware importer. Keep the inner name `Microduck-Robotd-FT6-R17.tar.gz`; the console verifies its SHA256 against the matched bundled firmware.

## Install separately over SSH

Use on ZERO with an existing official Microduck 0.15.1 or this project's Public Image R1 environment. **Run the commands in ZERO's SSH terminal.** For an empty microSD card, start with the system image instead.

```bash
(
  set -e
  microduck_fw_dir=$(mktemp -d "$HOME/microduck-control43.XXXXXX")
  curl -fL --progress-bar \
    -o "$microduck_fw_dir/Microduck-Robotd-FT6-R17.tar.gz" \
    "https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/microduck-hd1910/firmware/console/updates/Microduck-Robotd-FT6-R17.tar.gz"
  printf '%s  %s\n' \
    'bcfd5c183c697b9c4e0fdbd563d995eda6a48331a7c49b9e76d20bd156c65cce' \
    "$microduck_fw_dir/Microduck-Robotd-FT6-R17.tar.gz" | sha256sum -c -
  tar -xzf "$microduck_fw_dir/Microduck-Robotd-FT6-R17.tar.gz" -C "$microduck_fw_dir"
  sudo bash "$microduck_fw_dir/Microduck-Robotd-FT6-R17/service.sh" upgrade
)
```

Download progress is shown; a failed checksum stops the commands. The existing `service.sh upgrade` flow reads and prioritizes valid local calibration and saved settings. Wait for startup steps 1/4–4/4, verify this assembly's joints and IMU, then complete HOME before enabling movement.

## Identity and checksum

| Item | Value |
| --- | --- |
| Build | `1fa8438-feetech-ft6-control.43` |
| Official baseline / API | `0.15.1` / `40` |
| Console | `R17 V167` |
| Architecture | Linux AArch64 / ARM64 |
| Size | 34138802 bytes (approximately 32.56 MiB) |
| SHA256 | `bcfd5c183c697b9c4e0fdbd563d995eda6a48331a7c49b9e76d20bd156c65cce` |

This cleanup verified byte identity with V167 bundled firmware and all 160 archive checksum entries. Prior build records are in [the V167 guide](../microduck-hd1910/firmware/BUILDING-V167.en.md).

[Firmware source and versions](../microduck-hd1910/firmware/README-R17.en.md) · [Build from source](../microduck-hd1910/docs/BUILD.en.md) · [Component licenses](../microduck-hd1910/LICENSE)

## Software and policy licenses

Original consoles/tools and self-trained models explicitly covered by personal noncommercial terms are limited to that scope; commercial/organizational use requires prior written permission. Runtime firmware and dependencies retain their original licenses. See [software/model rights](../microduck-hd1910/docs/SOFTWARE-MODEL-RIGHTS.en.md) and [model provenance](../microduck-hd1910/docs/MODEL-PROVENANCE.en.md).

This updates repository/download-page documentation without repacking the ZIPs, payload or image, or changing program/weight bytes. Inspect notices actually contained in each historical package; previously valid grants remain effective.

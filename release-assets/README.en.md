[简体中文](README.md) | **English** | [Русский](README.ru.md)

# Compiled Feetech HD1910 firmware · control.43

An **ARM64 robot-service installation package for Radxa ZERO 3W**, based on official Microduck 0.15.1 and paired with Robot Console R17 V167, IPC API40. It includes compiled `robotd`, `padd`, `robotctl`, camera services, inference libraries, 10 movement models, and installation scripts. **No source compilation is required for ordinary use.**

[⬇️ Download compiled firmware .tar.gz](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/microduck-hd1910/firmware/console/updates/Microduck-Robotd-FT6-R17.tar.gz) · [SHA256 file](Microduck-Robotd-FT6-R17.sha256) · [Identity and verification record](firmware-control43.json) · [Project homepage](../README.en.md)

**Update: Fixed body jitter.**

**Flash STM32 FT6 separately on a newly built IMU:** [download and flashing guide](../hardware/IMU-FIRMWARE.en.md); installing control.43 on ZERO does not program the external IMU.

## Image, console, and standalone firmware

| Package | Purpose |
| --- | --- |
| System image `.img.xz` | Fresh microSD installation with control.40 and the robot environment preinstalled; upgrade to control.43 using V167 bundled firmware. |
| Robot Console V167 `.zip` | Computer-side control tool; `updates/` contains this same compiled firmware. |
| Standalone `.tar.gz` here | The exact V167 firmware payload, offered separately for existing-system upgrades. |

**Ordinary users need the system image and Robot Console.** Image R1 still includes control.40. After flashing, install V167 bundled firmware to upgrade to control.43. This package updates ZERO Linux services; HAT/IMU microcontroller firmware uses separate `.bin` files. This `.tar.gz` is not a microSD system image.

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

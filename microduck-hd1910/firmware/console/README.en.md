[简体中文](README.md) | **English** | [Русский](README.ru.md)

# 🎮 Microduck Robot Console · R17 V167

A Chinese-language console for a real robot duck: view pose and device feedback, calibrate joints and IMU, use a gamepad, manage movement models, and maintain robot firmware.

**Current pairing: Radxa ZERO 3 W · Feetech HD1910 · Official Microduck 0.15.1 · control.43 firmware.**

[⬇️ Download the complete V167 console](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/release-assets/Microduck-Console-R17-V167.zip) · [Detailed user and gamepad guide](USER-GUIDE.en.md) · [Project homepage](../../../README.en.md)

## Features

| Feature | Purpose |
| --- | --- |
| Live 3 D and device feedback | Robot pose, feedback from 15 servos, joint curves, and IMU body orientation. |
| Joint workbench | Check local zero positions, directions, limits, and IMU installation; calibrate after assembly. |
| Gamepad control | Walk, sit / stand, pick up, roll, kick, and use rollers with a physical gamepad; Chinese button explanations are shown on the page. |
| Model management | Inspect installed models and deployment parameters; import self-trained models of supported types. |
| Camera | Connect to the head camera and start or end video sessions on demand. |
| System maintenance | Inspect ZERO status, change volume, install bundled firmware, reboot, or shut down. |
| Recording and replay | Export observations and review debugging sessions in joint curves and the 3 D view. |

V167's firmware includes **10 movement models: 6 regular and 4 roller models**. The [detailed guide](USER-GUIDE.en.md) owns the button mappings, mode changes, action conditions, and deployment parameters.

## Download and start

Extract the complete runtime ZIP above and open the folder containing `start.cmd`. Your computer needs Python 3 and the OpenSSH `ssh` command; Python 3.10 or newer is recommended.

| Computer | Launcher |
| --- | --- |
| Windows | Double-click `start.cmd`; the script uses your installed Python. |
| macOS / Linux | Run `bash start.command` in this directory. |
| Direct Python launch | Run `python3 console.py --dashboard --feetech --open` here. |

The browser opens the console; you can also visit **http://127.0.0.1:8090** manually. Keep the launch terminal running.

Source in this directory uses the same launchers. For ordinary use, download the full runtime ZIP, which includes page assets and the firmware payload.

## First connection

1. Put your computer and ZERO on the same LAN. Wait for ZERO to boot and find its IP address.
2. Fill in **SSH 地址** (SSH address) as `username@robot-IP`, for example `radxa@your-robot-IP`.
3. Enter **SSH / sudo 密码** (SSH / sudo password) and click **连接** (Connect). Follow the page's guidance when credentials are saved or key authentication is configured.
4. Wait for robot-service startup **1/4–4/4**, then inspect feedback, IMU status, and model loading.
5. After initial assembly or servo replacement, check your own zero positions, directions, limits, and IMU in the joint workbench, then perform HOME.
6. After HOME completes, enable the movement policy and use the gamepad. Physical gamepad input takes priority over page input.

The released integrated image already includes robot services. To install or upgrade services on another existing system, use **系统维护 → 随包固件** (System Maintenance → Bundled Firmware). If ZERO already runs control.43, follow the version guide when updating only the computer-side console.

## Daily use

- **Walking and actions:** complete HOME, enable the policy, then use sticks and action buttons. See [gamepad mappings](USER-GUIDE.en.md#other-buttons) for Start, sit / stand, kicks, and rolls.
- **Rollers:** use the physical gamepad to switch walking / roller modes and roller actions; see [roller controls](USER-GUIDE.en.md#physical-gamepad-roller-controls).
- **Calibration:** use this robot's actual assembly data; see [calibration and settings](USER-GUIDE.en.md#calibration-and-settings).
- **Finish:** release torque using the page or gamepad. Press Ctrl+C in the launch terminal and wait for exit before closing the console process.

## Related guides

- [Standalone compiled firmware and installation](../../../release-assets/README.en.md)
- [Detailed user guide](USER-GUIDE.en.md)
- [Robot firmware source and version guide](../README-R17.en.md)
- [Firmware build guide](../../docs/BUILD.en.md)
- [Independent Training Studio](../../training-console/README.en.md)
- [License](LICENSE) · [Third-party notices](THIRD_PARTY_NOTICES.en.md)

If ZERO still runs control.40 or an older build, install V167 bundled firmware to upgrade to control.43.

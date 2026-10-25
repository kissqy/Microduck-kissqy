[简体中文](public-image-r1.md) | **English** | [Русский](public-image-r1.ru.md)

# 🦆 Microduck integrated system image R1

**Flash the image, connect to Wi-Fi, and open the console to get your duck moving!**

This Radxa ZERO 3 W image is based on Pollen Robotics' official Microduck 0.15.1. It comes with this project's Feetech HD1910 firmware adaptation, robot services, and movement models preinstalled. **You do not need to compile or individually install the ZERO-side software.**

> ✅ **A physical ZERO has passed a fresh-image installation check:** boot, first-boot hotspot setup, home Wi-Fi connection, SSH, robot bus communication, and R17 console recognition all worked. Motion and model performance on a different assembly still require local validation.

## 🚀 Three steps to start

**① Flash the system**

Download `microduck-zero3w-0.15.1-R1.img.xz` from this release.

Use **[Armbian Imager](https://imager.armbian.com/)**; [GitHub installers](https://github.com/armbian/imager/releases) are also available. Select a custom image and your microSD card, then flash it. **You do not need to unpack `.img.xz` manually: Armbian Imager decompresses it automatically.**

**② Join the hotspot and configure your home Wi-Fi**

Insert the card into the Radxa ZERO 3 W, power it on, and connect to:

- Network: `Microduck-kissqy`
- Password: `12345678`

Enter your home Wi-Fi details and a new system login password on the setup page. If it does not open automatically, visit `http://10.42.0.1:8088`.

**③ Open the Chinese-language console**

Run the Microduck R17 console on your computer and connect to ZERO to view the camera, 3 D pose, joints, and IMU status. Before using a physical gamepad, **check the zero positions, directions, limits, and IMU installation for your own 15-joint assembly**, then perform HOME, hold, and movement.

## 📦 Versions

| Component | Version |
| --- | --- |
| Official software baseline | Microduck 0.15.1 |
| Robot firmware adaptation | V164 · control.40 |
| Robot Console | R17 V164, supplied as a separate package |
| Training Studio | R1.5.27, supplied as a separate package |
| First-boot Wi-Fi setup | R5 |
| Hardware | Radxa ZERO 3 W + supported HD1910 / IMU assembly |

The image includes ZERO-side firmware and models. **The Windows consoles are separate tools** and are not automatically installed on your computer by flashing the image. The repository's online demos show earlier versions with simulated data and cannot control a physical robot.

## 📥 Image checksum

```text
microduck-zero3w-0.15.1-R1.img.xz
SHA256: 75da978b5d56acd9e4146256431732381de84523bb683e4ab7ac9f0580a7bce5
```

## ❤️ A personal robotics project, starting from components

The project includes circuits and PCBs, HD1910 adaptation, the R17 console, Training Studio, and self-trained movement models. The author developed the code with ChatGPT assistance, hoping to make robotics development more approachable for newcomers.

Repository: <https://github.com/kissqy/Microduck-kissqy>

**Licensing:** original work owned and independently licensable by the author is provided for personal learning, research, and noncommercial use only; obtain written permission for commercial use. Official Apache-2.0 firmware, third-party software, geometry, and model assets retain their own licenses. Personal terms do not override third-party rights. See the [component license](../../microduck-hd1910/LICENSE) and [third-party guide](../../microduck-hd1910/docs/THIRD-PARTY.en.md).

**Release conditions:** this image provides a validated reference software environment. Joint limits and motor directions from one assembly cannot be assumed correct for another; the operator must check movement conditions locally.

[简体中文](README.md) | **English** | [Русский](README.ru.md)

<div align="center">

# 🦆 Microduck Feetech HD1910 Replica · Build, control and reinforcement learning

A personal project with a working physical replica based on Pollen Robotics Microduck, providing a **Radxa ZERO 3W system image, Feetech HD1910 firmware, Chinese-language robot and training consoles, DIY HAT / IMU boards and complete 3D printing files** for building, running and training a bipedal robot duck.

**Stable public release: V167 / control.43 · Author: kissqy**

[🚀 Complete replica build guide](docs/MICRODUCK-BUILD-GUIDE.en.md) · [❓ FAQ](docs/MICRODUCK-FAQ.en.md) · [🌐 Read the guides online](https://kissqy.github.io/Microduck-kissqy/guides/en.html)

**An integrated ZERO 3W firmware image · Official Microduck 0.15.1 · Feetech HD1910 support · Two Chinese-language consoles**

**Versions: Robot Console R17 V167 · Firmware control.43 · Training Studio R1.5.27 · First-boot Wi-Fi setup R5**

[🦆 **Duck shopping guide**](DUCK-SHOPPING-LIST.en.md) · [🖨️ **Complete printing set · FrankenDuck**](hardware/3d-print-frankenduck/README.en.md) · [📥 Downloads](#downloads-and-versions) · [📚 Guides](docs/README.en.md) · [🛠️ Source](microduck-hd1910/README.en.md) · [🌱 The author's learning journey](docs/AUTHOR-JOURNEY.en.md)

[🎮 Robot Console online demo](https://kissqy.github.io/Microduck-kissqy/) · [🧠 Training Studio online demo](https://kissqy.github.io/Microduck-kissqy/training/)

<table align="center">
  <tr>
    <td align="center" valign="top">
      <b>💬 Join the WeChat group</b><br><br>
      <a href="docs/assets/community-wechat-qr.png"><img width="220" alt="WeChat community group QR code" src="docs/assets/community-wechat-qr.png" /></a><br>
      <sub>Scan in WeChat, or click the QR code for the original image.<br>This QR code is valid before October 29, 2026.</sub>
    </td>
  </tr>
</table>

## 🎬 See the duck in action — 7 real-robot videos

<table>
<tr>
      <td width="10%"><video src="https://github.com/user-attachments/assets/0ec5b46b-1ec0-483a-a95d-3b3f307e155f" controls></video></td>
   <td width="10%"><video src="https://github.com/user-attachments/assets/71fc2c95-8499-49f6-924b-837df42814cf" controls></video></td>
  <td width="10%"><video src="https://github.com/user-attachments/assets/d09a6bfe-7a28-4266-ba90-de2b331472ad" controls></video></td>
  <td width="10%"><video src="https://github.com/user-attachments/assets/a604c0e0-af01-413f-ab00-99ccd26db8d5" controls></video></td>
  <td width="10%"><video src="https://github.com/user-attachments/assets/4508d91c-e91c-40f4-8c3e-5ca5a3f959c3" controls></video></td>
  <td width="10%"><video src="https://github.com/user-attachments/assets/fd0dfafd-dd02-4852-940c-33706c287e9d" controls></video></td>
  <td width="10%"><video src="https://github.com/user-attachments/assets/693a3272-d814-42f6-86b3-be5cb3b35b0f" controls></video></td>
</tr>
</table>

<sub>These clips show the real robot. The online demos now match the Robot Console R17 V167 and Training Studio R1.5.27 interfaces. They use simulated data and cannot connect to your robot or run actual training.</sub>


</div>

> ✅ **Public Image R1 is available!** The integrated image has passed a fresh-card installation test covering boot, Wi-Fi setup, SSH, robot communication, and R17 recognition. **No need to compile the robot firmware yourself.**
>
> 📦 **Robot Console R17 V167 and Training Studio R1.5.27 are ready to download.** Compiled control.43 firmware and both console sources are also published. All downloads are grouped in the table below.

## 🧭 Start with your goal

| Your goal | Go here |
| --- | --- |
| Build a Microduck with Feetech servos | [Parts to first walking: build guide](docs/MICRODUCK-BUILD-GUIDE.en.md) |
| Flash, calibrate and operate an assembled duck | [V167 user guide](microduck-hd1910/firmware/console/USER-GUIDE.en.md) |
| Train walking, recovery or your own movements | [Training Studio R1.5.27](microduck-hd1910/training-console/USER-GUIDE.en.md) |
| Build HAT and a separate IMU | [PCB projects, build records and flashing](hardware/README.en.md) |
| Troubleshoot network, reboot, IMU or calibration | [FAQ and troubleshooting links](docs/MICRODUCK-FAQ.en.md) |


---

## ✨ Skip the software setup from scratch

This little duck can **walk, sit, pick things up, kick a ball, and roll forward**. Add rollers to explore **swizzling, crouching, spinning, and standing up after a fall**. Use a physical gamepad to control it; an independent Training Studio is available when you want to train your own movements.

**Public Image R1 is released and has been tested by reflashing a real board.** It combines the official system with this project's preinstalled robot services and movement models. Flash it onto a Radxa ZERO 3W, connect to Wi-Fi, and open the console to use the prepared software environment without compiling firmware from source.

## 🚀 Start in three steps

1. **Flash the image** — Use the `.img.xz` from the Downloads table. In [Armbian Imager](https://imager.armbian.com/), select a custom image and your microSD card, then flash it. **Manual decompression is unnecessary:** the imager decompresses it while writing.
2. **Connect to Wi-Fi** — On first boot, join the `Microduck-kissqy` hotspot with password `12345678`. Follow the setup page to enter your home Wi-Fi and set a new system login password. If the page does not open automatically, visit `http://10.42.0.1:8088`.
3. **Open the console** — Extract the complete Robot Console ZIP and run `start.cmd`. Connect to the duck, check its calibration, and complete HOME before enabling movement. For training, extract Training Studio and run `start-training.cmd`.

> 🛠️ **Preinstalled software still requires calibration for your assembly.** After assembly or servo replacement, verify every joint's zero position, direction, limits, and the IMU before enabling movement. Do not copy the reference duck's calibration blindly.

<div align="center">
  <img src="docs/assets/wifi-setup-desktop.webp" width="760" alt="Microduck first-boot hotspot and Wi-Fi setup page" />
  <p><sub>First-boot Wi-Fi setup preview. The actual screen is the one shipped with Public Image R1.</sub></p>
</div>

## Downloads and versions

| Package | Purpose | Download |
| --- | --- | --- |
| **System Image R1** · Official 0.15.1 / control.40 | Fresh ZERO 3W installation; robot services and movement models preinstalled | [⬇️ .img.xz](https://github.com/kissqy/Microduck-kissqy/releases/download/public-image-r1/microduck-zero3w-0.15.1-R1.img.xz) |
| **Robot Console R17 V167** | Connect to and operate the duck from your computer; includes the matching firmware payload | [⬇️ ZIP](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/release-assets/Microduck-Console-R17-V167.zip) |
| **Training Studio R1.5.27** | Train, evaluate, and export your own models | [⬇️ ZIP](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/release-assets/Microduck-Training-Studio-R1.5.27.zip) |
| **Compiled Feetech HD1910 firmware control.43** | Upgrade ZERO-side services on an existing system; ARM64 installation package | [⬇️ .tar.gz](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/microduck-hd1910/firmware/console/updates/Microduck-Robotd-FT6-R17.tar.gz) |
| **IMU firmware FT6 (STM32)** | Flash a newly built torso IMU separately; 8.2 KiB, Feetech HD1910 setup | [⬇️ .bin](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/microduck-hd1910/firmware/console/updates/imu_to_feetech_ReVA_FT6_SYNC15_UART_IRQ_v1.bin) · [Flashing guide](hardware/IMU-FIRMWARE.en.md) |
| **Complete printing set · FrankenDuck** | 36 STL files, 5-plate 3MF project, two battery-holder variants | [⬇️ RAR](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/hardware/3d-print-frankenduck/Microduck-Print-FrankenDuck-20261015.rar) · [Guide](hardware/3d-print-frankenduck/README.en.md) |

**For ordinary use, download the system image and Robot Console.** Training Studio is optional. The standalone firmware matches V167 bundled control.43. Image R1 still includes control.40; install bundled firmware from V167 to upgrade after flashing. No compilation is required. **A newly built IMU also needs the separate FT6 `.bin`; system images and ZERO service upgrades do not program it.**

[Robot Console guide](microduck-hd1910/firmware/console/README.en.md) · [Training Studio guide](microduck-hd1910/training-console/README.en.md) · [Standalone firmware installation and checksums](release-assets/README.en.md) · [Image release guide](docs/releases/public-image-r1.en.md)

Source: [firmware](microduck-hd1910/firmware/README.en.md) · [Robot Console](microduck-hd1910/firmware/console/README.en.md) · [Training Studio](microduck-hd1910/training-console/README.en.md) · [build guide](microduck-hd1910/docs/BUILD.en.md). Current source matches V167 / control.43; duplicate compiled resources are restored when needed.

**V167 update: Fixed body jitter.**

## 🎮 Two consoles, two jobs

| 🐣 Robot Console · R17 V167 | 🧠 Training Studio · R1.5.27 |
| --- | --- |
| Live 3D pose, camera, joint / IMU data, servo calibration | Training tasks, recipes, queue, progress and reward curves |
| Physical gamepad control, firmware maintenance, model status | Visual simulation, policy evaluation, ONNX export |
| No need to compile the ZERO services yourself | Requires a computer with a training environment; the interface itself does not require a ZERO |

**V167 includes 10 movement models: 6 regular models and 4 roller models.** The control service executes the models; you do not have to hand-script servo movements. Roller movements and recovery depend on assembly, calibration, and training and still need careful real-robot evaluation.

**English instructions:** [Robot Console](microduck-hd1910/firmware/console/README.en.md) · [Training Studio](microduck-hd1910/training-console/README.en.md) · [Image setup](docs/releases/public-image-r1.en.md) · [Source / build guides](microduck-hd1910/README.en.md). The application interfaces in the current downloads remain Chinese; the English guides include the original button labels where needed.

## 🖨️ Complete printing set · FrankenDuck

This set combines community improvements with the author's real-robot modifications, including STL files and a reference plate project. **Install rollers without removing the servos.** Choose a HUB-clamping battery holder or the official-style holder with thicker latches; both IMU mounts fit this repository's IMU. Rollers use **623ZZ (3×10×4 mm)** bearings.

[Printing files, plate previews, and battery holders](hardware/3d-print-frankenduck/README.en.md) · [623ZZ purchasing](DUCK-SHOPPING-LIST.en.md#optional-roller-bearings)

**October 21 printing update:** Added leg support ramps for easier foot installation, removed outer leg-shell counterbores to reduce screw-hole breakage in falls, and integrated interchangeable feet based on the official roller shoes so swaps do not require servo removal.

## 🔧 DIY HAT and IMU

> 🛒 **[Buy HAT / IMU boards from the author](https://item.taobao.com/item.htm?id=1095121548583)**
>
> **Please note: these boards are fabricated at JLCPCB (嘉立创) and populated by the author. Ready to use on arrival, they are the same boards the author uses, validated through extended real-robot operation, with no jumper bridging required and no packet loss. Feetech AMP2.0 connectors make them convenient and easy to use.**

🎬 **[Watch the complete IMU build · Bilibili](https://www.bilibili.com/video/BV1qapz6PERs/)**

Both the custom HAT and the independent torso IMU have passed extended real-robot use, operate normally, and have no identified issues.

**Two connector versions are available: original EH2.5 and AMP2.0.** The AMP2.0 HAT uses HP1.25 speaker / microphone sockets and adds a green LED plus a 1kΩ resistor. [Both project versions](hardware/README.en.md) · [AMP2.0 guide and parts](hardware/AMP2.0-VERSION.en.md)

[IMU firmware download and flashing](hardware/IMU-FIRMWARE.en.md) · [HAT build timeline](hardware/HAT-TIMELINE.en.md) · [IMU build timeline](hardware/IMU-TIMELINE.en.md) · [Hardware projects and notes](hardware/README.en.md) · [🔧 PCB shopping list (HAT / IMU)](hardware/README.en.md#shopping-list)

## ❤️ Sharing the project and crediting its creators

This is a **personal learning and development project** based on [Pollen Robotics' official Microduck](https://github.com/pollen-robotics/microduck) `0.15.1`, rather than an official release. **Except for explicitly identified upstream and third-party code, models, and assets, the additional firmware adaptations, consoles, tools, documentation, and the author's trained results were developed by this project's author, with AI-assisted programming.**

**Original work that the author owns and can license is provided for personal learning, research, and noncommercial use only. Obtain the author's written permission before commercial use**, including commercial products, paid services, or distribution with robots sold commercially. Upstream Apache-2.0 software, third-party MIT components, official geometry, and other assets retain their own licenses; personal terms do not override third-party rights.

Full scope: [Component licenses](microduck-hd1910/LICENSE) · [Personal noncommercial terms](microduck-hd1910/LICENSES/Personal-NonCommercial.txt) · [Third-party credits](microduck-hd1910/docs/THIRD-PARTY.en.md)

This project grew from one board, one duck, and many debugging sessions. I am an individual maker, with AI helping on parts of the code. I hope these files help you get your own duck moving sooner. Stars ⭐, discussion, and feedback are welcome.

<table align="center">
  <tr>
    <td align="center" valign="top" width="50%">
      <b>❤️ Support the author</b><br><br>
      <img width="180" alt="QR code to support the author" src="https://github.com/user-attachments/assets/49054608-65ba-41d6-b3f1-a97941976c4b" />
    </td>
    <td align="center" valign="top" width="50%">
      <b>🛒 Buy a complete robot</b><br><br>
      <a href="docs/assets/purchase-wechat-qr.jpg"><img width="220" alt="WeChat contact QR code for complete robot purchases" src="docs/assets/purchase-wechat-qr.jpg" /></a><br>
      <sub>Scan in WeChat to ask about purchasing a complete robot.<br>Click the QR code for the original image.</sub>
    </td>
  </tr>
</table>

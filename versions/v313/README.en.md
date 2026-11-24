[简体中文](README.md) | **English**

# R3 system image and Console Studio V313

[R3 image (.img.xz)](https://github.com/kissqy/Microduck-kissqy/releases/download/console-studio-v313/microduck-kissqy-zero3w-R3.img.xz) · [Baidu Netdisk](https://pan.baidu.com/s/1mGu_SiBGiYlzmvqPsVpfxw?pwd=km52) (code `km52`) · [V313 console (.zip)](https://github.com/kissqy/Microduck-kissqy/releases/download/console-studio-v313/Microduck-Console-Studio-V313.zip) · [Release notes](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v313)

## New installation

Use Armbian Imager to write the compressed R3 image to the target TF card. Flashing overwrites the card. Check the target, complete write verification, then boot the ZERO. All three freshly flashed TF cards booted and opened the setup hotspot on first power-on.

At boot, R10 tries saved Wi-Fi first. If no saved network connects, join `Microduck-kissqy` (password `12345678`) and open `http://10.42.0.1:8088`. A later disconnection does not start the hotspot automatically.

## Desktop console and firmware

Extract the whole V313 ZIP. Run `start.cmd` on Windows or `bash start.command` on macOS/Linux, then connect to your ZERO by its IP.

On an existing R2 card, connect with V313 and open **系统维护 (System Maintenance)**. If the robot runs `control.102` or `control.126`, select the bundled V313 / `control.127` firmware and click **升级所选固件 (Upgrade selected firmware)**. A robot already on `control.127` is ready to use. Flashing the R3 image is required to adopt the R3 disk layout.

V167 users can follow the documented upgrade to control.102 first. [V167 → V260](../v260/README.md)

## Source and features

The V313 runtime ZIP includes the console Python and frontend source, the 11 ONNX models and the bundled native source archive `source/Microduck-Native-Build-Source-V313.tar.gz`. [Four workspaces, HAT numbering and per-device timing](https://kissqy.github.io/Microduck-kissqy/console-v313/en.html)

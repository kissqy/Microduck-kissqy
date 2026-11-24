[简体中文](START-HERE.txt) | **English**

# Current public Microduck release

**R3 system image · Console Studio V313 · robot firmware `control.127`**

[R3 image (.img.xz)](https://github.com/kissqy/Microduck-kissqy/releases/download/console-studio-v313/microduck-kissqy-zero3w-R3.img.xz) · [V313 console (.zip)](https://github.com/kissqy/Microduck-kissqy/releases/download/console-studio-v313/Microduck-Console-Studio-V313.zip) · [Release notes](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v313)

On an existing R2 card, connect with V313 and open **系统维护 (System Maintenance)**. If the robot runs `control.102` or `control.126`, select the bundled V313 / `control.127` firmware and click **升级所选固件 (Upgrade selected firmware)**. A robot already on `control.127` is ready to use.

On boot, the system tries saved Wi-Fi first and opens a setup hotspot if it cannot connect. Join `Microduck-kissqy` (password `12345678`) and visit `http://10.42.0.1:8088` if the page does not open automatically. A disconnection during normal operation does not automatically start the hotspot; it can be enabled manually from the console.

Extract the complete V313 console. Run `start.cmd` on Windows or `bash start.command` on macOS/Linux. Before first movement, verify this robot's calibration and follow **HOME → hold → walk**.

## Versions

- [R3 / V313 · current](versions/v313/README.en.md)
- [V302 · archive](versions/v302/README.en.md)
- [R2 / V260 · archive](versions/v260/README.md)

## Historical releases

- [R1 image](https://github.com/kissqy/Microduck-kissqy/releases/tag/public-image-r1): control.40 and first-boot Wi-Fi R5.
- [Robot Console V167](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/versions/v167/release-assets/Microduck-Console-R17-V167.zip): matching control.43 firmware.
- V167 / control.43 source is grouped in `versions/v167/microduck-hd1910/firmware/`; its console is in `console/`.
- Training Studio source remains in `microduck-hd1910/training-console/`.

V167 and V260 occupy separate directories under `versions/` and do not trigger automatic upgrades. The original root `microduck-hd1910/` source path remains available. The root `release-assets/` directory has moved to `versions/v167/release-assets/`; use the updated download links. See [Known-Good and validation scope](microduck-hd1910/docs/BASELINE.en.md). All three freshly flashed TF cards booted and opened the setup hotspot on first power-on. See `microduck-hd1910/LICENSE` for component licensing; third-party content retains its original terms.

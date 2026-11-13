[简体中文](START-HERE.txt) | **English**

# Current public Microduck release

Updated November 13, 2026. Project: <https://github.com/kissqy/Microduck-kissqy>.

- Default setup: **System Image R2 + Microduck Console Studio V260 (R17)**.
- Robot firmware: official Microduck 0.15.1 / control.102.
- First-boot Wi-Fi: R10; runtime models: 11 ONNX.
- Optional independent Training Studio: R1.5.27.

[Download R2 image](https://github.com/kissqy/Microduck-kissqy/releases/download/console-studio-v260/microduck-kissqy-zero3w-R2.img.xz) · [V260 release downloads](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v260) · [Console, firmware and source-package guide](https://github.com/kissqy/Microduck-kissqy/blob/main/versions/v260/README.md) · [Independent V260 source](https://github.com/kissqy/Microduck-kissqy/tree/main/versions/v260)

On boot, the system tries saved Wi-Fi first and opens a setup hotspot if it cannot connect. Join `Microduck-kissqy` (password `12345678`) and visit `http://10.42.0.1:8088` if the page does not open automatically. A disconnection during normal operation does not automatically start the hotspot; it can be enabled manually from the console.

Extract the complete V260 console. Run `start.cmd` on Windows or `bash start.command` on macOS/Linux. Before first movement, verify this robot's calibration and follow **HOME → hold → walk**.

## Version directories on main

- [V260 · current release](versions/v260/): console, firmware source and runtime downloads.
- [V167 · historical release](versions/v167/README.en.md): preserved source layout and original packages.

No branch switching is needed. Training Studio R1.5.27 remains an independent tool.

## Historical releases

- [R1 image](https://github.com/kissqy/Microduck-kissqy/releases/tag/public-image-r1): control.40 and first-boot Wi-Fi R5.
- [Robot Console V167](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/release-assets/Microduck-Console-R17-V167.zip): matching control.43 firmware.
- V167 / control.43 source is grouped in `versions/v167/microduck-hd1910/firmware/`; its console is in `console/`.
- Training Studio source remains in `microduck-hd1910/training-console/`.

V167 and V260 occupy separate directories under `versions/` and do not trigger automatic upgrades. Original root `microduck-hd1910/` and `release-assets/` paths remain compatible with historical links. See [Known-Good and validation scope](microduck-hd1910/docs/BASELINE.en.md); this publication does not add real-robot acceptance results. See `microduck-hd1910/LICENSE` for component licensing; third-party content retains its original terms.

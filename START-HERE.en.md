[简体中文](START-HERE.txt) | **English** | [Русский](START-HERE.ru.md)

# Current public Microduck release

Project: <https://github.com/kissqy/Microduck-kissqy>

The homepage provides the system image, two console ZIPs, and source entry points.

- Robot Console: R17 V167 (1.0.167)
- Robot firmware: official 0.15.1 / control.43 / API40
- Training Studio: R1.5.27
- System image: Public Image R1; first-boot Wi-Fi setup R5

Source locations:

- Firmware: `microduck-hd1910/firmware/`
- Robot Console: `microduck-hd1910/firmware/console/`
- Training Studio: `microduck-hd1910/training-console/`
- Runtime ZIPs: root `release-assets/`
- System image: `public-image-r1` Release

V167 is paired with control.43. Update: Fixed body jitter.

Before first movement, verify this robot's calibration and follow HOME → hold → walk. See `microduck-hd1910/LICENSE` for component licensing; third-party content retains its original terms.

Image R1 still includes control.40; install V167 bundled firmware to upgrade to control.43.

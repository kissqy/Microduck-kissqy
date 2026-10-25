[简体中文](BASELINE.md) | **English** | [Русский](BASELINE.ru.md)

# Release baseline and verification scope

Published version: **R17 V167 / control.43 + Training R1.5.27**, based on official **0.15.1**. See [PUBLICATION-MANIFEST.json](../PUBLICATION-MANIFEST.json) for identities and hashes.

**V167 update: Fixed body jitter.**

| Component | Version |
| --- | --- |
| Official firmware | daemon-v0.15.1, `1fa84386f07884e27866411bc1ba166977bced95` |
| HD1910 firmware | `1fa8438-feetech-ft6-control.43`, API40 |
| Robot Console | R17 V167, `1.0.167` |
| Training Studio | R1.5.27; 14 action classes and 35 recipes |
| Training engine | microduck_rl `8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec` |
| System image | Public Image R1, first-boot Wi-Fi R5; still includes control.40 |

## File locations

- `firmware/`: firmware source, installer scripts, models, tests and licenses.
- `firmware/console/`: V167 console source and bundled firmware payload.
- `training-console/`: unchanged R1.5.27 release content.
- `release-assets/`: complete V167 console and R1.5.27 training ZIPs.
- `release-assets/build-baselines/`: one V164 ZIP retained for reproducible packaging.
- System image: the existing `public-image-r1` Release; after flashing, install V167 bundled firmware to upgrade to control.43.

Source no longer embeds an old complete installer ZIP or a second binary copy of compiled programs, ONNX libraries and packaged models. `firmware/prepare-V167.py` verifies and restores required resources; Git ignores generated copies. See [the V167 build guide](../firmware/BUILDING-V167.en.md).

## Verification

The image was previously verified by reflashing, first Wi-Fi setup, SSH, robot communication and R17 recognition. The author reports the currently running robot build as `1fa8438-feetech-ft6-control.43`.

`firmware/verification/v167/` contains prior compilation records: 237 Rust tests, 18 Python tests and ten ARM64/QEMU model loads and first inferences. This cleanup checks delivered archives, source, resource restoration and checksums without rebuilding firmware or operating the robot.

## Known-Good and next task

Current release reference: **0.15.1 + R17 V167 / control.43 + Training R1.5.27**, with the reflash-verified **Public Image R1**. Action-specific acceptance remains governed by the corresponding real-robot records.

**Single next task: reproduce V167 installation and local calibration from the published downloads.** Validate one variable at a time.

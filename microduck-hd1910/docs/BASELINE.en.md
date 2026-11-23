[简体中文](BASELINE.md) | **English**

# Release baseline and verification scope

## Current console release · November 23, 2026

[Console Studio V302 Beta](../../versions/v302/README.en.md) is published. It only updates the desktop console and isolated maintenance modules, reusing unchanged **control.102, R2 / R10 and the existing 11 ONNX models** on official **Microduck 0.15.1**. Existing control.102 users do not upgrade native firmware or reflash the card.

Local maintenance, compatibility and UI regressions passed; physical acceptance remains pending. Existing Reference Duck Known-Good records are retained. **Next single task: verify V302 numbering, midpoint calibration and mode changes on Reference Duck / control.102, recording actual results and latency.**

The following V167 records are historical and do not describe the latest release.


Historical published version: **R17 V167 / control.43 + Training R1.5.27**, based on official **0.15.1**. See [PUBLICATION-MANIFEST.json](../PUBLICATION-MANIFEST.json) for identities and hashes.

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
- `versions/v167/release-assets/`: complete V167 console and R1.5.27 training ZIPs.
- `versions/v167/release-assets/build-baselines/`: one V164 ZIP retained for reproducible packaging.
- System image: the existing `public-image-r1` Release; after flashing, install V167 bundled firmware to upgrade to control.43.

Source no longer embeds an old complete installer ZIP or a second binary copy of compiled programs, ONNX libraries and packaged models. `firmware/prepare-V167.py` verifies and restores required resources; Git ignores generated copies. See [the V167 build guide](../firmware/BUILDING-V167.en.md).

## Verification

The image was previously verified by reflashing, first Wi-Fi setup, SSH, robot communication and R17 recognition. The author reports the currently running robot build as `1fa8438-feetech-ft6-control.43`.

`firmware/verification/v167/` contains prior compilation records: 237 Rust tests, 18 Python tests and ten ARM64/QEMU model loads and first inferences. This cleanup checks delivered archives, source, resource restoration and checksums without rebuilding firmware or operating the robot.

## Known-Good and next task

Current release reference: **0.15.1 + R17 V167 / control.43 + Training R1.5.27**, with the reflash-verified **Public Image R1**. Action-specific acceptance remains governed by the corresponding real-robot records.

November 12: source cleanup revision 1 removed obsolete tools and an unlinked module, with duplicate model metadata restored by checksum. Resource restoration, 198 selected Python checks and console startup passed. No Rust/ARM64 rebuild or hardware acceptance was performed, and no new runtime Known-Good was established. See the [source cleanup audit (中文)](SOURCE-CLEANUP-20261112.md).

**Historical next task: validate Rust and ARM64 builds of the cleaned source in the existing Linux/WSL environment.** Validate one variable at a time.

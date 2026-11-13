# Microduck R17 V163 / control.40

This is the R17 adaptation of Microduck for a Radxa Zero robot with HD1910 servos and its IMU. The current console version is `1.0.163`, the firmware build is `1fa8438-feetech-ft6-control.40`, and the system version is `0.15.1`.

The physical gamepad uses the native padd → robotd path for walking and roller policies. The firmware includes swizzle, crouch, spin and stand-up ONNX models, with IMU heading feedback for roller steering. The current installation calibration, console credentials and GitHub entrances are included in the package.

## Current documentation

| Task | Reference |
| --- | --- |
| Install and operate the robot | [Console guide, Chinese](console/README.zh-CN.md) |
| Inspect models, calibration and services | [Firmware guide, Chinese](packaging/README.zh-CN.md) |
| Build the ARM64 programs and package | [V163 build guide, Chinese](V163-构建说明.md) |
| Read the R17 overview | [R17 README, Chinese](README-R17.zh-CN.md) |
| Understand daemon mechanisms | [Documentation index](docs/README.md) |

robotd and padd have been compiled for AArch64. The selected control, protocol, gamepad and roller test scope has 235 passes; all four roller models load with the ARM64 program under QEMU. Physical L3 requests a stand-up test only in roller mode, with motion already enabled and fresh IMU feedback confirming a fall. Each press requests one five-second test window through the existing skill API; Start cancels it. The export itself declares no duration; five seconds is the manual test setting. Each active roller model applies its own contract coefficients. Zero hardware motion is not yet verified. See the build guide and `verification/v163/` for the exact scope and complete diagnostic results.

## Source and licenses

R17 source: [kissqy/Microduck-kissqy](https://github.com/kissqy/Microduck-kissqy). Upstream: [pollen-robotics/microduck](https://github.com/pollen-robotics/microduck). Policy training: [microduck_rl](https://github.com/pollen-robotics/microduck_rl).

Third-party software and model licenses remain in their respective LICENSE and notice files. Use [CONTRIBUTING.md](CONTRIBUTING.md) for workspace conventions; the V163 build guide owns this package's target, toolchain and verification scope.

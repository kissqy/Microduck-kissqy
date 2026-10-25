[简体中文](README.zh-CN.md) | **English** | [Русский](README.ru.md)

# Microduck R17 V167 / control.43 bundled firmware

Build `1fa8438-feetech-ft6-control.43` pairs with console `1.0.164` and official system `0.15.1`. robotd and padd are ARM64 programs compiled for this build; robotctl, mediad, input bridge, and installation use the paired package configuration.

Install via **系统维护 → 随包固件** (System Maintenance → Bundled Firmware). Complete four-step service startup, switch to movement mode, perform HOME, and enable the policy before motion. See the [console user guide](../console/USER-GUIDE.en.md) for buttons.

## Models

| Mode / action | Model file or ID | Execution settings |
| --- | --- | --- |
| Roller swizzle | `roller/swizzle/policy.onnx` | Base scale 1.0; head / leg targets pass through |
| Roller crouch | `roller/crouch/policy.onnx` | Base scale 0.8; head 0.5, legs 0.7; 5-second period |
| Roller spin | `roller/spin/policy.onnx` | Base scale 1.0; passthrough; 4-second period |
| Roller recovery | `roller/standup/policy.onnx` | Actual checkpoint 11000; scale 1.0; passthrough; conditional physical L3 5-second manual test |
| Joint Walk / hold / recovery | `1cbf8730eadd75a5704332c9f3c10f60` | Base scale 1.0; head low-pass 0.5, legs 0.7 |
| Sit / stand | `1c94934c6421ec72ed48079cea749668` | Base scale 1.0; sit / stand execution path |
| Ground pick | `b14e3a8b56ddbb8d2d831e727774a168` | Base scale 1.0; target passthrough |
| Forward roll | `59e15d7b04d0c40e9b11b8a70bdecae6` | Base scale 1.0; passthrough |
| Left-foot kick | `ee0376c927044cdece056ba1d3e6eac7` | Base scale 1.0; single 0.5-second action; passthrough |
| Right-foot kick | `67ad09d82f4865d222a7ae06f250cf9f` | Base scale 1.0; passthrough |

The four roller models, `manifest.json`, and `deployment-contract.json` install in `/opt/robot/feetech-ft5-r5/roller/`. Roller mode drives with swizzle; A selects crouch or spin, defaulting to crouch on entry. Walking supplies six configurations, with LB for left-foot kick. The separate Stand slot is empty; physical L3 offers conditional roller recovery testing.

## Calibration and servo parameters

Bundled calibration comes from the confirmed `duck-10e4` assembly, with provenance in `robot-calibration-source.json`. All 15 directions are −1; ID 30 zero 2526, ID 31 zero 2228, ID 33 zero 1599; IMU calibration is included.

Installation prefers valid local calibration and saved parameters. Restoration uses the bundled assembly configuration when needed. Runtime calibration is `/etc/robot/feetech-ft5/hd1910-calibration.toml`; service config is `robotd.toml` in the same directory.

Servo P follows the contract, currently P=5. Writing and torque-release restoration affect only one byte at address 50. This path does not explicitly write addresses 48/51; it restores the P saved before torque enablement. The control loop is 50 Hz.

## Services

robotd uses native IPC to control the robot; padd accepts the physical gamepad. Startup, connection, and model loading do not automatically request movement. Commissioning collects feedback; movement mode loads policies. After switching models, enable the policy from HOME.

mediad wakes capture on demand and sleeps when the last consumer exits. System configuration disables automatic update and golden-recovery paths that could overwrite this firmware package.

## Integrity and verification

`BUILD.json` identifies the actual build; `ELF-CHECK.json` records native programs; `install-files.json` and `SHA256SUMS` define bundled files / hashes. Installation checks uploaded byte counts, SHA256, and AArch 64 ELF identity.

The current targeted scope passed 235 Rust tests, loading and first inference for six regular / four roller ARM64/QEMU models, product import, and individual file checks. Full logs are supplied with source. Physical ZERO roller movement was not yet validated in this build record.

Each roller model's original contract supplies coefficients applied to its active network. Recovery's original slot and `required_skill_settings` are empty and declare `manual_skill` with zero commands. The package uses the existing skill path for a physical L3 5-second test; padd checks roller mode, running state, and fresh IMU fall classification. No automatic recovery slot is added. Five seconds is local test configuration; original contracts and weights are preserved. The training archive says 10000, but the actual manifest checkpoint is 11000 and is authoritative.

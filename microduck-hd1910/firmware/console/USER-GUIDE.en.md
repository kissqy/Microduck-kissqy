[简体中文](README.zh-CN.md) | **English** | [Русский](USER-GUIDE.ru.md)

# Microduck R17 V167 / control.43 user guide

The console is `1.0.167`, bundled firmware is `1fa8438-feetech-ft6-control.43`, and the paired official system is `0.15.1`. The physical gamepad uses the native padd → robotd path for walking and roller models. Four roller ONNX models install with the firmware.

Project: [Microduck-kissqy](https://github.com/kissqy/Microduck-kissqy). Links appear at the top of the page and in the Windows launch window.

## Startup and installation

1. Fully extract `Microduck-Console-R17-V167.zip`. On Windows run `start.cmd`; on macOS run `start.command`; on Linux use `python3 console.py --dashboard --feetech --open`.
2. Connect to ZERO over SSH in the page and verify console `1.0.167` and actual robot firmware `control.43`. If ZERO already has control.43, replace only the computer-side console folder. For first installation use **系统维护 → 随包固件** (System Maintenance → Bundled Firmware).
3. Wait for all robotd startup steps 1/4–4/4, then check live feedback and gamepad connection. Connection alone does not trigger movement.
4. If the service shows `commissioning`, click **切到运动模式** (Switch to Movement Mode) and wait for four-step startup. Commissioning does not load movement policies.

## Physical gamepad roller controls

Fit the rollers first, release the sticks, and support the robot. The first Start press performs HOME. After HOME completes, hold ↑ for 3 seconds to enter roller mode. Wait for model switching, then press Start to enable the policy and use the sticks or A.

| Input | Behavior |
| --- | --- |
| Hold ↑ for 3 seconds | Switch walking / roller modes; entering roller mode makes A default to crouch. |
| Hold ← for 2 seconds | In roller mode, switch A between crouch and spin; requires stationary HOME with no active action. |
| A | Run the selected roller action; in walking mode, pick up from the ground. |
| Left stick forward / back | Symmetric swizzling; roller mode does not use lateral translation. |
| Right stick left / right | Adjust target heading; robotd uses current IMU heading to compute the model's heading error. |
| Start | First press: HOME. Later presses toggle policy enablement; disabling returns to HOME. |

To change A's action, release the sticks and wait for the active action to end. Press Start to disable the policy and wait for HOME, then hold ← for 2 seconds. After switching, press Start to enable the policy and A to act. If a request is refused, inspect the log, correct the condition, and retry.

Hold for the full duration. Each hold sends one switch request; release before switching again. Roller modes and actions use the physical gamepad; there is no dedicated web roller-mode button. Page input disables automatically when a physical gamepad connects.

## Model display and execution parameters

The left column below the gamepad shows models and advanced parameters; the right column explains buttons in Chinese. Model states come from the same configuration read. The recovery model shows the physical L3 test entry and its conditions; web L3 only displays guidance and sends no input.

The four roller cards are “滑轮对称滑 / Swizzle,” “滑轮蹲下 / Crouch,” “滑轮原地转 / Spin,” and “滑轮倒地起身 / Stand up.” Training iterations and installation status appear below the titles.

| Roller model | Base scale | Head filter | Leg filter | Current entry |
| --- | --- | --- | --- | --- |
| Swizzle | 1.0 | 1.0 | 1.0 | Roller sticks |
| Crouch | 0.8 | 0.5 | 0.7 | Roller A; 5-second period, end phase 0.7 |
| Spin | 1.0 | 1.0 | 1.0 | Roller A; 4-second period, end phase 0.7 |
| Stand up | 1.0 | 1.0 | 1.0 | Physical L3: roller mode, policy enabled, IMU confirms a fall; 5-second manual test |

When loading a model, robotd reads the original contract's `required_policy_settings` and applies scale and filtering for the current network. When an action ends, the swizzle model's own parameters return. Crouch deployment filtering and the historical training without EMA are recorded separately; training contracts and weights are not rewritten. Voltage compensation and gains continue using existing configuration.

The recovery package's actual checkpoint is 11000; 10000 in its filename is not model metadata. The original contract declares `manual_skill` with zero commands, without a Stand slot or duration. Existing `[[policy.skill]]` configuration provides a 5-second manual test window; this is a test setting, not a training-contract parameter. Physical L3 (left-stick press) reads actual mode and fresh IMU before execution. It accepts only roller mode with policy enabled, completed HOME, no other action, and an IMU-confirmed fall. Upright, walking, HOME, torque-released, and stale-IMU states are refused and logged. Each press requests once; holding or gamepad reconnection does not repeat it. Start cancels. At the end, control returns to swizzle. LB remains left-foot kick; web L3 is informational only.

## Other buttons

| Button | Default action |
| --- | --- |
| X | Forward roll |
| RB | Right-foot kick |
| LB | Left-foot kick, one 0.5-second action |
| D-pad down | Toggle sit / stand |
| Y / B | Head / body pose mode |
| RT / LT | Beak and sound controls |
| Short Select press, then release | Release torque |
| Hold Select for 2 seconds | Sit down, release torque, shut down |

There is no separate LB recovery test currently. The joint Walk model handles holding and recovery during walking. Valid saved custom button mappings continue using local configuration.

## Calibration and settings

Installation preserves valid calibration and saved parameters already on ZERO. When restoring bundled assembly calibration, the package uses user-confirmed settings: all 15 joint directions −1; neck ID 30 zero 2526, ID 31 zero 2228, head ID 33 zero 1599; bundled IMU calibration is also restored.

These settings came from the user's `duck-10e4` assembly. On a fresh ZERO without valid local calibration, “恢复装配标定” (Restore Assembly Calibration) in installation logs means using those bundled values. Check calibration against actual assembly when changing robots.

The live feedback direction column reads saved local calibration; missing data shows “—”. Advanced parameters retain action scaling. Contracts provide servo P; other parameters follow valid local settings and the current contract.

## Camera and connection

mediad remains resident and wakes video on demand. Clicking camera Connect starts acquisition; it sleeps after the last video consumer exits. Multiple pages can share it. System boot or opening the page alone does not keep capture running.

An initial connection shows a waiting state until full feedback arrives. Actual SSH, service, or startup errors are explained in the log. **导出启动诊断** (Export Startup Diagnostics) saves read-only diagnostics. For gamepad connection repair, follow page instructions for A+HOME mode and pairing.

## Exit

Closing a browser tab can leave the console script running. Before replacing or deleting the extracted folder, press Ctrl+C in its terminal and wait for exit. On Windows, addresses and DPAPI-protected passwords are stored in AppData; SSH uses the console's shared credential flow.

## Validation scope

robotd and padd have actual ARM64 builds. The current control core, IPC, padd, and roller scope passed 235 tests. The new ARM64 robotd loaded and ran first inference for six regular and four roller ONNX models in QEMU. Package manifest / hash checks and console firmware import checks passed.

Real ZERO roller movement was not validated in this build environment. Results cover the listed scope rather than the entire workspace. Original build and test records remain in `verification/v163/`.

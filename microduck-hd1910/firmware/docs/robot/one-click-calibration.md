# One-click CAL calibration

The R17 console can write the current physical pose of all 15 HD1910 servos as
`2048` and update the saved TOML in one job. It is the bulk form of **Save current
joint**, not a substitute for setting limits or assembling the robot.

## What the job does

1. Checks that all 15 servos are live and calibrated, robotd is in
   `commissioning` / `ready` / torque off, feedback is fresh, and no motion or
   power job is pending.
2. Records the pre-calibration `position_raw`, `zero_raw`, and angle for the
   page's before/after table.
3. Backs up the live calibration TOML (`hd1910-calibration.toml.bak-cal-all-*`).
4. For every servo, in order: unlock EEPROM (`55 = 0`), send CAL (`0x0B`),
   lock EEPROM (`55 = 1`), then read register `56` and require `2048`.
5. Writes `zero_raw = 2048` for every joint in the TOML, preserving direction
   and limits, and verifies all 15 joints again.

The whole sequence runs inside robotd. The console only sends
`robot.busCommand {"action":"calibrate-all"}` and reads
`robot.busStatus.calibration_all` for progress; it does not open the serial port
and does not stop or restart robotd.

## Requirements

- robotd `1fa8438-feetech-ft6-control.44` or newer. The capability is advertised
  as `calibrate_all: true` in `robot.busStatus`; older firmware gets a clear
  rejection instead of a partial calibration.
- The robot is supported, in commissioning mode, and torque is off.
- The robot is physically at **zero pose**: 14 movable joints at 0°, mouth
  closed/neutral. This is not the HOME pose, whose neck, head, and ankles have
  non-zero angles.

## Why it is not fully automatic

- CAL writes the servo EEPROM. Restoring the TOML backup does **not** undo CAL;
  to undo it, put the robot back at the desired zero and calibrate again.
- `capture` keeps writing `motion_enabled = false`. The success panel offers
  **Switch to motion mode**; it runs `calibration-config.py enable`, restarts
  robotd, and the robot may stand up, so only press it with the robot supported.
- While the job runs, the console rejects relax, reboot, and shutdown. The
  torque is already off, so there is no motion to emergency-stop; interrupting
  CAL would leave EEPROM and TOML inconsistent.

## Protocol

```text
robot.busCommand  {"action":"calibrate-all"}
robot.busStatus   {"calibrate_all":true, "calibration_all":{
                    "status":"running", "total":15, "done_ids":[...],
                    "current_id":20, "stage":"calibrate"}}
```

On success the command returns `completed_ids`, `positions`, `backup`, and the
updated `calibration` object. The implementation is in
[`feetech_commissioning.rs`](../../robotd/src/feetech_commissioning.rs); the
console orchestration is in
[`service_control.py`](../../console/service_control.py).

## Tests

```bash
cargo test -p duck-control cal_packet
cargo test -p robotd --bin robotd feetech_commissioning::tests

cd console
python3.13 -m unittest verification.test_calibrate_all -v
node verification/test_cal_all_ui.mjs
```

These are hermetic: no robot, serial port, SSH, or systemd. Hardware validation
for `.44` wrote all 15 servos to `position_raw = 2048` and `zero_raw = 2048`
without restarting robotd.

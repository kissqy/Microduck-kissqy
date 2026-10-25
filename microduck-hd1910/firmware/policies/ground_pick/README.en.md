[简体中文](使用说明.md) | **English** | [Русский](README.ru.md)

# HD1910 self-trained model · Target firmware 0.15.1

Official model slot: `ground_pick`.

- Original training task: `Mjlab-GroundPick-Flat-Backlash-MicroDuck`; official training commit: `8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec`.
- Evaluation / export task: `Mjlab-GroundPick-Flat-Backlash-MicroDuck`; export source: `8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec` . Original training friction: `official` (fixed=fixed friction; official=official randomization).
- Model: `policy.onnx`; `checkpoint.pt` is for resumed training and cannot be given directly to robotd for inference.
- `manifest.json` uses official schema 2. This ZIP is a training archive, not a firmware update package.
- `deployment-profile.toml` is an official `[policy]` fragment. Merge it into the existing runtime configuration; do not replace the complete file.
- Training used no additional head / leg EMA; head / neck and legs use passthrough 1.0. BAM servo dynamics remain in the training model. Filtering applies to joint targets after Home + action scale × raw output, without reducing the final angle. This filter is not embedded in the ONNX graph.
- Bundled `manifest.json` records parameters but does not guarantee automatic runtime loading. Apply the action scale and head / leg filtering from `deployment-profile.toml` during deployment.
- Voltage compensation, gains, and gain multipliers are not configuration fields of this training action. Export does not force them on / off or to 1; they retain existing runtime configuration. A disabled setting is not enabled by this fragment. BAM supply randomization and load-related voltage drop are preserved in the training snapshot and do not establish training of runtime voltage action compensation.
- `training-config.json` stores configuration provenance `training_run_readback`, environment, rewards, curricula, expert BC, BAM, mass, backlash, and more. Original training-start readback takes priority. Missing historical records are explicitly labeled as reconstruction from saved recipes, not fabricated original readback.
- Observation normalization: `embedded_in_onnx_once`; when enabled, the official exporter embeds it in ONNX. Do not normalize again at runtime.
- Use the HD1910/IMU adaptation driver and calibration for the current physical assembly. Bundled calibration is provenance only and does not overwrite physical joint zeros.
- Backlash simulation: `{"enabled": true, "joint_count": 14, "ranges_rad": {"passive_left_hip_yaw_backlash": [-0.017453292519943295, 0.017453292519943295], "passive_left_hip_roll_backlash": [-0.017453292519943295, 0.017453292519943295], "passive_left_hip_pitch_backlash": [-0.017453292519943295, 0.017453292519943295], "passive_left_knee_backlash": [-0.017453292519943295, 0.017453292519943295], "passive_left_ankle_backlash": [-0.017453292519943295, 0.017453292519943295], "passive_neck_pitch_backlash": [-0.017453292519943295, 0.017453292519943295], "passive_head_pitch_backlash": [-0.017453292519943295, 0.017453292519943295], "passive_head_yaw_backlash": [-0.017453292519943295, 0.017453292519943295], "passive_head_roll_backlash": [-0.017453292519943295, 0.017453292519943295], "passive_right_hip_yaw_backlash": [-0.017453292519943295, 0.017453292519943295], "passive_right_hip_roll_backlash": [-0.017453292519943295, 0.017453292519943295], "passive_right_hip_pitch_backlash": [-0.017453292519943295, 0.017453292519943295], "passive_right_knee_backlash": [-0.017453292519943295, 0.017453292519943295], "passive_right_ankle_backlash": [-0.017453292519943295, 0.017453292519943295]}, "encoder_position": "motor + passive backlash", "motor_velocity": "motor-side for friction and back-EMF", "policy_joint_velocity": "motor + passive backlash"}`. Passive backlash joints are not exported as ONNX actions; the robot uses actual encoder feedback.
- Walking teachers and joint models both use the walk slot; only the joint model includes the corresponding fall-recovery training. A recovery teacher is not a separate stationary-hold policy.
- Picking uses phase commands; sit / stand uses a pose flag. Forward rolls and left / right kicks use the official one-shot action window. Simulation episode length is not the firmware trigger window.
- This package passed model-format and finite-output checks; it does not establish physical gait acceptance on your robot.

See `deployment-contract.json`, `training-config.json`, and `upstream-params/` for action / observation order, actual Home, BAM parameters, and training snapshots.

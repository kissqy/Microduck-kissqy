[简体中文](使用说明.md) | **English** | [Русский](README.ru.md)

# HD1910 self-trained model · Target firmware 0.15.1

Native runtime model slot: `kick_right`; this historical R148 note does not grant import support.

- Native interface checked: `0.15.1` / `1fa84386f07884e27866411bc1ba166977bced95`; route `skill`; support scope `route_available`.
- The historical R148 task allowlist does not accept this task; a training export does not imply one-click robot import. These are self-trained weights, not an officially validated released model. Robot configuration is not written automatically.


- Original training task: `Mjlab-BallKick-Flat-MicroDuck`; official training commit: `8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec`.
- Evaluation / export task: `Mjlab-BallKick-Flat-MicroDuck`; export source: `8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec` . Original training friction: `official` (fixed=fixed friction; official=official randomization).
- Model: `policy.onnx`; `checkpoint.pt` is for resumed training and cannot be given directly to robotd for inference.
- `manifest.json` uses official schema 2. This ZIP is a training archive, not a firmware update package.
- `deployment-profile.toml` is an official `[policy]` / `[[policy.skill]]` fragment. Merge it into existing configuration rather than replacing the complete file. Preserve configured skill paths and gain multipliers when binding this model.
- Training used no additional head / leg EMA; head / neck and legs use passthrough 1.0. BAM servo dynamics remain in the training model. Filtering applies to joint targets after Home + action scale × raw output, without reducing the final angle. This filter is not embedded in the ONNX graph.
- Bundled `manifest.json` records parameters but does not guarantee automatic runtime loading. Apply the action scale and head / leg filtering from `deployment-profile.toml` during deployment.
- Voltage compensation, gains, and gain multipliers are not configuration fields of this training action. Export does not force them on / off or to 1; they retain existing runtime configuration. A disabled setting is not enabled by this fragment. BAM supply randomization and load-related voltage drop are preserved in the training snapshot and do not establish training of runtime voltage action compensation.
- `training-config.json` stores configuration provenance `training_run_readback`, environment, rewards, curricula, expert BC, BAM, mass, backlash, and more. Original training-start readback takes priority. Missing historical records are explicitly labeled as reconstruction from saved recipes, not fabricated original readback.
- Observation normalization: `embedded_in_onnx_once`; when enabled, the official exporter embeds it in ONNX. Do not normalize again at runtime.
- Use the HD1910/IMU adaptation driver and calibration for the current physical assembly. Bundled calibration is provenance only and does not overwrite physical joint zeros.
- Backlash simulation: `{"enabled": false, "joint_count": 0, "ranges_rad": {}, "encoder_position": "motor", "motor_velocity": "motor-side for friction and back-EMF", "policy_joint_velocity": "motor"}`. Passive backlash joints are not exported as ONNX actions; the robot uses actual encoder feedback.
- Walking teachers and joint models both use the walk slot; only the joint model includes the corresponding fall-recovery training. A recovery teacher is not a separate stationary-hold policy.
- Picking, roller crouch, and spin use phase commands with the period from the original training snapshot and end phase 0.7. Sit / stand uses a pose flag. Forward rolls and left / right kicks use the official one-shot window. Simulation episode length is not the firmware trigger window.
- Left-foot kick uses a separately trained left-foot task model. A filename containing left does not make the runtime mirror a right-foot model.
- This package passed model-format and finite-output checks; it does not establish physical gait acceptance on your robot.

See `deployment-contract.json`, `training-config.json`, and `upstream-params/` for action / observation order, actual Home, BAM parameters, and training snapshots.

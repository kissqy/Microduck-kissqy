# HD1910 自训模型 · 目标固件 0.15.1

这是倒地起身老师，供联合训练和仿真评估；不要自动作为 stand 槽的零速度保持模型。

- 训练来源任务：`Mjlab-StandUp-Rough-Backlash-MicroDuck`；官方训练提交：`8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec`。
- 本次评估/导出任务：`Mjlab-StandUp-Rough-Backlash-MicroDuck`；导出源码：`8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec`。原训练摩擦：`official`（fixed=固定摩擦；official=官方随机化）。
- 模型：`policy.onnx`；`checkpoint.pt` 用于续训，不能直接交给 robotd 推理。
- `manifest.json` 使用官方 schema 2；本 ZIP 是训练归档，不能当作固件升级包。
- `deployment-profile.toml` 是官方 `[policy]` 配置片段。由运行端合并到已有配置，不能覆盖整份配置文件。
- 训练未加额外头腿EMA；头颈/腿部直通 1.0。 模型内部仍包含 BAM 舵机动态。滤波作用于 Home＋动作系数×原始输出之后的关节目标，不缩小最终角度；ONNX图不内嵌此滤波。
- 包内 `manifest.json` 仅记录参数，不能保证现有固件自动读取；部署时必须落实 `deployment-profile.toml` 中的动作系数和头腿滤波。
- 电压补偿、增益及增益倍率不是本次训练动作项的配置字段，导出不强制开启、关闭或改成1。它们沿用运行端已有配置；如原配置已经是关闭，本片段不会自动改为开启。BAM供电随机化和负载掉压原样记录在训练快照，不能当作已训练运行端电压动作补偿。
- `training-config.json` 保存配置来源 `training_run_readback`、环境、奖励、课程、专家BC、BAM、质量和齿隙等。优先使用原训练启动读回；历史记录缺失时明确标为按保存配方重建，不伪造原训练读回。
- 观测归一化状态：`embedded_in_onnx_once`；启用时由官方导出器封装在ONNX内，运行端不要重复归一化。
- 必须使用 HD1910/IMU 适配驱动和当前机械装配的标定。包内标定只作来源记录，不覆盖实机零点。
- 齿隙仿真：`{"enabled": true, "joint_count": 14, "ranges_rad": {"passive_left_hip_yaw_backlash": [-0.017453292519943295, 0.017453292519943295], "passive_left_hip_roll_backlash": [-0.017453292519943295, 0.017453292519943295], "passive_left_hip_pitch_backlash": [-0.017453292519943295, 0.017453292519943295], "passive_left_knee_backlash": [-0.017453292519943295, 0.017453292519943295], "passive_left_ankle_backlash": [-0.017453292519943295, 0.017453292519943295], "passive_neck_pitch_backlash": [-0.017453292519943295, 0.017453292519943295], "passive_head_pitch_backlash": [-0.017453292519943295, 0.017453292519943295], "passive_head_yaw_backlash": [-0.017453292519943295, 0.017453292519943295], "passive_head_roll_backlash": [-0.017453292519943295, 0.017453292519943295], "passive_right_hip_yaw_backlash": [-0.017453292519943295, 0.017453292519943295], "passive_right_hip_roll_backlash": [-0.017453292519943295, 0.017453292519943295], "passive_right_hip_pitch_backlash": [-0.017453292519943295, 0.017453292519943295], "passive_right_knee_backlash": [-0.017453292519943295, 0.017453292519943295], "passive_right_ankle_backlash": [-0.017453292519943295, 0.017453292519943295]}, "encoder_position": "motor + passive backlash", "motor_velocity": "motor-side for friction and back-EMF", "policy_joint_velocity": "motor + passive backlash"}`。被动齿隙关节不作为ONNX动作导出，实机使用真实编码器反馈。
- 行走老师与联合模型都放 walk 槽；只有联合模型包含相应的倒地恢复训练。起身老师不是另一套“原地保持”策略。
- 捡取使用相位指令，坐站使用姿态标志；前滚翻和左右脚踢球使用官方一次动作窗口。仿真回合长度不等于固件触发窗口。
- 本包通过模型格式和有限输出检查，不代表已经通过你的机器人实机步态验证。

动作、观测顺序、实际 Home、BAM 参数及训练快照见 `deployment-contract.json`、`training-config.json` 和 `upstream-params/`。

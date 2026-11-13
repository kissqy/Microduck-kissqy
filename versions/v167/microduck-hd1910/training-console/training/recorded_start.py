"""One static encoder/gravity starting pose, never a trajectory replay.

Only the isolated single-world target-limit evaluation calls this module. The
normal reset still samples all random parameters and hidden actuator state.
"""
import copy
import math


SCHEMA = 'microduck-recorded-start-v1'
ENCODER_TOLERANCE_DEG = 0.1
GRAVITY_TOLERANCE = 0.001
CONVENTIONS = {
    'velocity': 'zero_all_qvel',
    'yaw': 'preserve_source_supine_world_z_twist',
    'placement': 'existing_plane_1mm_clearance_no_physics_step',
    'scope': 'encoder_pose_and_gravity_only',
}


def _vector(value, length, label):
    if not isinstance(value, (tuple, list)) or len(value) != length:
        raise ValueError(label + '长度无效。')
    if any(type(x) not in (float, int) or not math.isfinite(x) for x in value):
        raise ValueError(label + '含非有限数值。')
    return [float(x) for x in value]


def validate_pose(pose):
    """Defend the reset boundary; full source/freshness validation is upstream."""
    if not isinstance(pose, dict) or pose.get('schema') != SCHEMA:
        raise ValueError('真机起点格式无效。')
    names = pose.get('joint_names')
    if not isinstance(names, list) or len(names) != 14 or any(not isinstance(n, str) for n in names) or len(set(names)) != 14:
        raise ValueError('真机起点需要14个不重复的命名关节。')
    _vector(pose.get('joint_pos_rad'), 14, '真机关节位置')
    _vector(pose.get('joint_vel_rad_s'), 14, '真机关节速度')
    gravity = _vector(pose.get('gravity_b'), 3, '真机重力方向')
    _vector(pose.get('gyro_rad_s'), 3, '真机角速度')
    if not .98 <= math.sqrt(sum(v * v for v in gravity)) <= 1.02:
        raise ValueError('真机重力方向范数无效。')
    return pose


def multiply_quaternions(a, b):
    w, x, y, z = a
    v, i, j, k = b
    return [w*v-x*i-y*j-z*k, w*i+x*v+y*k-z*j,
            w*j-x*k+y*v+z*i, w*k+x*j-y*i+z*v]


def gravity_from_quaternion(quat):
    q = _vector(quat, 4, '根姿态四元数')
    norm = math.sqrt(sum(v * v for v in q))
    if norm < 1e-12:
        raise ValueError('根姿态四元数为零。')
    w, x, y, z = [v / norm for v in q]
    # R(q)^T * world_down. Body gravity is independent of global yaw.
    return [2*(w*y-x*z), -2*(y*z+w*x), 2*(x*x+y*y)-1]


def quaternion_for_gravity(gravity, source_quat):
    """Minimal gravity tilt, left-multiplied by the reset's world-Z twist.

    A gravity vector alone contains no yaw information. The upstream supine
    reset has q = yaw * pitch(-pi/2), whose world-Z twist is (w,0,0,z).
    Retaining that sampled twist preserves the reset's yaw convention/RNG.
    """
    g = _vector(gravity, 3, '真机重力方向')
    norm = math.sqrt(sum(v*v for v in g))
    if norm < 1e-12:
        raise ValueError('重力方向为零。')
    gx, gy, gz = [v / norm for v in g]
    # Shortest rotation mapping body gravity g to [0,0,-1].
    tilt = [1-gz, -gy, gx, 0.0]
    tilt_norm = math.sqrt(sum(v*v for v in tilt))
    tilt = [0.0, 1.0, 0.0, 0.0] if tilt_norm < 1e-12 else [v / tilt_norm for v in tilt]
    source = _vector(source_quat, 4, '原起点四元数')
    yaw_norm = math.hypot(source[0], source[3])
    if yaw_norm < 1e-12:
        raise ValueError('原仰躺起点无法确定约定的世界yaw。')
    yaw = [source[0]/yaw_norm, 0.0, 0.0, source[3]/yaw_norm]
    return multiply_quaternions(yaw, tilt)


def joint_layout(names, all_names, qpos_addresses, *, backlash_expected):
    if len(all_names) != len(qpos_addresses) or len(set(all_names)) != len(all_names):
        raise ValueError('仿真关节名称/位置索引不完整。')
    index = dict(zip(all_names, qpos_addresses))
    if any(name not in index for name in names):
        raise ValueError('真机起点关节名称与模型不一致。')
    passive = ['passive_' + name + '_backlash' for name in names]
    count = sum(name in index for name in passive)
    if count != (14 if backlash_expected else 0):
        raise ValueError('真机起点背隙关节配对不完整：%s/14。' % count)
    return [(all_names.index(name), int(index[name]),
             int(index[pname]) if backlash_expected else None)
            for name, pname in zip(names, passive)]


def encoder_positions(qpos, bias, layout):
    return [float(qpos[motor]) + (float(qpos[passive]) if passive is not None else 0.0)
            + float(bias[local]) for local, motor, passive in layout]


def motor_positions(encoders, qpos, bias, layout):
    values = [float(encoder) - (float(qpos[passive]) if passive is not None else 0.0)
              - float(bias[local]) for encoder, (local, motor, passive) in zip(encoders, layout)]
    if any(not math.isfinite(value) for value in values):
        raise ValueError('真机起点motor/背隙/编码器偏置含非有限数值。')
    return values


def _tolist(value):
    return value.detach().cpu().tolist()


def apply_pose(env, env_ids, pose, *, backlash_expected):
    """Called inside the official reset, before placement and history resets."""
    validate_pose(pose)
    if env.num_envs != 1:
        raise ValueError('真机起点仅支持隔离的单环境仿真对照。')
    robot = env.scene['robot']
    names = list(robot.joint_names)
    layout = joint_layout(pose['joint_names'], names, _tolist(robot.data.indexing.joint_q_adr),
                          backlash_expected=backlash_expected)
    for eid in env_ids.tolist():
        qpos = _tolist(env.sim.data.qpos[eid])
        bias = _tolist(robot.data.encoder_bias[eid])
        motors = motor_positions(pose['joint_pos_rad'], qpos, bias, layout)
        quat = quaternion_for_gravity(pose['gravity_b'], qpos[3:7])
        # Scalars work for both torch.Tensor and mjlab TorchArray views. No
        # forward/integration/action or RNG sampling is performed here.
        for value, (_, address, _) in zip(motors, layout):
            env.sim.data.qpos[eid, address] = value
        for address, value in enumerate(quat, 3):
            env.sim.data.qpos[eid, address] = value
        env.sim.data.qvel[eid, :] = 0.0
    env._studio_recorded_start_application = {
        'source_frame_index': pose.get('frame_index'),
        'conventions': copy.deepcopy(CONVENTIONS),
    }


def compare_readback(pose, encoder, gravity, quat, qvel):
    """JSON-only first-action gate. No tolerance is applied to bad numbers."""
    validate_pose(pose)
    result = {
        'schema': 'microduck-recorded-start-check-v1', 'passed': False,
        'source': {key: pose.get(key) for key in ('frame_index', 'active_frame_index', 'frame_at_s', 'state_t_ns', 'gap_s', 'source')},
        'requested': {'joint_names': list(pose['joint_names']), 'joint_pos_rad': list(pose['joint_pos_rad']),
                      'gravity_b': list(pose['gravity_b']), 'gravity_norm': math.sqrt(sum(v*v for v in pose['gravity_b'])),
                      'source_joint_vel_rad_s': list(pose['joint_vel_rad_s']), 'source_gyro_rad_s': list(pose['gyro_rad_s'])},
        'measured': {'joint_names': list(pose['joint_names']), 'joint_pos_rad': encoder,
                     'gravity_b': gravity, 'root_quat_wxyz': quat, 'qvel_max_abs': None,
                     'gravity_from_qpos_b': None,
                     'gravity_source': 'robot.data.projected_gravity_b'},
        'errors': {'encoder_max_abs_rad': None, 'encoder_max_abs_deg': None,
                   'gravity_l2': None, 'gravity_data_vs_qpos_l2': None},
        'tolerances': {'encoder_max_abs_deg': ENCODER_TOLERANCE_DEG, 'gravity_l2': GRAVITY_TOLERANCE,
                       'gravity_data_vs_qpos_l2': GRAVITY_TOLERANCE, 'qvel_max_abs': 1e-8},
        'conventions': copy.deepcopy(CONVENTIONS),
        'reason': '',
    }
    try:
        encoder = _vector(encoder, 14, '回读编码器位置')
        gravity = _vector(gravity, 3, '回读机身重力方向')
        quat = _vector(quat, 4, '回读四元数')
        qvel = _vector(qvel, len(qvel), '回读速度')
        qpos_gravity = gravity_from_quaternion(quat)
    except ValueError as error:
        result['reason'] = str(error)
        return result
    encoder_error = max(abs(a-b) for a, b in zip(pose['joint_pos_rad'], encoder))
    gravity_error = math.sqrt(sum((a-b)**2 for a, b in zip(pose['gravity_b'], gravity)))
    consistency_error = math.sqrt(sum((a-b)**2 for a, b in zip(gravity, qpos_gravity)))
    velocity_max = max((abs(v) for v in qvel), default=0.0)
    passed = (encoder_error <= math.radians(ENCODER_TOLERANCE_DEG) and gravity_error <= GRAVITY_TOLERANCE
              and consistency_error <= GRAVITY_TOLERANCE and velocity_max <= 1e-8)
    result['measured'].update(gravity_from_qpos_b=qpos_gravity, qvel_max_abs=velocity_max)
    result['errors'].update(encoder_max_abs_rad=encoder_error, encoder_max_abs_deg=math.degrees(encoder_error),
                            gravity_l2=gravity_error, gravity_data_vs_qpos_l2=consistency_error)
    result.update(passed=passed, reason='' if passed else '首次动作前真机起点回读未达到编码器/重力/静止误差要求。')
    return result


def verify_pose(env, pose, *, backlash_expected):
    if env.num_envs != 1:
        raise ValueError('真机起点回读仅支持单环境。')
    robot = env.scene['robot']
    qpos, qvel = _tolist(env.sim.data.qpos[0]), _tolist(env.sim.data.qvel[0])
    layout = joint_layout(pose['joint_names'], list(robot.joint_names),
                          _tolist(robot.data.indexing.joint_q_adr), backlash_expected=backlash_expected)
    encoder = encoder_positions(qpos, _tolist(robot.data.encoder_bias[0]), layout)
    # EntityData is also consumed by policy observations and the stand/roll
    # recorder. Checking it separately catches stale post-reset data without
    # performing an extra simulation step to hide the mismatch.
    gravity = _tolist(robot.data.projected_gravity_b[0])
    return compare_readback(pose, encoder, gravity, qpos[3:7], qvel)

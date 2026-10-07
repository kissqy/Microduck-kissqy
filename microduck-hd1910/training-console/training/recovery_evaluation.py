"""Isolated StandUp evaluation: mature curricula and repeatable ground starts.

Only play/ONNX environments opt in. Training, previews, export reconstruction,
checkpoint weights and the frozen upstream source are never changed here.
"""
import copy
import math


POSES = {
    'mixed': '训练最终混合',
    'back_flat': '完全背朝地',
    'left_side': '左侧躺',
    'right_side': '右侧躺',
    'face_down': '趴地',
}
GROUND_EVENT = 'set_ground_state'
STARTUP_EVENT = 'studio_recovery_evaluation'
HOLD_SECONDS = 1.0
MAX_TILT_DEG = 15.0
HEIGHT_TOLERANCE_M = 0.01
GROUND_CLEARANCE_M = 0.001


def eligible(request):
    if request.get('engine') != 'official_0151' or request.get('op') not in ('play', 'onnx'):
        return False
    if __package__:
        from .official_spec import TASKS
    else:
        from official_spec import TASKS
    return TASKS.get(request.get('task'), {}).get('role') == 'stand'


def prepare_config(cfg, request):
    """Install one startup event, after real managers exist and before reset.

Calling the original curriculum functions against those managers avoids a
second, incomplete translation of reward/event/command curriculum semantics.
The functions run once at their mature stage. No curriculum runs during play.
"""
    if not eligible(request) or STARTUP_EVENT in cfg.events:
        return cfg
    from mjlab.managers.event_manager import EventTermCfg

    specialist = bool(request.get('recovery_evaluation'))
    if specialist:
        cfg.scene.terrain.terrain_type = 'plane'
        cfg.scene.terrain.terrain_generator = None
        for name in ('push_robot', 'topple_push'):
            cfg.events.pop(name, None)
        for name, term in tuple(cfg.curriculum.items()):
            if term is not None and (term.params or {}).get('event_name') in ('push_robot', 'topple_push'):
                cfg.curriculum.pop(name)

    names, steps = [], []
    for name, term in cfg.curriculum.items():
        if term is None:
            continue
        scheduled = [stage['step'] for key, values in term.params.items()
                     if key.endswith('_stages') and isinstance(values, (list, tuple))
                     for stage in values if isinstance(stage, dict) and 'step' in stage]
        if scheduled:
            names.append(name)
            steps.extend(scheduled)
    cfg.events[STARTUP_EVENT] = EventTermCfg(
        func=initialize_evaluation, mode='startup',
        params={'mature_step': int(max(steps, default=0)) + 1,
                'timed_terms': tuple(names), 'specialist': specialist})
    return cfg


def initialize_evaluation(env, env_ids, mature_step, timed_terms, specialist=False):
    """Run original timed curricula against live managers, then freeze them."""
    import torch
    from mjlab.managers.curriculum_manager import NullCurriculumManager

    ids = torch.arange(env.num_envs, device=env.device, dtype=torch.long)
    original_step = env.common_step_counter
    manager = env.curriculum_manager
    try:
        env.common_step_counter = mature_step
        for name in timed_terms:
            term = manager.get_term_cfg(name)
            term.func(env, ids, **term.params)
    finally:
        env.common_step_counter = original_step
    # A later PT load may restore its counter. Both PT and ONNX must retain the
    # same fixed evaluation settings; untimed terrain promotion is also off.
    env.curriculum_manager = NullCurriculumManager()
    term = env.event_manager.get_term_cfg(GROUND_EVENT)
    env._studio_recovery_evaluation = {
        'mature_step': mature_step, 'timed_terms': list(timed_terms),
        'specialist': specialist,
        'final_mix': {key: float(term.params.get(key, 0.0)) for key in
                      ('standing_prob', 'sitting_prob', 'face_down_prob', 'face_up_prob')},
    }
    if specialist:
        source_func, source_params = term.func, copy.deepcopy(term.params)
        term.func = reset_ground_pose
        term.params = {'source_func': source_func, 'source_params': source_params,
                       'pose': 'back_flat'}
        zero_commands(env, freeze_ranges=True)


def zero_commands(env, freeze_ranges=False):
    """Keep all 13 command observations neutral during the recovery check."""
    for name in ('twist', 'head_pose', 'body_pose'):
        if name not in env.command_manager.active_terms:
            continue
        term = env.command_manager.get_term(name)
        if freeze_ranges:
            ranges = term.cfg.ranges
            if isinstance(ranges, (tuple, list)):
                term.cfg.ranges = tuple((0.0, 0.0) for _ in ranges)
            else:
                for field in ('lin_vel_x', 'lin_vel_y', 'ang_vel_z', 'heading'):
                    if hasattr(ranges, field):
                        setattr(ranges, field, (0.0, 0.0))
                # UniformVelocityCommand's forward bucket clamps vx to at
                # least 0.3 even with zero ranges, and init_velocity_prob can
                # write a launch velocity. Neither belongs in a ground check.
                for field in ('rel_forward_envs', 'rel_heading_envs', 'rel_world_envs',
                              'rel_turn_in_place_envs', 'init_velocity_prob'):
                    if hasattr(term.cfg, field):
                        setattr(term.cfg, field, 0.0)
                if hasattr(term.cfg, 'rel_standing_envs'):
                    term.cfg.rel_standing_envs = 1.0
                if hasattr(term.cfg, 'heading_command'):
                    term.cfg.heading_command = False
        term.command.zero_()


def reset_ground_pose(env, env_ids, source_func, source_params, pose='back_flat'):
    """Use upstream joint/reset conventions and restrict the starting pose.

Upstream supine is yaw * pitch(-90 degrees). Its log-roll axis is BODY Z;
right-multiplication by +/-90 degrees makes the left/right side face down.
The reset remains inside EventManager, before official history resets.
"""
    import torch

    if pose not in POSES:
        raise ValueError('未知翻身检查姿态：' + str(pose))
    if env_ids is None:
        env_ids = torch.arange(env.num_envs, device=env.device, dtype=torch.long)
    if len(env_ids) == 0:
        return
    ids = env_ids.to(device=env.device, dtype=torch.long)
    params = copy.deepcopy(source_params)
    if pose != 'mixed':
        params.update(standing_prob=0.0, sitting_prob=0.0, face_down_prob=0.0,
                      face_up_prob=0.0, face_up_roll_max=0.0)
        params['face_down_prob' if pose == 'face_down' else 'face_up_prob'] = 1.0
    source_func(env, ids, **params)
    if pose in ('left_side', 'right_side'):
        angle = math.pi / 2 if pose == 'left_side' else -math.pi / 2
        ct, st = math.cos(angle / 2), math.sin(angle / 2)
        q = env.sim.data.qpos[ids, 3:7].clone()
        w, x, y, z = q.unbind(dim=1)
        env.sim.data.qpos[ids, 3:7] = torch.stack(
            (w * ct - z * st, x * ct + y * st,
             y * ct - x * st, w * st + z * ct), dim=1)
    if pose != 'mixed':
        place_on_plane(env, ids)
        env.sim.data.qvel[ids, :] = 0.0
    # The original event can copy the previous episode's last action before
    # ActionManager subsequently zeroes it. Keep these caches consistent with
    # the zero previous-action observation of this new episode.
    for name in ('_prev_leg_actions', '_prev_neck_actions',
                 '_prev_leg_actions_for_acc', '_prev_prev_leg_actions_for_acc',
                 '_prev_neck_actions_for_acc', '_prev_prev_neck_actions_for_acc'):
        value = getattr(env, name, None)
        if value is not None:
            value[ids] = 0.0
    env._studio_recovery_reset_serial = getattr(env, '_studio_recovery_reset_serial', 0) + 1


def geom_lowest_z(model, data, index):
    """Exact vertical support for the collision primitives and mesh vertices."""
    import numpy as np
    import mujoco

    kind = model.geom_type[index]
    size = model.geom_size[index]
    z_axis = data.geom_xmat[index].reshape(3, 3)[2]
    center = float(data.geom_xpos[index, 2])
    if kind == mujoco.mjtGeom.mjGEOM_MESH:
        mesh = model.geom_dataid[index]
        start, count = model.mesh_vertadr[mesh], model.mesh_vertnum[mesh]
        vertices = model.mesh_vert[start:start + count]
        return center + float(np.min(vertices @ z_axis))
    if kind == mujoco.mjtGeom.mjGEOM_BOX:
        extent = float(np.dot(np.abs(z_axis), size))
    elif kind == mujoco.mjtGeom.mjGEOM_SPHERE:
        extent = float(size[0])
    elif kind == mujoco.mjtGeom.mjGEOM_CAPSULE:
        extent = float(size[0] + size[1] * abs(z_axis[2]))
    elif kind == mujoco.mjtGeom.mjGEOM_CYLINDER:
        extent = float(size[1] * abs(z_axis[2]) + size[0] * math.sqrt(max(0.0, 1.0 - z_axis[2] ** 2)))
    elif kind == mujoco.mjtGeom.mjGEOM_ELLIPSOID:
        extent = float(np.linalg.norm(size * z_axis))
    else:
        raise ValueError('翻身检查遇到未支持的机器人碰撞形状：' + str(int(kind)))
    return center - extent


def place_on_plane(env, env_ids):
    """Translate, without a physics step, until the lowest floor collider is 1mm up.

The CPU data is a kinematics scratch copy. It never integrates the live model
or supplies actions, so there is no hidden free fall or policy warm-up.
"""
    import mujoco

    model = env.sim.mj_model
    scratch = getattr(env, '_studio_recovery_kinematics', None)
    if scratch is None:
        scratch = mujoco.MjData(model)
        env._studio_recovery_kinematics = scratch
    robot_geoms = set(env.scene['robot'].data.indexing.geom_ids.tolist())
    planes = [i for i in range(model.ngeom)
              if i not in robot_geoms and model.geom_type[i] == mujoco.mjtGeom.mjGEOM_PLANE
              and (model.geom_contype[i] or model.geom_conaffinity[i])]
    if not planes:
        raise ValueError('固定翻身检查需要平地，未找到地面平面。')
    floor = planes[0]
    floor_type, floor_affinity = int(model.geom_contype[floor]), int(model.geom_conaffinity[floor])
    colliders = [i for i in robot_geoms if
                 ((int(model.geom_contype[i]) & floor_affinity) or
                  (int(model.geom_conaffinity[i]) & floor_type))]
    if not colliders:
        raise ValueError('固定翻身检查未找到可接触地面的机器人碰撞体。')
    for index in env_ids.tolist():
        scratch.qpos[:] = env.sim.data.qpos[index].detach().cpu().numpy()
        mujoco.mj_kinematics(model, scratch)
        lowest = min(geom_lowest_z(model, scratch, i) for i in colliders)
        floor_z = float(scratch.geom_xpos[floor, 2])
        env.sim.data.qpos[index, 2] += floor_z + GROUND_CLEARANCE_M - lowest


def stand_height(env):
    """Take the existing task's target, never a generic robot height."""
    term = env.reward_manager.get_term_cfg('height_stand')
    value = float(term.params['target_height'])
    if not math.isfinite(value) or value <= HEIGHT_TOLERANCE_M:
        raise ValueError('倒地老师缺少有效站立目标高度，不能统计起身结果。')
    return value


def capture_pose(env, request, trial=None, active_model_name=None):
    """Read a diagnostic state on the physics thread, without stepping or reset.

This is a pose/velocity record for a future starting-state bank, not a complete
checkpoint of actuator hysteresis, solver state, or random-number generators.
"""
    import hashlib
    import time
    from pathlib import Path
    import mujoco

    robot, model = env.scene['robot'], env.sim.mj_model
    data, indexing = robot.data, robot.data.indexing

    def values(tensor):
        return tensor.detach().cpu().tolist()

    requested = Path(request.get('onnx_path') or request.get('checkpoint') or 'zero')
    active = active_model_name or requested.name
    path = requested if active == requested.name else requested.with_name(Path(active).name)
    identity = {'requested_name': requested.name, 'active_name': active, 'sha256': None}
    # Read bytes only, never deserialize a checkpoint. Cache by exact file stat
    # so repeated captures do not repeatedly hash a large PT.
    if path.is_file():
        stat = path.stat()
        key = (str(path), stat.st_size, stat.st_mtime_ns)
        cached = getattr(env, '_studio_pose_model_hash', None)
        if cached is None or cached[0] != key:
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(chunk)
            cached = (key, digest.hexdigest())
            env._studio_pose_model_hash = cached
        identity['sha256'] = cached[1]
    contacts = {'available': False, 'support_forces_verified': False}
    try:
        live = env.sim.data.contact
        detected = int(env.sim.data.nacon[0].item())
        count = max(0, min(detected, int(live.worldid.shape[0])))
        ids = (live.worldid[:count] == 0).nonzero().flatten().tolist()
        pairs = []
        for index in ids[:32]:
            geoms = [int(value) for value in live.geom[index].tolist()]
            pairs.append({'geom_ids': geoms,
                          'geom_names': [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, i)
                                         if i >= 0 else None for i in geoms],
                          'body_names': [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, int(model.geom_bodyid[i]))
                                         if i >= 0 else None for i in geoms],
                          'distance_m': float(live.dist[index].item()),
                          'position_w': values(live.pos[index])})
        contacts.update(available=True, count=len(ids), global_detected_count=detected,
                        buffer_overflow=detected > count, pairs=pairs, pairs_truncated=len(ids) > 32)
    except (AttributeError, IndexError, RuntimeError, TypeError) as error:
        contacts['read_error'] = str(error)
    # mjlab creates these flags on its first step, so a paused, fresh viewer
    # can legitimately have no previous step result yet.
    reset_flags = {key: (bool(value[0].item()) if value is not None else None)
                   for key, value in (('terminated', getattr(env, 'reset_terminated', None)),
                                      ('timed_out', getattr(env, 'reset_time_outs', None)))}
    result = {
        'schema': 'microduck-pose-record-v1', 'captured_at_unix': time.time(),
        'task': request.get('task'), 'operation': request.get('op'),
        'model': identity, 'request_source_job': request.get('source_job'),
        'request_source_iteration': request.get('source_iteration'),
        'source_revision': request.get('expected_revision'),
        'terrain': {'type': env.cfg.scene.terrain.terrain_type,
                    'env_origin_w': values(env.scene.env_origins[0])},
        'evaluation': copy.deepcopy(getattr(env, '_studio_recovery_evaluation', None)),
        'trial': copy.deepcopy(trial.current) if trial is not None else None,
        'episode_step': int(env.episode_length_buf[0].item()), 'step_dt': env.step_dt,
        'reset_flags': reset_flags,
        'state_may_be_post_auto_reset': (any(reset_flags.values())
                                        if all(value is not None for value in reset_flags.values()) else None),
        'qpos': values(env.sim.data.qpos[0]), 'qvel': values(env.sim.data.qvel[0]),
        'projected_gravity_b': values(data.projected_gravity_b[0]),
        'root_link_pos_w': values(data.root_link_pos_w[0]),
        'root_link_quat_w_wxyz': values(data.root_link_quat_w[0]),
        'joint_names': list(robot.joint_names), 'joint_ids': values(indexing.joint_ids),
        'joint_qpos_addresses': values(indexing.joint_q_adr),
        'joint_qvel_addresses': values(indexing.joint_v_adr),
        'joint_pos': values(data.joint_pos[0]), 'joint_vel': values(data.joint_vel[0]),
        'raw_action': values(env.action_manager.action[0]),
        'commands': {name: values(env.command_manager.get_term(name).command[0])
                     for name in ('twist', 'head_pose', 'body_pose')
                     if name in env.command_manager.active_terms},
        'action_mapping': {'scale': env.cfg.actions['joint_pos'].scale,
                           'use_default_offset': env.cfg.actions['joint_pos'].use_default_offset,
                           'firmware_p': [float(a.kp_fw) for a in env.cfg.scene.entities['robot'].articulation.actuators
                                          if hasattr(a, 'kp_fw')],
                           'action_filter': copy.deepcopy((request.get('policy_parameters') or {}).get('action_filter'))},
        'contacts': contacts,
        'replay_scope': 'pose and velocity; actuator, solver and random-generator state are not included',
    }
    # A failed physics state can contain NaN. Keep the log valid JSON and mark
    # those values explicitly instead of silently inventing physical numbers.
    def finite_json(value):
        if isinstance(value, float) and not math.isfinite(value):
            return None
        if isinstance(value, dict):
            return {key: finite_json(item) for key, item in value.items()}
        if isinstance(value, (tuple, list)):
            return [finite_json(item) for item in value]
        return value
    result['finite_qpos_qvel'] = all(math.isfinite(value) for value in result['qpos'] + result['qvel'])
    return finite_json(result)


class TrialRecorder:
    """Pose-separated geometry results; reset observations never count as recovery."""

    def __init__(self, target_height):
        self.target_height = float(target_height)
        self.minimum_height = self.target_height - HEIGHT_TOLERANCE_M
        self.mode = 'back_flat'
        self.counts = {key: {'passed': 0, 'failed': 0, 'cancelled': 0} for key in POSES if key != 'mixed'}
        self.current = None
        self.history = []
        self.sequence = 0

    def start(self, mode):
        if mode not in POSES:
            raise ValueError('未知翻身检查姿态。')
        if self.current and self.current['result'] == 'running':
            self.finish('cancelled', '重新放置')
        self.mode = mode
        self.sequence += 1
        self.current = {'trial': self.sequence, 'pose': mode, 'elapsed_s': 0.0,
                        'hold_s': 0.0, 'result': 'observing' if mode == 'mixed' else 'running',
                        'reason': '', 'height_m': None, 'tilt_deg': None}

    def finish(self, result, reason):
        if not self.current or self.current['result'] != 'running':
            return False
        self.current.update(result=result, reason=reason)
        self.counts[self.current['pose']][result] += 1
        self.history.append(dict(self.current))
        self.history = self.history[-100:]
        return True

    def observe(self, step_dt, height=None, gravity_z=None, terminated=False, timed_out=False):
        if not self.current or self.current['result'] not in ('running', 'observing'):
            return False
        self.current['elapsed_s'] += step_dt
        # env.step returns a new episode's pose after auto-reset. Check its flags
        # FIRST, so a reset into standing cannot manufacture a passed trial.
        if terminated or timed_out:
            return self.finish('failed', '回合终止' if terminated else '回合到时')
        if height is None or gravity_z is None:
            return False
        tilt = math.degrees(math.acos(max(-1.0, min(1.0, -float(gravity_z)))))
        self.current.update(height_m=float(height), tilt_deg=tilt)
        qualifies = math.isfinite(height) and math.isfinite(gravity_z) and height >= self.minimum_height and tilt <= MAX_TILT_DEG
        self.current['hold_s'] = self.current['hold_s'] + step_dt if qualifies else 0.0
        if self.current['result'] == 'running' and self.current['hold_s'] + 1e-9 >= HOLD_SECONDS:
            return self.finish('passed', '达到站高与倾角指标并持续1秒')
        return False

    def state(self):
        return {'pose': self.mode, 'pose_label': POSES[self.mode],
                'target_height_m': self.target_height, 'minimum_height_m': self.minimum_height,
                'maximum_tilt_deg': MAX_TILT_DEG, 'hold_seconds': HOLD_SECONDS,
                'current': copy.deepcopy(self.current), 'counts': copy.deepcopy(self.counts),
                'history': copy.deepcopy(self.history), 'contact_verified': False,
                'terrain': 'plane', 'commands': 'zero'}

    def html(self):
        state = self.current or {}
        results = {'running': '检查中', 'observing': '混合观察，不计起身成功率',
                   'passed': '通过本次姿态与高度检查', 'failed': '本次未通过', 'cancelled': '已取消'}
        status = results.get(state.get('result'), '等待检查')
        reason = state.get('reason', '')
        rows = '<br>'.join(f'{POSES[key]}：通过 {v["passed"]} / 完成 {v["passed"] + v["failed"]}'
                           + (f'（取消 {v["cancelled"]}）' if v['cancelled'] else '')
                           for key, v in self.counts.items())
        return (f'<b>{POSES[self.mode]} · {status}</b><br>{reason}<br>'
                f'本次 {state.get("elapsed_s", 0.0):.1f} 秒；连续达标 {state.get("hold_s", 0.0):.1f} 秒<br>'
                f'标准：躯干高度 ≥ {self.minimum_height * 1000:.0f} mm，倾角 ≤ {MAX_TILT_DEG:.0f}°，持续 {HOLD_SECONDS:.0f} 秒。<br>'
                f'{rows}<br><small>仅记录姿态与高度；未核验脚底接触。自动重置不算起身，混合中的站姿不计成功。</small>')

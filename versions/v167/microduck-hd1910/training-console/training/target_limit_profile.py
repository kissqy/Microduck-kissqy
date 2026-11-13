"""Read-only extraction of hardware goal mapping for an ONNX A/B evaluation.

This profile never updates the saved training recipe, calibration, or robot.
Only named policy joints are exported; mouth and passive hinges have no action.
"""
import copy
import hashlib
import json
import math
import re

try:
    from .official_spec import RUNTIME_JOINTS, TASKS
except ImportError:
    from official_spec import RUNTIME_JOINTS, TASKS

SCHEMA = 'microduck-target-limit-profile-v1'
MAX_RECORDING_BYTES = 32 * 1024 * 1024
POLICY_IDS = dict(zip(RUNTIME_JOINTS, (20, 21, 22, 23, 24, 30, 31, 32, 33, 10, 11, 12, 13, 14)))
_SHA = re.compile(r'[0-9a-f]{64}')
RECORDED_START_SCHEMA = 'microduck-recorded-start-v1'
RECORDED_START_SOURCE = 'last_inactive_before_first_standup_enable'
# Availability checks for a near-static sample, not hardware specifications.
START_MAX_GAP_S = 0.3
START_MAX_JOINT_SPEED = 0.25
START_MAX_GYRO_NORM = 0.25


def _finite(value, label):
    if type(value) not in (int, float):
        raise ValueError(label + '必须是有限数值。')
    try:
        number = float(value)
    except (OverflowError, ValueError) as error:
        raise ValueError(label + '必须是有限数值。') from error
    if not math.isfinite(number):
        raise ValueError(label + '必须是有限数值。')
    return number


def _rows(rows):
    if not isinstance(rows, list) or len(rows) != 14:
        raise ValueError('限幅对照需要14个策略关节的完整标定。')
    found = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('关节标定格式无效。')
        name = row.get('name')
        if not isinstance(name, str) or name not in POLICY_IDS or name in found or type(row.get('id')) is not int or row['id'] != POLICY_IDS[name]:
            raise ValueError('限幅对照的关节名称或ID不匹配：' + str(name))
        zero, direction = row.get('zero_raw'), row.get('direction')
        if type(zero) is not int or not 0 <= zero <= 4095 or type(direction) is not int or direction not in (-1, 1):
            raise ValueError('关节零点或方向无效：' + name)
        lo, hi = (_finite(row.get(k), name + ' ' + k) for k in ('min_rad', 'max_rad'))
        if not -math.pi <= lo < hi <= math.pi:
            raise ValueError('关节标定限位必须在正负180度内且下限小于上限：' + name)
        for angle in (lo, hi):
            raw = zero + angle * direction * 4096.0 / math.tau
            # Rust f64::round uses ties away from zero, including a boundary
            # that lands just below raw zero. Do not silently clamp or wrap.
            rounded = math.floor(raw + .5) if raw >= 0 else math.ceil(raw - .5)
            if not 0 <= rounded <= 4095:
                raise ValueError('标定边界超出单圈编码器可写范围：' + name)
        found[name] = {'name': name, 'id': row['id'], 'zero_raw': zero,
                       'direction': direction, 'min_rad': lo, 'max_rad': hi}
    return [found[name] for name in RUNTIME_JOINTS]


def _recording_rows(rows):
    """Check the full runtime joint set, then discard only the known mouth row."""
    if not isinstance(rows, list) or len(rows) != 15:
        raise ValueError('起身过程缺少完整15关节标定，无法还原目标夹取。')
    expected = dict(POLICY_IDS, mouth=34)
    found = set()
    selected = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('关节标定格式无效。')
        name = row.get('name')
        if not isinstance(name, str) or name not in expected or name in found or type(row.get('id')) is not int or row['id'] != expected[name]:
            raise ValueError('真机记录的关节名称或ID不匹配：' + str(name))
        found.add(name)
        if name in POLICY_IDS:
            if row.get('calibrated') is not True:
                raise ValueError('真机记录中存在未完成标定的策略关节。')
            selected.append(row)
    return _rows(selected)


def _vector(value, length, label):
    if not isinstance(value, list) or len(value) != length:
        raise ValueError(label + '维数无效。')
    return [_finite(v, label) for v in value]


def _validate_recorded_start(value, frame_count):
    keys = {'schema', 'source', 'frame_index', 'active_frame_index', 'frame_at_s',
            'state_t_ns', 'gap_s', 'joint_names', 'joint_pos_rad', 'joint_vel_rad_s',
            'gravity_b', 'gyro_rad_s'}
    if not isinstance(value, dict) or set(value) != keys or value.get('schema') != RECORDED_START_SCHEMA or value.get('source') != RECORDED_START_SOURCE:
        raise ValueError('真机起点字段或来源无效。')
    first, active = value['frame_index'], value['active_frame_index']
    if type(first) is not int or type(active) is not int or not 0 <= first < active < frame_count or active != first + 1:
        raise ValueError('真机起点必须紧邻首次起身启用帧之前。')
    if type(value['state_t_ns']) is not int or not 0 < value['state_t_ns'] < 2**63:
        raise ValueError('真机起点缺少有效状态时间。')
    at, gap = _finite(value['frame_at_s'], '真机起点记录时间'), _finite(value['gap_s'], '真机起点间隔')
    if not 0 < gap <= START_MAX_GAP_S:
        raise ValueError('真机起点距启用帧超过0.3秒，或时间顺序无效。')
    names = value['joint_names']
    if not isinstance(names, list) or len(names) != 14 or any(not isinstance(n, str) for n in names) or set(names) != set(RUNTIME_JOINTS):
        raise ValueError('真机起点必须包含14个不重复的策略关节名称。')
    pos = _vector(value['joint_pos_rad'], 14, '真机起点关节角')
    vel = _vector(value['joint_vel_rad_s'], 14, '真机起点关节速度')
    gravity = _vector(value['gravity_b'], 3, '真机起点重力')
    gyro = _vector(value['gyro_rad_s'], 3, '真机起点角速度')
    if any(abs(v) > math.pi for v in pos):
        raise ValueError('真机起点关节角超出正负π。')
    if max(map(abs, vel)) > START_MAX_JOINT_SPEED or math.hypot(*gyro) > START_MAX_GYRO_NORM:
        raise ValueError('启用前样本仍在运动，无法作为近静止起点（关节/机身速度门槛0.25 rad/s）。')
    if not .98 <= math.hypot(*gravity) <= 1.02:
        raise ValueError('真机起点投影重力不是有效单位向量。')
    order = [names.index(name) for name in RUNTIME_JOINTS]
    return {'schema': RECORDED_START_SCHEMA, 'source': RECORDED_START_SOURCE,
            'frame_index': first, 'active_frame_index': active, 'frame_at_s': at,
            'state_t_ns': value['state_t_ns'], 'gap_s': gap,
            'joint_names': list(RUNTIME_JOINTS), 'joint_pos_rad': [pos[i] for i in order],
            'joint_vel_rad_s': [vel[i] for i in order], 'gravity_b': gravity, 'gyro_rad_s': gyro}


def _recorded_start(frames, active_index, identity):
    """Only the adjacent sample before the first matching activation is eligible."""
    if active_index == 0:
        raise ValueError('记录从起身启用后开始，没有首次启用前的样本。')
    previous, enabled = frames[active_index - 1], frames[active_index]
    bus, state = previous.get('bus'), previous.get('state')
    if not isinstance(bus, dict) or bus.get('policy_enabled') is not False or not isinstance(state, dict) or state.get('policy') != 'held':
        raise ValueError('首次起身启用前一帧不是已停用策略的保持状态。')
    enabled_state = enabled.get('state')
    if not isinstance(enabled_state, dict) or enabled_state.get('policy') not in ('stand', 'stand_test'):
        raise ValueError('首次起身启用帧缺少明确的策略状态。')
    loaded = bus.get('loaded_models')
    model = loaded.get(enabled_state['policy']) if isinstance(loaded, dict) else None
    if not isinstance(model, dict) or any(model.get(k) != identity[k] for k in ('task',)) or model.get('sha256') != identity['model_sha256']:
        raise ValueError('启用前样本的已加载起身模型身份无法核对。')
    calibration = previous.get('calibration')
    if isinstance(calibration, dict) and isinstance(calibration.get('calibration'), dict):
        calibration = calibration['calibration']
    if not isinstance(calibration, dict) or _recording_rows(calibration.get('joints')) != identity['joints']:
        raise ValueError('启用前后的关节标定不一致。')
    if previous.get('connection_paused') is not False:
        raise ValueError('启用前样本处于暂停状态或缺少连接状态。')
    channels = previous.get('channels')
    if not isinstance(channels, dict):
        raise ValueError('启用前样本缺少状态新鲜度。')
    for key in ('state', 'bus'):
        channel = channels.get(key)
        if not isinstance(channel, dict) or channel.get('status') != 'live' or not 0 <= _finite(channel.get('age_ms'), key + '样本年龄') <= 200 or type(channel.get('seq')) is not int:
            raise ValueError('启用前状态或总线样本过旧，无法复用起点。')
    if channels['state']['seq'] != channels['bus']['seq']:
        raise ValueError('启用前状态与总线不属于同一采样批次。')
    native = bus.get('native')
    if not isinstance(native, dict) or bus.get('fresh_sample') is not True or bus.get('all_joints_fresh') is not True or native.get('all_joints_fresh') is not True or native.get('held_joint_ids') != [] or native.get('stale_joint_ids') != [] or not 0 <= _finite(native.get('sample_age_ms'), '关节样本年龄') <= 100:
        raise ValueError('启用前关节反馈过旧或存在保持/缺失关节。')
    feedback = native.get('joints')
    if not isinstance(feedback, list) or len(feedback) != 15 or any(not isinstance(row, dict) or row.get('feedback_fresh') is not True or not 0 <= _finite(row.get('sample_age_ms'), '原始反馈年龄') <= 100 for row in feedback):
        raise ValueError('启用前原始关节反馈缺失或过旧。')
    now, then = enabled_state.get('t_ns'), state.get('t_ns')
    if type(now) is not int or type(then) is not int or not 0 < then < 2**63 or not 0 < now < 2**63:
        raise ValueError('启用前后缺少有效状态时间。')
    wall_gap = _finite(enabled.get('at'), '启用帧记录时间') - _finite(previous.get('at'), '起点帧记录时间')
    if not 0 < wall_gap <= START_MAX_GAP_S:
        raise ValueError('启用前后录制间隔超过0.3秒，或时间顺序无效。')
    servos = previous.get('servos')
    positions = _vector(state.get('joints'), 15, '启用前关节反馈')
    velocities = _vector(state.get('velocities'), 15, '启用前关节速度')
    expected = dict(POLICY_IDS, mouth=34)
    if not isinstance(servos, list) or len(servos) != 15:
        raise ValueError('启用前缺少完整15关节名称映射。')
    by_name, indices = {}, set()
    for row in servos:
        if not isinstance(row, dict) or not isinstance(row.get('name'), str):
            raise ValueError('启用前关节名称映射无效。')
        name, index = row['name'], row.get('index')
        if name not in expected or name in by_name or type(row.get('id')) is not int or row['id'] != expected[name] or type(index) is not int or not 0 <= index < 15 or index in indices:
            raise ValueError('启用前关节名称、ID或数组索引不一致。')
        if row.get('status') != 'live' or not 0 <= _finite(row.get('sample_age_ms'), name + '样本年龄') <= 100 or abs(math.radians(_finite(row.get('angle_deg'), name + '反馈角度')) - positions[index]) > 1e-6:
            raise ValueError('启用前关节反馈过旧或数据映射不一致：' + name)
        by_name[name], indices = index, indices | {index}
    imu, safety = state.get('imu'), state.get('safety')
    if not isinstance(imu, dict) or not isinstance(safety, dict) or native.get('imu_ready') is not True or native.get('imu_mount_verified') is not True:
        raise ValueError('启用前IMU数据缺失或安装方向未验证。')
    return _validate_recorded_start({
        'schema': RECORDED_START_SCHEMA, 'source': RECORDED_START_SOURCE,
        'frame_index': active_index - 1, 'active_frame_index': active_index,
        'frame_at_s': previous['at'], 'state_t_ns': then, 'gap_s': (now - then) / 1e9,
        'joint_names': list(RUNTIME_JOINTS),
        'joint_pos_rad': [positions[by_name[name]] for name in RUNTIME_JOINTS],
        'joint_vel_rad_s': [velocities[by_name[name]] for name in RUNTIME_JOINTS],
        'gravity_b': safety.get('gravity'), 'gyro_rad_s': imu.get('gyro')}, len(frames))


def validate_profile(profile, expected_sha=None, expected_task=None):
    if not isinstance(profile, dict) or profile.get('schema') != SCHEMA:
        raise ValueError('请通过“限幅对照”载入运行中控导出的真机JSON。')
    allowed = {'schema', 'model_sha256', 'task', 'joints', 'recording', 'runtime', 'seed'}
    optional = {'recorded_start', 'recorded_start_unavailable_reason'}
    if not allowed <= set(profile) or set(profile) - allowed - optional or optional <= set(profile):
        raise ValueError('限幅对照资料字段不完整或包含未知字段。')
    sha, task = profile.get('model_sha256'), profile.get('task')
    if not isinstance(sha, str) or not _SHA.fullmatch(sha):
        raise ValueError('真机记录缺少完整模型SHA256。')
    if not isinstance(task, str) or TASKS.get(task, {}).get('role') != 'stand':
        raise ValueError('限幅对照只用于倒地起身老师。')
    if expected_sha is not None and sha != expected_sha:
        raise ValueError('所选ONNX与真机记录的模型SHA256不同；请选择这次真机运行的同一份模型。')
    if expected_task is not None and task != expected_task:
        raise ValueError('所选ONNX任务与真机记录不一致。')
    seed = profile.get('seed')
    if type(seed) is not int or not 0 <= seed < 2**31:
        raise ValueError('对照随机种子无效。')
    recording, runtime = profile.get('recording'), profile.get('runtime')
    if not isinstance(recording, dict) or not isinstance(runtime, dict):
        raise ValueError('真机记录来源或运行参数无效。')
    if set(recording) != {'created_at', 'source_name', 'source_sha256', 'frame_count', 'active_frames', 'build'}:
        raise ValueError('真机记录来源字段无效。')
    if not isinstance(recording['source_name'], str) or not 1 <= len(recording['source_name']) <= 255:
        raise ValueError('真机记录文件名无效。')
    if not isinstance(recording['source_sha256'], str) or not _SHA.fullmatch(recording['source_sha256']):
        raise ValueError('真机记录校验值无效。')
    _finite(recording['created_at'], '记录时间')
    if any(type(recording[k]) is not int or not 1 <= recording[k] <= 1500 for k in ('frame_count', 'active_frames')):
        raise ValueError('真机记录帧数无效。')
    if recording['active_frames'] > recording['frame_count'] or not isinstance(recording['build'], str) or len(recording['build']) > 160:
        raise ValueError('真机记录帧数或版本无效。')
    keys = {'base_action_scale', 'effective_action_scale_min', 'effective_action_scale_max',
            'head_alpha', 'legs_alpha', 'voltage_adapt'}
    if set(runtime) != keys or type(runtime['voltage_adapt']) is not bool:
        raise ValueError('真机运行参数字段无效。')
    checked_runtime = {k: _finite(runtime[k], k) for k in keys if k != 'voltage_adapt'}
    if not 0 < checked_runtime['base_action_scale'] <= 3 or not 0 < checked_runtime['effective_action_scale_min'] <= checked_runtime['effective_action_scale_max'] <= 3:
        raise ValueError('真机动作倍率无效。')
    if not all(0 < checked_runtime[k] <= 1 for k in ('head_alpha', 'legs_alpha')):
        raise ValueError('真机滤波系数无效。')
    checked_runtime['voltage_adapt'] = runtime['voltage_adapt']
    result = {'schema': SCHEMA, 'model_sha256': sha, 'task': task,
            'joints': _rows(profile['joints']), 'recording': copy.deepcopy(recording),
            'runtime': checked_runtime, 'seed': seed}
    if 'recorded_start' in profile:
        result['recorded_start'] = _validate_recorded_start(profile['recorded_start'], recording['frame_count'])
    if 'recorded_start_unavailable_reason' in profile:
        reason = profile['recorded_start_unavailable_reason']
        if not isinstance(reason, str) or not 1 <= len(reason) <= 240:
            raise ValueError('真机起点不可用说明无效。')
        result['recorded_start_unavailable_reason'] = reason
    return result


def from_recording(value):
    """Accept the exact downloaded file as text, retaining a provenance digest."""
    if not isinstance(value, dict) or set(value) != {'name', 'text'}:
        raise ValueError('请载入运行中控导出的JSON文件。')
    text, name = value['text'], value['name']
    if not isinstance(text, str) or not isinstance(name, str):
        raise ValueError('真机记录内容无效。')
    try:
        encoded = text.encode('utf-8')
    except UnicodeEncodeError as error:
        raise ValueError('真机记录不是有效UTF-8文本。') from error
    if not 0 < len(encoded) <= MAX_RECORDING_BYTES:
        raise ValueError('真机记录文件上限为32MiB。')
    def bad_number(raw):
        raise ValueError('真机记录包含非有限数值：' + raw)
    def finite_float(raw):
        # JSON permits an exponent such as 1e999, while Python's default float
        # parser silently turns it into infinity without calling parse_constant.
        return _finite(float(raw), '真机记录数值')
    try:
        recording = json.loads(text, parse_constant=bad_number, parse_float=finite_float)
    except (ValueError, RecursionError) as error:
        raise ValueError('无法读取真机JSON：' + str(error)) from error
    if not isinstance(recording, dict) or recording.get('schema') != 'microduck-console-recording/v1':
        raise ValueError('这不是运行中控的完整观测记录，请使用“导出记录”。')
    frames = recording.get('frames')
    if not isinstance(frames, list) or not 1 <= len(frames) <= 1500:
        raise ValueError('真机记录没有有效帧。')
    profiles, active, active_indices = [], [], []
    for frame_index, frame in enumerate(frames):
        if not isinstance(frame, dict):
            raise ValueError('真机记录帧格式无效。')
        bus = frame.get('bus')
        if bus is None:
            bus = {}
        if not isinstance(bus, dict):
            raise ValueError('真机总线状态无效。')
        enabled = bus.get('policy_enabled', False)
        if type(enabled) is not bool:
            raise ValueError('真机策略运行状态无效。')
        if not enabled:
            continue
        model = bus.get('active_model')
        if not isinstance(model, dict) or not isinstance(model.get('task'), str):
            raise ValueError('真机当前模型状态无效。')
        if TASKS.get(model['task'], {}).get('role') != 'stand':
            continue
        calibration = frame.get('calibration') or {}
        if isinstance(calibration, dict) and isinstance(calibration.get('calibration'), dict):
            calibration = calibration['calibration']
        rows = calibration.get('joints') if isinstance(calibration, dict) else None
        joints = _recording_rows(rows)
        filters = bus.get('active_target_filters')
        scales = bus.get('model_action_scales')
        if not isinstance(filters, dict) or not isinstance(scales, dict):
            raise ValueError('起身过程缺少动作倍率或滤波参数。')
        runtime = {'base_action_scale': scales.get('stand_test'),
                   'effective_action_scale_min': bus.get('active_action_scale'),
                   'effective_action_scale_max': bus.get('active_action_scale'),
                   'head_alpha': filters.get('head_lowpass'), 'legs_alpha': filters.get('legs_lowpass'),
                   'voltage_adapt': bus.get('voltage_adapt')}
        profiles.append({'model_sha256': model.get('sha256'), 'task': model.get('task'),
                         'joints': joints, 'runtime': runtime})
        active.append(frame)
        active_indices.append(frame_index)
    if not profiles:
        raise ValueError('记录中没有倒地起身老师正在运行的帧；请录下按LB后的过程。')
    first = profiles[0]
    fixed_keys = ('model_sha256', 'task', 'joints')
    fixed_runtime = ('base_action_scale', 'head_alpha', 'legs_alpha', 'voltage_adapt')
    if any(any(p[k] != first[k] for k in fixed_keys) or
           any(p['runtime'][k] != first['runtime'][k] for k in fixed_runtime) for p in profiles[1:]):
        raise ValueError('记录中的起身模型、标定或基础运行参数发生变化，请使用同一设置的一次记录。')
    scales = [_finite(p['runtime']['effective_action_scale_min'], '实际动作倍率') for p in profiles]
    runtime = dict(first['runtime'], effective_action_scale_min=min(scales), effective_action_scale_max=max(scales))
    start = {}
    try:
        start['recorded_start'] = _recorded_start(frames, active_indices[0], first)
    except ValueError as error:
        start['recorded_start_unavailable_reason'] = str(error)[:240]
    return validate_profile({
        'schema': SCHEMA, **{k: first[k] for k in fixed_keys}, 'runtime': runtime, 'seed': 20261007,
        **start,
        'recording': {'created_at': recording.get('created_at'),
                      'source_name': name.replace('\\', '/').rsplit('/', 1)[-1],
                      'source_sha256': hashlib.sha256(encoded).hexdigest(),
                      'frame_count': len(frames), 'active_frames': len(active),
                      'build': active[0]['bus'].get('build', '')}})

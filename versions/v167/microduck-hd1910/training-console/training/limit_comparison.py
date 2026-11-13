"""Automatic A/B target-limit evaluation using two freshly constructed worlds.

This module never trains, writes a robot, or edits the model.  The two groups
use identical seeds, model bytes, original action scale/filter, and mechanical
limits.  Only B applies the firmware target mapping.  Initial-state fingerprints
are compared before B takes an action; a mismatch invalidates the comparison.
"""
import copy
import hashlib
import inspect
import json
import math
from pathlib import Path
import random
import time

if __package__:
    from . import recovery_evaluation as recovery
    from . import target_limit_actions
    from . import recorded_start
    from .limit_comparison_request import validate_request
else:
    import recovery_evaluation as recovery
    import target_limit_actions
    import recorded_start
    from limit_comparison_request import validate_request


SCHEMA = 'microduck-target-limit-ab-v1'
MAX_STEPS = 300
_REFERENCE_KEYS = {'cfg', '_cfg', 'limit_profile', 'limit_enabled', 'limit_last'}
NUMERIC_COMPONENTS = frozenset(('integrator', 'live_physics'))
# MuJoCo reference-configuration aggregates, recomputed from physical inputs.
# They remain comparison gates, with an explicitly separate arithmetic tolerance.
DERIVED_PHYSICS_FIELDS = frozenset((
    'body_subtreemass', 'body_invweight0', 'dof_invweight0',
    'tendon_length0', 'tendon_invweight0',
))
COMPARISON_METHOD = 'fresh_env_same_seed_numeric_physics_exact_histories_v2'


def roll_degrees(gravity):
    """Log-roll about the spine; vertical posture is explicitly not a roll."""
    gx, gy, gz = [float(x) for x in gravity]
    if not all(math.isfinite(v) for v in (gx, gy, gz)):
        return None, False
    rho = math.hypot(gx, gy)
    if rho < 1e-6:
        return 0.0, False
    angle = math.degrees(math.atan2(abs(gy), -gx))
    return angle, bool(angle >= 90 and abs(gz) <= .5)


def _hash_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def _numeric_tree(root, *, blocked=(), max_depth=16, capture_values=False):
    """Hash nested numeric buffers without following environment backrefs.

    No tensor values are rounded. Pointer identities are never fingerprinted.
    Numeric buffers in BAM, DelayBuffer, EMA/history, and RNG objects are
    included. Unsupported opaque leaves are reported separately in coverage.
    """
    import numpy as np
    import torch
    result, opaque, truncated, numeric_values = {}, [], [], {}
    active = set()
    blocked = set(blocked)

    def walk(value, path, depth):
        if id(value) in blocked or inspect.isroutine(value) or inspect.isclass(value):
            return
        source_type = type(value).__module__ + '.' + type(value).__qualname__
        # mjlab's TorchArray proxies are not torch.Tensor instances. Their
        # _wp_array and _torch_stream contain allocation addresses, not physics
        # state. Unwrap the numeric tensor before considering object attributes.
        wrapped = getattr(value, '_tensor', None)
        tensor_proxy = (type(value).__name__ == 'TorchArray' or
                        (hasattr(value, '_wp_array') and hasattr(value, '_tensor')))
        if tensor_proxy:
            if not isinstance(wrapped, torch.Tensor):
                raise ValueError('不能读取TorchArray的真实数值张量，拒绝比较GPU指针。')
            value = wrapped
        if isinstance(value, torch.Tensor):
            array = value.detach().cpu().contiguous().numpy().copy()
            result[path] = {'shape': list(array.shape), 'dtype': str(array.dtype),
                            'sha256': hashlib.sha256(array.tobytes()).hexdigest(),
                            'source_type': source_type}
            if capture_values:
                numeric_values[path] = {**result[path], 'kind': array.dtype.kind,
                                        'values': array.reshape(-1).tolist()}
            return
        if isinstance(value, np.ndarray):
            if value.dtype.hasobject:
                opaque.append(path + ':object-array')
            else:
                array = np.ascontiguousarray(value).copy()
                result[path] = {'shape': list(array.shape), 'dtype': str(array.dtype),
                                'sha256': hashlib.sha256(array.tobytes()).hexdigest(),
                                'source_type': source_type}
                if capture_values:
                    numeric_values[path] = {**result[path], 'kind': array.dtype.kind,
                                            'values': array.reshape(-1).tolist()}
            return
        if isinstance(value, (np.bool_, np.integer, np.floating)):
            array = np.asarray(value).copy()
            result[path] = {'shape': [], 'dtype': str(array.dtype),
                            'sha256': hashlib.sha256(array.tobytes()).hexdigest(),
                            'source_type': source_type}
            if capture_values:
                numeric_values[path] = {**result[path], 'kind': array.dtype.kind,
                                        'values': [value.item()]}
            return
        if value is None or isinstance(value, (bool, int, str)):
            result[path] = value
            if capture_values and isinstance(value, (bool, int)):
                numeric_values[path] = {'shape': [], 'dtype': 'bool' if isinstance(value, bool) else 'python_int',
                                        'kind': 'b' if isinstance(value, bool) else 'i',
                                        'values': [value], 'source_type': source_type,
                                        'sha256': _hash_json(value)}
            return
        if isinstance(value, float):
            result[path] = value if math.isfinite(value) else str(value)
            if capture_values:
                numeric_values[path] = {'shape': [], 'dtype': 'float64', 'kind': 'f',
                                        'values': [value], 'source_type': source_type,
                                        'sha256': hashlib.sha256(value.hex().encode()).hexdigest()}
            return
        if isinstance(value, np.random.Generator):
            walk(value.bit_generator.state, path + '.rng_state', depth + 1)
            return
        if isinstance(value, np.random.RandomState):
            walk(value.get_state(), path + '.rng_state', depth + 1)
            return
        if isinstance(value, torch.Generator):
            walk(value.get_state(), path + '.rng_state', depth + 1)
            return
        if id(value) in active:
            return
        if depth > max_depth:
            truncated.append(path)
            return
        active.add(id(value))
        try:
            if isinstance(value, dict):
                for name, item in sorted(value.items(), key=lambda pair: str(pair[0])):
                    if str(name) not in _REFERENCE_KEYS:
                        walk(item, path + '.' + str(name), depth + 1)
            elif isinstance(value, (list, tuple)):
                for index, item in enumerate(value):
                    walk(item, path + '.' + str(index), depth + 1)
            elif hasattr(value, '__dict__'):
                walk(vars(value), path, depth + 1)
            else:
                opaque.append(path + ':' + type(value).__name__)
        finally:
            active.remove(id(value))

    walk(root, 'state', 0)
    return {'sha256': _hash_json(result), 'fields': result, 'numeric_values': numeric_values,
            'opaque_leaves': sorted(set(opaque)), 'truncated_paths': sorted(set(truncated))}


def _require_numeric_coverage(component, field_names, captured):
    """Every selected physics input must be an actual array/scalar snapshot."""
    missing = [name for name in field_names if 'state.' + name not in captured]
    if missing:
        raise ValueError('初态字段未能读取真实数值，不能只核对包装器属性：' +
                         ', '.join(component + '.' + name for name in missing))


def startup_fingerprint(env, obs, policy, *, numeric_snapshots=None):
    """Capture both sampled physical parameters and hidden initial buffers."""
    import numpy as np
    import torch
    raw = env.unwrapped
    robot = raw.scene['robot']
    blocked = {id(raw), id(raw.scene), id(raw.sim), id(raw.sim.model),
               id(raw.sim.data), id(robot), id(raw.sim.mj_model)}
    components = {}
    coverage = {}

    def add(name, value, *, exclude_refs=True):
        tree = _numeric_tree(value, blocked=blocked if exclude_refs else (),
                             capture_values=name in NUMERIC_COMPONENTS)
        components[name] = tree['sha256']
        coverage[name] = {'numeric_fields': len(tree['fields']),
                          'opaque_leaves': tree['opaque_leaves'],
                          'truncated_paths': tree['truncated_paths']}
        if name in NUMERIC_COMPONENTS:
            _require_numeric_coverage(name, value.keys(), tree['numeric_values'])
            if not tree['numeric_values']:
                raise ValueError('必须比较的物理数值字段未读取：' + name)
            # Python-only CPU snapshots are retained by the caller until B is
            # checked; raw arrays are deliberately absent from emitted JSON.
            if numeric_snapshots is not None:
                numeric_snapshots[name] = tree['numeric_values']
            coverage[name]['field_metadata'] = {
                path.removeprefix('state.'): {key: item[key] for key in ('shape', 'dtype', 'sha256', 'source_type')}
                for path, item in tree['numeric_values'].items()
            }
        return tree

    # The static compiled model includes collision geometries, constraints,
    # ranges and inertia. Live per-world DR fields are captured separately.
    compiled = {}
    for name in dir(raw.sim.mj_model):
        if name.startswith('_'):
            continue
        try:
            value = getattr(raw.sim.mj_model, name)
        except (AttributeError, RuntimeError):
            continue
        if isinstance(value, np.ndarray) and not value.dtype.hasobject:
            compiled[name] = value
        elif isinstance(value, (int, float)):
            compiled[name] = value
    add('compiled_model', compiled)

    physics_names = set(raw.event_manager.domain_randomization_fields)
    physics_names.update(('body_mass', 'body_inertia', 'body_ipos', 'body_iquat',
                          'geom_friction', 'jnt_range', 'dof_damping', 'dof_frictionloss', 'dof_armature'))
    physics = {name: getattr(raw.sim.model, name) for name in sorted(physics_names)}
    add('live_physics', physics)
    data_names = ('qpos', 'qvel', 'qacc', 'qacc_warmstart', 'act', 'ctrl',
                  'qfrc_applied', 'xfrc_applied', 'mocap_pos', 'mocap_quat', 'time', 'userdata')
    state, missing = {}, []
    for name in data_names:
        try:
            state[name] = getattr(raw.sim.data, name)
        except AttributeError:
            missing.append(name)
    add('integrator', state)
    coverage['integrator']['unavailable_optional_fields'] = missing
    if any(name not in state for name in ('qpos', 'qvel', 'qacc_warmstart', 'ctrl')):
        raise ValueError('无法核对积分器/求解器初态，本次对照取消。')

    add('encoder_bias', robot.data.encoder_bias)
    # Task-level DR (for example IMU mounting rotation) and previous-action
    # caches can live directly on env, outside managers and EntityData.
    env_buffers = {name: value for name, value in vars(raw).items()
                   if isinstance(value, (torch.Tensor, np.ndarray))}
    add('task_buffers', env_buffers)
    coverage['task_buffers']['field_names'] = sorted(env_buffers)

    actuators = getattr(robot, 'actuators', None)
    if not actuators:
        raise ValueError('无法核对BAM/延迟初始状态，本次对照取消。')
    actuator_tree = add('actuators', actuators)
    actuator_fields = actuator_tree['fields']
    required = {
        'bam_target_smoothing': any('q_target_smooth' in path and isinstance(value, dict)
                                    for path, value in actuator_fields.items()),
        'goal_reset_pending': any('_goal_reset_pending' in path and isinstance(value, dict)
                                   for path, value in actuator_fields.items()),
        'previous_motor_torque': any('_prev_motor_torque' in path and isinstance(value, dict)
                                      for path, value in actuator_fields.items()),
        'actuator_delay_state': any(('delay' in path.lower() or 'lag' in path.lower())
                                      and isinstance(value, dict)
                                    for path, value in actuator_fields.items()),
    }
    coverage['actuators']['required_buffers_verified'] = required
    if not all(required.values()):
        raise ValueError('BAM/延迟初态字段不受支持：' + ', '.join(key for key, value in required.items() if not value))
    add('action_history', raw.action_manager)
    add('observation_history', raw.observation_manager)
    add('commands', raw.command_manager)
    add('event_timers', raw.event_manager)
    add('initial_observation', obs)
    add('policy_recurrent_state', policy.states)
    rng = {'python': random.getstate(), 'numpy': np.random.get_state(),
           'torch_cpu': torch.get_rng_state()}
    if torch.cuda.is_available():
        rng['torch_cuda'] = torch.cuda.get_rng_state_all()
    add('rng', rng)
    # A silently truncated BAM/history walk is not evidence of equal states.
    if any(info['truncated_paths'] for info in coverage.values()):
        raise ValueError('初态摘要遍历深度不足，不能确认A/B公平性。')
    for name in ('compiled_model', 'live_physics', 'integrator', 'actuators',
                 'action_history', 'observation_history', 'initial_observation', 'encoder_bias'):
        if not coverage[name]['numeric_fields']:
            raise ValueError('必要初态字段未读取：' + name)
    return {'sha256': _hash_json(components), 'components': components, 'coverage': coverage,
            'method': COMPARISON_METHOD,
            'intentional_exclusions': ['treatment_limit_enabled', 'configuration_objects',
                                       'environment_backreferences', 'opaque_non_numeric_handles']}


def fingerprint_differences(left, right):
    a, b = left['components'], right['components']
    return [name for name in sorted(set(a) | set(b)) if a.get(name) != b.get(name)]


def field_tolerance(component, field):
    """Small, published tolerances in each field's native SI/model units."""
    name = field.removeprefix('state.')
    if component == 'live_physics':
        if name in DERIVED_PHYSICS_FIELDS:
            return 1e-8, 4e-6, 'derived_reference_physics'
        return 1e-10, 2e-6, 'physical_parameter'
    if name in ('qpos', 'mocap_pos', 'mocap_quat'):
        return 1e-7, 1e-6, 'initial_pose'
    if name == 'qacc':
        return 1e-8, 4e-6, 'derived_acceleration_diagnostic'
    return 1e-8, 1e-6, 'integrator_state'


def compare_numeric_field(component, path, left, right):
    """Compare saved plain-Python values without torch/numpy dependencies."""
    field = path.removeprefix('state.')
    atol, rtol, category = field_tolerance(component, field)
    row = {'component': component, 'field': field,
           'category': category, 'gating': not (component == 'integrator' and field == 'qacc'),
           'passed': False, 'exact': False, 'reason': '',
           'shape_a': left.get('shape') if left else None,
           'shape_b': right.get('shape') if right else None,
           'dtype_a': left.get('dtype') if left else None,
           'dtype_b': right.get('dtype') if right else None,
           'source_type_a': left.get('source_type') if left else None,
           'source_type_b': right.get('source_type') if right else None,
           'max_abs_diff': None, 'max_rel_diff': None,
           'atol': atol, 'rtol': rtol, 'finite_a': None, 'finite_b': None}
    if left is None or right is None:
        row.update(reason='missing_field', gating=True)
        return row
    if left['shape'] != right['shape'] or left['dtype'] != right['dtype']:
        row.update(reason='shape_or_dtype_mismatch', gating=True)
        return row
    av, bv = left.get('values'), right.get('values')
    if not isinstance(av, list) or not isinstance(bv, list) or len(av) != len(bv):
        row.update(reason='missing_or_invalid_values', gating=True)
        return row
    expected_size = math.prod(left['shape'])
    if len(av) != expected_size:
        row.update(reason='shape_value_count_mismatch', gating=True)
        return row
    if left.get('kind') not in ('b', 'i', 'u', 'f') or right.get('kind') != left.get('kind'):
        row.update(reason='unsupported_numeric_dtype', gating=True)
        return row
    row['finite_a'] = all(math.isfinite(value) for value in av)
    row['finite_b'] = all(math.isfinite(value) for value in bv)
    if not row['finite_a'] or not row['finite_b']:
        # A corrupt forward result is not legitimized merely because qacc is
        # normally diagnostic. All sampled physics values must be finite.
        row.update(reason='nonfinite_value', gating=True)
        return row
    integer = left['kind'] in ('b', 'i', 'u')
    if integer:
        row.update(atol=0.0, rtol=0.0)
    differences = [abs(a - b) for a, b in zip(av, bv)]
    relatives = [difference / max(abs(a), abs(b)) if a or b else 0.0
                 for a, b, difference in zip(av, bv, differences)]
    row['max_abs_diff'] = max(differences, default=0.0)
    row['max_rel_diff'] = max(relatives, default=0.0)
    row['exact'] = left.get('sha256') == right.get('sha256') if left.get('sha256') and right.get('sha256') else av == bv
    row['passed'] = (av == bv) if integer else all(
        difference <= atol + rtol * max(abs(a), abs(b))
        for a, b, difference in zip(av, bv, differences))
    row['reason'] = ('exact' if row['exact'] else 'within_tolerance') if row['passed'] else 'outside_tolerance'
    example = next((index for index, (a, b, difference) in enumerate(zip(av, bv, differences))
                    if (a != b if integer else difference > atol + rtol * max(abs(a), abs(b)))), None)
    if example is None:
        example = next((index for index, difference in enumerate(differences) if difference), None)
    if example is not None:
        row['example_difference'] = {
            'flat_index': example, 'a': av[example], 'b': bv[example],
            'abs_diff': differences[example],
            'allowed_diff': 0.0 if integer else atol + rtol * max(abs(av[example]), abs(bv[example])),
        }
    return row


def compare_initial_states(left, right, numeric_a=None, numeric_b=None):
    """Numeric gates for physics; exact gates for RNG, models and histories.

    Old digest-only records stay exact-only. A differing old hash can never be
    retroactively accepted without the missing numerical evidence.
    """
    fields = []
    a, b = left['components'], right['components']
    if not a or not b:
        fields.append({'component': 'snapshot', 'field': '*', 'gating': True,
                       'passed': False, 'exact': False, 'reason': 'empty_component_snapshot'})
    for component in sorted(set(a) | set(b)):
        snapshots_present = (numeric_a is not None and numeric_b is not None and
                             component in numeric_a and component in numeric_b)
        if component in NUMERIC_COMPONENTS and snapshots_present:
            aa, bb = numeric_a[component], numeric_b[component]
            for path in sorted(set(aa) | set(bb)):
                fields.append(compare_numeric_field(component, path, aa.get(path), bb.get(path)))
            if not aa or not bb:
                fields.append({'component': component, 'field': '*', 'gating': True,
                               'passed': False, 'exact': False, 'reason': 'empty_numeric_snapshot'})
        else:
            present = component in a and component in b
            passed = present and a[component] == b[component]
            fields.append({'component': component, 'field': '*', 'gating': True,
                           'passed': passed, 'exact': passed,
                           'reason': 'exact_component_digest' if passed else
                                     ('missing_numeric_snapshot' if component in NUMERIC_COMPONENTS else 'component_digest_mismatch'),
                           'atol': 0.0, 'rtol': 0.0, 'max_abs_diff': None, 'max_rel_diff': None,
                           'shape_a': None, 'shape_b': None, 'dtype_a': None, 'dtype_b': None,
                           'finite_a': None, 'finite_b': None})
    differences = [row for row in fields if row['gating'] and not row['passed']]
    return {'method': COMPARISON_METHOD, 'passed': not differences,
            'exact': not fingerprint_differences(left, right),
            'fields': fields, 'differences': differences,
            'derived_physics_fields': sorted(DERIVED_PHYSICS_FIELDS),
            'diagnostic_only_fields': ['integrator.qacc'],
            'formula': 'abs(a-b) <= atol + rtol * max(abs(a), abs(b))',
            'exact_components': sorted((set(a) | set(b)) - NUMERIC_COMPONENTS)}


def _seed_everything(seed):
    import numpy as np
    import torch
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _build_group(req, profile, label):
    import torch
    from mjlab.envs import ManagerBasedRlEnv
    from mjlab.rl import RslRlVecEnvWrapper
    from mjlab.tasks.registry import load_env_cfg, load_rl_cfg
    if __package__:
        from .runtime_adapter import apply_env, apply_agent, apply_recipe, configure_evaluation_events
        from .sim_protocol import OnnxPolicy
        from .action_filter import describe
    else:
        from runtime_adapter import apply_env, apply_agent, apply_recipe, configure_evaluation_events
        from sim_protocol import OnnxPolicy
        from action_filter import describe

    _seed_everything(profile['seed'])
    request = copy.deepcopy(req)
    request.update(recovery_evaluation=True, eval_pushes=False)
    request['target_limit_comparison'] = copy.deepcopy(profile)
    parameters = request.get('policy_parameters', {})
    cfg = apply_env(load_env_cfg(request['task'], play=True), parameters)
    agent = apply_agent(load_rl_cfg(request['task']), parameters)
    apply_recipe(cfg, agent, request)
    cfg.scene.num_envs = 1
    cfg.seed = profile['seed']
    cfg.auto_reset = False  # A terminal pose is never replaced before recording.
    cfg.episode_length_s = 6.0
    configure_evaluation_events(cfg, request)
    recovery.prepare_config(cfg, request)
    source_action = {'scale': cfg.actions['joint_pos'].scale,
                     'filter': describe(cfg.actions['joint_pos']),
                     'clip_actions': agent.clip_actions}
    target_limit_actions.configure(cfg, profile, enabled=label == 'B')
    device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
    raw = ManagerBasedRlEnv(cfg=cfg, device=device)
    env = None
    try:
        env = RslRlVecEnvWrapper(raw, clip_actions=agent.clip_actions)
        # GUI-free command enforcement after each original command compute.
        for name in ('twist', 'head_pose', 'body_pose'):
            if name not in raw.command_manager.active_terms:
                continue
            term = raw.command_manager.get_term(name)
            original = term.compute
            def neutral(dt, _term=term, _original=original):
                _original(dt)
                _term.command.zero_()
            term.compute = neutral
        recovery.zero_commands(raw, freeze_ranges=True)
        obs = env.get_observations()
        groups = agent.obs_groups['actor']
        if any(obs[key].ndim != 2 for key in groups):
            raise ValueError('目标限幅对照只支持向量观测。')
        policy = OnnxPolicy(Path(req['onnx_path']), sum(obs[g].shape[-1] for g in groups),
                            env.num_actions, groups, env.device)
        policy(obs)
        policy.reset()
        return env, policy, obs, source_action
    except BaseException:
        (env if env is not None else raw).close()
        raise


def actual_joint_positions(names, all_names, joint_positions, encoder_bias, *, backlash_expected):
    """Read-only named pairing; never call actuator.compute/get_command here."""
    indices = {name: index for index, name in enumerate(all_names)}
    if len(indices) != len(all_names) or any(name not in indices for name in names):
        raise ValueError('关节实际位置名称缺失或重复。')
    passive_names = ['passive_' + name + '_backlash' for name in names]
    matches = sum(name in indices for name in passive_names)
    if matches != (14 if backlash_expected else 0):
        raise ValueError('背隙关节配对不完整或与所选任务不符：%s/14。' % matches)
    motor = [float(joint_positions[indices[name]]) for name in names]
    passive = [float(joint_positions[indices[name]]) if backlash_expected else 0.0
               for name in passive_names]
    bias = [float(encoder_bias[indices[name]]) for name in names]
    output = [value + gear for value, gear in zip(motor, passive)]
    encoder = [value + offset for value, offset in zip(output, bias)]
    return motor, output, encoder, bias


def _trace_frame(raw, profile, step):
    term = raw.action_manager.get_term('joint_pos')
    names = list(term.target_names)
    mapped = term.limit_last
    if mapped is None:
        raise ValueError('限幅动作管线没有产生目标记录。')
    robot = raw.scene['robot']
    motor, output, actual, bias = actual_joint_positions(
        names, list(robot.joint_names), robot.data.joint_pos[0].detach().cpu().tolist(),
        robot.data.encoder_bias[0].detach().cpu().tolist(),
        backlash_expected='-Backlash-' in profile['task'])
    gravity = robot.data.projected_gravity_b[0].detach().cpu().tolist()
    gyro = robot.data.root_link_ang_vel_b[0].detach().cpu().tolist()
    roll, side = roll_degrees(gravity)
    servo21 = next(joint['name'] for joint in profile['joints'] if joint['id'] == 21)
    index21 = names.index(servo21)
    clipped = [item['safety_clipped'] or item['calibration_clipped'] for item in mapped]
    values = {
        't_s': step * raw.step_dt, 'roll_deg': roll, 'reached_side': side,
        'gravity_b': gravity, 'gyro_rad_s': gyro,
        'height_m': float(robot.data.root_link_pos_w[0, 2] - raw.scene.env_origins[0, 2]),
        'joint21_target_before_rad': mapped[index21]['target_before_rad'],
        'joint21_target_after_rad': mapped[index21]['target_applied_rad'],
        'joint21_actual_rad': actual[index21], 'joint21_clamped': clipped[index21],
        'joint21_actual_motor_rad': motor[index21],
        'joint21_actual_output_rad': output[index21],
        'joint21_actual_encoder_rad': actual[index21],
        'joint21_encoder_bias_rad': bias[index21],
        'joint21_would_clamp': bool(mapped[index21]['would_safety_clip'] or mapped[index21]['would_calibration_clip']),
        'raw_action': raw.action_manager.action[0].detach().cpu().tolist(),
        'target_before_rad': [item['target_before_rad'] for item in mapped],
        'target_applied_rad': [item['target_applied_rad'] for item in mapped],
        'encoder_raw_if_limited': [item['encoder_raw'] for item in mapped],
        'actual_rad': actual, 'actual_motor_rad': motor, 'actual_output_rad': output,
        'actual_encoder_rad': actual,
        'encoder_bias_rad': bias, 'joint_names': names,
        'actual_measurement': 'output_encoder: motor + passive_backlash + simulated_encoder_bias',
        'safety_clipped': [item['safety_clipped'] for item in mapped],
        'calibration_clipped': [item['calibration_clipped'] for item in mapped],
        'clamp_joint_count': sum(clipped),
    }
    return values


def _run_group(req, profile, label, emit, expected_fingerprint=None, *,
               expected_numeric=None, numeric_out=None):
    env, policy, obs, source_action = _build_group(req, profile, label)
    raw = env.unwrapped
    result = {'label': label, 'status': 'running', 'steps': 0, 'elapsed_s': 0.0,
              'max_roll_deg': 0.0, 'reached_side': False, 'joint21_clamp_steps': 0,
              'joint21_would_clamp_steps': 0, 'clamp_joint_steps': 0,
              'action_mapping': source_action, 'trace': [], 'error': None}
    trial = recovery.TrialRecorder(recovery.stand_height(raw))
    trial.start('back_flat')
    try:
        emit('log', line='[目标限幅%s组] 同模型动作系数=%s；头颈/腿EMA=%s/%s；'
             '不启用实机电压动作倍率补偿（记录范围=%s..%s）；仅B应用命令限幅与编码器取整。' %
             (label, source_action['scale'], source_action['filter']['head_alpha'],
              source_action['filter']['legs_alpha'], profile['runtime']['effective_action_scale_min'],
              profile['runtime']['effective_action_scale_max']))
        if req.get('target_limit_start_mode', 'standard') == 'recorded':
            check = recorded_start.verify_pose(raw, profile['recorded_start'],
                                               backlash_expected='Backlash' in req['task'])
            result['recorded_start_check'] = check
            if not check['passed']:
                result.update(status='invalid', error=check['reason'])
                trial.finish('cancelled', check['reason'])
                result['stand'] = copy.deepcopy(trial.current)
                return result
        numeric = {}
        fingerprint = startup_fingerprint(env, obs, policy, numeric_snapshots=numeric)
        if numeric_out is not None:
            numeric_out.update(numeric)
        result['initial_fingerprint'] = fingerprint
        comparison = (compare_initial_states(expected_fingerprint, fingerprint,
                                             expected_numeric, numeric)
                      if expected_fingerprint else None)
        self_check = compare_initial_states(fingerprint, fingerprint, numeric, numeric)
        if not self_check['passed']:
            comparison = self_check
        result['initial_state_comparison'] = comparison
        result['initial_state_differences'] = comparison['differences'] if comparison else []
        result['initial_state_exact'] = comparison['exact'] if comparison else None
        differences = sorted({row['component'] for row in result['initial_state_differences']})
        result['initial_state_mismatches'] = differences
        if differences:
            failed_fields = [row['component'] + '.' + row['field']
                             for row in result['initial_state_differences']]
            result.update(status='invalid', error=label + '组未运行：初态核对未通过：' + ', '.join(failed_fields[:8]))
            trial.finish('cancelled', result['error'])
            result['stand'] = copy.deepcopy(trial.current)
            return result
        if abs(raw.step_dt - .02) > 1e-9:
            raise ValueError('目标限幅对照要求50Hz控制周期。')
        for step in range(1, MAX_STEPS + 1):
            actions = policy(obs)
            obs, _, _, _ = env.step(actions)
            terminated = bool(raw.reset_terminated[0])
            timed_out = bool(raw.reset_time_outs[0])
            result['steps'] = step
            result['elapsed_s'] = step * raw.step_dt
            # With auto_reset=False these are still the terminal physical state.
            # Guard again if an incompatible engine unexpectedly auto-resets.
            if raw.cfg.auto_reset and (terminated or timed_out):
                trial.observe(raw.step_dt, terminated=terminated, timed_out=timed_out)
                break
            frame = _trace_frame(raw, profile, step)
            result['trace'].append(frame)
            if frame['roll_deg'] is not None and abs(frame['gravity_b'][2]) <= .5:
                result['max_roll_deg'] = max(result['max_roll_deg'], frame['roll_deg'])
            result['reached_side'] |= frame['reached_side']
            result['joint21_clamp_steps'] += int(frame['joint21_clamped'])
            result['joint21_would_clamp_steps'] += int(frame['joint21_would_clamp'])
            result['clamp_joint_steps'] += frame['clamp_joint_count']
            finished = trial.observe(raw.step_dt, height=frame['height_m'],
                                     gravity_z=frame['gravity_b'][2],
                                     terminated=terminated, timed_out=timed_out)
            if step == 1 or step % 10 == 0 or finished:
                emit('limit_comparison_state', data={'phase': 'running', 'group': label,
                     'step': step, 'total_steps': MAX_STEPS, 'elapsed_s': result['elapsed_s'],
                     'seed': profile['seed'], 'message': '%s组检查中' % label})
            if finished:
                break
        if trial.current['result'] == 'running':
            trial.finish('failed', '6秒内未达到连续1秒站起标准')
        result['stand'] = copy.deepcopy(trial.current)
        result['status'] = trial.current['result']
        return result
    except Exception as error:
        trial.finish('cancelled', '仿真/记录错误：' + str(error))
        result.update(status='error', error=str(error), stand=copy.deepcopy(trial.current))
        return result
    finally:
        env.close()


def _finite_json(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _finite_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_finite_json(item) for item in value]
    return value


def _configure_backends():
    from mjlab.utils.torch import configure_torch_backends
    configure_torch_backends()


def run(req, emit):
    """Run A then B automatically. Emits a downloadable structured result."""
    if __package__:
        from .target_limit_profile import validate_profile
    else:
        from target_limit_profile import validate_profile
    if req.get('op') != 'onnx' or not recovery.eligible(req):
        raise ValueError('目标限幅对照仅适用于ONNX倒地老师评估。')
    path = Path(req['onnx_path'])
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != req['onnx_sha256']:
        raise ValueError('ONNX文件已变化，不能开始限幅对照。')
    profile = validate_profile(req['target_limit_comparison'], expected_sha=digest,
                               expected_task=req['task'])
    start_mode = validate_request(req, profile=profile)
    result = {'schema': SCHEMA, 'created_at_unix': time.time(),
              'model': {'sha256': digest, 'filename': path.name, 'task': req['task']},
              'seed': profile['seed'], 'profile': profile, 'valid': False,
              'initial_state_equal': False, 'initial_state_exact': None,
              'initial_state_method': COMPARISON_METHOD,
              'initial_state_comparison': None, 'initial_state_differences': [],
              'initial_state_mismatches': [], 'groups': [],
              'mechanical_limits_changed': False, 'voltage_compensation_enabled': False,
              'start_mode': start_mode,
              'start_pose': ('shared_recorded_encoder_gravity_static_pose_not_trajectory_replay'
                             if start_mode == 'recorded' else 'shared_supine_HOME_reset_not_recorded_real_trajectory'),
              'comparison_scope': 'only_target_safety_calibration_clip_and_encoder_roundtrip',
              'criterion': {'max_seconds': 6, 'stand_hold_s': recovery.HOLD_SECONDS,
                            'stand_max_tilt_deg': recovery.MAX_TILT_DEG,
                            'side_angle_deg': 90, 'side_max_abs_gravity_z': .5},
              'error': None}
    try:
        _configure_backends()
        snapshots = {}
        for label in ('A', 'B'):
            emit('limit_comparison_state', data={'phase': 'starting', 'group': label,
                 'step': 0, 'total_steps': MAX_STEPS, 'elapsed_s': 0.0,
                 'seed': profile['seed'], 'message': '新建%s组独立环境与策略' % label})
            # Bind both groups to exactly the same model bytes, including B's
            # load after A has completed; never silently follow a replaced file.
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise ValueError('A/B期间ONNX文件发生变化，比较无效。')
            expected = result['groups'][0]['initial_fingerprint'] if label == 'B' else None
            numeric = {}
            try:
                group = _run_group(req, profile, label, emit, expected,
                                   expected_numeric=snapshots.get('A'), numeric_out=numeric)
            except Exception as error:
                # Environment/policy construction precedes _run_group's trial
                # handler. Preserve the current group and zero executed steps
                # so initialization errors cannot look like physical failures.
                group = {'label': label, 'status': 'error', 'steps': 0,
                         'elapsed_s': 0.0, 'trace': [], 'error': str(error),
                         'initial_state_mismatches': []}
            snapshots[label] = numeric
            result['groups'].append(group)
            if group['status'] in ('error', 'invalid'):
                result['error'] = group.get('error')
                result['initial_state_mismatches'] = group.get('initial_state_mismatches', [])
                break
        if len(result['groups']) == 2 and all(group.get('initial_fingerprint') for group in result['groups']):
            check = result['groups'][1].get('initial_state_comparison') or compare_initial_states(
                result['groups'][0]['initial_fingerprint'], result['groups'][1]['initial_fingerprint'],
                snapshots.get('A'), snapshots.get('B'))
            result['initial_state_comparison'] = check
            result['initial_state_differences'] = check['differences']
            result['initial_state_mismatches'] = sorted({row['component'] for row in check['differences']})
            result['initial_state_equal'] = check['passed']
            result['initial_state_exact'] = check['exact']
            result['valid'] = result['initial_state_equal'] and not result['error']
    except Exception as error:
        result['error'] = str(error)
    result = _finite_json(result)
    emit('limit_comparison_result', data=result)
    emit('limit_comparison_state', data={'phase': 'completed' if result['valid'] else 'invalid',
         'group': None, 'step': MAX_STEPS, 'total_steps': MAX_STEPS,
         'elapsed_s': sum(group['elapsed_s'] for group in result['groups']),
         'seed': profile['seed'], 'message': 'A/B完成' if result['valid'] else result['error'] or '初态不匹配'})
    return result

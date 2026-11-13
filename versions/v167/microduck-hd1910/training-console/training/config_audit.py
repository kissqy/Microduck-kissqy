"""Audit resolved/compiled training facts without changing the recipe.

No training-engine import is needed. Numeric tuning stays editable; structural
mapping errors fail strict mode. A passing report is not a simulation-step test
or a guarantee that a learned policy will work on the real robot.
"""
import copy
import math
import re

try:
    from .official_spec import OBSERVATIONS, RUNTIME_HOME, RUNTIME_JOINTS
except ImportError:
    from official_spec import OBSERVATIONS, RUNTIME_HOME, RUNTIME_JOINTS


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _json_safe(value):
    """Keep rejected non-finite input visible in strict-JSON error reports."""
    if isinstance(value, float) and not math.isfinite(value):
        return {'non_finite': str(value)}
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _function(term):
    value = (term or {}).get('func', {})
    return value.get('callable', '').rsplit('.', 1)[-1] if isinstance(value, dict) else ''


def _at(tree, path):
    try:
        for part in path:
            tree = tree[int(part)] if isinstance(tree, list) else tree[part]
        return copy.deepcopy(tree)
    except (KeyError, IndexError, TypeError, ValueError):
        return {'unresolved_path': True}


def _select(patterns, names, preserve=False):
    if patterns is None:
        return list(names)
    if isinstance(patterns, str):
        patterns = [patterns]
    if not isinstance(patterns, (list, tuple)):
        raise ValueError('关节选择器必须是名称或正则表达式列表。')
    matches = [[name for name in names if re.fullmatch(pattern, name)] for pattern in patterns]
    if any(not row for row in matches):
        raise ValueError('关节选择器没有匹配到实际模型。')
    return list(dict.fromkeys(name for row in matches for name in row)) if preserve else [
        name for name in names if any(name in row for row in matches)]


def audit_configuration(task, inspection, request=None, strict=True):
    """Return JSON-compatible evidence; strict structural failures raise ValueError.

    ``inspection`` is recipe.inspect_configs output. The report distinguishes
    XML geometry from Entity-compiled contacts and configured DR from sampled
    per-environment values. It never treats BAM friction as ground friction.
    """
    request = request or {}
    errors, warnings = [], []
    def issue(code, message, path='', severity='error'):
        (errors if severity == 'error' else warnings).append(
            {'code': code, 'message': message, 'path': path})
    if not isinstance(inspection, dict):
        raise ValueError('配置审计需要实际检查结果。')
    full = inspection.get('full') or {}
    env, agent = full.get('env') or {}, full.get('agent') or {}
    model = inspection.get('model') or {}
    compiled = model.get('entity_compiled') or {}
    if not full or not model or compiled.get('nu') != 14:
        issue('compiled_action_count', '需要 Entity 编译后恰好14个主动执行器。', 'model.entity_compiled.nu')
    if inspection.get('task') not in (None, task):
        issue('task_mismatch', '检查结果的任务与请求任务不同。', 'task')
    joints = model.get('joints') or []
    active = [j for j in joints if j.get('type') == 3 and not j.get('name', '').startswith('passive_')]
    names = [j.get('name') for j in active]
    if names != RUNTIME_JOINTS:
        issue('joint_order', '实际主动关节顺序与14关节运行协议不一致。', 'model.joints')
    homes = [j.get('home_rad') for j in active]
    home_matches = len(homes) == len(RUNTIME_HOME) and all(
        _finite(a) and abs(a-b) <= 1e-7 for a, b in zip(homes, RUNTIME_HOME))
    if not home_matches:
        issue('home_runtime_difference', 'Home 与0.15.1运行参考不同；保留编辑值，但不能视为直接部署兼容。',
              'model.joints.home_rad', 'warning')
    for j in joints:
        name = j.get('name', '?')
        if not _finite(j.get('home_rad')):
            issue('invalid_home', '关节Home必须为有限数值：'+name, 'model.joints')
        limits = j.get('range', [])
        if j.get('limited') and (len(limits) != 2 or not all(map(_finite, limits)) or limits[0] >= limits[1]):
            issue('invalid_joint_range', '关节限位必须为有限且递增的区间：'+name, 'model.joints')
    dt = (env.get('sim') or {}).get('mujoco', {}).get('timestep')
    decimation = env.get('decimation')
    hz = 1/(dt*decimation) if _finite(dt) and dt > 0 and type(decimation) is int and decimation > 0 else None
    if hz is None or abs(hz-50) > 1e-6:
        issue('control_frequency', '实际控制频率必须对应0.15.1的50Hz。', 'full.env.sim/decimation')
    obs = (env.get('observations') or {}).get('actor') or {}
    terms = obs.get('terms') or {}
    if list(terms) != OBSERVATIONS or obs.get('history_length') not in (None, 0) or any(
            t.get('history_length') not in (None, 0) for t in terms.values()):
        issue('actor_layout', 'actor必须保持既有61维项顺序，不能额外堆叠历史。', 'full.env.observations.actor')
    allowed = {
        'base_ang_vel': {'base_ang_vel', 'base_ang_vel_imu_misaligned'},
        'projected_gravity': {'projected_gravity', 'projected_gravity_imu_misaligned'},
        'joint_pos': {'joint_pos_rel', 'joint_pos_rel_backlash'},
        'joint_vel': {'joint_vel_rel', 'joint_vel_rel_backlash'},
        'actions': {'last_action'},
    }
    for name, functions in allowed.items():
        if _function(terms.get(name)) not in functions:
            issue('actor_semantics', 'actor观测语义不匹配：'+name, 'full.env.observations.actor.terms.'+name)
    all_hinges = [j['name'] for j in joints if j.get('type') == 3]
    for name in ('joint_pos', 'joint_vel'):
        term = terms.get(name) or {};asset = (term.get('params') or {}).get('asset_cfg') or {}
        try:
            selected = _select(asset.get('joint_names'), all_hinges, asset.get('preserve_order', False))
            ids = asset.get('joint_ids')
            if isinstance(ids, list):
                selected = [all_hinges[i] for i in ids]
            elif isinstance(ids, dict) and ids.get('slice') != [None, None, None]:
                selected = all_hinges[slice(*ids['slice'])]
            if selected != RUNTIME_JOINTS:
                issue('actor_joint_mapping', 'actor关节观测必须只选14个主动关节且顺序一致。', name)
        except (ValueError, TypeError, IndexError, re.error):
            issue('actor_joint_mapping', 'actor关节选择器不能映射到实际14关节。', name)
    for name, command, dim in [('command', 'twist', 3), ('head_command', 'head_pose', 4), ('body_command', 'body_pose', 6)]:
        term = terms.get(name) or {};params = term.get('params') or {};func = _function(term)
        generated = func == 'generated_commands' and params.get('command_name') == command and command in (env.get('commands') or {})
        padding = name != 'command' and func == 'zero_command_padding' and params.get('dim') == dim
        if not (generated or padding):
            issue('command_mapping', '指令观测的来源或维度不符合部署布局：'+name, name)
    action = (env.get('actions') or {}).get('joint_pos') or {}
    if list(env.get('actions') or {}) != ['joint_pos'] or not action.get('use_default_offset') or not _finite(action.get('scale')) or action['scale'] <= 0:
        issue('action_mapping', '动作必须为Home加正有限标量系数乘原始14维动作。', 'full.env.actions')
    if action.get('clip') is not None or agent.get('clip_actions') is not None or action.get('offset', 0) != 0:
        issue('action_clipping_or_offset', '额外动作裁剪或偏移与既有运行映射不同。', 'full.env.actions.joint_pos')
    backlash = [j for j in joints if j.get('name', '').startswith('passive_') and j['name'].endswith('_backlash')]
    expects_backlash = '-Backlash-' in task
    if bool(backlash) != expects_backlash:
        issue('backlash_model', '任务齿隙标识与真实模型不一致。', 'model.joints')
    if expects_backlash:
        expected = {'passive_'+n+'_backlash' for n in RUNTIME_JOINTS}
        if {j['name'] for j in backlash} != expected:
            issue('backlash_joint_count', '齿隙模型必须逐个覆盖14个主动关节。', 'model.joints')
        for j in backlash:
            r = j.get('range', [])
            if len(r) != 2 or not all(_finite(v) for v in r) or any(abs(a-b) > 1e-6 for a,b in zip(r, (-math.pi/180, math.pi/180))):
                issue('backlash_range', '此官方Backlash任务要求每轴±1°齿隙：'+j['name'], 'model.joints')
        if any('backlash' not in _function(terms.get(k)) for k in ('joint_pos', 'joint_vel')):
            issue('backlash_encoder', '齿隙模型必须使用穿过齿隙的编码器观测。', 'full.env.observations.actor')
    rollers = any(x in task for x in ('Rollers', 'Roller', 'Swizzle', 'Spin'))
    wheels = [j for j in joints if j.get('type') == 3 and j.get('name', '').startswith('passive_') and 'wheel' in j['name']]
    if rollers and not wheels:
        issue('missing_wheels', '轮滑任务的实际模型没有被动轮轴。', 'model.joints')
    actuators = model.get('actuators') or []
    selected_actuators = []
    if not actuators:
        issue('missing_actuator_evidence', '检查结果缺少实际执行器证据。', 'model.actuators')
    for i, a in enumerate(actuators):
        try:
            selected = _select(a.get('target_names_expr'), all_hinges)
            selected_actuators.extend(selected)
            if any(n.startswith('passive_') for n in selected):
                issue('passive_actuated', '被动轮轴/齿隙不能被BAM执行器驱动。', f'model.actuators.{i}')
        except (ValueError, TypeError, re.error):
            issue('actuator_selector', '执行器选择器无法解析。', f'model.actuators.{i}')
        for key in ('kp_fw', 'vin_min'):
            if a.get(key) is not None and (not _finite(a[key]) or a[key] <= 0):
                issue('invalid_actuator_value', key+'必须为正有限值。', f'model.actuators.{i}.{key}')
        for key in ('vin_range', 'vin_drop_gain_range'):
            r = a.get(key)
            if r is not None and (len(r) != 2 or not all(map(_finite,r)) or r[0] > r[1] or r[0] < 0 or (key=='vin_range' and r[0] == 0)):
                issue('invalid_actuator_range', key+'区间无效。', f'model.actuators.{i}.{key}')
        lo, hi = a.get('delay_min_lag', 0), a.get('delay_max_lag', 0)
        if type(lo) is not int or type(hi) is not int or not 0 <= lo <= hi:
            issue('invalid_delay', '执行器延迟必须是非负且递增的整数区间。', f'model.actuators.{i}')
        if expects_backlash and 'backlash' not in str(a.get('implementation', '')).lower():
            issue('backlash_actuator_feedback', '齿隙模型必须使用穿过齿隙反馈的执行器实现。', f'model.actuators.{i}')
    if selected_actuators != RUNTIME_JOINTS:
        issue('actuator_joint_mapping', '执行器目标必须恰好覆盖14个主动关节且顺序一致。', 'model.actuators')
    for joint in compiled.get('joints', []):
        for field in ('armature', 'damping', 'frictionloss'):
            value = joint.get(field)
            if not _finite(value) or value < 0:
                issue('invalid_joint_dynamics', '编译后的关节惯量/阻尼/摩擦必须非负有限。', 'model.entity_compiled.joints')
    for geom in compiled.get('geoms', []):
        friction = geom.get('friction', [])
        if len(friction) != 3 or any(not _finite(v) or v < 0 for v in friction):
            issue('invalid_contact_friction', '接触摩擦必须是3个非负有限分量。', 'model.entity_compiled.geoms')
    bodies = model.get('bodies') or []
    if bodies:
        mass = model.get('total_mass_kg')
        if not _finite(mass) or mass <= 0:
            issue('invalid_robot_mass', '机器人总质量必须是正有限值。', 'model.total_mass_kg')
        for body in bodies:
            inertia = body.get('inertia', [])
            if not _finite(body.get('mass_kg')) or body['mass_kg'] < 0 or len(inertia) != 3 or any(
                    not _finite(v) or v < 0 for v in inertia):
                issue('invalid_body_inertia', '刚体质量和主惯量必须是非负有限值。', 'model.bodies')
    events = env.get('events') or {}
    contact_dr, motor_dr = {}, {}
    for name, term in events.items():
        func = _function(term)
        if func == 'geom_friction':
            value = copy.deepcopy(term);value['effective_axes'] = value.get('params', {}).get('axes', [0])
            value['component_names'] = ['sliding', 'torsional', 'rolling']
            value['sampled_values_available'] = False
            contact_dr[name] = value
        elif 'friction' in func and 'bam' in func:
            motor_dr[name] = copy.deepcopy(term)
        if func in ('geom_friction', 'randomize_bam_friction'):
            params = term.get('params') or {}
            ranges = params.get('scale_range') if func == 'randomize_bam_friction' else params.get('ranges')
            ranges = list(ranges.values()) if isinstance(ranges, dict) else [ranges]
            for bounds in ranges:
                if not isinstance(bounds, (list, tuple)) or len(bounds) != 2 or not all(map(_finite, bounds)) or not 0 <= bounds[0] <= bounds[1]:
                    issue('invalid_friction_randomization', '摩擦随机化区间必须非负、有限且递增。', 'full.env.events.'+name)
    for name, reward in (env.get('rewards') or {}).items():
        if not _finite(reward.get('weight')):
            issue('invalid_reward_weight', '奖励权重必须为有限值。', 'full.env.rewards.'+name)
        if _function(reward) in ('pose_target_match', 'pose_l1_penalty', 'standing_composite_score'):
            indices = (reward.get('params') or {}).get('joint_indices')
            if indices is not None and (not isinstance(indices, (list, tuple)) or any(type(i) is not int or not 0 <= i < 14 for i in indices)):
                issue('servo_reward_index', '奖励函数使用14主动关节坐标，索引不能包含轮轴槽位或超过13。', 'full.env.rewards.'+name)
    recipe = request.get('studio_recipe') or {}
    overrides = []
    for item in (recipe.get('task_overrides') or {}).get(task, []):
        path = item.get('path', []);actual = _at(full, path)
        overrides.append({'path': copy.deepcopy(path), 'requested': copy.deepcopy(item.get('value')),
                          'resolved': actual, 'matches': actual == item.get('value')})
    terrain = (env.get('scene') or {}).get('terrain') or {}
    terrain_note = None
    if '-Rough-' in task:
        terrain_note = {'upstream_declaration': {'num_rows': 10, 'num_cols': 20, 'curriculum': False},
                        'upstream_registry_observed': {'num_rows': 5, 'num_cols': 5, 'curriculum': False},
                        'cause': 'upstream train/play factories share a generator; play changes rows/cols in place',
                        'scope': '8d0db749 and 273afe0b; declaration and observed values are evidence, not enforced defaults',
                        'note': 'generator.curriculum=False is already the mjlab default; terrain_levels is a separate environment curriculum'}
    if any(_function(v)=='randomize_bam_friction' for v in events.values()) and 'expand_bam_friction_fields' not in events:
        issue('bam_field_expansion', '配置有BAM摩擦随机化但没有显式字段展开事件，需实际环境步进验证。', 'full.env.events', 'warning')
    report = {
        'schema': 'microduck-training-config-audit/v1', 'task': task,
        'inspection_sha256': inspection.get('sha256'), 'passed': not errors,
        'runtime_structure_compatible': not errors and home_matches,
        'errors': errors, 'warnings': warnings,
        'joint_mapping': {'order': names, 'home_rad': homes, 'runtime_home_matches': home_matches,
                          'limits_and_axes': copy.deepcopy(active), 'compiled_nu': compiled.get('nu'),
                          'evidence': 'compiled joint order and actuator selectors; inspection does not expose actuator transmission ids'},
        'timing': {'physics_dt_s': dt, 'decimation': decimation, 'control_hz': hz,
                   'episode_length_s': env.get('episode_length_s')},
        'observations': copy.deepcopy(obs), 'commands': copy.deepcopy(env.get('commands', {})),
        'actions': copy.deepcopy(env.get('actions', {})),
        'backlash': {'required': expects_backlash, 'joints': copy.deepcopy(backlash)},
        'rollers': {'required': rollers, 'passive_wheels': copy.deepcopy(wheels)},
        'contact_friction': {'configured_randomization': contact_dr,
                             'entity_compiled_geoms': copy.deepcopy(compiled.get('geoms', [])),
                             'xml_geometry': copy.deepcopy(model.get('collision_geoms', [])),
                             'note': 'before per-world startup/reset DR; condim 3 supports sliding, 4 adds torsion, 6 adds rolling'},
        'bam_motor_friction': {'configured_randomization': motor_dr, 'actuators': copy.deepcopy(actuators),
                               'compiled_joint_dynamics': copy.deepcopy(compiled.get('joints', [])),
                               'note': 'internal motor friction and back-EMF are distinct from foot/ground contact friction'},
        'body_physics': {'total_mass_kg': model.get('total_mass_kg'), 'bodies': copy.deepcopy(bodies),
                         'collision_overrides': copy.deepcopy(model.get('collision_overrides', [])),
                         'initial_state': copy.deepcopy((env.get('scene') or {}).get('entities', {}).get('robot', {}).get('init_state', {})),
                         'note': 'configured mass/inertia before per-world startup/reset DR; does not identify every effective contact pair'},
        'simulation': copy.deepcopy(env.get('sim', {})),
        'optimization': copy.deepcopy(agent),
        'terrain': {'effective': copy.deepcopy(terrain), 'declared_vs_registry': terrain_note},
        'curricula': copy.deepcopy(env.get('curriculum', {})),
        'reset_and_events': copy.deepcopy(events), 'terminations': copy.deepcopy(env.get('terminations', {})),
        'rewards': copy.deepcopy(env.get('rewards', {})),
        'requested_overrides': overrides, 'requested_robot_changes': copy.deepcopy(recipe.get('robot', {})),
        'requested_execution': {k: copy.deepcopy(request[k]) for k in
                                ('training_action_scale', 'training_firmware_p', 'action_filter') if k in request},
        'validation_scope': 'configuration and Entity compilation only; no reset/step/convergence/hardware claim',
    }
    report = _json_safe(report)
    if strict and errors:
        error = ValueError('训练配置审计失败：'+'；'.join(x['message'] for x in errors))
        error.report = report
        raise error
    return report

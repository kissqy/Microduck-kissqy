"""Official schema-2 packaging and explicit 0.15.1 deployment settings.

No firmware writes and no inference-output transformations happen here.
"""
import copy
import hashlib
import json
import math
from pathlib import Path

if __package__:
    from . import action_filter
else:
    import action_filter

if __package__:
    from .official_spec import TASKS, REVISION, RUNTIME_VERSION, RUNTIME_REVISION, OBSERVATIONS, RUNTIME_JOINTS, RUNTIME_HOME, training_origin, contract as physics_contract, compare_contracts
else:
    from official_spec import TASKS, REVISION, RUNTIME_VERSION, RUNTIME_REVISION, OBSERVATIONS, RUNTIME_JOINTS, RUNTIME_HOME, training_origin, contract as physics_contract, compare_contracts


EXPORT_REVISION = 2


def training_snapshot(request, resolved):
    """Keep the train-time readback, not the exporter/play-only configuration.

    Evaluation drops expert BC and may disable external pushes. Those are not
    changes to what the checkpoint learned. Old runs without a readback remain
    usable, but their reconstructed config must not be called a train receipt.
    """
    source = request.get('source_training_snapshot')
    if source:
        source = copy.deepcopy(source)
        try:
            compare_contracts(physics_contract(source, training_origin(request)), physics_contract(resolved))
        except ValueError as error:
            raise ValueError('导出配置与原训练读回不一致；不会用当前页面配置改写模型合同：' + str(error)) from error
        provenance = request.get('source_training_snapshot_kind', 'training_run_readback')
        if provenance not in ('training_run_readback', 'checkpoint_params_yaml'):
            raise ValueError('原训练配置快照的来源标记无效。')
    else:
        source = {'task': resolved.get('task', request['task']),
                  'full': copy.deepcopy(resolved['full']), 'model': copy.deepcopy(resolved['model'])}
        provenance = 'reconstructed_from_saved_recipe'
    # Do not include the large UI row/help table or paths unrelated to physics.
    result = {k: source[k] for k in ('task', 'full', 'model')}
    result['provenance'] = provenance
    result['sha256'] = hashlib.sha256(json.dumps(
        result, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    return result


def training_physics(snapshot):
    """Simulation features are archived; they are not firmware on/off knobs."""
    env = snapshot['full']['env']
    model = snapshot['model']
    return {
        'actuators': copy.deepcopy(model['actuators']),
        'gear_backlash': copy.deepcopy(model.get('gear_backlash', {'enabled': False})),
        'total_mass_kg': model.get('total_mass_kg'),
        'randomization_events': {name: copy.deepcopy(term) for name, term in env.get('events', {}).items()
                                 if term is not None},
        'curricula': copy.deepcopy(env.get('curriculum', {})),
        'terrain': copy.deepcopy(env.get('scene', {}).get('terrain')),
        'simulation': copy.deepcopy(env.get('sim')),
        'export_behavior': 'archive_actual_training_configuration_without_runtime_switch_conversion',
    }


def deployment_contract(request, resolved):
    task = request['task']
    info = TASKS[task]
    snapshot = training_snapshot(request, resolved)
    env = snapshot['full']['env']
    obs = env['observations']['actor']
    if list(obs['terms']) != OBSERVATIONS or obs.get('history_length') not in (None, 0):
        raise ValueError('观测顺序或历史长度不符合 0.15.1，不能标记为兼容导出。')
    if any(x.get('history_length', 0) not in (None, 0) for x in obs['terms'].values()):
        raise ValueError('0.15.1 的本次 MLP 导出不接受历史观测堆叠。')
    if any(x.get('scale') not in (None,1,1.0) or x.get('clip') is not None for x in obs['terms'].values()):
        raise ValueError('额外观测缩放或裁剪不符合 0.15.1 的原始观测接口。')
    joints=[j for j in snapshot['model']['joints'] if j['type']==3 and not j['name'].startswith('passive_')]
    if [j['name'] for j in joints] != RUNTIME_JOINTS or any(abs(j['home_rad']-home)>1e-7 for j,home in zip(joints,RUNTIME_HOME)):
        raise ValueError('关节顺序或 Home 与 0.15.1 不一致，不能标记为直接兼容模型。')
    action = env['actions']['joint_pos']
    scale = action['scale']
    if type(scale) not in (int, float) or not math.isfinite(scale) or not action.get('use_default_offset'):
        raise ValueError('目标角映射必须为 Home + 标量系数 × 原始动作。')
    if action.get('clip') is not None or snapshot['full']['agent'].get('clip_actions') is not None:
        raise ValueError('额外动作裁剪与 0.15.1 原始策略输出映射不一致。')
    hz = 1.0 / (env['sim']['mujoco']['timestep'] * env['decimation'])
    if abs(hz - 50) > 1e-6:
        raise ValueError('当前训练控制频率不是 0.15.1 的 50Hz；请恢复官方时间步长。')
    role = info['role']
    slot = {'walk': 'walk', 'joint': 'walk', 'stand': None, 'roller': None, 'crouch': None}.get(role, role)
    encoding = {'ground_pick': 'phase', 'crouch': 'phase', 'sitstand': 'posture_flag'}.get(role, 'constant')
    filter_state = action_filter.describe(action, hz)
    policy = {
        'head_lowpass': filter_state['head_alpha'] if filter_state['enabled'] else 1.0,
        'legs_lowpass': filter_state['legs_alpha'] if filter_state['enabled'] else 1.0,
    }
    if role in ('walk', 'joint', 'stand', 'roller'):
        policy['action_scale'] = float(scale)
    elif role in ('ground_pick', 'crouch'):
        policy['ground_pick_action_scale'] = float(scale)
    elif role == 'roulade':
        policy['roulade_action_scale'] = float(scale)
    elif role in ('kick_left', 'kick_right'):
        policy['standing_action_scale'] = float(scale)
    elif role == 'sitstand':
        if abs(scale - 1.0) > 1e-7:
            raise ValueError('官方坐站运行分支固定动作系数1.0，不能直接部署不同系数模型。')
    if role in ('ground_pick', 'crouch'):
        period = env['commands']['twist']['period']
        policy['ground_pick_period'] = float(period)
    return {
        'export_contract_revision': EXPORT_REVISION,
        'target_firmware': {'version': RUNTIME_VERSION, 'revision': RUNTIME_REVISION},
        'training_source': {'repo': 'pollen-robotics/microduck_rl', 'commit': training_origin(request)['baseline_pin']['revision']},
        'model_origin': training_origin(request), 'evaluation_source_revision': REVISION,
        'model_api': 1, 'control_hz': hz, 'role': role, 'slot': slot, 'trained_action_scale': float(scale),
        'runtime_joint_order': RUNTIME_JOINTS, 'runtime_home_rad': RUNTIME_HOME,
        'command_encoding': encoding,
        'required_policy_settings': policy,
        'runtime_only_settings': {
            'voltage_adapt': {
                'export_behavior': 'inherit_existing_runtime_configuration',
                'training_action_compensation': 'not_present_in_training_action_term',
                'note': '供电随机化/负载掉压属于BAM训练物理；不等于运行端动态动作倍率补偿。导出不强制开启或关闭。',
            },
            'gain_and_gain_ratios': {
                'keys': ['gain', 'standing_gain_ratio', 'ground_pick_gain_ratio', 'roulade_gain_ratio'],
                'export_behavior': 'inherit_existing_runtime_configuration',
                'note': '训练BAM的实际kp_fw见hardware_command和training_physics；不能凭空推导固件增益或翻译层寄存器映射。',
            },
        },
        'training_snapshot': snapshot,
        'training_physics': training_physics(snapshot),
        'robot_mode': 'roller' if role in ('roller', 'crouch') else 'feet',
        'gear_backlash': snapshot['model'].get('gear_backlash', {'enabled': False}),
        'hardware_adapter_required': 'HD1910 + 本机IMU；官方XL330驱动不能直接驱动本机',
        'hardware_command': {'goal_speed_raw': 0, 'write_acceleration_register_41': False,
                             'firmware_kp_raw': snapshot['model']['actuators'][0]['kp_fw']},
        'previous_action_observation': 'raw_policy_output_before_scaling_and_filtering',
        'normalization': ('embedded_in_onnx_once' if snapshot['full']['agent']['actor'].get('obs_normalization')
                          else 'not_used_in_training'),
        'teacher_only': role == 'stand', 'deployment_verified': False,
        'action_filter': filter_state,
        'action_filter_note': action_filter.note(filter_state),
    }


def manifest_for(request, contract, onnx_sha256):
    info = TASKS[request['task']]
    role = info['role']
    command = {'encoding': contract['command_encoding'], 'idle': [0, 0, 0]}
    if role in ('walk', 'joint'):
        command.update(twist='vx / vy / yaw velocity', head='neck pitch / head pitch / yaw / roll',
                       body='body pose command in official observation order')
    elif role == 'sitstand':
        command.update(slot='twist[0]', sit=1, stand=0,
                       twist='posture flag, not velocity', head='official head pose command', body='official body command')
    elif role in ('ground_pick', 'crouch'):
        command.update(period_s=contract['required_policy_settings']['ground_pick_period'], end_phase=0.7,
                       twist='cos(2*pi*phase), sin(2*pi*phase), 0', head='zeros', body='zeros')
    else:
        command.update(twist='zeros', head='zeros', body='zeros')
    kind = 'scripted' if role == 'sitstand' else 'episodic' if role in ('roulade', 'kick_left', 'kick_right', 'ground_pick', 'crouch') else 'perpetual'
    result = {
        'schema_version': 2, 'model_api': 1, 'obs_len': 61, 'action_len': 14,
        'robot': {'model': 'microduck', 'hw_rev': 1, 'servos': 'hd1910', 'control_hz': 50},
        'name': {'stand': 'standup-teacher', 'joint': 'velstand'}.get(role, role),
        'kind': kind, 'description': info['description'],
        'entry_pose': 'fallen' if role == 'stand' else 'standing', 'command': command,
        'action_scale': contract['trained_action_scale'],
        'action_filter': contract['action_filter'],
        'required_policy_settings': copy.deepcopy(contract['required_policy_settings']),
        'runtime_only_settings': copy.deepcopy(contract['runtime_only_settings']),
        'normalization': contract['normalization'],
        'export_contract_revision': contract['export_contract_revision'],
        'training_snapshot_sha256': contract['training_snapshot']['sha256'],
        'training': {'task_id': training_origin(request)['task'], 'repo': 'pollen-robotics/microduck_rl', 'commit': training_origin(request)['baseline_pin']['revision'],
                     'checkpoint': request.get('source_iteration'), 'source_file': request.get('checkpoint')},
        'target_firmware': RUNTIME_VERSION, 'teacher_only': role == 'stand',
        'source_revision': training_origin(request)['baseline_pin']['revision'], 'task': request['task'], 'checkpoint': request.get('checkpoint'),
        'model_origin': training_origin(request), 'export_source_revision': REVISION,
        'onnx_sha256': onnx_sha256, 'deployment_verified': False,
    }
    if contract['slot']: result['slot'] = contract['slot']
    if role in ('roller', 'crouch'): result['mode'] = 'roller'
    result['gear_backlash'] = contract['gear_backlash']
    if kind == 'episodic':
        result['duration_s'] = {'roulade': 1.0, 'kick_right': 0.5, 'kick_left': 0.5}.get(role, command.get('period_s', 4.0) * 0.7)
        result['chain'] = role == 'roulade'
    elif role == 'sitstand':
        result.update(unwind_s=1.0, ramp_s=2.0)
    else:
        result['duration_s'] = None
    return result


def write_sidecars(path, request, contract):
    path = Path(path)
    manifest = manifest_for(request, contract, hashlib.sha256(path.read_bytes()).hexdigest())
    path.with_suffix('.manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    path.with_suffix('.training.json').write_text(json.dumps(contract['training_snapshot'], ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['# 0.15.1 的 [policy] 参数片段；合并使用，不是完整 robotd.toml。',
             '# 仅适用于本包对应的 HD1910 自训模型；硬件驱动仍需飞特/IMU适配。',
             '# 只写原训练已确认的动作映射和滤波。',
             '# 电压动作补偿、增益及增益倍率沿用运行端配置；本片段不改这些开关。', '[policy]']
    for name, value in contract['required_policy_settings'].items():
        lines.append(name + ' = ' + json.dumps(value))
    path.with_suffix('.deployment.toml').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    slot = contract['slot']
    use = ('这是倒地起身老师，供联合训练和仿真评估；不要自动作为 stand 槽的零速度保持模型。'
           if contract['teacher_only'] else ('对应官方模式：滑轮 roller，动作 `'+contract['role']+'`。' if slot is None else '对应官方模型槽：`'+slot+'`。'))
    text = f'''# HD1910 自训模型 · 目标固件 0.15.1

{use}

- 训练来源任务：`{training_origin(request)['task']}`；官方训练提交：`{training_origin(request)['baseline_pin']['revision']}`。
- 本次评估/导出任务：`{request['task']}`；导出源码：`{REVISION}`。原训练摩擦：`{training_origin(request)['friction_randomization']}`（fixed=固定摩擦；official=官方随机化）。
- 模型：`policy.onnx`；`checkpoint.pt` 用于续训，不能直接交给 robotd 推理。
- `manifest.json` 使用官方 schema 2；本 ZIP 是训练归档，不能当作固件升级包。
- `deployment-profile.toml` 是官方 `[policy]` 配置片段。由运行端合并到已有配置，不能覆盖整份配置文件。
- {contract['action_filter_note']} 模型内部仍包含 BAM 舵机动态。滤波作用于 Home＋动作系数×原始输出之后的关节目标，不缩小最终角度；ONNX图不内嵌此滤波。
- 包内 `manifest.json` 仅记录参数，不能保证现有固件自动读取；部署时必须落实 `deployment-profile.toml` 中的动作系数和头腿滤波。
- 电压补偿、增益及增益倍率不是本次训练动作项的配置字段，导出不强制开启、关闭或改成1。它们沿用运行端已有配置；如原配置已经是关闭，本片段不会自动改为开启。BAM供电随机化和负载掉压原样记录在训练快照，不能当作已训练运行端电压动作补偿。
- `training-config.json` 保存配置来源 `{contract['training_snapshot']['provenance']}`、环境、奖励、课程、专家BC、BAM、质量和齿隙等。优先使用原训练启动读回；历史记录缺失时明确标为按保存配方重建，不伪造原训练读回。
- 观测归一化状态：`{contract['normalization']}`；启用时由官方导出器封装在ONNX内，运行端不要重复归一化。
- 必须使用 HD1910/IMU 适配驱动和当前机械装配的标定。包内标定只作来源记录，不覆盖实机零点。
- 齿隙仿真：`{json.dumps(contract['gear_backlash'], ensure_ascii=False)}`。被动齿隙关节不作为ONNX动作导出，实机使用真实编码器反馈。
- 行走老师与联合模型都放 walk 槽；只有联合模型包含相应的倒地恢复训练。起身老师不是另一套“原地保持”策略。
- 捡取使用相位指令，坐站使用姿态标志；前滚翻和左右脚踢球使用官方一次动作窗口。仿真回合长度不等于固件触发窗口。
- 本包通过模型格式和有限输出检查，不代表已经通过你的机器人实机步态验证。

动作、观测顺序、实际 Home、BAM 参数及训练快照见 `deployment-contract.json`、`training-config.json` 和 `upstream-params/`。
'''
    path.with_suffix('.deployment.md').write_text(text, encoding='utf-8')

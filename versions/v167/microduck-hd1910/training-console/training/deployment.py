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
    from .official_spec import TASKS, ROLLER_ROLES, REVISION, RUNTIME_VERSION, RUNTIME_REVISION, OBSERVATIONS, RUNTIME_JOINTS, RUNTIME_HOME, training_origin, contract as physics_contract, compare_contracts
else:
    from official_spec import TASKS, ROLLER_ROLES, REVISION, RUNTIME_VERSION, RUNTIME_REVISION, OBSERVATIONS, RUNTIME_JOINTS, RUNTIME_HOME, training_origin, contract as physics_contract, compare_contracts


EXPORT_REVISION = 3
# Reference 0.15.1 published roller weights: train action scale=1.0,
# *runtime* scale=0.8 and head/legs LPF=0.5/0.7. These are deployment
# sidecar presets, not PPO training parameters. For custom historical action
# scaling, preserve the original execution mapping instead of overwriting it.
PUBLISHED_ROLLER_PRESETS = {
    'roller': {'filename': 'roller.onnx', 'action_scale': 0.8, 'head_lowpass': 0.5, 'legs_lowpass': 0.7},
    'crouch': {'filename': 'roller_crouch.onnx', 'action_scale': 0.8, 'head_lowpass': 0.5, 'legs_lowpass': 0.7},
}
PHASE_ROLES = ('ground_pick', 'crouch', 'spin')
SKILL_WINDOWS = {'roulade': 1.0, 'kick_left': 0.5, 'kick_right': 0.5}
# Frozen R148 official-adapter task gate; graph, hardware and model checks still apply.
R148_TASKS = frozenset((
    'Mjlab-VelStand-Flat-MicroDuck', 'Mjlab-GroundPick-Flat-MicroDuck',
    'Mjlab-Roulade-Flat-MicroDuck', 'Mjlab-StandUp-Flat-MicroDuck',
    'Mjlab-Velocity-Rough-Backlash-MicroDuck',
    'Mjlab-StandUp-Rough-Backlash-MicroDuck',
    'Mjlab-VelStand-Rough-Backlash-MicroDuck',
))


def _callable_name(value):
    return value.get('callable', '') if isinstance(value, dict) else str(value or '')


def _command_contract(role, env):
    """Describe actual command meanings, not merely a 61-element tensor shape."""
    terms = env['observations']['actor']['terms']
    if role in ROLLER_ROLES or role == 'ground_pick':
        for name, dim in (('head_command', 4), ('body_command', 6)):
            term = terms[name]
            expected_live = role == 'swizzle' and name == 'head_command'
            func = _callable_name(term.get('func'))
            params = term.get('params', {})
            valid = (func.endswith('.generated_commands') and params.get('command_name') == 'head_pose'
                     if expected_live else
                     func.endswith('.zero_command_padding') and params.get('dim') == dim)
            if not valid:
                raise ValueError(f'{role} 的 {name} 与冻结运行通道不一致，不能按该动作合同导出。')
    command = {'encoding': 'phase' if role in PHASE_ROLES else 'posture_flag' if role == 'sitstand' else 'constant',
               'idle': [0, 0, 0], 'twist': 'zeros', 'head': 'zeros', 'body': 'zeros'}
    if role in ('walk', 'joint'):
        command.update(twist='vx / vy / yaw velocity', head='neck pitch / head pitch / yaw / roll',
                       body='body pose command in official observation order')
    elif role == 'sitstand':
        command.update(slot='twist[0]', sit=1, stand=0, twist='posture flag, not velocity',
                       head='official head pose command', body='zeros')
    elif role in PHASE_ROLES:
        cfg = env['commands']['twist']
        period = cfg.get('period')
        if (not _callable_name(cfg.get('class_type')).endswith('.GroundPickPhaseCommand')
                or type(period) not in (int, float) or not math.isfinite(period) or period <= 0
                or type(cfg.get('randomize_phase')) is not bool):
            raise ValueError('相位动作必须使用 GroundPickPhaseCommand、有限正周期和明确的训练初始相位配置。')
        command.update(period_s=float(period), end_phase=0.7,
                       start_phase=0.0, training_randomize_phase=cfg['randomize_phase'],
                       twist='cos(2*pi*phase), sin(2*pi*phase), 0')
    elif role in ('roller', 'swizzle'):
        command.update(twist=('forward/backward push, 0, clipped heading error (not yaw velocity)'
                              if role == 'swizzle' else 'push/coast/brake, 0, 0 (not velocity tracking)'),
                       allowed_twist_ranges=copy.deepcopy(env['commands']['twist']['ranges']))
        if role == 'swizzle':
            command['head'] = 'neck pitch / head pitch / yaw / roll; deltas from HOME'
    return command


def _runtime_compatibility(task, role):
    """A native route does not grant compatibility with the installed HD1910 importer."""
    route = ('ground_pick' if role in PHASE_ROLES else 'skill' if role in SKILL_WINDOWS
             else 'sitstand' if role == 'sitstand' else 'manual_skill' if role == 'roller_stand'
             else 'teacher_only' if role == 'stand' else 'walk')
    limitations = []
    level = 'route_available'
    if role in ('roller', 'swizzle', 'slope'):
        level = 'restricted_command_protocol'
        limitations.append('冻结 robotd 不按模型屏蔽 head/body 或转换指令；调用端必须落实本合同中的命令限制。')
    if role == 'swizzle':
        limitations.append('现有 yaw 速度控制不能当作目标航向控制；现成控制路径仅核定 y=0、yaw=0、body=0 的直行子集。完整转向需要显式按航向误差协议下发的控制端，当前没有端到端验证。')
    elif role == 'roller':
        limitations.append('x 是推进/滑行/刹车意图；y、yaw、head、body 必须为0。')
    elif role == 'slope':
        limitations.append('斜坡平衡策略只能持续接收全零 twist/head/body，不能作为可遥控行走模型。')
    elif role == 'roller_stand':
        level = 'manual_configuration_required'
        limitations.append('Roller 模式不自动切换 Stand；只能另配零命令通用技能。官方未给出该任务的执行窗口，训练回合时长不能直接作 duration。此导出不生成可触发技能或 stand 槽。')
    elif role == 'stand':
        level = 'teacher_only'
        limitations.append('倒地起身老师保留为联合训练/评估输入，不自动部署为原地保持 stand 策略。')
    if role in PHASE_ROLES:
        limitations.append('同一 mode 只有一个 ground_pick 槽；只加载 ONNX 不会自动更新 period/end_phase，必须核对所选模型及相位配置。')
    return {
        'native_runtime': {'version': RUNTIME_VERSION, 'revision': RUNTIME_REVISION,
                           'route': route, 'support': level, 'limitations': limitations},
        'r148_importer': {'task_allowlisted': task in R148_TASKS,
                          'direct_import_verified': False,
                          'note': ('任务通过 R148 白名单；图算子、合同、硬件等检查仍独立执行。' if task in R148_TASKS
                                   else 'R148 当前任务白名单不接收此任务；训练导出不等于现有机器人一键导入。')},
        'requires_passive_roller_hardware': role in ROLLER_ROLES,
        'official_finished_weights': False,
        'automatic_deployment': False,
    }


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
    if (type(scale) not in (int, float) or not math.isfinite(scale) or scale <= 0
            or not action.get('use_default_offset') or action.get('offset', 0) != 0):
        raise ValueError('目标角映射必须为 Home + 标量系数 × 原始动作。')
    if action.get('clip') is not None or snapshot['full']['agent'].get('clip_actions') is not None:
        raise ValueError('额外动作裁剪与 0.15.1 原始策略输出映射不一致。')
    hz = 1.0 / (env['sim']['mujoco']['timestep'] * env['decimation'])
    if abs(hz - 50) > 1e-6:
        raise ValueError('当前训练控制频率不是 0.15.1 的 50Hz；请恢复官方时间步长。')
    role = info['role']
    slot = {'walk': 'walk', 'joint': 'walk', 'stand': None, 'roller': 'walk',
            'swizzle': 'walk', 'slope': 'walk', 'roller_stand': None,
            'crouch': 'ground_pick', 'spin': 'ground_pick'}.get(role, role)
    command = _command_contract(role, env)
    filter_state = action_filter.describe(action, hz)
    published = PUBLISHED_ROLLER_PRESETS.get(role) if abs(float(scale) - 1.0) < 1e-9 else None
    runtime_scale = float(published['action_scale']) if published else float(scale)
    policy = {
        'head_lowpass': published['head_lowpass'] if published else (filter_state['head_alpha'] if filter_state['enabled'] else 1.0),
        'legs_lowpass': published['legs_lowpass'] if published else (filter_state['legs_alpha'] if filter_state['enabled'] else 1.0),
    }
    skill = None
    if role in ('walk', 'joint', 'stand', 'roller', 'swizzle', 'slope'):
        policy['action_scale'] = runtime_scale
    elif role in PHASE_ROLES:
        policy['ground_pick_action_scale'] = runtime_scale
    elif role in SKILL_WINDOWS:
        skill = {'name': role, 'duration': SKILL_WINDOWS[role], 'command': [0, 0, 0],
                 'unwind': [0, 0, 0], 'unwind_s': 0.0, 'chain': role == 'roulade',
                 'params': {'action_scale': float(scale)}}
    elif role == 'sitstand':
        if abs(scale - 1.0) > 1e-7:
            raise ValueError('官方坐站运行分支固定动作系数1.0，不能直接部署不同系数模型。')
    if role in PHASE_ROLES:
        policy['ground_pick_period'] = command['period_s']
    result = {
        'export_contract_revision': EXPORT_REVISION,
        'target_firmware': {'version': RUNTIME_VERSION, 'revision': RUNTIME_REVISION},
        'training_source': {'repo': 'pollen-robotics/microduck_rl', 'commit': training_origin(request)['baseline_pin']['revision']},
        'model_origin': training_origin(request), 'evaluation_source_revision': REVISION,
        'model_api': 1, 'control_hz': hz, 'role': role, 'slot': slot, 'trained_action_scale': float(scale),
        'runtime_action_scale': runtime_scale,
        'runtime_execution_preset': ({'name': published['filename'], 'source': 'official_0.15.1_roller_mode_and_published_manifest'} if published else None),
        'runtime_joint_order': RUNTIME_JOINTS, 'runtime_home_rad': RUNTIME_HOME,
        'command_encoding': command['encoding'], 'command_contract': command,
        'required_policy_settings': policy,
        'required_skill_settings': skill,
        'runtime_compatibility': _runtime_compatibility(task, role),
        'runtime_only_settings': {
            'voltage_adapt': {
                'export_behavior': 'inherit_existing_runtime_configuration',
                'training_action_compensation': 'not_present_in_training_action_term',
                'note': '供电随机化/负载掉压属于BAM训练物理；不等于运行端动态动作倍率补偿。导出不强制开启或关闭。',
            },
            'gain_and_gain_ratios': {
                'keys': ['gain', 'standing_gain_ratio', 'ground_pick_gain_ratio', 'skill[].params.gain_ratio'],
                'export_behavior': 'inherit_existing_runtime_configuration',
                'note': '训练BAM的实际kp_fw见hardware_command和training_physics；不能凭空推导固件增益或翻译层寄存器映射。',
            },
        },
        'training_snapshot': snapshot,
        'training_physics': training_physics(snapshot),
        'robot_mode': 'roller' if role in ROLLER_ROLES else 'feet',
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
    return result


def manifest_for(request, contract, onnx_sha256):
    info = TASKS[request['task']]
    role = info['role']
    command = copy.deepcopy(contract['command_contract'])
    kind = 'scripted' if role == 'sitstand' else 'episodic' if role in (*SKILL_WINDOWS, *PHASE_ROLES) else 'perpetual'
    result = {
        'schema_version': 2, 'model_api': 1, 'obs_len': 61, 'action_len': 14,
        'robot': {'model': 'microduck', 'hw_rev': 1, 'servos': 'hd1910', 'control_hz': 50},
        'name': {'stand': 'standup-teacher', 'joint': 'velstand'}.get(role, role),
        'kind': kind, 'description': info['description'],
        'entry_pose': 'fallen' if role in ('stand', 'roller_stand') else 'standing', 'command': command,
        'action_scale': contract['runtime_action_scale'],
        'trained_action_scale': contract['trained_action_scale'],
        'action_filter': contract['action_filter'],
        'required_policy_settings': copy.deepcopy(contract['required_policy_settings']),
        'required_skill_settings': copy.deepcopy(contract['required_skill_settings']),
        'runtime_compatibility': copy.deepcopy(contract['runtime_compatibility']),
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
    if role in ROLLER_ROLES: result['mode'] = 'roller'
    result['gear_backlash'] = contract['gear_backlash']
    if kind == 'episodic':
        result['duration_s'] = SKILL_WINDOWS[role] if role in SKILL_WINDOWS else command['period_s'] * command['end_phase']
        result['chain'] = role == 'roulade'
    elif role == 'sitstand':
        ramp = contract['training_snapshot']['full']['env']['commands']['twist']['ramp_s']
        if type(ramp) not in (int, float) or not math.isfinite(ramp) or ramp <= 0:
            raise ValueError('坐站 ramp_s 必须为有限正数。')
        result.update(unwind_s=1.0, ramp_s=float(ramp))
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
             '# 轮滑行走/轮滑蹲下官方推理0.8与PPO训练1.0分开记录，其他动作不套用该预设。',
             '# 电压动作补偿、增益及增益倍率沿用运行端配置；本片段不改这些开关。', '[policy]']
    for name, value in contract['required_policy_settings'].items():
        lines.append(name + ' = ' + json.dumps(value))
    skill = contract.get('required_skill_settings')
    if skill:
        lines.extend(['', '# 合并对应名称的技能；保留现有 path / params.gain_ratio。',
                      '# 必须另将该技能路径绑定到本模型；不要用片段替换其它技能。', '[[policy.skill]]'])
        for name, value in skill.items():
            if name != 'params':
                lines.append(name + ' = ' + json.dumps(value))
        lines.extend(['[policy.skill.params]', 'action_scale = ' + json.dumps(skill['params']['action_scale'])])
    compatibility = contract['runtime_compatibility']
    lines.extend(['', '# 原生路由：' + compatibility['native_runtime']['route'],
                  '# ' + compatibility['r148_importer']['note']])
    for limitation in compatibility['native_runtime']['limitations']:
        lines.append('# ' + limitation)
    path.with_suffix('.deployment.toml').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    slot = contract['slot']
    use = ('这是倒地起身老师，供联合训练和仿真评估；不要自动作为 stand 槽的零速度保持模型。'
           if contract['teacher_only'] else ('需要手工定义零命令技能及验证执行窗口；不生成自动起身槽。' if slot is None else '对应原生运行通道的模型槽：`'+slot+'`；这不是当前 R148 的导入许可。'))
    restrictions = '\n'.join('- ' + item for item in compatibility['native_runtime']['limitations'])
    roller_note = ('- 此任务需要被动轮滑机械组件；普通脚底模型不能只换 ONNX 来运行。' if compatibility['requires_passive_roller_hardware'] else '')
    profile_use = '`deployment-profile.toml` 是官方 `[policy]` / `[[policy.skill]]` 配置片段。由运行端合并到已有配置，不能覆盖整份配置文件；技能必须保留已配置的路径和增益倍率，再绑定到本次模型。'
    mapping_use = '包内 `manifest.json` 仅记录参数，不能保证现有固件自动读取；部署时必须落实 `deployment-profile.toml` 中的动作系数和头腿滤波。'
    text = f'''# HD1910 自训模型 · 目标固件 0.15.1

{use}

- 原生接口核对：`{RUNTIME_VERSION}` / `{RUNTIME_REVISION}`；路由 `{compatibility['native_runtime']['route']}`，支持范围 `{compatibility['native_runtime']['support']}`。
- {compatibility['r148_importer']['note']} 本包是自训模型，不是官方已经验证的成品权重；不自动写入机器人配置。
{restrictions}
{roller_note}
- 训练来源任务：`{training_origin(request)['task']}`；官方训练提交：`{training_origin(request)['baseline_pin']['revision']}`。
- 本次评估/导出任务：`{request['task']}`；导出源码：`{REVISION}`。原训练摩擦：`{training_origin(request)['friction_randomization']}`（fixed=固定摩擦；official=官方随机化）。
- 模型：`policy.onnx`；`checkpoint.pt` 用于续训，不能直接交给 robotd 推理。
- `manifest.json` 使用官方 schema 2；本 ZIP 是训练归档，不能当作固件升级包。
- {profile_use}
- {contract['action_filter_note']} 此项为原训练历史；实际推理以 deployment-profile.toml 的参数为准。模型内部仍包含 BAM 舵机动态。滤波作用于 Home＋动作系数×原始输出之后的关节目标，不缩小最终角度；ONNX图不内嵌此滤波。
- {mapping_use}
- 电压补偿、增益及增益倍率不是本次训练动作项的配置字段，导出不强制开启、关闭或改成1。它们沿用运行端已有配置；如原配置已经是关闭，本片段不会自动改为开启。BAM供电随机化和负载掉压原样记录在训练快照，不能当作已训练运行端电压动作补偿。
- `training-config.json` 保存配置来源 `{contract['training_snapshot']['provenance']}`、环境、奖励、课程、专家BC、BAM、质量和齿隙等。优先使用原训练启动读回；历史记录缺失时明确标为按保存配方重建，不伪造原训练读回。
- 观测归一化状态：`{contract['normalization']}`；启用时由官方导出器封装在ONNX内，运行端不要重复归一化。
- 必须使用 HD1910/IMU 适配驱动和当前机械装配的标定。包内标定只作来源记录，不覆盖实机零点。
- 齿隙仿真：`{json.dumps(contract['gear_backlash'], ensure_ascii=False)}`。被动齿隙关节不作为ONNX动作导出，实机使用真实编码器反馈。
- 行走老师与联合模型都放 walk 槽；只有联合模型包含相应的倒地恢复训练。起身老师不是另一套“原地保持”策略。
- 捡取、轮滑蹲下和旋转使用相位指令，周期取原训练快照，结束相位为0.7；坐站使用姿态标志。前滚翻和左右脚踢球使用官方一次动作窗口。仿真回合长度不等于固件触发窗口。
- 左脚踢球使用左脚任务独立训练的模型；运行端不会因为文件名是 left 就镜像右脚模型。
- 本包通过模型格式和有限输出检查，不代表已经通过你的机器人实机步态验证。

动作、观测顺序、实际 Home、BAM 参数及训练快照见 `deployment-contract.json`、`training-config.json` 和 `upstream-params/`。
'''
    path.with_suffix('.deployment.md').write_text(text, encoding='utf-8')

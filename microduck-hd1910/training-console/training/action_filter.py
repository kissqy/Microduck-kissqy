"""Portable settings for the external, per-control-step joint-target EMA.

Missing settings mean legacy pass-through. No torch/mjlab imports here: the
dashboard and old run records must remain readable without the training engine.
"""
import math

HEAD_JOINTS = ('neck_pitch', 'head_pitch', 'head_yaw', 'head_roll')
LEG_JOINTS = tuple(side + '_' + joint for side in ('left', 'right')
                   for joint in ('hip_yaw', 'hip_roll', 'hip_pitch', 'knee', 'ankle'))
VERSION = 1


def validate(value=None):
    if value is None:
        return {'enabled': False, 'head_alpha': 1.0, 'legs_alpha': 1.0, 'version': VERSION}
    if not isinstance(value, dict) or type(value.get('enabled')) is not bool:
        raise ValueError('训练动作滤波设置无效。')
    if type(value.get('version', VERSION)) is not int or value.get('version', VERSION) != VERSION:
        raise ValueError('不支持的训练动作滤波版本。')
    result = {'enabled': value['enabled'], 'version': VERSION}
    for name, default in (('head_alpha', .5), ('legs_alpha', .7)):
        alpha = value.get(name, default)
        if type(alpha) not in (int, float) or not math.isfinite(alpha) or not 0 < alpha <= 1:
            raise ValueError('头颈/腿部滤波系数 α 应大于 0 且不超过 1；1 为直通。')
        result[name] = float(alpha)
    return result


def from_action(action):
    """Read the resolved config, rather than trusting mutable page settings."""
    if not isinstance(action, dict):
        action = vars(action)
    if 'filter_version' not in action:
        return validate()
    return validate({'enabled': True, 'version': action['filter_version'],
                     'head_alpha': action['head_alpha'], 'legs_alpha': action['legs_alpha']})


def describe(action, control_hz=50.0):
    settings = from_action(action)
    return {**settings, 'control_hz': float(control_hz),
            'stage': 'joint_position_target_after_home_and_scale',
            'formula': 'filtered = alpha * target + (1 - alpha) * previous_filtered',
            'head_joints': list(HEAD_JOINTS), 'leg_joints': list(LEG_JOINTS),
            'update': 'once_per_policy_step', 'reset': 'first_target_passthrough_per_environment',
            'previous_action_observation': 'raw_policy_output', 'onnx': 'external_filter_not_baked_into_graph'}


def note(settings):
    if not settings['enabled']:
        return '训练未加额外头腿EMA；头颈/腿部直通 1.0。'
    return ('训练使用关节目标EMA：头颈 α=%g、腿部 α=%g，每个50Hz控制周期更新一次；'
            '实机必须使用相同系数且只滤波一次。' %
            (settings['head_alpha'], settings['legs_alpha']))


def configure(env_cfg, parameters):
    """Install only the local action term; leave official source/BAM/PPO intact."""
    settings = validate(parameters.get('action_filter'))
    if not settings['enabled']:
        return settings
    from dataclasses import fields
    from mjlab.envs.mdp.actions import JointPositionActionCfg
    if __package__:
        from .filtered_actions import FilteredJointPositionActionCfg
    else:
        from filtered_actions import FilteredJointPositionActionCfg
    action = env_cfg.actions.get('joint_pos')
    if not isinstance(action, JointPositionActionCfg) or not action.use_default_offset or action.clip is not None:
        raise ValueError('动作滤波要求 Home + 系数 × 原始输出的关节位置映射，且无额外动作裁剪。')
    hz = 1.0 / (env_cfg.sim.mujoco.timestep * env_cfg.decimation)
    if abs(hz - 50.0) > 1e-6:
        raise ValueError('本次固件对应的动作滤波使用50Hz；当前控制频率不匹配。')
    base = {field.name: getattr(action, field.name) for field in fields(JointPositionActionCfg)}
    env_cfg.actions['joint_pos'] = FilteredJointPositionActionCfg(
        **base, head_alpha=settings['head_alpha'], legs_alpha=settings['legs_alpha'])
    return settings

"""Evaluation-only hardware target mapping, after Home/scale/EMA.

The portable scalar implementation deliberately follows Rust f64::round
(ties away from zero), rather than Python/torch bankers' rounding.  Imports of
torch/mjlab remain lazy so the dashboard and numerical tests can run offline.
"""
import math


ENCODER_COUNTS = 4096
RAD_PER_COUNT = 2.0 * math.pi / ENCODER_COUNTS
_ACTION_CLASSES = None


def round_away(value):
    if not math.isfinite(value):
        raise ValueError('编码器目标必须是有限数。')
    return math.floor(value + .5) if value >= 0 else math.ceil(value - .5)


def map_target(target, joint, *, enabled):
    """Map one filtered target; return real and counterfactual diagnostics."""
    target = float(target)
    if not math.isfinite(target):
        raise ValueError('关节目标含非有限数，已取消目标限幅对照。')
    safety = max(-math.pi, min(math.pi, target))
    calibrated = max(float(joint['min_rad']), min(float(joint['max_rad']), safety))
    raw_float = (float(joint['zero_raw']) + calibrated * int(joint['direction'])
                 * ENCODER_COUNTS / math.tau)
    raw = round_away(raw_float)
    if raw < 0 or raw >= ENCODER_COUNTS:
        raise ValueError('关节 %s 的编码器目标 %s 超出0..4095；不取模或再次夹取。' %
                         (joint['name'], raw))
    encoded = (raw - int(joint['zero_raw'])) * math.tau / ENCODER_COUNTS * int(joint['direction'])
    safety_changed = safety != target
    calibration_changed = calibrated != safety
    return {
        'target_before_rad': target,
        'safety_target_rad': safety,
        'calibrated_target_rad': calibrated,
        'encoder_raw': raw,
        'encoded_target_rad': encoded,
        # Quantization may exceed a calibration endpoint by half a tick.
        # Do not clip again: that would no longer reproduce the encoder write.
        'target_applied_rad': encoded if enabled else target,
        'would_safety_clip': safety_changed,
        'would_calibration_clip': calibration_changed,
        'safety_clipped': bool(enabled and safety_changed),
        'calibration_clipped': bool(enabled and calibration_changed),
        'quantized': bool(enabled and encoded != calibrated),
    }


def map_targets(targets, names, profile, *, enabled):
    by_name = {joint['name']: joint for joint in profile['joints']}
    if len(names) != 14 or len(set(names)) != 14 or set(names) != set(by_name):
        raise ValueError('目标限幅需要准确匹配14个主动关节，不含嘴巴/passive关节。')
    if len(targets) != 14:
        raise ValueError('目标限幅需要14维关节目标。')
    return [map_target(value, by_name[name], enabled=enabled)
            for name, value in zip(names, targets)]


def _action_classes():
    global _ACTION_CLASSES
    if _ACTION_CLASSES is not None:
        return _ACTION_CLASSES
    from dataclasses import dataclass, field
    import torch
    if __package__:
        from .filtered_actions import FilteredJointPositionAction, FilteredJointPositionActionCfg
    else:
        from filtered_actions import FilteredJointPositionAction, FilteredJointPositionActionCfg

    @dataclass(kw_only=True)
    class TargetLimitJointPositionActionCfg(FilteredJointPositionActionCfg):
        limit_profile: dict = field(default_factory=dict)
        limit_enabled: bool = False

        def build(self, env):
            return TargetLimitJointPositionAction(self, env)

    class TargetLimitJointPositionAction(FilteredJointPositionAction):
        def __init__(self, cfg, env):
            super().__init__(cfg, env)
            if self._processed_actions.shape[0] != 1:
                raise ValueError('目标限幅对照只允许单环境评估。')
            self.limit_profile = cfg.limit_profile
            self.limit_enabled = bool(cfg.limit_enabled)
            self.limit_last = None
            # Validate order by actual target names rather than action slices.
            map_targets([0.0] * 14, self.target_names, self.limit_profile, enabled=False)

        def process_actions(self, actions):
            super().process_actions(actions)
            # EMA has already updated its own *unclipped* history.  Raw actions
            # and the previous-action observation are untouched.  apply_actions
            # subsequently applies encoder bias, actuator delay and dynamics.
            values = self._processed_actions[0].detach().cpu().tolist()
            self.limit_last = map_targets(
                values, self.target_names, self.limit_profile, enabled=self.limit_enabled)
            if self.limit_enabled:
                mapped = [item['target_applied_rad'] for item in self.limit_last]
                self._processed_actions[0] = torch.as_tensor(
                    mapped, device=self._processed_actions.device,
                    dtype=self._processed_actions.dtype)

        def reset(self, env_ids=None):
            super().reset(env_ids)
            self.limit_last = None

    _ACTION_CLASSES = TargetLimitJointPositionActionCfg, TargetLimitJointPositionAction
    return _ACTION_CLASSES


def configure(cfg, profile, *, enabled):
    """Change only the comparison action term; preserve source scale/filter."""
    from dataclasses import fields
    from mjlab.envs.mdp.actions import JointPositionActionCfg
    if __package__:
        from .action_filter import from_action
    else:
        from action_filter import from_action
    action = cfg.actions.get('joint_pos')
    if not isinstance(action, JointPositionActionCfg) or not action.use_default_offset or action.clip is not None:
        raise ValueError('对照要求原始 Home + scale × action 映射，不能叠加未知动作裁剪。')
    settings = from_action(action)
    cls, _ = _action_classes()
    base = {field.name: getattr(action, field.name) for field in fields(JointPositionActionCfg)}
    cfg.actions['joint_pos'] = cls(
        **base,
        head_alpha=settings['head_alpha'] if settings['enabled'] else 1.0,
        legs_alpha=settings['legs_alpha'] if settings['enabled'] else 1.0,
        limit_profile=profile, limit_enabled=bool(enabled),
    )
    return cfg

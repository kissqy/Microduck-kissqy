"""mjlab 1.3 action term matching duck-control's head/leg target filtering."""
from dataclasses import dataclass
import torch
from mjlab.envs.mdp.actions.actions import JointPositionAction, JointPositionActionCfg

if __package__:
    from .action_filter import HEAD_JOINTS, LEG_JOINTS, VERSION, validate
else:
    from action_filter import HEAD_JOINTS, LEG_JOINTS, VERSION, validate


@dataclass(kw_only=True)
class FilteredJointPositionActionCfg(JointPositionActionCfg):
    head_alpha: float = .5
    legs_alpha: float = .7
    filter_version: int = VERSION

    def build(self, env):
        return FilteredJointPositionAction(self, env)


class FilteredJointPositionAction(JointPositionAction):
    def __init__(self, cfg, env):
        super().__init__(cfg, env)
        validate({'enabled': True, 'head_alpha': cfg.head_alpha,
                  'legs_alpha': cfg.legs_alpha, 'version': cfg.filter_version})
        names = self.target_names
        expected = set(HEAD_JOINTS + LEG_JOINTS)
        if len(names) != 14 or set(names) != expected:
            raise ValueError('动作滤波必须准确匹配4个头颈和10个腿部关节；不包含嘴巴和passive关节。')
        # Resolve by names, never by guessed tensor slices or servo IDs.
        self._alpha = torch.tensor([cfg.head_alpha if n in HEAD_JOINTS else cfg.legs_alpha
                                    for n in names], device=self._processed_actions.device,
                                   dtype=self._processed_actions.dtype).unsqueeze(0)
        self._previous_filtered = torch.zeros_like(self._processed_actions)
        self._filter_first = torch.ones_like(self._processed_actions[:, :1], dtype=torch.bool)

    def process_actions(self, actions):
        # Base computes Home + scale * raw and leaves raw action observations
        # intact. EMA belongs here, ONCE per policy step, not in apply_actions()
        # which mjlab calls four times per step for physics decimation.
        super().process_actions(actions)
        target = self._processed_actions
        self._processed_actions = torch.where(
            self._filter_first, target,
            self._alpha * target + (1 - self._alpha) * self._previous_filtered)
        self._previous_filtered.copy_(self._processed_actions)
        self._filter_first.fill_(False)

    def reset(self, env_ids=None):
        super().reset(env_ids)
        ids = slice(None) if env_ids is None else env_ids
        self._filter_first[ids] = True
        self._previous_filtered[ids] = 0

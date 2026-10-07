"""HD1910 hardware adapter; the official friction-DR base remains canonical.

Goal-state reset follows fanhao375/microduck-replica, commit
25791f0bd260fd869ed841578785fa8d7e14396d, actuator/feetech_bam.py.
The complete legacy training engine is neither imported nor installed.
"""
from dataclasses import dataclass
from pathlib import Path
import torch
from mjlab.actuator.actuator import ActuatorCmd
from mjlab_microduck.actuator.friction_dr_bam import (
    FrictionDRBamActuator, FrictionDRBamActuatorCfg, BacklashEncoderBamActuator, BacklashEncoderBamActuatorCfg,
)


class Hd1910Actuator(FrictionDRBamActuator):
    def initialize(self, mj_model, model, data, device):
        super().initialize(mj_model, model, data, device)
        self._bam_model.actuator.q_target_smooth = torch.zeros_like(self._prev_motor_torque)
        self._goal_reset_pending = torch.ones((data.nworld, 1), dtype=torch.bool, device=device)

    def reset(self, env_ids=None):
        super().reset(env_ids)
        if env_ids is None:
            self._goal_reset_pending.fill_(True)
        else:
            self._goal_reset_pending[env_ids] = True

    def compute(self, cmd: ActuatorCmd):
        actuator = self._bam_model.actuator
        actuator.q_target_smooth = torch.where(self._goal_reset_pending, cmd.pos, actuator.q_target_smooth)
        self._goal_reset_pending.zero_()
        return super().compute(cmd)


@dataclass(kw_only=True)
class Hd1910ActuatorCfg(FrictionDRBamActuatorCfg):
    def build(self, entity, target_ids, target_names):
        return Hd1910Actuator(self, entity, target_ids, target_names)


class Hd1910BacklashActuator(Hd1910Actuator, BacklashEncoderBamActuator):
    """HD1910 goal reset + official output encoder through serial gear play.

    The official get_command adds passive hinge position to motor position;
    velocity remains motor-side for back-EMF/friction. Do not add passive actions.
    """


@dataclass(kw_only=True)
class Hd1910BacklashActuatorCfg(Hd1910ActuatorCfg, BacklashEncoderBamActuatorCfg):
    def build(self, entity, target_ids, target_names):
        return Hd1910BacklashActuator(self, entity, target_ids, target_names)


def hardware_actuator(backlash=False):
    cfg_type = Hd1910BacklashActuatorCfg if backlash else Hd1910ActuatorCfg
    return cfg_type(
        json_path=str(Path(__file__).with_name('hd1910_m6.json')),
        target_names_expr=('left_hip_yaw', 'left_hip_roll', 'left_hip_pitch', 'left_knee', 'left_ankle',
                           'neck_pitch', 'head_pitch', 'head_yaw', 'head_roll',
                           'right_hip_yaw', 'right_hip_roll', 'right_hip_pitch', 'right_knee', 'right_ankle'),
        kp_fw=5.0,
        vin_range=(7.4, 8.0), vin_drop_gain_range=(0.0, 0.2), vin_min=7.0,
        delay_min_lag=3, delay_max_lag=6,
    )

//! V160 / control.37: an opt-in roller-only policy preset and heading adapter.
//! No servo writes, no changes to normal walking/HOME/startup torque semantics.
use std::{path::{Path,PathBuf}, time::Instant};
use robotd_params::{Mode, ResolvedPolicy};
use duck_control::{imu::ImuData, obs::Command};

pub const CROUCH_CODE: u8 = 1;
pub const SPIN_CODE: u8 = 2;
pub const MODEL_ROOT: &str = "/opt/robot/feetech-ft5-r5/roller";

pub fn available() -> bool {
    ["swizzle","crouch","spin"].iter().all(|name| {
        let dir=Path::new(MODEL_ROOT).join(name);
        ["policy.onnx","manifest.json","deployment-contract.json"]
            .iter().all(|item| dir.join(item).is_file())
    })
}

/// Only roller mode takes a different policy path; the original Walk overrides
/// remain untouched on disk and in memory. All values come from the supplied manifests.
pub fn resolved(mut cfg: ResolvedPolicy, code: u8) -> ResolvedPolicy {
    if cfg.mode != Mode::Roller { return cfg; }
    let (name,period,scale) = if code == SPIN_CODE { ("spin",4.0,1.0) }
                                  else { ("crouch",5.0,0.8) };
    let root=PathBuf::from(MODEL_ROOT);
    cfg.walk = root.join("swizzle/policy.onnx");
    cfg.stand = None;
    cfg.ground_pick = Some(root.join(name).join("policy.onnx"));
    cfg.action_scale = 1.0;
    // Each loaded network applies its own required runtime coefficients, including
    // crouch's 0.5/0.7 deployment filter. Ordinary Walk settings stay on disk.
    cfg.head_lowpass = None;
    cfg.legs_lowpass = None;
    cfg.ground_pick_period = period;
    cfg.ground_pick_end_phase = 0.7;
    cfg.ground_pick_action_scale = scale;
    cfg
}

fn wrap(angle: f64) -> f64 { angle.sin().atan2(angle.cos()) }

pub fn yaw(imu: &ImuData) -> Option<f64> {
    let [w,x,y,z] = imu.quat;
    let norm=w*w+x*x+y*y+z*z;
    if !norm.is_finite() || norm < 0.8 || norm > 1.2 { return None; }
    Some((2.0*(w*z+x*y)).atan2(1.0-2.0*(y*y+z*z)))
}

/// `padd` still sends the official right-stick yaw *rate* with its original
/// deadman. Only roller mode maps that to target heading - measured IMU yaw.
/// Recenter on disable / stale sample / mode change: no old steering goal survives.
#[derive(Default)]
pub struct Heading { target: Option<f64>, last: Option<Instant> }
impl Heading {
    pub fn reset(&mut self) { self.target=None;self.last=None; }
    pub fn adapt(&mut self, command: &Command, imu: &ImuData, now: Instant) -> Command {
        let mut result=*command;
        let Some(measured)=yaw(imu) else {
            self.reset();result.twist=[0.0;3];return result;
        };
        let Some(last)=self.last else {
            self.target=Some(measured);self.last=Some(now);
            result.twist=[0.0;3];return result;
        };
        let dt=now.saturating_duration_since(last).as_secs_f64();
        if dt > 0.15 {
            self.reset();result.twist=[0.0;3];return result;
        }
        self.last=Some(now);
        let angular=command.twist[2];
        if !angular.is_finite() || !command.twist[0].is_finite() {
            self.reset();result.twist=[0.0;3];return result;
        }
        // Model contract: cmd[2] = wrap(target_yaw - current_yaw), ±0.5 rad.
        // Integration is strictly bounded by the real tick interval.
        let target=wrap(self.target.unwrap_or(measured)+angular.clamp(-0.3,0.3)*dt);
        self.target=Some(target);
        result.twist=[command.twist[0].clamp(-0.6,0.6), 0.0,
                      wrap(target-measured).clamp(-0.5,0.5)];
        result.body=Default::default();
        result
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::Duration;
    #[test] fn yaw_and_steering_are_wrapped_and_clipped() {
        let mut h=Heading::default();let now=Instant::now();
        let imu=ImuData::default();let c=Command {twist:[0.4,0.0,0.3],..Default::default()};
        assert_eq!(h.adapt(&c,&imu,now).twist,[0.0;3]);
        let a=h.adapt(&c,&imu,now+Duration::from_millis(100));
        assert!((a.twist[2]-0.03).abs()<1e-9);
        let lost=h.adapt(&c,&imu,now+Duration::from_secs(2));
        assert_eq!(lost.twist,[0.0;3]);
    }
    #[test] fn walking_configuration_is_never_touched() {
        let cfg=robotd_params::PolicyParams::default().resolved();
        let a=resolved(cfg.clone(),SPIN_CODE);
        assert_eq!(a.walk,cfg.walk);
        assert_eq!(a.ground_pick,cfg.ground_pick);
    }
    #[test]
    fn both_roller_actions_load_with_the_complete_shipped_configuration() {
        let params: crate::Params = toml::from_str(include_str!(
            "../../packaging/robotd-profile.toml"
        )).unwrap();
        let mut base = params.policy.resolved();
        base.mode = Mode::Roller;
        let fixture = Path::new(env!("CARGO_MANIFEST_DIR")).join("../packaging");
        let relocate = |path: &Path| {
            fixture.join(path.strip_prefix("/opt/robot/feetech-ft5-r5").unwrap())
        };
        for code in [CROUCH_CODE, SPIN_CODE] {
            let mut cfg = resolved(base.clone(), code);
            cfg.walk = relocate(&cfg.walk);
            for path in [&mut cfg.stand, &mut cfg.sitstand, &mut cfg.ground_pick,
                         &mut cfg.kick_left, &mut cfg.kick_right, &mut cfg.roulade] {
                if let Some(value) = path { *value = relocate(value); }
            }
            for skill in &mut cfg.skills {
                if let Some(path) = &mut skill.path {
                    if path.is_absolute() { *path = relocate(path); }
                }
            }
            let mut controller = crate::try_controller(&cfg, false).unwrap().unwrap();
            let sensors = duck_control::Sensors::default();
            controller.step(&sensors, &Command::default(), false, 0.02, 1.0).unwrap();
            assert_eq!(controller.applied_action_scale(), Some(1.0));
            assert_eq!(controller.active_target_filters(), (1.0, 1.0));
            controller.start_ground_pick().unwrap();
            controller.step(&sensors, &Command::default(), false, 0.02, 1.0).unwrap();
            let expected = if code == CROUCH_CODE { (0.8, (0.5, 0.7)) }
                else { (1.0, (1.0, 1.0)) };
            assert_eq!(controller.applied_action_scale(), Some(expected.0));
            assert_eq!(controller.active_target_filters(), expected.1);
            for _ in 0..180 {
                controller.step(&sensors, &Command::default(), false, 0.02, 1.0).unwrap();
            }
            assert_eq!(controller.applied_action_scale(), Some(1.0));
            assert_eq!(controller.active_target_filters(), (1.0, 1.0));
        }
    }
}

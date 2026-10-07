//! R17 entry guard: starting a stopped policy requires measured HOME and upright IMU.
//! This never gates a policy that is already running (including official fall recovery).
use std::time::{Duration, Instant};

use duck_control::{NUM_JOINTS, io::Sensors, model::MOUTH_INDEX};
use serde::Serialize;

pub const MAX_JOINT_ERROR_DEG: f64 = 5.0;
pub const MAX_TILT_DEG: f64 = 10.0;
const STABLE_SAMPLES: u32 = 3;
const MAX_AGE: Duration = Duration::from_millis(80);

#[derive(Debug, Serialize)]
pub struct Report {
    #[serde(skip)]
    pub at: Instant,
    /// Reuse the existing per-tick report for LB's sensor gate. This is internal
    /// and adds neither a wire field nor a second telemetry snapshot.
    #[serde(skip)]
    pub recovery_sensors_ready: bool,
    pub ready: bool,
    pub reason: String,
    pub stable_samples: u32,
    pub max_joint_error_deg: Option<f64>,
    pub tilt_deg: Option<f64>,
    pub joint_tolerance_deg: f64,
    pub tilt_tolerance_deg: f64,
}

impl Report {
    pub fn recovery_refusal(
        &self,
        now: Instant,
        allow_upright: bool,
        fallen: bool,
    ) -> Option<String> {
        if now.saturating_duration_since(self.at) > MAX_AGE || !self.recovery_sensors_ready {
            Some("LB 起身需要新鲜、完整的关节反馈和已确认方向的就绪 IMU，请恢复后重新按键".into())
        } else if !allow_upright && !fallen {
            Some("卸力或回 HOME 途中，仅确认倒地后可按 LB 起身".into())
        } else {
            None
        }
    }

    pub fn refusal(&self, now: Instant) -> Option<String> {
        if now.saturating_duration_since(self.at) > MAX_AGE {
            Some("不能进入保持：HOME / IMU 反馈已过期，请回 HOME 后重新按键".into())
        } else if !self.ready {
            Some(format!(
                "不能进入保持：{}；请回 HOME、扶正后重新按键",
                self.reason
            ))
        } else {
            None
        }
    }
}

/// The same fresh sample requirement is used at IPC and again before the
/// recovery's first inference. HOME angle/torque are deliberately not included:
/// fallen limp recovery owns the explicit torque-on edge itself.
pub fn recovery_sensors_ready(
    sensors: Option<&Sensors>,
    all_joints_fresh: bool,
    imu_ready: bool,
) -> bool {
    all_joints_fresh
        && imu_ready
        && sensors.is_some_and(|s| {
            let norm = s.imu.gravity.iter().map(|v| v * v).sum::<f64>();
            s.positions
                .iter()
                .chain(&s.velocities)
                .chain(&s.imu.gyro)
                .all(|v| v.is_finite())
                && norm.is_finite()
                && norm > 0.25
                && norm < 2.25
        })
}

#[derive(Default)]
pub struct Guard {
    stable: u32,
    last_good: Option<Instant>,
}

pub struct Conditions {
    pub home_phase: bool,
    pub all_joints_fresh: bool,
    pub imu_ready: bool,
    pub torque_confirmed: bool,
}

impl Guard {
    pub fn observe(
        &mut self,
        at: Instant,
        sensors: Option<&Sensors>,
        home: &[f64; NUM_JOINTS],
        conditions: Conditions,
    ) -> Report {
        let max_error = sensors.and_then(|s| {
            // The independently controlled beak does not determine the HOME stance.
            s.positions
                .iter()
                .zip(home)
                .enumerate()
                .filter(|(i, _)| *i != MOUTH_INDEX)
                .try_fold(0.0_f64, |largest, (_, (actual, target))| {
                    (actual.is_finite() && target.is_finite())
                        .then(|| largest.max((actual - target).abs().to_degrees()))
                })
        });
        let tilt = sensors.and_then(|s| {
            let [x, y, z] = s.imu.gravity;
            let norm = (x * x + y * y + z * z).sqrt();
            (norm.is_finite() && norm > 0.5 && norm < 1.5)
                .then(|| (-z / norm).clamp(-1.0, 1.0).acos().to_degrees())
        });
        let reason = if !conditions.home_phase {
            Some("尚未完成回 HOME，或正在卸力 / 关机")
        } else if sensors.is_none() || !conditions.all_joints_fresh {
            Some("舵机反馈不完整或不新鲜")
        } else if !conditions.imu_ready {
            Some("IMU 安装方向未确认或姿态尚未就绪")
        } else if !conditions.torque_confirmed {
            Some("尚未确认所有关节已上力")
        } else if max_error.is_none_or(|v| v > MAX_JOINT_ERROR_DEG) {
            Some("关节实际位置尚未到 HOME（允许误差 5°）")
        } else if tilt.is_none_or(|v| v > MAX_TILT_DEG) {
            Some("机身未直立（倾斜超过 10° 或 IMU 无效）")
        } else {
            None
        };
        if reason.is_none() {
            if self
                .last_good
                .is_none_or(|last| at.saturating_duration_since(last) > MAX_AGE)
            {
                self.stable = 0;
            }
            self.stable = self.stable.saturating_add(1).min(STABLE_SAMPLES);
            self.last_good = Some(at);
        } else {
            self.stable = 0;
            self.last_good = None;
        }
        Report {
            at,
            recovery_sensors_ready: recovery_sensors_ready(
                sensors,
                conditions.all_joints_fresh,
                conditions.imu_ready,
            ),
            ready: reason.is_none() && self.stable >= STABLE_SAMPLES,
            reason: reason
                .unwrap_or(if self.stable >= STABLE_SAMPLES {
                    "实际 HOME 且机身直立"
                } else {
                    "正在确认实际 HOME 和直立姿态（连续 3 帧）"
                })
                .into(),
            stable_samples: self.stable,
            max_joint_error_deg: max_error,
            tilt_deg: tilt,
            joint_tolerance_deg: MAX_JOINT_ERROR_DEG,
            tilt_tolerance_deg: MAX_TILT_DEG,
        }
    }
}

/// Recheck the exact sample used for the first inference, not only the IPC snapshot.
/// Explicit enable edges are distinct from temporary pauses due to a bus drop or IMU.
pub fn check_edge(enabled: &mut bool, latched: &mut bool, report: &Report) -> Option<String> {
    if !*enabled {
        *latched = false;
        return None;
    }
    if *latched {
        return None;
    }
    if let Some(reason) = report.refusal(Instant::now()) {
        *enabled = false;
        return Some(reason);
    }
    *latched = true;
    None
}

#[cfg(test)]
mod tests {
    use super::*;
    fn conditions() -> Conditions {
        Conditions {
            home_phase: true,
            all_joints_fresh: true,
            imu_ready: true,
            torque_confirmed: true,
        }
    }
    fn sample() -> Sensors {
        let mut s = Sensors::default();
        s.imu.gravity = [0.0, 0.0, -1.0];
        s
    }
    fn ready(g: &mut Guard, s: &Sensors, home: &[f64; NUM_JOINTS]) -> Report {
        g.observe(Instant::now(), Some(s), home, conditions());
        g.observe(Instant::now(), Some(s), home, conditions());
        g.observe(Instant::now(), Some(s), home, conditions())
    }
    #[test]
    fn limp_recovery_needs_live_fallen_feedback_without_upright_home() {
        let mut s = sample();
        s.imu.gravity = [1.0, 0.0, 0.0];
        s.positions[3] = 0.8;
        let mut c = conditions();
        c.home_phase = false;
        c.torque_confirmed = false;
        let r = Guard::default().observe(Instant::now(), Some(&s), &[0.0; NUM_JOINTS], c);
        assert!(!r.ready);
        assert!(r.recovery_refusal(Instant::now(), false, true).is_none());
        assert!(r.recovery_refusal(Instant::now(), false, false).is_some());
        assert!(
            r.recovery_refusal(r.at + MAX_AGE + Duration::from_millis(1), false, true)
                .is_some()
        );
        assert!(!recovery_sensors_ready(None, true, true));
        assert!(!recovery_sensors_ready(Some(&s), false, true));
        assert!(!recovery_sensors_ready(Some(&s), true, false));
        s.velocities[0] = f64::NAN;
        assert!(!recovery_sensors_ready(Some(&s), true, true));
    }

    #[test]
    fn actual_home_is_required_even_after_the_ramp() {
        let mut g = Guard::default();
        let mut s = sample();
        s.positions[0] = 6_f64.to_radians();
        let r = ready(&mut g, &s, &[0.0; NUM_JOINTS]);
        assert!(!r.ready);
        assert!(r.reason.contains("实际位置"));
    }
    #[test]
    fn tilt_and_invalid_gravity_block_start() {
        for gravity in [
            [0.5, 0.0, -0.866],
            [0.0, 0.0, 1.0],
            [0.0; 3],
            [f64::NAN, 0.0, -1.0],
        ] {
            let mut s = sample();
            s.imu.gravity = gravity;
            assert!(!ready(&mut Guard::default(), &s, &[0.0; NUM_JOINTS]).ready);
        }
    }
    #[test]
    fn incomplete_sensors_torque_and_homing_each_block_start() {
        let s = sample();
        let home = [0.0; NUM_JOINTS];
        for index in 0..4 {
            let mut c = conditions();
            match index {
                0 => c.home_phase = false,
                1 => c.all_joints_fresh = false,
                2 => c.imu_ready = false,
                _ => c.torque_confirmed = false,
            }
            assert!(
                !Guard::default()
                    .observe(Instant::now(), Some(&s), &home, c)
                    .ready
            );
        }
        assert!(
            !Guard::default()
                .observe(Instant::now(), None, &home, conditions())
                .ready
        );
    }
    #[test]
    fn home_uses_the_model_contract_and_beak_remains_independent() {
        let mut s = sample();
        s.positions = [0.5; NUM_JOINTS];
        s.positions[MOUTH_INDEX] = 1.2;
        assert!(ready(&mut Guard::default(), &s, &[0.5; NUM_JOINTS]).ready);
        assert!(!ready(&mut Guard::default(), &s, &[0.0; NUM_JOINTS]).ready);
        s.positions[2] = f64::NAN;
        assert!(!ready(&mut Guard::default(), &s, &[0.5; NUM_JOINTS]).ready);
    }
    #[test]
    fn stable_frames_reset_on_a_gap_and_ready_feedback_expires() {
        let s = sample();
        let mut g = Guard::default();
        let now = Instant::now();
        let home = [0.0; NUM_JOINTS];
        assert!(!g.observe(now, Some(&s), &home, conditions()).ready);
        assert!(
            !g.observe(
                now + Duration::from_millis(100),
                Some(&s),
                &home,
                conditions()
            )
            .ready
        );
        let r = ready(&mut g, &s, &home);
        assert!(r.ready);
        assert!(r.refusal(r.at + Duration::from_millis(81)).is_some());
    }
    #[test]
    fn first_inference_rechecks_home_and_never_queues_a_rejected_press() {
        let mut s = sample();
        s.positions[0] = 1.0;
        let bad = ready(&mut Guard::default(), &s, &[0.0; NUM_JOINTS]);
        let mut on = true;
        let mut latched = false;
        assert!(check_edge(&mut on, &mut latched, &bad).is_some());
        assert!(!on);
        assert!(!latched);
        let good = ready(&mut Guard::default(), &sample(), &[0.0; NUM_JOINTS]);
        assert!(check_edge(&mut on, &mut latched, &good).is_none());
        assert!(!on, "HOME becoming ready cannot replay a rejected press");
        on = true;
        assert!(check_edge(&mut on, &mut latched, &good).is_none());
        assert!(latched);
        assert!(check_edge(&mut on, &mut latched, &bad).is_none());
        assert!(on, "already running fall recovery must continue");
        on = false;
        check_edge(&mut on, &mut latched, &bad);
        assert!(!latched);
        on = true;
        assert!(check_edge(&mut on, &mut latched, &bad).is_some());
    }
}

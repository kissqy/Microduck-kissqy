use super::*;
use duck_control::{Sensors, imu::ImuData, policy::PolicyPaths};
use std::path::{Path, PathBuf};

const JOINT_SHA: &str = "1cbf8730eadd75a5704332c9f3c10f60bfa9412135b907831c9dbd731ce1795f";

fn directory() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../policies/walk")
}

fn controller(path: &Path) -> Controller {
    Controller::new(
        Policy::load(
            &PolicyPaths {
                walk: path.join("policy.onnx"),
                ..Default::default()
            },
            0.05,
        )
        .unwrap(),
        Tuning {
            action_scale: 0.63,
            head_lowpass: Some(0.42),
            legs_lowpass: Some(0.68),
            ..Tuning::default()
        },
        SkillTuning::default(),
    )
}

fn without_override() -> tempfile::TempDir {
    let temp = tempfile::tempdir().unwrap();
    for name in [
        "policy.onnx",
        "deployment-contract.json",
        "manifest.json",
        "deployment-runtime.json",
    ] {
        let from = directory().join(name);
        if from.exists() {
            std::fs::copy(from, temp.path().join(name)).unwrap();
        }
    }
    temp
}

fn sensors(home: [f64; NUM_JOINTS], tilt: f64) -> Sensors {
    let angle = tilt.to_radians();
    Sensors {
        positions: home,
        imu: ImuData {
            gravity: [angle.sin(), 0.0, -angle.cos()],
            ..Default::default()
        },
        ..Default::default()
    }
}

/// The exported training mapping remains available without the separate runtime
/// choice. Previously saved settings for a different gait must not silently scale it.
#[test]
fn joint_without_profile_keeps_training_baseline_at_every_posture() {
    let plain = without_override();
    let mut c = controller(plain.path());
    let home = c.policy.contract(Net::Walk).unwrap().home;
    for (angle, voltage) in [
        (0.0, 1.0),
        (90.0, 1.1),
        (180.0, 0.95),
        (-90.0, 1.0),
        (0.0, 1.0),
    ] {
        let step = c
            .step(
                &sensors(home, angle),
                &Command::default(),
                false,
                0.02,
                voltage,
            )
            .unwrap();
        assert_eq!(step.label, "walk");
        assert_eq!(c.active_model().unwrap().sha256, JOINT_SHA);
        assert_eq!(c.applied_action_scale(), Some(voltage));
        assert_eq!(c.active_target_filters(), (1.0, 1.0));
        assert!(!c.active_uniform_profile());
        let offsets = Observation::scatter_action(&c.last_action);
        for j in 0..NUM_JOINTS {
            assert!((step.targets[j] - home[j] - voltage * offsets[j]).abs() < 1e-9);
        }
    }
}

/// The real ONNX sees identical raw previous-action observations in both runs.
/// The uniform run changes only HOME+scale and the official per-target EMA arithmetic;
/// upright, prone, supine, side and zero/nonzero commands cannot select another tuning.
#[test]
fn joint_uniform_real_onnx_uses_point_nine_and_official_filters_in_every_posture() {
    let plain = without_override();
    let mut c = controller(&directory());
    let mut raw = controller(plain.path());
    let home = c.policy.contract(Net::Walk).unwrap().home;
    let mut previous: Option<[f64; NUM_JOINTS]> = None;
    for i in 0..48 {
        let angle = [0.0, 35.0, 90.0, 180.0, -90.0, 25.0, 40.0, 0.0][i % 8];
        let voltage = [1.0, 1.1, 0.95][i % 3];
        let command = Command {
            twist: if i % 2 == 0 {
                [0.15, 0.0, 0.2]
            } else {
                [0.0; 3]
            },
            ..Default::default()
        };
        let sample = sensors(home, angle);
        let step = c.step(&sample, &command, false, 0.02, voltage).unwrap();
        raw.step(&sample, &command, false, 0.02, voltage).unwrap();
        assert_eq!(
            c.last_action, raw.last_action,
            "frame {i}: do not feed scaled/filtered targets back into the actor"
        );
        assert_eq!(step.label, "walk");
        assert!(!step.busy);
        assert!(c.active_uniform_profile());
        assert_eq!(c.applied_action_scale(), Some(0.9 * voltage));
        assert_eq!(c.active_target_filters(), (0.5, 0.7));
        let offsets = Observation::scatter_action(&c.last_action);
        let mut expected = std::array::from_fn(|j| home[j] + 0.9 * voltage * offsets[j]);
        if let Some(before) = previous {
            for j in 0..NUM_JOINTS {
                let alpha = if HEAD_JOINTS.contains(&j) {
                    0.5
                } else if j == duck_control::model::MOUTH_INDEX {
                    1.0
                } else {
                    0.7
                };
                expected[j] = alpha * expected[j] + (1.0 - alpha) * before[j];
            }
        }
        for j in 0..NUM_JOINTS {
            assert!(
                (step.targets[j] - expected[j]).abs() < 1e-9,
                "frame {i}, joint {j}"
            );
        }
        previous = Some(expected);
        assert_eq!(c.active_model().unwrap().sha256, JOINT_SHA);
    }
    let metadata = serde_json::to_value(c.active_model().unwrap()).unwrap();
    assert_eq!(metadata["runtime_execution_profile"]["mode"], "uniform");
    assert_eq!(metadata["runtime_execution_profile"]["action_scale"], 0.9);
    assert_eq!(
        metadata["runtime_execution_profile"]["model_sha256"],
        JOINT_SHA
    );
}

#[test]
fn joint_uniform_reload_keeps_raw_memory_and_reset_clears_it() {
    let mut original = controller(&directory());
    let home = original.policy.contract(Net::Walk).unwrap().home;
    let sample = sensors(home, 90.0);
    original
        .step(&sample, &Command::default(), false, 0.02, 1.0)
        .unwrap();
    let mut replacement = controller(&directory());
    replacement.carry_over(&original);
    assert_eq!(replacement.last_action, original.last_action);
    assert_eq!(replacement.previous, original.previous);
    assert_eq!(
        replacement.active_target_filters(),
        original.active_target_filters()
    );
    let a = original
        .step(&sample, &Command::default(), false, 0.02, 1.0)
        .unwrap();
    let b = replacement
        .step(&sample, &Command::default(), false, 0.02, 1.0)
        .unwrap();
    assert_eq!(a.targets, b.targets);
    replacement.reset_for_home();
    assert_eq!(replacement.last_action, [0.0; ACTION_LEN]);
    assert!(replacement.previous.is_none());
    assert!(replacement.applied_action_scale().is_none());
    let mut fresh = controller(&directory());
    let a = replacement
        .step(&sample, &Command::default(), false, 0.02, 1.0)
        .unwrap();
    let b = fresh
        .step(&sample, &Command::default(), false, 0.02, 1.0)
        .unwrap();
    assert_eq!(a.targets, b.targets);
}

/// LB keeps its independent unfiltered 11000-round teacher. Expiring that skill returns
/// to the new single Walk, with its uniform tuning and the existing target-history handoff.
#[test]
fn joint_uniform_keeps_manual_lb_teacher_and_returns_to_new_walk() {
    let config: robotd_params::Params =
        toml::from_str(include_str!("../../packaging/robotd-profile.toml")).unwrap();
    let mut skill = config
        .policy
        .skills
        .into_iter()
        .find(|s| s.name == "stand_test")
        .unwrap();
    skill.path = Some(Path::new(env!("CARGO_MANIFEST_DIR")).join("../policies/stand/policy.onnx"));
    let mut c = Controller::new(
        Policy::load(
            &PolicyPaths {
                walk: directory().join("policy.onnx"),
                skills: vec![skill.resolved_path().unwrap()],
                ..Default::default()
            },
            0.05,
        )
        .unwrap(),
        Tuning::default(),
        SkillTuning {
            skills: vec![skill],
            ..Default::default()
        },
    );
    let home = c.policy.contract(Net::Walk).unwrap().home;
    let sample = sensors(home, 90.0);
    assert!(c.start_skill(0).unwrap());
    for _ in 0..300 {
        assert_eq!(
            c.step(&sample, &Command::default(), false, 0.02, 1.1)
                .unwrap()
                .label,
            "stand_test"
        );
        assert_eq!(c.applied_action_scale(), Some(1.1));
        assert_eq!(c.active_target_filters(), (1.0, 1.0));
        assert!(!c.active_uniform_profile());
        assert_eq!(
            c.active_model().unwrap().sha256,
            "a481d9f211f31d9476ab1a319fe362a21ef0879d9fa59442a122845af598268c"
        );
    }
    for _ in 0..2 {
        c.step(&sample, &Command::default(), false, 0.02, 1.1)
            .unwrap();
    }
    assert_eq!(c.active_model().unwrap().sha256, JOINT_SHA);
    assert!(c.active_uniform_profile());
    assert_eq!(c.applied_action_scale(), Some(0.9 * 1.1));
    assert_eq!(c.active_target_filters(), (0.5, 0.7));
}

#[test]
fn joint_failed_inference_clears_applied_readback_without_poisoning_feedback() {
    let mut c = controller(&directory());
    let home = c.policy.contract(Net::Walk).unwrap().home;
    let sample = sensors(home, 90.0);
    c.step(&sample, &Command::default(), false, 0.02, 1.0)
        .unwrap();
    assert!(c.active_uniform_profile());
    let previous_action = c.last_action;
    let previous_target = c.previous;
    let mut invalid = sample;
    invalid.imu.gyro[0] = f64::NAN;
    assert!(
        c.step(&invalid, &Command::default(), false, 0.02, 1.0)
            .is_err()
    );
    assert!(c.applied_action_scale().is_none());
    assert!(c.applied_target_filters.is_none());
    assert!(!c.active_uniform_profile());
    assert_eq!(c.last_action, previous_action);
    assert_eq!(c.previous, previous_target);
}

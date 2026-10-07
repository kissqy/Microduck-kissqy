use super::*;
use duck_control::{Sensors, imu::ImuData, obs::BodyPose, policy::PolicyPaths};
const WALK_SHA: &str = "0b8f04476cab068f6db14b4b088562129b5eca3f1d6164ab5d9d34cda5ea1432";
const PICK_SHA: &str = "2b69fa681ed06f7ded9e2a2d12ba5c6776ec87308ac4a299e4b8196199c17f24";
const ROLL_SHA: &str = "8fdaf12c7478a8314a63647a466bfa34ba1f15a7d9a5cb3b6ffa242719666168";
const JOINT_SHA: &str = "5c019c3d3d2c490947f21974f394750671b0ec7b7a2d1e36734e82c8a3c9225b";
fn paths() -> PolicyPaths {
    PolicyPaths {
        walk: concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../test-data/walk-teacher10000/policy.onnx"
        )
        .into(),
        sitstand: Some(
            concat!(
                env!("CARGO_MANIFEST_DIR"),
                "/../policies/sitstand/policy.onnx"
            )
            .into(),
        ),
        ..Default::default()
    }
}
fn policy() -> Policy {
    let mut p = Policy::load(&paths(), 0.05).unwrap();
    p.set_standing_disabled(true);
    p
}

/// Recovery uses full scale independently of walking; training scale is not
/// applied a second time. Binding here exercises the optional Stand slot.
#[test]
fn flat_stand_uses_full_scale_and_walk_remains_the_existing_teacher() {
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../policies");
    for scale in [0.7, 0.63] {
        let p = Policy::load(
            &PolicyPaths {
                walk: root.join("../test-data/walk-teacher14000/policy.onnx"),
                stand: Some(root.join("stand/policy.onnx")),
                ..Default::default()
            },
            0.05,
        )
        .unwrap();
        let mut c = Controller::new(
            p,
            Tuning {
                action_scale: scale,
                standing_action_scale: 1.0,
                ..Tuning::default()
            },
            SkillTuning::default(),
        );
        let home = c.policy.contract(Net::Walk).unwrap().home;
        let sensors = Sensors {
            positions: home,
            ..Default::default()
        };
        let mut previous = None;
        for (twist, label, sha) in [
            (
                [0.0; 3],
                "stand",
                "a481d9f211f31d9476ab1a319fe362a21ef0879d9fa59442a122845af598268c",
            ),
            (
                [0.25, 0.0, 0.0],
                "walk",
                "9e3ff8bde021be28a728c02dbd8e7aaf9b447dd75545dacaa72ccec8e9ec7e6c",
            ),
        ] {
            let result = c
                .step(
                    &sensors,
                    &Command {
                        twist,
                        ..Default::default()
                    },
                    false,
                    0.02,
                    1.1,
                )
                .unwrap();
            assert_eq!(result.label, label);
            assert_eq!(c.active_model().unwrap().sha256, sha);
            let active_scale = if label == "stand" { 1.0 } else { scale };
            assert_eq!(c.applied_action_scale, Some(active_scale * 1.1));
            let offsets = Observation::scatter_action(&c.last_action);
            let expected = filtered(
                std::array::from_fn(|j| home[j] + offsets[j] * active_scale * 1.1),
                previous,
            );
            for j in 0..NUM_JOINTS {
                assert!(
                    (result.targets[j] - expected[j]).abs() < 1e-6,
                    "{label} joint {j}"
                );
            }
            previous = Some(expected);
        }
    }
}

/// LB starts the teacher through the existing named-skill window, never the
/// automatic Stand slot. It expires at six seconds and HOME cancels it early.
#[test]
fn lb_recovery_test_runs_official_skill_and_returns_to_original_walk() {
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../policies");
    let config: robotd_params::Params =
        toml::from_str(include_str!("../../packaging/robotd-profile.toml")).unwrap();
    assert_eq!(config.pad.lb, "stand_test");
    assert_eq!(config.policy.stand.as_ref().unwrap().to_str(), Some("none"));
    let mut skill = config
        .policy
        .skills
        .into_iter()
        .find(|s| s.name == "stand_test")
        .unwrap();
    skill.path = Some(root.join("stand/policy.onnx"));
    let p = Policy::load(
        &PolicyPaths {
            walk: root.join("../test-data/walk-teacher14000/policy.onnx"),
            skills: vec![skill.resolved_path().unwrap()],
            ..Default::default()
        },
        0.05,
    )
    .unwrap();
    let home = p.contract(Net::Walk).unwrap().home;
    let mut c = Controller::new(
        p,
        Tuning {
            action_scale: 0.63,
            ..Tuning::default()
        },
        SkillTuning {
            skills: vec![skill],
            ..SkillTuning::default()
        },
    );
    let sensors = Sensors {
        positions: home,
        ..Default::default()
    };
    let command = Command::default();
    let first = c.step(&sensors, &command, false, 0.02, 1.0).unwrap();
    assert_eq!(first.label, "walk");
    assert!(c.start_skill(0).unwrap());
    for _ in 0..300 {
        let step = c.step(&sensors, &command, false, 0.02, 1.0).unwrap();
        assert_eq!(step.label, "stand_test");
        assert_eq!(
            c.active_model().unwrap().sha256,
            "a481d9f211f31d9476ab1a319fe362a21ef0879d9fa59442a122845af598268c"
        );
        assert_eq!(c.applied_action_scale, Some(1.0));
        assert_eq!(c.active_target_filters(), (1.0, 1.0));
        let home = c.policy.contract(Net::Skill(0)).unwrap().home;
        let offsets = Observation::scatter_action(&c.last_action);
        for joint in 0..NUM_JOINTS {
            assert!((step.targets[joint] - home[joint] - offsets[joint]).abs() < 1e-6);
        }
    }
    // The native window advances after inference; floating-point accumulation
    // can leave the last frame in the window. It must return within one tick.
    let _ = c.step(&sensors, &command, false, 0.02, 1.0).unwrap();
    assert_eq!(
        c.step(&sensors, &command, false, 0.02, 1.0).unwrap().label,
        "walk"
    );
    assert_eq!(
        c.active_model().unwrap().sha256,
        "9e3ff8bde021be28a728c02dbd8e7aaf9b447dd75545dacaa72ccec8e9ec7e6c"
    );
    assert_eq!(c.applied_action_scale, Some(0.63));
    assert_eq!(c.active_target_filters(), (0.5, 0.7));
    c.start_skill(0).unwrap();
    c.reset_for_home();
    assert!(!c.busy());
    assert_eq!(
        c.step(&sensors, &command, false, 0.02, 1.0).unwrap().label,
        "walk"
    );
}
fn controller(scale: Option<f64>) -> Controller {
    Controller::new(
        policy(),
        Tuning {
            action_scale: scale.unwrap_or(0.9),
            ..Tuning::default()
        },
        SkillTuning::default(),
    )
}

#[test]
fn explicit_home_ends_sitting_and_rising_and_resumes_the_walk_teacher() {
    let mut c = controller(None);
    let sensors = Sensors {
        positions: c.policy.contract(Net::Walk).unwrap().home,
        ..Default::default()
    };
    for rising in [false, true] {
        c.sit_toggle().unwrap();
        assert_eq!(
            c.step(&sensors, &Command::default(), false, 0.02, 1.0)
                .unwrap()
                .label,
            "sit"
        );
        if rising {
            c.sit_toggle().unwrap();
        }
        c.reset_for_home();
        assert!(!c.is_sitting());
        assert!(!c.busy());
        assert!(c.active_model().is_none());
        assert_eq!(
            c.step(&sensors, &Command::default(), false, 0.02, 1.0)
                .unwrap()
                .label,
            "walk"
        );
        assert_eq!(c.active_model().unwrap().sha256, WALK_SHA);
    }
}

#[test]
fn a_feedback_reset_still_preserves_an_intentionally_seated_robot() {
    let mut c = controller(None);
    c.sit_toggle().unwrap();
    c.reset();
    assert!(c.is_sitting());
    let sensors = Sensors {
        positions: c.policy.contract(Net::Walk).unwrap().home,
        ..Default::default()
    };
    assert_eq!(
        c.step(&sensors, &Command::default(), false, 0.02, 1.0)
            .unwrap()
            .label,
        "sit"
    );
}
fn filtered(raw: [f64; 15], previous: Option<[f64; 15]>) -> [f64; 15] {
    std::array::from_fn(|j| {
        let alpha = if HEAD_JOINTS.contains(&j) {
            0.5
        } else if j == duck_control::model::MOUTH_INDEX {
            1.0
        } else {
            0.7
        };
        previous.map_or(raw[j], |p| alpha * raw[j] + (1.0 - alpha) * p[j])
    })
}
#[derive(serde::Deserialize)]
struct Frame {
    reset: bool,
    positions: [f64; 15],
    velocities: [f64; 15],
    gyro: [f64; 3],
    gravity: [f64; 3],
    twist: [f64; 3],
    head: [f64; 4],
    body: [f64; 3],
    targets: [f64; 15],
}

#[test]
fn real_python_onnx_export_matches_controller_with_official_filters_40_frames() {
    let mut c = controller(None);
    let home = c.policy.contract(Net::Walk).unwrap().home;
    let mut previous = None;
    let mut maximum = 0.0_f64;
    let frames: Vec<Frame> =
        serde_json::from_str(include_str!("../test-data/selftrained-reference.json")).unwrap();
    for f in frames {
        if f.reset {
            c.reset();
            previous = None;
        }
        let sensors = Sensors {
            positions: f.positions,
            velocities: f.velocities,
            imu: ImuData {
                gyro: f.gyro,
                gravity: f.gravity,
                ..Default::default()
            },
            ..Default::default()
        };
        let command = Command {
            twist: f.twist,
            head: f.head,
            body: BodyPose {
                z: f.body[0],
                roll: f.body[1],
                pitch: f.body[2],
            },
        };
        let raw = std::array::from_fn(|j| home[j] + 0.9 * (f.targets[j] - home[j]));
        let expected = filtered(raw, previous);
        previous = Some(expected);
        let got = c.step(&sensors, &command, false, 0.02, 1.0).unwrap();
        for (a, b) in got.targets.into_iter().zip(expected) {
            maximum = maximum.max((a - b).abs());
        }
    }
    assert!(maximum < 1e-6, "maximum target error {maximum}");
}

#[test]
fn loaded_network_digest_is_the_new_walk_and_retained_sitstand() {
    let p = policy();
    let identity = p.loaded_model(Net::Walk).unwrap();
    assert_eq!(identity.sha256, WALK_SHA);
    assert_eq!(
        identity.task.as_deref(),
        Some("Mjlab-Velocity-Flat-MicroDuck-V2-HD1910")
    );
    assert_eq!(
        p.loaded_model(Net::SitStand).unwrap().sha256,
        "1c94934c6421ec72ed48079cea74966868a7a59f7d732e0207d0f7bdaeed3c50"
    );
    assert!(!p.has_standing());
    assert!(!p.has_ground_pick());
    assert_eq!(p.skill_count(), 0);
}

#[test]
fn requested_ground_pick_infers_at_official_one_and_returns_to_walk_at_phase_cutoff() {
    let mut model_paths = paths();
    model_paths.ground_pick = Some(
        concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../policies/ground_pick/policy.onnx"
        )
        .into(),
    );
    let make = |scale| {
        Controller::new(
            Policy::load(&model_paths, 0.05).unwrap(),
            Tuning {
                action_scale: scale,
                ..Tuning::default()
            },
            SkillTuning::default(),
        )
    };
    let mut a = make(0.9);
    let mut b = make(0.65);
    assert_eq!(
        a.policy.loaded_model(Net::GroundPick).unwrap().sha256,
        PICK_SHA
    );
    let home = a.policy.contract(Net::GroundPick).unwrap().home;
    let sensors = Sensors {
        positions: home,
        ..Default::default()
    };
    a.start_ground_pick().unwrap();
    b.start_ground_pick().unwrap();
    for _ in 0..140 {
        let x = a
            .step(&sensors, &Command::default(), false, 0.02, 1.0)
            .unwrap();
        let y = b
            .step(&sensors, &Command::default(), false, 0.02, 1.0)
            .unwrap();
        assert_eq!(x.label, "ground_pick");
        assert_eq!(x.targets, y.targets);
        assert!(x.targets.iter().all(|v| v.is_finite()));
        assert_eq!(a.applied_action_scale(), Some(1.0));
        assert_eq!(a.active_model().unwrap().sha256, PICK_SHA);
    }
    assert_eq!(
        a.step(&sensors, &Command::default(), false, 0.02, 1.0)
            .unwrap()
            .label,
        "walk"
    );
    assert_eq!(a.applied_action_scale(), Some(0.9));
    assert_eq!(a.active_model().unwrap().sha256, WALK_SHA);
}

#[test]
fn saved_point_seven_overrides_point_nine_once_and_preserves_raw_feedback() {
    let mut official = controller(None);
    let mut saved = controller(Some(0.7));
    let home = official.policy.contract(Net::Walk).unwrap().home;
    let sensors = Sensors {
        positions: home,
        ..Default::default()
    };
    let command = Command {
        twist: [0.3, 0.0, 0.0],
        ..Default::default()
    };
    for _ in 0..40 {
        let a = official.step(&sensors, &command, false, 0.02, 1.0).unwrap();
        let b = saved.step(&sensors, &command, false, 0.02, 1.0).unwrap();
        for j in 0..15 {
            assert!((b.targets[j] - home[j] - (0.7 / 0.9) * (a.targets[j] - home[j])).abs() < 1e-9);
        }
        assert_eq!(official.last_action, saved.last_action);
    }
    assert_eq!(official.applied_action_scale(), Some(0.9));
    assert_eq!(saved.applied_action_scale(), Some(0.7));
    assert_eq!(saved.active_model().unwrap().sha256, WALK_SHA);
}

#[test]
fn six_directions_and_zero_speed_keep_the_same_official_scale_and_raw_feedback() {
    for twist in [
        [0.3, 0.0, 0.0],
        [-0.3, 0.0, 0.0],
        [0.0, 0.3, 0.0],
        [0.0, -0.3, 0.0],
        [0.0, 0.0, 1.5],
        [0.0, 0.0, -1.5],
    ] {
        let mut c = controller(Some(0.6));
        let mut raw = Controller::new(
            policy(),
            Tuning {
                action_scale: 1.0,
                head_lowpass: None,
                legs_lowpass: None,
                ..Tuning::default()
            },
            SkillTuning::default(),
        );
        let home = c.policy.contract(Net::Walk).unwrap().home;
        let sensors = Sensors {
            positions: home,
            ..Default::default()
        };
        let mut previous = None;
        for tick in 0..75 {
            let cmd = Command {
                twist: if (25..50).contains(&tick) {
                    [0.0; 3]
                } else {
                    twist
                },
                ..Default::default()
            };
            let a = raw.step(&sensors, &cmd, false, 0.02, 1.0).unwrap();
            let b = c.step(&sensors, &cmd, false, 0.02, 1.0).unwrap();
            let expected = filtered(
                std::array::from_fn(|j| home[j] + 0.6 * (a.targets[j] - home[j])),
                previous,
            );
            previous = Some(expected);
            assert_eq!(b.label, "walk");
            for j in 0..15 {
                assert!(
                    (b.targets[j] - expected[j]).abs() < 1e-9,
                    "tick {tick} joint {j}"
                );
            }
            assert_eq!(raw.last_action, c.last_action);
            assert_eq!(c.active_model().unwrap().sha256, WALK_SHA);
            assert_eq!(c.applied_action_scale(), Some(0.6));
        }
    }
}

#[test]
fn sitstand_stays_full_scale_when_global_walk_scale_is_reduced() {
    let mut a = controller(None);
    let mut b = controller(Some(0.6));
    a.sit_toggle().unwrap();
    b.sit_toggle().unwrap();
    let home = a.policy.contract(Net::SitStand).unwrap().home;
    let sensors = Sensors {
        positions: home,
        ..Default::default()
    };
    for _ in 0..40 {
        let x = a
            .step(&sensors, &Command::default(), false, 0.02, 1.0)
            .unwrap();
        let y = b
            .step(&sensors, &Command::default(), false, 0.02, 1.0)
            .unwrap();
        assert_eq!(x.label, "sit");
        assert_eq!(x.targets, y.targets);
        assert_eq!(b.applied_action_scale(), Some(1.0));
    }
}
fn roll_controller(walk_scale: f64) -> Controller {
    let mut model_paths = paths();
    model_paths.skills = vec![
        concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../policies/roulade/policy.onnx"
        )
        .into(),
    ];
    let configured: crate::params::Params =
        toml::from_str(include_str!("../../packaging/robotd-profile.toml")).unwrap();
    let mut roll = configured.policy.skills[0].clone();
    roll.path = Some(model_paths.skills[0].clone());
    Controller::new(
        Policy::load(&model_paths, 0.05).unwrap(),
        Tuning {
            action_scale: walk_scale,
            ..Tuning::default()
        },
        SkillTuning {
            skills: vec![roll],
            ..Default::default()
        },
    )
}
fn sensors_from_frame(f: &Frame) -> Sensors {
    Sensors {
        positions: f.positions,
        velocities: f.velocities,
        imu: ImuData {
            gyro: f.gyro,
            gravity: f.gravity,
            ..Default::default()
        },
        ..Default::default()
    }
}
#[test]
fn roulade_original_onnx_and_manifest_scale_match_independent_reference() {
    let mut c = roll_controller(0.65);
    assert_eq!(c.loaded_models()["roulade"]["sha256"], ROLL_SHA);
    c.start_skill(0).unwrap();
    let home = c.policy.contract(Net::Skill(0)).unwrap().home;
    let frames: Vec<Frame> =
        serde_json::from_str(include_str!("../test-data/roulade-reference111.json")).unwrap();
    let mut previous = None;
    for f in frames {
        // User stick/head/body values must not leak into this zero-command skill.
        let command = Command {
            twist: f.twist,
            head: f.head,
            body: BodyPose {
                z: f.body[0],
                roll: f.body[1],
                pitch: f.body[2],
            },
            ..Default::default()
        };
        let actual = c
            .step(&sensors_from_frame(&f), &command, true, 0.02, 1.05)
            .unwrap();
        assert_eq!(actual.label, "roulade");
        assert_eq!(c.active_model().unwrap().sha256, ROLL_SHA);
        assert_eq!(c.applied_action_scale(), Some(1.05));
        let raw = std::array::from_fn(|j| home[j] + 1.05 * (f.targets[j] - home[j]));
        let expected = filtered(raw, previous);
        for j in 0..15 {
            assert!((actual.targets[j] - expected[j]).abs() < 2e-5, "joint {j}");
        }
        previous = Some(expected);
    }
    let actual = c
        .step(
            &Sensors {
                positions: home,
                ..Default::default()
            },
            &Command::default(),
            false,
            0.02,
            1.0,
        )
        .unwrap();
    assert_eq!(actual.label, "walk");
    assert_eq!(c.applied_action_scale(), Some(0.65));
}
#[test]
fn roulade_held_button_chains_and_home_cancels_the_episode() {
    let mut c = roll_controller(0.65);
    let sensors = Sensors {
        positions: c.policy.contract(Net::Skill(0)).unwrap().home,
        ..Default::default()
    };
    for _ in 0..120 {
        c.start_skill(0).unwrap();
        assert_eq!(
            c.step(&sensors, &Command::default(), false, 0.02, 1.0)
                .unwrap()
                .label,
            "roulade"
        );
    }
    // Releasing completes the roll in flight, then restores the gait's saved scale.
    for _ in 0..50 {
        c.step(&sensors, &Command::default(), false, 0.02, 1.0)
            .unwrap();
    }
    assert_eq!(c.active_model().unwrap().sha256, WALK_SHA);
    assert_eq!(c.applied_action_scale(), Some(0.65));
    c.start_skill(0).unwrap();
    c.step(&sensors, &Command::default(), false, 0.02, 1.0)
        .unwrap();
    c.reset_for_home();
    assert!(!c.busy());
    assert_eq!(
        c.step(&sensors, &Command::default(), false, 0.02, 1.0)
            .unwrap()
            .label,
        "walk"
    );
}
#[test]
fn joint_walk_remains_selected_when_fallen_and_matches_python_inference() {
    let model_paths = PolicyPaths {
        walk: concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/test-data/joint-audit/policy.onnx"
        )
        .into(),
        ..Default::default()
    };
    let mut c = Controller::new(
        Policy::load(&model_paths, 0.05).unwrap(),
        Tuning::default(),
        SkillTuning::default(),
    );
    let home = c.policy.contract(Net::Walk).unwrap().home;
    let frames: Vec<Frame> =
        serde_json::from_str(include_str!("../test-data/joint-reference111.json")).unwrap();
    let mut previous = None;
    for f in frames {
        if f.reset {
            c.reset();
            previous = None;
        }
        let actual = c
            .step(
                &sensors_from_frame(&f),
                &Command::default(),
                false,
                0.02,
                1.0,
            )
            .unwrap();
        assert_eq!(
            actual.label, "walk",
            "fall recovery belongs to the same walk model"
        );
        assert_eq!(c.active_model().unwrap().sha256, JOINT_SHA);
        assert_eq!(c.applied_action_scale(), Some(0.9));
        let raw = std::array::from_fn(|j| home[j] + 0.9 * (f.targets[j] - home[j]));
        let expected = filtered(raw, previous);
        for j in 0..15 {
            assert!((actual.targets[j] - expected[j]).abs() < 2e-5, "joint {j}");
        }
        previous = Some(expected);
    }
}

#[test]
fn global_filter_off_is_passthrough_and_keeps_original_raw_action_feedback() {
    let mut filtered = roll_controller(0.65);
    let mut direct = roll_controller(0.65);
    direct.tuning.head_lowpass = None;
    direct.tuning.legs_lowpass = None;
    filtered.start_skill(0).unwrap();
    direct.start_skill(0).unwrap();
    let frames: Vec<Frame> =
        serde_json::from_str(include_str!("../test-data/roulade-reference111.json")).unwrap();
    let mut changed = false;
    for f in frames {
        let sensors = sensors_from_frame(&f);
        let a = filtered
            .step(&sensors, &Command::default(), false, 0.02, 1.0)
            .unwrap();
        let b = direct
            .step(&sensors, &Command::default(), false, 0.02, 1.0)
            .unwrap();
        assert_eq!(direct.last_action, filtered.last_action);
        assert_eq!(direct.applied_action_scale(), Some(1.0));
        for j in 0..15 {
            assert!((b.targets[j] - f.targets[j]).abs() < 2e-5);
        }
        changed |= a
            .targets
            .iter()
            .zip(b.targets)
            .any(|(a, b)| (a - b).abs() > 1e-4);
    }
    assert!(changed, "disable actually removes head/leg smoothing");
}

#[test]
fn imported_backlash_teacher_uses_saved_global_tuning_once_and_raw_action_history() {
    #[derive(serde::Deserialize)]
    struct TeacherFrame {
        #[serde(flatten)]
        frame: Frame,
        raw_actions: [f32; 14],
    }
    let model_paths = PolicyPaths {
        walk: concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../test-data/walk-teacher14000/policy.onnx"
        )
        .into(),
        sitstand: paths().sitstand,
        ..Default::default()
    };
    let make = |scale, head, legs| {
        Controller::new(
            Policy::load(&model_paths, 0.05).unwrap(),
            Tuning {
                action_scale: scale,
                head_lowpass: Some(head),
                legs_lowpass: Some(legs),
                ..Tuning::default()
            },
            SkillTuning::default(),
        )
    };
    let mut trained = make(0.7, 0.5, 0.7);
    let mut saved = make(0.63, 0.42, 0.68);
    let home = trained.policy.contract(Net::Walk).unwrap().home;
    let frames: Vec<TeacherFrame> =
        serde_json::from_str(include_str!("../test-data/filtered-teacher-reference.json")).unwrap();
    let mut previous: Option<[f64; 15]> = None;
    for record in frames {
        let f = record.frame;
        if f.reset {
            trained.reset_for_home();
            saved.reset_for_home();
            previous = None;
        }
        let command = Command {
            twist: f.twist,
            head: f.head,
            body: BodyPose {
                z: f.body[0],
                roll: f.body[1],
                pitch: f.body[2],
            },
        };
        let a = trained
            .step(&sensors_from_frame(&f), &command, false, 0.02, 1.0)
            .unwrap();
        let b = saved
            .step(&sensors_from_frame(&f), &command, false, 0.02, 1.0)
            .unwrap();
        let offsets = Observation::scatter_action(&record.raw_actions);
        let mut expected = std::array::from_fn::<_, 15, _>(|j| home[j] + 0.63 * offsets[j]);
        if let Some(p) = previous {
            for j in 0..15 {
                let alpha = if HEAD_JOINTS.contains(&j) {
                    0.42
                } else if j == duck_control::model::MOUTH_INDEX {
                    1.0
                } else {
                    0.68
                };
                expected[j] = alpha * expected[j] + (1.0 - alpha) * p[j];
            }
        }
        previous = Some(expected);
        for j in 0..15 {
            assert!(
                (a.targets[j] - f.targets[j]).abs() < 2e-5,
                "training target joint {j}"
            );
            assert!(
                (b.targets[j] - expected[j]).abs() < 2e-5,
                "saved tuning joint {j}"
            );
        }
        for j in 0..14 {
            assert!((trained.last_action[j] - record.raw_actions[j]).abs() < 2e-5);
        }
        assert_eq!(trained.last_action, saved.last_action);
        assert_eq!(a.label, "walk");
        assert_eq!(trained.applied_action_scale(), Some(0.7));
        assert_eq!(
            trained.active_model().unwrap().sha256,
            "9e3ff8bde021be28a728c02dbd8e7aaf9b447dd75545dacaa72ccec8e9ec7e6c"
        );
    }
    trained.sit_toggle().unwrap();
    assert_eq!(
        trained
            .step(
                &Sensors {
                    positions: home,
                    ..Default::default()
                },
                &Command::default(),
                false,
                0.02,
                1.0
            )
            .unwrap()
            .label,
        "sit"
    );
    trained.reset_for_home();
    assert_eq!(
        trained
            .step(
                &Sensors {
                    positions: home,
                    ..Default::default()
                },
                &Command::default(),
                false,
                0.02,
                1.0
            )
            .unwrap()
            .label,
        "walk"
    );
}

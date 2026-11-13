use super::*;
use duck_control::{Sensors, imu::ImuData, model::MOUTH_INDEX, policy::PolicyPaths};
use std::path::Path;

const ROLL_SHA: &str = "59e15d7b04d0c40e9b11b8a70bdecae6da87a5e096efc204fb58eea304fcbbac";
const PICK_SHA: &str = "b14e3a8b56ddbb8d2d831e727774a168c8f5b00194e3e431ae7593a840498c69";
const WALK_SHA: &str = "1cbf8730eadd75a5704332c9f3c10f60bfa9412135b907831c9dbd731ce1795f";

fn configured() -> (Controller, Policy) {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../policies");
    let paths = PolicyPaths {
        walk: root.join("walk/policy.onnx"),
        ground_pick: Some(root.join("ground_pick/policy.onnx")),
        skills: vec![root.join("roulade/policy.onnx")],
        ..Default::default()
    };
    let cfg: robotd_params::Params =
        toml::from_str(include_str!("../../packaging/robotd-profile.toml")).unwrap();
    assert_eq!(cfg.pad.x, "roulade");
    assert_eq!(cfg.pad.a, "ground_pick");
    let resolved = cfg.policy.resolved();
    let mut roll = resolved
        .skills
        .into_iter()
        .find(|s| s.name == cfg.pad.x)
        .unwrap();
    roll.path = Some(paths.skills[0].clone());
    assert_eq!(roll.params.action_scale, Some(1.0));
    assert_eq!(roll.duration, 1.0);
    assert!(roll.chain);
    let skills = SkillTuning {
        skills: vec![roll],
        ground_pick_period: resolved.ground_pick_period,
        ground_pick_end_phase: resolved.ground_pick_end_phase,
        ground_pick_action_scale: resolved.ground_pick_action_scale,
        ground_pick_gain_ratio: resolved.ground_pick_gain_ratio,
        ..Default::default()
    };
    assert_eq!(skills.ground_pick_period, 4.0);
    assert_eq!(skills.ground_pick_end_phase, 0.7);
    assert_eq!(skills.ground_pick_action_scale, 1.0);
    let c = Controller::new(
        Policy::load(&paths, 0.05).unwrap(),
        Tuning {
            action_scale: 0.63,
            head_lowpass: Some(0.42),
            legs_lowpass: Some(0.68),
            ..Default::default()
        },
        skills,
    );
    (c, Policy::load(&paths, 0.05).unwrap())
}

fn sensors(home: &[f64; NUM_JOINTS], i: usize) -> Sensors {
    let t = i as f64 * 0.02;
    Sensors {
        positions: std::array::from_fn(|j| home[j] + (t + j as f64 * 0.2).sin() * 0.08),
        velocities: std::array::from_fn(|j| (t + j as f64 * 0.2).cos() * 0.08),
        imu: ImuData {
            gyro: [t.sin() * 0.2, t.cos() * 0.1, -0.12],
            gravity: [t.sin(), 0.0, -t.cos()],
            ..Default::default()
        },
        ..Default::default()
    }
}

/// Build the network input without the Controller/Observation builder. Hardware
/// feedback is already encoder-side: neither model asks for synthetic lash,
/// simulated sensor delays or filtered/scaled previous policy outputs.
fn raw_observation(
    s: &Sensors,
    home: &[f64; NUM_JOINTS],
    previous: &[f32; ACTION_LEN],
    twist: [f64; 3],
) -> Observation {
    let mut data = [0.0; 61];
    data[..3].copy_from_slice(&s.imu.gyro.map(|v| v as f32));
    data[3..6].copy_from_slice(&s.imu.gravity.map(|v| v as f32));
    for (slot, joint) in (0..NUM_JOINTS).filter(|j| *j != MOUTH_INDEX).enumerate() {
        data[6 + slot] = (s.positions[joint] - home[joint]) as f32;
        data[20 + slot] = s.velocities[joint] as f32;
    }
    data[34..48].copy_from_slice(previous);
    data[48..51].copy_from_slice(&twist.map(|v| v as f32));
    Observation::from(data)
}

fn assert_direct(c: &Controller, actual: &Step, home: &[f64; NUM_JOINTS], voltage: f64) {
    assert_eq!(c.applied_action_scale(), Some(voltage));
    assert_eq!(c.active_target_filters(), (1.0, 1.0));
    assert!(!c.active_uniform_profile());
    for (slot, joint) in (0..NUM_JOINTS).filter(|j| *j != MOUTH_INDEX).enumerate() {
        let expected = home[joint] + voltage * c.last_action[slot] as f64;
        assert!(
            (actual.targets[joint] - expected).abs() < 1e-9,
            "joint {joint}"
        );
    }
    assert_eq!(actual.targets[MOUTH_INDEX], home[MOUTH_INDEX]);
}

fn assert_returns_to_joint_walk(c: &mut Controller, home: &[f64; NUM_JOINTS]) {
    let before = c.previous.unwrap();
    let step = c
        .step(&sensors(home, 0), &Command::default(), false, 0.02, 1.1)
        .unwrap();
    assert_eq!(step.label, "walk");
    assert_eq!(c.active_model().unwrap().sha256, WALK_SHA);
    assert_eq!(c.applied_action_scale(), Some(1.1));
    assert_eq!(c.active_target_filters(), (0.5, 0.7));
    assert!(c.active_uniform_profile());
    let offsets = Observation::scatter_action(&c.last_action);
    for j in 0..NUM_JOINTS {
        let alpha = if HEAD_JOINTS.contains(&j) {
            0.5
        } else if j == MOUTH_INDEX {
            1.0
        } else {
            0.7
        };
        let expected = alpha * (home[j] + 1.1 * offsets[j]) + (1.0 - alpha) * before[j];
        assert!(
            (step.targets[j] - expected).abs() < 1e-9,
            "return joint {j}"
        );
    }
}

/// A previous Walk EMA target must not contaminate either new direct-target
/// skill, while the normal Walk filter history remains available after it ends.
#[test]
fn new_roulade_original_onnx_uses_direct_targets_raw_feedback_and_existing_window() {
    let (mut c, mut reference) = configured();
    let home = c.policy.contract(Net::Skill(0)).unwrap().home;
    c.step(&sensors(&home, 0), &Command::default(), false, 0.02, 1.0)
        .unwrap();
    let mut previous = c.last_action;
    c.start_skill(0).unwrap();
    for i in 0..50 {
        let sample = sensors(&home, i);
        let expected_raw = reference
            .infer(
                &raw_observation(&sample, &home, &previous, [0.0; 3]),
                Net::Skill(0),
            )
            .unwrap();
        let voltage = [1.0, 1.1, 0.95][i % 3];
        let step = c
            .step(
                &sample,
                &Command {
                    twist: [0.9, -0.4, 0.3],
                    head: [0.3; 4],
                    body: duck_control::obs::BodyPose {
                        z: 0.05,
                        roll: 0.1,
                        pitch: 0.2,
                    },
                },
                false,
                0.02,
                voltage,
            )
            .unwrap();
        assert_eq!(step.label, "roulade");
        assert_eq!(c.active_model().unwrap().sha256, ROLL_SHA);
        assert_eq!(
            c.last_action, expected_raw,
            "raw encoder observation and previous output at frame {i}"
        );
        assert_direct(&c, &step, &home, voltage);
        previous = expected_raw;
    }
    assert_returns_to_joint_walk(&mut c, &home);
}

/// The A-button request still encodes a four-second cycle in cos/sin slots and
/// ends at phase .7 (140 ticks). Pad head/body/twist cannot replace those slots.
#[test]
fn new_backlash_pick_original_onnx_keeps_phase_cutoff_and_encoder_observation() {
    let (mut c, mut reference) = configured();
    let home = c.policy.contract(Net::GroundPick).unwrap().home;
    c.step(&sensors(&home, 0), &Command::default(), false, 0.02, 1.0)
        .unwrap();
    let mut previous = c.last_action;
    let mut phase: f64 = 0.0;
    c.start_ground_pick().unwrap();
    for i in 0..140 {
        let sample = sensors(&home, i);
        let angle = std::f64::consts::TAU * phase;
        let expected_raw = reference
            .infer(
                &raw_observation(&sample, &home, &previous, [angle.cos(), angle.sin(), 0.0]),
                Net::GroundPick,
            )
            .unwrap();
        let voltage = [1.1, 0.95, 1.0][i % 3];
        let step = c
            .step(
                &sample,
                &Command {
                    twist: [0.8, 0.3, -0.2],
                    head: [-0.2; 4],
                    body: duck_control::obs::BodyPose {
                        z: 0.03,
                        roll: -0.1,
                        pitch: -0.2,
                    },
                },
                false,
                0.02,
                voltage,
            )
            .unwrap();
        assert_eq!(step.label, "ground_pick");
        assert_eq!(c.active_model().unwrap().sha256, PICK_SHA);
        assert_eq!(
            c.last_action, expected_raw,
            "phase/encoder/raw action mapping at frame {i}"
        );
        assert_direct(&c, &step, &home, voltage);
        previous = expected_raw;
        phase += 0.02 / 4.0;
    }
    assert!(c.ground_pick.is_none());
    assert_returns_to_joint_walk(&mut c, &home);
}

#[test]
fn new_roulade_still_chains_from_held_pad_requests_and_home_cancels() {
    let (mut c, _) = configured();
    let home = c.policy.contract(Net::Skill(0)).unwrap().home;
    for i in 0..120 {
        c.start_skill(0).unwrap();
        let step = c
            .step(&sensors(&home, i), &Command::default(), false, 0.02, 1.0)
            .unwrap();
        assert_eq!(step.label, "roulade");
        assert_direct(&c, &step, &home, 1.0);
    }
    for _ in 0..50 {
        c.step(&sensors(&home, 0), &Command::default(), false, 0.02, 1.0)
            .unwrap();
    }
    assert_eq!(c.active_model().unwrap().sha256, WALK_SHA);
    c.start_skill(0).unwrap();
    c.reset_for_home();
    assert!(!c.busy());
    assert_eq!(c.last_action, [0.0; ACTION_LEN]);
    assert!(c.previous.is_none());
    let step = c
        .step(&sensors(&home, 0), &Command::default(), false, 0.02, 1.0)
        .unwrap();
    assert_eq!(step.label, "walk");
    assert_eq!(c.active_target_filters(), (0.5, 0.7));
}

#[test]
fn flamingo_toggle_holds_alternates_and_lowers_before_walk() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../policies");
    let paths = PolicyPaths { walk:root.join("walk/policy.onnx"),
        ground_pick:Some(root.join("ground_pick/policy.onnx")),
        sitstand:Some(root.join("sitstand/policy.onnx")),
        skills:vec![root.join("flamingo/policy.onnx"),root.join("roulade/policy.onnx")],
        ..Default::default() };
    let cfg:robotd_params::Params=toml::from_str(include_str!("../../packaging/robotd-profile.toml")).unwrap();
    let defs=cfg.policy.resolved().skills;
    let skill=defs.iter().find(|s|s.name=="flamingo").unwrap().clone();
    assert_eq!((skill.duration,skill.unwind_s,skill.chain),(6.0,2.0,false));
    let mut c=Controller::new(Policy::load(&paths,0.05).unwrap(),Tuning::default(),
        SkillTuning{skills:vec![skill,defs.iter().find(|s|s.name=="roulade").unwrap().clone()],..Default::default()});
    let mut reference=Policy::load(&paths,0.05).unwrap();
    let home=c.policy.contract(Net::Skill(0)).unwrap().home;
    for side in [1.0,-1.0,1.0] {
        assert_eq!(c.start_skill(0),Ok(true));
        // Early cancellation after four seconds still lowers on the same support side.
        for i in 0..201 {
            let sample=sensors(&home,i);let previous=c.last_action;
            let step=c.step(&sample,&Command{twist:[0.8,-0.4,0.3],head:[0.2;4],..Default::default()},false,
                0.02,1.0).unwrap();
            assert_eq!(step.label,"flamingo");assert!(step.busy);
            let expected=reference.infer(&raw_observation(&sample,&home,&previous,[1.0,side,0.0]),Net::Skill(0)).unwrap();
            assert_eq!(c.last_action,expected);assert_direct(&c,&step,&home,1.0);
            assert!(c.start_skill(1).is_err());assert!(c.start_ground_pick().is_err());assert!(c.sit_toggle().is_err());
        }
        assert_eq!(c.start_skill(0),Ok(true)); // second tap lowers
        let mut lower_ticks=0;
        loop {
            let sample=sensors(&home,lower_ticks);let previous=c.last_action;
            let step=c.step(&sample,&Command::default(),false,0.02,1.0).unwrap();
            if step.label=="walk" {
                assert_eq!(lower_ticks,100);assert!(!c.flamingo_active());
                assert_eq!(c.active_target_filters(),(0.5,0.7));
                assert_eq!(c.active_model().unwrap().sha256,WALK_SHA);break;
            }
            assert_eq!(step.label,"flamingo:unwind");
            let expected=reference.infer(&raw_observation(&sample,&home,&previous,[0.0,side,0.0]),Net::Skill(0)).unwrap();
            assert_eq!(c.last_action,expected);assert_direct(&c,&step,&home,1.0);
            assert_eq!(c.start_skill(0),Ok(false)); // no restart, no queued lift
            lower_ticks+=1;assert!(lower_ticks<=100);
        }
        for i in 0..5 {assert_eq!(c.step(&sensors(&home,i),&Command::default(),false,0.02,1.0).unwrap().label,"walk");}
    }
}

#[test]
fn flamingo_times_out_without_success_feedback_and_alternates_after_each_exit() {
    let root=Path::new(env!("CARGO_MANIFEST_DIR")).join("../policies");
    let paths=PolicyPaths{walk:root.join("walk/policy.onnx"),skills:vec![root.join("flamingo/policy.onnx")],..Default::default()};
    let cfg:robotd_params::Params=toml::from_str(include_str!("../../packaging/robotd-profile.toml")).unwrap();
    let mut skill=cfg.policy.resolved().skills.into_iter().find(|s|s.name=="flamingo").unwrap();
    // An old saved V176 duration must not make the attempt immediate or unlimited.
    skill.duration=0.0;
    let mut c=Controller::new(Policy::load(&paths,0.05).unwrap(),Tuning::default(),SkillTuning{skills:vec![skill],..Default::default()});
    let home=c.policy.contract(Net::Walk).unwrap().home;
    let sample=sensors(&home,0); // No successful stance signal: the timeout is unconditional.
    for (cycle,side) in [1.0,-1.0,1.0,-1.0].into_iter().enumerate() {
        assert_eq!(c.start_skill(0),Ok(true));
        assert_eq!(c.flamingo_side,side);
        let mut hold_ticks=0;
        let mut lower_ticks=0;
        for _ in 0..410 {
            let step=c.step(&sample,&Command::default(),false,0.02,1.0).unwrap();
            match step.label.as_ref() {
                "flamingo" => {
                    hold_ticks+=1;
                    if cycle==1 && hold_ticks==50 {assert_eq!(c.start_skill(0),Ok(true));}
                },
                "flamingo:unwind" => {
                    lower_ticks+=1;
                    assert_eq!(c.flamingo_side,side);
                    assert_eq!(c.start_skill(0),Ok(false)); // Neither restart nor queue.
                },
                "walk" => break,
                label => panic!("unexpected phase {label}"),
            }
        }
        if cycle==1 {assert_eq!(hold_ticks,50);}
        else {assert!((300..=301).contains(&hold_ticks),"{hold_ticks}");}
        assert_eq!(lower_ticks,100);
        assert!(!c.flamingo_active());
        assert_eq!(c.active_model().unwrap().sha256,WALK_SHA);
        for _ in 0..5 {assert_eq!(c.step(&sample,&Command::default(),false,0.02,1.0).unwrap().label,"walk");}
    }
}

#[test]
fn flamingo_fall_exits_both_phases_and_never_replays() {
    let root=Path::new(env!("CARGO_MANIFEST_DIR")).join("../policies");
    let paths=PolicyPaths{walk:root.join("walk/policy.onnx"),skills:vec![root.join("flamingo/policy.onnx")],..Default::default()};
    let cfg:robotd_params::Params=toml::from_str(include_str!("../../packaging/robotd-profile.toml")).unwrap();
    let skill=cfg.policy.resolved().skills.into_iter().find(|s|s.name=="flamingo").unwrap();
    let mut c=Controller::new(Policy::load(&paths,0.05).unwrap(),Tuning::default(),SkillTuning{skills:vec![skill],..Default::default()});
    let home=c.policy.contract(Net::Walk).unwrap().home;
    for lowering in [false,true] {
        c.start_skill(0).unwrap();
        if lowering {c.start_skill(0).unwrap();}
        assert!(!c.recover_flamingo_if_fallen(false,true));
        assert!(!c.recover_flamingo_if_fallen(true,false));
        assert!(c.flamingo_active());
        assert!(c.recover_flamingo_if_fallen(true,true));
        assert!(!c.busy());assert!(!c.flamingo_active());
        assert!(!c.recover_flamingo_if_fallen(true,true));
        for i in 0..10 {
            let mut fallen=sensors(&home,i);fallen.imu.gravity=[0.0,0.0,1.0];
            assert_eq!(c.step(&fallen,&Command::default(),false,0.02,1.0).unwrap().label,"walk");
            assert_eq!(c.active_model().unwrap().sha256,WALK_SHA);
            assert_eq!(c.active_target_filters(),(0.5,0.7));
        }
    }
}

#[test]
fn flamingo_busy_seated_and_home_cancel_do_not_replay() {
    let root=Path::new(env!("CARGO_MANIFEST_DIR")).join("../policies");
    let paths=PolicyPaths {walk:root.join("walk/policy.onnx"), sitstand:Some(root.join("sitstand/policy.onnx")),
        ground_pick:Some(root.join("ground_pick/policy.onnx")),skills:vec![root.join("flamingo/policy.onnx")],..Default::default()};
    let cfg:robotd_params::Params=toml::from_str(include_str!("../../packaging/robotd-profile.toml")).unwrap();
    let skill=cfg.policy.resolved().skills.into_iter().find(|s|s.name=="flamingo").unwrap();
    let mut c=Controller::new(Policy::load(&paths,0.05).unwrap(),Tuning::default(),SkillTuning{skills:vec![skill],..Default::default()});
    c.sit_toggle().unwrap();assert!(c.start_skill(0).is_err());
    c.reset_for_home();c.start_ground_pick().unwrap();assert!(c.start_skill(0).is_err());
    c.reset_for_home();assert_eq!(c.start_skill(0),Ok(true));assert!(c.flamingo_active());
    c.reset_for_home();assert!(!c.flamingo_active());assert!(!c.busy());
    let home=c.policy.contract(Net::Walk).unwrap().home;
    assert_eq!(c.step(&sensors(&home,0),&Command::default(),false,0.02,1.0).unwrap().label,"walk");
}

#[test]
fn play_dead_original_onnx_runs_once_and_restores_existing_walk() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../policies");
    let paths = PolicyPaths {
        walk: root.join("walk/policy.onnx"),
        sitstand: Some(root.join("sitstand/policy.onnx")),
        ground_pick: Some(root.join("ground_pick/policy.onnx")),
        skills: vec![root.join("play_dead/policy.onnx"), root.join("roulade/policy.onnx")],
        ..Default::default()
    };
    let cfg: robotd_params::Params =
        toml::from_str(include_str!("../../packaging/robotd-profile.toml")).unwrap();
    let defs = cfg.policy.resolved().skills;
    let mut skill = defs.iter().find(|s| s.name == "play_dead").unwrap().clone();
    assert_eq!((skill.duration, skill.unwind_s, skill.chain), (5.0, 0.0, false));
    skill.duration = 0.0; // Saved settings cannot turn the action into an unlimited hold.
    let mut c = Controller::new(Policy::load(&paths, 0.05).unwrap(), Tuning::default(),
        SkillTuning { skills: vec![skill, defs.iter().find(|s| s.name == "roulade").unwrap().clone()], ..Default::default() });
    let mut reference = Policy::load(&paths, 0.05).unwrap();
    let home = c.policy.contract(Net::Skill(0)).unwrap().home;
    c.sit_toggle().unwrap();
    assert!(c.start_skill(0).is_err());
    c.reset_for_home();
    c.step(&sensors(&home, 0), &Command::default(), false, 0.02, 1.0).unwrap();
    assert_eq!(c.start_skill(0), Ok(true));
    let mut count = 0;
    for i in 0..260 {
        let sample = sensors(&home, i); // Includes lying attitudes: these are part of this skill.
        let previous = c.last_action;
        let step = c.step(&sample, &Command { twist: [0.8, -0.3, 0.2], head: [0.3; 4],
            body: duck_control::obs::BodyPose { z: 0.05, roll: 0.1, pitch: 0.2 } }, false, 0.02, 1.0).unwrap();
        if step.label == "walk" { break; }
        count += 1;
        assert_eq!(step.label, "play_dead");
        assert_eq!(c.active_model().unwrap().sha256,
            "9203bb8f5df15cffaa29f5315a722835c1bd718b940b14330f97556ccab83065");
        let expected = reference.infer(&raw_observation(&sample, &home, &previous, [0.0; 3]), Net::Skill(0)).unwrap();
        assert_eq!(c.last_action, expected, "zero command/raw observation at frame {i}");
        assert_direct(&c, &step, &home, 1.0);
        assert!(c.start_skill(0).is_err());
        assert!(c.start_skill(1).is_err());
        assert!(c.start_ground_pick().is_err());
        assert!(c.sit_toggle().is_err());
    }
    assert!((250..=251).contains(&count), "five-second policy window: {count}");
    assert!(!c.play_dead_active());
    assert!(!c.busy());
    assert_returns_to_joint_walk(&mut c, &home);
    c.start_skill(0).unwrap();
    c.reset_for_home();
    assert!(!c.play_dead_active());
    assert_returns_to_joint_walk_after_reset(&mut c, &home);
}

fn assert_returns_to_joint_walk_after_reset(c: &mut Controller, home: &[f64; NUM_JOINTS]) {
    let step = c.step(&sensors(home, 0), &Command::default(), false, 0.02, 1.0).unwrap();
    assert_eq!(step.label, "walk");
    assert_eq!(c.active_model().unwrap().sha256, WALK_SHA);
    assert_eq!(c.active_target_filters(), (0.5, 0.7));
}

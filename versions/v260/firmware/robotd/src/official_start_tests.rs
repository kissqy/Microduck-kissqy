//! Start through IPC and the real control loop/ONNX, with measured poses that
//! cannot satisfy the retired upright/HOME guard. No physical robot is driven.
use super::feetech_recovery_tests::{RecoveryIo, Trace, bus_status, until};
use super::*;
use std::sync::Mutex;

async fn run_case(name: &str, gravity: [f64; 3], direct_enable: bool) {
    let models = Path::new(env!("CARGO_MANIFEST_DIR")).join("../policies");
        let mut params = Params::default();
        params.bus.protocol = params::BusProtocol::Feetech;
        params.policy.walk = Some(models.join("walk/policy.onnx"));
        params.policy.stand = Some("none".into());
        params.policy.sitstand = Some("none".into());
        params.policy.ground_pick = Some("none".into());
        params.policy.kick_left = Some("none".into());
        params.policy.kick_right = Some("none".into());
        params.policy.roulade = Some("none".into());
        params.safety.limp_fall = false;
        params.audio.enabled = false;
        params.audio.greet = false;
        let path = PathBuf::from("/tmp/unused-v186-official-start.toml");
        let state = Arc::new(RobotState::new(&params, &path, false, false));
        let intents = Arc::new(Intents::new());
        let trace = Arc::new(Mutex::new(Trace::default()));
        let mut sample = duck_control::io::Sensors::default();
        sample.positions = duck_control::deployment::home();
        sample.positions[3] += 20_f64.to_radians();
        sample.imu.gravity = gravity;
        let task = tokio::spawn(control_loop(
            RecoveryIo {
                sensors: sample,
                dropping: Arc::new(AtomicBool::new(false)),
                fail_write: Arc::new(AtomicBool::new(false)),
                trace: trace.clone(),
                missing: 0,
            },
            state.clone(), intents.clone(), params, path,
            Duration::from_millis(5), Arc::new(|| {}),
        ));
        until(|| state.ticks.load(Ordering::Relaxed) > 3).await;
        assert!(!intents.enabled(), "{name}: boot never starts a policy");
        assert!(trace.lock().unwrap().torque.is_empty());
        let call = |c| dispatch(&state, &intents, proto::Id::Number(1), &c)
            .result_as::<proto::IntentResult>().unwrap();
        if !direct_enable {
            let answer = call(proto::Call::RobotInit);
            assert!(answer.accepted, "{name}: {:?}", answer.reason);
            until(|| state.homed.load(Ordering::Relaxed)).await;
            assert!(!intents.enabled(), "{name}: first Start only initializes");
        }
        assert!(!state.home_start.load_full().unwrap().ready,
            "fixture must fail the former HOME gate");
        assert!(call(proto::Call::RobotEnable(proto::EnableParams {
            on: direct_enable, toggle: !direct_enable,
        })).accepted, "{name}: Start accepted");
        until(|| bus_status(&state).is_some_and(|r| {
            r["scale_use"] == "joint_uniform"
                && r["active_model"]["sha256"] == "1cbf8730eadd75a5704332c9f3c10f60bfa9412135b907831c9dbd731ce1795f"
        })).await;
        assert!(intents.enabled(), "{name}: first inference did not cancel enable");
        let report = bus_status(&state).unwrap();
        assert_eq!(report["active_target_filters"]["head_lowpass"], 0.5);
        assert_eq!(report["active_target_filters"]["legs_lowpass"], 0.7);
        assert_eq!(trace.lock().unwrap().torque, [true]);
        assert!(call(proto::Call::RobotEnable(proto::EnableParams {
            on: false, toggle: true,
        })).accepted);
        assert!(!intents.enabled());
        let off_tick = state.ticks.load(Ordering::Relaxed);
        until(|| state.ticks.load(Ordering::Relaxed) > off_tick + 3
            && state.homed.load(Ordering::Relaxed)).await;
        assert!(!intents.enabled(), "{name}: HOME does not restart Walk");
        assert!(call(proto::Call::RobotRelax).accepted);
        until(|| trace.lock().unwrap().torque == [true, false]).await;
        assert!(!intents.enabled());
        state.shutdown.store(true, Ordering::Relaxed);
        task.await.unwrap();
}

// Contract installation is intentionally process-wide, as in the daemon.
// run-V186-tests.py launches each posture in a separate test process.
#[tokio::test]
async fn v186_official_start_sagged() {
    run_case("sagged upright", [0.0, 0.0, -1.0], false).await;
}
#[tokio::test]
async fn v186_official_start_prone() {
    run_case("prone", [1.0, 0.0, 0.0], false).await;
}
#[tokio::test]
async fn v186_official_start_supine() {
    run_case("supine", [-1.0, 0.0, 0.0], false).await;
}
#[tokio::test]
async fn v186_official_start_side_from_limp() {
    run_case("side, direct enable from limp", [0.0, 1.0, 0.0], true).await;
}

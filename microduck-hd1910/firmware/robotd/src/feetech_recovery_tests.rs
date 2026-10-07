//! Exercise the real policy/control loop, including writes on missing reads.
use super::*;
use duck_control::io::{IoError, Result, Sensors};
use std::sync::Mutex;

#[derive(Default)]
struct Trace {
    writes: Vec<(u32, [f64; NUM_JOINTS])>,
    torque: Vec<bool>,
}

struct RecoveryIo {
    sensors: Sensors,
    dropping: Arc<AtomicBool>,
    fail_write: Arc<AtomicBool>,
    trace: Arc<Mutex<Trace>>,
    missing: u32,
}

impl RobotIo for RecoveryIo {
    fn reboot(&mut self, _id: u8) -> duck_control::io::Result<()> {
        Err(duck_control::io::IoError::Simulated)
    }
    fn read(&mut self) -> Result<Sensors> {
        if self.dropping.load(Ordering::Relaxed) {
            self.missing += 1;
            Err(IoError::Simulated)
        } else {
            self.missing = 0;
            Ok(self.sensors)
        }
    }
    fn write(&mut self, target: &duck_control::JointTargets) -> Result<()> {
        if self.fail_write.swap(false, Ordering::Relaxed) {
            return Err(IoError::Simulated);
        }
        self.trace
            .lock()
            .unwrap()
            .writes
            .push((self.missing, target.positions));
        Ok(())
    }
    fn set_gain(&mut self, _: u16) -> Result<()> {
        Ok(())
    }
    fn set_torque(&mut self, on: bool) -> Result<()> {
        self.trace.lock().unwrap().torque.push(on);
        Ok(())
    }
    fn imu_ready(&self) -> bool {
        true
    }
    fn feetech_diagnostics(&self) -> Option<duck_control::feetech::FeetechDiagnostics> {
        use duck_control::feetech::FeetechDiagnostics;
        // This fake starts with all motors off unless its trace explicitly
        // seeds a pre-existing powered state (daemon restart coverage).
        let torque = Some(
            self.trace
                .lock()
                .unwrap()
                .torque
                .last()
                .copied()
                .unwrap_or(false),
        );
        Some(FeetechDiagnostics {
            backend: "fake_feetech",
            read_timing_revision: "test",
            motion_enabled: true,
            calibration_complete: true,
            imu_mount_verified: true,
            torque_enabled: torque == Some(true),
            torque_state_confirmed: torque,
            gain_mode: "test",
            velocity_source: "test",
            velocity_rad_s_per_count: None,
            current_available: false,
            sample_age_ms: Some(0),
            imu_ready: true,
            imu_sequence: None,
            imu_age_ms: Some(0),
            imu_age_upper_bound_ms: Some(0),
            imu_status: None,
            command_clamps_total: 0,
            partial_samples_total: 0,
            all_joints_fresh: self.missing == 0,
            stale_joint_ids: vec![],
            held_joint_ids: vec![],
            joints: vec![],
            sync: Default::default(),
            telemetry: Default::default(),
            hd1910: duck_control::hd1910::State::default().diagnostics(),
        })
    }
    fn slow_sensors(&mut self) -> Result<duck_control::SlowSensors> {
        Ok(duck_control::SlowSensors {
            volts: 7.3,
            temps_c: [35.0; NUM_JOINTS],
        })
    }
    fn feetech_snapshot(&self) -> Option<duck_control::feetech_snapshot::Snapshot> {
        use duck_control::feetech_snapshot as raw;
        // This fake has no joint/register payload; publish exactly its existing
        // diagnostic facts through the new read-only hand-off.
        let d = self.feetech_diagnostics().unwrap();
        let metadata = Arc::new(raw::Metadata {
            backend: d.backend,
            read_timing_revision: d.read_timing_revision,
            motion_enabled: d.motion_enabled,
            calibration_complete: d.calibration_complete,
            imu_mount_verified: d.imu_mount_verified,
            velocity_source: d.velocity_source,
            velocity_rad_s_per_count: d.velocity_rad_s_per_count,
            current_available: d.current_available,
            joints: Vec::new(),
        });
        Some(raw::Snapshot {
            metadata: metadata.clone(),
            dynamic: raw::Dynamic {
                torque_enabled: d.torque_enabled,
                torque_state_confirmed: d.torque_state_confirmed,
                gain_mode: d.gain_mode,
                sample_age_ms: d.sample_age_ms,
                imu_ready: d.imu_ready,
                imu_sequence: d.imu_sequence,
                imu_age_ms: d.imu_age_ms,
                imu_age_upper_bound_ms: d.imu_age_upper_bound_ms,
                imu_status: d.imu_status,
                command_clamps_total: d.command_clamps_total,
                partial_samples_total: d.partial_samples_total,
                all_joints_fresh: d.all_joints_fresh,
                stale_joint_ids: Default::default(),
                held_joint_ids: Default::default(),
                joints: raw::JointSamples {
                    samples: Default::default(),
                    metadata,
                },
                sync: d.sync,
                telemetry: d.telemetry,
                hd1910: raw::HdState {
                    temporary_gains_applied: d.hd1910.temporary_gains_applied,
                    restore_pending: d.hd1910.restore_pending,
                },
            },
            hd1910: d.hd1910,
        })
    }
}

fn bus_status(state: &RobotState) -> Option<serde_json::Value> {
    state
        .raw
        .latest
        .load_full()?
        .bus
        .as_ref()
        .map(raw_stream::Bus::report)
}

async fn until(predicate: impl Fn() -> bool) {
    tokio::time::timeout(Duration::from_secs(8), async {
        while !predicate() {
            tokio::time::sleep(Duration::from_millis(2)).await;
        }
    })
    .await
    .expect("control-loop condition timed out");
}

#[tokio::test]
async fn start_home_ends_the_seat_even_when_reads_are_paused() {
    let mut params = Params::default();
    params.bus.protocol = params::BusProtocol::Feetech;
    let models = Path::new(env!("CARGO_MANIFEST_DIR")).join("../policies");
    params.policy.walk = Some(models.join("../test-data/walk-teacher14000/policy.onnx"));
    params.policy.sitstand = Some(models.join("sitstand/policy.onnx"));
    params.policy.stand = Some("none".into());
    params.policy.ground_pick = Some("none".into());
    params.policy.kick_left = Some("none".into());
    params.policy.kick_right = Some("none".into());
    params.policy.roulade = Some("none".into());
    params.safety.limp_fall = false;
    params.audio.enabled = false;
    params.audio.greet = false;
    let state = Arc::new(RobotState::new(
        &params,
        Path::new("/tmp/unused-home.toml"),
        false,
        false,
    ));
    let intents = Arc::new(Intents::new());
    let dropping = Arc::new(AtomicBool::new(false));
    let trace = Arc::new(Mutex::new(Trace::default()));
    let io = RecoveryIo {
        sensors: Sensors {
            positions: duck_control::deployment::home(),
            ..Default::default()
        },
        dropping: dropping.clone(),
        fail_write: Arc::new(AtomicBool::new(false)),
        trace: trace.clone(),
        missing: 0,
    };
    let task = tokio::spawn(control_loop(
        io,
        state.clone(),
        intents.clone(),
        params,
        PathBuf::from("/tmp/unused-home.toml"),
        Duration::from_millis(5),
        Arc::new(|| {}),
    ));
    let start = || {
        let result: proto::IntentResult = dispatch(
            &state,
            &intents,
            proto::Id::Number(1),
            &proto::Call::RobotEnable(proto::EnableParams {
                on: false,
                toggle: true,
            }),
        )
        .result_as()
        .unwrap();
        assert!(result.accepted, "{result:?}");
    };
    until(|| state.ticks.load(Ordering::Relaxed) > 2).await;
    intents.request_init();
    until(|| state.home_start.load_full().is_some_and(|r| r.ready)).await;
    for pause_reads in [false, true, false] {
        start();
        until(|| bus_status(&state).is_some_and(|r| r["scale_use"] == "hold")).await;
        let sit: proto::IntentResult = dispatch(
            &state,
            &intents,
            proto::Id::Number(2),
            &proto::Call::RobotDo(proto::DoParams {
                skill: "sit_toggle".into(),
            }),
        )
        .result_as()
        .unwrap();
        assert!(sit.accepted);
        until(|| state.sitting.load(Ordering::Relaxed)).await;
        if pause_reads {
            dropping.store(true, Ordering::Relaxed);
            until(|| state.consecutive_errors.load(Ordering::Relaxed) > COAST_TICKS).await;
        }
        start(); // Start-off must finish the skill, not merely stop its inference.
        assert!(!intents.enabled());
        let off_tick = state.ticks.load(Ordering::Relaxed);
        until(|| state.ticks.load(Ordering::Relaxed) > off_tick + 3).await;
        assert!(
            !state.sitting.load(Ordering::Relaxed),
            "HOME left the seat latched; next Start would sit again"
        );
        dropping.store(false, Ordering::Relaxed);
        until(|| {
            state.homed.load(Ordering::Relaxed)
                && state.home_start.load_full().is_some_and(|r| r.ready)
        })
        .await;
        assert!(!intents.enabled(), "arriving HOME must not replay Start");
    }
    start();
    until(|| {
        bus_status(&state).is_some_and(|r| {
            r["scale_use"] == "hold"
                && r["active_model"]["sha256"]
                    == "9e3ff8bde021be28a728c02dbd8e7aaf9b447dd75545dacaa72ccec8e9ec7e6c"
        })
    })
    .await;
    assert!(!state.sitting.load(Ordering::Relaxed));
    state.shutdown.store(true, Ordering::Relaxed);
    task.await.unwrap();
    assert_eq!(
        trace.lock().unwrap().torque,
        [true],
        "HOME must not add a torque cycle"
    );
}

#[tokio::test]
async fn feetech_official_coast_holds_and_resumes_without_reenable() {
    let mut params = Params::default();
    params.bus.protocol = params::BusProtocol::Feetech;
    params.policy.walk = Some(
        std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../test-data/walk-teacher14000/policy.onnx"),
    );
    params.policy.stand = Some("none".into());
    params.policy.sitstand = Some("none".into());
    params.policy.ground_pick = Some("none".into());
    params.policy.kick_left = Some("none".into());
    params.policy.kick_right = Some("none".into());
    params.policy.roulade = Some("none".into());
    params.safety.limp_fall = false;
    params.audio.enabled = false;
    params.audio.greet = false;
    let state = Arc::new(RobotState::new(
        &params,
        Path::new("/tmp/unused-robotd.toml"),
        false,
        false,
    ));
    let intents = Arc::new(Intents::new());
    let dropping = Arc::new(AtomicBool::new(false));
    let fail_write = Arc::new(AtomicBool::new(false));
    let trace = Arc::new(Mutex::new(Trace::default()));
    let mut measured = DEFAULT_POSITION;
    measured[0] += 0.08; // measured pose differs from both Home and policy output
    let io = RecoveryIo {
        sensors: Sensors {
            positions: measured,
            ..Sensors::default()
        },
        dropping: dropping.clone(),
        fail_write: fail_write.clone(),
        trace: trace.clone(),
        missing: 0,
    };
    let task = tokio::spawn(control_loop(
        io,
        state.clone(),
        intents.clone(),
        params,
        PathBuf::from("/tmp/unused-robotd.toml"),
        Duration::from_millis(5),
        Arc::new(|| {}),
    ));
    until(|| state.ticks.load(Ordering::Relaxed) > 2).await;
    assert!(
        state.policy_error.load_full().is_none(),
        "real ONNX policy must load: {:?}",
        state.policy_error.load_full()
    );
    intents.request_init();
    until(|| state.home_start.load_full().is_some_and(|r| r.ready)).await;
    intents.set_twist([0.1, 0.0, 0.0]);
    intents.set_enabled(true);
    let start = state.ticks.load(Ordering::Relaxed);
    until(|| state.ticks.load(Ordering::Relaxed) > start + 5).await;
    dropping.store(true, Ordering::Relaxed);
    until(|| {
        trace
            .lock()
            .unwrap()
            .writes
            .last()
            .is_some_and(|(n, _)| *n >= 8)
    })
    .await;
    {
        let log = trace.lock().unwrap();
        for n in 1..=8 {
            let (_, target) = log
                .writes
                .iter()
                .find(|(m, _)| *m == n)
                .expect("must write even on a dropped read");
            if n <= COAST_TICKS {
                assert_ne!(*target, measured, "coast must keep calculating targets");
            } else {
                assert_eq!(*target, measured, "blind hold must use the measured pose");
            }
        }
        assert_eq!(log.torque, [true], "read failures must not release torque");
    }
    assert!(intents.enabled());
    let recovery = trace.lock().unwrap().writes.len();
    dropping.store(false, Ordering::Relaxed);
    until(|| {
        trace.lock().unwrap().writes[recovery..]
            .iter()
            .any(|(n, t)| *n == 0 && *t != measured)
    })
    .await;
    assert!(
        intents.enabled(),
        "recovery must not need a new enable command"
    );
    fail_write.store(true, Ordering::Relaxed);
    until(|| !fail_write.load(Ordering::Relaxed)).await;
    let stop = state.ticks.load(Ordering::Relaxed);
    until(|| state.ticks.load(Ordering::Relaxed) > stop + 5).await;
    assert!(
        intents.enabled(),
        "upstream keeps running after a failed write"
    );
    assert_eq!(
        trace.lock().unwrap().torque,
        [true],
        "a write fault is not a relax request"
    );
    state.shutdown.store(true, Ordering::Relaxed);
    task.await.unwrap();
}

struct FallingIo {
    inner: RecoveryIo,
    current: Arc<Mutex<Sensors>>,
}
impl RobotIo for FallingIo {
    fn read(&mut self) -> Result<Sensors> {
        self.inner.sensors = *self.current.lock().unwrap();
        self.inner.read()
    }
    fn write(&mut self, t: &duck_control::JointTargets) -> Result<()> {
        self.inner.write(t)
    }
    fn set_gain(&mut self, p: u16) -> Result<()> {
        self.inner.set_gain(p)
    }
    fn set_torque(&mut self, on: bool) -> Result<()> {
        self.inner.set_torque(on)
    }
    fn reboot(&mut self, id: u8) -> Result<()> {
        self.inner.reboot(id)
    }
    fn imu_ready(&self) -> bool {
        true
    }
    fn feetech_diagnostics(&self) -> Option<duck_control::feetech::FeetechDiagnostics> {
        self.inner.feetech_diagnostics()
    }
    fn feetech_snapshot(&self) -> Option<duck_control::feetech_snapshot::Snapshot> {
        self.inner.feetech_snapshot()
    }
    fn slow_sensors(&mut self) -> Result<duck_control::SlowSensors> {
        self.inner.slow_sensors()
    }
}

#[tokio::test]
async fn enabled_joint_model_keeps_driving_falls_despite_non_home_readback() {
    let mut params: Params =
        toml::from_str(include_str!("../../packaging/robotd-profile.toml")).unwrap();
    params.policy.walk =
        Some(Path::new(env!("CARGO_MANIFEST_DIR")).join("test-data/joint-audit/policy.onnx"));
    params.policy.sitstand = Some("none".into());
    params.policy.ground_pick = Some("none".into());
    params.policy.roulade = Some("none".into());
    params.policy.skills.clear();
    params.policy.action_scale = Some(0.65);
    params.policy.voltage_adapt = false;
    params.audio.enabled = false;
    params.audio.greet = false;
    let state = Arc::new(RobotState::new(
        &params,
        Path::new("/tmp/joint-audit-unused.toml"),
        false,
        false,
    ));
    let intents = Arc::new(Intents::new());
    let trace = Arc::new(Mutex::new(Trace::default()));
    let current = Arc::new(Mutex::new(Sensors {
        positions: duck_control::deployment::home(),
        ..Default::default()
    }));
    let io = FallingIo {
        inner: RecoveryIo {
            sensors: *current.lock().unwrap(),
            dropping: Arc::new(AtomicBool::new(false)),
            fail_write: Arc::new(AtomicBool::new(false)),
            trace: trace.clone(),
            missing: 0,
        },
        current: current.clone(),
    };
    let task = tokio::spawn(control_loop(
        io,
        state.clone(),
        intents.clone(),
        params,
        PathBuf::from("/tmp/joint-audit-unused.toml"),
        Duration::from_millis(5),
        Arc::new(|| {}),
    ));
    until(|| state.ticks.load(Ordering::Relaxed) > 2).await;
    intents.request_init();
    until(|| state.home_start.load_full().is_some_and(|r| r.ready)).await;
    let result: proto::IntentResult = dispatch(
        &state,
        &intents,
        proto::Id::Number(11),
        &proto::Call::RobotEnable(proto::EnableParams {
            on: true,
            toggle: false,
        }),
    )
    .result_as()
    .unwrap();
    assert!(result.accepted);
    until(|| bus_status(&state).is_some_and(|r| r["scale_use"] == "hold")).await;
    for gravity in [[1.0, 0.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 1.0, 0.0]] {
        current.lock().unwrap().imu.gravity = gravity;
        let before = state.ticks.load(Ordering::Relaxed);
        until(|| {
            state.ticks.load(Ordering::Relaxed) > before + 60
                && state.fallen.load(Ordering::Relaxed)
        })
        .await;
        let bus = bus_status(&state).unwrap();
        assert!(intents.enabled(), "a fall must not become an enable edge");
        assert_eq!(bus["policy_enabled"], true);
        assert_eq!(bus["scale_use"], "hold");
        assert_eq!(bus["active_action_scale"], 0.65);
        assert_eq!(
            bus["active_model"]["sha256"],
            "5c019c3d3d2c490947f21974f394750671b0ec7b7a2d1e36734e82c8a3c9225b"
        );
        assert!(!state.home_start.load_full().unwrap().ready);
        assert!(
            trace
                .lock()
                .unwrap()
                .writes
                .last()
                .unwrap()
                .1
                .iter()
                .all(|v| v.is_finite())
        );
    }
    state.shutdown.store(true, Ordering::Relaxed);
    task.await.unwrap();
    assert_eq!(
        trace.lock().unwrap().torque,
        [true],
        "no automatic limp, HOME or torque-off during recovery"
    );
}

/// A fallen HOME robot runs the uploaded LB network immediately. In particular,
/// the expiration tick must not choose Walk even for one frame.
#[tokio::test]
async fn home_lb_starts_fallen_finishes_home_and_start_cancels_while_blind() {
    let mut params: Params =
        toml::from_str(include_str!("../../packaging/robotd-profile.toml")).unwrap();
    let models = Path::new(env!("CARGO_MANIFEST_DIR")).join("../policies");
    params.policy.walk = Some(models.join("../test-data/walk-teacher14000/policy.onnx"));
    params.policy.stand = Some("none".into());
    params.policy.sitstand = Some("none".into());
    params.policy.ground_pick = Some("none".into());
    params.policy.roulade = Some("none".into());
    params.policy.skills.retain(|s| s.name == "stand_test");
    params.policy.skills[0].path = Some(models.join("stand/policy.onnx"));
    params.policy.skills[0].duration = 0.12;
    params.policy.action_scale = Some(0.63);
    params.policy.voltage_adapt = false;
    params.audio.enabled = false;
    params.audio.greet = false;
    let state = Arc::new(RobotState::new(
        &params,
        Path::new("/tmp/home-lb-unused.toml"),
        false,
        false,
    ));
    let intents = Arc::new(Intents::new());
    let trace = Arc::new(Mutex::new(Trace::default()));
    let dropping = Arc::new(AtomicBool::new(false));
    let current = Arc::new(Mutex::new(Sensors {
        positions: duck_control::deployment::home(),
        ..Default::default()
    }));
    let io = FallingIo {
        inner: RecoveryIo {
            sensors: *current.lock().unwrap(),
            dropping: dropping.clone(),
            fail_write: Arc::new(AtomicBool::new(false)),
            trace: trace.clone(),
            missing: 0,
        },
        current: current.clone(),
    };
    let mut frames = state.state_tx.subscribe();
    let task = tokio::spawn(control_loop(
        io,
        state.clone(),
        intents.clone(),
        params,
        PathBuf::from("/tmp/home-lb-unused.toml"),
        Duration::from_millis(5),
        Arc::new(|| {}),
    ));
    let call = |call| -> proto::IntentResult {
        dispatch(&state, &intents, proto::Id::Number(1), &call)
            .result_as()
            .unwrap()
    };
    let lb = || {
        proto::Call::RobotDo(proto::DoParams {
            skill: "stand_test".into(),
        })
    };
    assert!(
        !call(lb()).accepted,
        "before any fresh feedback LB stays unavailable"
    );
    until(|| state.ticks.load(Ordering::Relaxed) > 2).await;
    intents.request_init();
    until(|| state.home_start.load_full().is_some_and(|r| r.ready)).await;
    {
        let mut fallen = current.lock().unwrap();
        fallen.imu.gravity = [1.0, 0.0, 0.0];
        fallen.positions[3] += 0.8;
    }
    until(|| state.home_start.load_full().is_some_and(|r| !r.ready)).await;
    assert!(
        !call(proto::Call::RobotEnable(proto::EnableParams {
            on: true,
            toggle: false
        }))
        .accepted,
        "the recovery exception must not bypass ordinary Walk start"
    );
    assert!(
        !call(proto::Call::RobotDo(proto::DoParams {
            skill: "sit_toggle".into()
        }))
        .accepted
    );
    while !matches!(
        frames.try_recv(),
        Err(tokio::sync::broadcast::error::TryRecvError::Empty)
    ) {}
    assert!(call(lb()).accepted);
    until(|| bus_status(&state).is_some_and(|r| r["scale_use"] == "stand_test")).await;
    let bus = bus_status(&state).unwrap();
    assert_eq!(bus["home_recovery"], true);
    assert_eq!(
        bus["active_model"]["sha256"],
        "a481d9f211f31d9476ab1a319fe362a21ef0879d9fa59442a122845af598268c"
    );
    assert_eq!(bus["active_action_scale"], 1.0);
    assert_eq!(bus["active_target_filters"]["head_lowpass"], 1.0);
    assert_eq!(bus["active_target_filters"]["legs_lowpass"], 1.0);
    assert_eq!(bus["action_scale"], 0.63);
    assert!(state.enable_refusal.load().is_none());
    assert!(
        !call(proto::Call::RobotDo(proto::DoParams {
            skill: "sit_toggle".into()
        }))
        .accepted
    );
    until(|| !intents.enabled() && !state.home_recovery.load(Ordering::Relaxed)).await;
    let end_tick = state.ticks.load(Ordering::Relaxed);
    until(|| state.ticks.load(Ordering::Relaxed) > end_tick + 3).await;
    let mut ran_teacher = false;
    while let Ok(frame) = frames.try_recv() {
        assert!(
            matches!(frame.policy.as_str(), "held" | "stand_test"),
            "unexpected network: {}",
            frame.policy
        );
        if frame.policy == "stand_test" {
            ran_teacher = true;
        }
        if frame.policy == "held" {
            // Mouth closure retains its native calibrated target, independently
            // of the body HOME vector and any motion policy.
            for joint in 0..NUM_JOINTS {
                if joint != duck_control::model::MOUTH_INDEX {
                    assert_eq!(
                        frame.targets[joint],
                        duck_control::deployment::home()[joint]
                    );
                }
            }
        }
    }
    assert!(ran_teacher);
    assert_eq!(
        bus_status(&state).unwrap()["active_action_scale"],
        serde_json::Value::Null
    );

    assert!(call(lb()).accepted);
    until(|| state.home_recovery.load(Ordering::Relaxed)).await;
    dropping.store(true, Ordering::Relaxed);
    until(|| state.consecutive_errors.load(Ordering::Relaxed) > COAST_TICKS).await;
    assert!(
        call(proto::Call::RobotEnable(proto::EnableParams {
            on: false,
            toggle: true
        }))
        .accepted
    );
    assert!(!intents.enabled());
    until(|| !state.home_recovery.load(Ordering::Relaxed)).await;
    dropping.store(false, Ordering::Relaxed);
    until(|| state.homed.load(Ordering::Relaxed)).await;
    let end_tick = state.ticks.load(Ordering::Relaxed);
    until(|| state.ticks.load(Ordering::Relaxed) > end_tick + 3).await;
    assert!(
        !intents.enabled(),
        "cancelled HOME recovery must not replay or start Walk"
    );
    assert_eq!(bus_status(&state).unwrap()["scale_use"], "held");
    state.shutdown.store(true, Ordering::Relaxed);
    task.await.unwrap();
    assert_eq!(
        trace.lock().unwrap().torque,
        [true],
        "direct recovery must not cycle torque"
    );
}

/// Cancelling a request before the control tick must cancel the request too,
/// rather than turning Start into a queued Walk launch.
#[test]
fn home_lb_pending_request_is_cancelled_by_start_home_disable_and_relax() {
    let params: Params =
        toml::from_str(include_str!("../../packaging/robotd-profile.toml")).unwrap();
    let state = RobotState::new(&params, Path::new("/tmp/home-lb-unused.toml"), false, false);
    state.homed.store(true, Ordering::Relaxed);
    state
        .home_start
        .store(Some(Arc::new(home_start::Guard::default().observe(
            Instant::now(),
            Some(&Sensors::default()),
            &duck_control::deployment::home(),
            home_start::Conditions {
                home_phase: true,
                all_joints_fresh: true,
                imu_ready: true,
                torque_confirmed: true,
            },
        ))));
    let intents = Intents::new();
    for cancel in 0..4 {
        let accepted: proto::IntentResult = dispatch(
            &state,
            &intents,
            proto::Id::Number(1),
            &proto::Call::RobotDo(proto::DoParams {
                skill: "stand_test".into(),
            }),
        )
        .result_as()
        .unwrap();
        assert!(accepted.accepted);
        assert!(!intents.enabled());
        assert!(intents.home_skill_pending());
        match cancel {
            0 => {
                let result: proto::IntentResult = dispatch(
                    &state,
                    &intents,
                    proto::Id::Number(2),
                    &proto::Call::RobotEnable(proto::EnableParams {
                        on: false,
                        toggle: true,
                    }),
                )
                .result_as()
                .unwrap();
                assert!(result.accepted);
            }
            1 => intents.request_init(),
            2 => intents.set_enabled(false),
            _ => intents.request_relax(),
        }
        assert_eq!(intents.take_home_skill(), None);
        assert!(!intents.enabled());
        intents.take_power_request();
    }
    intents.request_home_skill(1);
    assert_eq!(intents.take_home_skill().map(|r| r.index), Some(1));
    assert_eq!(
        intents.take_home_skill(),
        None,
        "one request runs only once"
    );
}

fn manual_lb_params(duration: f64) -> Params {
    let mut params: Params =
        toml::from_str(include_str!("../../packaging/robotd-profile.toml")).unwrap();
    let models = Path::new(env!("CARGO_MANIFEST_DIR")).join("../policies");
    params.policy.walk = Some(models.join("../test-data/walk-teacher14000/policy.onnx"));
    params.policy.stand = Some("none".into());
    params.policy.sitstand = Some("none".into());
    params.policy.ground_pick = Some("none".into());
    params.policy.roulade = Some("none".into());
    params.policy.skills.retain(|s| s.name == "stand_test");
    params.policy.skills[0].path = Some(models.join("stand/policy.onnx"));
    params.policy.skills[0].duration = duration;
    params.policy.action_scale = Some(0.63);
    params.policy.voltage_adapt = false;
    params.audio.enabled = false;
    params.audio.greet = false;
    params
}

struct LbRig {
    state: Arc<RobotState>,
    intents: Arc<Intents>,
    current: Arc<Mutex<Sensors>>,
    dropping: Arc<AtomicBool>,
    trace: Arc<Mutex<Trace>>,
    frames: tokio::sync::broadcast::Receiver<Arc<proto::RobotState>>,
    task: tokio::task::JoinHandle<()>,
}

impl LbRig {
    async fn new(duration: f64) -> Self {
        let params = manual_lb_params(duration);
        let path = PathBuf::from("/tmp/lb-all-poses-unused.toml");
        let state = Arc::new(RobotState::new(&params, &path, false, false));
        let intents = Arc::new(Intents::new());
        let current = Arc::new(Mutex::new(Sensors {
            positions: duck_control::deployment::home(),
            ..Default::default()
        }));
        let dropping = Arc::new(AtomicBool::new(false));
        let trace = Arc::new(Mutex::new(Trace::default()));
        let io = FallingIo {
            inner: RecoveryIo {
                sensors: *current.lock().unwrap(),
                dropping: dropping.clone(),
                fail_write: Arc::new(AtomicBool::new(false)),
                trace: trace.clone(),
                missing: 0,
            },
            current: current.clone(),
        };
        let frames = state.state_tx.subscribe();
        let task = tokio::spawn(control_loop(
            io,
            state.clone(),
            intents.clone(),
            params,
            path,
            Duration::from_millis(5),
            Arc::new(|| {}),
        ));
        until(|| state.ticks.load(Ordering::Relaxed) > 2).await;
        Self {
            state,
            intents,
            current,
            dropping,
            trace,
            frames,
            task,
        }
    }

    fn call(&self, call: proto::Call) -> proto::IntentResult {
        dispatch(&self.state, &self.intents, proto::Id::Number(1), &call)
            .result_as()
            .unwrap()
    }

    fn lb(&self) -> proto::IntentResult {
        self.call(proto::Call::RobotDo(proto::DoParams {
            skill: "stand_test".into(),
        }))
    }

    async fn fall(&self) {
        {
            let mut sample = self.current.lock().unwrap();
            sample.imu.gravity = [1.0, 0.0, 0.0];
            sample.positions[3] += 0.8;
        }
        until(|| self.state.fallen.load(Ordering::Relaxed)).await;
    }

    fn clear_frames(&mut self) {
        while !matches!(
            self.frames.try_recv(),
            Err(tokio::sync::broadcast::error::TryRecvError::Empty)
        ) {}
    }

    async fn stop(self) {
        self.state.shutdown.store(true, Ordering::Relaxed);
        self.task.await.unwrap();
    }
}

/// The test drives the real ONNX and control loop from a measured fallen pose,
/// without init. A HOME or Walk frame before/after the teacher would be a visible
/// motor movement that the caller of limp LB never requested.
#[tokio::test]
async fn fallen_limp_lb_starts_teacher_directly_finishes_home_and_retries_after_select() {
    let mut rig = LbRig::new(0.12).await;
    assert!(
        !rig.lb().accepted,
        "upright limp still needs normal HOME, or a fall"
    );
    assert!(
        rig.trace.lock().unwrap().torque.is_empty(),
        "startup stays limp"
    );
    rig.fall().await;
    rig.clear_frames();
    assert!(rig.lb().accepted);
    until(|| bus_status(&rig.state).is_some_and(|r| r["scale_use"] == "stand_test")).await;
    let status = bus_status(&rig.state).unwrap();
    assert_eq!(status["home_recovery"], true);
    assert_eq!(
        status["active_model"]["sha256"],
        "a481d9f211f31d9476ab1a319fe362a21ef0879d9fa59442a122845af598268c"
    );
    assert_eq!(status["active_action_scale"], 1.0);
    assert_eq!(status["active_target_filters"]["head_lowpass"], 1.0);
    assert_eq!(status["active_target_filters"]["legs_lowpass"], 1.0);
    until(|| !rig.intents.enabled() && !rig.state.home_recovery.load(Ordering::Relaxed)).await;
    let mut teacher = false;
    while let Ok(frame) = rig.frames.try_recv() {
        assert!(
            matches!(frame.policy.as_str(), "held" | "stand_test"),
            "unexpected policy {}",
            frame.policy
        );
        teacher |= frame.policy == "stand_test";
    }
    assert!(teacher);
    assert_eq!(rig.trace.lock().unwrap().torque, [true]);

    assert!(rig.lb().accepted);
    until(|| rig.state.home_recovery.load(Ordering::Relaxed)).await;
    assert!(rig.call(proto::Call::RobotRelax).accepted);
    until(|| {
        !rig.state.homed.load(Ordering::Relaxed) && !rig.state.home_recovery.load(Ordering::Relaxed)
    })
    .await;
    assert!(!rig.intents.enabled());
    assert_eq!(rig.trace.lock().unwrap().torque, [true, false]);
    assert!(
        rig.lb().accepted,
        "Select does not permanently block limp LB"
    );
    until(|| rig.state.home_recovery.load(Ordering::Relaxed)).await;
    assert_eq!(rig.trace.lock().unwrap().torque, [true, false, true]);
    rig.stop().await;
}

/// After limp LB, padd's local `up=false` means Start emits RobotInit rather
/// than RobotEnable(toggle). This actual branch must cancel even on a blind bus.
#[tokio::test]
async fn limp_lb_start_via_padd_init_cancels_even_while_sensors_are_blind() {
    let rig = LbRig::new(1.0).await;
    rig.fall().await;
    assert!(rig.lb().accepted);
    until(|| rig.state.home_recovery.load(Ordering::Relaxed)).await;
    rig.dropping.store(true, Ordering::Relaxed);
    until(|| rig.state.consecutive_errors.load(Ordering::Relaxed) > COAST_TICKS).await;
    assert!(rig.call(proto::Call::RobotInit).accepted);
    until(|| !rig.state.home_recovery.load(Ordering::Relaxed)).await;
    assert!(!rig.intents.enabled());
    rig.dropping.store(false, Ordering::Relaxed);
    let tick = rig.state.ticks.load(Ordering::Relaxed);
    until(|| rig.state.ticks.load(Ordering::Relaxed) > tick + 5).await;
    assert!(
        !rig.intents.enabled(),
        "a cancelled LB cannot restart on fresh feedback"
    );
    assert_eq!(bus_status(&rig.state).unwrap()["scale_use"], "held");
    rig.stop().await;
}

/// A one-shot admitted by IPC may be stale before the next tick. It must be
/// consumed/refused, with no latent torque-on when the bus later recovers.
#[tokio::test]
async fn limp_lb_rechecks_current_feedback_and_never_replays_a_refused_edge() {
    let rig = LbRig::new(0.12).await;
    rig.fall().await;
    rig.dropping.store(true, Ordering::Relaxed);
    until(|| rig.state.consecutive_errors.load(Ordering::Relaxed) > COAST_TICKS).await;
    assert!(
        !rig.lb().accepted,
        "IPC refuses its current stale sensor report"
    );
    rig.intents.request_home_skill(0); // Simulate acceptance just before the read failed.
    until(|| !rig.intents.home_skill_pending()).await;
    assert!(!rig.intents.enabled());
    assert!(rig.trace.lock().unwrap().torque.is_empty());
    rig.dropping.store(false, Ordering::Relaxed);
    until(|| rig.state.consecutive_errors.load(Ordering::Relaxed) == 0).await;
    let tick = rig.state.ticks.load(Ordering::Relaxed);
    until(|| rig.state.ticks.load(Ordering::Relaxed) > tick + 4).await;
    assert!(rig.trace.lock().unwrap().torque.is_empty());
    assert!(!rig.intents.enabled());
    assert!(rig.lb().accepted, "a fresh, explicit retry is accepted");
    until(|| rig.state.home_recovery.load(Ordering::Relaxed)).await;
    rig.stop().await;
}

/// Select previously left policy-origin LB's active timer frozen, so a later
/// limp LB looked like a duplicate and never powered the robot. Keep the same
/// physical stop/retry sequence exercised through the production dispatch path.
#[tokio::test]
async fn policy_lb_returns_walk_and_select_then_limp_lb_can_restart() {
    let rig = LbRig::new(0.12).await;
    assert!(rig.call(proto::Call::RobotInit).accepted);
    until(|| rig.state.home_start.load_full().is_some_and(|r| r.ready)).await;
    assert!(
        rig.call(proto::Call::RobotEnable(proto::EnableParams {
            on: true,
            toggle: false
        }))
        .accepted
    );
    until(|| bus_status(&rig.state).is_some_and(|r| r["scale_use"] == "hold")).await;
    rig.fall().await;
    assert!(rig.lb().accepted);
    until(|| bus_status(&rig.state).is_some_and(|r| r["scale_use"] == "stand_test")).await;
    assert!(!rig.state.home_recovery.load(Ordering::Relaxed));
    until(|| bus_status(&rig.state).is_some_and(|r| r["scale_use"] == "hold")).await;
    assert!(
        rig.intents.enabled(),
        "policy-origin LB keeps the original Walk return"
    );
    assert!(rig.lb().accepted);
    until(|| bus_status(&rig.state).is_some_and(|r| r["scale_use"] == "stand_test")).await;
    assert!(rig.call(proto::Call::RobotRelax).accepted);
    until(|| !rig.state.homed.load(Ordering::Relaxed)).await;
    assert!(rig.lb().accepted);
    until(|| rig.state.home_recovery.load(Ordering::Relaxed)).await;
    assert_eq!(bus_status(&rig.state).unwrap()["scale_use"], "stand_test");
    assert_eq!(rig.trace.lock().unwrap().torque, [true, false, true]);
    rig.stop().await;
}

#[tokio::test]
async fn fallen_lb_preempts_home_ramp_and_drops_same_tick_mode_or_policy_changes() {
    let rig = LbRig::new(0.12).await;
    rig.fall().await;
    assert!(rig.call(proto::Call::RobotInit).accepted);
    until(|| bus_status(&rig.state).is_some_and(|r| r["scale_use"] == "homing")).await;
    assert!(rig.lb().accepted);
    until(|| bus_status(&rig.state).is_some_and(|r| r["scale_use"] == "stand_test")).await;
    assert!(rig.state.home_recovery.load(Ordering::Relaxed));
    assert!(rig.call(proto::Call::RobotRelax).accepted);
    until(|| {
        !rig.state.homed.load(Ordering::Relaxed) && !rig.state.home_recovery.load(Ordering::Relaxed)
    })
    .await;
    let torque_before = rig.trace.lock().unwrap().torque.clone();
    rig.intents.request_mode_switch(mode_code(Mode::Walk));
    rig.intents.request_home_skill(0);
    until(|| !rig.intents.home_skill_pending()).await;
    assert_eq!(rig.trace.lock().unwrap().torque, torque_before);
    assert!(!rig.intents.enabled());
    assert!(
        rig.state
            .enable_refusal
            .load_full()
            .is_some_and(|r| r.contains("切换模式"))
    );
    rig.stop().await;
}

/// Inject something that happens during the real backend's longer torque
/// readback transaction, after the original tick's sensor sample was taken.
struct LbEntryIo {
    inner: FallingIo,
    fault: Option<(u8, Arc<Intents>)>,
}
impl RobotIo for LbEntryIo {
    fn read(&mut self) -> Result<Sensors> {
        self.inner.read()
    }
    fn write(&mut self, t: &duck_control::JointTargets) -> Result<()> {
        self.inner.write(t)
    }
    fn set_gain(&mut self, gain: u16) -> Result<()> {
        self.inner.set_gain(gain)
    }
    fn set_torque(&mut self, on: bool) -> Result<()> {
        self.inner.set_torque(on)?;
        if on && let Some((kind, intents)) = self.fault.take() {
            match kind {
                0 => intents.request_init(),
                1 => self.inner.inner.dropping.store(true, Ordering::Relaxed),
                2 => self.inner.current.lock().unwrap().imu.gravity = [0.0, 0.0, -1.0],
                3 => self.inner.current.lock().unwrap().positions[3] += 0.31,
                _ => intents.request_relax(),
            }
        }
        Ok(())
    }
    fn reboot(&mut self, id: u8) -> Result<()> {
        self.inner.reboot(id)
    }
    fn imu_ready(&self) -> bool {
        self.inner.imu_ready()
    }
    fn feetech_diagnostics(&self) -> Option<duck_control::feetech::FeetechDiagnostics> {
        self.inner.feetech_diagnostics()
    }
    fn feetech_snapshot(&self) -> Option<duck_control::feetech_snapshot::Snapshot> {
        self.inner.feetech_snapshot()
    }
    fn slow_sensors(&mut self) -> Result<duck_control::SlowSensors> {
        self.inner.slow_sensors()
    }
}

#[tokio::test]
async fn limp_lb_revalidates_after_torque_readback_and_honors_late_init_or_select() {
    for (fault, previously_on) in [
        (0, false),
        (1, false),
        (2, false),
        (3, false),
        (4, false),
        (1, true),
    ] {
        let params = manual_lb_params(0.12);
        let path = PathBuf::from("/tmp/lb-torque-window-unused.toml");
        let state = Arc::new(RobotState::new(&params, &path, false, false));
        let intents = Arc::new(Intents::new());
        let mut sample = Sensors {
            positions: duck_control::deployment::home(),
            ..Default::default()
        };
        sample.imu.gravity = [1.0, 0.0, 0.0];
        sample.positions[3] += 0.8;
        let current = Arc::new(Mutex::new(sample));
        let trace = Arc::new(Mutex::new(Trace {
            torque: if previously_on {
                vec![true]
            } else {
                Vec::new()
            },
            ..Default::default()
        }));
        let io = LbEntryIo {
            inner: FallingIo {
                inner: RecoveryIo {
                    sensors: sample,
                    dropping: Arc::new(AtomicBool::new(false)),
                    fail_write: Arc::new(AtomicBool::new(false)),
                    trace: trace.clone(),
                    missing: 0,
                },
                current: current.clone(),
            },
            fault: Some((fault, intents.clone())),
        };
        let mut frames = state.state_tx.subscribe();
        let task = tokio::spawn(control_loop(
            io,
            state.clone(),
            intents.clone(),
            params,
            path,
            Duration::from_millis(5),
            Arc::new(|| {}),
        ));
        until(|| state.fallen.load(Ordering::Relaxed)).await;
        while !matches!(
            frames.try_recv(),
            Err(tokio::sync::broadcast::error::TryRecvError::Empty)
        ) {}
        let accepted: proto::IntentResult = dispatch(
            &state,
            &intents,
            proto::Id::Number(1),
            &proto::Call::RobotDo(proto::DoParams {
                skill: "stand_test".into(),
            }),
        )
        .result_as()
        .unwrap();
        assert!(accepted.accepted, "fault {fault}");
        if fault == 3 {
            until(|| bus_status(&state).is_some_and(|r| r["scale_use"] == "stand_test")).await;
            let mut saw_teacher = false;
            while let Ok(frame) = frames.try_recv() {
                if frame.policy == "stand_test" {
                    saw_teacher = true;
                    assert!(
                        (frame.joints[3] - (sample.positions[3] + 0.31)).abs() < 1e-12,
                        "first inference must use the post-torque measurement"
                    );
                }
                assert_ne!(frame.policy, "homing");
                assert_ne!(frame.policy, "walk");
            }
            assert!(saw_teacher);
            assert_eq!(trace.lock().unwrap().torque, [true]);
        } else {
            until(|| state.enable_refusal.load().is_some()).await;
            assert!(!intents.enabled(), "fault {fault}");
            assert!(!state.home_recovery.load(Ordering::Relaxed));
            if previously_on {
                assert_eq!(
                    trace.lock().unwrap().torque,
                    [true, true],
                    "a read failure must not cut pre-existing supporting torque after daemon restart"
                );
            } else {
                assert!(
                    trace.lock().unwrap().torque.starts_with(&[true, false]),
                    "failed entry rolls back its newly enabled torque"
                );
            }
            while let Ok(frame) = frames.try_recv() {
                assert_ne!(
                    frame.policy, "stand_test",
                    "fault {fault} must not infer once"
                );
                assert_ne!(
                    frame.policy, "walk",
                    "fault {fault} must not fall through to Walk"
                );
            }
        }
        state.shutdown.store(true, Ordering::Relaxed);
        task.await.unwrap();
    }
}

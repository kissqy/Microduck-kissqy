use super::*;
use duck_control::io::{IoError, JointTargets, Sensors, SlowSensors};
use std::sync::Mutex;
struct Probe {
    io: FakeIo,
    torque: Arc<Mutex<Vec<bool>>>,
    ready: Arc<AtomicBool>,
    writes_fail: Arc<AtomicBool>,
}
impl RobotIo for Probe {
    fn reboot(&mut self, _id: u8) -> duck_control::io::Result<()> {
        Err(duck_control::io::IoError::Simulated)
    }
    fn read(&mut self) -> Result<Sensors, IoError> {
        self.io.read()
    }
    fn write(&mut self, targets: &JointTargets) -> Result<(), IoError> {
        if self.writes_fail.load(Ordering::Relaxed) {
            Err(IoError::Simulated)
        } else {
            self.io.write(targets)
        }
    }
    fn set_gain(&mut self, _: u16) -> Result<(), IoError> {
        Ok(())
    }
    fn set_torque(&mut self, on: bool) -> Result<(), IoError> {
        self.torque.lock().unwrap().push(on);
        self.io.set_torque(on)
    }
    fn slow_sensors(&mut self) -> Result<SlowSensors, IoError> {
        self.io.slow_sensors()
    }
    fn imu_ready(&self) -> bool {
        self.ready.load(Ordering::Relaxed)
    }
}
async fn ticks(s: &RobotState, n: u64) {
    let goal = s.ticks.load(Ordering::Relaxed) + n;
    tokio::time::timeout(Duration::from_secs(3), async {
        while s.ticks.load(Ordering::Relaxed) < goal {
            tokio::time::sleep(Duration::from_millis(2)).await;
        }
    })
    .await
    .unwrap();
}
#[tokio::test]
async fn faults_and_service_teardown_preserve_torque_explicit_relax_still_works() {
    let mut params = Params::default();
    params.bus.protocol = params::BusProtocol::Feetech;
    params.policy.enabled = false;
    params.audio.enabled = false;
    params.theremin.enabled = false;
    params.chorale.accept = false;
    let state = Arc::new(RobotState::new(
        &params,
        Path::new("/tmp/unused-robotd.toml"),
        false,
        false,
    ));
    let intents = Arc::new(Intents::new());
    let torque = Arc::new(Mutex::new(Vec::new()));
    let ready = Arc::new(AtomicBool::new(true));
    let fails = Arc::new(AtomicBool::new(false));
    let io = Probe {
        io: FakeIo::at(DEFAULT_POSITION).frozen(),
        torque: torque.clone(),
        ready: ready.clone(),
        writes_fail: fails.clone(),
    };
    let task = tokio::spawn(control_loop(
        io,
        state.clone(),
        intents.clone(),
        params,
        PathBuf::from("/tmp/unused-robotd.toml"),
        Duration::from_millis(2),
        Arc::new(|| {}),
    ));
    ticks(&state, 5).await;
    assert!(
        torque.lock().unwrap().is_empty(),
        "startup must not touch torque"
    );
    intents.request_init();
    ticks(&state, 5).await;
    assert_eq!(*torque.lock().unwrap(), vec![true]);
    ready.store(false, Ordering::Relaxed);
    ticks(&state, 5).await;
    assert_eq!(
        *torque.lock().unwrap(),
        vec![true],
        "IMU readiness gates inference, not torque"
    );
    fails.store(true, Ordering::Relaxed);
    ticks(&state, 5).await;
    assert_eq!(
        *torque.lock().unwrap(),
        vec![true],
        "write errors must not request relax"
    );
    intents.request_relax();
    ticks(&state, 5).await;
    assert_eq!(
        *torque.lock().unwrap(),
        vec![true, false],
        "explicit relax must remain effective"
    );
    state.shutdown.store(true, Ordering::Relaxed);
    task.await.unwrap();
    assert_eq!(
        *torque.lock().unwrap(),
        vec![true, false],
        "teardown must not inject another torque write"
    );
}

#[tokio::test]
async fn feetech_acquisition_ticks_before_first_valid_pose_without_target_writes() {
    struct Pending {
        valid: Arc<AtomicBool>,
        invalid_id: Arc<AtomicU64>,
        writes: Arc<AtomicU64>,
        torque: Arc<AtomicU64>,
    }
    impl RobotIo for Pending {
        fn reboot(&mut self, _id: u8) -> duck_control::io::Result<()> {
            Err(duck_control::io::IoError::Simulated)
        }
        fn read(&mut self) -> Result<Sensors, IoError> {
            if !self.valid.load(Ordering::Relaxed) {
                return Err(IoError::Bus(format!(
                    "ID {} position outside single-turn range: raw=65535",
                    self.invalid_id.load(Ordering::Relaxed)
                )));
            }
            Ok(Sensors {
                positions: DEFAULT_POSITION,
                ..Sensors::default()
            })
        }
        fn write(&mut self, _: &JointTargets) -> Result<(), IoError> {
            self.writes.fetch_add(1, Ordering::Relaxed);
            Ok(())
        }
        fn set_gain(&mut self, _: u16) -> Result<(), IoError> {
            Ok(())
        }
        fn set_torque(&mut self, _: bool) -> Result<(), IoError> {
            self.torque.fetch_add(1, Ordering::Relaxed);
            Ok(())
        }
        fn slow_sensors(&mut self) -> Result<SlowSensors, IoError> {
            Ok(SlowSensors {
                volts: 7.3,
                temps_c: [30.; NUM_JOINTS],
            })
        }
    }
    let mut params = Params::default();
    params.bus.protocol = params::BusProtocol::Feetech;
    params.policy.enabled = false;
    params.audio.enabled = false;
    let state = Arc::new(RobotState::new(
        &params,
        Path::new("/tmp/unused-robotd.toml"),
        false,
        false,
    ));
    let intents = Arc::new(Intents::new());
    let valid = Arc::new(AtomicBool::new(false));
    let writes = Arc::new(AtomicU64::new(0));
    let torque = Arc::new(AtomicU64::new(0));
    let invalid_id = Arc::new(AtomicU64::new(10));
    let io = Pending {
        valid: valid.clone(),
        invalid_id: invalid_id.clone(),
        writes: writes.clone(),
        torque: torque.clone(),
    };
    let task = tokio::spawn(control_loop(
        io,
        state.clone(),
        intents,
        params,
        PathBuf::from("/tmp/unused-robotd.toml"),
        Duration::from_millis(2),
        Arc::new(|| {}),
    ));
    for id in [10, 11, 12, 13, 14, 20, 21, 22, 23, 24, 30, 31, 32, 33, 34] {
        invalid_id.store(id, Ordering::Relaxed);
        ticks(&state, 2).await;
    }
    assert!(state.consecutive_errors.load(Ordering::Relaxed) >= 6);
    assert_eq!(
        writes.load(Ordering::Relaxed),
        0,
        "no fabricated startup target"
    );
    assert_eq!(torque.load(Ordering::Relaxed), 0);
    valid.store(true, Ordering::Relaxed);
    ticks(&state, 6).await;
    assert_eq!(
        state.consecutive_errors.load(Ordering::Relaxed),
        0,
        "feedback recovers without restart"
    );
    assert_eq!(
        torque.load(Ordering::Relaxed),
        0,
        "recovery does not arm motion"
    );
    state.shutdown.store(true, Ordering::Relaxed);
    task.await.unwrap();
}

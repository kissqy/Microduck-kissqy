//! Offline PTY coverage for startup ordering, one-command-per-tick and fail-stop.
use super::feetech_commissioning::{dispatch, run};
use super::*;
use duck_control::model::JOINT_IDS;
use std::io::{Read, Write};
use std::os::fd::FromRawFd;

#[test]
fn r9_startup_cadence_and_motion_use_one_bus_without_recovery() {
    let mut master = 0;
    let mut slave = 0;
    let mut name = [0i8; 128];
    assert_eq!(
        unsafe {
            libc::openpty(
                &mut master,
                &mut slave,
                name.as_mut_ptr(),
                std::ptr::null(),
                std::ptr::null(),
            )
        },
        0
    );
    let port = unsafe { std::ffi::CStr::from_ptr(name.as_ptr()) }
        .to_str()
        .unwrap()
        .to_owned();
    let mut wire = unsafe { std::fs::File::from_raw_fd(master) };
    unsafe {
        libc::close(slave);
    }

    let dir = std::env::temp_dir().join(format!("microduck-r9-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let calibration_path = dir.join("calibration.toml");
    let cal = duck_control::feetech::Calibration::commissioning(JOINT_IDS);
    let original = toml::to_string(&cal).unwrap();
    std::fs::write(&calibration_path, &original).unwrap();
    let state = Arc::new(RobotState::new(
        &Params::default(),
        std::path::Path::new("/tmp/unused-robotd.toml"),
        false,
        false,
    ));
    state.commissioning.store(true, Ordering::Relaxed);
    let started = Arc::new(AtomicBool::new(false));
    let corrupt = Arc::new(AtomicBool::new(false));
    let goals = Arc::new(AtomicU64::new(0));
    let exits = Arc::new(AtomicBool::new(false));
    let (device_started, device_corrupt, device_goals, device_exits) = (
        started.clone(),
        corrupt.clone(),
        goals.clone(),
        exits.clone(),
    );
    let device = std::thread::spawn(move || {
        use std::os::fd::AsRawFd;
        let mut pending = Vec::new();
        let mut rounds = 0u8;
        let mut initialization_reply = None;
        let mut writes_in_tick = 0;
        let mut pos = [2048u16; 256];
        let mut torque = [0u8; 256];
        while !device_exits.load(Ordering::Relaxed) {
            let mut fd = libc::pollfd {
                fd: wire.as_raw_fd(),
                events: libc::POLLIN,
                revents: 0,
            };
            if unsafe { libc::poll(&mut fd, 1, 10) } <= 0 {
                continue;
            }
            let mut bytes = [0u8; 1024];
            let n = match wire.read(&mut bytes) {
                Ok(n) => n,
                Err(_) => continue,
            };
            if n == 0 {
                continue;
            }
            assert!(
                device_started.load(Ordering::Acquire),
                "UART transmitted before configuration acknowledgement"
            );
            pending.extend_from_slice(&bytes[..n]);
            while pending.len() >= 4 {
                let size = pending[3] as usize + 4;
                if pending.len() < size {
                    break;
                }
                let packet = pending.drain(..size).collect::<Vec<_>>();
                assert_eq!(&packet[..2], &[255, 255]);
                assert_eq!(packet[2..].iter().fold(0u8, |a, b| a.wrapping_add(*b)), 255);
                let args = &packet[5..size - 1];
                let address = args[0];
                let length = args[1] as usize;
                if packet[4] == 0x83 {
                    for row in args[2..].chunks_exact(length + 1) {
                        assert!(JOINT_IDS.contains(&row[0]));
                        match address {
                            40 => torque[row[0] as usize] = row[1],
                            42 => {
                                // Outside an emergency stop, transitions and position
                                // writes may consume at most one additional transaction.
                                writes_in_tick += 1;
                                assert!(writes_in_tick <= 1);
                                pos[row[0] as usize] = u16::from_le_bytes([row[1], row[2]]);
                                device_goals.fetch_add(1, Ordering::Relaxed);
                            }
                            _ => panic!("unexpected write"),
                        }
                    }
                    continue;
                }
                assert!(packet[4] == 2 || packet[4] == 0x82);
                let ids = if packet[4] == 0x82 {
                    args[2..].to_vec()
                } else {
                    vec![packet[2]]
                };
                if address == 56 {
                    if rounds == 0 {
                        let gap = Instant::now().duration_since(
                            initialization_reply.expect("startup torque verification"),
                        );
                        assert!(
                            gap >= Duration::from_millis(18),
                            "first telemetry crowded startup: {gap:?}"
                        );
                    }
                    assert_eq!(packet[4], 0x82, "no unicast telemetry recovery");
                    assert_eq!(length, 15);
                    assert_eq!(
                        ids,
                        std::iter::once(200).chain(JOINT_IDS).collect::<Vec<_>>()
                    );
                    rounds = rounds.wrapping_add(1);
                    writes_in_tick = 0;
                } else if rounds > 0 && packet[4] == 2 {
                    writes_in_tick += 1;
                    assert!(writes_in_tick <= 1, "multiple transition reads in one tick");
                }
                let fail = address == 56 && device_corrupt.swap(false, Ordering::AcqRel);
                let mut replies = Vec::new();
                for id in ids {
                    let mut data = vec![0u8; length];
                    if id == 200 {
                        if address == 0 {
                            data.copy_from_slice(&duck_control::feetech::IMU_IDENTITY);
                        } else {
                            data[7] = 0x30;
                            data[12] = 250u8.wrapping_add(rounds);
                        }
                    } else {
                        match address {
                            56 => {
                                data[..2].copy_from_slice(&pos[id as usize].to_le_bytes());
                                data[6] = 64;
                                data[7] = 34;
                            }
                            40 => data[0] = torque[id as usize],
                            42 => data.copy_from_slice(&pos[id as usize].to_le_bytes()),
                            _ => panic!("unexpected read"),
                        }
                    }
                    let mut frame = vec![255, 255, id, length as u8 + 2, 0];
                    frame.extend(data);
                    let checksum = !frame[2..].iter().fold(0u8, |a, b| a.wrapping_add(*b));
                    frame.push(if fail && id == 13 {
                        checksum ^ 128
                    } else {
                        checksum
                    });
                    replies.extend(frame);
                }
                wire.write_all(&replies).unwrap();
                if address == 40 && rounds == 0 {
                    initialization_reply = Some(Instant::now());
                }
            }
        }
    });
    let (control_state, path) = (state.clone(), calibration_path.clone());
    let control = std::thread::spawn(move || {
        tokio::runtime::Builder::new_current_thread()
            .enable_time()
            .build()
            .unwrap()
            .block_on(run(
                &port,
                &control_state,
                Duration::from_millis(20),
                &path,
                true,
            ))
    });
    let wait = |predicate: &dyn Fn() -> bool| {
        let until = Instant::now() + Duration::from_secs(4);
        while !predicate() {
            assert!(
                Instant::now() < until,
                "condition timeout: goals={} status={:?}",
                goals.load(Ordering::Relaxed),
                state.bus_status.load_full()
            );
            std::thread::sleep(Duration::from_millis(5));
        }
    };
    wait(&|| {
        state
            .bus_status
            .load_full()
            .is_some_and(|s| s["phase"] == "configuring_uart")
    });
    std::thread::sleep(Duration::from_millis(60));
    assert_eq!(state.ticks.load(Ordering::Relaxed), 0);
    started.store(true, Ordering::Release);
    state.uart_setup_ready.store(true, Ordering::Release);
    wait(&|| state.ticks.load(Ordering::Relaxed) >= 8);
    let runtime = tokio::runtime::Runtime::new().unwrap();
    let (command_state, command_started) = (state.clone(), Arc::new(AtomicBool::new(false)));
    let entered = command_started.clone();
    let command = std::thread::spawn(move || {
        entered.store(true, Ordering::Relaxed);
        let response = runtime.block_on(dispatch(
            &command_state,
            proto::Id::Number(1),
            serde_json::json!({"action":"move","id":13,"position":2105,"duration_ms":1000}),
        ));
        response
    });
    wait(&|| command_started.load(Ordering::Relaxed) && goals.load(Ordering::Relaxed) >= 4);
    corrupt.store(true, Ordering::Release);
    // At a 20 ms transaction deadline the next tick can recover before the
    // observer wakes. Inspect the persisted failure, not a transient counter.
    wait(&|| {
        state.bus_snapshot.load_full().is_some_and(|snapshot| {
            serde_json::to_value(snapshot.as_ref()).unwrap()["errors_by_id"]["13"] == 1
        })
    });
    let failure = state.bus_snapshot.load_full().unwrap();
    let failure = serde_json::to_value(failure.as_ref()).unwrap();
    assert_eq!(failure["errors_by_id"]["13"], 1);
    assert!(!failure.as_object().unwrap().contains_key("diagnostics"));
    let reply = serde_json::to_value(command.join().unwrap()).unwrap();
    assert!(reply.get("error").is_some());
    let before = goals.load(Ordering::Relaxed);
    let tick = state.ticks.load(Ordering::Relaxed);
    wait(&|| state.ticks.load(Ordering::Relaxed) >= tick + 8);
    assert_eq!(goals.load(Ordering::Relaxed), before, "motion auto-resumed");
    let reply = tokio::runtime::Runtime::new().unwrap().block_on(dispatch(
        &state,
        proto::Id::Number(2),
        serde_json::json!({"action":"move","id":13,"position":2080,"duration_ms":500}),
    ));
    let reply = serde_json::to_value(reply).unwrap();
    assert_eq!(reply["result"]["torque"], "off");
    state.shutdown.store(true, Ordering::Relaxed);
    control.join().unwrap();
    exits.store(true, Ordering::Relaxed);
    device.join().unwrap();
    assert_eq!(
        std::fs::read_to_string(&calibration_path).unwrap(),
        original
    );
    std::fs::remove_dir_all(dir).unwrap();
}

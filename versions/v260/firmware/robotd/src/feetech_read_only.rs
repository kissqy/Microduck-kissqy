//! Raw telemetry mode of robotd. The control thread owns the same native Feetech
//! Bus used by FeetechIo; IPC only reads snapshots. No fabricated calibration.
use super::{Ordering, RobotState};
use duck_control::feetech::{
    Bus, IMU_ID, IMU_IDENTITY, ImuSample, SYNC_ADDRESS, SYNC_LENGTH, ServoSample, SyncTrace,
};
use duck_control::model::{JOINT_IDS, JOINT_NAMES};
use serde_json::{Value, json};
use std::collections::BTreeMap;
use std::path::Path;
use std::process::ExitCode;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};

pub const BUILD: &str = "590b986-feetech-ft6-readonly.2";
const WINDOW: u64 = 3000;

#[derive(Default)]
struct Window {
    cycles: u64,
    success: u64,
    failed: u64,
    imu_faults: u64,
    duplicate_imu: u64,
    bad_checksums: u64,
    discarded: u64,
    late_over_2ms: u64,
    over_period: u64,
    missing: BTreeMap<u8, u64>,
    read_ms: Vec<f64>,
    period_ms: Vec<f64>,
    first_failure: Option<Value>,
}

fn distribution(values: &[f64]) -> Value {
    if values.is_empty() {
        return Value::Null;
    }
    let mut sorted = values.to_vec();
    sorted.sort_by(f64::total_cmp);
    json!({"mean": values.iter().sum::<f64>() / values.len() as f64,
        "p95": sorted[(sorted.len() * 95).div_ceil(100).saturating_sub(1)],
        "max": sorted.last(), "samples": values.len()})
}

impl Window {
    fn report(&self) -> Value {
        json!({"cycles": self.cycles, "success": self.success,
            "communication_failures": self.failed, "imu_faults": self.imu_faults,
            "imu_duplicates": self.duplicate_imu, "bad_checksums": self.bad_checksums,
            "discarded_bytes": self.discarded, "missing_by_id": self.missing,
            "scheduler_late_over_2ms": self.late_over_2ms, "read_over_period": self.over_period,
            "read_ms": distribution(&self.read_ms), "period_ms": distribution(&self.period_ms),
            "first_failure": self.first_failure})
    }
}

pub(super) fn uart_counts(port: &str) -> Option<Value> {
    let number = port.strip_prefix("/dev/ttyS")?.parse::<u32>().ok()?;
    let text = std::fs::read_to_string("/proc/tty/driver/serial").ok()?;
    let prefix = format!("{number}:");
    let line = text
        .lines()
        .find(|line| line.trim_start().starts_with(&prefix))?;
    let mut counters = serde_json::Map::new();
    for item in line.split_whitespace() {
        if let Some((key, value)) = item.split_once(':')
            && matches!(key, "tx" | "rx" | "fe" | "pe" | "brk" | "oe" | "bo")
            && let Ok(n) = value.parse::<u64>()
        {
            counters.insert(key.into(), json!(n));
        }
    }
    Some(json!({"driver_line": line, "counters": counters}))
}

fn publish(state: &RobotState, report: Value) {
    state.bus_status.store(Some(Arc::new(report)));
}

fn connect(port: &str) -> Result<(Bus, Vec<Value>), String> {
    let mut bus = Bus::open_read_only(port).map_err(|e| e.to_string())?;
    let identity = bus.read(IMU_ID, 0, 5).map_err(|e| e.to_string())?;
    if identity != IMU_IDENTITY {
        return Err(format!(
            "expected FT6 IMU200 identity 06 00 00 00 f2, received {identity:02x?}"
        ));
    }
    let mut torque = Vec::new();
    for id in JOINT_IDS {
        let raw = bus.read(id, 40, 1).map_err(|e| e.to_string())?;
        torque.push(json!({"id": id, "torque_register_at_start": raw[0]}));
    }
    Ok((bus, torque))
}

pub async fn run(port: &str, state: &RobotState, period: Duration) {
    let mut ids = vec![IMU_ID];
    ids.extend(JOINT_IDS);
    let mut attempt = 0u32;
    let (mut bus, torque_at_start) = loop {
        if state.shutdown.load(Ordering::Relaxed) {
            return;
        }
        match connect(port) {
            Ok(connected) => break connected,
            Err(error) => {
                attempt += 1;
                state.startup_bus_failures.store(attempt, Ordering::Relaxed);
                publish(
                    state,
                    json!({"build": BUILD, "mode": "read_only", "phase": "waiting_for_bus",
                    "port": port, "ids": ids, "attempt": attempt, "error": error}),
                );
                if attempt == 1 || attempt.is_multiple_of(30) {
                    tracing::warn!(%error, attempt, port, "native Feetech service waiting");
                }
                tokio::time::sleep(Duration::from_secs(1)).await;
            }
        }
    };
    state.startup_bus_failures.store(0, Ordering::Relaxed);
    tracing::warn!(
        build = BUILD,
        port,
        ?ids,
        hz = 1.0 / period.as_secs_f64(),
        "robotd native FT5 read-only service running; ALL motor writes blocked"
    );

    // Identical scheduling policy to robotd's motion loop: fixed phase, skip missed
    // deadlines, no backlog of immediate retries. No additional guard subprocesses.
    let mut ticker = super::control_ticker(period);
    let mut rate_start = Instant::now();
    let mut rate_ticks = 0u64;
    let mut previous_tick: Option<Instant> = None;
    let mut previous_sequence = None;
    let mut stale_run = 0u64;
    let mut total_failures = 0u64;
    let mut total_success = 0u64;
    let mut total_imu_faults = 0u64;
    let mut window = Window::default();
    let mut window_uart = uart_counts(port);
    let mut completed: Option<Value> = None;
    let mut last_sample = Value::Null;
    let mut last_failure: Option<Value> = None;

    while !state.shutdown.load(Ordering::Relaxed) {
        let scheduled = ticker.tick().await;
        if state.shutdown.load(Ordering::Relaxed) {
            break;
        }
        let tick_start = Instant::now();
        let late = tokio::time::Instant::now().saturating_duration_since(scheduled);
        window.late_over_2ms += u64::from(late > Duration::from_millis(2));
        if let Some(previous) = previous_tick {
            window
                .period_ms
                .push(tick_start.duration_since(previous).as_secs_f64() * 1000.0);
        }
        previous_tick = Some(tick_start);
        let blocks = bus.sync_read(SYNC_ADDRESS, SYNC_LENGTH, &ids);
        let read_us = bus.last_sync.elapsed_us;
        window.read_ms.push(read_us as f64 / 1000.0);
        window.over_period += u64::from(Duration::from_micros(read_us) > period);
        window.cycles += 1;
        window.bad_checksums += bus.last_sync.bad_checksums;
        window.discarded += bus.last_sync.discarded;
        let cycle = state.ticks.load(Ordering::Relaxed) + 1;
        let last_error: Option<String>;
        let mut fault = None;
        match blocks {
            Ok(blocks) => {
                total_success += 1;
                window.success += 1;
                state.consecutive_errors.store(0, Ordering::Relaxed);
                let imu = ImuSample::decode(&blocks[&IMU_ID]);
                let mut imu_json = Value::Null;
                let mut imu_fault = None;
                match imu {
                    Ok(imu) => {
                        let duplicate = previous_sequence == Some(imu.sequence);
                        window.duplicate_imu += u64::from(duplicate);
                        stale_run = if duplicate { stale_run + 1 } else { 0 };
                        previous_sequence = Some(imu.sequence);
                        if duplicate {
                            state.imu_stale_blocks.fetch_add(1, Ordering::Relaxed);
                        }
                        state.imu_stale_run.store(stale_run, Ordering::Relaxed);
                        let valid = imu.is_fresh(read_us) && stale_run < 3;
                        state.imu_ready.store(valid, Ordering::Relaxed);
                        if !valid {
                            imu_fault = Some("IMU not ready/stale".to_owned());
                        }
                        imu_json = json!({"id": IMU_ID, "sequence": imu.sequence,
                            "age_ms": imu.age_ms, "age_upper_bound_ms":imu.age_upper_bound_ms,
                            "status":imu.status, "sequence_bits":8, "ready": imu.ready, "valid": valid,
                            "payload_12_hex": imu.block.iter().map(|b| format!("{b:02x}")).collect::<String>()});
                    }
                    Err(error) => {
                        state.imu_ready.store(false, Ordering::Relaxed);
                        imu_fault = Some(error.to_string());
                    }
                }
                if imu_fault.is_some() {
                    window.imu_faults += 1;
                    total_imu_faults += 1;
                }
                let mut servos = Vec::with_capacity(JOINT_IDS.len());
                for (i, id) in JOINT_IDS.iter().enumerate() {
                    // Every block was checked for the exact 15-byte response length.
                    let sample =
                        ServoSample::decode(&blocks[id]).expect("validated Sync Read length");
                    let fb = sample.feedback;
                    servos.push(json!({"id": id, "joint": JOINT_NAMES[i],
                        "position_raw": fb.position_raw, "speed_raw": fb.speed_raw,
                        "load_raw": fb.load_raw, "current_raw": sample.current_raw,
                        "voltage_v": fb.volts, "temperature_c": fb.temperature_c, "moving": fb.moving}));
                }
                last_sample = json!({"cycle": cycle, "at_us": state.started.elapsed().as_micros() as u64,
                    "servos": servos, "imu": imu_json, "imu_error": imu_fault});
                last_error = None;
            }
            Err(error) => {
                total_failures += 1;
                window.failed += 1;
                state.consecutive_errors.fetch_add(1, Ordering::Relaxed);
                state.imu_ready.store(false, Ordering::Relaxed);
                for id in &bus.last_sync.missing_ids {
                    *window.missing.entry(*id).or_default() += 1;
                }
                fault = Some(error.to_string());
                last_error = fault.clone();
            }
        }
        if let Some(error) = fault {
            let evidence = failure(cycle, &error, &bus.last_sync);
            if window.first_failure.is_none() {
                window.first_failure = Some(evidence.clone());
            }
            last_failure = Some(evidence);
            if total_failures <= 10 || total_failures.is_multiple_of(100) {
                tracing::warn!(cycle, %error, missing = ?bus.last_sync.missing_ids,
                    checksum_errors = bus.last_sync.bad_checksums, read_us, "native FT5 read failed");
            }
        }
        state.ticks.store(cycle, Ordering::Relaxed);
        state.last_tick_us.store(
            state.started.elapsed().as_micros() as u64,
            Ordering::Relaxed,
        );
        if tick_start.elapsed() > period {
            state.missed.fetch_add(1, Ordering::Relaxed);
        }
        rate_ticks += 1;
        let elapsed = rate_start.elapsed();
        if elapsed >= super::RATE_WINDOW {
            state.achieved_hz.store(
                (rate_ticks as f64 / elapsed.as_secs_f64()).to_bits(),
                Ordering::Relaxed,
            );
            rate_start = Instant::now();
            rate_ticks = 0;
        }

        let done = window.cycles == WINDOW;
        if done {
            let mut report = window.report();
            report["ending_cycle"] = json!(cycle);
            report["uart_start"] = json!(window_uart);
            report["uart_end"] = json!(uart_counts(port));
            tracing::info!(report = %report, "FT5_3000_RESULT");
            completed = Some(report);
        }
        if cycle == 1 || cycle.is_multiple_of(50) || last_error.is_some() || done {
            publish(
                state,
                json!({"build": BUILD, "mode": "read_only", "phase": "reading",
                "port": port, "baud": 1_000_000, "ids": ids, "target_hz": 1.0 / period.as_secs_f64(),
                "calibrated": false, "motor_writes_blocked": true,
                "total_cycles": cycle, "total_success": total_success, "total_communication_failures": total_failures,
                "total_imu_faults": total_imu_faults,
                "achieved_hz": f64::from_bits(state.achieved_hz.load(Ordering::Relaxed)),
                "updated_at_us": state.started.elapsed().as_micros() as u64,
                "window": window.report(), "last_3000": completed,
                "torque_at_start": torque_at_start, "last_sample": last_sample,
                "last_cycle_error": last_error, "last_failure": last_failure}),
            );
        }
        if cycle.is_multiple_of(250) {
            tracing::info!(
                cycles = cycle,
                success = total_success,
                failures = total_failures,
                imu_faults = total_imu_faults,
                hz = f64::from_bits(state.achieved_hz.load(Ordering::Relaxed)),
                "native FT5 service"
            );
        }
        if done {
            window = Window::default();
            window_uart = uart_counts(port);
        }
    }
    tracing::info!("native FT5 read-only service stopped; no motor writes issued");
}

fn failure(cycle: u64, error: &str, trace: &SyncTrace) -> Value {
    json!({"cycle": cycle, "error": error, "trace": trace})
}

pub async fn show(socket: &Path) -> ExitCode {
    let query = async {
        let stream = tokio::net::UnixStream::connect(socket).await?;
        let (reader, mut writer) = stream.into_split();
        writer
            .write_all(
                b"{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"robot.busStatus\",\"params\":{}}\n",
            )
            .await?;
        let mut lines = BufReader::new(reader).lines();
        let line = lines
            .next_line()
            .await?
            .ok_or_else(|| std::io::Error::other("daemon closed the connection"))?;
        let value: Value = serde_json::from_str(&line).map_err(std::io::Error::other)?;
        if let Some(error) = value.get("error") {
            return Err(std::io::Error::other(error.to_string()));
        }
        let report = value
            .get("result")
            .ok_or_else(|| std::io::Error::other("missing result"))?;
        println!(
            "{}",
            serde_json::to_string_pretty(report).map_err(std::io::Error::other)?
        );
        Ok::<(), std::io::Error>(())
    };
    match tokio::time::timeout(Duration::from_secs(5), query).await {
        Ok(Ok(())) => ExitCode::SUCCESS,
        other => {
            eprintln!("cannot read robotd bus status: {other:?}");
            ExitCode::FAILURE
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs::File;
    use std::io::{Read, Write};
    use std::os::fd::FromRawFd;
    use std::sync::Mutex;
    use std::sync::atomic::AtomicBool;

    fn reply(id: u8, data: &[u8]) -> Vec<u8> {
        let mut frame = vec![255, 255, id, data.len() as u8 + 2, 0];
        frame.extend_from_slice(data);
        frame.push(!frame[2..].iter().fold(0u8, |a, b| a.wrapping_add(*b)));
        frame
    }

    #[tokio::test(flavor = "multi_thread", worker_threads = 2)]
    async fn service_loop_counts_faults_without_any_motor_write() {
        let (mut master, mut slave) = (0, 0);
        let mut name = [0 as libc::c_char; 128];
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
        let path = unsafe { std::ffi::CStr::from_ptr(name.as_ptr()) }
            .to_str()
            .unwrap()
            .to_owned();
        let slave_file = unsafe { File::from_raw_fd(slave) };
        let mut master_file = unsafe { File::from_raw_fd(master) };
        assert_ne!(
            unsafe { libc::fcntl(master, libc::F_SETFL, libc::O_NONBLOCK) },
            -1
        );
        let stop = Arc::new(AtomicBool::new(false));
        let written = Arc::new(Mutex::new(Vec::new()));
        let worker_stop = Arc::clone(&stop);
        let worker_written = Arc::clone(&written);
        let firmware = std::thread::spawn(move || {
            let mut pending = Vec::new();
            let mut cycle = 0u32;
            let mut bytes = [0u8; 512];
            while !worker_stop.load(Ordering::Relaxed) {
                match master_file.read(&mut bytes) {
                    Ok(n) => pending.extend_from_slice(&bytes[..n]),
                    Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => {}
                    other => panic!("PTY read: {other:?}"),
                }
                while pending.len() >= 4 && pending.len() >= usize::from(pending[3]) + 4 {
                    let len = usize::from(pending[3]) + 4;
                    let frame: Vec<u8> = pending.drain(..len).collect();
                    assert_eq!(&frame[..2], &[255, 255]);
                    assert_eq!(frame[2..].iter().fold(0u8, |a, b| a.wrapping_add(*b)), 255);
                    let id = frame[2];
                    let inst = frame[4];
                    worker_written.lock().unwrap().push(inst);
                    assert!(matches!(inst, 2 | 0x82), "motor WRITE observed");
                    if inst == 2 {
                        let data = if id == 200 {
                            IMU_IDENTITY.to_vec()
                        } else {
                            vec![0]
                        };
                        master_file.write_all(&reply(id, &data)).unwrap();
                    } else {
                        let mut expected = vec![SYNC_ADDRESS, SYNC_LENGTH, IMU_ID];
                        expected.extend(JOINT_IDS);
                        assert_eq!(&frame[5..frame.len() - 1], expected);
                        cycle += 1;
                        let mut ids = vec![200];
                        ids.extend(JOINT_IDS);
                        let mut response = Vec::new();
                        for id in ids {
                            if cycle == 17 && id == 13 {
                                continue;
                            }
                            let mut data = [0u8; 15];
                            if id == 200 {
                                data[12] = cycle as u8;
                            } else {
                                data[0..2].copy_from_slice(&2048u16.to_le_bytes());
                                data[6] = 58;
                                data[7] = 32;
                            }
                            let mut frame = reply(id, &data);
                            if cycle == 28 && id == 12 {
                                assert_ne!(*frame.last().unwrap(), 255);
                                *frame.last_mut().unwrap() = 255;
                            }
                            response.extend(frame);
                        }
                        master_file.write_all(&response).unwrap();
                    }
                }
                std::thread::sleep(Duration::from_micros(200));
            }
        });
        // The transport's own write APIs must refuse before putting anything on the wire.
        let mut bus = Bus::open_read_only(&path).unwrap();
        assert!(bus.torque(&JOINT_IDS, true).is_err());
        assert!(bus.positions(&[(10, 2048)]).is_err());
        drop(bus);

        let mut params = super::super::Params::default();
        params.control.hz = 200;
        let state = Arc::new(RobotState::new(
            &params,
            std::path::Path::new("/tmp/unused-robotd.toml"),
            false,
            false,
        ));
        state.read_only.store(true, Ordering::Relaxed);
        let intents = super::super::Intents::new();
        for call in [
            duck_ipc_proto::Call::RobotInit,
            duck_ipc_proto::Call::RobotRelax,
        ] {
            let response =
                super::super::dispatch(&state, &intents, duck_ipc_proto::Id::Number(1), &call);
            let value = serde_json::to_value(response).unwrap();
            assert!(
                value["error"]["message"]
                    .as_str()
                    .unwrap()
                    .contains("read-only")
            );
        }
        let worker_state = Arc::clone(&state);
        let daemon = tokio::spawn(async move {
            run(&path, &worker_state, Duration::from_millis(5)).await;
        });
        let result = tokio::time::timeout(Duration::from_secs(35), async {
            loop {
                if let Some(report) = state.bus_status.load_full()
                    && !report["last_3000"].is_null()
                {
                    break report;
                }
                tokio::time::sleep(Duration::from_millis(20)).await;
            }
        })
        .await;
        state.shutdown.store(true, Ordering::Relaxed);
        daemon.await.unwrap();
        stop.store(true, Ordering::Relaxed);
        firmware.join().unwrap();
        drop(slave_file);
        let report = result.expect("service did not complete a 3000-cycle window");
        let window = &report["last_3000"];
        assert_eq!(window["cycles"], 3000);
        assert_eq!(window["success"], 2998, "{window}");
        assert_eq!(window["communication_failures"], 2);
        assert_eq!(window["imu_faults"], 0);
        assert_eq!(window["bad_checksums"], 1);
        assert_eq!(window["missing_by_id"], json!({"12":1,"13":1}));
        assert_eq!(report["last_failure"]["trace"]["missing_ids"], json!([12]));
        assert_eq!(
            report["last_sample"]["servos"].as_array().unwrap().len(),
            15
        );
        assert!(
            written
                .lock()
                .unwrap()
                .iter()
                .all(|op| matches!(op, 2 | 0x82))
        );
    }
}

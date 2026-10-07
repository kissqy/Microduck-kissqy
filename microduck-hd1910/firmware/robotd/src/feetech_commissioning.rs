//! Commission the real Feetech bus through robotd's socket. The control thread is
//! the sole UART owner; raw positions never masquerade as calibrated joint angles.
use super::{Ordering, RobotState};
use clap::Subcommand;
use duck_control::feetech::{
    Bus, Calibration, IMU_ID, IMU_IDENTITY, ImuSample, ServoSample, signed_position_word,
};
use duck_control::imu::SflpDecoder;
use duck_control::model::{JOINT_IDS, NUM_JOINTS};
use duck_ipc_proto as proto;
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::collections::{BTreeMap, VecDeque};
use std::path::{Path, PathBuf};
use std::process::ExitCode;
use std::sync::atomic::AtomicBool;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::sync::oneshot;

pub const BUILD: &str = "1fa8438-feetech-ft6-control.29";
const MAX_PENDING: usize = 16;
const POSITION_TOLERANCE: u16 = 8;
const SETTLE_TIMEOUT: Duration = Duration::from_secs(4);
type Reply = Result<Value, String>;

#[derive(Debug, Clone, Subcommand, Serialize, Deserialize)]
#[serde(tag = "action", rename_all = "kebab-case", deny_unknown_fields)]
pub enum BusCommand {
    /// Immediately interrupt commissioning movement and cut torque on all joints.
    Relax,
    /// Confirm torque-off, then reboot this Zero after returning the RPC reply.
    Reboot {},
    /// Confirm torque-off, then power off this Zero after returning the RPC reply.
    Shutdown {},
    /// Move one identified servo in encoder counts, then release its torque.
    Move {
        #[arg(long)]
        id: u8,
        #[arg(long)]
        position: u16,
        #[arg(long, default_value_t = 2000)]
        duration_ms: u64,
    },
    /// Sequentially center loose, unassembled servos. Never a joint calibration.
    Center {
        #[arg(long, required = true)]
        unassembled: bool,
        #[arg(long, default_value_t = 2000)]
        duration_ms: u64,
    },
    /// Record a known physical joint angle using its current encoder position.
    Capture {
        #[arg(long)]
        id: u8,
        #[arg(long, allow_hyphen_values = true)]
        angle_deg: f64,
        #[arg(long, allow_hyphen_values = true)]
        direction: i8,
        #[arg(long, allow_hyphen_values = true)]
        min_deg: f64,
        #[arg(long, allow_hyphen_values = true)]
        max_deg: f64,
    },
    /// Show the persisted calibration and what still prevents full control.
    CalibrationStatus,
    /// Record that the official IMU mounting axes have been physically checked.
    VerifyImu {
        #[arg(long, required = true)]
        confirmed: bool,
        /// Sensor-to-trunk quaternion, scalar first. Omit to retain configured mounting.
        #[arg(long, value_delimiter = ',', num_args = 4, allow_hyphen_values = true)]
        #[serde(default)]
        mount_wxyz: Vec<f64>,
    },
}

fn command_timeout(command: &BusCommand) -> Duration {
    match command {
        BusCommand::Move { duration_ms, .. } => {
            Duration::from_millis((*duration_ms).min(60_000)) + Duration::from_secs(15)
        }
        BusCommand::Center { duration_ms, .. } => {
            Duration::from_millis((*duration_ms).min(60_000) * NUM_JOINTS as u64)
                + Duration::from_secs(8 * NUM_JOINTS as u64 + 15)
        }
        _ => Duration::from_secs(15),
    }
}

struct Job {
    command: BusCommand,
    reply: oneshot::Sender<Reply>,
}

#[derive(Default)]
pub struct Commands {
    pending: Mutex<VecDeque<Job>>,
    power_pending: AtomicBool,
}
impl Commands {
    fn push(&self, job: Job) -> Result<(), String> {
        let mut queue = self
            .pending
            .lock()
            .map_err(|_| "bus command queue unavailable")?;
        if self.power_pending.load(Ordering::Relaxed)
            && !matches!(
                job.command,
                BusCommand::Relax | BusCommand::CalibrationStatus
            )
        {
            return Err("Zero power operation pending; new movement refused".into());
        }
        // Relax remains available even when the queue is full and takes priority.
        if matches!(job.command, BusCommand::Relax) {
            while let Some(old) = queue.pop_front() {
                let _ = old.reply.send(Err("cancelled by relax".into()));
            }
            queue.push_front(job);
        } else if queue.len() >= MAX_PENDING {
            return Err("bus command queue full".into());
        } else {
            queue.push_back(job);
        }
        Ok(())
    }
    fn pop(&self) -> Option<Job> {
        self.pending.lock().ok()?.pop_front()
    }
    fn cancel_all(&self, reason: &str) {
        if let Ok(mut queue) = self.pending.lock() {
            for job in queue.drain(..) {
                let _ = job.reply.send(Err(reason.to_owned()));
            }
        }
    }
}

pub async fn dispatch(state: &RobotState, id: proto::Id, params: Value) -> proto::Response {
    let fail = |message: String| {
        proto::Response::err(
            Some(id.clone()),
            proto::Error::new(proto::code::INVALID_REQUEST, message),
        )
    };
    let command: BusCommand = match serde_json::from_value(params) {
        Ok(command) => command,
        Err(e) => return fail(format!("invalid bus command: {e}")),
    };
    if matches!(command, BusCommand::CalibrationStatus) {
        return match state.bus_calibration.load_full() {
            Some(calibration) => proto::Response::ok(Some(id), calibration.as_ref()),
            None => fail("calibration not available yet".into()),
        };
    }
    if !state.commissioning.load(Ordering::Relaxed) {
        return fail("raw bus commands require the running robotd commissioning mode".into());
    }
    let power = match command {
        BusCommand::Reboot {} => Some("reboot"),
        BusCommand::Shutdown {} => Some("poweroff"),
        _ => None,
    };
    if power.is_some()
        && state
            .bus_commands
            .power_pending
            .swap(true, Ordering::Relaxed)
    {
        return fail("a Zero power operation is already pending".into());
    }
    let command = if power.is_some() {
        BusCommand::Relax
    } else {
        command
    };
    let timeout = command_timeout(&command);
    let (reply, receive) = oneshot::channel();
    if let Err(error) = state.bus_commands.push(Job { command, reply }) {
        if power.is_some() {
            state
                .bus_commands
                .power_pending
                .store(false, Ordering::Relaxed);
        }
        return fail(error);
    }
    let mut result = match tokio::time::timeout(timeout, receive).await {
        Ok(Ok(value)) => value,
        Ok(Err(_)) => Err("bus command cancelled because its controller stopped".into()),
        Err(_) => Err("bus command timed out; check robot.busStatus".into()),
    };
    if let Some(operation) = power {
        if result.is_ok() {
            // Existing robotd runs as root on this Zero. Do not change sudoers or
            // collect passwords in the web app. Only these two fixed operations.
            result = match std::process::Command::new("/usr/bin/systemd-run")
                .args([
                    "--quiet",
                    "--collect",
                    "--on-active=3s",
                    "--timer-property=AccuracySec=1s",
                    "/usr/bin/systemctl",
                    operation,
                ])
                .output()
            {
                Ok(output) if output.status.success() => Ok(
                    json!({"power_action":operation,"scheduled":true,"delay_seconds":3,"torque":"off"}),
                ),
                Ok(output) => Err(format!(
                    "Zero power request failed: {}",
                    String::from_utf8_lossy(&output.stderr)
                )),
                Err(error) => Err(format!("cannot schedule Zero power request: {error}")),
            };
        }
        if result.is_err() {
            state
                .bus_commands
                .power_pending
                .store(false, Ordering::Relaxed);
        }
    }
    match result {
        Ok(value) => proto::Response::ok(Some(id), &value),
        Err(error) => fail(error),
    }
}

pub async fn cli(socket: &Path, command: &BusCommand) -> ExitCode {
    let run = async {
        let stream = tokio::net::UnixStream::connect(socket).await?;
        let (read, mut write) = stream.into_split();
        let request =
            json!({"jsonrpc":"2.0", "id":1, "method":"robot.busCommand", "params":command});
        let mut encoded = serde_json::to_vec(&request).map_err(std::io::Error::other)?;
        encoded.push(b'\n');
        write.write_all(&encoded).await?;
        let mut lines = BufReader::new(read).lines();
        let line = tokio::time::timeout(
            command_timeout(command) + Duration::from_secs(5),
            lines.next_line(),
        )
        .await
        .map_err(|_| std::io::Error::other("robotd command timed out"))??
        .ok_or_else(|| std::io::Error::other("robotd closed the connection"))?;
        let value: Value = serde_json::from_str(&line).map_err(std::io::Error::other)?;
        if let Some(error) = value.get("error") {
            return Err(std::io::Error::other(error.to_string()));
        }
        println!(
            "{}",
            serde_json::to_string_pretty(&value["result"]).map_err(std::io::Error::other)?
        );
        Ok::<(), std::io::Error>(())
    };
    match run.await {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("{error}");
            ExitCode::FAILURE
        }
    }
}

fn read_calibration(path: &Path) -> Result<Calibration, String> {
    match std::fs::read_to_string(path) {
        Ok(text) => {
            let calibration: Calibration =
                toml::from_str(&text).map_err(|e| format!("{}: {e}", path.display()))?;
            calibration.validate().map_err(|e| e.to_string())?;
            Ok(calibration)
        }
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
            Ok(Calibration::commissioning(JOINT_IDS))
        }
        Err(e) => Err(format!("{}: {e}", path.display())),
    }
}

fn save_calibration(path: &Path, calibration: &Calibration) -> Result<(), String> {
    calibration.validate().map_err(|e| e.to_string())?;
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let encoded = toml::to_string_pretty(calibration).map_err(|e| e.to_string())?;
    for target in [path.to_path_buf(), path.with_extension("saved.toml")] {
        let temporary: PathBuf = target.with_extension(format!("toml.tmp.{}", std::process::id()));
        let result = (|| -> std::io::Result<()> {
            use std::io::Write;
            let mut file = std::fs::OpenOptions::new()
                .write(true)
                .create_new(true)
                .open(&temporary)?;
            file.write_all(encoded.as_bytes())?;
            file.sync_all()?;
            std::fs::rename(&temporary, &target)?;
            if let Some(parent) = target.parent() {
                std::fs::File::open(parent)?.sync_all()?;
            }
            Ok(())
        })();
        if result.is_err() {
            let _ = std::fs::remove_file(&temporary);
        }
        result.map_err(|e| format!("cannot save {}: {e}", target.display()))?;
    }
    Ok(())
}

pub(crate) fn calibration_status(calibration: &Calibration, path: &Path) -> Value {
    let missing = calibration
        .joints
        .iter()
        .filter(|joint| !joint.calibrated)
        .map(|joint| joint.name.as_str())
        .collect::<Vec<_>>();
    json!({"calibration_path":path, "calibration":calibration, "uncalibrated_joints":missing,
        "motion_validation":calibration.validate_motion().err().map(|e| e.to_string()),
        "note":"Capture uses a manually known joint angle; encoder center is not joint zero."})
}

fn capture(
    calibration: &Calibration,
    samples: &BTreeMap<u8, ServoSample>,
    id: u8,
    angle_deg: f64,
    direction: i8,
    min_deg: f64,
    max_deg: f64,
) -> Result<Calibration, String> {
    if ![-1, 1].contains(&direction)
        || ![angle_deg, min_deg, max_deg].iter().all(|v| v.is_finite())
        || min_deg >= max_deg
        || !(min_deg..=max_deg).contains(&angle_deg)
    {
        return Err(
            "capture needs direction -1/+1 and finite min < max containing the measured angle"
                .into(),
        );
    }
    let sample = samples
        .get(&id)
        .ok_or_else(|| format!("ID {id} is not a configured joint"))?;
    let zero =
        f64::from(sample.feedback.position_raw) - f64::from(direction) * angle_deg / 360.0 * 4096.0;
    if !(0.0..=4095.0).contains(&zero) {
        return Err("calculated zero is outside 0..4095; check angle and direction".into());
    }
    let mut updated = calibration.clone();
    let joint = updated
        .joints
        .iter_mut()
        .find(|joint| joint.id == id)
        .ok_or("unknown joint ID")?;
    joint.zero_raw = zero.round() as u16;
    joint.direction = direction;
    joint.min_rad = Some(min_deg.to_radians());
    joint.max_rad = Some(max_deg.to_radians());
    joint.calibrated = true;
    updated.motion_enabled = false;
    // Verify both physical travel endpoints before allowing this calibration to persist.
    for angle in [min_deg, max_deg] {
        let raw = f64::from(joint.zero_raw) + f64::from(direction) * angle / 360.0 * 4096.0;
        if !(0.0..=4095.0).contains(&raw) {
            return Err("joint limits cross the single-turn encoder boundary".into());
        }
    }
    updated.validate().map_err(|e| e.to_string())?;
    Ok(updated)
}

#[derive(Clone, Copy)]
enum MotionStage {
    Preload,
    ConfirmGoal,
    Enable,
    ConfirmEnabled,
    Moving,
    Disable,
    ConfirmDisabled,
}

struct Motion {
    remaining: VecDeque<u8>,
    active_id: u8,
    from: i32,
    target: u16,
    started: Instant,
    duration: Duration,
    reply: oneshot::Sender<Reply>,
    completed: Vec<u8>,
    center: bool,
    stage: MotionStage,
    last_target: Option<i32>,
    torque_confirmed: Option<bool>,
    deadline: Instant,
}

fn torque_off(bus: &mut Bus, ids: &[u8]) -> Result<(), String> {
    bus.torque(ids, false).map_err(|e| e.to_string())?;
    bus.verify_torque(ids, false).map_err(|e| e.to_string())
}

fn abort_motion(
    bus: &mut Bus,
    ids: &[u8],
    motion: &mut Option<Motion>,
    reason: &str,
) -> Option<String> {
    let stop_error = torque_off(bus, ids).err();
    if let Some(moving) = motion.take() {
        let suffix = stop_error
            .as_ref()
            .map(|e| format!("; torque-off not confirmed: {e}"))
            .unwrap_or_default();
        let _ = moving.reply.send(Err(format!(
            "{reason}; active ID {}; completed IDs {:?}{suffix}",
            moving.active_id, moving.completed
        )));
    }
    stop_error
}

fn center_partition(ids: &[u8], samples: &BTreeMap<u8, ServoSample>) -> (Vec<u8>, VecDeque<u8>) {
    let (done, pending): (Vec<_>, Vec<_>) = ids.iter().copied().partition(|id| {
        samples.get(id).is_some_and(|s| {
            s.feedback.position_raw.abs_diff(2048) <= u32::from(POSITION_TOLERANCE)
                && !s.feedback.moving
        })
    });
    (done, pending.into())
}

fn process_job(
    job: Job,
    bus: &mut Bus,
    samples: &BTreeMap<u8, ServoSample>,
    calibration: &mut Calibration,
    path: &Path,
    motion: &mut Option<Motion>,
    ids: &[u8],
    off_pending: &mut Option<String>,
) {
    if job.reply.is_closed() {
        return;
    }
    if matches!(job.command, BusCommand::Relax) {
        let stop_error = abort_motion(bus, ids, motion, "movement interrupted by relax");
        *off_pending = stop_error.clone();
        let result =
            stop_error.map_or_else(|| Ok(json!({"torque":"off", "confirmed_ids":ids})), Err);
        let _ = job.reply.send(result);
        return;
    }
    if matches!(job.command, BusCommand::CalibrationStatus) {
        let _ = job.reply.send(Ok(calibration_status(calibration, path)));
        return;
    }
    if off_pending.is_some() {
        let _ = job.reply.send(Err(
            "torque-off has not been confirmed; wait for busStatus torque_off_pending to clear"
                .into(),
        ));
        return;
    }
    if motion.is_some() {
        let _ = job.reply.send(Err(
            "a movement is already active; use bus relax to interrupt it".into(),
        ));
        return;
    }
    match job.command {
        BusCommand::Move {
            id,
            position,
            duration_ms,
        } => {
            if !ids.contains(&id) || position > 4095 || !(500..=60_000).contains(&duration_ms) {
                let _ = job.reply.send(Err("move requires a configured servo ID, position 0..4095 and duration-ms 500..60000".into()));
                return;
            }
            if let Some(joint) = calibration.joints.iter().find(|joint| joint.id == id)
                && let (Some(min), Some(max)) = (joint.min_rad, joint.max_rad)
            {
                let angle = (f64::from(position) - f64::from(joint.zero_raw))
                    * std::f64::consts::TAU
                    / 4096.0
                    * f64::from(joint.direction);
                if !(min..=max).contains(&angle) {
                    let _ = job.reply.send(Err(
                        "requested raw position exceeds this joint's saved physical limits".into(),
                    ));
                    return;
                }
            }
            *motion = Some(Motion {
                remaining: VecDeque::new(),
                active_id: id,
                from: samples[&id].feedback.position_raw,
                target: position,
                started: Instant::now(),
                duration: Duration::from_millis(duration_ms),
                reply: job.reply,
                completed: vec![],
                center: false,
                stage: MotionStage::Preload,
                last_target: None,
                torque_confirmed: Some(false),
                deadline: Instant::now()
                    + Duration::from_millis(duration_ms)
                    + SETTLE_TIMEOUT
                    + Duration::from_secs(1),
            });
        }

        BusCommand::Center {
            unassembled,
            duration_ms,
        } => {
            if !unassembled || !(500..=60_000).contains(&duration_ms) {
                let _ = job.reply.send(Err(
                    "center requires --unassembled and duration-ms 500..60000; it is unsuitable for assembled joints".into(),
                ));
                return;
            }
            if calibration.joints.iter().any(|j| j.calibrated) {
                let _ = job
                    .reply
                    .send(Err("center is unavailable after joint calibration".into()));
                return;
            }
            // A new click always uses fresh positions, including after a previous
            // cancelled job or service restart. Never repeat already-centered joints.
            let (completed, mut remaining) = center_partition(ids, samples);
            let Some(id) = remaining.pop_front() else {
                let _ = job.reply.send(Ok(
                    json!({"completed_ids":completed,"position_raw":2048,"torque":"off"}),
                ));
                return;
            };
            *motion = Some(Motion {
                remaining,
                active_id: id,
                from: samples[&id].feedback.position_raw,
                target: 2048,
                started: Instant::now(),
                duration: Duration::from_millis(duration_ms),
                reply: job.reply,
                completed,
                center: true,
                stage: MotionStage::Preload,
                last_target: None,
                torque_confirmed: Some(false),
                deadline: Instant::now()
                    + Duration::from_millis(duration_ms * ids.len() as u64)
                    + SETTLE_TIMEOUT * ids.len() as u32
                    + Duration::from_secs(30),
            });
        }

        BusCommand::Capture {
            id,
            angle_deg,
            direction,
            min_deg,
            max_deg,
        } => {
            let result = capture(calibration, samples, id, angle_deg, direction, min_deg, max_deg).and_then(|updated| {
                save_calibration(path, &updated)?;
                *calibration = updated;
                Ok(json!({"saved":true,"id":id,"position_raw":samples[&id].feedback.position_raw,
                    "known_angle_deg":angle_deg,"calibration":calibration_status(calibration,path)}))
            });
            let _ = job.reply.send(result);
        }
        BusCommand::VerifyImu {
            confirmed,
            mount_wxyz,
        } => {
            let result = if confirmed {
                let mut updated = calibration.clone();
                if !mount_wxyz.is_empty() {
                    match mount_wxyz.try_into() {
                        Ok(mount) => updated.imu_mount_quat = mount,
                        Err(_) => {
                            let _ = job
                                .reply
                                .send(Err("mount-wxyz needs exactly four values: w,x,y,z".into()));
                            return;
                        }
                    }
                }
                updated.imu_mount_verified = true;
                updated.motion_enabled = false;
                save_calibration(path, &updated).map(|()| {
                    *calibration = updated;
                    calibration_status(calibration, path)
                })
            } else {
                Err(
                    "verify-imu requires --confirmed after checking the official mounting axes"
                        .into(),
                )
            };
            let _ = job.reply.send(result);
        }
        BusCommand::Relax
        | BusCommand::CalibrationStatus
        | BusCommand::Reboot {}
        | BusCommand::Shutdown {} => unreachable!(),
    }
}

fn step_motion(
    bus: &mut Bus,
    samples: &BTreeMap<u8, ServoSample>,
    ids: &[u8],
    motion: &mut Option<Motion>,
    off_pending: &mut Option<String>,
) {
    let Some(m) = motion.as_mut() else {
        return;
    };
    if m.reply.is_closed() || Instant::now() >= m.deadline {
        *off_pending = abort_motion(bus, ids, motion, "movement cancelled or timed out");
        return;
    }
    let step = (|| -> Result<bool, String> {
        match m.stage {
            MotionStage::Preload => {
                let feedback = &samples[&m.active_id].feedback;
                m.from = feedback.position_raw;
                bus.signed_positions(&[(m.active_id, feedback.position_signed_raw)])
                    .map_err(|e| e.to_string())?;
                m.stage = MotionStage::ConfirmGoal;
            }
            MotionStage::ConfirmGoal => {
                if bus
                    .read_control(m.active_id, 42, 2)
                    .map_err(|e| e.to_string())?
                    != signed_position_word(m.from)
                        .map_err(|e| e.to_string())?
                        .to_le_bytes()
                {
                    return Err("hold goal preload was not confirmed".into());
                }
                m.stage = MotionStage::Enable;
            }
            MotionStage::Enable => {
                bus.torque(&[m.active_id], true)
                    .map_err(|e| e.to_string())?;
                m.torque_confirmed = None;
                m.stage = MotionStage::ConfirmEnabled;
            }
            MotionStage::ConfirmEnabled => {
                if bus
                    .read_control(m.active_id, 40, 1)
                    .map_err(|e| e.to_string())?
                    != [1]
                {
                    return Err("torque-on was not confirmed".into());
                }
                m.torque_confirmed = Some(true);
                m.started = Instant::now();
                m.stage = MotionStage::Moving;
            }
            MotionStage::Moving => {
                let elapsed = m.started.elapsed();
                let fraction = (elapsed.as_secs_f64() / m.duration.as_secs_f64()).min(1.0);
                let target = (f64::from(m.from)
                    + (f64::from(m.target) - f64::from(m.from)) * fraction)
                    .round() as i32;
                if m.last_target != Some(target) {
                    bus.signed_positions(&[(m.active_id, target)])
                        .map_err(|e| e.to_string())?;
                    m.last_target = Some(target);
                }
                if elapsed >= m.duration
                    && samples[&m.active_id]
                        .feedback
                        .position_signed_raw
                        .abs_diff(i32::from(m.target))
                        <= u32::from(POSITION_TOLERANCE)
                {
                    m.stage = MotionStage::Disable;
                } else if elapsed > m.duration + SETTLE_TIMEOUT {
                    return Err(format!(
                        "ID {} did not reach {}; stopped",
                        m.active_id, m.target
                    ));
                }
            }
            MotionStage::Disable => {
                bus.torque(&[m.active_id], false)
                    .map_err(|e| e.to_string())?;
                m.torque_confirmed = None;
                m.stage = MotionStage::ConfirmDisabled;
            }
            MotionStage::ConfirmDisabled => {
                if bus
                    .read_control(m.active_id, 40, 1)
                    .map_err(|e| e.to_string())?
                    != [0]
                {
                    return Err("torque-off was not confirmed".into());
                }
                m.torque_confirmed = Some(false);
                m.completed.push(m.active_id);
                if let Some(next) = m.remaining.pop_front() {
                    m.active_id = next;
                    m.stage = MotionStage::Preload;
                    m.last_target = None;
                } else {
                    return Ok(true);
                }
            }
        }
        Ok(false)
    })();
    match step {
        Ok(true) => {
            let done = motion.take().unwrap();
            let _ = done.reply.send(Ok(
                json!({"completed_ids":done.completed,"position_raw":done.target,"torque":"off"}),
            ));
        }
        Ok(false) => {}
        Err(error) => *off_pending = abort_motion(bus, ids, motion, &error),
    }
}

#[derive(Clone, Serialize)]
pub struct ServoStatus {
    id: u8,
    joint: String,
    position_raw: i32,
    position_wire_raw: u16,
    position_signed_raw: i32,
    speed_raw: i32,
    load_raw: i32,
    current_raw: i32,
    voltage_v: f64,
    temperature_c: u8,
    moving: bool,
    calibrated: bool,
}
#[derive(Clone, Serialize)]
pub struct ImuStatus {
    id: u8,
    sequence: u32,
    ready: bool,
    valid: bool,
    gravity: [f64; 3],
    gyro_rad_s: [f64; 3],
    quaternion_wxyz: [f64; 4],
    mount_verified: bool,
}
#[derive(Clone, Serialize)]
pub struct Sample {
    cycle: u64,
    at_us: u64,
    servos: Vec<ServoStatus>,
    imu: ImuStatus,
}
#[derive(Clone, Serialize)]
pub struct Failure {
    cycle: u64,
    error: String,
    missing_ids: Vec<u8>,
}
#[derive(Clone, Serialize)]
pub struct MotionStatus {
    id: u8,
    target_raw: u16,
    action: &'static str,
    completed_ids: Vec<u8>,
}
/// Plain snapshot published at 10 Hz. JSON is produced only by the IPC thread.
#[derive(Clone, Serialize)]
pub struct Status {
    build: &'static str,
    port: String,
    mode: &'static str,
    phase: &'static str,
    session: u32,
    target_hz: f64,
    achieved_hz: f64,
    total_cycles: u64,
    total_success: u64,
    total_communication_failures: u64,
    errors_by_id: BTreeMap<u8, u64>,
    device_communication: super::communication_stats::CommunicationStats,
    last_cycle_error: Option<String>,
    last_failure: Option<Failure>,
    last_sample: Option<Sample>,
    calibrated: bool,
    imu_mount_verified: bool,
    torque_state: &'static str,
    torque_off_pending: Option<String>,
    power_pending: bool,
    motion: Option<MotionStatus>,
    policy_motion_enabled: bool,
    updated_at_us: u64,
}

/// An installation-only barrier: no periodic polling after startup. The helper
/// applies FIFO/IRQ settings while this UART is open and completely idle.
pub async fn await_uart_setup(state: &RobotState, port: &str, mode: &str) -> Result<(), String> {
    state.uart_setup_ready.store(false, Ordering::Release);
    state.bus_status.store(Some(Arc::new(
        json!({"build":BUILD,"mode":mode,"phase":"configuring_uart","port":port}),
    )));
    let until = Instant::now() + Duration::from_secs(8);
    while !state.uart_setup_ready.load(Ordering::Acquire) {
        if state.shutdown.load(Ordering::Relaxed) || Instant::now() >= until {
            return Err("UART startup configuration did not complete".into());
        }
        tokio::time::sleep(Duration::from_millis(10)).await;
    }
    Ok(())
}

pub async fn run(
    port: &str,
    state: &RobotState,
    period: Duration,
    calibration_path: &Path,
    uart_setup: bool,
) {
    state.imu_ready.store(false, Ordering::Relaxed);
    let mut calibration = match read_calibration(calibration_path) {
        Ok(c) => c,
        Err(error) => {
            state.bus_status.store(Some(Arc::new(json!({"build":BUILD,"mode":"commissioning","phase":"configuration_error","error":error}))));
            state.startup_bus_failures.store(1, Ordering::Relaxed);
            return;
        }
    };
    if !calibration_path.exists() {
        if let Err(error) = save_calibration(calibration_path, &calibration) {
            state.bus_status.store(Some(Arc::new(json!({"build":BUILD,"mode":"commissioning","phase":"configuration_error","error":error}))));
            state.startup_bus_failures.store(1, Ordering::Relaxed);
            return;
        }
    }
    state
        .bus_calibration
        .store(Some(Arc::new(calibration_status(
            &calibration,
            calibration_path,
        ))));
    let ids = calibration.joints.iter().map(|j| j.id).collect::<Vec<_>>();
    let connect = async {
        let mut bus = Bus::open(port).map_err(|e| e.to_string())?;
        if uart_setup {
            await_uart_setup(state, port, "commissioning").await?;
        }
        if bus.read(IMU_ID, 0, 5).map_err(|e| e.to_string())? != IMU_IDENTITY {
            return Err("IMU200 requires FT6 firmware (06 00 00 00 f2)".into());
        }
        torque_off(&mut bus, &ids)?;
        Ok::<Bus, String>(bus)
    }
    .await;
    let mut bus = match connect {
        Ok(bus) => bus,
        Err(error) => {
            state.startup_bus_failures.store(1, Ordering::Relaxed);
            state.bus_status.store(Some(Arc::new(json!({"build":BUILD,"mode":"commissioning","phase":"configuration_error","error":error}))));
            state.bus_commands.cancel_all(&error);
            tracing::error!(%error,"bus initialization failed; restart after correcting the fault");
            return;
        }
    };
    state.startup_bus_failures.store(0, Ordering::Relaxed);
    let mut ticker = super::control_ticker(period);
    // Tokio intervals tick immediately on creation. Start periodic telemetry one
    // normal period after startup torque verification, not in the same burst.
    // This runs once: no warm-up read, discarded failure or steady-state delay.
    ticker.reset_after(period);
    let mut rate_start = Instant::now();
    let mut rate_ticks = 0u64;
    let mut total_success = 0u64;
    let mut total_failures = 0u64;
    let mut last_sequence = None;
    let mut stale_run = 0u64;
    let mut motion: Option<Motion> = None;
    let mut off_pending = None;
    let mut imu_decoder = SflpDecoder::new(calibration.imu_mount_quat);
    let mut last_sample = None;
    let mut last_failure = None;
    let mut errors_by_id = BTreeMap::<u8, u64>::new();
    let mut communication_stats =
        super::communication_stats::CommunicationStats::new(ids.iter().copied().chain([IMU_ID]));
    let mut next_publish = Instant::now();
    while !state.shutdown.load(Ordering::Relaxed) {
        ticker.tick().await;
        if state.shutdown.load(Ordering::Relaxed) {
            break;
        }
        let tick = Instant::now();
        let cycle = state.ticks.load(Ordering::Relaxed) + 1;
        let publish = tick >= next_publish;
        let mut samples = BTreeMap::new();
        let mut imu_status = None;
        let result = (|| -> Result<(), String> {
            let acquisition = bus.telemetry(&ids);
            communication_stats.observe(&bus.last_sync);
            let blocks = acquisition.map_err(|e| e.to_string())?;
            for id in &ids {
                let sample =
                    ServoSample::decode(&blocks[id]).map_err(|e| format!("ID {id}: {e}"))?;
                samples.insert(*id, sample);
            }
            let imu = ImuSample::decode(&blocks[&IMU_ID]).map_err(|e| format!("IMU200: {e}"))?;
            let duplicate = last_sequence == Some(imu.sequence);
            stale_run = if duplicate { stale_run + 1 } else { 0 };
            last_sequence = Some(imu.sequence);
            if duplicate {
                state.imu_stale_blocks.fetch_add(1, Ordering::Relaxed);
            }
            state.imu_stale_run.store(stale_run, Ordering::Relaxed);
            let decoded = imu_decoder.decode(&imu.block);
            if !imu.is_fresh(bus.last_sync.elapsed_us) || stale_run >= 3 {
                return Err("IMU200 data stale or not ready".into());
            }
            let valid = imu_decoder.ready();
            state.imu_ready.store(valid, Ordering::Relaxed);
            if publish {
                imu_status = Some(ImuStatus {
                    id: IMU_ID,
                    sequence: imu.sequence,
                    ready: imu.ready,
                    valid,
                    gravity: decoded.gravity,
                    gyro_rad_s: decoded.gyro,
                    quaternion_wxyz: decoded.quat,
                    mount_verified: calibration.imu_mount_verified,
                });
            }
            Ok(())
        })();
        let error = result.err();
        if let Some(error) = &error {
            total_failures += 1;
            if error.starts_with("IMU200") {
                *errors_by_id.entry(IMU_ID).or_default() += 1;
            }
            for id in &bus.last_sync.missing_ids {
                *errors_by_id.entry(*id).or_default() += 1;
            }
            last_failure = Some(Failure {
                cycle,
                error: error.clone(),
                missing_ids: bus.last_sync.missing_ids.clone(),
            });
            state.imu_ready.store(false, Ordering::Relaxed);
            let consecutive = state.consecutive_errors.fetch_add(1, Ordering::Relaxed) + 1;
            if motion.is_some() {
                off_pending = abort_motion(&mut bus, &ids, &mut motion, error);
            }
            if consecutive == 1 {
                tracing::warn!(cycle,%error,"bus read failed");
            }
            while let Some(job) = state.bus_commands.pop() {
                if matches!(job.command, BusCommand::Relax) {
                    process_job(
                        job,
                        &mut bus,
                        &samples,
                        &mut calibration,
                        calibration_path,
                        &mut motion,
                        &ids,
                        &mut off_pending,
                    );
                } else {
                    let _ = job.reply.send(Err(error.clone()));
                }
            }
        } else {
            total_success += 1;
            state.consecutive_errors.store(0, Ordering::Relaxed);
            if publish {
                let servos = calibration
                    .joints
                    .iter()
                    .map(|j| {
                        let x = &samples[&j.id];
                        let f = &x.feedback;
                        ServoStatus {
                            id: j.id,
                            joint: j.name.clone(),
                            position_raw: f.position_raw,
                            position_wire_raw: f.position_wire_raw,
                            position_signed_raw: f.position_signed_raw,
                            speed_raw: f.speed_raw,
                            load_raw: f.load_raw,
                            current_raw: x.current_raw,
                            voltage_v: f.volts,
                            temperature_c: f.temperature_c,
                            moving: f.moving,
                            calibrated: j.calibrated,
                        }
                    })
                    .collect();
                last_sample = Some(Sample {
                    cycle,
                    at_us: state.started.elapsed().as_micros() as u64,
                    servos,
                    imu: imu_status.unwrap(),
                });
                let volts =
                    samples.values().map(|s| s.feedback.volts).sum::<f64>() / NUM_JOINTS as f64;
                state.battery_v.store(volts.to_bits(), Ordering::Relaxed);
                let (hottest, temp) = calibration
                    .joints
                    .iter()
                    .enumerate()
                    .map(|(i, j)| (i, samples[&j.id].feedback.temperature_c))
                    .max_by_key(|(_, t)| *t)
                    .unwrap();
                state
                    .motor_max_c
                    .store(f64::from(temp).to_bits(), Ordering::Relaxed);
                state.motor_hottest.store(hottest as u32, Ordering::Relaxed);
                state.motor_mean_c.store(
                    (samples
                        .values()
                        .map(|s| f64::from(s.feedback.temperature_c))
                        .sum::<f64>()
                        / NUM_JOINTS as f64)
                        .to_bits(),
                    Ordering::Relaxed,
                );
            }
            if let Some(job) = state.bus_commands.pop() {
                let changes_calibration = matches!(
                    job.command,
                    BusCommand::Capture { .. } | BusCommand::VerifyImu { .. }
                );
                let old_mount = calibration.imu_mount_quat;
                process_job(
                    job,
                    &mut bus,
                    &samples,
                    &mut calibration,
                    calibration_path,
                    &mut motion,
                    &ids,
                    &mut off_pending,
                );
                if changes_calibration {
                    state
                        .bus_calibration
                        .store(Some(Arc::new(calibration_status(
                            &calibration,
                            calibration_path,
                        ))));
                }
                if old_mount != calibration.imu_mount_quat {
                    imu_decoder = SflpDecoder::new(calibration.imu_mount_quat);
                }
            }
            step_motion(&mut bus, &samples, &ids, &mut motion, &mut off_pending);
        }
        state
            .moving
            .store(motion.is_some() || off_pending.is_some(), Ordering::Relaxed);
        state.ticks.store(cycle, Ordering::Relaxed);
        state.last_tick_us.store(
            state.started.elapsed().as_micros() as u64,
            Ordering::Relaxed,
        );
        rate_ticks += 1;
        if rate_start.elapsed() >= super::RATE_WINDOW {
            state.achieved_hz.store(
                (rate_ticks as f64 / rate_start.elapsed().as_secs_f64()).to_bits(),
                Ordering::Relaxed,
            );
            rate_ticks = 0;
            rate_start = Instant::now();
        }
        if publish || error.is_some() {
            let power = state.bus_commands.power_pending.load(Ordering::Relaxed);
            state.bus_snapshot.store(Some(Arc::new(Status {
                build: BUILD,
                port: port.to_owned(),
                mode: "commissioning",
                phase: if power {
                    "power_pending"
                } else if error.is_some() {
                    "read_error"
                } else if off_pending.is_some() {
                    "stop_unconfirmed"
                } else if motion.is_some() {
                    "moving"
                } else {
                    "ready"
                },
                session: std::process::id(),
                target_hz: 1.0 / period.as_secs_f64(),
                achieved_hz: f64::from_bits(state.achieved_hz.load(Ordering::Relaxed)),
                total_cycles: cycle,
                total_success,
                total_communication_failures: total_failures,
                errors_by_id: errors_by_id.clone(),
                device_communication: communication_stats.clone(),
                last_cycle_error: error,
                last_failure: last_failure.clone(),
                last_sample: last_sample.clone(),
                calibrated: calibration.joints.iter().all(|j| j.calibrated),
                imu_mount_verified: calibration.imu_mount_verified,
                torque_state: if off_pending.is_some() {
                    "unknown"
                } else if let Some(m) = &motion {
                    match m.torque_confirmed {
                        Some(true) => "single_joint_enabled",
                        Some(false) => "off",
                        None => "unknown",
                    }
                } else {
                    "off"
                },
                torque_off_pending: off_pending.clone(),
                power_pending: power,
                policy_motion_enabled: false,
                motion: motion.as_ref().map(|m| MotionStatus {
                    id: m.active_id,
                    target_raw: m.target,
                    action: if m.center { "center" } else { "move" },
                    completed_ids: m.completed.clone(),
                }),
                updated_at_us: state.started.elapsed().as_micros() as u64,
            })));
            next_publish = tick + Duration::from_millis(100);
        }
        if tick.elapsed() > period {
            state.missed.fetch_add(1, Ordering::Relaxed);
        }
    }
    let stop_error = abort_motion(&mut bus, &ids, &mut motion, "service stopping");
    if let Some(error) = stop_error {
        tracing::error!(%error,"shutdown torque-off not confirmed");
    }
    state.bus_commands.cancel_all("service stopping");
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Optimizing the motion Value cache must not shadow commissioning's typed
    /// snapshot or change its existing serialization and error/status fields.
    #[tokio::test]
    async fn typed_bus_status_keeps_priority_and_original_wire_response() {
        let state = Arc::new(RobotState::new(
            &crate::Params::default(),
            Path::new("/nonexistent/robotd.toml"),
            false,
            false,
        ));
        state.commissioning.store(true, Ordering::Relaxed);
        state.raw.publish(crate::raw_stream::tests::fixture(99));
        state
            .bus_status
            .store(Some(Arc::new(json!({"phase":"older-value-cache"}))));
        let report = Status {
            build: BUILD,
            port: "/dev/test-no-uart".into(),
            mode: "commissioning",
            phase: "read_error",
            session: 123,
            target_hz: 50.0,
            achieved_hz: 49.5,
            total_cycles: 42,
            total_success: 40,
            total_communication_failures: 2,
            errors_by_id: [(22, 2)].into_iter().collect(),
            device_communication: crate::communication_stats::CommunicationStats::new([22, 200]),
            last_cycle_error: Some("回包缺失".into()),
            last_failure: Some(Failure {
                cycle: 42,
                error: "missing 22".into(),
                missing_ids: vec![22],
            }),
            last_sample: None,
            calibrated: true,
            imu_mount_verified: true,
            torque_state: "off",
            torque_off_pending: None,
            power_pending: false,
            motion: None,
            policy_motion_enabled: false,
            updated_at_us: 840_000,
        };
        let id = proto::Id::Text("typed-report".into());
        let expected = proto::Response::ok(Some(id.clone()), &report);
        state.bus_snapshot.store(Some(Arc::new(report)));
        let line = crate::tests::ipc_response(
            state,
            json!({"jsonrpc":"2.0", "id":id, "method":"robot.busStatus"}),
        )
        .await;
        assert_eq!(
            line,
            format!("{}\n", serde_json::to_string(&expected).unwrap())
        );
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn workbench_moves_from_signed_feedback_to_the_requested_positive_target() {
        use duck_control::feetech::{READ, SYNC_WRITE, packet};
        use std::fs::File;
        use std::io::{Read, Write};
        use std::os::fd::FromRawFd;
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
        let _slave_file = unsafe { File::from_raw_fd(slave) };
        let mut master_file = unsafe { File::from_raw_fd(master) };
        assert_ne!(
            unsafe { libc::fcntl(master, libc::F_SETFL, libc::O_NONBLOCK) },
            -1
        );
        let stop = Arc::new(AtomicBool::new(false));
        let written = Arc::new(Mutex::new(Vec::new()));
        let worker_stop = Arc::clone(&stop);
        let worker_written = Arc::clone(&written);
        let worker = std::thread::spawn(move || {
            let mut registers = [0u8; 96];
            let mut pending = Vec::new();
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
                    assert_eq!(frame[2..].iter().fold(0u8, |a, b| a.wrapping_add(*b)), 255);
                    let address = usize::from(frame[5]);
                    if frame[4] == SYNC_WRITE {
                        let width = usize::from(frame[6]);
                        for row in frame[7..len - 1].chunks_exact(width + 1) {
                            assert_eq!(row[0], 22);
                            registers[address..address + width].copy_from_slice(&row[1..]);
                            worker_written
                                .lock()
                                .unwrap()
                                .push((address, row[1..].to_vec()));
                        }
                    } else {
                        assert_eq!((frame[2], frame[4]), (22, READ));
                        let count = usize::from(frame[6]);
                        master_file
                            .write_all(
                                &packet(22, 0, &registers[address..address + count]).unwrap(),
                            )
                            .unwrap();
                    }
                }
                std::thread::sleep(Duration::from_micros(200));
            }
        });
        let sample = |position| {
            let mut raw = [0u8; 15];
            raw[..2].copy_from_slice(&signed_position_word(position).unwrap().to_le_bytes());
            ServoSample::decode(&raw).unwrap()
        };
        let mut samples = [(22, sample(-1323))].into_iter().collect();
        let (reply, mut receive) = oneshot::channel();
        let mut motion = Some(Motion {
            remaining: VecDeque::new(),
            active_id: 22,
            from: -1323,
            target: 2276,
            started: Instant::now(),
            duration: Duration::from_secs(1),
            reply,
            completed: vec![],
            center: false,
            stage: MotionStage::Preload,
            last_target: None,
            torque_confirmed: Some(false),
            deadline: Instant::now() + Duration::from_secs(10),
        });
        let mut bus = Bus::open(&path).unwrap();
        let mut off_pending = None;
        for _ in 0..4 {
            step_motion(&mut bus, &samples, &[22], &mut motion, &mut off_pending);
        }
        assert!(matches!(
            motion.as_ref().unwrap().stage,
            MotionStage::Moving
        ));
        assert_eq!(
            bus.read_control(22, 42, 2).unwrap(),
            signed_position_word(-1323).unwrap().to_le_bytes()
        );
        assert_eq!(
            written.lock().unwrap()[..2],
            [(42, vec![0x2b, 0x85, 0, 0, 0, 0]), (40, vec![1])]
        );
        motion.as_mut().unwrap().started = Instant::now() - Duration::from_secs(1);
        // Arrival uses the requested raw value, never its modulo-equivalent.
        samples.insert(22, sample(-1820));
        step_motion(&mut bus, &samples, &[22], &mut motion, &mut off_pending);
        assert!(matches!(
            motion.as_ref().unwrap().stage,
            MotionStage::Moving
        ));
        assert_eq!(
            bus.read_control(22, 42, 6).unwrap(),
            [0xe4, 0x08, 0, 0, 0, 0]
        );
        samples.insert(22, sample(2276));
        for _ in 0..3 {
            step_motion(&mut bus, &samples, &[22], &mut motion, &mut off_pending);
        }
        assert!(motion.is_none() && off_pending.is_none());
        assert_eq!(
            receive.try_recv().unwrap().unwrap()["completed_ids"],
            json!([22])
        );
        assert_eq!(bus.read_control(22, 40, 1).unwrap(), [0]);
        stop.store(true, Ordering::Relaxed);
        worker.join().unwrap();
    }

    #[test]
    fn pending_power_blocks_new_motion_but_allows_confirmed_stop() {
        let commands = Commands::default();
        commands.power_pending.store(true, Ordering::Relaxed);
        let (reply, _receive) = oneshot::channel();
        assert!(
            commands
                .push(Job {
                    command: BusCommand::Move {
                        id: 20,
                        position: 2048,
                        duration_ms: 2000
                    },
                    reply
                })
                .is_err()
        );
        let (reply, _receive) = oneshot::channel();
        commands
            .push(Job {
                command: BusCommand::Relax,
                reply,
            })
            .unwrap();
        assert!(matches!(commands.pop().unwrap().command, BusCommand::Relax));
        assert!(matches!(
            serde_json::from_value::<BusCommand>(json!({"action":"reboot"})).unwrap(),
            BusCommand::Reboot {}
        ));
        assert!(
            serde_json::from_value::<BusCommand>(json!({"action":"reboot","command":"arbitrary"}))
                .is_err()
        );
    }

    #[test]
    fn capture_uses_known_angle_and_direction_without_enabling_motion() {
        let calibration = Calibration::commissioning(JOINT_IDS);
        let mut bytes = [0u8; 15];
        bytes[..2].copy_from_slice(&2300u16.to_le_bytes());
        let samples = [(JOINT_IDS[0], ServoSample::decode(&bytes).unwrap())]
            .into_iter()
            .collect();
        let changed = capture(&calibration, &samples, JOINT_IDS[0], 22.5, -1, -90.0, 90.0).unwrap();
        assert_eq!(changed.joints[0].zero_raw, 2556);
        assert_eq!(changed.joints[0].direction, -1);
        assert!(changed.joints[0].calibrated);
        assert!(!changed.motion_enabled);
        assert!(capture(&calibration, &samples, JOINT_IDS[0], 0.0, 1, 90.0, -90.0).is_err());
        assert!(
            capture(
                &calibration,
                &samples,
                JOINT_IDS[0],
                f64::NAN,
                1,
                -90.0,
                90.0
            )
            .is_err()
        );
    }

    #[test]
    fn relax_cancels_pending_movement_and_takes_priority() {
        let commands = Commands::default();
        let (reply, mut cancelled) = oneshot::channel();
        commands
            .push(Job {
                command: BusCommand::Move {
                    id: 10,
                    position: 2048,
                    duration_ms: 2000,
                },
                reply,
            })
            .unwrap();
        let (reply, _receive) = oneshot::channel();
        commands
            .push(Job {
                command: BusCommand::Relax,
                reply,
            })
            .unwrap();
        assert!(matches!(commands.pop().unwrap().command, BusCommand::Relax));
        assert!(cancelled.try_recv().unwrap().is_err());
    }
}

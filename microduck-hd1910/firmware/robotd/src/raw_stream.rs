//! R17 read-only snapshots. The control thread publishes facts; one worker encodes them.
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;

use arc_swap::ArcSwapOption;
use duck_control::feetech_snapshot;
use duck_ipc_proto as proto;
use serde::Serialize;
use serde_json::{Value, json};
use tokio::io::AsyncWriteExt;
use tokio::sync::{Notify, broadcast};

use crate::{RobotState, communication_stats::CommunicationStats, home_start, raw_codec};

pub const SCHEMA: &str = "r17.raw.v1";
const BUFFER: usize = 4;

#[derive(Default)]
pub struct ModelCache {
    loaded: Option<Arc<Value>>,
    active_address: usize,
    active: Option<Arc<duck_control::policy::LoadedModel>>,
}
impl ModelCache {
    pub fn capture(&mut self, controller: Option<&crate::control::Controller>) {
        let loaded = controller.map(|c| c.loaded_models_shared());
        let current = controller.and_then(|c| c.active_model());
        let address = current.map_or(0, |v| v as *const _ as usize);
        if ptr(&loaded) != ptr(&self.loaded) || address != self.active_address {
            self.active = current.map(|v| Arc::new(v.clone()));
            self.active_address = address;
        }
        self.loaded = loaded;
    }
    pub fn loaded(&self) -> Option<Arc<Value>> {
        self.loaded.clone()
    }
    pub fn active(&self) -> Option<Arc<duck_control::policy::LoadedModel>> {
        self.active.clone()
    }
}
fn ptr<T>(value: &Option<Arc<T>>) -> usize {
    value.as_ref().map_or(0, |v| Arc::as_ptr(v) as usize)
}

#[derive(Serialize)]
pub struct TargetFilters {
    pub head_lowpass: f64,
    pub legs_lowpass: f64,
}
#[derive(Serialize)]
pub struct ActionScales {
    pub walk: f64,
    pub stand: f64,
    pub stand_test: f64,
    pub sitstand: f64,
    pub ground_pick: f64,
    pub roulade: f64,
}
#[derive(Clone, Copy, Serialize, PartialEq, Eq)]
pub struct Skills {
    pub getup: bool,
    pub pick: bool,
}

#[derive(Serialize)]
pub struct BusDynamic {
    pub device_communication: CommunicationStats,
    pub startup_pose_ready: bool,
    pub last_cycle_error: Option<String>,
    pub cycle: u64,
    pub fresh_sample: bool,
    pub all_joints_fresh: bool,
    pub partial_sample: bool,
    pub read_recovery: &'static str,
    pub homed: bool,
    #[serde(serialize_with = "serialize_option_arc")]
    pub home_start_guard: Option<Arc<home_start::Report>>,
    #[serde(serialize_with = "serialize_option_arc")]
    pub last_enable_refusal: Option<Arc<String>>,
    pub policy_enabled: bool,
    pub home_recovery: bool,
    pub walk_action_scale: f64,
    pub walking_action_scale: f64,
    pub hold_action_scale: f64,
    pub head_lowpass: f64,
    pub legs_lowpass: f64,
    pub action_scale: f64,
    pub voltage_scale_mult: f64,
    pub voltage_adapt: bool,
    pub nominal_voltage: f64,
    pub active_action_scale: Option<f64>,
    pub active_target_filters: Option<TargetFilters>,
    pub scale_use: String,
    pub model_action_scales: ActionScales,
}

fn serialize_option_arc<T: Serialize, S: serde::Serializer>(
    value: &Option<Arc<T>>,
    serializer: S,
) -> Result<S::Ok, S::Error> {
    value.as_deref().serialize(serializer)
}

pub struct Bus {
    pub port: Arc<str>,
    pub loaded_models: Option<Arc<Value>>,
    pub active_model: Option<Arc<duck_control::policy::LoadedModel>>,
    pub skills: Skills,
    pub native: feetech_snapshot::Snapshot,
    pub dynamic: BusDynamic,
}

#[derive(Serialize)]
struct DynamicBus<'a> {
    #[serde(flatten)]
    body: &'a BusDynamic,
    native: &'a feetech_snapshot::Dynamic,
}
impl Bus {
    fn dynamic(&self) -> DynamicBus<'_> {
        DynamicBus {
            body: &self.dynamic,
            native: &self.native.dynamic,
        }
    }
    /// Invoked by the IPC/reporting thread only. The metadata tree is never built on a tick.
    fn metadata(&self) -> Value {
        let mut native =
            serde_json::to_value(self.native.metadata.as_ref()).expect("native metadata");
        let mut hd = serde_json::to_value(&self.native.hd1910).expect("HD1910 metadata");
        let hd = hd.as_object_mut().unwrap();
        hd.remove("temporary_gains_applied");
        hd.remove("restore_pending");
        hd.insert("model_source".into(), json!("deployment_contract_disk"));
        hd.insert("skills".into(), serde_json::to_value(self.skills).unwrap());
        native["hd1910"] = Value::Object(std::mem::take(hd));
        json!({
            "build": crate::feetech_commissioning::BUILD,
            "mode":"motion", "port": self.port.as_ref(), "phase":"control",
            "joint_recovery":"per_joint_three_tick_coast_then_hold",
            "loaded_models": self.loaded_models.as_deref(), "active_model": self.active_model.as_deref(),
            "torque_off_pending":false, "stability_revision":"r16-startup.2", "native":native,
        })
    }
    pub fn report(&self) -> Value {
        let mut value = self.metadata();
        merge(
            &mut value,
            serde_json::to_value(self.dynamic()).expect("bus snapshot"),
        );
        value
    }
    fn key(&self) -> BusKey {
        BusKey {
            native: Arc::as_ptr(&self.native.metadata) as usize,
            registers: self.native.hd1910.registers_before_arm.as_ptr() as usize,
            loaded: ptr(&self.loaded_models),
            active: ptr(&self.active_model),
            skills: self.skills,
            parameters: self.native.hd1910.servo_parameters,
        }
    }
}

/// Objects inherit static members; arrays are entire samples, never merged by position.
fn merge(base: &mut Value, newer: Value) {
    match (base, newer) {
        (Value::Object(base), Value::Object(newer)) => {
            for (key, value) in newer {
                match base.get_mut(&key) {
                    Some(old) => merge(old, value),
                    None => {
                        base.insert(key, value);
                    }
                }
            }
        }
        (base, newer) => *base = newer,
    }
}

pub struct Snapshot {
    pub cycle: u64,
    pub state: Option<Arc<proto::RobotState>>,
    pub bus: Option<Bus>,
}
#[derive(Serialize)]
struct Dynamic<'a> {
    #[serde(skip_serializing_if = "Option::is_none")]
    state: Option<&'a proto::RobotState>,
    #[serde(skip_serializing_if = "Option::is_none")]
    bus: Option<DynamicBus<'a>>,
}

#[derive(PartialEq, Eq)]
struct BusKey {
    native: usize,
    registers: usize,
    loaded: usize,
    active: usize,
    skills: Skills,
    parameters: Option<duck_control::hd1910_test::Parameters>,
}
#[derive(PartialEq, Eq)]
struct MetaKey {
    bus: Option<BusKey>,
    calibration: usize,
    policies: usize,
    error: usize,
}

pub struct Packet {
    pub metadata: Arc<Vec<u8>>,
    pub bytes: Arc<Vec<u8>>,
}
pub struct Hub {
    pub latest: ArcSwapOption<Snapshot>,
    output: broadcast::Sender<Arc<Packet>>,
    started: AtomicBool,
    wake: Notify,
    joins: std::sync::atomic::AtomicU64,
    #[cfg(test)]
    encoded: std::sync::atomic::AtomicU64,
}
impl Default for Hub {
    fn default() -> Self {
        Self {
            latest: ArcSwapOption::empty(),
            output: broadcast::channel(BUFFER).0,
            started: AtomicBool::new(false),
            wake: Notify::new(),
            joins: std::sync::atomic::AtomicU64::new(0),
            #[cfg(test)]
            encoded: std::sync::atomic::AtomicU64::new(0),
        }
    }
}
impl Hub {
    pub fn subscribed(&self) -> bool {
        self.output.receiver_count() != 0
    }
    pub fn publish(&self, snapshot: Snapshot) {
        self.latest.store(Some(Arc::new(snapshot)));
        if self.subscribed() {
            self.wake.notify_one();
        }
    }
}

fn capabilities(state: &RobotState) -> proto::SubscribeResult {
    let policies = state.policies.load();
    proto::SubscribeResult {
        accepted: true,
        walk: policies.walk.clone(),
        stand: policies.stand.clone(),
        sitstand: policies.sitstand.clone(),
        ground_pick: policies.ground_pick.clone(),
        skills: policies.skills.clone(),
        unavailable: state.policy_error.load_full().map_or_else(
            || {
                policies
                    .walk
                    .is_none()
                    .then(|| "no policy configured; holding the startup pose".to_owned())
            },
            |error| Some(format!("policy would not load: {error}")),
        ),
    }
}

pub async fn serve(
    state: Arc<RobotState>,
    mut lines: tokio::io::Lines<tokio::io::BufReader<tokio::net::unix::OwnedReadHalf>>,
    mut writer: tokio::net::unix::OwnedWriteHalf,
    id: proto::Id,
) -> std::io::Result<()> {
    let mut receiver = state.raw.output.subscribe();
    state.raw.joins.fetch_add(1, Ordering::Relaxed);
    if !state.raw.started.swap(true, Ordering::AcqRel) {
        tokio::spawn(worker(state.clone()));
    }
    state.raw.wake.notify_one();
    crate::write_line(&mut writer, &proto::Response::ok(Some(id), &json!({
        "accepted":true, "schema":SCHEMA, "framing":"u32le", "api_version":proto::API_VERSION,
    }))).await?;
    // This connection is now exclusively a stream. EOF cancels even a blocked write.
    tokio::select! {
        read = lines.next_line() => { read?; Ok(()) }
        result = async {
            let mut last_metadata: Option<Arc<Vec<u8>>> = None;
            loop {
                match receiver.recv().await {
                    Ok(packet) => {
                        let replace_metadata = last_metadata.as_ref().is_none_or(|old| !Arc::ptr_eq(old, &packet.metadata));
                        tokio::time::timeout(Duration::from_secs(1), async {
                            if replace_metadata { writer.write_all(&packet.metadata).await?; }
                            writer.write_all(&packet.bytes).await
                        }).await.map_err(|_| std::io::Error::new(std::io::ErrorKind::TimedOut, "raw telemetry receiver is not draining"))??;
                        if replace_metadata { last_metadata = Some(packet.metadata.clone()); }
                    }
                    Err(broadcast::error::RecvError::Lagged(_)) => continue,
                    Err(broadcast::error::RecvError::Closed) => return Ok(()),
                }
            }
        } => result,
    }
}

async fn worker(state: Arc<RobotState>) {
    let mut tick = tokio::time::interval(Duration::from_millis(20));
    tick.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Skip);
    // A new connection waits for a newly completed control tick. Replaying the
    // last disconnected frame would give stale sensor facts a fresh receive time.
    let mut previous_cycle = state.raw.latest.load().as_ref().map(|s| s.cycle);
    let mut previous_fallback = (0usize, 0usize);
    let mut fallback_packet: Option<Arc<Packet>> = None;
    let mut _fallback_sources = None;
    let mut joins = 0;
    let mut previous_key = None;
    let mut _metadata_owners = None;
    let mut metadata = Arc::new(Vec::new());
    let mut last_slow = tokio::time::Instant::now() - Duration::from_secs(2);
    // Geometry and model definitions are immutable; serialize them only on metadata changes.
    let model = crate::mapping::model();
    let geometry = crate::telemetry_geometry::definition();
    loop {
        if state.shutdown.load(Ordering::Relaxed) {
            return;
        }
        if !state.raw.subscribed() {
            state.raw.wake.notified().await;
            previous_cycle = state.raw.latest.load().as_ref().map(|s| s.cycle);
            last_slow = tokio::time::Instant::now() - Duration::from_secs(2);
            continue;
        }
        tokio::select! { _ = tick.tick() => {}, _ = state.raw.wake.notified() => {} }
        if !state.raw.subscribed() {
            continue;
        }
        let current_joins = state.raw.joins.load(Ordering::Relaxed);
        let joined = current_joins != joins;
        joins = current_joins;
        let snapshot = state.raw.latest.load_full();
        let bus = snapshot.as_ref().and_then(|s| s.bus.as_ref());
        let calibration = state.bus_calibration.load_full();
        let policies = state.policies.load_full();
        let error = state.policy_error.load_full();
        let key = MetaKey {
            bus: bus.map(Bus::key),
            calibration: ptr(&calibration),
            policies: Arc::as_ptr(&policies) as usize,
            error: ptr(&error),
        };
        if previous_key.as_ref() != Some(&key) {
            let result = raw_codec::json_record(&json!({
                "schema":SCHEMA,
                "channels":{"state":{},"bus":bus.map(Bus::metadata).unwrap_or_else(|| json!({}))},
                "model": &model, "kinematics": &geometry,
                "calibration":calibration.as_deref(), "capabilities":capabilities(&state),
            }));
            match result {
                Ok(bytes) => {
                    metadata = Arc::new(bytes);
                    previous_key = Some(key);
                    // Keep pointer identities alive until their metadata is replaced.
                    _metadata_owners = Some((
                        snapshot.clone(),
                        calibration.clone(),
                        policies.clone(),
                        error.clone(),
                    ));
                }
                Err(error) => {
                    tracing::warn!(%error, "raw metadata encoding failed");
                    continue;
                }
            }
        }
        let bytes = if let Some(snapshot) = snapshot.as_ref() {
            if previous_cycle == Some(snapshot.cycle) {
                None
            } else {
                previous_cycle = Some(snapshot.cycle);
                Some(raw_codec::record(
                    2,
                    &Dynamic {
                        state: snapshot.state.as_deref(),
                        bus: snapshot.bus.as_ref().map(Bus::dynamic),
                    },
                ))
            }
        } else {
            let typed = state.bus_snapshot.load_full();
            let fallback = state.bus_status.load_full();
            let identity = (ptr(&typed), ptr(&fallback));
            if previous_fallback == identity {
                None
            } else {
                previous_fallback = identity;
                _fallback_sources = Some((typed.clone(), fallback.clone()));
                #[derive(Serialize)]
                struct Report<'a, T: Serialize> {
                    bus: &'a T,
                }
                typed
                    .as_ref()
                    .map(|bus| raw_codec::record(2, &Report { bus: bus.as_ref() }))
                    .or_else(|| {
                        fallback
                            .as_ref()
                            .map(|bus| raw_codec::record(2, &Report { bus: bus.as_ref() }))
                    })
            }
        };
        if let Some(bytes) = bytes {
            let packet = publish(&state.raw, metadata.clone(), bytes);
            if snapshot.is_none() {
                fallback_packet = packet;
            }
        } else if joined
            && snapshot.is_none()
            && let Some(packet) = fallback_packet.as_ref()
        {
            // A startup/configuration error can remain unchanged indefinitely.
            // Give a new viewer that current status, reusing its already encoded
            // bytes. Motion samples deliberately never use this replay path.
            let _ = state.raw.output.send(Arc::new(Packet {
                metadata: metadata.clone(),
                bytes: packet.bytes.clone(),
            }));
        }
        if last_slow.elapsed() >= Duration::from_secs(2) {
            last_slow = tokio::time::Instant::now();
            #[derive(Serialize)]
            struct Slow<'a> {
                health: proto::HealthResult,
                system: Value,
                capabilities: proto::SubscribeResult,
                #[serde(skip_serializing_if = "Option::is_none")]
                calibration: Option<&'a Value>,
            }
            let bytes = raw_codec::record(
                4,
                &Slow {
                    health: state.health(),
                    system: crate::telemetry_system::snapshot(),
                    capabilities: capabilities(&state),
                    calibration: calibration.as_deref(),
                },
            );
            let _ = publish(&state.raw, metadata.clone(), bytes);
        }
    }
}

fn publish(
    hub: &Hub,
    metadata: Arc<Vec<u8>>,
    bytes: Result<Vec<u8>, raw_codec::Error>,
) -> Option<Arc<Packet>> {
    match bytes {
        Ok(bytes) => {
            #[cfg(test)]
            hub.encoded.fetch_add(1, Ordering::Relaxed);
            let packet = Arc::new(Packet {
                metadata,
                bytes: Arc::new(bytes),
            });
            let _ = hub.output.send(packet.clone());
            Some(packet)
        }
        Err(error) => {
            tracing::warn!(%error, "raw snapshot encoding failed");
            None
        }
    }
}

#[cfg(test)]
pub(crate) mod tests {
    use super::*;
    use duck_control::{NUM_JOINTS, feetech, hd1910};
    use feetech_snapshot::{
        Dynamic as Native, HdState, Joint, JointMetadata, JointSamples, Metadata, Samples,
    };
    use tokio::io::{AsyncBufReadExt, AsyncReadExt, BufReader};

    pub(crate) fn fixture(cycle: u64) -> Snapshot {
        let metadata = Arc::new(Metadata {
            backend: "feetech_ft6",
            read_timing_revision: feetech::READ_TIMING_REVISION,
            motion_enabled: true,
            calibration_complete: true,
            imu_mount_verified: true,
            velocity_source: hd1910::VELOCITY_SOURCE,
            velocity_rad_s_per_count: Some(hd1910::SPEED_RAD_S_PER_COUNT),
            current_available: false,
            joints: proto::JOINT_NAMES
                .iter()
                .zip(duck_control::JOINT_IDS)
                .map(|(name, id)| JointMetadata {
                    name: (*name).into(),
                    id,
                    calibrated: true,
                })
                .collect(),
        });
        let samples = Samples {
            values: std::array::from_fn(|i| Joint {
                id: duck_control::JOINT_IDS[i],
                position_raw: -4096 + i as i32,
                position_wire_raw: 0x8000 | (4096 - i as u16),
                position_signed_raw: -4096 + i as i32,
                speed_raw: -12,
                load_raw: 3,
                current_raw: -7,
                volts: 8.2,
                temperature_c: 35,
                position_rad: Some(i as f64 / 100.0),
                velocity_rad_s: None,
                current_ma: None,
                feedback_fresh: true,
                sample_age_ms: 0,
                missing_total: if i == 0 { u64::MAX } else { 0 },
                consecutive_missing: 0,
                read_recovery: "fresh",
            }),
            len: NUM_JOINTS,
        };
        let hd1910 = hd1910::Diagnostics {
            profile: "hd1910-selftrained",
            goal_address: 42,
            goal_length: 6,
            goal_speed_raw: 0,
            acceleration_policy: "preserve_register_41_never_written",
            temporary_gains_applied: true,
            restore_pending: false,
            registers_before_arm: Arc::from([]),
            servo_parameters: None,
        };
        let native = feetech_snapshot::Snapshot {
            metadata: metadata.clone(),
            hd1910,
            dynamic: Native {
                torque_enabled: true,
                torque_state_confirmed: Some(true),
                gain_mode: "hd1910_bam_p_d20_mouth_p10_restore_on_relax",
                sample_age_ms: Some(0),
                imu_ready: true,
                imu_sequence: Some(123),
                imu_age_ms: Some(2),
                imu_age_upper_bound_ms: Some(3),
                imu_status: Some(0),
                command_clamps_total: 1,
                partial_samples_total: 2,
                all_joints_fresh: true,
                stale_joint_ids: Samples::default(),
                held_joint_ids: Samples::default(),
                joints: JointSamples { samples, metadata },
                sync: feetech::SyncTrace::default(),
                telemetry: feetech::TelemetryTotals {
                    total_reads: cycle,
                    last_error: Some("飞特 \"回包\"\\状态".into()),
                    ..Default::default()
                },
                hd1910: HdState {
                    temporary_gains_applied: true,
                    restore_pending: false,
                },
            },
        };
        Snapshot {
            cycle,
            state: Some(Arc::new(proto::RobotState {
                t: 1.5,
                movement: proto::MoveState {
                    requested: [0.0; 3],
                    applied: [0.0; 3],
                    limited_by: Vec::new(),
                },
                head: [0.0; 4],
                policy: "held".into(),
                safety: proto::SafetyState {
                    fallen: false,
                    limp: false,
                    gravity: [0.0, 0.0, -1.0],
                    gain: None,
                },
                control_loop: proto::LoopState {
                    hz: 50.0,
                    missed: 0,
                },
                joints: (0..NUM_JOINTS).map(|i| i as f64 / 100.0).collect(),
                targets: vec![0.0; NUM_JOINTS],
                velocities: vec![0.1; NUM_JOINTS],
                currents_ma: Vec::new(),
                odom: Default::default(),
                theremin: None,
                chorale: None,
                t_ns: u64::MAX,
                imu: Some(proto::ImuState {
                    gyro: [0.1, -0.0, 0.3],
                    quat: [1.0, 0.0, 0.0, 0.0],
                }),
                frames: None,
                skeleton: Vec::new(),
            })),
            bus: Some(Bus {
                port: Arc::from("/dev/ttyS1"),
                loaded_models: Some(Arc::new(
                    json!({"walk":{"path":"/model.onnx","sha256":"test"},"stand":null}),
                )),
                active_model: None,
                skills: Skills {
                    getup: false,
                    pick: false,
                },
                native,
                dynamic: BusDynamic {
                    device_communication: CommunicationStats::new(
                        duck_control::JOINT_IDS.into_iter().chain([200]),
                    ),
                    startup_pose_ready: true,
                    last_cycle_error: None,
                    cycle,
                    fresh_sample: true,
                    all_joints_fresh: true,
                    partial_sample: false,
                    read_recovery: "fresh",
                    homed: true,
                    home_start_guard: None,
                    last_enable_refusal: None,
                    policy_enabled: false,
                    home_recovery: false,
                    walk_action_scale: 0.25,
                    walking_action_scale: 0.25,
                    hold_action_scale: 0.25,
                    head_lowpass: 1.0,
                    legs_lowpass: 1.0,
                    action_scale: 0.25,
                    voltage_scale_mult: 1.0,
                    voltage_adapt: false,
                    nominal_voltage: 8.0,
                    active_action_scale: None,
                    active_target_filters: None,
                    scale_use: "held".into(),
                    model_action_scales: ActionScales {
                        walk: 0.25,
                        stand: 0.1,
                        stand_test: 0.25,
                        sitstand: 1.0,
                        ground_pick: 0.2,
                        roulade: 0.25,
                    },
                },
            }),
        }
    }

    async fn data(receiver: &mut broadcast::Receiver<Arc<Packet>>) -> Arc<Packet> {
        tokio::time::timeout(Duration::from_secs(2), async {
            loop {
                let packet = receiver.recv().await.unwrap();
                if packet.bytes[4] == 2 {
                    return packet;
                }
            }
        })
        .await
        .unwrap()
    }

    #[tokio::test]
    async fn subscribers_share_one_encoding_and_disconnect_stops_encoding() {
        let mut params = crate::Params::default();
        params.policy.enabled = false;
        let state = Arc::new(RobotState::new(
            &params,
            std::path::Path::new("/test/robotd.toml"),
            false,
            false,
        ));
        let mut first = state.raw.output.subscribe();
        let mut second = state.raw.output.subscribe();
        state.raw.publish(fixture(1));
        let task = tokio::spawn(worker(state.clone()));
        tokio::task::yield_now().await;
        state.raw.publish(fixture(2));
        let a = data(&mut first).await;
        let b = data(&mut second).await;
        assert!(
            Arc::ptr_eq(&a, &b),
            "both sockets reuse the exact encoded packet"
        );
        assert_eq!(
            state.state_tx.receiver_count(),
            0,
            "raw does not request official geometry"
        );
        let metadata: Value = serde_json::from_slice(&a.metadata[5..]).unwrap();
        assert_eq!(metadata["schema"], SCHEMA);
        assert_eq!(
            metadata["channels"]["bus"]["native"]["hd1910"]["model_source"],
            "deployment_contract_disk"
        );
        if let Ok(path) = std::env::var("R17_RAW_FIXTURE_PATH") {
            let mut bytes = a.metadata.as_ref().clone();
            bytes.extend_from_slice(&a.bytes);
            std::fs::write(&path, bytes).unwrap();
            let snapshot = state.raw.latest.load_full().unwrap();
            let expected = json!({ "state":snapshot.state.as_deref(), "bus":snapshot.bus.as_ref().unwrap().report() });
            std::fs::write(
                format!("{path}.json"),
                serde_json::to_vec(&expected).unwrap(),
            )
            .unwrap();
        }
        drop(first);
        drop(second);
        tokio::time::sleep(Duration::from_millis(40)).await;
        let encoded = state.raw.encoded.load(Ordering::Relaxed);
        state.raw.publish(fixture(3));
        tokio::time::sleep(Duration::from_millis(60)).await;
        assert_eq!(
            state.raw.encoded.load(Ordering::Relaxed),
            encoded,
            "offline stores facts but does no encoding"
        );
        let report = state
            .raw
            .latest
            .load_full()
            .unwrap()
            .bus
            .as_ref()
            .unwrap()
            .report();
        assert_eq!(report["cycle"], 3);
        assert_eq!(report["native"]["joints"][0]["name"], proto::JOINT_NAMES[0]);
        assert_eq!(report["native"]["joints"][0]["missing_total"], u64::MAX);
        task.abort();
    }

    #[tokio::test]
    async fn lazy_bus_rpc_preserves_snapshot_fields_without_streaming() {
        let state = Arc::new(RobotState::new(
            &crate::Params::default(),
            std::path::Path::new("/test/robotd.toml"),
            false,
            false,
        ));
        state.raw.publish(fixture(42));
        let expected = state
            .raw
            .latest
            .load_full()
            .unwrap()
            .bus
            .as_ref()
            .unwrap()
            .report();
        let line = crate::tests::ipc_response(
            state.clone(),
            json!({"jsonrpc":"2.0","id":"查询","method":"robot.busStatus"}),
        )
        .await;
        let reply: Value = serde_json::from_str(&line).unwrap();
        assert_eq!(reply["result"], expected);
        assert_eq!(reply["id"], "查询");
        assert!(!state.raw.subscribed());
        assert_eq!(state.raw.encoded.load(Ordering::Relaxed), 0);
        // A legacy startup report is retired by a live snapshot; commissioning is
        // still checked first by the existing typed branch in handle().
        state
            .bus_status
            .store(Some(Arc::new(json!({"phase":"configuring_uart"}))));
        let line = crate::tests::ipc_response(
            state,
            json!({"jsonrpc":"2.0","id":2,"method":"robot.busStatus"}),
        )
        .await;
        assert_eq!(
            serde_json::from_str::<Value>(&line).unwrap()["result"],
            expected
        );
    }

    async fn wire_record(reader: &mut BufReader<tokio::net::UnixStream>) -> Vec<u8> {
        let mut size = [0; 4];
        reader.read_exact(&mut size).await.unwrap();
        let len = u32::from_le_bytes(size) as usize;
        assert!(len > 0 && len <= raw_codec::MAX_RECORD);
        let mut bytes = vec![0; len];
        reader.read_exact(&mut bytes).await.unwrap();
        bytes
    }

    #[tokio::test]
    async fn dedicated_connection_rejects_unknown_params_and_waits_for_new_sample() {
        let state = Arc::new(RobotState::new(
            &crate::Params::default(),
            std::path::Path::new("/test/robotd.toml"),
            false,
            false,
        ));
        state.raw.publish(fixture(11));
        let (client, server) = tokio::net::UnixStream::pair().unwrap();
        let task = tokio::spawn(crate::handle(
            state.clone(),
            Arc::new(crate::Intents::new()),
            server,
        ));
        let mut client = BufReader::new(client);
        client.get_mut().write_all(b"{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"robot.rawSubscribe\",\"params\":{\"hz\":50}}\n").await.unwrap();
        let mut ack = String::new();
        client.read_line(&mut ack).await.unwrap();
        assert!(
            serde_json::from_str::<Value>(&ack)
                .unwrap()
                .get("error")
                .is_some()
        );
        assert!(!state.raw.subscribed());
        client
            .get_mut()
            .write_all(
                b"{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"robot.rawSubscribe\",\"params\":{}}\n",
            )
            .await
            .unwrap();
        ack.clear();
        client.read_line(&mut ack).await.unwrap();
        assert_eq!(
            serde_json::from_str::<Value>(&ack).unwrap()["result"]["api_version"],
            proto::API_VERSION
        );
        assert_eq!(wire_record(&mut client).await[0], 1);
        assert_eq!(wire_record(&mut client).await[0], 4);
        assert!(
            tokio::time::timeout(Duration::from_millis(60), wire_record(&mut client))
                .await
                .is_err(),
            "old disconnected state must not be emitted as a newly received sample"
        );
        state.raw.publish(fixture(12));
        loop {
            if wire_record(&mut client).await[0] == 2 {
                break;
            }
        }
        drop(client);
        tokio::time::timeout(Duration::from_secs(1), task)
            .await
            .unwrap()
            .unwrap()
            .unwrap();
        assert!(!state.raw.subscribed());
        state.shutdown.store(true, Ordering::Relaxed);
        state.raw.wake.notify_one();
    }

    #[tokio::test]
    async fn stalled_writer_times_out_without_retaining_a_subscriber() {
        let state = Arc::new(RobotState::new(
            &crate::Params::default(),
            std::path::Path::new("/test/robotd.toml"),
            false,
            false,
        ));
        let (client, server) = tokio::net::UnixStream::pair().unwrap();
        let (read, write) = server.into_split();
        let task = tokio::spawn(serve(
            state.clone(),
            BufReader::new(read).lines(),
            write,
            proto::Id::Number(1),
        ));
        let mut client = BufReader::new(client);
        let mut ack = String::new();
        client.read_line(&mut ack).await.unwrap();
        let metadata = Arc::new(raw_codec::json_record(&json!({"schema":SCHEMA})).unwrap());
        // A socket whose reader has stopped cannot absorb a two-megabyte packet.
        let _ = publish(
            &state.raw,
            metadata,
            raw_codec::record(2, &"x".repeat(2 * 1024 * 1024)),
        );
        let error = tokio::time::timeout(Duration::from_secs(2), task)
            .await
            .unwrap()
            .unwrap()
            .unwrap_err();
        assert_eq!(error.kind(), std::io::ErrorKind::TimedOut);
        assert!(!state.raw.subscribed());
        state.shutdown.store(true, Ordering::Relaxed);
        state.raw.wake.notify_one();
    }

    #[tokio::test(start_paused = true)]
    async fn offline_control_keeps_acquisition_counts_without_full_reports_or_geometry() {
        use duck_control::io::{Result as IoResult, RobotIo};
        struct Io {
            inner: duck_control::FakeIo,
            reads: u64,
            trace: feetech::SyncTrace,
        }
        impl RobotIo for Io {
            fn read(&mut self) -> IoResult<duck_control::Sensors> {
                self.reads += 1;
                self.inner.read()
            }
            fn write(&mut self, goal: &duck_control::JointTargets) -> IoResult<()> {
                self.inner.write(goal)
            }
            fn set_gain(&mut self, gain: u16) -> IoResult<()> {
                self.inner.set_gain(gain)
            }
            fn set_torque(&mut self, on: bool) -> IoResult<()> {
                self.inner.set_torque(on)
            }
            fn reboot(&mut self, id: u8) -> IoResult<()> {
                self.inner.reboot(id)
            }
            fn slow_sensors(&mut self) -> IoResult<duck_control::SlowSensors> {
                self.inner.slow_sensors()
            }
            fn feetech_control_status(&self) -> Option<feetech::FeetechControlStatus> {
                Some(feetech::FeetechControlStatus {
                    all_joints_fresh: true,
                    imu_mount_verified: true,
                    imu_ready: true,
                    torque_state_confirmed: Some(false),
                    joints_held: false,
                })
            }
            fn feetech_diagnostics(&self) -> Option<feetech::FeetechDiagnostics> {
                panic!("full diagnostic report on the control thread")
            }
            fn feetech_snapshot(&self) -> Option<feetech_snapshot::Snapshot> {
                Some(fixture(self.reads).bus.unwrap().native)
            }
            fn feetech_sync_trace(&self) -> Option<&feetech::SyncTrace> {
                Some(&self.trace)
            }
        }
        let mut params = crate::Params::default();
        params.policy.enabled = false;
        params.audio.enabled = false;
        params.bus.protocol = crate::params::BusProtocol::Feetech;
        let state = Arc::new(RobotState::new(
            &params,
            std::path::Path::new("/test/robotd.toml"),
            false,
            false,
        ));
        let task = tokio::spawn(crate::control_loop(
            Io {
                inner: duck_control::FakeIo::at(duck_control::DEFAULT_POSITION),
                reads: 0,
                trace: feetech::SyncTrace {
                    address: 56,
                    length: 15,
                    request_sent: true,
                    ..Default::default()
                },
            },
            state.clone(),
            Arc::new(crate::Intents::new()),
            params,
            "/test/robotd.toml".into(),
            Duration::from_millis(20),
            Arc::new(|| {}),
        ));
        while state.ticks.load(Ordering::Relaxed) < 6 {
            tokio::time::sleep(Duration::from_millis(20)).await;
        }
        state.shutdown.store(true, Ordering::Relaxed);
        task.await.unwrap();
        let snapshot = state.raw.latest.load_full().unwrap();
        let bus = snapshot.bus.as_ref().unwrap();
        assert_eq!(
            bus.dynamic.device_communication.total_reads,
            state.ticks.load(Ordering::Relaxed)
        );
        assert_eq!(
            bus.native.dynamic.telemetry.total_reads,
            state.ticks.load(Ordering::Relaxed)
        );
        assert!(
            snapshot.state.is_none(),
            "no state/geometry assembled without either subscription"
        );
        assert!(!state.raw.started.load(Ordering::Relaxed));
        assert_eq!(state.raw.encoded.load(Ordering::Relaxed), 0);
        assert!(
            state.bus_status.load().is_none(),
            "no full motion JSON cache is manufactured"
        );
    }

    #[tokio::test]
    async fn new_viewer_gets_unchanged_startup_failure_without_reencoding() {
        let state = Arc::new(RobotState::new(
            &crate::Params::default(),
            std::path::Path::new("/test/robotd.toml"),
            false,
            false,
        ));
        state.bus_status.store(Some(Arc::new(
            json!({"phase":"configuration_error", "error":"UART unavailable"}),
        )));
        let mut first = state.raw.output.subscribe();
        state.raw.joins.fetch_add(1, Ordering::Relaxed);
        let task = tokio::spawn(worker(state.clone()));
        let initial = data(&mut first).await;
        // The first iteration also emits slow channels; let it finish before
        // measuring that a second viewer causes no second encoding.
        tokio::task::yield_now().await;
        let encoded = state.raw.encoded.load(Ordering::Relaxed);
        let mut second = state.raw.output.subscribe();
        state.raw.joins.fetch_add(1, Ordering::Relaxed);
        state.raw.wake.notify_one();
        let joined = data(&mut second).await;
        assert!(Arc::ptr_eq(&initial.bytes, &joined.bytes));
        assert_eq!(state.raw.encoded.load(Ordering::Relaxed), encoded);
        task.abort();
    }
}

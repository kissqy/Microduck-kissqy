//! Read-only, owned facts for a reporter on another thread. No UART owner and no JSON tree.
use std::sync::Arc;

use serde::{Serialize, Serializer};

use crate::NUM_JOINTS;
use crate::feetech::{SyncTrace, TelemetryTotals};

#[derive(Debug, Serialize)]
pub struct JointMetadata {
    pub name: String,
    pub id: u8,
    pub calibrated: bool,
}

#[derive(Debug, Serialize)]
pub struct Metadata {
    pub backend: &'static str,
    pub read_timing_revision: &'static str,
    pub motion_enabled: bool,
    pub calibration_complete: bool,
    pub imu_mount_verified: bool,
    pub velocity_source: &'static str,
    pub velocity_rad_s_per_count: Option<f64>,
    pub current_available: bool,
    pub joints: Vec<JointMetadata>,
}

#[derive(Debug, Clone, Copy, Default, Serialize)]
pub struct Joint {
    pub id: u8,
    pub position_raw: i32,
    pub position_wire_raw: u16,
    pub position_signed_raw: i32,
    pub speed_raw: i32,
    pub load_raw: i32,
    pub current_raw: i32,
    pub volts: f64,
    pub temperature_c: u8,
    pub position_rad: Option<f64>,
    pub velocity_rad_s: Option<f64>,
    pub current_ma: Option<f64>,
    pub feedback_fresh: bool,
    pub sample_age_ms: u64,
    pub missing_total: u64,
    pub consecutive_missing: u32,
    pub read_recovery: &'static str,
}

/// Fixed storage, including the pre-first-sample empty case. The wire is still an array.
#[derive(Debug, Clone)]
pub struct Samples<T: Default + Copy> {
    pub values: [T; NUM_JOINTS],
    pub len: usize,
}

impl<T: Default + Copy> Default for Samples<T> {
    fn default() -> Self {
        Self {
            values: [T::default(); NUM_JOINTS],
            len: 0,
        }
    }
}

impl<T: Default + Copy + Serialize> Serialize for Samples<T> {
    fn serialize<S: Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        self.values[..self.len].serialize(serializer)
    }
}

#[derive(Debug, Clone)]
pub struct JointSamples {
    pub samples: Samples<Joint>,
    pub metadata: Arc<Metadata>,
}

impl Serialize for JointSamples {
    fn serialize<S: Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        use serde::ser::SerializeSeq;
        #[derive(Serialize)]
        struct NamedJoint<'a> {
            name: &'a str,
            calibrated: bool,
            #[serde(flatten)]
            data: &'a Joint,
        }
        let mut sequence = serializer.serialize_seq(Some(self.samples.len))?;
        for (data, metadata) in self.samples.values[..self.samples.len]
            .iter()
            .zip(&self.metadata.joints)
        {
            sequence.serialize_element(&NamedJoint {
                name: &metadata.name,
                calibrated: metadata.calibrated,
                data,
            })?;
        }
        sequence.end()
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct HdState {
    pub temporary_gains_applied: bool,
    pub restore_pending: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct Dynamic {
    pub torque_enabled: bool,
    pub torque_state_confirmed: Option<bool>,
    pub gain_mode: &'static str,
    pub sample_age_ms: Option<u64>,
    pub imu_ready: bool,
    pub imu_sequence: Option<u32>,
    pub imu_age_ms: Option<u16>,
    pub imu_age_upper_bound_ms: Option<u16>,
    pub imu_status: Option<u8>,
    pub command_clamps_total: u64,
    pub partial_samples_total: u64,
    pub all_joints_fresh: bool,
    pub stale_joint_ids: Samples<u8>,
    pub held_joint_ids: Samples<u8>,
    pub joints: JointSamples,
    pub sync: SyncTrace,
    pub telemetry: TelemetryTotals,
    pub hd1910: HdState,
}

#[derive(Debug, Clone)]
pub struct Snapshot {
    pub metadata: Arc<Metadata>,
    pub dynamic: Dynamic,
    // This existing immutable register cache is replaced only by a real inspection.
    pub hd1910: crate::hd1910::Diagnostics,
}

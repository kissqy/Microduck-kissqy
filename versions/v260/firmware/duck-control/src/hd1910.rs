//! HD1910 position payload, model-contract P, RAM D=0 and torque limit=1000.
//! Local joint calibration and FT6/SFLP body frame remain authoritative.
use crate::feetech::{Bus, Calibration};
use crate::io::{IoError, Result, Sensors};
use crate::model::NUM_JOINTS;
use serde::{Serialize, Serializer};
use std::sync::Arc;
use std::time::Instant;

/// HD1910/HLS present-speed contract used by HD1910 runtime a6dc9f98:
/// duck_config.h SERVO_SPEED_UNIT and scs_bus.h applyMotorFb.
/// Register 58..59 is signed magnitude (bit 15), 50 encoder steps/s per count.
/// The wire decoder removes bit 15; the installed joint direction is applied once
/// by FeetechIo. This is a feedback scale, not the goal-speed register's unit.
pub const SPEED_RAD_S_PER_COUNT: f64 = 50.0 * std::f64::consts::TAU / 4096.0;
pub const VELOCITY_SOURCE: &str = "hd1910_native_register_50_steps_per_second";

fn error(s: impl Into<String>) -> IoError {
    IoError::Bus(s.into())
}

#[derive(Clone, Debug, Serialize)]
pub struct RegisterSnapshot {
    pub id: u8,
    pub name: String,
    pub mode: u8,
    pub eeprom_pdi: [u8; 3],
    pub temporary_pdi: [u8; 3],
    pub acceleration_raw: u8,
    pub goal_current_raw: u16,
    pub goal_speed_raw: u16,
}

#[derive(Clone, Debug, Serialize)]
pub struct Diagnostics {
    pub profile: &'static str,
    pub goal_address: u8,
    pub goal_length: u8,
    pub goal_speed_raw: u16,
    pub acceleration_policy: &'static str,
    pub temporary_gains_applied: bool,
    pub restore_pending: bool,
    #[serde(serialize_with = "serialize_register_snapshots")]
    pub registers_before_arm: Arc<[RegisterSnapshot]>,
}

fn serialize_register_snapshots<S: Serializer>(
    snapshots: &[RegisterSnapshot],
    serializer: S,
) -> std::result::Result<S::Ok, S::Error> {
    snapshots.serialize(serializer)
}

#[derive(Default)]
pub struct State {
    // An inspection replaces the whole snapshot. Diagnostics can share it until
    // the next inspection without copying 15 joint names every control tick.
    snapshots: Arc<[RegisterSnapshot]>,
    restore: Option<Vec<(u8, Vec<u8>)>>,
    applied: bool,
    velocity_delay: Option<(Instant, [f64; NUM_JOINTS])>,
}

impl State {
    pub fn inspect(&mut self, bus: &mut Bus, calibration: &Calibration) -> Result<()> {
        let ids: Vec<_> = calibration.joints.iter().map(|j| j.id).collect();
        let saved = bus.sync_read(21, 3, &ids)?;
        let modes = bus.sync_read(33, 1, &ids)?;
        let temporary = bus.sync_read(50, 3, &ids)?;
        let motion = bus.sync_read(41, 7, &ids)?;
        let mut snapshots = Vec::with_capacity(ids.len());
        for joint in &calibration.joints {
            let id = joint.id;
            let m = &motion[&id];
            snapshots.push(RegisterSnapshot {
                id,
                name: joint.name.clone(),
                mode: modes[&id][0],
                eeprom_pdi: saved[&id]
                    .as_slice()
                    .try_into()
                    .map_err(|_| error("EEPROM snapshot length"))?,
                temporary_pdi: temporary[&id]
                    .as_slice()
                    .try_into()
                    .map_err(|_| error("temporary gain snapshot length"))?,
                acceleration_raw: m[0],
                goal_current_raw: u16::from_le_bytes([m[3], m[4]]),
                goal_speed_raw: u16::from_le_bytes([m[5], m[6]]),
            });
        }
        self.snapshots = snapshots.into();
        Ok(())
    }

    pub fn arm(&mut self, bus: &mut Bus, calibration: &Calibration) -> Result<()> {
        if self.applied {
            return Ok(());
        }
        if self.restore.is_some() {
            return Err(error(
                "HD1910 temporary gain restoration pending; relax first",
            ));
        }
        let ids: Vec<_> = calibration.joints.iter().map(|j| j.id).collect();
        let off = bus.verify_torque(&ids, false).is_ok();
        if !off {
            bus.verify_torque(&ids, true)?;
        }
        self.inspect(bus, calibration)?;
        let desired: Vec<_> = self
            .snapshots
            .iter()
            .map(|s| (s.id, vec![crate::deployment::firmware_p()]))
            .collect();
        if !off {
            verify_gains(bus, &desired)?;
            write_fixed_settings(bus, &ids)?;
            // Existing gains are already correct; do not interrupt torque to
            // reapply them, and do not invent restoration data from another run.
            self.applied = true;
            tracing::warn!(
                "HD1910 existing P verified; RAM D=0 and limit=1000 written; torque preserved"
            );
            return Ok(());
        }
        let restore: Vec<_> = self
            .snapshots
            .iter()
            .map(|s| (s.id, vec![s.temporary_pdi[0]]))
            .collect();
        // Retain the rollback data BEFORE the first write. A partial write or failed
        // readback cannot discard the information required by the relax path.
        self.restore = Some(restore);
        bus.sync_write(50, &desired)?;
        verify_gains(bus, &desired)?;
        write_fixed_settings(bus, &ids)?;
        self.applied = true;
        tracing::warn!(
            "HD1910 temporary P confirmed from model contract; RAM D=0 and limit=1000 written; acceleration preserved"
        );
        Ok(())
    }

    pub fn disarm(&mut self, bus: &mut Bus) -> Result<()> {
        self.applied = false;
        self.velocity_delay = None;
        if let Some(rows) = &self.restore {
            bus.sync_write(50, rows)?;
            verify_gains(bus, rows)?;
            self.restore = None;
        }
        Ok(())
    }

    pub fn delay_velocity(
        &mut self,
        now: Instant,
        sensors: &mut Sensors,
        fresh: &[bool; NUM_JOINTS],
    ) {
        let current = sensors.velocities;
        if let Some((previous, velocity)) = self.velocity_delay {
            if now.duration_since(previous).as_secs_f64() <= 0.1 {
                for i in 0..NUM_JOINTS {
                    if fresh[i] {
                        sensors.velocities[i] = velocity[i];
                    }
                }
            }
        }
        self.velocity_delay = Some((now, current));
    }

    pub fn diagnostics(&self) -> Diagnostics {
        Diagnostics {
            profile: "hd1910-selftrained",
            goal_address: 42,
            goal_length: 6,
            goal_speed_raw: 0,
            acceleration_policy: "preserve_register_41_never_written",
            temporary_gains_applied: self.applied,
            restore_pending: self.restore.is_some(),
            registers_before_arm: self.snapshots.clone(),
        }
    }
}

fn verify_gains(bus: &mut Bus, rows: &[(u8, Vec<u8>)]) -> Result<()> {
    let ids: Vec<_> = rows.iter().map(|(id, _)| *id).collect();
    let values = bus.sync_read(50, 1, &ids)?;
    for (id, expected) in rows {
        if values.get(id) != Some(expected) {
            return Err(error(format!(
                "ID {id}: temporary P readback mismatch; torque-on refused"
            )));
        }
    }
    Ok(())
}

fn write_fixed_settings(bus: &mut Bus, ids: &[u8]) -> Result<()> {
    // Separate register widths preserve model P at 50, I at 52 and speed at 46.
    // Use the existing broadcast writer, without adding a read transaction.
    let d = ids.iter().map(|id| (*id, vec![0])).collect::<Vec<_>>();
    let limit = ids
        .iter()
        .map(|id| (*id, 1000u16.to_le_bytes().to_vec()))
        .collect::<Vec<_>>();
    bus.sync_write(51, &d)?;
    bus.sync_write(48, &limit)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::Duration;

    #[test]
    fn native_velocity_uses_one_sample_delay_and_resets_after_long_gap() {
        let mut state = State::default();
        let now = Instant::now();
        let fresh = [true; NUM_JOINTS];
        let mut sensors = Sensors {
            velocities: [1.; NUM_JOINTS],
            ..Sensors::default()
        };
        state.delay_velocity(now, &mut sensors, &fresh);
        assert_eq!(sensors.velocities, [1.; NUM_JOINTS]);
        // Training randomizes zero/one-frame observation delay. Use one prior speed
        // sample on hardware; no legacy exponential smoothing is added.
        sensors.velocities.fill(3.);
        state.delay_velocity(now + Duration::from_millis(20), &mut sensors, &fresh);
        assert_eq!(sensors.velocities, [1.; NUM_JOINTS]);
        sensors.velocities.fill(-2.);
        state.delay_velocity(now + Duration::from_millis(30), &mut sensors, &fresh);
        assert_eq!(sensors.velocities, [3.; NUM_JOINTS]);
        sensors.velocities.fill(5.);
        state.delay_velocity(now + Duration::from_millis(131), &mut sensors, &fresh);
        assert_eq!(sensors.velocities, [5.; NUM_JOINTS]);
    }

    #[test]
    fn missing_speed_is_not_refiltered_and_fresh_speed_resumes_independently() {
        let mut state = State::default();
        let now = Instant::now();
        let mut fresh = [true; NUM_JOINTS];
        let mut sensors = Sensors {
            velocities: [1.; NUM_JOINTS],
            ..Sensors::default()
        };
        state.delay_velocity(now, &mut sensors, &fresh);
        sensors.velocities.fill(3.);
        sensors.velocities[7] = 0.; // expired joint is held by the existing R3 path
        fresh[7] = false;
        state.delay_velocity(now + Duration::from_millis(20), &mut sensors, &fresh);
        assert_eq!(sensors.velocities[7], 0.);
        assert_eq!(sensors.velocities[0], 1.);
        sensors.velocities.fill(3.);
        fresh[7] = true;
        state.delay_velocity(now + Duration::from_millis(40), &mut sensors, &fresh);
        assert_eq!(sensors.velocities[7], 0.);
        assert_eq!(sensors.velocities[0], 3.);
    }
}

//! The head ToF sensor: an 8×8 matrix of distances, once per scan.
//!
//! A VL53L5CX or VL53L8CX on the HAT's I²C bus — the same `i2c3` bus the audio
//! codec sits on — looking where the head looks. This crate is the driver and the
//! frame shape; `tofd` (`src/main.rs`) is the daemon that owns the sensor and
//! publishes frames on a socket.
//!
//! **Both generations, decided at runtime.** The two are interchangeable on the
//! board and differ only in firmware and a driver prefix, so which one is fitted
//! is not a build-time choice: an ID read picks the driver before any firmware is
//! uploaded ([`Generation`]). Ducks in the field have both.
//!
//! ## Why the C is vendored
//!
//! Each of ST's Ultra Lite Drivers is 40 KB of register sequences plus a 550 KB
//! firmware blob that is uploaded into the sensor on every start. Reimplementing
//! that in Rust would be transcribing a binary blob and a state machine nobody
//! has documented outside the driver; depending on a third-party crate would put
//! a sensor this robot needs behind someone else's maintenance. So both ULDs are
//! vendored verbatim (BSD-3-Clause, `vendor/LICENSE.txt`), the Linux i2c-dev
//! platform hooks come from `microduck_runtime` where they were measured — one
//! implementation, compiled once per generation — and a flat shim keeps every
//! struct on the C side of the boundary. `build.rs` compiles them and explains
//! the one trick involved; there is no system library and no Python. The
//! prototype reached the older sensor through a pip package and a `.so` loaded by
//! ctypes; nothing here needs either.
//!
//! Which makes the driver **Linux-only**, and deliberately visibly so: on any
//! other target `build.rs` compiles none of the C and [`Sensor`] is uninhabited,
//! so `open` refuses rather than a build failing. `tofd --fake` is how this daemon
//! runs off a board, and it is unaffected — as is `cargo test --workspace`, which
//! is the point.
//!
//! ## What a frame is, and is not
//!
//! Raw zone distances and ST's per-zone status, in the sensor's own frame. There
//! is **no reprojection**: turning zones into directions in the robot's frame
//! needs the head's forward kinematics, which this daemon does not have and does
//! not fake. Consumers that want geometry (mapping, obstacle avoidance) will
//! combine `tof.frame` with joint state when the kinematics arrive; consumers
//! that want to *look* at the sensor — `robotctl monitor` — need none of it.

pub mod sensor;

pub use sensor::{Generation, Sensor};

/// The sensor's resolution. Pinned: 8×8 is what `start` configures and what the
/// wire format carries.
pub const ROWS: usize = 8;
pub const COLS: usize = 8;
pub const ZONES: usize = ROWS * COLS;

/// One scan, as the driver produces it.
///
/// `distance_mm` and `status` are parallel, row-major, `ZONES` long. A distance
/// is only meaningful where the status says so — see [`Zone`].
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Frame {
    pub rows: u8,
    pub cols: u8,
    pub distance_mm: Vec<i16>,
    pub status: Vec<u8>,
}

/// What one zone of a frame actually says.
///
/// ST's status byte is the difference between "nothing is there" and "I could not
/// tell", and collapsing them loses the distinction a map most needs: empty space
/// is information, an unusable measurement is not.
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum Zone {
    /// A measurement, in metres. Status 5 (valid) or 9 (valid, large pulse).
    Range(f32),
    /// Status 255: the sensor looked and found nothing in range. Empty space.
    NoTarget,
    /// Any other status: the measurement failed. Says nothing about what is out
    /// there — carries the raw code, because the codes mean specific things to
    /// anyone reading ST's table.
    Unusable(u8),
}

/// Status codes ST documents as a usable range: valid, and valid with a large
/// pulse (~50% confidence, which the sensor still stands behind).
pub const STATUS_VALID: [u8; 2] = [5, 9];
/// Status code for "measured, nothing there".
pub const STATUS_NO_TARGET: u8 = 255;

impl Frame {
    /// The zone at `index`, interpreted.
    pub fn zone(&self, index: usize) -> Zone {
        let status = self.status.get(index).copied().unwrap_or(STATUS_NO_TARGET);
        let distance = self.distance_mm.get(index).copied().unwrap_or(0);
        if STATUS_VALID.contains(&status) {
            // Negative distances come back from the sensor occasionally on a
            // failed convergence; they are not a range whatever the status says.
            if distance > 0 {
                return Zone::Range(f32::from(distance) / 1000.0);
            }
            return Zone::Unusable(status);
        }
        if status == STATUS_NO_TARGET {
            return Zone::NoTarget;
        }
        Zone::Unusable(status)
    }

    /// Every zone, row-major, interpreted.
    pub fn zones(&self) -> impl Iterator<Item = Zone> + '_ {
        (0..self.distance_mm.len()).map(|i| self.zone(i))
    }

    /// How many zones carry a usable range. The one number that says whether the
    /// sensor is seeing anything at all.
    pub fn valid_count(&self) -> usize {
        self.zones().filter(|z| matches!(z, Zone::Range(_))).count()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn frame(status: u8, distance_mm: i16) -> Frame {
        Frame {
            rows: ROWS as u8,
            cols: COLS as u8,
            distance_mm: vec![distance_mm; ZONES],
            status: vec![status; ZONES],
        }
    }

    /// The three classes a consumer must be able to tell apart. Especially the
    /// last two: "nothing there" and "I could not measure" look identical in a
    /// distance-only view, and mean opposite things to a map.
    #[test]
    fn status_decides_what_a_distance_means() {
        assert_eq!(frame(5, 1234).zone(0), Zone::Range(1.234));
        assert_eq!(frame(9, 500).zone(0), Zone::Range(0.5));
        assert_eq!(frame(255, 0).zone(0), Zone::NoTarget);
        assert_eq!(frame(4, 900).zone(0), Zone::Unusable(4));
        assert_eq!(
            frame(5, -3).zone(0),
            Zone::Unusable(5),
            "a valid status with a negative range is not a range"
        );
    }

    #[test]
    fn valid_count_counts_ranges_only() {
        assert_eq!(frame(5, 1000).valid_count(), ZONES);
        assert_eq!(frame(255, 0).valid_count(), 0);
        assert_eq!(frame(4, 1000).valid_count(), 0);
    }

    /// A short or ragged frame must not panic a consumer — the wire carries
    /// vectors, and a peer from another release could send fewer.
    #[test]
    fn a_ragged_frame_reads_as_no_target() {
        let ragged = Frame {
            rows: ROWS as u8,
            cols: COLS as u8,
            distance_mm: vec![1000; 3],
            status: vec![5; 2],
        };
        assert_eq!(ragged.zone(0), Zone::Range(1.0));
        assert_eq!(ragged.zone(2), Zone::NoTarget, "missing status");
        assert_eq!(ragged.zone(99), Zone::NoTarget, "past the end");
    }
}

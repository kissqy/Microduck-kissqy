//! The sensor itself: a safe wrapper over the vendored ULDs, either generation.
//!
//! Every call here is one FFI call into a `vendor/*/shim.c`, whose whole surface
//! is scalars and two 64-entry arrays. The unsafety is therefore confined to this
//! file and is all of one shape — "the C writes 64 entries into a buffer I sized
//! at 64" — rather than spread across a hand-mirrored `repr(C)` struct.
//!
//! **Two generations, one interface.** A VL53L5CX and a VL53L8CX are the same
//! package, the same register map and the same 8×8 output, with different
//! firmware and a differently-prefixed driver. [`Generation`] is decided by an ID
//! read before any firmware is uploaded, and from then on this file dispatches
//! every call to that generation's shim. Nothing above it needs to know which is
//! fitted — but everything below reports it, because "which sensor is on this
//! duck" is the first question when depth looks wrong.
//!
//! **One instance per process, enforced.** Each shim keeps its configuration in a
//! file-scope static (see its header for why), so a second [`Sensor`] would
//! quietly share and corrupt the first one's state. [`Sensor::open`] refuses
//! instead.

#[cfg(target_os = "linux")]
use std::ffi::CString;
use std::path::Path;
#[cfg(target_os = "linux")]
use std::sync::atomic::{AtomicBool, Ordering};

#[cfg(target_os = "linux")]
use anyhow::{Context, anyhow};
use anyhow::{Result, bail};

use crate::Frame;
#[cfg(target_os = "linux")]
use crate::{COLS, ROWS, ZONES};

#[cfg(target_os = "linux")]
unsafe extern "C" {
    /// Generation-agnostic: `vendor/probe.c`, no driver involved.
    fn tof_probe_id(
        dev_path: *const std::ffi::c_char,
        addr_7bit: u8,
        device_id: *mut u8,
        revision_id: *mut u8,
    ) -> i32;

    fn vl8_open(dev_path: *const std::ffi::c_char, addr_7bit: u8) -> i32;
    fn vl8_close();
    fn vl8_is_alive() -> i32;
    fn vl8_init() -> i32;
    fn vl8_start(freq_hz: u8) -> i32;
    fn vl8_stop() -> i32;
    fn vl8_data_ready() -> i32;
    fn vl8_get_frame(dist_mm: *mut i16, status: *mut u8) -> i32;

    fn vl5_open(dev_path: *const std::ffi::c_char, addr_7bit: u8) -> i32;
    fn vl5_close();
    fn vl5_is_alive() -> i32;
    fn vl5_init() -> i32;
    fn vl5_start(freq_hz: u8) -> i32;
    fn vl5_stop() -> i32;
    fn vl5_data_ready() -> i32;
    fn vl5_get_frame(dist_mm: *mut i16, status: *mut u8) -> i32;
}

/// Held for the life of the process by the one [`Sensor`] that exists.
#[cfg(target_os = "linux")]
static TAKEN: AtomicBool = AtomicBool::new(false);

/// Which sensor answered the ID probe.
///
/// The revision byte is ST's, and it is the only thing that distinguishes the two
/// before a driver is loaded — the packages are interchangeable on the board.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Generation {
    /// Revision 0x0C.
    L8cx,
    /// Revision 0x02 — the older sensor, and the one most ducks in the field have.
    L5cx,
    /// Something answered, but not with an ID either driver knows.
    Unknown { device_id: u8, revision_id: u8 },
}

impl Generation {
    // Both this and `driver` below are only ever reached from an open sensor, and
    // no sensor opens without the driver — see the off-board `Sensor` at the end.
    #[cfg(target_os = "linux")]
    fn from_ids(device_id: u8, revision_id: u8) -> Self {
        match revision_id {
            0x0C => Self::L8cx,
            0x02 => Self::L5cx,
            _ => Self::Unknown {
                device_id,
                revision_id,
            },
        }
    }

    pub fn as_str(&self) -> &'static str {
        match self {
            Self::L8cx => "VL53L8CX",
            Self::L5cx => "VL53L5CX",
            Self::Unknown { .. } => "unknown",
        }
    }

    /// The shim this generation drives through. `None` for one neither ULD knows.
    #[cfg(target_os = "linux")]
    fn driver(&self) -> Option<Driver> {
        match self {
            Self::L8cx => Some(Driver::L8),
            Self::L5cx => Some(Driver::L5),
            Self::Unknown { .. } => None,
        }
    }
}

/// Which set of `extern "C"` functions to call. One variant per vendored ULD.
#[cfg(target_os = "linux")]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Driver {
    L5,
    L8,
}

#[cfg(target_os = "linux")]
impl Driver {
    // Each of these is the same call into a different generation's shim. Wrapped
    // one per operation rather than as a table of function pointers because the
    // `unsafe` blocks then each say what they are doing.

    fn open(self, path: &CString, address: u8) -> i32 {
        // SAFETY: `path` is NUL-terminated and outlives the call; the shim only
        // opens the file and stores the descriptor.
        unsafe {
            match self {
                Self::L5 => vl5_open(path.as_ptr(), address),
                Self::L8 => vl8_open(path.as_ptr(), address),
            }
        }
    }

    fn close(self) {
        // SAFETY: closes the descriptor the shim owns; idempotent there.
        unsafe {
            match self {
                Self::L5 => vl5_close(),
                Self::L8 => vl8_close(),
            }
        }
    }

    fn is_alive(self) -> i32 {
        // SAFETY: the shim's descriptor is open and its configuration zeroed.
        unsafe {
            match self {
                Self::L5 => vl5_is_alive(),
                Self::L8 => vl8_is_alive(),
            }
        }
    }

    fn init(self) -> i32 {
        // SAFETY: uploads the firmware into the sensor over the open descriptor.
        unsafe {
            match self {
                Self::L5 => vl5_init(),
                Self::L8 => vl8_init(),
            }
        }
    }

    fn start(self, hz: u8) -> i32 {
        // SAFETY: writes registers over the open descriptor.
        unsafe {
            match self {
                Self::L5 => vl5_start(hz),
                Self::L8 => vl8_start(hz),
            }
        }
    }

    fn stop(self) -> i32 {
        // SAFETY: as above.
        unsafe {
            match self {
                Self::L5 => vl5_stop(),
                Self::L8 => vl8_stop(),
            }
        }
    }

    fn data_ready(self) -> i32 {
        // SAFETY: reads one register.
        unsafe {
            match self {
                Self::L5 => vl5_data_ready(),
                Self::L8 => vl8_data_ready(),
            }
        }
    }

    fn get_frame(self, distance_mm: &mut [i16; ZONES], status: &mut [u8; ZONES]) -> i32 {
        // SAFETY: both pointers are to arrays of exactly ZONES (64) entries,
        // which is what the shims' `memcpy`s write — the resolution is pinned to
        // 8×8 by `start`, and both ULDs' results blocks are 64 wide regardless.
        unsafe {
            match self {
                Self::L5 => vl5_get_frame(distance_mm.as_mut_ptr(), status.as_mut_ptr()),
                Self::L8 => vl8_get_frame(distance_mm.as_mut_ptr(), status.as_mut_ptr()),
            }
        }
    }
}

/// An open, initialised sensor, ranging or not.
#[cfg(target_os = "linux")]
pub struct Sensor {
    generation: Generation,
    driver: Driver,
    ranging: bool,
}

#[cfg(target_os = "linux")]
impl Sensor {
    /// Probe what is on the bus, then open it with the matching driver.
    ///
    /// The slow part is the firmware: ~90 KB over I²C, a few seconds at 400 kHz
    /// (tens on a bit-banged bus). It happens once per process, before ranging,
    /// which is why the daemon does it off the socket-serving task.
    pub fn open(bus: &Path, address: u8) -> Result<Self> {
        if TAKEN.swap(true, Ordering::AcqRel) {
            bail!("a sensor is already open in this process");
        }
        // From here on every early return must release the claim, or one failed
        // attempt would refuse every retry for the life of the process.
        Self::open_inner(bus, address).inspect_err(|_| TAKEN.store(false, Ordering::Release))
    }

    fn open_inner(bus: &Path, address: u8) -> Result<Self> {
        let path = CString::new(bus.as_os_str().as_encoded_bytes())
            .with_context(|| format!("{} is not a usable device path", bus.display()))?;

        // Ask what is there before loading anything: the two generations take
        // different firmware, and the upload is the expensive, slow step.
        let mut device_id = 0u8;
        let mut revision_id = 0u8;
        // SAFETY: `path` outlives the call; both out-pointers are live locals the
        // C writes one byte each into.
        let probed =
            unsafe { tof_probe_id(path.as_ptr(), address, &mut device_id, &mut revision_id) };
        if probed != 0 {
            bail!("nothing answered at {address:#04x} on {}", bus.display());
        }

        let generation = Generation::from_ids(device_id, revision_id);
        let Some(driver) = generation.driver() else {
            return Err(anyhow!(
                "something at {address:#04x} answered with device {device_id:#04x} \
                 revision {revision_id:#04x}, which is neither a VL53L5CX nor a VL53L8CX"
            ));
        };

        if driver.open(&path, address) != 0 {
            bail!("cannot open {}", bus.display());
        }
        if driver.is_alive() != 1 {
            driver.close();
            bail!(
                "the {} stopped answering between the probe and the handshake",
                generation.as_str()
            );
        }
        let status = driver.init();
        if status != 0 {
            driver.close();
            bail!(
                "{} firmware upload failed (ULD status {status})",
                generation.as_str()
            );
        }

        Ok(Self {
            generation,
            driver,
            ranging: false,
        })
    }

    pub fn generation(&self) -> Generation {
        self.generation
    }

    /// Start ranging at `hz`, 8×8.
    pub fn start(&mut self, hz: u8) -> Result<()> {
        let status = self.driver.start(hz);
        if status != 0 {
            bail!("start ranging at {hz} Hz failed (ULD status {status})");
        }
        self.ranging = true;
        Ok(())
    }

    /// Is a new frame ready? `Err` is a bus error, which the caller treats as
    /// "the sensor went away" rather than "not yet".
    pub fn data_ready(&self) -> Result<bool> {
        match self.driver.data_ready() {
            1 => Ok(true),
            0 => Ok(false),
            _ => Err(anyhow!("the sensor stopped answering")),
        }
    }

    /// Read the frame the sensor has ready.
    pub fn read_frame(&mut self) -> Result<Frame> {
        let mut distance_mm = [0i16; ZONES];
        let mut status = [0u8; ZONES];
        let rc = self.driver.get_frame(&mut distance_mm, &mut status);
        if rc != 0 {
            bail!("reading the frame failed (ULD status {rc})");
        }
        Ok(Frame {
            rows: ROWS as u8,
            cols: COLS as u8,
            distance_mm: distance_mm.to_vec(),
            status: status.to_vec(),
        })
    }
}

#[cfg(target_os = "linux")]
impl Drop for Sensor {
    fn drop(&mut self) {
        if self.ranging {
            // Ignored: there is nothing left to do about a sensor that will not
            // stop, and the descriptor closes on the next line either way.
            self.driver.stop();
        }
        self.driver.close();
        TAKEN.store(false, Ordering::Release);
    }
}

/// The same type on a platform with no i2c-dev, so the daemon still builds there.
///
/// `vendor/platform.c` reaches the bus through Linux's `I2C_RDWR` ioctl, so
/// `build.rs` compiles no driver anywhere else and there is nothing for `open` to
/// open. This is not a fake sensor and must never become one — `tofd --fake`
/// already exists for a laptop, and it says what it is in its name. This exists so
/// that `cargo test --workspace` works off a board.
///
/// Uninhabited on purpose: `open` is the only constructor and it always fails, so
/// the compiler discharges every other method instead of leaving a body that could
/// one day return an invented frame.
#[cfg(not(target_os = "linux"))]
pub struct Sensor(std::convert::Infallible);

#[cfg(not(target_os = "linux"))]
impl Sensor {
    pub fn open(bus: &Path, _address: u8) -> Result<Self> {
        bail!(
            "no i2c-dev on this platform, so {} cannot be opened — off a board, run `tofd --fake`",
            bus.display()
        )
    }

    pub fn generation(&self) -> Generation {
        match self.0 {}
    }

    pub fn start(&mut self, _hz: u8) -> Result<()> {
        match self.0 {}
    }

    pub fn data_ready(&self) -> Result<bool> {
        match self.0 {}
    }

    pub fn read_frame(&mut self) -> Result<Frame> {
        match self.0 {}
    }
}

// Both tests reach the driver — one the generation-to-shim mapping, the other the
// single-instance claim — so neither has anything to say where no driver is built.
#[cfg(all(test, target_os = "linux"))]
mod tests {
    use super::*;

    /// The revision byte is what picks the firmware, so the mapping is the whole
    /// two-generation story. ST's values, and an unknown one must not be guessed
    /// at — uploading the wrong blob is how you brick a probe.
    #[test]
    fn revisions_map_to_generations_and_drivers() {
        assert_eq!(Generation::from_ids(0xF0, 0x0C), Generation::L8cx);
        assert_eq!(Generation::L8cx.driver(), Some(Driver::L8));

        assert_eq!(Generation::from_ids(0xF0, 0x02), Generation::L5cx);
        assert_eq!(Generation::L5cx.driver(), Some(Driver::L5));

        let odd = Generation::from_ids(0x00, 0xFF);
        assert!(matches!(
            odd,
            Generation::Unknown {
                device_id: 0x00,
                revision_id: 0xFF
            }
        ));
        assert_eq!(odd.driver(), None, "an unknown sensor gets no firmware");
    }

    /// Opening a bus that cannot exist must fail *and* release the single-instance
    /// claim — the daemon retries after a failure, and a claim left set would turn
    /// one bad open into a permanently sensorless process.
    #[test]
    fn a_failed_open_releases_the_claim() {
        let nowhere = Path::new("/dev/definitely-not-an-i2c-bus");
        assert!(Sensor::open(nowhere, 0x29).is_err());
        assert!(!TAKEN.load(Ordering::Acquire), "the claim must be released");
        assert!(
            Sensor::open(nowhere, 0x29).is_err(),
            "a retry must be possible"
        );
        assert!(!TAKEN.load(Ordering::Acquire));
    }
}

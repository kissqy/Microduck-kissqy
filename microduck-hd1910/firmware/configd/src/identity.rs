//! Per-device identity, and the default name derived from it.
//!
//! Three friends with three robots in one room must each reach *theirs*. Every board flashed from
//! one image used to advertise `radxa-zero3`, so a phone could not tell them apart — and picking
//! the wrong one means writing your wifi credentials into someone else's robot. The fix is that a
//! robot is distinguishable **before anyone renames anything**, which needs something per-board to
//! hang a name off.
//!
//! **The SoC serial, not the Bluetooth address.** The obvious candidate was the adapter address,
//! since a peer already sees it at the link layer, so a name derived from it leaks nothing new.
//! Measured on a board, it does not hold still: `btd`'s startup line recorded
//! `50:37:CD:16:2B:EC` and then `50:37:CD:16:1B:92` across sixteen boots, with no reflash in
//! between and nothing but BLE connections and gamepad pairing done to it. An identity that
//! changes for reasons nobody can name is not an identity. (That wandering is a bug in its own
//! right — an address change orphans every bond under `/var/lib/bluetooth/<address>/` and
//! invalidates the peripheral identifier a phone saved — but it is not this module's problem.)
//!
//! The serial comes out of the SoC's one-time-programmable fuses by way of the bootloader, so it
//! survives a reflash, survives swapping the radio module, and needs no provisioning step to
//! exist — which is what makes a hand-flashed board work. It is also readable *immediately*: a
//! plain file, no root, no D-Bus, no waiting the ~73 seconds it takes `hci0` to appear on this
//! board.

use std::path::Path;

use sha2::{Digest, Sha256};

/// Where the bootloader leaves the SoC serial.
///
/// `/proc/device-tree/serial-number` rather than `/proc/cpuinfo`: both report the same value on
/// this board (`bb7b734a7717ac41`), but the devicetree property is a generic binding that any
/// board populating it satisfies, while `cpuinfo`'s `Serial` line is a per-architecture quirk of
/// how the kernel chooses to print it. A future board on a different SoC is more likely to keep
/// the first.
const SERIAL_PATH: &str = "/proc/device-tree/serial-number";

/// The prefix every derived name carries.
///
/// Hardcoded rather than built from the hostname, which would give `radxa-zero3-7f3a` — longer
/// than what it replaces and no more meaningful. The robot is a duck.
const NAME_PREFIX: &str = "duck";

/// The board's serial number, or `None` where there is not one to read.
///
/// `None` on a macOS laptop, and on any board whose bootloader does not fill the property in. The
/// caller falls back rather than failing: a robot with no serial must still come up with a working
/// name.
pub fn serial() -> Option<String> {
    serial_at(Path::new(SERIAL_PATH))
}

/// [`serial`], against an arbitrary path so it can be tested off a board.
pub fn serial_at(path: &Path) -> Option<String> {
    let raw = std::fs::read(path).ok()?;
    let text = String::from_utf8_lossy(&raw);

    // Devicetree properties are NUL-terminated strings, and a property may hold several — so the
    // first NUL ends the value rather than being trailing junk to trim.
    let serial = text.split('\0').next()?.trim();

    // A property that exists but is blank, or full of control characters, is no identity at all,
    // and it also reaches a client verbatim through `system.info`.
    if serial.is_empty() || !serial.chars().all(|c| c.is_ascii_graphic()) {
        return None;
    }
    Some(serial.to_owned())
}

/// The name a robot answers to before anyone has renamed it: `duck-7f3a`.
///
/// **Hashed rather than sliced.** Taking the last four characters of the serial would assume that
/// is where two chips differ, and nothing guarantees it — a vendor is free to make any part of the
/// value sequential, or constant. A digest spreads whatever entropy the serial has across the
/// whole output.
///
/// **SHA-256 rather than [`std::hash::DefaultHasher`]**, whose output is explicitly not stable
/// across Rust releases. A `rustup update` would silently rename every robot in the field, and
/// nobody would ever connect the two.
///
/// Four hex characters, so 65 536 possibilities: three robots in a room share a name about once in
/// 22 000 times. This is a *default* meant to be distinguishable, not a unique key — `system.setName`
/// from a phone and `robotctl system set-name` from provisioning both override it, and renaming is
/// the escape hatch on the rare collision.
pub fn default_name(serial: &str) -> String {
    let digest = Sha256::digest(serial.as_bytes());
    format!("{NAME_PREFIX}-{:02x}{:02x}", digest[0], digest[1])
}

#[cfg(test)]
mod tests {
    use super::*;

    fn write(dir: &Path, contents: &[u8]) -> std::path::PathBuf {
        let path = dir.join("serial-number");
        std::fs::write(&path, contents).unwrap();
        path
    }

    /// The real shape of the property on the board: the value, NUL-terminated.
    #[test]
    fn a_nul_terminated_property_reads_as_the_value() {
        let dir = tempfile::tempdir().unwrap();
        let path = write(dir.path(), b"bb7b734a7717ac41\0");
        assert_eq!(serial_at(&path).as_deref(), Some("bb7b734a7717ac41"));
    }

    /// `/proc/device-tree` is absent on a laptop, and that must be a fallback rather than a panic.
    #[test]
    fn a_missing_property_is_no_serial() {
        let dir = tempfile::tempdir().unwrap();
        assert_eq!(serial_at(&dir.path().join("absent")), None);
    }

    /// A board that fills the property in with nothing has no identity, and saying so lets the
    /// caller fall back to the hostname instead of naming every such board `duck-e3b0`.
    #[test]
    fn a_blank_or_unprintable_property_is_no_serial() {
        let dir = tempfile::tempdir().unwrap();
        for raw in [&b""[..], b"\0", b"   \0", b"\x01\x02\0"] {
            assert_eq!(serial_at(&write(dir.path(), raw)), None, "{raw:?}");
        }
    }

    /// The name has to be stable for the life of the board: it is what a phone remembers, and a
    /// robot that renames itself is one a kid has to find again. This pins the exact output for
    /// the serial the board actually has, so a change to the derivation fails here rather than in
    /// someone's Bluetooth list.
    #[test]
    fn the_name_derived_from_this_boards_serial_is_pinned() {
        assert_eq!(default_name("bb7b734a7717ac41"), "duck-c51b");
    }

    /// Two boards must not collide, which is the entire point.
    #[test]
    fn different_serials_give_different_names() {
        assert_ne!(
            default_name("bb7b734a7717ac41"),
            default_name("bb7b734a7717ac42")
        );
    }

    /// A one-character difference in the serial has to move the name, which slicing the last
    /// characters off a sequential serial would not guarantee.
    #[test]
    fn a_name_is_shaped_like_a_name() {
        let name = default_name("bb7b734a7717ac41");
        let suffix = name.strip_prefix("duck-").expect("the prefix");
        assert_eq!(suffix.len(), 4, "{name}");
        assert!(suffix.chars().all(|c| c.is_ascii_hexdigit()), "{name}");
        assert!(name.len() <= crate::store::MAX_NAME, "{name}");
    }
}

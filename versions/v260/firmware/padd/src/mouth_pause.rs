//! A short lease pauses only padd's mouth writer while HAT language PCM plays.
//!
//! The root-owned AI worker writes `<token>.lease` under padd's existing systemd
//! RuntimeDirectory. The payload is CLOCK_MONOTONIC milliseconds, not wall time.
//! The worker waits for the exact same deadline in `<token>.ack` before PCM.
//! No live lease means the official mouth notification runs on every pad tick.

use std::collections::BTreeMap;
use std::fs::{self, OpenOptions};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
#[cfg(unix)]
use std::os::unix::fs::OpenOptionsExt;

const DIRECTORY: &str = "/run/padd/ai-mouth";
const MAX_FUTURE_MS: u64 = 1500;
const MAX_LEASES: usize = 64;

pub struct MouthPause {
    directory: PathBuf,
    acknowledged: BTreeMap<String, u64>,
}

impl MouthPause {
    pub fn new() -> Self {
        let directory = PathBuf::from(DIRECTORY);
        // /run/padd is already writable by padd under ProtectSystem=strict.
        // The helper may also create this child, with the same padd ownership.
        let _ = fs::create_dir(&directory);
        Self { directory, acknowledged: BTreeMap::new() }
    }

    pub fn poll(&mut self) -> bool {
        match monotonic_ms() {
            Some(now) => self.poll_at(now),
            None => { self.acknowledged.clear(); false }
        }
    }

    fn poll_at(&mut self, now: u64) -> bool {
        let Ok(entries) = fs::read_dir(&self.directory) else {
            self.acknowledged.clear();
            return false;
        };
        let mut live = BTreeMap::new();
        for entry in entries.flatten().filter(|entry| {
            entry.file_name().to_str().is_some_and(|name| name.ends_with(".lease"))
        }).take(MAX_LEASES) {
            let Some(name) = entry.file_name().to_str().map(str::to_owned) else { continue; };
            let Some(token) = name.strip_suffix(".lease") else { continue; };
            if token.len() != 32 || !token.bytes().all(|c| c.is_ascii_digit() || (b'a'..=b'f').contains(&c)) {
                continue;
            }
            if live.len() == MAX_LEASES { break; }
            // Reject directories and symlinks. A malformed or expired request
            // cannot suppress manual control and never receives an ACK.
            if !entry.file_type().is_ok_and(|kind| kind.is_file()) { continue; }
            let Some(expiry) = read_expiry(&entry.path()) else { continue; };
            if expiry <= now || expiry - now > MAX_FUTURE_MS { continue; }
            let ack = self.directory.join(format!("{token}.ack"));
            let acknowledged = self.acknowledged.get(token) == Some(&expiry)
                && read_expiry(&ack) == Some(expiry);
            if acknowledged || write_ack(&ack, expiry).is_ok() {
                live.insert(token.to_owned(), expiry);
            }
        }
        let paused = !live.is_empty();
        self.acknowledged = live;
        paused
    }
}

fn read_expiry(path: &Path) -> Option<u64> {
    let file = fs::File::open(path).ok()?;
    if file.metadata().ok()?.len() > 32 { return None; }
    let mut value = String::new();
    file.take(33).read_to_string(&mut value).ok()?;
    value.trim().parse().ok()
}

fn write_ack(path: &Path, expiry: u64) -> std::io::Result<()> {
    // One padd process owns the runtime directory. Atomic rename prevents the
    // root helper from seeing a partially written acknowledgement on renewal.
    let temporary = path.with_extension("ack.tmp");
    let mut options = OpenOptions::new();
    options.write(true).create(true).truncate(true);
    #[cfg(unix)]
    options.mode(0o644);
    let mut output = options.open(&temporary)?;
    writeln!(output, "{expiry}")?;
    drop(output);
    fs::rename(temporary, path)
}

#[cfg(target_os = "linux")]
fn monotonic_ms() -> Option<u64> {
    // Linux's CLOCK_MONOTONIC is the same clock Python time.monotonic_ns uses.
    let mut value = libc::timespec { tv_sec: 0, tv_nsec: 0 };
    if unsafe { libc::clock_gettime(libc::CLOCK_MONOTONIC, &mut value) } != 0
        || value.tv_sec < 0 || value.tv_nsec < 0 {
        return None;
    }
    Some((value.tv_sec as u64).saturating_mul(1000) + value.tv_nsec as u64 / 1_000_000)
}

#[cfg(not(target_os = "linux"))]
fn monotonic_ms() -> Option<u64> { None }

#[cfg(test)]
mod tests {
    use super::*;

    const A: &str = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
    const B: &str = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";

    fn setup() -> (tempfile::TempDir, MouthPause) {
        let directory = tempfile::tempdir().unwrap();
        let pause = MouthPause { directory: directory.path().to_owned(), acknowledged: BTreeMap::new() };
        (directory, pause)
    }

    fn lease(directory: &Path, token: &str, expiry: u64) {
        fs::write(directory.join(format!("{token}.lease")), format!("{expiry}\n")).unwrap();
    }

    #[test]
    fn idle_mouth_is_not_paused_and_valid_lease_is_acknowledged() {
        let (directory, mut pause) = setup();
        assert!(!pause.poll_at(1000));
        lease(directory.path(), A, 1750);
        assert!(pause.poll_at(1000));
        assert_eq!(read_expiry(&directory.path().join(format!("{A}.ack"))), Some(1750));
    }

    #[test]
    fn renewal_is_exact_and_close_or_crash_expiry_restores_manual_writer() {
        let (directory, mut pause) = setup();
        lease(directory.path(), A, 1750);
        assert!(pause.poll_at(1000));
        lease(directory.path(), A, 1950);
        assert!(pause.poll_at(1200));
        assert_eq!(read_expiry(&directory.path().join(format!("{A}.ack"))), Some(1950));
        assert!(!pause.poll_at(1950), "a crashed worker cannot leave the mouth paused");
        lease(directory.path(), A, 2700);
        assert!(pause.poll_at(2000));
        fs::remove_file(directory.path().join(format!("{A}.lease"))).unwrap();
        assert!(!pause.poll_at(2001));
    }

    #[test]
    fn each_player_owns_its_lease() {
        let (directory, mut pause) = setup();
        lease(directory.path(), A, 1600);
        lease(directory.path(), B, 1750);
        assert!(pause.poll_at(1000));
        fs::remove_file(directory.path().join(format!("{A}.lease"))).unwrap();
        assert!(pause.poll_at(1600), "closing one speaker must not release another");
        assert!(!pause.poll_at(1750));
    }

    #[test]
    fn bad_names_payloads_and_unbounded_deadlines_are_ignored() {
        let (directory, mut pause) = setup();
        lease(directory.path(), "bad-token", 1750);
        lease(directory.path(), A, 2501);
        fs::write(directory.path().join(format!("{B}.lease")), "not a deadline").unwrap();
        assert!(!pause.poll_at(1000));
        assert!(!directory.path().join(format!("{A}.ack")).exists());
    }

    #[test]
    fn stale_acknowledgements_cannot_hide_a_live_lease() {
        let (directory, mut pause) = setup();
        for i in 0..200 {
            fs::write(directory.path().join(format!("{i:032x}.ack")), "1750\n").unwrap();
        }
        lease(directory.path(), A, 1750);
        assert!(pause.poll_at(1000));
    }

    #[test]
    fn lease_symlinks_and_failed_ack_do_not_pause_manual_control() {
        let (directory, mut pause) = setup();
        let elsewhere = directory.path().join("elsewhere");
        fs::write(&elsewhere, "1750\n").unwrap();
        #[cfg(unix)]
        std::os::unix::fs::symlink(&elsewhere, directory.path().join(format!("{A}.lease"))).unwrap();
        lease(directory.path(), B, 1750);
        fs::create_dir(directory.path().join(format!("{B}.ack"))).unwrap();
        assert!(!pause.poll_at(1000));
    }

    #[test]
    fn linux_clock_matches_uptime_domain() {
        let now = monotonic_ms().expect("Linux monotonic clock");
        let uptime: f64 = fs::read_to_string("/proc/uptime").unwrap().split_whitespace().next().unwrap().parse().unwrap();
        assert!((now as f64 - uptime * 1000.0).abs() < 100.0);
    }
}

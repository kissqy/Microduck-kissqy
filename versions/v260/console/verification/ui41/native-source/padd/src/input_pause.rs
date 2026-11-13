//! One bounded AI input lease. Only padd's ordinary writer yields; safety buttons
//! remain in the original event loop. This is not robotd-level arbitration.
use std::collections::BTreeMap;
use std::fs::{self, OpenOptions};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
#[cfg(unix)]
use std::os::unix::fs::OpenOptionsExt;

const DIRECTORY: &str = "/run/padd/ai-input";
const MAX_FUTURE_MS: u64 = 1500;
const MAX_REQUESTS: usize = 64;

#[derive(Default, Debug, Clone, Copy)]
pub struct Status { pub active: bool, pub pending: bool }

pub struct InputPause {
    directory: PathBuf,
    owner: Option<(String, u64)>,
}

impl InputPause {
    pub fn new() -> Self {
        let directory = PathBuf::from(DIRECTORY);
        let _ = fs::create_dir(&directory);
        Self { directory, owner: None }
    }

    /// Called after consuming buttons, before any ordinary write this tick.
    /// Once granted, moved sticks cannot steal the lease. Start/Select cancel it.
    pub fn poll(&mut self, ready: Result<(), &'static str>, manual: Option<&str>) -> Status {
        let Some(now) = monotonic_ms() else { self.owner = None; return Status::default(); };
        self.poll_at(now, ready, manual)
    }

    fn poll_at(&mut self, now: u64, ready: Result<(), &'static str>, manual: Option<&str>) -> Status {
        let mut requests = BTreeMap::new();
        if let Ok(entries) = fs::read_dir(&self.directory) {
            for entry in entries.flatten().filter(|e| e.file_name().to_str().is_some_and(|s| s.ends_with(".lease"))).take(MAX_REQUESTS) {
                let Some(name) = entry.file_name().to_str().map(str::to_owned) else { continue; };
                let Some(token) = name.strip_suffix(".lease") else { continue; };
                if token.len() != 32 || !token.bytes().all(|c| c.is_ascii_digit() || (b'a'..=b'f').contains(&c))
                    || !entry.file_type().is_ok_and(|t| t.is_file()) { continue; }
                let Some(expiry) = read_expiry(&entry.path()) else { continue; };
                if expiry > now && expiry - now <= MAX_FUTURE_MS {
                    requests.insert(token.to_owned(), expiry);
                }
            }
        }
        let pending = !requests.is_empty();
        if let Some(reason) = manual {
            // Mark every fresh contender, not just the acknowledged owner. A
            // pending claimant must not take over after the manual stop.
            for token in requests.keys() { self.cancel(token, reason); }
            if let Some((token, _)) = self.owner.take() { self.cancel(&token, reason); }
            return Status { active: false, pending };
        }

        if let Some((token, confirmed)) = self.owner.take() {
            if let Some(&expiry) = requests.get(&token)
                && !self.cancelled(&token) {
                let ack = self.directory.join(format!("{token}.ack"));
                let updated = confirmed == expiry && read_expiry(&ack) == Some(expiry)
                    || write_atomic(&ack, &format!("{expiry}\n")).is_ok();
                // A renewal ACK write failure cannot release padd while the
                // previously confirmed ACK is still valid to the RPC helper.
                let trusted = if updated { Some(expiry) }
                    else if confirmed > now && confirmed <= expiry { Some(confirmed) }
                    else { None };
                if let Some(trusted) = trusted {
                    for other in requests.keys().filter(|other| *other != &token) { self.cancel(other, "busy"); }
                    self.owner = Some((token, trusted));
                    return Status { active: true, pending };
                }
            }
            // A missing lease is an intentional release. An unreadable lease or
            // directory is not: root's RPC validator may still see the live old
            // ACK. Keep yielding until that confirmed deadline, then recover.
            if !requests.contains_key(&token) && !self.cancelled(&token) && confirmed > now
                && self.directory.join(format!("{token}.lease")).try_exists().unwrap_or(true) {
                for other in requests.keys().filter(|other| *other != &token) { self.cancel(other, "busy"); }
                self.owner = Some((token, confirmed));
                return Status { active: true, pending: true };
            }
            // Let padd finish the previous owner's one-time handoff before
            // acknowledging any replacement owner on a later tick.
            return Status { active: false, pending };
        }

        // A cancelled, still-live request remains a barrier until its helper
        // removes it (or its TTL expires). Renewing it can never recover an ACK.
        if requests.keys().any(|token| self.cancelled(token)) {
            for token in requests.keys().filter(|token| !self.cancelled(token)) { self.cancel(token, "busy"); }
            return Status { active: false, pending };
        }
        if let Err(reason) = ready {
            for token in requests.keys() { self.cancel(token, reason); }
            return Status { active: false, pending };
        }
        if let Some((token, &expiry)) = requests.iter().next() {
            let ack = self.directory.join(format!("{token}.ack"));
            if write_atomic(&ack, &format!("{expiry}\n")).is_ok() {
                self.owner = Some((token.clone(), expiry));
                for other in requests.keys().filter(|other| *other != token) { self.cancel(other, "busy"); }
                return Status { active: true, pending };
            }
        }
        Status { active: false, pending }
    }

    fn cancelled(&self, token: &str) -> bool { self.directory.join(format!("{token}.cancel")).exists() }

    fn cancel(&self, token: &str, reason: &str) {
        let _ = write_atomic(&self.directory.join(format!("{token}.cancel")), &format!("{reason}\n"));
        let _ = fs::remove_file(self.directory.join(format!("{token}.ack")));
    }
}

fn read_expiry(path: &Path) -> Option<u64> {
    let file = fs::File::open(path).ok()?;
    if file.metadata().ok()?.len() > 32 { return None; }
    let mut value = String::new();
    file.take(33).read_to_string(&mut value).ok()?;
    value.trim().parse().ok()
}

fn write_atomic(path: &Path, payload: &str) -> std::io::Result<()> {
    let temporary = path.with_extension(format!("{}.tmp", path.extension().unwrap_or_default().to_string_lossy()));
    let mut options = OpenOptions::new();
    options.write(true).create(true).truncate(true);
    #[cfg(unix)] options.mode(0o644);
    let mut file = options.open(&temporary)?;
    file.write_all(payload.as_bytes())?;
    drop(file);
    fs::rename(temporary, path)
}

#[cfg(target_os = "linux")]
fn monotonic_ms() -> Option<u64> {
    let mut t = libc::timespec { tv_sec: 0, tv_nsec: 0 };
    if unsafe { libc::clock_gettime(libc::CLOCK_MONOTONIC, &mut t) } != 0 || t.tv_sec < 0 || t.tv_nsec < 0 { return None; }
    Some((t.tv_sec as u64).saturating_mul(1000) + t.tv_nsec as u64 / 1_000_000)
}
#[cfg(not(target_os = "linux"))]
fn monotonic_ms() -> Option<u64> { None }

#[cfg(test)]
mod tests {
    use super::*;
    const A: &str = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
    const B: &str = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
    fn setup() -> (tempfile::TempDir, InputPause) {
        let d = tempfile::tempdir().unwrap();
        let p = InputPause { directory: d.path().to_owned(), owner: None };
        (d,p)
    }
    fn lease(d: &Path, token: &str, expiry: u64) {
        fs::write(d.join(format!("{token}.lease")), format!("{expiry}\n")).unwrap();
    }
    #[test]
    fn grant_and_renew_require_exact_first_ack_but_do_not_recheck_moved_sticks() {
        let (d,mut p)=setup(); lease(d.path(),A,1750);
        assert!(p.poll_at(1000,Ok(()),None).active);
        assert_eq!(read_expiry(&d.path().join(format!("{A}.ack"))),Some(1750));
        lease(d.path(),A,1950);
        assert!(p.poll_at(1200,Err("not-neutral"),None).active);
        assert_eq!(read_expiry(&d.path().join(format!("{A}.ack"))),Some(1950));
    }
    #[test]
    fn grant_refuses_unsafe_modes_and_held_controls() {
        for reason in ["not-drive","not-neutral","imu-head","pose-active"] {
            let (d,mut p)=setup(); lease(d.path(),A,1750);
            assert!(!p.poll_at(1000,Err(reason),None).active);
            assert_eq!(fs::read_to_string(d.path().join(format!("{A}.cancel"))).unwrap().trim(),reason);
            assert!(!d.path().join(format!("{A}.ack")).exists());
        }
    }
    #[test]
    fn manual_stop_cancels_owner_and_every_pending_token_without_replay() {
        let (d,mut p)=setup(); lease(d.path(),A,1750);
        assert!(p.poll_at(1000,Ok(()),None).active);
        lease(d.path(),B,1850);
        assert!(!p.poll_at(1100,Ok(()),Some("manual-select")).active);
        for token in [A,B] { assert!(d.path().join(format!("{token}.cancel")).exists()); }
        lease(d.path(),A,2000);
        assert!(!p.poll_at(1200,Ok(()),None).active, "late renewal cannot undo cancel");
    }
    #[test]
    fn input_is_single_owner_and_busy_requests_cannot_affect_owner() {
        let (d,mut p)=setup(); lease(d.path(),A,1750);
        assert!(p.poll_at(1000,Ok(()),None).active);
        lease(d.path(),B,1900);
        assert!(p.poll_at(1100,Ok(()),None).active);
        assert_eq!(fs::read_to_string(d.path().join(format!("{B}.cancel"))).unwrap().trim(),"busy");
        assert_eq!(p.owner.as_ref().unwrap().0,A);
    }
    #[test]
    fn expiry_or_removal_releases_owner() {
        let (d,mut p)=setup(); lease(d.path(),A,1750);
        assert!(p.poll_at(1000,Ok(()),None).active);
        assert!(!p.poll_at(1750,Ok(()),None).active);
        lease(d.path(),A,2500); assert!(p.poll_at(1800,Ok(()),None).active);
        fs::remove_file(d.path().join(format!("{A}.lease"))).unwrap();
        assert!(!p.poll_at(1850,Ok(()),None).active);
    }
    #[test]
    fn cancelled_live_request_blocks_new_claim_until_helper_cleans_up() {
        let (d,mut p)=setup(); lease(d.path(),A,1750);
        p.poll_at(1000,Ok(()),Some("manual-start")); lease(d.path(),B,1900);
        assert!(!p.poll_at(1100,Ok(()),None).active);
        fs::remove_file(d.path().join(format!("{A}.lease"))).unwrap();
        fs::remove_file(d.path().join(format!("{B}.lease"))).unwrap();
        fs::remove_file(d.path().join(format!("{B}.cancel"))).unwrap();
        lease(d.path(),B,2000); assert!(p.poll_at(1200,Ok(()),None).active);
    }
    #[test]
    fn ack_write_failure_preserves_only_the_old_confirmed_lifetime() {
        let (d,mut p)=setup(); lease(d.path(),A,1750);
        assert!(p.poll_at(1000,Ok(()),None).active);
        // Block the temporary ACK path while retaining the previously live ACK.
        fs::create_dir(d.path().join(format!("{A}.ack.tmp"))).unwrap();
        lease(d.path(),A,1950);
        assert!(p.poll_at(1200,Ok(()),None).active);
        assert_eq!(read_expiry(&d.path().join(format!("{A}.ack"))),Some(1750));
        assert!(!p.poll_at(1750,Ok(()),None).active);
    }
    #[test]
    fn malformed_expired_and_unbounded_leases_do_not_pause_input() {
        let (d,mut p)=setup(); lease(d.path(),A,2501); lease(d.path(),"bad",1750);
        assert!(!p.poll_at(1000,Ok(()),None).active);
        lease(d.path(),A,999); assert!(!p.poll_at(1000,Ok(()),None).active);
    }
    #[test]
    fn unreadable_renewal_cannot_release_before_the_old_ack_expires() {
        let (d,mut p)=setup(); lease(d.path(),A,1750);
        assert!(p.poll_at(1000,Ok(()),None).active);
        let lease=d.path().join(format!("{A}.lease"));
        fs::remove_file(&lease).unwrap(); fs::create_dir(&lease).unwrap();
        assert!(p.poll_at(1200,Ok(()),None).active);
        assert!(!p.poll_at(1750,Ok(()),None).active);
    }
    #[test]
    fn replacement_owner_waits_for_a_handoff_tick() {
        let (d,mut p)=setup(); lease(d.path(),A,1750);
        assert!(p.poll_at(1000,Ok(()),None).active);
        fs::remove_file(d.path().join(format!("{A}.lease"))).unwrap();
        lease(d.path(),B,2000);
        assert!(!p.poll_at(1200,Ok(()),None).active);
        assert!(!d.path().join(format!("{B}.ack")).exists());
        assert!(p.poll_at(1220,Ok(()),None).active);
    }
}

//! Did the restarts an update scheduled actually happen?
//!
//! An update restarts the units a release ships, then — five seconds after its reply is on the wire
//! — restarts the two it could not touch while running: itself, and `btd`, which may be carrying
//! the reply. Both are scheduled through `systemd-run`, and **scheduling is all that is checked
//! today.** `systemd-run` succeeding means a transient timer was created, not that the restart ran,
//! and not that the new binary started. Failures are logged and swallowed on purpose, because an
//! update that worked must not report failure over a restart it could not arrange.
//!
//! That leaves one way for a robot to end up running a release it did not install, and it is silent.
//! This closes it: on every `updaterd` start, each unit's running binary is compared with the
//! release its component has active, and anything stale is restarted.
//!
//! ## What it reads
//!
//! Each daemon publishes its own identity at startup — see [`duck_ipc_proto::Identity`] — so this
//! reads a file rather than interrogating a process. A daemon that published nothing is *not* treated
//! as stale: it is either stopped, or too old to publish, and restarting a robot's daemons because
//! they are old is a decision nobody asked for. The next update makes them able to answer.
//!
//! ## Why startup is the right moment
//!
//! It is the first moment the answer can be trusted. `updaterd` cannot watch its own restart land —
//! it is the process being replaced — so the check has to run in the *successor*, which is exactly
//! what a fresh start is. It also catches everything, not merely a missed timer: a restart that
//! failed, a new binary that would not start, a unit someone stopped mid-update, a rollback that
//! left one daemon behind.
//!
//! At boot this is a no-op, since everything starts from the same symlink. It costs one file read
//! per unit.
//!
//! ## Restarting rather than only reporting
//!
//! Reporting alone would leave a robot running the wrong code with a warning in a journal nobody is
//! reading — the situation this exists to end. So a stale unit is restarted.
//!
//! **Except this one.** `updaterd` restarting itself here would be a loop if the new binary ever
//! disagreed about what "current" is, and a loop in the process that owns recovery is the one
//! failure with no way out. It is reported and left alone, which is safe: it has just started, so
//! anything stale about it was decided before this code ran.
//!
//! That exception used to be the end of the story, and it left one skew nothing repaired. It is now
//! reached from the other side: [`stale_units`] is the same reading without the acting, and
//! `Engine::apply` calls it when a release turns out to be already installed — so an operator running
//! `apply` on a robot that looks wrong schedules the restart this module refuses to perform. Once,
//! on a request, which is not the loop guarded against above.

use duck_ipc_proto as proto;

/// What the check found for one unit.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Finding {
    pub unit: String,
    /// The release the running process was started from. `None` when the unit is stopped, or its
    /// binary sits outside the release layout — a hand-built one on a dev board.
    pub running: Option<semver::Version>,
    pub expected: semver::Version,
    pub verdict: Verdict,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Verdict {
    /// Running the release its component has active.
    Current,
    /// Stale, and restarted.
    Restarted,
    /// Stale, and deliberately not restarted: `updaterd` must not restart itself from its own
    /// startup path.
    ReportedOnly,
    /// Stale, and the restart failed. The journal has systemd's reason.
    RestartFailed,
    /// Nothing to compare: stopped, or running a binary outside the release layout.
    Unknown,
}

/// Decide what to do about one unit, given what it is running and what it should be.
///
/// Pure, and separated from every syscall in this file for one reason: the decisions are the part
/// that can be wrong, and they are impossible to arrange on a real board — a unit running a release
/// that is not the active one is precisely the state that requires a broken update to produce.
pub fn verdict_for(
    running: Option<&semver::Version>,
    expected: &semver::Version,
    is_self: bool,
) -> Verdict {
    match running {
        // A stopped unit is not a stale unit. Something stopped it deliberately, and starting it
        // here would override that decision on every `updaterd` restart.
        None => Verdict::Unknown,
        Some(running) if running == expected => Verdict::Current,
        Some(_) if is_self => Verdict::ReportedOnly,
        Some(_) => Verdict::Restarted,
    }
}

/// Which of these units are not running `expected`, without touching any of them.
///
/// The observing half of [`check`], for the one caller that must act differently. `Engine::apply`
/// reaching an already-current release is the only way a stale `updaterd` gets looked at — this
/// module will not restart it, deliberately — and it cannot drive `systemctl` the way [`check`] does:
/// restarting `updaterd` or `btd` from inside a running update kills the process doing the restarting
/// or drops the transport carrying the reply. So it reads here and schedules there.
///
/// [`verdict_for`] rather than a second comparison, so what counts as stale stays in one place: a
/// stopped unit does not, and neither does one whose build predates the identity file.
///
/// `is_self` is false and both stale verdicts are accepted, because whether a unit may be restarted
/// is the caller's question and not this one's. Every stale unit is named.
pub fn stale_units(expected: &semver::Version, units: &[String]) -> Vec<String> {
    units
        .iter()
        .filter(|unit| {
            let verdict = verdict_for(running_release(unit).as_ref(), expected, false);
            matches!(verdict, Verdict::Restarted | Verdict::ReportedOnly)
        })
        .cloned()
        .collect()
}

/// The release each unit is running, checked against what its component has active.
///
/// `systemctl` is a parameter for the same reason it is one in `engine`: a test hands it a stub. It
/// is only used to *act* now — the reading is a file read, needing nothing.
pub async fn check(
    systemctl: &str,
    expected: &semver::Version,
    self_unit: &str,
    units: Vec<String>,
) -> Vec<Finding> {
    let mut findings = Vec::new();

    for unit in units {
        let running = running_release(&unit);
        let is_self = unit == self_unit;
        let mut verdict = verdict_for(running.as_ref(), expected, is_self);

        if verdict == Verdict::Restarted {
            tracing::warn!(
                unit = %unit,
                running = %running.as_ref().map(|v| v.to_string()).unwrap_or_default(),
                %expected,
                "still running the release it had before the update; restarting it now"
            );
            if let Err(e) = restart(systemctl, &unit).await {
                tracing::error!(unit = %unit, error = %e, "could not restart it");
                verdict = Verdict::RestartFailed;
            }
        } else if verdict == Verdict::ReportedOnly {
            tracing::warn!(
                unit = %unit,
                running = %running.as_ref().map(|v| v.to_string()).unwrap_or_default(),
                %expected,
                "this process is not running the active release, and will not restart itself"
            );
        }

        findings.push(Finding {
            unit,
            running,
            expected: expected.clone(),
            verdict,
        });
    }

    findings
}

/// The release the unit's process says it is running.
///
/// From the identity the daemon published, so the answer comes from the process rather than from a
/// path someone inferred — and needs no privilege, no D-Bus and no `/proc` read. `None` when nothing
/// was published: stopped, or a build predating the mechanism.
fn running_release(unit: &str) -> Option<semver::Version> {
    let service = unit.strip_suffix(".service").unwrap_or(unit);
    proto::read_identity(service)?.release()
}

async fn restart(systemctl: &str, unit: &str) -> Result<(), String> {
    let mut command = tokio::process::Command::new(systemctl);
    command.arg("restart").arg(unit);
    let status = crate::spawn::retrying_busy(&mut command)
        .await
        .map_err(|e| e.to_string())?
        .wait()
        .await
        .map_err(|e| e.to_string())?;
    if status.success() {
        Ok(())
    } else {
        Err(status.to_string())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn v(s: &str) -> semver::Version {
        semver::Version::parse(s).expect("a test version")
    }

    /// The case this exists for: an update's deferred restart never happened, so `btd` is still on
    /// the release it had before. Nothing else on the robot would ever say so.
    #[test]
    fn a_unit_left_on_the_old_release_is_restarted() {
        assert_eq!(
            verdict_for(Some(&v("0.3.0")), &v("0.4.0"), false),
            Verdict::Restarted
        );
    }

    /// A dev release differs from the stable one it precedes only in the prerelease suffix, and
    /// both report the same crate version. Comparing the *release* rather than the build is what
    /// makes those distinguishable at all.
    #[test]
    fn a_dev_release_is_not_the_stable_one_it_precedes() {
        assert_eq!(
            verdict_for(Some(&v("0.4.0-dev.271.7610e6e")), &v("0.4.0"), false),
            Verdict::Restarted
        );
        assert_eq!(
            verdict_for(
                Some(&v("0.4.0-dev.271.7610e6e")),
                &v("0.4.0-dev.271.7610e6e"),
                false
            ),
            Verdict::Current
        );
    }

    /// **`updaterd` must never restart itself from here.** If the successor disagreed about which
    /// release is active it would restart, disagree again, and loop — in the one process that owns
    /// recovery, so nothing would be left to break the cycle.
    #[test]
    fn updaterd_reports_itself_but_does_not_restart_itself() {
        assert_eq!(
            verdict_for(Some(&v("0.3.0")), &v("0.4.0"), true),
            Verdict::ReportedOnly
        );
    }

    /// A stopped unit is not a stale unit. Starting one here would override, on every `updaterd`
    /// start, whoever stopped it — someone with no gamepad who disabled `padd`, most likely.
    #[test]
    fn a_stopped_unit_is_left_stopped() {
        assert_eq!(verdict_for(None, &v("0.4.0"), false), Verdict::Unknown);
    }

    /// The matching case has to stay quiet: this runs on every start, and a check that acts when
    /// nothing is wrong is a restart loop with extra steps.
    #[test]
    fn a_current_unit_is_left_alone() {
        assert_eq!(
            verdict_for(Some(&v("0.4.0")), &v("0.4.0"), false),
            Verdict::Current
        );
    }

    /// Write what a daemon would have published, so the reader has a real file to read.
    ///
    /// Constructed rather than produced by `publish_identity`, which publishes *this* process — and
    /// the test binary's own exe path names no release, so every unit would come back `Unknown` and
    /// the test would pass while asserting nothing.
    fn publish(root: &std::path::Path, service: &str, release: &str) {
        let dir = root.join(service);
        std::fs::create_dir_all(&dir).expect("a runtime dir");
        let identity = proto::Identity {
            service: service.to_owned(),
            version: release.to_owned(),
            revision: None,
            built_at: None,
            exe: Some(format!(
                "/opt/robot/daemon/releases/{release}/bin/{service}"
            )),
            pid: 4242,
        };
        std::fs::write(
            dir.join("identity.json"),
            serde_json::to_vec(&identity).expect("serialising an identity"),
        )
        .expect("publishing");
    }

    /// A `systemctl` that records every call and refuses one named unit, so both the acting path and
    /// the failure path are exercised by the same run.
    fn stub_systemctl(dir: &std::path::Path, failing_unit: &str) -> std::path::PathBuf {
        let path = dir.join("systemctl");
        std::fs::write(
            &path,
            format!(
                "#!/bin/sh\n\
                 echo \"$@\" >> \"$(dirname \"$0\")/calls\"\n\
                 [ \"$2\" = {failing_unit} ] && {{ echo 'job failed' >&2; exit 1; }}\n\
                 exit 0\n"
            ),
        )
        .expect("write stub");
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o755)).unwrap();
        }
        path
    }

    fn verdict_of(findings: &[Finding], unit: &str) -> Verdict {
        findings
            .iter()
            .find(|f| f.unit == unit)
            .unwrap_or_else(|| panic!("no finding for {unit}: {findings:?}"))
            .verdict
    }

    /// The whole function, over real files and a real subprocess — every verdict in one run.
    ///
    /// **One test rather than five, and that is about the environment variable rather than about
    /// taste.** `DUCK_RUNTIME_DIR` is process-wide, so two tests setting it would race inside one
    /// test binary and the loser would read the other's runtime directory. Driving every case through
    /// a single root sidesteps that entirely, and costs only that the failures name a unit.
    ///
    /// Until this existed the module's tests covered `verdict_for` and nothing else — so what a
    /// startup actually *did* about a stale unit, which is the point of the module, was unobserved.
    #[tokio::test]
    async fn every_verdict_over_real_files() {
        let root = tempfile::tempdir().expect("a temp runtime root");
        let bin = tempfile::tempdir().expect("a temp bin dir");
        // SAFETY: set once, in a single test, and nothing else in this crate reads the variable.
        unsafe { std::env::set_var("DUCK_RUNTIME_DIR", root.path()) };

        let active = v("0.4.0");
        publish(root.path(), "configd", "0.3.0"); // stale → restarted
        publish(root.path(), "robotd", "0.4.0"); // already right → untouched
        publish(root.path(), "updaterd", "0.3.0"); // stale, but is self → reported only
        publish(root.path(), "btd", "0.3.0"); // stale, and its restart fails
        // `padd` publishes nothing: stopped, or a build too old to say. Left alone either way.

        let systemctl = stub_systemctl(bin.path(), "btd");
        let units = ["btd", "configd", "padd", "robotd", "updaterd"]
            .map(str::to_owned)
            .to_vec();

        let findings = check(
            systemctl.to_str().unwrap(),
            &active,
            "updaterd",
            units.clone(),
        )
        .await;

        assert_eq!(verdict_of(&findings, "configd"), Verdict::Restarted);
        assert_eq!(verdict_of(&findings, "robotd"), Verdict::Current);
        assert_eq!(verdict_of(&findings, "updaterd"), Verdict::ReportedOnly);
        assert_eq!(verdict_of(&findings, "btd"), Verdict::RestartFailed);
        assert_eq!(verdict_of(&findings, "padd"), Verdict::Unknown);

        // And what it actually asked systemd to do, which no assertion on verdicts can show.
        let calls = std::fs::read_to_string(bin.path().join("calls")).unwrap_or_default();
        assert!(calls.contains("restart configd"), "{calls}");
        assert!(calls.contains("restart btd"), "{calls}");
        // The three that must never be touched: the one that is current, the one that published
        // nothing, and — most importantly — this process's own unit.
        assert!(!calls.contains("restart robotd"), "{calls}");
        assert!(!calls.contains("restart padd"), "{calls}");
        assert!(!calls.contains("restart updaterd"), "{calls}");

        // And the observing half, over the same files, because it has to agree with the above on what
        // stale means while disagreeing on what to do about it. `updaterd` is in this list precisely
        // where it is absent from the calls: the caller schedules that restart instead of running it,
        // and a `stale_units` that hid it would leave the one skew nothing else repairs unreported.
        let stale = stale_units(&active, &units);
        assert_eq!(stale, ["btd", "configd", "updaterd"], "{stale:?}");
    }
}

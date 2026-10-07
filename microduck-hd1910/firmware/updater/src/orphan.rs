//! Would this release leave an installed unit with nothing to exec?
//!
//! `hooks/postinstall` installs the units a release ships and, by design, leaves them behind on a
//! rollback: the next successful update reinstalls whatever it ships, so recording what was added
//! is not worth it. That reasoning holds for a rollback and stops holding for a **downgrade to a
//! release that predates a daemon**. The unit stays, its `ExecStart` names a binary the older
//! release does not contain, and systemd fails it with `203/EXEC`. Since that daemon is also in the
//! derived restart set, the failed restart fails the *update*, which reverts.
//!
//! Observed exactly that way: `apply daemon` on a board running a dev build resolved to stable
//! `0.2.0`, which predates `configd`; `configd.service` could not start; the engine rolled back and
//! said so. The outcome was right and the diagnosis was a systemd error code — nothing named the
//! cause, and nothing *stated* the rule that a board should not silently drop below the release
//! that introduced a daemon it is running. This states it.
//!
//! ## What it reads, and why the live directory
//!
//! `/etc/systemd/system/*.service`, filtered to units whose `Exec*=` points into the component's
//! `current` symlink. Both halves matter. The live directory is the only place the orphan appears —
//! it outlived the release that installed it, so the previous release's `systemd/` cannot name it
//! by construction. And the filter is what keeps out units no release of ours ever shipped, put
//! there by hand or by an unrelated package, which is the objection to reading the live directory
//! at all.
//!
//! ## Failing open
//!
//! A unit whose file cannot be read, or whose `Exec*=` this cannot resolve to a path under
//! `current`, produces no finding. The cost of a false negative is the `203/EXEC` rollback that
//! happens today; the cost of a false positive is refusing an update over a unit file this parser
//! merely did not understand — and refusing updates is the one thing the update system may not do
//! wrongly.
//!
//! ## Where it is not
//!
//! Not in `preflight`, which cannot see the candidate's file list: both passes run before the
//! artifact is downloaded. The engine runs this after extraction and before the swap, where the
//! files exist and staging is still disposable — see [`crate::engine`].
//!
//! Not on rollback, reset-to-golden or `select` either, and that is deliberate rather than
//! unfinished. Those paths move backwards on purpose, they are how a board gets off a bad release,
//! and a check that can refuse must never sit in the recovery path (`docs/design/architecture.md`
//! §1.1). Rolling back onto an orphaned unit is the documented behaviour of `hooks/postinstall`,
//! and it is self-correcting: the next update that ships the unit reinstalls it.

use std::path::{Path, PathBuf};

/// An installed unit the candidate release would leave with nothing to exec.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Orphan {
    /// As systemd knows it: `configd.service`.
    pub unit: String,
    /// The unit file itself, so the refusal can name the thing to remove.
    pub path: PathBuf,
    /// What it execs, relative to a release root: `bin/configd`.
    pub missing: String,
}

/// Every installed unit that execs something this candidate does not contain.
///
/// `unit_dir` and `current` are parameters rather than constants for the reason `systemctl` is one
/// in [`crate::engine`]: a test needs to hand it a directory it controls. On a board they are
/// always `/etc/systemd/system` and the component's `current` symlink.
///
/// One finding per unit — the first missing path. A unit with two broken execs is one broken unit,
/// and the operator's move is the same either way.
pub fn would_orphan(unit_dir: &Path, current: &Path, candidate_root: &Path) -> Vec<Orphan> {
    let Ok(entries) = std::fs::read_dir(unit_dir) else {
        // No unit directory at all: a container, a test box, a dev laptop. Nothing to orphan.
        return Vec::new();
    };

    let mut files: Vec<PathBuf> = entries
        .flatten()
        .map(|e| e.path())
        .filter(|p| p.extension().and_then(|e| e.to_str()) == Some("service"))
        .collect();
    // Sorted so a board with several orphans reports them in the same order every time.
    files.sort();

    let mut orphans = Vec::new();
    for path in files {
        let Ok(text) = std::fs::read_to_string(&path) else {
            continue;
        };
        let Some(name) = path.file_name().and_then(|n| n.to_str()) else {
            continue;
        };

        if let Some(missing) = execs_under(&text, current)
            .into_iter()
            .find(|rel| !candidate_root.join(rel).exists())
        {
            orphans.push(Orphan {
                unit: name.to_owned(),
                path: path.clone(),
                missing,
            });
        }
    }

    orphans
}

/// The paths a unit execs from inside `current`, relative to the release root.
///
/// Every `Exec*=` directive, not `ExecStart` alone: an `ExecStartPre` naming a missing binary fails
/// the unit in exactly the same way, and it is the same parse.
pub fn execs_under(unit: &str, current: &Path) -> Vec<String> {
    let prefix = format!("{}/", current.display());

    logical_lines(unit)
        .iter()
        .filter_map(|line| {
            let (key, value) = line.split_once('=')?;
            if !key.trim().starts_with("Exec") {
                return None;
            }
            let path = exec_path(value)?;
            let rel = path.strip_prefix(&prefix)?;
            (!rel.is_empty()).then(|| rel.to_owned())
        })
        .collect()
}

/// Unit-file lines with systemd's `\` continuations joined.
///
/// Not a nicety: `updaterd.service` writes its own `ExecStart` across three lines, so a
/// line-at-a-time parse reads a truncated command. It gets the right answer there by luck — the
/// binary is on the first line — and would not on a unit that wrapped anywhere else.
fn logical_lines(text: &str) -> Vec<String> {
    let mut lines = Vec::new();
    let mut pending = String::new();

    for raw in text.lines() {
        let piece = raw.trim();
        if !pending.is_empty() {
            // A continuation: its indentation is layout, and joining without a separator would
            // glue the last word of one line to the first of the next.
            pending.push(' ');
        }

        match piece.strip_suffix('\\') {
            Some(head) => pending.push_str(head.trim_end()),
            None => {
                pending.push_str(piece);
                lines.push(std::mem::take(&mut pending));
            }
        }
    }

    // A file ending mid-continuation. Malformed, but systemd would still read the command.
    if !pending.is_empty() {
        lines.push(pending);
    }

    lines
}

/// The executable an `Exec*=` value names, before its arguments.
///
/// `None` for a value this cannot resolve, which includes the bare `ExecStart=` that resets the
/// list. See the module's note on failing open.
fn exec_path(value: &str) -> Option<String> {
    // systemd's prefix characters — `@ - : + ! !!` — in any order and repeatable.
    let mut rest = value.trim();
    while let Some(stripped) = rest.strip_prefix(['@', '-', ':', '+', '!']) {
        rest = stripped.trim_start();
    }

    let token = match rest.strip_prefix('"') {
        Some(quoted) => quoted.split('"').next()?,
        None => rest.split_whitespace().next()?,
    };

    (!token.is_empty()).then(|| token.to_owned())
}

/// What the operator is told, and what to do about it.
///
/// The remedy is the load-bearing half. Without it this is a refusal whose way past is not
/// guessable from the board, which is worse than the `203/EXEC` rollback it replaces. And it is
/// deliberately *not* a new `--force` flag: removing the unit is what the operator actually means —
/// a board downgraded below the release that introduced a daemon should not be running that daemon
/// — so it makes the situation true rather than overriding a check that says it is not. The next
/// update that ships the unit reinstalls it, so nothing is lost by removing it.
///
/// The same move `install --force` and `systemctl stop robotd` already make elsewhere: an existing
/// mechanism, named in the message, rather than a flag that exists to be typed.
pub fn refusal(version: &semver::Version, orphans: &[Orphan]) -> String {
    let listed = orphans
        .iter()
        .map(|o| format!("  {} execs {}", o.unit, o.missing))
        .collect::<Vec<_>>()
        .join("\n");

    let remedy = orphans
        .iter()
        .map(|o| {
            format!(
                "  systemctl disable --now {} && rm {}",
                o.unit,
                o.path.display()
            )
        })
        .collect::<Vec<_>>()
        .join("\n");

    format!(
        "{version} does not contain a binary that an installed unit runs:\n\
         {listed}\n\
         That unit would fail with 203/EXEC after the swap, its failed restart would fail the \
         update, and the update would roll back — so it is refused now, while nothing has moved. \
         This is the ordinary shape of a downgrade past the release that introduced a daemon; the \
         release being installed is not broken. To install it anyway, remove the unit that would \
         be orphaned:\n{remedy}"
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    fn current() -> PathBuf {
        PathBuf::from("/opt/robot/daemon/current")
    }

    /// The plain case, and the one every unit in this repo is written as.
    #[test]
    fn an_execstart_into_current_is_relative_to_the_release() {
        let unit = "[Service]\nExecStart=/opt/robot/daemon/current/bin/configd --allow-user btd\n";
        assert_eq!(execs_under(unit, &current()), ["bin/configd"]);
    }

    /// `updaterd.service` is written this way today. A line-at-a-time parser gets the right answer
    /// here by accident — the binary is on the first line — and the accident is the point: nothing
    /// stops the next unit from wrapping before its path.
    #[test]
    fn a_continued_execstart_is_one_command() {
        let unit = "[Service]\n\
                    ExecStart=/opt/robot/daemon/current/bin/updaterd \\\n\
                    \x20   --config /etc/robot/updater.toml \\\n\
                    \x20   --socket /run/updaterd.sock\n";
        assert_eq!(execs_under(unit, &current()), ["bin/updaterd"]);
    }

    /// Every `Exec*=`, because a missing `ExecStartPre` fails the unit just as thoroughly.
    #[test]
    fn every_exec_directive_counts_not_only_execstart() {
        let unit = "[Service]\n\
                    ExecStartPre=-/opt/robot/daemon/current/bin/migrate\n\
                    ExecStart=@/opt/robot/daemon/current/bin/robotd argv0\n\
                    ExecStopPost=!/opt/robot/daemon/current/bin/cleanup\n";
        assert_eq!(
            execs_under(unit, &current()),
            ["bin/migrate", "bin/robotd", "bin/cleanup"]
        );
    }

    /// Anything not under `current` belongs to someone else. Reading the live unit directory is
    /// only defensible because of this line.
    #[test]
    fn units_pointing_outside_the_release_are_not_ours() {
        let unit = "[Unit]\n\
                    Documentation=file:///opt/robot/daemon/current/docs/architecture.md\n\
                    [Service]\n\
                    ExecStart=/usr/bin/sshd -D\n\
                    ExecStart=/opt/robot/other-component/current/bin/thing\n";
        assert!(execs_under(unit, &current()).is_empty());
    }

    /// Failing open, in the two shapes it arrives in: a reset directive, and a value with no path.
    #[test]
    fn a_value_with_no_path_yields_nothing() {
        assert_eq!(exec_path(""), None);
        assert_eq!(exec_path("  -@ "), None);
        assert_eq!(
            exec_path("\"/opt/robot/daemon/current/bin/a b\" --flag").as_deref(),
            Some("/opt/robot/daemon/current/bin/a b")
        );
    }

    fn write_unit(dir: &Path, name: &str, exec: &str) {
        std::fs::write(
            dir.join(name),
            format!("[Service]\nExecStart={exec}\n[Install]\nWantedBy=multi-user.target\n"),
        )
        .expect("writing a unit");
    }

    /// The whole scan over real files: one unit the candidate can run, one it cannot, one that is
    /// not ours, and one that is not a unit file at all.
    #[test]
    fn only_units_the_candidate_cannot_run_are_reported() {
        let dir = tempfile::tempdir().expect("a temp unit dir");
        let candidate = tempfile::tempdir().expect("a temp release root");
        std::fs::create_dir_all(candidate.path().join("bin")).unwrap();
        std::fs::write(candidate.path().join("bin/robotd"), b"elf").unwrap();

        write_unit(
            dir.path(),
            "robotd.service",
            "/opt/robot/daemon/current/bin/robotd",
        );
        write_unit(
            dir.path(),
            "configd.service",
            "/opt/robot/daemon/current/bin/configd",
        );
        write_unit(dir.path(), "sshd.service", "/usr/sbin/sshd -D");
        std::fs::write(dir.path().join("notes.txt"), "not a unit").unwrap();

        let found = would_orphan(dir.path(), &current(), candidate.path());

        assert_eq!(found.len(), 1, "{found:?}");
        assert_eq!(found[0].unit, "configd.service");
        assert_eq!(found[0].missing, "bin/configd");
    }

    /// A board with no `/etc/systemd/system` must not be an update failure — that is every
    /// container and every dev laptop this code also runs on.
    #[test]
    fn no_unit_directory_is_not_a_finding() {
        let candidate = tempfile::tempdir().expect("a temp release root");
        let missing = candidate.path().join("nowhere");
        assert!(would_orphan(&missing, &current(), candidate.path()).is_empty());
    }

    /// The refusal has to carry the way past it, or this is a bricked update path on a board where
    /// the remedy is not guessable.
    #[test]
    fn the_refusal_names_the_unit_the_binary_and_the_way_past() {
        let text = refusal(
            &semver::Version::parse("0.2.0").unwrap(),
            &[Orphan {
                unit: "configd.service".into(),
                path: "/etc/systemd/system/configd.service".into(),
                missing: "bin/configd".into(),
            }],
        );

        assert!(text.contains("0.2.0"), "{text}");
        assert!(text.contains("configd.service execs bin/configd"), "{text}");
        assert!(
            text.contains("systemctl disable --now configd.service"),
            "{text}"
        );
        assert!(
            text.contains("rm /etc/systemd/system/configd.service"),
            "{text}"
        );
    }
}

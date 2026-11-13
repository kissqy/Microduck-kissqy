//! The sideload directory and the unit that has to read it, checked against each other.
//!
//! `scripts/dev-push.sh` copies a release onto the board and `updaterd` installs it. Those two
//! agree about the path by convention, and one of the ways they can disagree is invisible from
//! either side alone: `updaterd.service` sets `PrivateTmp=yes`, which gives the unit its own
//! `/tmp` **and** its own `/var/tmp`, so a directory under either is not the one the daemon reads.
//! The push succeeds, every file is demonstrably in place, and the apply fails with "no manifest
//! for version ... in /var/tmp/duck-sideload" — a sentence that cannot be reconciled with `ls`.
//!
//! `updater/src/preflight.rs` makes that failure say so when it happens. This file is the other
//! half: the default path must not be one the unit hides in the first place. Neither file can
//! check it — the script does not read the unit, the unit does not know the script — so it is
//! checked here, where the whole repository is readable.

use std::path::{Path, PathBuf};

const SCRIPT: &str = "scripts/dev-push.sh";
const UNIT: &str = "updater/systemd/updaterd.service";

/// Paths a `PrivateTmp=yes` unit gets a private copy of, and therefore cannot be sideloaded from.
const PRIVATE: [&str; 2] = ["/tmp/", "/var/tmp/"];

fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("xtask/ has a parent")
        .to_path_buf()
}

fn read(rel: &str) -> String {
    std::fs::read_to_string(root().join(rel)).unwrap_or_else(|e| panic!("{rel}: {e}"))
}

/// The file with `#` comments removed, so an explanation of why a path is *not* used does not
/// read as a use of it — the reason for that comment is the bug this file exists to hold shut.
///
/// Cuts at the first `#`, which is wrong for a `#` inside quotes. The only such line here is a
/// `sed` expression with no path in it, and a mangled line can at worst hide a match, which the
/// assertions below would report as a pass — so the failure mode is a weaker test, never a false
/// alarm.
fn code(text: &str) -> String {
    text.lines()
        .map(|l| l.split_once('#').map_or(l, |(before, _)| before))
        .collect::<Vec<_>>()
        .join("\n")
}

/// A `KEY=VALUE` directive from a unit file, last assignment winning as systemd does.
fn directive(unit: &str, key: &str) -> Option<String> {
    unit.lines()
        .map(str::trim)
        .filter(|l| !l.starts_with('#'))
        .filter_map(|l| l.split_once('='))
        .filter(|(k, _)| k.trim() == key)
        .map(|(_, v)| v.trim().to_owned())
        .next_back()
}

fn privatises_tmp() -> bool {
    matches!(
        directive(&read(UNIT), "PrivateTmp").as_deref(),
        Some("yes" | "true" | "on" | "1")
    )
}

/// The push must not put a release where the daemon cannot see it.
#[test]
fn the_sideload_path_is_not_one_private_tmp_hides() {
    if !privatises_tmp() {
        return;
    }

    let script = code(&read(SCRIPT));
    for hidden in PRIVATE {
        assert!(
            !script.contains(hidden),
            "{SCRIPT} names {hidden} while {UNIT} sets PrivateTmp=yes, so `updaterd` would read \
             its own copy of that directory and find nothing there. Either put the release \
             somewhere outside {PRIVATE:?}, or drop PrivateTmp from the unit."
        );
    }
}

/// And the home directory it uses instead has to stay reachable.
///
/// `ProtectHome=` would hide it exactly as `PrivateTmp=` hides `/var/tmp` — same failure, same
/// unreadable error, and adding one line of hardening to the unit is all it would take.
#[test]
fn a_home_sideload_path_requires_no_protect_home() {
    let script = code(&read(SCRIPT));
    if !script.contains("$HOME/duck-sideload") {
        return;
    }

    match directive(&read(UNIT), "ProtectHome").as_deref() {
        None | Some("no" | "false" | "off" | "0") => {}
        Some(other) => panic!(
            "{UNIT} sets ProtectHome={other}, and {SCRIPT} sideloads from a home directory — \
             `updaterd` cannot read it, and `apply --from` will fail with a path that is \
             plainly there. Move the sideload directory, or leave ProtectHome unset."
        ),
    }
}

/// The whole reason the path moved: the daemon reads it, so it has to exist for the daemon.
///
/// Named here rather than left implicit because both tests above are conditional, and a
/// conditional test that stops applying is indistinguishable from one that passes.
#[test]
fn the_unit_still_privatises_tmp_or_this_file_is_moot() {
    assert!(
        privatises_tmp() || code(&read(SCRIPT)).contains("$HOME/duck-sideload"),
        "{UNIT} no longer sets PrivateTmp=yes and {SCRIPT} no longer sideloads from a home \
         directory: nothing above is asserting anything. Delete this file, or restore one half."
    );
}

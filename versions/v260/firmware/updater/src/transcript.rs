//! Per-run update transcripts — what `updaterd` actually did, kept where it survives.
//!
//! The update log (`crate::journal`) records that an attempt happened and how it ended. This
//! records what it *did*: every phase boundary, the manifest it verified, the hook output it
//! collected, the units it restarted, the gate's verdict. One file per run, in `state_dir`
//! beside the log and under the same rule — outside every component's `install_dir`, so a
//! symlink swap or a rollback cannot destroy the account of the swap or the rollback
//! (`docs/design/updater-design.md` §5.7, §8.3).
//!
//! **Why not the journal.** `updaterd` already logs its notable events there, and for watching
//! an update happen that is the better place — `journalctl -f` needs no new machinery. But
//! `/var/log` on this board is a zram device (`deploy/README.md`), so `Storage=persistent` buys
//! survival of a clean reboot and not of a power cut, and the updates anyone needs a transcript
//! for are disproportionately the ones that end in a power cut. The same argument put the update
//! log here in the first place; this is its second application, not a new one.
//!
//! **Recording never fails an update.** Every write here is best-effort and reports failure to
//! the journal, because an update that completed and lost its diary is strictly better than one
//! that was abandoned to keep the diary honest — the same direction `crate::engine`'s log writes
//! already fail in.

use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::Mutex;

use crate::Error;
use crate::journal::now_unix;
use crate::proto::{ComponentId, RunEvent, RunRecord};

/// Directory holding the run files, under `state_dir`.
const RUNS_DIR: &str = "runs";

/// Most events one run may record.
///
/// A backstop against a hook in a retry loop, not a budget anyone should reach: a daemon update
/// records on the order of twenty.
const MAX_EVENTS: u64 = 4_000;

/// Most bytes one run's file may reach.
const MAX_BYTES: u64 = 2 * 1024 * 1024;

/// Longest single string — hook output, mostly — kept in one event.
///
/// Clamped rather than counted against the file cap alone, so one talkative hook cannot push
/// every later event out of a run it did not fail.
const MAX_TEXT: usize = 64 * 1024;

/// An open transcript, being appended to as a run proceeds.
pub struct Transcript {
    path: PathBuf,
    id: u64,
    caps: Mutex<Caps>,
}

#[derive(Default)]
struct Caps {
    events: u64,
    bytes: u64,
    /// Set once a cap trips. Everything after is counted and discarded, except the ending.
    stopped: bool,
    dropped: u64,
}

impl Transcript {
    /// Open the next run.
    ///
    /// The id is one past the highest on disk, so it is short, sortable and typable —
    /// `robotctl update show 42`. Held under the update lock by every caller, so "read the
    /// highest, add one" cannot race: `crate::engine::Engine::apply` acquires it before this
    /// runs.
    pub fn begin(state_dir: &Path, max_runs: usize) -> Result<Self, Error> {
        let dir = state_dir.join(RUNS_DIR);
        std::fs::create_dir_all(&dir).map_err(|e| Error::Io {
            path: dir.clone(),
            source: e,
        })?;

        let existing = ids_in(&dir);
        let id = existing.last().copied().unwrap_or(0) + 1;

        // Trim before writing, so a board that has been updating for years holds `max_runs`
        // files and not one more. `saturating_sub` because `max_runs` may exceed what is there.
        let excess = (existing.len() + 1).saturating_sub(max_runs.max(1));
        for old in existing.iter().take(excess) {
            let path = run_path(&dir, *old);
            if let Err(e) = std::fs::remove_file(&path) {
                tracing::warn!(path = %path.display(), error = %e, "could not prune an old transcript");
            }
        }

        // Created empty, here, rather than left to the first event.
        //
        // The id is "one past the highest file on disk", so a run that records nothing would not
        // claim its number and the next run would reuse it — and an entry in the update log would
        // then point at somebody else's transcript. Claiming it costs one `open`.
        let path = run_path(&dir, id);
        if let Err(source) = std::fs::File::create(&path) {
            return Err(Error::Io { path, source });
        }

        Ok(Self {
            path,
            id,
            caps: Mutex::new(Caps::default()),
        })
    }

    pub fn id(&self) -> u64 {
        self.id
    }

    /// Append one event. Never fails; a write that cannot happen is a journal warning.
    pub fn record(&self, event: RunEvent) {
        let ending = matches!(event, RunEvent::Ended { .. });
        let event = clamp(event);

        let mut caps = self.caps.lock().unwrap_or_else(|e| e.into_inner());

        // The ending is always recorded, cap or no cap. It is small, bounded, and the single
        // most useful line in the file — dropping it to respect a limit the run had already
        // blown would leave a transcript that reads as a run which never finished.
        if caps.stopped && !ending {
            caps.dropped += 1;
            return;
        }
        if ending && caps.dropped > 0 {
            let dropped = caps.dropped;
            self.append(&mut caps, RunEvent::Truncated { dropped }, true);
        }

        self.append(&mut caps, event, ending);
    }

    fn append(&self, caps: &mut Caps, event: RunEvent, exempt: bool) {
        let record = RunRecord {
            at: now_unix(),
            event,
        };
        let mut line = match serde_json::to_vec(&record) {
            Ok(line) => line,
            Err(e) => {
                tracing::warn!(error = %e, "could not serialise a transcript event");
                return;
            }
        };
        line.push(b'\n');

        if !exempt && (caps.events + 1 > MAX_EVENTS || caps.bytes + line.len() as u64 > MAX_BYTES) {
            caps.stopped = true;
            caps.dropped += 1;
            return;
        }

        if let Err(e) = self.write(&line) {
            // Once, not per event: a full or read-only `/var` would otherwise put one warning
            // in the journal for every phase of every update from here on.
            if !caps.stopped {
                tracing::warn!(path = %self.path.display(), error = %e, "could not write the update transcript");
            }
            caps.stopped = true;
            return;
        }
        caps.events += 1;
        caps.bytes += line.len() as u64;
    }

    /// `sync_data` per line, like the update log, and for the same reason: the failure this file
    /// exists to explain is one that can take the power with it.
    fn write(&self, line: &[u8]) -> std::io::Result<()> {
        let mut file = std::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.path)?;
        file.write_all(line)?;
        file.sync_data()
    }

    /// Every run still on disk, oldest first.
    pub fn ids(state_dir: &Path) -> Vec<u64> {
        ids_in(&state_dir.join(RUNS_DIR))
    }

    /// One run's events, oldest first.
    ///
    /// A line that will not parse is skipped, not fatal: the last one can be torn by a power cut
    /// mid-append, and refusing to show a run because its final line is half-written would fail
    /// at exactly the moment the file matters most.
    pub fn read(state_dir: &Path, id: u64) -> Result<Vec<RunRecord>, Error> {
        let path = run_path(&state_dir.join(RUNS_DIR), id);
        let text = match std::fs::read_to_string(&path) {
            Ok(text) => text,
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
                return Err(Error::NoSuchRun {
                    run: Some(id),
                    available: Self::ids(state_dir),
                    // Only the "most recent" case needs this; a named run that is missing is
                    // already answered by the range of the ones that are not.
                    earlier: 0,
                });
            }
            Err(source) => return Err(Error::Io { path, source }),
        };
        Ok(text
            .lines()
            .filter(|line| !line.trim().is_empty())
            .filter_map(|line| serde_json::from_str(line).ok())
            .collect())
    }

    /// Which component a run was about, from its own opening event.
    ///
    /// Read back rather than stored in the filename: one fact, one place. A run whose first line
    /// never made it to disk reports the component as unknown rather than refusing to render.
    pub fn component_of(events: &[RunRecord]) -> ComponentId {
        events
            .iter()
            .find_map(|record| match &record.event {
                RunEvent::Began { component, .. } => Some(component.clone()),
                _ => None,
            })
            .unwrap_or_else(|| ComponentId::new("unknown"))
    }
}

/// What to tell someone whose run is not here.
///
/// The runs kept are a contiguous window — ids only count up, and only the oldest are pruned — so
/// a range says everything a list would and stays one line at any retention.
pub fn no_such_run(run: Option<u64>, available: &[u64], earlier: usize) -> String {
    let Some(run) = run else {
        // Asked for the most recent and there is none. Not an error about a number they typed.
        return match earlier {
            0 => "no update has recorded a transcript on this board yet".to_owned(),
            // The once-per-board case. `update log` is full of updates and this says none
            // happened, so it has to say which of those two things it means.
            n => format!(
                "no transcripts on this board yet. The {n} attempt{} in `robotctl update log` \
                 ran under an updaterd that did not record them — a release cannot transcribe \
                 its own installation, because the one before it performs that. The next update \
                 will have one.",
                if n == 1 { "" } else { "s" }
            ),
        };
    };
    match (available.first(), available.last()) {
        (Some(first), Some(last)) if first == last => {
            format!("no transcript for run {run} on this board; run {first} is the only one kept")
        }
        (Some(first), Some(last)) => format!(
            "no transcript for run {run} on this board; runs {first} to {last} are kept, and \
             `robotctl update log` says what each one did"
        ),
        _ => format!("no transcript for run {run}; none are kept on this board"),
    }
}

fn run_path(dir: &Path, id: u64) -> PathBuf {
    // Zero-padded so `ls` sorts them the way they happened, which is how anyone poking at this
    // directory by hand will read it.
    dir.join(format!("{id:06}.jsonl"))
}

/// Run ids present in the directory, ascending. Anything not named like a run is ignored.
fn ids_in(dir: &Path) -> Vec<u64> {
    let Ok(entries) = std::fs::read_dir(dir) else {
        return Vec::new();
    };
    let mut ids: Vec<u64> = entries
        .flatten()
        .filter_map(|entry| {
            let name = entry.file_name();
            let name = name.to_str()?;
            name.strip_suffix(".jsonl")?.parse().ok()
        })
        .collect();
    ids.sort_unstable();
    ids
}

/// Keep one event's free text within [`MAX_TEXT`], saying so where it cut.
fn clamp(event: RunEvent) -> RunEvent {
    fn cut(text: String) -> String {
        if text.len() <= MAX_TEXT {
            return text;
        }
        // On a char boundary: hook output is whatever the hook printed, and splitting a UTF-8
        // sequence would make the line unparseable rather than merely shorter.
        let mut end = MAX_TEXT;
        while end > 0 && !text.is_char_boundary(end) {
            end -= 1;
        }
        let dropped = text.len() - end;
        let mut kept = text[..end].to_owned();
        kept.push_str(&format!("\n… {dropped} more bytes not recorded"));
        kept
    }

    match event {
        RunEvent::Hook {
            hook,
            exit_code,
            output,
        } => RunEvent::Hook {
            hook,
            exit_code,
            output: cut(output),
        },
        RunEvent::Note { text } => RunEvent::Note { text: cut(text) },
        other => other,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::proto::{Outcome, Phase};

    fn note(text: &str) -> RunEvent {
        RunEvent::Note {
            text: text.to_owned(),
        }
    }

    #[test]
    fn runs_are_numbered_from_one_and_upwards() {
        let dir = tempfile::tempdir().unwrap();
        assert_eq!(Transcript::begin(dir.path(), 10).unwrap().id(), 1);
        assert_eq!(Transcript::begin(dir.path(), 10).unwrap().id(), 2);
        assert_eq!(Transcript::begin(dir.path(), 10).unwrap().id(), 3);
    }

    #[test]
    fn events_read_back_in_the_order_they_happened() {
        let dir = tempfile::tempdir().unwrap();
        let run = Transcript::begin(dir.path(), 10).unwrap();
        run.record(note("first"));
        run.record(RunEvent::Phase {
            phase: Phase::Downloading,
            detail: None,
        });
        run.record(RunEvent::Ended {
            outcome: Some(Outcome::Success),
            summary: "applied 0.1.3 → 0.1.4".into(),
        });

        let events = Transcript::read(dir.path(), run.id()).unwrap();
        assert_eq!(events.len(), 3);
        assert_eq!(events[0].event, note("first"));
        assert!(matches!(events[2].event, RunEvent::Ended { .. }));
    }

    #[test]
    fn asking_for_a_run_that_never_existed_says_so() {
        let dir = tempfile::tempdir().unwrap();
        let message = Transcript::read(dir.path(), 99).unwrap_err().to_string();
        assert!(message.contains("run 99"), "{message}");
        assert!(message.contains("none are kept"), "{message}");

        // And with runs on disk it says which, because that is the caller's next move.
        Transcript::begin(dir.path(), 10).unwrap().record(note("x"));
        Transcript::begin(dir.path(), 10).unwrap().record(note("x"));
        let message = Transcript::read(dir.path(), 99).unwrap_err().to_string();
        assert!(message.contains("1 to 2"), "{message}");
    }

    /// The state every board passes through once: a log full of updates, and no transcripts,
    /// because the release that added them was installed by the release before it.
    #[test]
    fn no_transcripts_but_a_log_full_of_updates_says_which_it_means() {
        let fresh = no_such_run(None, &[], 0);
        assert_eq!(
            fresh,
            "no update has recorded a transcript on this board yet"
        );

        let upgraded = no_such_run(None, &[], 3);
        assert!(upgraded.contains("The 3 attempts"), "{upgraded}");
        assert!(upgraded.contains("next update will have one"), "{upgraded}");
        // Not "no update has happened", which is what the board is looking at a list of.
        assert!(!upgraded.contains("no update has"), "{upgraded}");

        assert!(no_such_run(None, &[], 1).contains("The 1 attempt in"));
    }

    /// The oldest runs are pruned, and the newest are the ones kept.
    #[test]
    fn only_the_last_few_runs_are_kept() {
        let dir = tempfile::tempdir().unwrap();
        for _ in 0..6 {
            let run = Transcript::begin(dir.path(), 3).unwrap();
            run.record(note("x"));
        }
        assert_eq!(Transcript::ids(dir.path()), vec![4, 5, 6]);
    }

    /// A half-written final line costs that line and nothing else.
    #[test]
    fn a_torn_last_line_does_not_lose_the_run() {
        let dir = tempfile::tempdir().unwrap();
        let run = Transcript::begin(dir.path(), 10).unwrap();
        run.record(note("intact"));
        let path = dir.path().join(RUNS_DIR).join("000001.jsonl");
        let mut text = std::fs::read_to_string(&path).unwrap();
        text.push_str(r#"{"at":2,"event":"note","tex"#);
        std::fs::write(&path, text).unwrap();

        let events = Transcript::read(dir.path(), 1).unwrap();
        assert_eq!(events.len(), 1);
        assert_eq!(events[0].event, note("intact"));
    }

    /// A hook that will not stop talking loses its tail, not the run's.
    #[test]
    fn a_huge_hook_output_is_cut_and_says_so() {
        let dir = tempfile::tempdir().unwrap();
        let run = Transcript::begin(dir.path(), 10).unwrap();
        run.record(RunEvent::Hook {
            hook: "pre-install".into(),
            exit_code: Some(0),
            output: "y".repeat(MAX_TEXT * 2),
        });
        run.record(RunEvent::Ended {
            outcome: Some(Outcome::Success),
            summary: "applied 0.1.3 → 0.1.4".into(),
        });

        let events = Transcript::read(dir.path(), 1).unwrap();
        let RunEvent::Hook { output, .. } = &events[0].event else {
            panic!("expected a hook event, got {:?}", events[0].event);
        };
        assert!(output.len() < MAX_TEXT + 100, "{}", output.len());
        assert!(output.ends_with("more bytes not recorded"), "{output:.80}");
        // The ending still made it, which is the whole point of clamping rather than stopping.
        assert!(matches!(events[1].event, RunEvent::Ended { .. }));
    }

    /// Past the event cap the run stops recording, says how much it dropped, and still ends.
    #[test]
    fn a_runaway_run_is_truncated_but_still_ends() {
        let dir = tempfile::tempdir().unwrap();
        let run = Transcript::begin(dir.path(), 10).unwrap();
        for i in 0..(MAX_EVENTS + 50) {
            run.record(note(&format!("{i}")));
        }
        run.record(RunEvent::Ended {
            outcome: Some(Outcome::Success),
            summary: "applied 0.1.3 → 0.1.4".into(),
        });

        let events = Transcript::read(dir.path(), 1).unwrap();
        let truncated = events
            .iter()
            .find_map(|record| match record.event {
                RunEvent::Truncated { dropped } => Some(dropped),
                _ => None,
            })
            .expect("a truncated run must say so");
        assert_eq!(truncated, 50);
        assert!(matches!(
            events.last().unwrap().event,
            RunEvent::Ended { .. }
        ));
    }

    #[test]
    fn a_run_knows_which_component_it_was_about() {
        let dir = tempfile::tempdir().unwrap();
        let run = Transcript::begin(dir.path(), 10).unwrap();
        run.record(RunEvent::Began {
            component: ComponentId::new("daemon"),
            target: "latest".into(),
            installed: None,
            source: "github".into(),
            requested_by: None,
        });
        let events = Transcript::read(dir.path(), 1).unwrap();
        assert_eq!(Transcript::component_of(&events).as_str(), "daemon");
    }
}

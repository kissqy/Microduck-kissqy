//! Spawning a child that the kernel may refuse to `exec` yet.
//!
//! One function, and the reason it exists is worth more than the code.

use std::time::Duration;

/// How many times to retry a spawn that fails with `ETXTBSY`, and how long to wait between.
///
/// Ten attempts over ~100 ms. The window this closes is the few microseconds between a
/// `fork` and the child's `execve`, so the first retry almost always succeeds; the budget
/// exists so a pathological case gives up rather than hanging an update.
const BUSY_RETRIES: u32 = 10;
const BUSY_BACKOFF: Duration = Duration::from_millis(10);

/// Spawn, retrying `ETXTBSY` — which is not a real failure here.
///
/// The kernel refuses to `exec` a file that *any* process has open for writing, tracked on the
/// inode. We extract a release — writing `hooks/preinstall` — and then exec it moments later, while
/// also spawning other children around the same time: the other hook, `systemctl` for `on_apply`, a
/// command-style health probe. A child inherits a duplicate of the whole fd table at fork and only
/// drops `O_CLOEXEC` descriptors at its own `execve`, so for a few microseconds some unrelated child
/// holds a write handle to the file we are about to run, and the exec fails with "Text file busy".
///
/// Left unhandled that is a failed hook, which fails the update, which rolls back a release that was
/// fine — rarely, unreproducibly, and reported on the robot as "failed at RunningPreHook" with
/// nothing anyone can act on. It first showed up as an intermittently red CI job, which is the same
/// bug wearing a costume.
///
/// Retrying is the remedy because nothing else addresses it: the offending descriptor belongs to a
/// *different* process, so closing or syncing ours changes nothing, and `rename` keeps the same
/// inode.
///
/// **Every spawn in this crate goes through here, including ones whose program we never write.**
/// `systemctl` is not a file the updater rewrites, so on a board it cannot be busy for this reason —
/// but the test suite writes stub `systemctl` scripts and executes them from parallel threads of one
/// process, which is the same race with the same cause, and it failed a pull request that had touched
/// nothing but documentation. A spawn helper that some callers skip is a helper that will be skipped
/// by the next caller too.
pub(crate) async fn retrying_busy(
    command: &mut tokio::process::Command,
) -> std::io::Result<tokio::process::Child> {
    for attempt in 1..=BUSY_RETRIES {
        match command.spawn() {
            Ok(child) => {
                if attempt > 1 {
                    tracing::debug!(attempt, "spawned after ETXTBSY");
                }
                return Ok(child);
            }
            // `raw_os_error`, not `kind`: ETXTBSY has no stable `ErrorKind` — it maps to
            // `Uncategorized`, which is unstable to match on.
            Err(e) if e.raw_os_error() == Some(libc::ETXTBSY) && attempt < BUSY_RETRIES => {
                tracing::debug!(attempt, "busy for exec; retrying");
                tokio::time::sleep(BUSY_BACKOFF).await;
            }
            Err(e) => return Err(e),
        }
    }
    unreachable!("the loop returns on the final attempt")
}

#[cfg(test)]
mod tests {
    /// Nothing in this crate may spawn a process except through [`retrying_busy`].
    ///
    /// The doc above claims every spawn goes through here, and a claim in a comment is exactly what
    /// drifted: `hooks.rs` had the retry, `engine.rs` did not, and the paragraph explaining the race
    /// already named `systemctl` as one of the processes causing it. What that cost was an
    /// intermittently red `check` job — including on a pull request that changed only documentation —
    /// and, on a board, an `ETXTBSY` from `self_test_updaterd` rolling back a release that was fine.
    ///
    /// A source grep rather than a type: `tokio::process::Command` is not ours to seal, and a
    /// newtype wrapping it would have to re-export every builder method to be worth anything.
    #[test]
    fn every_spawn_in_the_crate_goes_through_the_retry() {
        let src = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("src");
        let mut offenders = Vec::new();

        let mut dirs = vec![src.clone()];
        while let Some(dir) = dirs.pop() {
            for entry in std::fs::read_dir(&dir).expect("readable src dir").flatten() {
                let path = entry.path();
                if path.is_dir() {
                    dirs.push(path);
                    continue;
                }
                if path.extension().is_some_and(|e| e == "rs")
                    && path.file_name().is_some_and(|n| n != "spawn.rs")
                {
                    let text = std::fs::read_to_string(&path).expect("readable source");
                    // Only files that build a `Command`, which is what makes the three method names
                    // below unambiguous: `engine.status().await` is the engine's own status, and
                    // `response.status()` is HTTP's. A file that spawns has to name `Command` to do
                    // it, so nothing escapes by being new.
                    if !text.contains("tokio::process::Command") {
                        continue;
                    }
                    for (n, line) in text.lines().enumerate() {
                        let spawns = line.contains(".output()")
                            || line.contains(".spawn()")
                            || line.contains(".status().await");
                        if spawns {
                            let name = path.strip_prefix(&src).unwrap_or(&path).display();
                            offenders.push(format!("{name}:{} {}", n + 1, line.trim()));
                        }
                    }
                }
            }
        }

        assert!(
            offenders.is_empty(),
            "spawn a child with `spawn::retrying_busy(&mut command)` and then `wait()` or \
             `wait_with_output()`, rather than `output()`/`status()`/`spawn()` — see the module \
             docs for what the kernel does otherwise. Offenders:\n{}",
            offenders.join("\n")
        );
    }
}

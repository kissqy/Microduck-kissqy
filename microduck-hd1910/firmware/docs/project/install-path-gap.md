# The install path had no test

Status: closed · Date: 2026-08-05, revised 2026-08-07 and 2026-08-11 · Owner: pierre

Four bugs in a row reached a board, all in the install path, none caught by 418 tests or by
`board-test.sh`. This records why, and what closed it. The general rule this taught — anything a
fresh install does to a board belongs in a hook too, because that is the only thing that runs on
every board on every update — outgrew this document and now lives in `updater-design.md` §9.1.
**That is where to read it; this page is the story, not the rule.** It has been got wrong twice
more since, so §9.1 is worth reading before adding an install step rather than after. Written the
same day, while the reasons were still concrete, and kept in the past tense it has earned rather
than rewritten as reference — what it is useful for now is the shape of the mistake, not the state
of the tree.

A second section covers two findings that *look* like the same thing and are not: version skew
between a daemon that is already running and a release that has just been installed. Neither would
be caught by any amount of install testing, and they need their own fixes — kept here rather than in
their own document because anyone investigating one will arrive believing it is the other.

**Revision note.** All four bugs are fixed, and so is the version-skew section that follows them:
case 1's `serde(default)` discipline landed, case 2's handshake proposal was decided *against* with
its reasoning written down, and the "units outlive the release that installed them" consequence is
now a refusal rather than emergent behaviour.

**And the gap the title named is closed.** A test installs a real artifact — `board-test.sh` unpacks
one and runs `install.sh` and `hooks/postinstall` against it — every unit's `ExecStart` binary is
checked against the tarball that shipped it, a board check runs on every `dev-push.sh`, and
`scripts/systemd-test.sh` drives a real update against real systemd. The plan those came from is
below, with what each one turned up; two engine bugs were found by the last of them.

One change since the first draft moves enough of this document to call out here: `updaterd` and
`btd` are now restarted a few seconds *after* the update replies (`RESTART_AFTER_REPLYING`), and the
release's own `updaterd` is proved to start before the commit (`updaterd --self-test`). Two claims
below were written against the old behaviour and are now false — both are corrected in place, and
the second section's premise in particular no longer holds.

**Second revision note.** The skew half of §4 is now closed by code rather than by argument. Every
daemon publishes what it is running (`duck_ipc_proto::publish_identity`), and `updaterd` compares each
unit against the active release at every start and restarts what is stale
(`updater/src/reconcile.rs`, `Engine::reconcile_running_units`). Two more claims below were true when
written and are not now: that a running/installed mismatch is undecided, and that `btd`'s running
revision cannot be read. Both are corrected in place. `docs/design/restart-order.md` §5 and §7 own
the mechanism and how to read a skew; what stays here is why it was needed.

## What got through

All four landed within a day, all while installing `btd` and `configd` onto a dev board. (The count
read "three" until §4 was added below it.)

**1. `on_apply` restarts several units in one command.** `systemctl restart robotd configd` fails as
a whole if *either* unit is unknown — and fails without restarting the one that exists. A release
introducing a new daemon therefore could not restart anything, because the unit file arrives *with*
that release and nothing installed it. The rollback reason was
`not healthy within 30s: unreachable`, which names neither the unit nor the command.

Latent rather than fatal, since a board keeps its own `/etc/robot/updater.toml`.

Fixed twice, and the second one is the real fix. First, defensively: units are restarted one at a
time and a unit systemd does not know is skipped. Then properly: **`hooks/postinstall` installs the
release's units.** The engine has always had a post-install hook point — `extract → [pre_install] →
swap → [post_install] → apply → health gate` — which runs after `current` moves, so `ExecStart`
resolves, and before the restart, so `on_apply` finds a unit that exists. Nothing used it; only
`scripts/install.sh` ever copied units out of a release, so every new service needed a manual step on
every board, forever. That the mechanism existed and was unused was pointed out in review, not found
by me.

**2. The artifact did not contain the new units.** The packaging workflows name every shipped file
with an explicit `--include`, and the units were added to `install.sh` without being added there.
Found by hand: `ls current/systemd/` on the board.

**3. The artifact did not contain the new binaries.** The Package step copies binaries with an
explicit `cp` per binary. `cargo board --bins` built `btd` and `configd`; nothing staged them.
`btd.service` failed with `203/EXEC`, which reads as a broken daemon rather than an incomplete
artifact.

Bug 3 is the same class as bug 2, in the same file, **two commits after a test was added to stop
bug 2 recurring** — that test checked units and not the binaries they exec. Each fix was correct
and each was too narrow, which is the pattern worth attacking rather than the bugs.

**4. `on_apply`'s restart list lives on the board, so a new daemon is never restarted.**  ·
**measured** The most expensive one, and the one already written down here as "latent rather than
fatal".

`[component.daemon.on_apply].units` is read from `/etc/robot/updater.toml` — the *operator's* file,
which `install.sh` deliberately preserves. `configd` was added to the shipped `deploy/updater.toml`
in the branch that introduced it, so a board set up before that keeps `units = ["robotd"]` forever.
Every `configd` release therefore swapped the binary and left the old process running.

What made it cost two hours rather than two minutes is the shape of the failure:

- the update reports **success** — the swap happened, the health gate passed, nothing failed;
- `robotctl update apply` then reports **`already_current`** and does nothing, so the obvious
  recovery command is a no-op;
- the daemon keeps answering, on old code, so it looks like the fix was wrong rather than absent.
  Four wifi fixes were verified as broken against binaries that were never running.

`robotctl version` *does* diagnose this, in as many words: "configd is running X but the installed
daemon release is Y … either the restart did not happen, or it failed". Nobody ran it. A diagnostic
that exists and is not reached for is worth as much as one that does not exist, which is an argument
for the update itself noticing rather than for more diagnostics.

**Fixed** (`engine.rs::units_to_restart`): the restart set is derived from the release's
`systemd/*.service` files, unioned with whatever the config names, minus `updaterd` and `btd` — which
moved from a config convention enforced by a test into a `NEVER_RESTART` constant in code, because
they are properties of what those daemons are rather than operator choices. A board whose
`updater.toml` predates a daemon now restarts it anyway, and needs no edit. What follows is the
reasoning, kept because it is the argument for where such lists belong.

**Derive the restart set from the release, not from the board.** A release ships
`systemd/*.service`, so it already states which units it provides — the same realisation that made
`hooks/postinstall` the right answer for *installing* them. The engine can restart what the release
ships, minus the two documented exclusions (`updaterd`, which is performing the update; `btd`, which
may be the transport it was requested over). Then a release that adds a daemon restarts that daemon
on every board, with no operator edit and no way for a board's config to be silently out of date.

Two smaller options were noted here as companions to the above rather than alternatives to it:
`apply` could gain a `--force` that re-runs the hooks and the restart on an already-current release
(there is precedent — `install --force` exists for the same class of chicken-and-egg), and
`already_current` could compare *running* revisions rather than only the installed one, so it stops
being a no-op precisely when something is wrong.

**The second one is answered, and not where it was proposed.** The question it really posed was
whether a running/installed mismatch should be reported and refused or repaired, and the answer is
repaired — by `updater/src/reconcile.rs`, which runs at every `updaterd` start rather than inside
`apply`. Each unit's running release comes from the identity file its process published, is compared
with what its component has active, and anything stale is restarted. Since `updaterd` restarts itself
five seconds after every applied update, that check runs seconds after every `apply`, so the state
this section is about now heals itself with `Engine::apply` unchanged.

What that left was narrower than either option as written, and it is now closed too. `reconcile`
deliberately does not repair one skew — `updaterd`'s own, because a self-restart loop in the process
that owns recovery is the one failure with no way out — and that met an `apply` returning
`AlreadyCurrent` on the installed version alone in a single case: a stale `updaterd`, an operator
reaching for `apply`, `already_current`, no restart scheduled, and nothing to fix it but a hand-run
`systemctl restart updaterd`.

**Fixed** (`engine.rs::restarts_owed`, `reconcile::stale_units`). `apply` and `select` read the same
identity files on their already-current paths, name the units running something else in the
`already_current` outcome, and schedule those restarts the way an update schedules its deferred pair.
It is not the loop the startup check guards against: it fires once, on a request, and through
`systemd-run` rather than from inside the process being restarted.

**And `apply --force` is dropped rather than deferred.** Its whole job was to re-run the restart on an
already-current release; that is now what `apply` does when — and only when — something is actually
stale. A flag would add a second way to ask for it, gated by a question that took a paragraph to get
right: `install --force` refuses while `robotd` answers because it disables the health gate, `apply`
keeps that gate, so copying the guard by symmetry would have disabled the flag exactly when a robot is
up and skewed. Nothing needs to answer that now.

**Fixed, and this paragraph used to say otherwise.** `btd` is excluded from the *in-flight* restart
because restarting it drops the BLE connection carrying the update's own progress stream — that part
was and remains right. The conclusion drawn from it was not: this said a `btd` fix "needs a manual
restart or a reboot … a real gap in a phone-driven flow", and it does not any more. The exclusion
expires the moment the outcome is on the wire, so `btd` and `updaterd` both restart five seconds later
via `systemd-run --on-active=5s` (`RESTART_AFTER_REPLYING`). A client sees its outcome and then a
dropped connection, which for BLE is an ordinary reconnect.

**Also fixed, and this paragraph used to say otherwise too.** The observability half was said to
survive: `robotctl version` could not see `btd`, because `btd` serves no socket, so there was nothing
to ask. The premise was that the answer had to come over a socket. It does not — every daemon now
writes its identity to a file at startup, `btd` and `padd` included, so `robotctl health` reads the
release each process was launched from and warns when it disagrees with what is installed. No daemon
is unobservable for the reason this claimed.

### A consequence worth knowing: units outlive the release that installed them

`hooks/postinstall` installs the units a release ships and, by design, leaves them behind on a
rollback — the alternative is recording what was added so a revert can undo it, and the hook's own
comment argues that is not worth it because the next successful update reinstalls whatever it ships.

That reasoning holds for a rollback. It does not hold for a **downgrade to a release that predates a
daemon**: the unit stays, its `ExecStart` names a binary the older release does not contain, and the
daemon fails with `203/EXEC`. Once that daemon is also in `on_apply`'s restart set, the failed restart
fails the *update*, which reverts.

Observed exactly this way: `robotctl update apply daemon` on a board running a dev build resolved to
stable `0.2.0`, which predates `configd`; `configd.service` could not start; the engine rolled back
and said so. The outcome is right — a board should not silently downgrade below the release that
introduced a daemon it is now running — but nothing states the rule, and the error names a systemd
failure rather than the cause.

**Now stated rather than emergent.** `updater/src/orphan.rs` refuses a candidate that lacks a binary
some installed unit execs, and the refusal names the unit, the missing binary and the way past it —
remove the unit, `systemctl disable --now configd.service && rm /etc/systemd/system/configd.service`.
There is no override flag: removing the unit is what the operator means anyway, since a board below
the release that introduced a daemon should not be running that daemon, and the next update that
ships the unit reinstalls it.

Two things about where it runs. It is **not** in preflight, which cannot see the candidate's file
list — both preflight passes run before the artifact is downloaded — so it runs after extraction and
before the swap, where staging is still disposable and nothing is armed. And **no target is exempt**,
unlike `Error::WouldDowngrade`, which fires on `Latest` alone: that guard is about a mirror serving a
stale manifest, this one is about a unit that will not start, and `Ref` is precisely how it was
observed.

It does not run on rollback, reset-to-golden or `select`. Those move backwards on purpose and are how
a board gets off a bad release, so a check that can refuse must not sit in the recovery path
(`docs/design/architecture.md` §1.1) — rolling back onto an orphaned unit stays the documented
behaviour above, and stays self-correcting.

## Why the existing tests could not have caught them

Not an accusation of the tests; they cover what they claim. The point is what nothing covers.

This was written when the answer was "nothing", and the row that says so has since changed. Kept as
the record of what was missing, with what each check covers **today**:

| | covers | does not |
|---|---|---|
| `board-test.sh` | binaries executed on real aarch64 Linux, **and a real artifact unpacked and installed** by `install.sh` and `hooks/postinstall` against a stubbed `systemctl` — placements, modes, ordering, idempotence, and every unit's `ExecStart` binary being present | services actually starting, which needs real systemd |
| `xtask` tests | the workflow YAML vs `install.sh`, and unit `ExecStart` vs staged binaries | whether the *built artifact* matches either — it reads source files |
| `updater` tests | engine, journal, verification, rollback, with fakes | `install.sh` at all |
| `shipped_config_is_safe_for_a_client_robot` | `deploy/updater.toml`'s content | that the config is installable |

What the first row used to say was "unpacking an artifact, installing units, starting services", and
the sentence beneath it was: **no test takes a real artifact and installs it.** That was the finding
this document exists for, and it is fixed — the `xtask` row is still the weaker form, asserting that
two source files agree rather than observing what they produce, but it is no longer the only thing
standing between a packaging mistake and a board.

## What would close it

Revised 2026-08-11, after the restart mechanisms below landed and with one constraint that was not
stated the first time: **CI is already the slowest part of iterating, so the plan is judged on what it
adds to the wait, not only on what it covers.** Everything here therefore names where it runs.

### The budget, first

CI runs on every push and every pull request that touches code, as parallel jobs, so the wait for
green is the *slowest* job — not the total. That single fact decides where new tests belong:

| job | what makes it slow |
|---|---|
| `check` | fmt, clippy, `cargo test --workspace`, the installer lint, and a real `xtask package` |
| `board` | `cargo install cargo-zigbuild` from source, plus QEMU emulation for aarch64 |
| `coverage` | a full instrumented build |

So a millisecond-scale test added to `cargo test` costs nothing anybody notices, while anything that
lands in `board` or `coverage` is paid on every push. Three rules follow, and they are the point of
this section:

- **The default `cargo test --workspace` takes only in-process tests.** No tarballs, no `systemd`, no
  network, no sleeps.
- **Anything that unpacks an artifact or drives a service runs on demand**, as a script or an
  `#[ignore]`d test — never on the pull-request path.
- **No new CI job.** If a check needs an artifact, it hangs off the `xtask package` step `check`
  already runs, and reuses the tarball that step already built.

Both of those numbers used to be worse, and the two removals that fixed them are the shape this
section argues for — **taking work out of CI is worth more than any test below adds**:

- **`coverage` ran the whole instrumented suite twice** on a pull request, head and base, purely to
  print a delta. Removed: `--fail-under-lines` is what catches a regression, and this job went from
  over seven minutes to about two. The cost is stated rather than glossed — a change that lowers
  coverage while staying over the floor no longer says so, and the floor is a ratchet now.
- **A documentation-only change paid the whole bill.** `on:` had no path filter, so editing this file
  cross-compiled for aarch64 under QEMU and built the workspace under instrumentation. Three
  consecutive docs pull requests did exactly that while this plan was being written. Removed with a
  `paths-ignore` for `docs/**` and `*.md`.

  That one has a trap attached, checked rather than assumed: a skipped job reports **no status at
  all**, so filtering a check that is *required* for merge leaves docs pull requests permanently
  pending. It is safe here because `main` has no required status checks — the branch-protection API
  answers 403 on this plan. Turning protection on means revisiting it, and the shape then is a
  filtered job plus a no-op job of the same name.

### 1. Two tests that need no new machinery

In-process, in `cargo test`, and they cover the acting half of the two mechanisms that exist to make
an update self-healing — neither of which was observable by any test. Both are written; what follows
is why they were the first thing to do.

- **`systemd-run` is unobservable.** `schedule_deferred_restarts` hardcodes
  `Command::new("systemd-run")`, while `SYSTEMCTL` two functions away is a `const` precisely so
  `restart_tests` can substitute a stub script. Same treatment, and then assert what has never been
  asserted: `--on-active=5s`, one invocation per unit, both `updaterd` and `btd` named. The flag could
  be wrong today and every test would still pass.
- **`reconcile::check` is never called by a test**, only its pure `verdict_for`. It already takes
  `systemctl` as a parameter, and identities are read through `DUCK_RUNTIME_DIR` — a seam whose own
  comment says it exists so this is testable. Write identity files into a temp runtime directory and
  assert the four outcomes: stale is restarted, `updaterd` is reported and not restarted, a missing
  identity file is left alone, a failed restart reports itself.

### 2. The artifact install — done, and what it left

**This is no longer open, and the title of this document is no longer true.** `scripts/board-test.sh`
packages a real release from the `--include` list in `_build-release.yml`, unpacks it, and runs
`scripts/install.sh` *and* `hooks/postinstall` against it inside the container with a stubbed
`systemctl` (PR #47, 2026-08-07). Eleven assertions: units installed byte-identical at mode 644,
sysusers drop-ins, the `robotctl` symlink resolving through `current`, the journald drop-in,
`daemon-reload` before any `enable` and `configd` before `btd`, operator config files preserved,
idempotence on a second run, a unit `install.sh` does not recognise installed-but-not-started, and
postinstall reproducing the lot on its own.

That covers what this section used to ask for, and the "assert the artifact's contents" idea with it,
because the tarball is open by then. **Bug 2 is closed against the artifact rather than against the
YAML.**

One gap was left, and it is bug 3 — the one class of the four with no strong test. Nothing asked
whether the binary a unit `ExecStart`s is *in* the artifact that shipped the unit, which is exactly how
`btd.service` came to fail with `203/EXEC` on a board where the release looked complete. The
protection was `xtask/tests/artifact.rs`, comparing a workflow against `install.sh` — the
two-files-agree form criticised above. Now asked directly, three lines, in the job that already has
the tree unpacked and `current` pointing at it.

Only `ExecStart` paths inside the release are checked: a unit may deliberately exec out of the base —
the boot recovery net does, so that a broken release cannot break it — and requiring those to be
packaged would be wrong rather than strict.

**What is still genuinely missing here is nothing.** The remaining items are the two below, and they
cover different things rather than more of this one.

### 3. The board check — done, inside `dev-push.sh`

**Done, and not as a separate scenario script.** `dev-push.sh` used to end at "is live", which means
the swap happened and the health gate passed — not that the five daemons are running what was swapped
in. That gap is where an afternoon goes: four wifi fixes were once verified as broken against a
`configd` that had never restarted.

So the check runs on every push rather than before a promotion. It reads the identity each daemon
publishes at startup, compares the release named there against the board's `current`, and — separately,
because everything agreeing on the *previous* release would otherwise pass — against the version this
push built. `robotd`, `configd` and `padd` are expected to match at once; `updaterd` and `btd` are
polled for up to 30 s, because they restart five seconds after the reply.

This is the only thing that observes the whole restart mechanism end to end, and nothing in CI can
replace it: the transient timer, the `RuntimeDirectory=` holding each identity, and the five-second
delay are all systemd, on real timing. A stale unit fails the push and names what to look at.

Two deliberate non-failures. A daemon that published nothing is reported and not failed — systemd
removes the runtime directory when a unit stops, so it is also what a deliberately disabled `padd`
looks like. And `robotctl health` only has to *answer*: a bench board with no servo power reports
degraded, which is a fact about the bench rather than about the build, exactly as the health gate
treats it.

### 4. Real systemd — done, as `scripts/systemd-test.sh`

**Done, and it paid for itself before asserting anything.** `scripts/systemd-test.sh` boots systemd as
pid 1, mints three signed releases carrying real units and a real `updaterd`, installs one, applies
the next through the running daemon, and then applies one that ships a unit which cannot start.

Four things it observes that nothing else in the tree can, because everything else has a stub
`systemctl`:

- **`on_apply` really restarts** what the release ships — asserted on the unit's main PID changing,
  not on the command having been issued;
- **the deferred transient timer really fires and really replaces `updaterd`**, in about four
  seconds, and the successor is running the new release. A child process could not do this: it would
  sit in the cgroup being killed, which is the reason for `systemd-run` and was until now an
  untested claim;
- **`hooks/postinstall` really installs, enables and starts** a unit the board has never had;
- **a unit that installs cleanly and cannot start fails the update and names itself** —
  `restart failed: Job for broken.service failed` — rather than reverting with
  `not healthy within 30s: unreachable`. That is bug 1, and it is the one class the items above
  cannot reach.

**Docker rather than `systemd-nspawn`**, which is a change from what this section used to propose.
The objection to privileged containers *in CI* stands and this is not CI. What decided it is the
argument this section itself made for ranking real systemd last: a check that can only run on a
machine nobody develops on stops being read. Docker Desktop runs a privileged container with systemd
as pid 1 on the laptop this is developed on; nspawn does not.

It found a bug on its first run, in the code rather than in itself. `self_test_updaterd` ran the new
binary with no `--config`, so it validated `/etc/robot/updater.toml` however the running daemon was
started — defeating the check's whole purpose, which is to catch a new binary that rejects *the
board's* config file.

Both injections named here are in it too, and both landed assertions nothing else could make:

- **`systemd-run` cannot be run.** The update still succeeds — scheduling is best-effort by design,
  because the update is committed by then — the journal says so, and `btd` and `updaterd` are left on
  the old release exactly as a missed timer leaves them. Then the next `updaterd` start reconciles the
  stale `btd` onto the active release and does **not** restart itself, which in that process would be a
  loop with no way out. That is `reconcile.rs` closing the loop for the first time outside a unit test.
- **A unit whose `User=` the release brings with it.** `postinstall` installs `sysusers.d` files and
  runs `systemd-sysusers` before the units, and its comment calls that ordering load-bearing. The
  account exists and its unit runs. The other half — the same unit with nothing creating the user —
  fails the update and names the unit rather than the account.

### The gap the harness found on the way — fixed

**A failed update reported a failed rollback for a robot it had successfully put back.** Reproduced by
the missing-user release above, and `RollbackFailed` is the outcome the design calls the most serious
one — so it was worth more than a note.

The cause is not the rollback. `hooks/postinstall` overwrites unit files and, by design, does not put
them back: the hook argues that a release which did not take leaves one service failing until the next
one does, which is the same situation either way. That reasoning holds and is unchanged. What it did
not anticipate is the unit being in the restart set of the release being reverted **to** — then the
revert re-runs the same restart and inherits the same failure. Reachable by an ordinary bad release
rather than only by the downgrade case above: two consecutive releases ship the same unit name and the
newer one is broken.

**The fix separates the swap from the apply action, because only one of them is the recovery.** Past
`swap_to` and the trial being cleared, the robot *is* back on the release it came from; a unit that
then fails to restart is a second fact, not a contradiction of the first. So `Error::RollbackFailed`
keeps its meaning — the robot could not be put back at all — and a failed apply action during a revert
is carried into the reported outcome and logged at `error`:

```text
not healthy within 30s: …; the release was reverted, but restarting robotd failed: …
`Restart=` may have brought it back since — `robotctl health` says whether it did.
```

Both facts, in the order someone needs them: why the update failed first, then the unit that did not
come back with the revert.

The second half of that sentence used to read "so something on this robot is down", and it was wrong
often enough to be worth naming. Every daemon here runs `Restart=always`, and a daemon that exits
immediately burns systemd's five starts per ten seconds long before the health gate's thirty are up —
so the revert's restart is routinely refused with `Start request repeated too quickly` and the unit is
back on its own moments later. A bench board printed that outage claim directly beneath its own
`robot healthy` line. `restart_one` now clears the counter with `reset-failed` and tries once more,
which removes the cause; the outcome reports the refusal it observed and names the command that
answers what it cannot.

The two rejected alternatives, since neither is obviously wrong. Making `postinstall` reversible is the
change the hook explicitly declined; it needs state outside the release and adds a failure mode to the
recovery path, which is the one place that has to stay boring. Tolerating a failed restart *everywhere*
would weaken the distinction `restart_one` draws on purpose — a unit that exists and will not start is
how a broken release is caught, and that is still fatal on the way *in*.

### Not doing

**A board as a self-hosted runner.** Ops cost, and a single point of failure for CI. Item 3 gets most
of the value on demand, which is where a robot in a room belongs.

## A second, separate problem: version skew on the dev channel

Found in the same session and easily confused with the above, but no amount of install testing
would catch either — in both cases the artifact was complete and correct.

The shape was always the same, and **the sentence that used to open this section is no longer true.**
It read: "`updaterd` never restarts itself during an update (§4.1), so it keeps running the old binary
until the next reboot, while everything else on the box moves to the new release immediately." That was
the root cause of both instances below, and it is fixed — `updaterd` now restarts itself five seconds
after the update replies. The skew window is seconds, not "until someone reboots".

Read the two cases with that in mind. Neither is a live incident any more, and **both are now
closed** — case 1 by fixing what it proposed, case 2 by deciding against it:

- Case 1's `serde(default)` fix was **not** made redundant by the shorter window: version skew is
  only the commonest way to hit it, and any newer-parser-older-sender pair does. Done, on the
  sections where a defaulted zero is honest.
- Case 2's handshake fix was **mostly** made redundant by it, dropping from "the recovery command
  itself stops working" to "a five-second window during which it does" — and when the design
  argument was finally written out, the premise it rested on did not survive. The exact `!=` stays;
  what changed is the message. See below and #77.

Two instances, both real, both cost about an hour.

### 1. A required field added to `HealthResult`

`main` added `consecutive_stale_blocks` to the IMU section and released 0.2.0 from it. A branch that
had merged `main` *before* that did not send the field. `robotd` came up perfectly — served the
socket, loaded both policies, ran the loop at 50 Hz — and the resident 0.2.0 `updaterd` rejected its
reply for a missing field. `RobotIo::health` maps an unparseable answer to `Health::Unreachable`, so
the gate reported `not healthy within 30s: unreachable` about a robot that was entirely healthy, and
reverted a good release.

Fixes, both small, and **both done**:

- **`#[serde(default)]` on new `HealthResult` fields**, so a newer `updaterd` can still parse an
  older `robotd`. Every `--ref` install of a branch predating a health-field addition hit this
  otherwise, which is the entire dev workflow.

  The half that bit was the nested one: every *top-level* field carried `#[serde(default)]`
  already, including `imu`, while `consecutive_stale_blocks` on the nested `ImuHealth` did not.
  `ImuHealth` and `BusHealth` now carry it at the container level, so a field added to either
  defaults rather than failing the whole parse.

  `LoopHealth`, `Battery` and `MotorThermal` deliberately do **not**, and the exception is the
  useful part of the fix: those sections carry *measurements*, where a defaulted zero is a lie an
  older sender never told — a defaulted `percent: 0.0` renders as a flat pack on a robot with a
  full one. The rule is "default what an omission honestly means", not "default everything", and
  `ImuHealth`'s doc comment argues it field by field.
- **A distinct `Health::Incompatible`** rather than reusing `Unreachable`, so the reason reads
  "answered in a shape this updaterd does not understand" instead of implying the robot is down.
  Pure diagnostics, and it would have found the above in a minute.

  Done. It also turned up its own neighbour while being added: `safe_to_restart` was collapsing an
  unreadable reply the same way, and `permits_restart` then read it as *safe* — the opposite of what
  its own comment promised. That became `SafeToRestart::Incompatible` and #68.

### 2. `API_VERSION` skew between `robotctl` and `updaterd`

`robotctl` is a symlink into `current`, so it follows the installed release. `updaterd` does not. So
the moment a release changes `API_VERSION`, the two are **guaranteed** to disagree until `updaterd`
restarts — and the command that stops working is `robotctl update apply`, which is exactly the one
you would use to get out of it.

Demonstrated by ordinary use rather than by contrivance: install branch A, install branch B while
waiting for CI, and every `robotctl` call fails with `client speaks API v2, daemon speaks v3`. The
escape is to invoke a `robotctl` from a release directory whose version matches the running daemon,
or to restart `updaterd` — neither of which is discoverable from the error.

The handshake at least *caught* it and named both versions, which is more than case 1 managed.

The first proposed fix was **`hello` should refuse only when the client is *newer* than the daemon**,
and it was **decided against** (#77): it assumed bumps are additive, and they are not — v5 added
`pad.*` and was additive, v4 made `system.authenticate` mandatory and was not. Accepting older
clients on the strength of a pattern the constant does not track would have promised backward
compatibility with nothing to enforce it.

**Fixed instead by removing the gate outright.** The premise of that refusal survives — a bump
promises nothing — but the conclusion does not follow from it. What breaks a mismatched peer is a
*route it cannot reach* or a *parameter shape that moved*, and both of those already refuse
themselves, by name, on the one call that cannot be served: `METHOD_NOT_FOUND` from
`Request::as_call`, `INVALID_PARAMS` from a params decode. A gate on the handshake fired on every
other call as well — every call, in fact, since `hello` precedes all of them — which is how a
one-digit difference took away `update apply` and `version` at the same time. So `updaterd` now
logs the pair of versions and serves the call; the difference reaches the client through
`HelloResult::api_version`, and `robotctl` prints one warning line per run.

Two things had to be true before the gate could go, and the second is the useful part:

- **The refusal had to be redundant, not merely annoying.** It is: `robotd`, `configd` and `padd`
  never checked the number at all, and `updaterd` required no handshake before `update.status`
  anyway. `duck-btctl` had already reached the same conclusion from the far end of the link (#102).
- **A silently ignored parameter had to stop being possible.** `serde` ignores what it does not
  know, which is what made the gate feel load-bearing: v7 added `ApplyOptions::from_dir`, and a v6
  daemon that ignored it would install from its *configured* source while the operator believed they
  were sideloading a directory. Every params type now denies unknown fields, so that is an
  `INVALID_PARAMS` naming the member. It reaches forward only — a daemon built before this still
  ignores what it does not know — which is why an `API_VERSION` bump is still worth making.

The message was rewritten before this and is now gone with the gate. It said `client speaks API v2,
daemon speaks v3` and named no way out; the remedy it grew (retry, or use the symlink at
`/usr/local/bin/robotctl`) now lives in `robotctl`'s warning, where nothing is being refused.

### Why these are not install-path bugs

Nothing in the plan above would have caught either. The artifact was correct both times; what was
wrong was the *pair* of versions running at one moment, which only exists on a machine that has been
updated. Item 4 (real systemd locally) would catch the *health-gate* consequence of case 1 if the
container also ran an older `updaterd`, but constructing that skew deliberately is a different kind of
test — closer to a compatibility matrix than to an install test, and worth keeping separate.

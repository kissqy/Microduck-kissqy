# Updating a robot from a phone

Status: shipped, not yet run on a board · Date: 2026-08-19 · Owner: pierre

The update path over Bluetooth was most of the way there and nobody had driven it. `btd` already
routed the update subset, `updaterd` already streamed progress to whoever asked, and `duck-btctl`
could reach all of it through `call`. Driving it turned up one defect that made the app's own flow
— start an update, watch it — an update the robot silently never performed, two smaller ones in
`updaterd`, and a client surface worth typing.

This records what was found and what was decided. The mechanisms live next to the code:
[`app-path-design.md`](../design/app-path-design.md) §3.5 owns the connection lanes and §3.1 the
routed subset, and `btd/src/route.rs` carries the reasoning for every route on the arm that makes
it.

## 1. What already worked, and was not rebuilt

**The routed subset covered the reads and the trigger.** `hello`, `update.check`, `update.apply`,
`update.status`, `update.subscribe`, `update.log` and `update.listInstalled` already reached
`updaterd`, and `robot.health` `robotd`. Nothing here added a method to the protocol.

**An apply already streamed its own progress.** `updaterd`'s `run_mutating` writes
`update.progress` notifications to the connection the apply arrived on, before the reply; `btd`
pumps every line from an upstream into the session without reading it; `duck-btctl` printed id-less
lines and kept waiting. So progress reached a BLE client during an apply with no subscription at
all — and `duck-btctl.md` claimed the opposite, *"an apply on its own connection is silent until it
is done"*, which is corrected.

**A client that reconnects mid-update was not lost.** `updaterd` keeps the latest `Progress` per
component and replays it to a new subscriber, and `update.status` answers during an update from a
cached snapshot with the live phase patched in. Both are what a phone needs after the link drops.

**And the reply gets out before the transport dies.** `updaterd` and `btd` are the two units an
update never restarts, and both are restarted about five seconds *after* the reply
([`restart-order.md`](../design/restart-order.md) §1).

## 2. What was wrong

### 2.1 A long call silenced the rest of the session · `btd` · **fixed**

`Pool` held one connection per service per session, and both daemons behind it serve one connection
one request at a time. So `update.subscribe` followed by `update.apply` wrote the apply into a
socket `stream_progress` had stopped reading: it never ran, never replied and never errored. An
owner taps "update", the robot does nothing, and there is no error anywhere to find. `update.apply`
followed by `update.status` was the same defect with a milder symptom — a status poll that timed
out while the robot was fine and updating.

Calls are now grouped by how long they hold a connection and each group gets its own:
`app-path-design.md` §3.5 has the lanes, why sharing one is correct where it happens, and why a
connection per call was rejected. Both failures have tests that fail without the fix.

This was the only change here a mobile app could not have worked around.

### 2.2 Progress was a firehose aimed at a 20-byte pipe · `updaterd` · **fixed**

The source reports every HTTP chunk it writes — thousands, for a release artifact — and every
subscriber paid for all of them. A progress line is around a hundred bytes, which is five or six
notifications at the 20-byte floor `btd` frames to, and `btd` drops lines when the client falls
behind, so a phone saw an arbitrary subset of the percentages and a bar that jumped 12 → 61 → 34.

Now at most one notification per whole percent and at most four a second, coalesced in the engine
where the numbers are made, so `robotctl update watch` gets the same stream. A percent suppressed
by the gap is still published when the download ends, or a fast download visibly finishes at 97%.

### 2.3 `update.check` blocked on the engine lock · `updaterd` · **fixed**

`ipc.rs` states the rule in its own header — read-only requests use `try_lock` so `status` and
`subscribe` stay answerable during an update — and `check` did not follow it. Asked during an
apply it answered whenever the apply finished, minutes later, which on a phone is
indistinguishable from a robot that has stopped answering. It now answers `BUSY` at once, and so
does `update.pin`.

### 2.4 Decided: going back is reachable from a phone

`update.rollback` and `update.select` were refused; both are now routed. `update.pin` and
`update.resetToGolden` stay refused. The reasoning is on the arms in `btd/src/route.rs` and
summarised in `app-path-design.md` §3.1; what decided it:

`update.apply` was already routed and is the more consequential of the three — it installs code
that has never run on this board, from the network — while rollback and select move to a release
that ran on it yesterday, download nothing, and are gated and auto-reverted like any other
transition. The engine's own auto-revert covers the release that fails its health gate, which is
not the case an owner reaches for a phone about: that is a release that installs, passes its gate,
and then behaves *worse* — a policy that walks unsteadily rather than not at all, a pad that stops
reconnecting. Nothing reverts that but a person, and the person is holding a phone and has no ssh.

Both were opened rather than only `rollback`, because `update.listInstalled` is already routed: an
app can show every release on the board, and being able to show them without being able to choose
one is the odd half. `select` needs a version picked from a list, which is a bigger surface to get
wrong from a mistap, and that is the cost accepted.

`pin` is the interesting refusal. A wrong `select` is one release away from being undone and the
robot says which release it is on; a robot pinned by a mistap refuses every later update and
reports itself as up to date, which is the one failure here that looks like correct behaviour.

### 2.5 A phone-triggered update is logged as `btd` · **recorded, not fixed**

`updaterd` records the caller's uid and pid from `SO_PEERCRED` on every mutation, which is how
support answers "who triggered this rollback". Over BLE the answer is always `btd`, for every
phone. `btd` forwards params verbatim and adding a "who" field would make it an author of requests
rather than a pipe. Worth reopening only if support needs to tell two phones apart.

### 2.6 Client deadlines were total, not idle · `duck-btctl` · **fixed**

A fixed budget either cuts off a working update or waits out a dead robot, and the useful signal
was already arriving: every progress notification is proof the robot is working. Deadlines are now
silences — three minutes for an update, which is the longest gap one can legitimately have (a
post-install hook), not the longest one can take. A phone app inherits the principle, not the code.

### 2.7 The link drops about five seconds after a daemon apply replies

Not a defect — §1's ordering, working — but every client has to expect it, and a disconnect the
robot announced must not read as a failed update. The sequence to build against:

1. `update.apply` replies with its outcome. That is the answer; the update is done.
2. About five seconds later `btd` restarts and the connection drops.
3. Reconnect, and read `update.status`. `last_attempt` carries the outcome, so a client that missed
   the reply in step 1 can still report it.

`duck-btctl` prints step 2 before it happens.

### 2.8 Open, deliberately: `from_dir` over Bluetooth

`ApplyOptions.from_dir` names a directory on the robot, which is meaningless to a phone and useful
on a bench. Filtering it would mean `route.rs` deciding on params rather than methods, and
inspecting params is what `btd` does not do. Preflight already refuses the cases that bite — and
says so — so this is left as it is, named here so the next person finds a decision rather than an
oversight.

## 3. What `duck-btctl` offers now

`version`, and `update` with `check`, `apply`, `status`, `versions`, `log`, `rollback`, `select`
and `watch` — the same words `robotctl update` uses, so a command learned on the robot works over
the radio. Params are built from `duck_ipc_proto`'s own types rather than hand-written JSON, which
is what `call` left to whoever was typing: `update.apply`'s target is an externally tagged enum, so
`--ref` and `--version` are different JSON *shapes*, and a wrong one is a parse error with nothing
in it to act on. [`duckctl.md`](../robot/duckctl.md) has every command.

Progress prints as one line per event on stderr, which that page already promised and the tool did
not do.

`duck-btctl` is a stopgap, and this is where that mattered: §2.1, §2.2 and §2.3 are robot-side, so
the app inherits the fixes, while §2.6's deadline shape is client-side, so the tool got it right
and the app's own notes will have to say why.

## 4. What is left

**None of it has run on a board.** Everything above is covered by tests, and the tests cannot see
what a phone sees: whether progress arrives smoothly over a real 20-byte link, whether an apply's
reply reaches the client before `btd` restarts, and whether the fourth socket per service costs
anything on a Zero 3W. That is the next session, with `duck-btctl update apply --ref` against a dev
board.

**The stale claim in `duck-btctl.md` was corrected from reading the code, not from a board.** If an
apply over BLE turns out to be silent after all, the mechanism to look at is the outbound queue in
`btd/src/link.rs`, not the routing.

## 5. What this deliberately does not do

**No cancel.** The engine has none, and a half-applied update is worse than a slow one. A client
that walks away is already handled: the update finishes.

**No auto-apply toggle from the phone.** `deploy/updater.toml` deliberately does not opt client
robots into unattended restarts, and that is not a decision to expose as a switch before there is
a fleet to reason about.

**No encryption.** `app-path-design.md` §8.1 owns it, it blocked nothing here, and every claim
above about what a peer in radio range can do assumes it is still off.

//! Which of the robot's daemons are running, and which release each is running.
//!
//! Started as "is `padd` running?", reported alongside the pads because a connected pad and a dead
//! `padd` is the failure that looks like working hardware: the light on the controller is on, the
//! robot ignores it, and nothing in either place says why. That argument was never specific to
//! `padd` — a dead `btd` is a robot no phone can see, with the same silence — so it answers for
//! every unit a release manages.
//!
//! Asked of systemd rather than tracked: these are started, stopped and restarted by systemd, so
//! systemd is the only thing that knows. `configd` deliberately holds no opinion about most of
//! them — it does not start them, does not restart them, and reporting is almost the whole of its
//! involvement. The one exception is `padd`: `system.serviceAction` stops and starts it, because
//! a phone driving the robot has no way to settle a fight with a gamepad otherwise. That call is
//! whitelisted down to this one unit in [`permitted_unit`].
//!
//! ## Which release is running
//!
//! Not asked of systemd and not inferred from `/proc`: **each daemon publishes its own identity at
//! startup**, to `/run/<service>/identity.json`, and this reads it. See
//! [`duck_ipc_proto::Identity`] for why that beats inspecting a process from outside — briefly, a
//! process knows its version, its git revision and its own exe, and needs no privilege to say so.
//!
//! What is left for systemd is the question only systemd can answer: whether the unit is running.
//! The two are read together because they mean different things apart. A published identity with a
//! stopped unit cannot happen — systemd deletes the runtime directory with the unit — but a *stopped
//! unit with no identity* and a *running daemon too old to publish one* both report nothing, and the
//! unit state is what distinguishes them.

use duck_ipc_proto as proto;

/// The unit that turns a pad into intents.
pub const PADD: &str = "padd.service";

/// Whether `system.serviceAction` may act on this unit.
///
/// **A whitelist of one, and it is the security boundary of that method.** The client names a
/// unit as a string, and this is the only thing between a phone and `systemctl stop` with
/// whatever it liked. `padd` is on it because two drivers fighting is the case the call exists
/// for — a gamepad left connected while somebody drives from the phone — and because the phone
/// has no ssh to settle it. Returning here with a second entry should be a decision written
/// down, not a pattern widened.
pub fn permitted_unit(unit: &str) -> bool {
    unit == PADD
}

/// Stop or start [`PADD`] through systemd, and answer with the state afterwards.
///
/// The job is queued by systemd, so an immediate read is a state in transition — which is why
/// this waits for the target rather than racing it. Bounded, because a unit that refuses to
/// stop must not hold the connection open: the caller gets the state it ended at either way.
#[cfg(target_os = "linux")]
pub async fn perform(unit: &str, action: proto::ServiceAction) -> Result<proto::UnitState, String> {
    use std::time::{Duration, Instant};

    let bus = zbus::Connection::system()
        .await
        .map_err(|e| format!("cannot reach the system bus ({e})"))?;
    let method = match action {
        proto::ServiceAction::Stop => "StopUnit",
        proto::ServiceAction::Start => "StartUnit",
    };
    bus.call_method(
        Some("org.freedesktop.systemd1"),
        "/org/freedesktop/systemd1",
        Some("org.freedesktop.systemd1.Manager"),
        method,
        // "replace": a queued start from a previous tap must not make this one a no-op.
        &(unit, "replace"),
    )
    .await
    .map_err(|e| format!("systemd refused {method} for {unit}: {e}"))?;

    let wanted = match action {
        proto::ServiceAction::Stop => proto::UnitState::Inactive,
        proto::ServiceAction::Start => proto::UnitState::Active,
    };
    let deadline = Instant::now() + Duration::from_secs(3);
    loop {
        let now = state(unit).await;
        if now == wanted
            // A stop that ends in `failed` is the answer too — waiting out the rest of the
            // deadline would tell the caller nothing new.
            || (action == proto::ServiceAction::Stop
                && matches!(now, proto::UnitState::Failed | proto::UnitState::Absent))
            || Instant::now() >= deadline
        {
            return Ok(now);
        }
        tokio::time::sleep(Duration::from_millis(100)).await;
    }
}

/// Off the board there is no systemd to act on, and pretending a unit stopped would be worse
/// than saying so — the caller would show a phone a state nothing on this machine is in.
#[cfg(not(target_os = "linux"))]
pub async fn perform(
    unit: &str,
    _action: proto::ServiceAction,
) -> Result<proto::UnitState, String> {
    Err(format!(
        "system.serviceAction needs systemd; {unit} cannot be changed on this machine"
    ))
}

/// Every unit a daemon release manages, in the order a reader wants them: the update engine, then
/// the robot, then the ones that depend on both.
///
/// Hardcoded rather than discovered, and that is a real limitation worth naming: a unit added to a
/// release and not to this list is invisible here. The alternative — asking systemd for everything
/// and filtering — reports units this project does not own, which is worse for a status line.
/// `scripts/install.sh` knows exactly these.
///
/// It has already cost once: `mediad` and `tofd` shipped units two releases before they were named
/// here, so the block a person reads after an update — the one that exists to say which daemon is
/// still on the old release — could not report either of them at all.
pub const MANAGED: [&str; 7] = [
    "updaterd.service",
    "robotd.service",
    "configd.service",
    "btd.service",
    "padd.service",
    "mediad.service",
    "tofd.service",
];

/// What systemd says about one unit. The narrow question, kept for `pad.status`.
pub async fn state(unit: &str) -> proto::UnitState {
    describe(unit).await.state
}

pub async fn all() -> Vec<proto::ServiceUnit> {
    let mut units = Vec::with_capacity(MANAGED.len());
    for unit in MANAGED {
        units.push(describe(unit).await);
    }
    units
}

#[cfg(target_os = "linux")]
pub async fn describe(unit: &str) -> proto::ServiceUnit {
    let state = match query(unit).await {
        Ok(state) => state,
        Err(e) => {
            // A warning, not an error: this is one line of a status report, and failing to read it
            // must not fail the report.
            tracing::warn!(error = %e, unit, "could not ask systemd about a unit");
            proto::UnitState::Unknown
        }
    };

    proto::ServiceUnit {
        identity: proto::read_identity(service_of(unit)),
        unit: unit.to_owned(),
        state,
    }
}

/// Off the board there is no systemd to ask, and inventing an answer would make a laptop look like a
/// robot with a broken daemon. The identity file is still read: it is an ordinary file, and a daemon
/// run by hand on a laptop publishes one.
#[cfg(not(target_os = "linux"))]
pub async fn describe(unit: &str) -> proto::ServiceUnit {
    proto::ServiceUnit {
        identity: proto::read_identity(service_of(unit)),
        unit: unit.to_owned(),
        state: proto::UnitState::Unknown,
    }
}

/// `btd.service` names the service `btd`, which is what it publishes under — and, with a pid
/// after it, what it logs under. [`crate::logs`] reads it for the second reason.
pub fn service_of(unit: &str) -> &str {
    unit.strip_suffix(".service").unwrap_or(unit)
}

#[cfg(target_os = "linux")]
async fn query(unit: &str) -> Result<proto::UnitState, String> {
    let bus = zbus::Connection::system()
        .await
        .map_err(|e| e.to_string())?;

    // `LoadUnit` rather than `GetUnit`: `GetUnit` fails for a unit systemd has not loaded, which is
    // indistinguishable from a unit that does not exist — and those are different answers here.
    // `LoadUnit` loads it if the file is there and fails only when it genuinely is not.
    let path: zbus::zvariant::OwnedObjectPath = match bus
        .call_method(
            Some("org.freedesktop.systemd1"),
            "/org/freedesktop/systemd1",
            Some("org.freedesktop.systemd1.Manager"),
            "LoadUnit",
            &(unit),
        )
        .await
    {
        Ok(reply) => reply.body().deserialize().map_err(|e| e.to_string())?,
        Err(e) => {
            // No such unit: a board on a release older than the one that added it. That is a fact
            // about the install, not a failure to report as one.
            tracing::debug!(error = %e, unit, "no such unit");
            return Ok(proto::UnitState::Absent);
        }
    };

    let active: String = property(&bus, &path, "org.freedesktop.systemd1.Unit", "ActiveState")
        .await?
        .try_into()
        .map_err(|e: zbus::zvariant::Error| e.to_string())?;

    // A second property on the connection and object path already in hand, so it costs one more
    // round trip on the same bus. It buys the only distinction systemd makes between a daemon
    // coming up and a daemon that keeps dying: both are `ActiveState=activating`.
    let sub: String = property(&bus, &path, "org.freedesktop.systemd1.Unit", "SubState")
        .await?
        .try_into()
        .map_err(|e: zbus::zvariant::Error| e.to_string())?;

    Ok(state_of(&active, &sub, unit))
}

/// What one `ActiveState`/`SubState` pair means.
///
/// Pure, and separated from the bus call for the reason `reconcile::verdict_for` is: the mapping is
/// the part that can be wrong, and the states worth checking are the ones a test cannot arrange —
/// a crash loop needs a daemon that will not start, and asking systemd for one on a board means
/// breaking the robot.
///
/// **`SubState` is read first**, because `auto-restart` is the answer `ActiveState` cannot give.
/// systemd reports a unit waiting out its `RestartSec=` as `activating`, exactly as it reports one
/// starting for the first time; taking `activating` for `Active` is what let `mediad` crash-loop on
/// an unplugged camera flex while `robotctl health` called it active. `auto-restart-queued` is the
/// same state one systemd version later, hence the prefix rather than an equality.
pub fn state_of(active: &str, sub: &str, unit: &str) -> proto::UnitState {
    if sub.starts_with("auto-restart") {
        return proto::UnitState::Restarting;
    }

    match active {
        // `activating` still counts as active: `padd` spends its first moments connecting to
        // `robotd`, and reporting that as "not running" would make a robot mid-boot look broken.
        // With `auto-restart` taken out above, that is all this arm now catches.
        "active" | "activating" | "reloading" => proto::UnitState::Active,
        // Reported apart from `inactive`, because a daemon that could not start and a daemon
        // somebody stopped are different news even though neither is running.
        "failed" => proto::UnitState::Failed,
        "inactive" | "deactivating" => proto::UnitState::Inactive,
        other => {
            tracing::warn!(state = other, unit, "unfamiliar unit state");
            proto::UnitState::Unknown
        }
    }
}

#[cfg(target_os = "linux")]
async fn property(
    bus: &zbus::Connection,
    path: &zbus::zvariant::OwnedObjectPath,
    interface: &str,
    name: &str,
) -> Result<zbus::zvariant::Value<'static>, String> {
    bus.call_method(
        Some("org.freedesktop.systemd1"),
        path,
        Some("org.freedesktop.DBus.Properties"),
        "Get",
        &(interface, name),
    )
    .await
    .map_err(|e| e.to_string())?
    .body()
    .deserialize::<zbus::zvariant::Value>()
    .map(|value| value.try_to_owned().map(Into::into))
    .map_err(|e| e.to_string())?
    .map_err(|e| e.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The pair a crash loop presents as, and the whole reason [`state_of`] reads `SubState`.
    #[test]
    fn auto_restart_is_not_active() {
        assert_eq!(
            state_of("activating", "auto-restart", "mediad.service"),
            proto::UnitState::Restarting
        );
        // The same state on a systemd new enough to queue the job separately.
        assert_eq!(
            state_of("activating", "auto-restart-queued", "mediad.service"),
            proto::UnitState::Restarting
        );
    }

    /// A daemon coming up for the first time is `activating` too, and must keep reading as running
    /// — `padd` is `activating` while it connects to `robotd` on every boot.
    #[test]
    fn starting_still_counts_as_active() {
        assert_eq!(
            state_of("activating", "start", "padd.service"),
            proto::UnitState::Active
        );
        assert_eq!(
            state_of("active", "running", "padd.service"),
            proto::UnitState::Active
        );
    }

    /// `failed` and a deliberate stop both mean "not running" and are not the same news.
    #[test]
    fn failed_is_not_a_stop() {
        assert_eq!(
            state_of("failed", "failed", "mediad.service"),
            proto::UnitState::Failed
        );
        assert_eq!(
            state_of("inactive", "dead", "padd.service"),
            proto::UnitState::Inactive
        );
    }

    /// An unfamiliar `ActiveState` reports "I do not know" rather than guessing at one of the
    /// answers that would be acted on.
    #[test]
    fn an_unknown_state_stays_unknown() {
        assert_eq!(
            state_of("maintenance", "whatever", "robotd.service"),
            proto::UnitState::Unknown
        );
    }

    /// `system.serviceAction` acts on `padd` and nothing else — not even a unit this project
    /// ships, and certainly not one a caller made up.
    #[test]
    fn only_the_pad_driver_may_be_stopped() {
        assert!(permitted_unit("padd.service"));
        for unit in [
            "robotd.service",
            "btd.service",
            "updaterd.service",
            "configd.service",
            "ssh.service",
            "padd",
            "",
        ] {
            assert!(!permitted_unit(unit), "{unit}");
        }
    }
}

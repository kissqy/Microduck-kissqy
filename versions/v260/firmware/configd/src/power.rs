//! Rebooting, through systemd rather than around it.
//!
//! `reboot(2)` would be one syscall and is wrong here: it cuts power without stopping services,
//! so `robotd` never releases servo torque and the update journal never flushes. A robot that
//! reboots by falling over is not an acceptable implementation of `system.reboot`.
//!
//! logind's `Reboot` is polkit-gated, and there is **no polkit on this board** — so a
//! session-less non-root caller is simply denied. That is the whole reason `configd` runs as
//! root. It is a narrow, sandboxed root (see `systemd/configd.service`), and the alternative was
//! installing a JS policy engine to authorise a single call.

use std::time::Duration;

/// Gap between answering and rebooting.
///
/// Load-bearing rather than polite: a daemon that rebooted inside the call would drop the
/// connection before responding, and every client — a phone especially — would have to treat a
/// broken pipe as success. Long enough for the response to be chunked out over BLE at 20 bytes a
/// notification, short enough that nobody wonders whether it worked.
pub const REBOOT_DELAY: Duration = Duration::from_secs(3);

/// Answer now, reboot shortly.
pub fn schedule() {
    tokio::spawn(async {
        tokio::time::sleep(REBOOT_DELAY).await;
        tracing::warn!("rebooting now, as requested over IPC");
        if let Err(e) = reboot().await {
            // Nothing else to try: a failed reboot leaves the robot running, which is the safe
            // direction, but the reason must reach the journal or this looks like a call that was
            // silently ignored.
            tracing::error!(error = %e, "reboot failed; the robot is still running");
        }
    });
}

#[cfg(target_os = "linux")]
async fn reboot() -> Result<(), String> {
    // `Reboot(false)` — false meaning "not interactive", so logind does not try to ask anyone.
    let bus = zbus::Connection::system()
        .await
        .map_err(|e| e.to_string())?;
    bus.call_method(
        Some("org.freedesktop.login1"),
        "/org/freedesktop/login1",
        Some("org.freedesktop.login1.Manager"),
        "Reboot",
        &(false),
    )
    .await
    .map_err(|e| format!("logind refused: {e}"))?;
    Ok(())
}

#[cfg(not(target_os = "linux"))]
async fn reboot() -> Result<(), String> {
    // Rebooting a developer's laptop because a test called `system.reboot` would be a memorable
    // way to learn about `cfg`.
    Err("not rebooting: this is not the robot".to_owned())
}

//! Wifi, as a trait plus a fake.
//!
//! **NetworkManager owns the credentials** (`architecture.md` §3). `configd` never stores a
//! PSK: it hands one to NM, which persists the profile root-only and reconnects on its own.
//! That is less code, better security, and one less thing to migrate — and it survives
//! `configd` being restarted, updated or rolled back.
//!
//! The trait exists for the same reason `duck-control` has `RobotIo`: the suite runs on a
//! laptop with no hardware, no network and no D-Bus, and the logic worth testing is the
//! dispatch and authorisation around this, not NM itself.

use async_trait::async_trait;
use duck_ipc_proto as proto;

/// What went wrong, in terms a caller can act on.
pub type NetResult<T> = Result<T, String>;

#[async_trait]
pub trait Net: Send + Sync {
    async fn status(&self) -> NetResult<proto::NetStatusResult>;
    async fn scan(&self) -> NetResult<proto::NetScanResult>;
    /// Join `ssid`, storing it so NM reconnects by itself next time.
    async fn connect(&self, ssid: &str, psk: Option<&str>) -> NetResult<proto::ConnectResult>;
    async fn forget(&self, ssid: &str) -> NetResult<proto::ForgetResult>;
}

/// No wifi stack at all: every call answers, and every answer says why.
///
/// What `configd` serves when it cannot reach the system bus. Refusing to start was the obvious
/// alternative and it is the wrong one — `configd` also answers `system.*`, which is where `btd`
/// gets the pairing PIN, so a `configd` that exits takes BLE provisioning down with it. That turns
/// "wifi is unavailable" into "the robot cannot be reached at all", on a board where the phone is
/// the only way in.
///
/// It is also what makes `configd` eligible for the boot recovery net: a unit may only join the set
/// if it waits for its dependency rather than exiting, so that a `failed` unit means a broken
/// release rather than a broken board (`docs/design/boot-recovery-net.md`).
///
/// `reason` is the bus error, carried into every reply rather than logged once at startup, because
/// the person who needs it is holding a phone and cannot see the journal.
pub struct UnavailableNet {
    reason: String,
    mac: Option<String>,
    iface: Option<String>,
}

impl UnavailableNet {
    pub fn new(reason: String) -> Self {
        Self {
            reason,
            mac: None,
            iface: None,
        }
    }
}

#[async_trait]
impl Net for UnavailableNet {
    /// `Unavailable` and not an error: "there is no wifi stack here" is a diagnosable answer, and
    /// the state exists in the protocol precisely to distinguish a provisioning problem from a
    /// network one. A client that gets an error instead cannot tell which it has.
    async fn status(&self) -> NetResult<proto::NetStatusResult> {
        Ok(proto::NetStatusResult {
            state: proto::NetState::Unavailable,
            ssid: None,
            signal: None,
            ip4: None,
            ip6: None,
            mac: self.mac.clone(),
            iface: self.iface.clone(),
        })
    }

    /// Empty rather than an error, for the same reason: a phone shows "no networks found", which is
    /// true, next to a status that says why.
    async fn scan(&self) -> NetResult<proto::NetScanResult> {
        Ok(proto::NetScanResult {
            networks: Vec::new(),
        })
    }

    /// Joining *is* an error. Reporting success for a network it did not join would be a lie, and
    /// silently doing nothing is worse than saying what is wrong.
    async fn connect(&self, _ssid: &str, _psk: Option<&str>) -> NetResult<proto::ConnectResult> {
        Err(self.reason.clone())
    }

    async fn forget(&self, _ssid: &str) -> NetResult<proto::ForgetResult> {
        Err(self.reason.clone())
    }
}

/// A wifi stack that exists only in memory.
///
/// Used by every test and by `--fake`, which is how the whole `net.*` surface can be exercised
/// end to end from a laptop — including the failures that are awkward to provoke against a real
/// access point, like a wrong passphrase.
pub struct FakeNet {
    inner: tokio::sync::Mutex<FakeState>,
}

struct FakeState {
    /// What the radio can see, and the key each one actually wants.
    visible: Vec<(proto::Network, Option<String>)>,
    saved: Vec<String>,
    connected: Option<String>,
}

impl FakeNet {
    /// Two networks in range: one WPA2 with a known key, one open.
    pub fn new() -> Self {
        Self::with_visible(vec![
            (
                proto::Network {
                    ssid: "Pollen".into(),
                    signal: 82,
                    security: proto::Security::WpaPsk,
                    saved: false,
                },
                Some("correct-key".to_owned()),
            ),
            (
                proto::Network {
                    ssid: "Cafe".into(),
                    signal: 41,
                    security: proto::Security::Open,
                    saved: false,
                },
                None,
            ),
        ])
    }

    pub fn with_visible(visible: Vec<(proto::Network, Option<String>)>) -> Self {
        Self {
            inner: tokio::sync::Mutex::new(FakeState {
                visible,
                saved: Vec::new(),
                connected: None,
            }),
        }
    }
}

impl Default for FakeNet {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl Net for FakeNet {
    async fn status(&self) -> NetResult<proto::NetStatusResult> {
        let state = self.inner.lock().await;
        Ok(match &state.connected {
            Some(ssid) => proto::NetStatusResult {
                state: proto::NetState::Connected,
                ssid: Some(ssid.clone()),
                signal: state
                    .visible
                    .iter()
                    .find(|(n, _)| &n.ssid == ssid)
                    .map(|(n, _)| n.signal),
                ip4: Some("192.168.50.63".into()),
                ip6: None,
                mac: Some("50:37:cd:16:1b:92".into()),
                iface: Some("wlan0".into()),
            },
            None => proto::NetStatusResult {
                state: proto::NetState::Disconnected,
                ssid: None,
                signal: None,
                ip4: None,
                ip6: None,
                mac: Some("50:37:cd:16:1b:92".into()),
                iface: Some("wlan0".into()),
            },
        })
    }

    async fn scan(&self) -> NetResult<proto::NetScanResult> {
        let state = self.inner.lock().await;
        let mut networks: Vec<proto::Network> = state
            .visible
            .iter()
            .map(|(n, _)| proto::Network {
                saved: state.saved.contains(&n.ssid),
                ..n.clone()
            })
            .collect();
        networks.sort_by_key(|n| std::cmp::Reverse(n.signal));
        Ok(proto::NetScanResult { networks })
    }

    async fn connect(&self, ssid: &str, psk: Option<&str>) -> NetResult<proto::ConnectResult> {
        let mut state = self.inner.lock().await;

        let Some((network, wanted)) = state.visible.iter().find(|(n, _)| n.ssid == ssid).cloned()
        else {
            return Ok(proto::ConnectResult::Failed {
                reason: proto::ConnectFailure::NotFound,
                detail: None,
            });
        };

        if network.security == proto::Security::Enterprise {
            return Ok(proto::ConnectResult::Failed {
                reason: proto::ConnectFailure::Unsupported,
                detail: Some("802.1X needs a certificate flow this API does not have".into()),
            });
        }
        if wanted.is_some() && psk.is_none() {
            return Ok(proto::ConnectResult::Failed {
                reason: proto::ConnectFailure::Unsupported,
                detail: Some("this network needs a passphrase".into()),
            });
        }
        if wanted.is_some() && wanted.as_deref() != psk {
            return Ok(proto::ConnectResult::Failed {
                reason: proto::ConnectFailure::BadKey,
                detail: None,
            });
        }

        state.connected = Some(ssid.to_owned());
        if !state.saved.iter().any(|s| s == ssid) {
            state.saved.push(ssid.to_owned());
        }
        Ok(proto::ConnectResult::Connected {
            ssid: ssid.to_owned(),
            ip4: Some("192.168.50.63".into()),
        })
    }

    async fn forget(&self, ssid: &str) -> NetResult<proto::ForgetResult> {
        let mut state = self.inner.lock().await;
        let before = state.saved.len();
        state.saved.retain(|s| s != ssid);
        if state.connected.as_deref() == Some(ssid) {
            state.connected = None;
        }
        Ok(proto::ForgetResult {
            removed: state.saved.len() != before,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The whole point of degrading rather than exiting: every call still answers. `status` and
    /// `scan` report the truth, and only joining — which cannot be faked — is an error, carrying
    /// the reason to a client that has no way to read the journal.
    #[tokio::test]
    async fn an_unavailable_stack_answers_everything_and_joins_nothing() {
        let net = UnavailableNet::new("cannot reach the system D-Bus (no socket)".to_owned());

        assert_eq!(
            net.status().await.unwrap().state,
            proto::NetState::Unavailable,
            "an error here would leave a client unable to tell a provisioning problem from a \
             network one"
        );
        assert!(net.scan().await.unwrap().networks.is_empty());

        let err = net.connect("Pollen", Some("key")).await.unwrap_err();
        assert!(err.contains("D-Bus"), "the reason has to travel: {err}");
        assert!(net.forget("Pollen").await.is_err());
    }

    #[tokio::test]
    async fn a_wrong_key_is_reported_as_a_wrong_key() {
        let net = FakeNet::new();
        let result = net.connect("Pollen", Some("wrong")).await.unwrap();
        assert!(matches!(
            result,
            proto::ConnectResult::Failed {
                reason: proto::ConnectFailure::BadKey,
                ..
            }
        ));
    }

    /// A secured network with no passphrase is refused before trying, and distinguishably from a
    /// wrong one — a client should ask for a password rather than say "that was wrong".
    #[tokio::test]
    async fn a_missing_key_is_not_a_wrong_key() {
        let net = FakeNet::new();
        let result = net.connect("Pollen", None).await.unwrap();
        assert!(matches!(
            result,
            proto::ConnectResult::Failed {
                reason: proto::ConnectFailure::Unsupported,
                ..
            }
        ));
    }

    #[tokio::test]
    async fn an_unknown_ssid_is_not_found() {
        let net = FakeNet::new();
        assert!(matches!(
            net.connect("Nowhere", Some("k")).await.unwrap(),
            proto::ConnectResult::Failed {
                reason: proto::ConnectFailure::NotFound,
                ..
            }
        ));
    }

    /// The whole provisioning arc: scan, join, see it stored and connected, forget it.
    #[tokio::test]
    /// The flow a phone actually produces: a passphrase typed wrong, then typed right.
    ///
    /// Worth pinning because the NM implementation got it wrong in a way no fake could show —
    /// `AddAndActivateConnection` always adds, and NM tolerates two profiles with the same id, so
    /// the corrected attempt left the bad one behind for a later boot to autoconnect with. The
    /// contract asserted here is the one that fix implements: **re-provisioning an SSID replaces
    /// its configuration; it does not accumulate.**
    async fn a_corrected_passphrase_replaces_the_bad_attempt() {
        let net = FakeNet::new();

        assert!(matches!(
            net.connect("Pollen", Some("wrong")).await.unwrap(),
            proto::ConnectResult::Failed {
                reason: proto::ConnectFailure::BadKey,
                ..
            }
        ));

        // Nothing saved by the failure. NM keeps what `AddAndActivateConnection` added even when
        // the activation fails, so the real implementation has to delete it explicitly or
        // autoconnect retries a known-bad key forever.
        assert!(
            !net.scan()
                .await
                .unwrap()
                .networks
                .iter()
                .any(|n| n.ssid == "Pollen" && n.saved),
            "a failed attempt must not leave a saved profile"
        );

        assert!(matches!(
            net.connect("Pollen", Some("correct-key")).await.unwrap(),
            proto::ConnectResult::Connected { .. }
        ));

        // One profile, not two: a single forget leaves nothing behind. Were a stale duplicate kept,
        // the second forget would also report `removed` — which is precisely the symptom that made
        // this worth a test.
        assert!(net.forget("Pollen").await.unwrap().removed);
        assert!(!net.forget("Pollen").await.unwrap().removed);
    }

    #[tokio::test]
    async fn connecting_stores_the_network_and_forgetting_removes_it() {
        let net = FakeNet::new();
        assert!(net.scan().await.unwrap().networks.iter().all(|n| !n.saved));

        assert!(matches!(
            net.connect("Pollen", Some("correct-key")).await.unwrap(),
            proto::ConnectResult::Connected { .. }
        ));

        let status = net.status().await.unwrap();
        assert_eq!(status.state, proto::NetState::Connected);
        assert_eq!(status.ssid.as_deref(), Some("Pollen"));
        assert!(status.ip4.is_some(), "connected with no address");

        let saved = net.scan().await.unwrap();
        assert!(
            saved
                .networks
                .iter()
                .find(|n| n.ssid == "Pollen")
                .unwrap()
                .saved
        );

        assert!(net.forget("Pollen").await.unwrap().removed);
        assert_eq!(
            net.status().await.unwrap().state,
            proto::NetState::Disconnected
        );
        // Forgetting again is not an error — a client must not present it as one.
        assert!(!net.forget("Pollen").await.unwrap().removed);
    }

    /// An open network needs no key, and asking with one is not an error either.
    #[tokio::test]
    async fn an_open_network_joins_without_a_key() {
        let net = FakeNet::new();
        assert!(matches!(
            net.connect("Cafe", None).await.unwrap(),
            proto::ConnectResult::Connected { .. }
        ));
    }

    /// Strongest first, because that is the order a phone shows them in.
    #[tokio::test]
    async fn scan_results_are_sorted_by_signal() {
        let net = FakeNet::new();
        let networks = net.scan().await.unwrap().networks;
        assert!(
            networks.windows(2).all(|w| w[0].signal >= w[1].signal),
            "{networks:?}"
        );
    }
}

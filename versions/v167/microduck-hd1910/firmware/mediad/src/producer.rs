//! Who this robot is, said before a session starts.
//!
//! `webrtcsink` takes a `meta` structure and the signalling server hands it to every peer in its
//! `list` answer — so a client learns which robot it found *before* it negotiates anything. The page
//! already logs that field and it has always been empty. `webrtc-console.md` §5.
//!
//! Four fields, and each has a caller:
//!
//! - **`name`** — so a page can title itself with the robot rather than with an id, and so a client
//!   that finds two producers on one network can say which is which. This is the whole of the field's
//!   value today.
//! - **`serial`** — the durable handle. A name is renamed and a peer id is per-session; the serial
//!   outlives both, which is what an app keying on a robot needs (`app-path-design.md` §8.6).
//! - **`release`** — what is running, so a client that behaves oddly against one robot can be told
//!   apart from a robot that is a release behind, without opening a session to ask.
//! - **`api_version`** — the same skew a session's `hello` reports, one round trip earlier. A client
//!   can put the banner up before it starts negotiating.
//!
//! ## The name comes from `configd`, and its absence is not a failure
//!
//! `system.info` owns the name and the serial, and `mediad` has a connection to `configd` for it
//! already. But `mediad` starts alongside `configd` rather than after it, and the unit says so
//! deliberately — `After=` and not `Requires=`, because a service being down must not keep this one
//! from starting. So this asks, waits [`ASK_TIMEOUT`], and goes on with what it knows about itself
//! either way: a producer with no name is a robot that streams, and a robot that will not stream
//! because it could not learn its own name would be a much worse trade.
//!
//! Asked once at startup rather than per peer. A rename takes effect on the next restart of this
//! daemon, which is what `configd` does to `btd`'s advertisement too — and a peer that wants the
//! live answer can call `system.info` over its own control channel.

use std::time::Duration;

use duck_ipc_proto as proto;
use tokio::sync::mpsc;

use crate::upstream::{Pool, Sockets};

/// How long `configd` gets to say who this robot is.
///
/// It is one unix-socket round trip against a daemon that answers `system.info` from memory, so this
/// is generous. It is spent once, before the pipeline exists, on a boot where every daemon is
/// starting at once — which is the only case where it is spent at all.
const ASK_TIMEOUT: Duration = Duration::from_secs(3);

/// What a peer learns about this robot from the producer list.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Producer {
    /// As `configd` has it, or `None` when it did not answer in time.
    pub name: Option<String>,
    /// The SoC serial. `None` on a board with none to read, as `system.info` reports it.
    pub serial: Option<String>,
    /// The release this process was installed as, or the build it was compiled from.
    pub release: String,
    pub api_version: u32,
    /// This robot is a duck in MuJoCo. `configd` owns the fact; this only carries it.
    ///
    /// Worth carrying rather than re-deriving from `--sim-camera`: a duck in the twin is simulated
    /// all the way down — servos, ToF and camera are all a simulator — and what a client sees
    /// should say *that*, not "this daemon happens to be reading frames off a socket".
    pub simulated: bool,
}

impl Producer {
    /// What this process knows about itself, with nothing else asked.
    ///
    /// **The release, from the path rather than from the version.** Every crate in this workspace
    /// shares one version line, so `0.9.1` names two different builds on a dev channel and the
    /// directory a release installs into is what tells them apart — the same reasoning
    /// [`proto::Identity::release`] exists for. A hand-built binary run from a home directory has no
    /// such path, and then the compiled-in build string is the honest answer rather than a version
    /// that implies a release nobody installed.
    pub fn local(build: proto::BuildInfo) -> Self {
        let release = std::env::current_exe()
            .ok()
            .and_then(|exe| proto::release_from_path(&exe.display().to_string()))
            .map(|version| version.to_string())
            .unwrap_or_else(|| build.to_string());

        Self {
            name: None,
            serial: None,
            simulated: false,
            release,
            api_version: proto::API_VERSION,
        }
    }

    /// [`Producer::local`], plus whatever `configd` says about the name and the serial.
    pub async fn learn(sockets: Sockets, build: proto::BuildInfo) -> Self {
        let mut producer = Self::local(build);

        match ask_configd(sockets).await {
            Ok(info) => {
                producer.name = Some(info.name);
                producer.serial = info.serial;
                producer.simulated = info.simulated;
            }
            // At `warn` rather than `error`: the pipeline still starts and still streams, and the
            // only cost is a producer a client cannot name. The reason is in the message because
            // "no socket" and "answered something unexpected" want different next moves.
            Err(e) => tracing::warn!(
                error = %e,
                "configd did not say who this robot is; the producer will have no name"
            ),
        }
        producer
    }

    /// The `meta` fields, as the pairs a `GstStructure` is built from.
    ///
    /// Absent fields are absent rather than empty strings: a client reading `serial: ""` has to know
    /// that means "none", where a missing key needs no convention. Keys are snake_case, as every
    /// other field on this wire is.
    pub fn fields(&self) -> Vec<(&'static str, String)> {
        let mut fields = Vec::new();
        if let Some(name) = &self.name {
            fields.push(("name", name.clone()));
        }
        if let Some(serial) = &self.serial {
            fields.push(("serial", serial.clone()));
        }
        if self.simulated {
            // Only when true, for the reason the fields above are only present when known: a
            // client reading `simulated: "false"` off every real robot learns nothing, and the key
            // is worth noticing exactly where it appears.
            fields.push(("simulated", "true".to_owned()));
        }
        fields.push(("release", self.release.clone()));
        fields.push(("api_version", self.api_version.to_string()));
        fields
    }
}

/// One `system.info` call, and the first line back.
///
/// A [`Pool`] rather than a socket opened here, so this shares the connect and write timeouts every
/// other call to a service gets rather than growing a second set of them.
async fn ask_configd(sockets: Sockets) -> Result<proto::SystemInfoResult, String> {
    let (replies_tx, mut replies_rx) = mpsc::channel::<String>(4);
    let mut pool = Pool::new(sockets, replies_tx);

    let request = serde_json::json!({
        "jsonrpc": "2.0",
        "id": 1,
        "method": proto::method::SYSTEM_INFO,
        "params": {},
    })
    .to_string();

    pool.send(proto::Service::Config, proto::Lane::Prompt, &request)
        .await
        .map_err(|e| format!("could not ask configd: {e}"))?;

    let line = tokio::time::timeout(ASK_TIMEOUT, replies_rx.recv())
        .await
        .map_err(|_| format!("configd did not answer within {ASK_TIMEOUT:?}"))?
        .ok_or_else(|| "configd closed the connection".to_owned())?;

    let reply: serde_json::Value =
        serde_json::from_str(&line).map_err(|e| format!("configd answered nonsense: {e}"))?;
    if let Some(error) = reply.get("error") {
        return Err(format!("configd refused system.info: {error}"));
    }
    serde_json::from_value(reply["result"].clone())
        .map_err(|e| format!("configd's system.info does not fit: {e}"))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn build() -> proto::BuildInfo {
        proto::BuildInfo {
            version: "0.9.1",
            revision: Some("abc1234"),
            built_at: None,
        }
    }

    /// The two fields that are always known, and the version this daemon actually speaks — not a
    /// constant copied into a page.
    #[test]
    fn what_is_known_without_asking_anything() {
        let producer = Producer::local(build());
        assert_eq!(producer.api_version, proto::API_VERSION);
        assert!(!producer.release.is_empty());
        assert_eq!(producer.name, None);
    }

    /// A client keys on what is there. An unnamed robot publishes three fields, not four with two
    /// of them empty.
    #[test]
    fn absent_fields_are_absent() {
        let fields = Producer::local(build()).fields();
        let keys: Vec<_> = fields.iter().map(|(key, _)| *key).collect();
        assert_eq!(keys, ["release", "api_version"]);
    }

    #[test]
    fn a_named_robot_publishes_the_lot() {
        let producer = Producer {
            name: Some("duck-c51b".to_owned()),
            serial: Some("3fa1c51b".to_owned()),
            ..Producer::local(build())
        };
        let fields = producer.fields();
        assert_eq!(
            fields.iter().map(|(key, _)| *key).collect::<Vec<_>>(),
            ["name", "serial", "release", "api_version"]
        );
        assert_eq!(fields[0].1, "duck-c51b");
    }

    /// The console is told too, not only the rendezvous — a page open on a simulated duck reads
    /// this same structure and should be able to say so.
    #[test]
    fn a_simulated_duck_publishes_the_key_and_a_real_one_does_not() {
        let producer = Producer {
            name: Some("duck-a".to_owned()),
            serial: Some("sim-duck-a".to_owned()),
            simulated: true,
            ..Producer::local(build())
        };
        assert_eq!(
            producer
                .fields()
                .iter()
                .map(|(k, _)| *k)
                .collect::<Vec<_>>(),
            ["name", "serial", "simulated", "release", "api_version"]
        );
        assert!(
            !Producer::local(build())
                .fields()
                .iter()
                .any(|(k, _)| *k == "simulated")
        );
    }

    /// `configd` not answering costs the name and nothing else. This is the boot case: `mediad` is
    /// `After=configd.service` and not `Requires=`, so it can and does start first.
    #[tokio::test]
    async fn a_silent_configd_still_yields_a_producer() {
        let sockets = Sockets {
            config: "/nonexistent/configd.sock".into(),
            ..Default::default()
        };
        let producer = Producer::learn(sockets, build()).await;
        assert_eq!(producer.name, None);
        assert_eq!(producer.api_version, proto::API_VERSION);
    }
}

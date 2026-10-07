//! Tests for the HTTP download layer against a real local server.
//!
//! `axum` rather than a mocking crate because the behaviour under test *is* HTTP
//! semantics — `Range` handling, a server that ignores `Range`, byte-exact bodies —
//! and stubs would only assert what I already assumed.
//!
//! What matters here, in order of how badly it would hurt:
//!
//!  1. **Resume must not corrupt.** A server that ignores `Range` returns 200 with
//!     the whole body; appending that to a partial file yields a plausible-looking
//!     file of the wrong length. The hash would catch it, but the retry would be
//!     wasted and the failure misleading.
//!  2. Progress reaches the caller, or the app's bar sticks.
//!  3. Failures say something actionable.

use std::net::SocketAddr;
use std::sync::Arc;
use std::sync::atomic::{AtomicUsize, Ordering};

use axum::Router;
use axum::extract::State;
use axum::http::{HeaderMap, StatusCode, header};
use axum::response::IntoResponse;
use axum::routing::get;
use updater::source::http;

/// Body served by the test endpoints. Large enough to arrive in several chunks.
fn body() -> Vec<u8> {
    (0..200_000u32).map(|i| (i % 251) as u8).collect()
}

#[derive(Default)]
struct Counters {
    /// Requests that arrived with a `Range` header.
    ranged: AtomicUsize,
    /// Total requests, for asserting a retry actually happened.
    total: AtomicUsize,
}

/// Honours `Range: bytes=N-` with a 206, like GitHub and HF do.
async fn ranged(State(counters): State<Arc<Counters>>, headers: HeaderMap) -> impl IntoResponse {
    counters.total.fetch_add(1, Ordering::Relaxed);
    let full = body();

    let Some(range) = headers.get(header::RANGE).and_then(|v| v.to_str().ok()) else {
        return (StatusCode::OK, full).into_response();
    };
    counters.ranged.fetch_add(1, Ordering::Relaxed);

    let start: usize = range
        .trim_start_matches("bytes=")
        .trim_end_matches('-')
        .parse()
        .unwrap_or(0);
    let tail = full[start.min(full.len())..].to_vec();

    let mut response_headers = HeaderMap::new();
    response_headers.insert(
        header::CONTENT_RANGE,
        format!("bytes {start}-{}/{}", full.len() - 1, full.len())
            .parse()
            .unwrap(),
    );
    (StatusCode::PARTIAL_CONTENT, response_headers, tail).into_response()
}

/// Deliberately ignores `Range`, always returning the whole body with a 200.
///
/// Legal HTTP, and the case that would corrupt a naive resume.
async fn ignores_range(State(counters): State<Arc<Counters>>) -> impl IntoResponse {
    counters.total.fetch_add(1, Ordering::Relaxed);
    (StatusCode::OK, body())
}

async fn not_found(State(counters): State<Arc<Counters>>) -> impl IntoResponse {
    counters.total.fetch_add(1, Ordering::Relaxed);
    (StatusCode::NOT_FOUND, "nope")
}

/// Fails with a 500 until the third attempt, then succeeds — a mirror having a bad
/// minute, which is exactly what retries are for.
async fn flaky(State(counters): State<Arc<Counters>>) -> impl IntoResponse {
    let seen = counters.total.fetch_add(1, Ordering::Relaxed);
    if seen < 2 {
        (StatusCode::INTERNAL_SERVER_ERROR, Vec::new()).into_response()
    } else {
        (StatusCode::OK, body()).into_response()
    }
}

async fn forbidden() -> impl IntoResponse {
    (StatusCode::FORBIDDEN, "nope")
}

/// Serve on an ephemeral port and return its address plus the shared counters.
async fn serve() -> (SocketAddr, Arc<Counters>) {
    let counters = Arc::new(Counters::default());
    let app = Router::new()
        .route("/ranged", get(ranged))
        .route("/ignores-range", get(ignores_range))
        .route("/missing", get(not_found))
        .route("/flaky", get(flaky))
        .route("/forbidden", get(forbidden))
        .with_state(Arc::clone(&counters));

    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    tokio::spawn(async move {
        let _ = axum::serve(listener, app).await;
    });
    (addr, counters)
}

/// `(bytes_so_far, total_if_known)` — the shape `ProgressSink` carries.
type ProgressUpdate = (u64, Option<u64>);

fn progress_channel() -> (
    tokio::sync::mpsc::UnboundedSender<ProgressUpdate>,
    tokio::sync::mpsc::UnboundedReceiver<ProgressUpdate>,
) {
    tokio::sync::mpsc::unbounded_channel()
}

#[tokio::test]
async fn downloads_a_whole_file_and_reports_progress() {
    let (addr, _counters) = serve().await;
    let dir = tempfile::tempdir().unwrap();
    let dest = dir.path().join("artifact.bin");

    let (tx, mut rx) = progress_channel();
    let written = http::download_to(
        &http::client().unwrap(),
        &format!("http://{addr}/ranged"),
        &dest,
        // No Accept header: these serve bytes directly, unlike GitHub's asset API.
        None,
        &tx,
    )
    .await
    .unwrap();
    drop(tx);

    assert_eq!(written, body().len() as u64);
    assert_eq!(std::fs::read(&dest).unwrap(), body());

    let mut updates = Vec::new();
    while let Some(update) = rx.recv().await {
        updates.push(update);
    }
    assert!(!updates.is_empty(), "no progress reported");

    // The final update must reach the true total, or the app's bar stops short.
    let (done, total) = *updates.last().unwrap();
    assert_eq!(done, body().len() as u64);
    assert_eq!(total, Some(body().len() as u64));

    // And progress must be monotonic — a bar that goes backwards reads as a bug.
    assert!(updates.windows(2).all(|w| w[0].0 <= w[1].0));
}

#[tokio::test]
async fn resumes_from_a_partial_file() {
    let (addr, counters) = serve().await;
    let dir = tempfile::tempdir().unwrap();
    let dest = dir.path().join("artifact.bin");

    // Pretend a previous attempt got a third of the way.
    let partial = &body()[..70_000];
    std::fs::write(&dest, partial).unwrap();

    let (tx, _rx) = progress_channel();
    let written = http::download_to(
        &http::client().unwrap(),
        &format!("http://{addr}/ranged"),
        &dest,
        // No Accept header: these serve bytes directly, unlike GitHub's asset API.
        None,
        &tx,
    )
    .await
    .unwrap();

    assert_eq!(written, body().len() as u64);
    assert_eq!(
        std::fs::read(&dest).unwrap(),
        body(),
        "resumed file must match byte for byte"
    );
    assert_eq!(
        counters.ranged.load(Ordering::Relaxed),
        1,
        "should have sent a Range header"
    );
}

/// The corruption case: a server that ignores `Range` sends the whole body with a
/// 200. Appending it to a partial file would produce a too-long file.
#[tokio::test]
async fn restarts_when_the_server_ignores_range() {
    let (addr, _counters) = serve().await;
    let dir = tempfile::tempdir().unwrap();
    let dest = dir.path().join("artifact.bin");

    std::fs::write(&dest, &body()[..70_000]).unwrap();

    let (tx, _rx) = progress_channel();
    let written = http::download_to(
        &http::client().unwrap(),
        &format!("http://{addr}/ignores-range"),
        &dest,
        // No Accept header: these serve bytes directly, unlike GitHub's asset API.
        None,
        &tx,
    )
    .await
    .unwrap();

    assert_eq!(
        written,
        body().len() as u64,
        "a 200 reply must restart, not append"
    );
    assert_eq!(std::fs::read(&dest).unwrap(), body());
}

/// A 404 is permanent — wrong repo, tag, or asset name. Retrying it four times with
/// backoff only delays a clear error, so it must fail immediately.
#[tokio::test]
async fn a_missing_artifact_fails_immediately_without_retrying() {
    let (addr, counters) = serve().await;
    let dir = tempfile::tempdir().unwrap();
    let dest = dir.path().join("x.bin");

    let started = std::time::Instant::now();
    let (tx, _rx) = progress_channel();
    let err = http::download_to(
        &http::client().unwrap(),
        &format!("http://{addr}/missing"),
        &dest,
        // No Accept header: these serve bytes directly, unlike GitHub's asset API.
        None,
        &tx,
    )
    .await
    .unwrap_err();

    assert!(matches!(err, updater::Error::Network(_)), "got {err:?}");
    assert!(err.to_string().contains("404"), "{err}");
    // The hint is what stops someone hunting through logs.
    assert!(err.to_string().contains("wrong repo"), "{err}");

    assert_eq!(
        counters.total.load(Ordering::Relaxed),
        1,
        "a permanent failure must not be retried"
    );
    assert!(
        started.elapsed() < std::time::Duration::from_secs(1),
        "should fail fast, took {:?}",
        started.elapsed()
    );
    assert!(
        !dest.exists(),
        "a rejected request must not leave a partial file behind"
    );
}

/// A 5xx is transient — a mirror having a bad minute — so it *must* be retried.
#[tokio::test]
async fn a_server_error_is_retried_until_it_succeeds() {
    let (addr, counters) = serve().await;
    let dir = tempfile::tempdir().unwrap();
    let dest = dir.path().join("artifact.bin");

    let (tx, _rx) = progress_channel();
    let written = http::download_to(
        &http::client().unwrap(),
        &format!("http://{addr}/flaky"),
        &dest,
        // No Accept header: these serve bytes directly, unlike GitHub's asset API.
        None,
        &tx,
    )
    .await
    .expect("should recover after transient failures");

    assert_eq!(written, body().len() as u64);
    assert_eq!(std::fs::read(&dest).unwrap(), body());
    assert_eq!(
        counters.total.load(Ordering::Relaxed),
        3,
        "two failures then a success"
    );
}

#[tokio::test]
async fn get_bytes_reads_small_resources() {
    let (addr, _counters) = serve().await;
    let bytes = http::get_bytes(
        &http::client().unwrap(),
        &format!("http://{addr}/ranged"),
        None,
    )
    .await;
    // The test body is under the metadata ceiling, so this succeeds; the point is
    // that get_bytes round-trips a real response.
    assert_eq!(bytes.unwrap(), body());
}

#[tokio::test]
async fn get_bytes_maps_403_to_a_token_hint() {
    let (addr, _counters) = serve().await;
    let err = http::get_bytes(
        &http::client().unwrap(),
        &format!("http://{addr}/forbidden"),
        None,
    )
    .await
    .unwrap_err();

    assert!(err.to_string().contains("GITHUB_TOKEN"), "{err}");
}

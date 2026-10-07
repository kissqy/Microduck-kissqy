//! The ToF theremin: a hand's distance in front of the beak becomes a note.
//!
//! Three things have to meet for that, and they run at three different rates. The depth
//! frames arrive from `tofd` at 15 Hz over a socket this daemon does not own. The control
//! loop runs at 50 Hz and is the only thing allowed to touch the mouth. The audio is
//! rendered at 48 kHz in a writer thread. This module is where the first two meet: a reader
//! thread parks on the depth socket and leaves the newest frame in a slot, and
//! [`Theremin::tick`] — called from the control loop, never blocking — turns whatever is in
//! that slot into a note, a mouth opening, and a line of state for clients to watch.
//!
//! **One gesture, three outputs.** Closeness (0 at the far end of the playable band, 1 at
//! the near end, from [`kinematics::hand`]) drives the pitch, the level, *and* how far the
//! mouth opens. Not three tunings of the same thing but literally one number, because a duck
//! whose mouth opens on a different curve from its pitch reads as a mouth animation playing
//! over a sound rather than as an animal making one.
//!
//! **An explicit mode, and nothing clever inside it.** The first version armed: it captured
//! what was in front of the duck as a background so it could tell a hand from a wall without
//! being told. On a bench that worked; on a duck the same gesture armed one moment and was
//! refused the next, because *which zones carry a usable status varies frame to frame* and a
//! background is only as stable as the frames it was averaged from. So the mode is now
//! something you turn on, and while it is on the nearest return in the band is the hand —
//! see [`kinematics::hand`] for what is left and why. The state machine here is two states,
//! and the only judgement it makes is about the *sensor*: is a frame recent enough to play.
//!
//! **Rate mismatch is a fade, not a gate.** A depth frame that stops arriving — `tofd`
//! restarted, the sensor dropped off the bus — must not leave a note sounding forever, and
//! must not chop one off either. A frame older than [`FRAME_STALE`] takes the level to zero
//! and leaves everything else alone, so the instrument goes quiet and comes back when the
//! frames do. Short dropouts never reach here at all: `hand::Tracker` bridges those.

use std::io::{BufRead, BufReader, Write};
use std::os::unix::net::UnixStream;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::{Duration, Instant};

use arc_swap::ArcSwapOption;
use duck_ipc_proto as proto;
use kinematics::hand::{self, Tracker};

/// How long a depth frame stays playable.
///
/// Longer than the tracker's own hold, and doing a different job: the tracker bridges a
/// sensor that fumbled a zone, this notices a sensor that has stopped talking at all.
const FRAME_STALE: Duration = Duration::from_millis(500);

/// How fast the reader thread retries a depth socket that is not there. `tofd` may be
/// restarting, or may not be running at all on a duck without the sensor — either way this is
/// a background thread and its failure is a log line, not an error anybody waits on.
const RECONNECT: Duration = Duration::from_secs(2);

/// Request id for the subscription. Any number; `tofd` echoes it.
const SUBSCRIBE_ID: u64 = 1;

/// One depth frame, as the wire sent it.
///
/// Kept raw — distances and status bytes, uninterpreted — because which statuses count is
/// [`hand::Config`]'s decision and it is the decision this feature turned out to hinge on.
/// Interpreting here would have buried it.
struct Frame {
    distance_mm: Vec<i16>,
    status: Vec<u8>,
    at: Instant,
}

/// What one tick of the theremin produced.
///
/// Deliberately *not* a frequency: mapping closeness to a note needs this duck's register,
/// which lives with its voice (`crate::sound::Sound::theremin_hz_at`) and not with its depth
/// sensor. This module says how close the hand is; the voice says what that sounds like.
#[derive(Debug, Clone, PartialEq)]
pub struct Note {
    /// Mouth opening to drive, 0..1. Always present while the instrument is up, because a
    /// silent theremin is a *closed* mouth and that has to be commanded too.
    pub mouth: f64,
    /// The state block for `robot.state`. `note_hz` is left for the caller to fill, for the
    /// reason above.
    pub state: proto::ThereminState,
    /// Where the hand is in the playable band, 0 far to 1 near. `None` is silence.
    pub closeness: Option<f64>,
}

pub struct Theremin {
    /// Newest frame from the reader thread. `ArcSwapOption` for the reason every other intent
    /// slot is one: the loop does an atomic load and can never be held up by the thread
    /// writing the other side.
    latest: Arc<ArcSwapOption<Frame>>,
    tracker: Tracker,
    /// Up or down. The whole state machine — see the module docs for what used to be here.
    active: bool,
}

impl Theremin {
    /// Start the depth reader and hold an instrument that is down.
    ///
    /// The reader runs whether or not a theremin is ever asked for: it is one parked read on a
    /// socket, and connecting lazily would make picking the instrument up wait for a
    /// connection as well as for frames.
    pub fn spawn(socket: PathBuf, config: hand::Config) -> Self {
        let theremin = Self::new(config);
        let slot = theremin.latest.clone();
        let spawned = std::thread::Builder::new()
            .name("tof-reader".into())
            .spawn(move || read_frames(&socket, &slot));
        if spawned.is_err() {
            tracing::warn!("cannot spawn the depth reader; no theremin");
        }
        theremin
    }

    /// An instrument with no depth reader behind it — frames are whatever is put in the slot.
    ///
    /// Exists for the tests, and it is not a convenience: a reader pointed at a socket nobody
    /// answers on clears the slot the moment its connect fails, which under a parallel suite
    /// wiped the frame a test had just pushed. A construction that starts no thread is the
    /// difference between a deterministic test and an intermittent one.
    fn new(config: hand::Config) -> Self {
        Self {
            latest: Arc::new(ArcSwapOption::empty()),
            tracker: Tracker::new(config),
            active: false,
        }
    }

    #[cfg(test)]
    fn active(&self) -> bool {
        self.active
    }

    /// Whether depth frames are arriving at all. What a refusal at the door is made of:
    /// accepting a theremin on a duck with no sensor would be a feature that silently does
    /// nothing.
    pub fn has_frames(&self) -> bool {
        self.latest
            .load()
            .as_ref()
            .is_some_and(|frame| frame.at.elapsed() < FRAME_STALE)
    }

    /// Pick the instrument up, or put it down.
    pub fn set_active(&mut self, active: bool) {
        if active != self.active {
            tracing::warn!(active, "theremin");
        }
        self.active = active;
        // Held notes do not survive being put down: picking the instrument back up must not
        // open with a note from the last time.
        self.tracker.reset();
    }

    /// One tick. Never blocks, and returns `None` when there is nothing for the loop to do.
    pub fn tick(&mut self, now: Instant) -> Option<Note> {
        if !self.active {
            return None;
        }
        let frame = self.latest.load_full();
        let fresh = frame
            .as_ref()
            .filter(|frame| frame.at.elapsed() < FRAME_STALE);

        // A silent sensor is silence with the instrument still in hand: it plays again the
        // moment frames return, rather than needing to be picked up afresh.
        let Some(frame) = fresh else {
            self.tracker.reset();
            return Some(Note {
                mouth: 0.0,
                state: proto::ThereminState {
                    sensor: Some("no depth frames".to_owned()),
                    ..Default::default()
                },
                closeness: None,
            });
        };

        let hand = self.tracker.track(&frame.distance_mm, &frame.status, now);
        let closeness = hand.map(|h| h.closeness);
        Some(Note {
            // A silent theremin closes the beak; a played one opens it as far as the note is
            // high, which is the same number.
            mouth: closeness.unwrap_or(0.0),
            state: proto::ThereminState {
                hand_range_m: hand.map(|h| h.range_m),
                zones: hand.map_or(0, |h| h.zones) as u32,
                held: hand.is_some_and(|h| h.held),
                // The one diagnostic that would have found the first version's bug in a
                // minute instead of a session: what the sensor is actually saying about each
                // zone, rather than what this build makes of it.
                sensor: Some(describe(&frame.status, self.tracker.config())),
                note_hz: None,
                mouth: closeness.unwrap_or(0.0),
            },
            closeness,
        })
    }
}

/// The frame's status bytes as a line: how many zones each code covers, and how many of those
/// this build believes.
fn describe(status: &[u8], config: &hand::Config) -> String {
    let histogram = hand::status_histogram(status);
    let believed: usize = histogram
        .iter()
        .filter(|(code, _)| config.believes(*code))
        .map(|(_, count)| count)
        .sum();
    let codes: Vec<String> = histogram
        .iter()
        .map(|(code, count)| {
            // A marker on the codes this build acts on, so "the sensor is talking but we are
            // ignoring it" is visible at a glance rather than needing the config to hand.
            let mark = if config.believes(*code) { "*" } else { "" };
            format!("{code}{mark}:{count}")
        })
        .collect();
    format!("{believed} usable · {}", codes.join(" "))
}

/// Park on `tofd`'s depth stream, forever, leaving the newest frame in `slot`.
fn read_frames(socket: &Path, slot: &ArcSwapOption<Frame>) {
    loop {
        if let Err(why) = stream_frames(socket, slot) {
            tracing::debug!(why, "theremin: the depth stream ended");
        }
        // Nothing is playable without frames, and `tick` already treats a stale frame as
        // silence — so clear the slot rather than leaving a note hanging on the last thing
        // the sensor said before it went away.
        slot.store(None);
        std::thread::sleep(RECONNECT);
    }
}

/// One connection, from its subscribe to whatever ended it.
fn stream_frames(socket: &Path, slot: &ArcSwapOption<Frame>) -> Result<(), String> {
    let stream = UnixStream::connect(socket).map_err(|e| format!("connect: {e}"))?;
    let mut writer = stream.try_clone().map_err(|e| format!("clone: {e}"))?;
    let request = proto::Request::call(proto::Id::Number(SUBSCRIBE_ID), &proto::Call::TofStream);
    let line = serde_json::to_string(&request).map_err(|e| format!("encode: {e}"))?;
    writer
        .write_all(format!("{line}\n").as_bytes())
        .map_err(|e| format!("subscribe: {e}"))?;

    let mut reader = BufReader::new(stream);
    let mut line = String::new();
    loop {
        line.clear();
        match reader.read_line(&mut line) {
            Err(e) => return Err(format!("read: {e}")),
            Ok(0) => return Err("tofd closed the stream".to_owned()),
            Ok(_) => {}
        }
        // The subscription's answer names the sensor; everything after it is a frame.
        // Anything else is skipped rather than treated as an end — a future `tofd` may say
        // more than this build knows how to read.
        if let Ok(response) = serde_json::from_str::<proto::Response>(&line)
            && let Ok(status) = response.result_as::<proto::TofStreamResult>()
        {
            tracing::warn!(
                sensor = status.sensor.as_deref().unwrap_or("none"),
                unavailable = status.unavailable.as_deref().unwrap_or(""),
                hz = status.hz,
                "theremin: subscribed to the depth stream"
            );
            continue;
        }
        let Some(wire) = serde_json::from_str::<proto::Request>(&line)
            .ok()
            .and_then(|r| r.as_tof_frame())
        else {
            continue;
        };
        slot.store(Some(Arc::new(Frame {
            distance_mm: wire.distance_mm,
            status: wire.status,
            at: Instant::now(),
        })));
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn theremin() -> Theremin {
        // No reader thread: frames are pushed in directly. See `Theremin::new`.
        Theremin::new(hand::Config::default())
    }

    /// A frame with `zones` zones at `distance_m` carrying `code`, the rest reporting nothing.
    fn frame(distance_m: f64, code: u8, zones: usize) -> (Vec<i16>, Vec<u8>) {
        let mut distance = vec![0i16; 64];
        let mut status = vec![255u8; 64];
        for zone in 0..zones.min(64) {
            distance[zone] = (distance_m * 1000.0) as i16;
            status[zone] = code;
        }
        (distance, status)
    }

    fn push(t: &Theremin, distance_m: f64, code: u8, zones: usize) {
        let (distance_mm, status) = frame(distance_m, code, zones);
        t.latest.store(Some(Arc::new(Frame {
            distance_mm,
            status,
            at: Instant::now(),
        })));
    }

    /// A theremin that was never picked up produces nothing at all — not silence, nothing:
    /// the loop must not be commanding a mouth for a feature nobody asked for.
    #[test]
    fn a_theremin_that_is_down_says_nothing() {
        let mut t = theremin();
        assert!(!t.active());
        push(&t, 0.3, 5, 8);
        assert!(t.tick(Instant::now()).is_none());
    }

    /// Picked up, it plays at once — no arming, no window, no waiting. That immediacy is the
    /// point of the rewrite.
    #[test]
    fn it_plays_on_the_first_frame_after_being_picked_up() {
        let mut t = theremin();
        t.set_active(true);
        push(&t, 0.30, 5, 8);
        let note = t.tick(Instant::now()).expect("up");
        let range = note.state.hand_range_m.expect("a hand");
        assert!((range - 0.30).abs() < 0.01, "{range}");
        assert!(note.mouth > 0.0, "the beak opens on a note");
        assert_eq!(note.mouth, note.state.mouth);
        assert_eq!(note.state.zones, 8);
    }

    /// The regression that sent this back to the drawing board: a hand at 40 cm arrives with
    /// a consistency-failure status, and the theremin must play it.
    #[test]
    fn a_hand_past_thirty_centimetres_plays() {
        let mut t = theremin();
        t.set_active(true);
        for code in [4u8, 13] {
            for distance in [0.35, 0.45, 0.60] {
                push(&t, distance, code, 6);
                let note = t.tick(Instant::now()).expect("up");
                let range = note
                    .state
                    .hand_range_m
                    .unwrap_or_else(|| panic!("status {code} at {distance} m must play"));
                assert!((range - distance).abs() < 0.01);
            }
        }
    }

    /// Closer is higher *and* wider: the mouth opening and the pitch are one number, so the
    /// two can never drift apart into a mouth animation over a sound.
    #[test]
    fn the_mouth_opens_with_the_note() {
        let mut t = theremin();
        t.set_active(true);
        let at = |t: &mut Theremin, distance: f64| {
            push(t, distance, 5, 8);
            t.tick(Instant::now()).expect("up").mouth
        };
        let far = at(&mut t, 0.65);
        let mid = at(&mut t, 0.40);
        let near = at(&mut t, 0.12);
        assert!(far < mid && mid < near, "{far} {mid} {near}");
        assert!(
            near > 0.8,
            "a hand at the near end opens the beak wide: {near}"
        );
    }

    /// The readout has to say what the sensor said, not what this build made of it — the
    /// diagnostic that would have found the status bug immediately.
    #[test]
    fn the_state_reports_what_the_sensor_actually_said() {
        let mut t = theremin();
        t.set_active(true);
        // Half the frame consistency-failed, the rest saw nothing.
        push(&t, 0.40, 4, 32);
        let note = t.tick(Instant::now()).expect("up");
        let sensor = note
            .state
            .sensor
            .expect("the sensor line is always present");
        assert!(sensor.starts_with("32 usable"), "{sensor}");
        assert!(
            sensor.contains("4*:32"),
            "believed codes are marked: {sensor}"
        );
        assert!(sensor.contains("255:32"), "{sensor}");

        // A frame this build ignores entirely still reports itself, and says zero usable —
        // which is the difference between "no sensor" and "a sensor we are not listening to".
        // On a fresh instrument, so the hold is not bridging the previous frame's hand.
        let mut fresh = theremin();
        fresh.set_active(true);
        push(&fresh, 0.40, 1, 64);
        let note = fresh.tick(Instant::now()).expect("up");
        let sensor = note.state.sensor.expect("present");
        assert!(sensor.starts_with("0 usable"), "{sensor}");
        assert!(sensor.contains("1:64"), "{sensor}");
        assert_eq!(note.state.hand_range_m, None);

        // And on the instrument that *was* playing, that same frame is a bridged dropout
        // rather than a silence — reported as held, so the readout can say so.
        push(&t, 0.40, 1, 64);
        let note = t.tick(Instant::now()).expect("up");
        assert!(note.state.held, "{:?}", note.state);
        assert_eq!(note.state.hand_range_m, Some(0.40));
    }

    /// A sensor that stops delivering falls silent with the instrument still in hand, and
    /// plays again when it comes back.
    #[test]
    fn a_stale_frame_is_silence_and_the_instrument_stays_up() {
        let mut t = theremin();
        t.set_active(true);
        push(&t, 0.25, 5, 8);
        assert!(t.tick(Instant::now()).expect("up").mouth > 0.0);

        let (distance_mm, status) = frame(0.25, 5, 8);
        t.latest.store(Some(Arc::new(Frame {
            distance_mm,
            status,
            at: Instant::now() - FRAME_STALE * 2,
        })));
        let note = t.tick(Instant::now()).expect("still up");
        assert_eq!(note.mouth, 0.0, "a dead sensor closes the beak");
        assert_eq!(note.closeness, None);
        assert_eq!(note.state.sensor.as_deref(), Some("no depth frames"));
        assert!(
            t.active(),
            "the instrument is not taken away by a quiet sensor"
        );

        push(&t, 0.25, 5, 8);
        assert!(t.tick(Instant::now()).expect("up").mouth > 0.0);
    }

    /// A dropped frame does not chop the note — the chop was the loudest thing wrong with the
    /// first version on a real duck.
    #[test]
    fn a_flickering_sensor_does_not_chop_the_note() {
        let mut t = theremin();
        t.set_active(true);
        let mut played = 0;
        // An explicit clock, not `Instant::now()`: the hold is a duration, and a test that
        // read the wall clock would depend on whether its thread was descheduled — which it
        // duly was, under a parallel suite. The frames are pushed fresh each step so only the
        // hold is under test.
        let start = Instant::now();
        // Alternate usable and unusable frames, as the sensor does at the edge of its range.
        for step in 0..20 {
            if step % 2 == 0 {
                push(&t, 0.35, 5, 6);
            } else {
                push(&t, 0.35, 1, 6);
            }
            let note = t
                .tick(start + Duration::from_millis(66 * step))
                .expect("up");
            if note.closeness.is_some() {
                played += 1;
            }
        }
        assert_eq!(played, 20, "every frame must sound, half of them held");
    }

    /// Putting the instrument down forgets the held note, so picking it back up does not open
    /// with a note from before.
    #[test]
    fn putting_it_down_forgets_the_held_note() {
        let mut t = theremin();
        t.set_active(true);
        push(&t, 0.25, 5, 8);
        assert!(t.tick(Instant::now()).expect("up").closeness.is_some());

        t.set_active(false);
        assert!(t.tick(Instant::now()).is_none());

        // Up again, with a frame carrying nothing: silence, not the old note.
        t.set_active(true);
        push(&t, 0.25, 1, 8);
        let note = t.tick(Instant::now()).expect("up");
        assert_eq!(note.closeness, None);
        assert_eq!(note.mouth, 0.0);
    }
}

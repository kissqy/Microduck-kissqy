//! The preset gestures — `look_up`, `look_around`, `circle`, `quack` — played by the control
//! loop instead of a client.
//!
//! Ported from `duckphone/actions.py`, where the player had to be a Python thread because a
//! phone could only send intents. A phone with no Python host cannot run that thread, and the
//! daemon already owns the head and the mouth: the gestures live here so the web page, the
//! console and the Bluetooth app get the same motion from one implementation.
//!
//! Two halves, exactly as `intents.rs` splits a request from the loop:
//!
//!  - [`Handle`] is what the IPC side touches. It is in [`RobotState`](crate::RobotState), so a
//!    request does not have to reach the loop to be queued, and a state frame can say what is
//!    playing without the loop answering a question.
//!  - [`Player`] is the loop's own. It is `&mut` and lives on the control thread; [`Player::tick`]
//!    runs once per tick, before the snapshot the loop reads, so a gesture's head arrives on the
//!    same tick it was written.
//!
//! **A user intent stops a gesture but does not zero anything.** The client and the loop race,
//! and writing head back on the way out would fight a `robot.head` that arrived in the same
//! millisecond. The one exception is the mouth a `quack` opened: nothing else closes it, so
//! stopping leaves a beak hanging open. See [`Command`].

use std::sync::Mutex;
use std::sync::atomic::{AtomicBool, AtomicU8, Ordering};
use std::time::Instant;

use duck_ipc_proto as proto;

use crate::intents::{Intents, PoseIntent};

/// One of the four gestures [`proto::method::ROBOT_ACTION`] names.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Action {
    LookUp,
    LookAround,
    Circle,
    Quack,
}

impl Action {
    /// The name a client sends, or `None` for a name this release does not have.
    pub fn from_name(name: &str) -> Option<Self> {
        match name {
            "look_up" => Some(Self::LookUp),
            "look_around" => Some(Self::LookAround),
            "circle" => Some(Self::Circle),
            "quack" => Some(Self::Quack),
            _ => None,
        }
    }

    pub fn name(self) -> &'static str {
        match self {
            Self::LookUp => "look_up",
            Self::LookAround => "look_around",
            Self::Circle => "circle",
            Self::Quack => "quack",
        }
    }

    /// The voice-bank tag this gesture beats out.
    fn sound(self) -> proto::SoundTag {
        match self {
            Self::LookUp => proto::SoundTag::Coo,
            Self::LookAround => proto::SoundTag::Inquire,
            Self::Circle => proto::SoundTag::Greet,
            Self::Quack => proto::SoundTag::Chirp,
        }
    }

    /// How long the gesture runs, seconds.
    pub fn duration(self) -> f64 {
        match self {
            Self::LookUp => 1.2,
            Self::LookAround => 1.6,
            // Three turns at a 1.3 s period.
            Self::Circle => 3.9,
            Self::Quack => 2.1,
        }
    }

    /// When the sound beats land, seconds from the start. Beat 0 is played as the gesture
    /// begins; the rest are played as the clock crosses them.
    fn beats(self) -> &'static [f64] {
        match self {
            Self::LookUp => &[0.0, 0.7],
            Self::LookAround => &[0.0, 0.6, 1.2],
            Self::Circle => &[0.0, 0.8, 1.6, 2.4, 3.2],
            Self::Quack => &[0.0, 0.7, 1.4],
        }
    }

    /// The head this gesture wants at `elapsed` seconds, or `None` for a gesture that only moves
    /// the mouth.
    ///
    /// The numbers are the Python player's, unchanged: the point of moving the gestures down is
    /// that the duck looks the same from every client.
    fn head_at(self, elapsed: f64) -> Option<[f64; 4]> {
        match self {
            Self::LookUp => Some([0.0, -0.30, 0.0, 0.0]),
            Self::LookAround => {
                // Eight hundred milliseconds each way, held.
                let yaw = if elapsed < 0.8 { 0.30 } else { -0.30 };
                Some([0.0, -0.18, yaw, 0.0])
            }
            Self::Circle => {
                let phase = 2.0 * std::f64::consts::PI * elapsed / CIRCLE_PERIOD;
                Some([
                    0.0,
                    -0.20 + 0.25 * phase.cos(),
                    1.00 * phase.sin(),
                    0.08 * phase.sin(),
                ])
            }
            Self::Quack => None,
        }
    }

    /// The mouth at `elapsed` seconds for the one gesture that uses it.
    fn mouth_at(self, elapsed: f64) -> Option<f64> {
        match self {
            Self::Quack => Some(if elapsed % QUACK_CYCLE < QUACK_OPEN_S {
                0.9
            } else {
                0.0
            }),
            _ => None,
        }
    }

    fn code(self) -> u8 {
        match self {
            Self::LookUp => 1,
            Self::LookAround => 2,
            Self::Circle => 3,
            Self::Quack => 4,
        }
    }

    fn from_code(code: u8) -> Option<Self> {
        match code {
            1 => Some(Self::LookUp),
            2 => Some(Self::LookAround),
            3 => Some(Self::Circle),
            4 => Some(Self::Quack),
            _ => None,
        }
    }
}

const CIRCLE_PERIOD: f64 = 1.3;
const QUACK_CYCLE: f64 = 0.7;
const QUACK_OPEN_S: f64 = 0.35;

/// What the IPC side asked for, once. Taken by the next [`Player::tick`].
#[derive(Debug, Clone, Copy)]
pub enum Command {
    Start {
        action: Action,
        idle: bool,
        sound: bool,
    },
    /// An explicit `robot.action {}`: stop, and neutralise what the gesture left behind.
    Cancel,
    /// A user intent: stop, but write nothing back. See the module comment.
    Stop,
}

/// The gesture slot shared between the IPC side and the control loop.
#[derive(Debug)]
pub struct Handle {
    pending: Mutex<Option<Command>>,
    /// [`Action::code`], or 0 for none — what [`proto::RobotState::act`] reports.
    current: AtomicU8,
    idle: AtomicBool,
    /// The loop's gate verdict from its last tick, so `robot.action` can refuse a gesture on a
    /// robot it is not safe to gesture from rather than accepting and dropping it.
    ready: AtomicBool,
}

impl Default for Handle {
    fn default() -> Self {
        Self {
            pending: Mutex::new(None),
            current: AtomicU8::new(0),
            idle: AtomicBool::new(false),
            ready: AtomicBool::new(false),
        }
    }
}

impl Handle {
    /// Queue a gesture, replacing whatever is playing.
    pub fn start(&self, action: Action, idle: bool, sound: bool) {
        self.queue(Command::Start {
            action,
            idle,
            sound,
        });
    }

    /// Explicit cancel: stop, and put the robot back the way it was.
    pub fn cancel(&self) {
        self.queue(Command::Cancel);
    }

    /// A user intent: stop, and leave the head and body where the user's last command put them.
    pub fn stop(&self) {
        self.queue(Command::Stop);
    }

    fn queue(&self, command: Command) {
        // A lock poisoned by a panicking loop is not a reason to refuse an intent — the loop is
        // gone and the robot is holding anyway.
        if let Ok(mut pending) = self.pending.lock() {
            *pending = Some(command);
        }
    }

    /// Whether the loop's last tick considered a gesture safe. False until the first tick.
    pub fn ready(&self) -> bool {
        self.ready.load(Ordering::Relaxed)
    }

    /// The gesture playing now, by name.
    pub fn current(&self) -> Option<&'static str> {
        Action::from_code(self.current.load(Ordering::Relaxed)).map(Action::name)
    }

    /// Whether the playing gesture was chosen by the idle director. Only meaningful with
    /// [`Self::current`].
    pub fn idle(&self) -> bool {
        self.idle.load(Ordering::Relaxed)
    }

    fn publish(&self, action: Option<Action>, idle: bool) {
        self.current
            .store(action.map_or(0, Action::code), Ordering::Relaxed);
        self.idle.store(idle, Ordering::Relaxed);
    }
}

/// The control loop's half: one gesture at a time, on the loop's own thread.
#[derive(Debug, Default)]
pub struct Player {
    running: Option<Running>,
}

#[derive(Debug)]
struct Running {
    action: Action,
    sound: bool,
    started: Instant,
    /// The next beat in [`Action::beats`] that has not been played. Beat 0 is played on start.
    beat: usize,
}

impl Player {
    /// One tick: take whatever was queued, then advance the gesture if one is running.
    ///
    /// `ready` is the gate computed by the caller — the loop is the only place that sees homed,
    /// enabled, the fall verdict, the limp-fall sequence and the live twist together.
    pub fn tick(&mut self, now: Instant, handle: &Handle, intents: &Intents, ready: bool) {
        handle.ready.store(ready, Ordering::Relaxed);

        if let Some(command) = handle.pending.lock().ok().and_then(|mut p| p.take()) {
            match command {
                Command::Start {
                    action,
                    idle,
                    sound,
                } => {
                    // Between the caller's check and this tick the gate can have closed. Dropping
                    // it silently is better than gesturing out of a fall: the state frame never
                    // shows it, and the next tick is 20 ms away.
                    if ready {
                        // Replacing a gesture neutralises the old one first, so a head-only
                        // gesture cannot inherit an open mouth — the Python player's ordering.
                        if self.running.is_some() {
                            self.neutralise(intents);
                        }
                        self.begin(action, idle, sound, now, handle, intents);
                    }
                }
                Command::Cancel => {
                    let had = self.running.take().is_some();
                    handle.publish(None, false);
                    if had {
                        self.neutralise(intents);
                    }
                }
                Command::Stop => {
                    if let Some(running) = self.running.take() {
                        handle.publish(None, false);
                        // The only thing a gesture leaves that nothing else closes. Head, twist
                        // and pose stay where the user's own command put them.
                        if running.action == Action::Quack {
                            intents.set_mouth(0.0);
                        }
                    }
                }
            }
        }

        let Some(running) = self.running.as_mut() else {
            return;
        };

        if !ready {
            self.running = None;
            handle.publish(None, false);
            self.neutralise(intents);
            return;
        }

        let elapsed = now.saturating_duration_since(running.started).as_secs_f64();
        if elapsed >= running.action.duration() {
            self.running = None;
            handle.publish(None, false);
            self.neutralise(intents);
            return;
        }

        if let Some(head) = running.action.head_at(elapsed) {
            intents.set_head(head);
        }
        if let Some(mouth) = running.action.mouth_at(elapsed) {
            intents.set_mouth(mouth);
        }
        if running.sound {
            let beats = running.action.beats();
            while running.beat < beats.len() && elapsed >= beats[running.beat] {
                intents.request_sound(proto::SoundParams {
                    tag: running.action.sound(),
                    hold: None,
                });
                running.beat += 1;
            }
        }
    }

    fn begin(
        &mut self,
        action: Action,
        idle: bool,
        sound: bool,
        now: Instant,
        handle: &Handle,
        intents: &Intents,
    ) {
        // A gesture owns the body while it plays: a stale twist walks the duck while its head
        // draws a circle, and a stale pose rolls it.
        intents.set_twist([0.0; 3]);
        intents.set_pose(PoseIntent::default());
        intents.set_mouth(0.0);
        let mut beat = 0;
        if sound {
            intents.request_sound(proto::SoundParams {
                tag: action.sound(),
                hold: None,
            });
            beat = 1;
        }
        self.running = Some(Running {
            action,
            sound,
            started: now,
            beat,
        });
        handle.publish(Some(action), idle);
    }

    /// Put the robot back the way a gesture found it. Called when one ends on its own, by
    /// explicit cancel, or because the gate closed — never on a user intent.
    fn neutralise(&self, intents: &Intents) {
        intents.set_head([0.0; 4]);
        intents.set_mouth(0.0);
        intents.set_twist([0.0; 3]);
        intents.set_pose(PoseIntent::default());
    }
}

/// Is this a robot a gesture may start or keep playing on?
///
/// Homed, driven by a policy, upright, and not moving. `enabled` rather than the Python
/// `policy == "walk"`: `enabled` is the more direct "the policy is driving", and a head or a
/// mouth is equally safe while the robot stands. The difference is noted in the design's
/// acceptance notes.
pub fn ready(
    homed: bool,
    enabled: bool,
    fallen: bool,
    limp_fall: bool,
    gravity: [f64; 3],
    twist: [f64; 3],
) -> bool {
    if !(homed && enabled && !fallen && !limp_fall) {
        return false;
    }
    // Trunk-frame gravity points down at 0° of tilt.
    let tilt = (-gravity[2]).clamp(-1.0, 1.0).acos();
    if tilt >= 30.0f64.to_radians() {
        return false;
    }
    twist[0].abs() < 0.02 && twist[2].abs() < 0.02
}

#[cfg(test)]
mod tests {
    use std::time::Duration;

    use super::*;

    fn gate() -> bool {
        ready(true, true, false, false, [0.0, 0.0, -1.0], [0.0; 3])
    }

    /// A player and the slots it writes into, started at a known instant.
    fn fixture() -> (Player, Handle, Intents, Instant) {
        (Player::default(), Handle::default(), Intents::new(), Instant::now())
    }

    #[test]
    fn the_gate_needs_a_standing_robot_that_is_not_moving() {
        let still = [0.0; 3];
        assert!(ready(true, true, false, false, [0.0, 0.0, -1.0], still));
        assert!(!ready(false, true, false, false, [0.0, 0.0, -1.0], still));
        assert!(!ready(true, false, false, false, [0.0, 0.0, -1.0], still));
        assert!(!ready(true, true, true, false, [0.0, 0.0, -1.0], still));
        assert!(!ready(true, true, false, true, [0.0, 0.0, -1.0], still));
        // 45° of tilt.
        assert!(!ready(
            true,
            true,
            false,
            false,
            [0.707, 0.0, -0.707],
            still
        ));
        assert!(!ready(
            true,
            true,
            false,
            false,
            [0.0, 0.0, -1.0],
            [0.05, 0.0, 0.0]
        ));
        assert!(!ready(
            true,
            true,
            false,
            false,
            [0.0, 0.0, -1.0],
            [0.0, 0.0, 0.05]
        ));
        // Sideways sliding is not driving: only vx and yaw were asked about, as upstream.
        assert!(ready(
            true,
            true,
            false,
            false,
            [0.0, 0.0, -1.0],
            [0.0, 0.5, 0.0]
        ));
    }

    #[test]
    fn look_up_writes_the_head_and_ends_at_its_duration() {
        let (mut player, handle, intents, t0) = fixture();
        handle.start(Action::LookUp, false, false);
        player.tick(t0, &handle, &intents, gate());
        assert_eq!(intents.snapshot().command.head, [0.0, -0.30, 0.0, 0.0]);
        assert_eq!(handle.current(), Some("look_up"));

        player.tick(t0 + Duration::from_millis(700), &handle, &intents, gate());
        assert_eq!(intents.snapshot().command.head, [0.0, -0.30, 0.0, 0.0]);

        player.tick(t0 + Duration::from_millis(1200), &handle, &intents, gate());
        assert_eq!(intents.snapshot().command.head, [0.0; 4], "end is neutral");
        assert_eq!(handle.current(), None);
    }

    #[test]
    fn quack_opens_and_closes_the_mouth_within_one_cycle() {
        let (mut player, handle, intents, t0) = fixture();
        handle.start(Action::Quack, false, false);
        player.tick(t0, &handle, &intents, gate());
        assert_eq!(intents.snapshot().mouth, 0.9);
        player.tick(t0 + Duration::from_millis(400), &handle, &intents, gate());
        assert_eq!(intents.snapshot().mouth, 0.0);
        // And it ends closed.
        player.tick(t0 + Duration::from_millis(2100), &handle, &intents, gate());
        assert_eq!(intents.snapshot().mouth, 0.0);
        assert_eq!(handle.current(), None);
    }

    #[test]
    fn a_user_stop_keeps_the_head_the_user_asked_for() {
        let (mut player, handle, intents, t0) = fixture();
        handle.start(Action::LookUp, false, false);
        player.tick(t0, &handle, &intents, gate());
        // A user command arrives between ticks.
        intents.set_head([0.4, 0.3, 0.2, 0.1]);
        handle.stop();
        player.tick(t0 + Duration::from_millis(20), &handle, &intents, gate());
        assert_eq!(intents.snapshot().command.head, [0.4, 0.3, 0.2, 0.1]);
        assert_eq!(handle.current(), None);
    }

    #[test]
    fn a_cancel_puts_everything_back() {
        let (mut player, handle, intents, t0) = fixture();
        handle.start(Action::Quack, false, false);
        player.tick(t0, &handle, &intents, gate());
        assert_eq!(intents.snapshot().mouth, 0.9);

        handle.cancel();
        player.tick(t0 + Duration::from_millis(20), &handle, &intents, gate());
        let snapshot = intents.snapshot();
        assert_eq!(snapshot.command.head, [0.0; 4]);
        assert_eq!(snapshot.mouth, 0.0);
        assert_eq!(snapshot.command.twist, [0.0; 3]);
        assert!(!snapshot.pose.active);
        assert_eq!(handle.current(), None);
    }

    #[test]
    fn the_gate_closing_ends_the_gesture_and_neutralises() {
        let (mut player, handle, intents, t0) = fixture();
        handle.start(Action::LookUp, false, false);
        player.tick(t0, &handle, &intents, gate());
        assert!(handle.ready());

        player.tick(t0 + Duration::from_millis(40), &handle, &intents, false);
        assert_eq!(intents.snapshot().command.head, [0.0; 4]);
        assert_eq!(handle.current(), None);
        assert!(!handle.ready());
    }

    #[test]
    fn the_idle_flag_survives_until_the_gesture_ends() {
        let (mut player, handle, intents, t0) = fixture();
        handle.start(Action::Circle, true, false);
        player.tick(t0, &handle, &intents, gate());
        assert!(handle.idle());
        player.tick(t0 + Duration::from_millis(4000), &handle, &intents, gate());
        assert!(!handle.idle());
    }

    #[test]
    fn starting_a_second_gesture_closes_the_first_ones_mouth() {
        let (mut player, handle, intents, t0) = fixture();
        handle.start(Action::Quack, false, false);
        player.tick(t0, &handle, &intents, gate());
        assert_eq!(intents.snapshot().mouth, 0.9);

        handle.start(Action::LookUp, false, false);
        player.tick(t0 + Duration::from_millis(20), &handle, &intents, gate());
        assert_eq!(intents.snapshot().mouth, 0.0);
        assert_eq!(handle.current(), Some("look_up"));
    }
}

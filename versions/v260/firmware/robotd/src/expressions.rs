//! Official emotion curves from pollen-robotics/microduck_emotions robot/pad-expressions.patch.
//! Integration uses the existing control loop; play_dead and scene-only pick are excluded.
//! Motion amplitudes, timings and mouth envelopes below retain the official implementation.

use std::time::{Duration, Instant};

use duck_ipc_proto as proto;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Kind {
    Curious,
    Peck,
    /// Startled: the head snaps up and the duck backs away a step. The scream is on the trigger.
    Startled,
    /// Devastated (emotion mode, B): the duck sits down at once (the shock), then the head
    /// droops and shakes "no" three times while it sobs, then comes back level. It stays
    /// seated. The sound and the sit are fired when the expression starts; the beak follows
    /// the sound through `mouth_at`.
    Devastated,
    /// Sad (emotion mode, A): standing, the head droops with a small bow of the body while a
    /// low coo glides down, two slow silent "no" shakes at the bottom, then back level. The
    /// walking policy stays in charge underneath, sticks locked.
    Sad,
    /// Curious with a voice (emotion mode, Y): the head comes forward, beak level, then tilts
    /// right on a chirp and left on a second, higher chirp ("hm?"), holds, and comes back.
    /// LB's `Curious` is the silent cousin; this one is the emotion, quacks included.
    CuriousQuacks,
    /// Yes (emotion mode, LB): one clear nod with one affirmative quack. Episode 3.
    Yes,
    /// No (emotion mode, RB): a short head shake with a two-note "no-ah". Episode 3.
    No,
    /// Angry (emotion mode, X): bow pulses and yaw snaps with hard barks; the beak opens wide
    /// on the first bark so a held leash drops. Body pose on the pose slot. Episode 3.
    Angry,
    /// Excited (emotion mode, DPad-Down): body bounces, beak up, head wagging, a run of fast
    /// rising quacks. Body pose on the pose slot. Episode 3.
    Excited,
    /// Mmh, "what do you mean?" (emotion mode, Y): a small roll tilt with a muffled rising
    /// "mmh?". Rémi's pick from the closed-beak page; the beak opens normally. Episode 3.
    Mmh,
    /// Yes, fast (emotion mode, L3): the same nod as `Yes` with a curt "wak". Episode 3.
    YesFast,
    /// Laugh (emotion mode, R3): beak up, the head wagging, the body dipping on a staccato
    /// "ha-ha-ha-ha, ha-ha-ha". Body pose on the pose slot. Episode 3.
    Laugh,
    /// Mock ("gnagnagnagna"): the laugh's staccato run with the head rolling instead of
    /// wagging. Rémi: "a great move for a mockery, after someone scolds the duck". Cue only.
    Mock,
    /// Defiant ("says who?", cue only): the beak up and to the left with a quack, then up and to
    /// the right with a second one. Episode 3, the answer after the water-resistance line.
    Defiant,
    /// Impatient ("come on!", cue only): four quick yaw shakes with a grumble and a body bob on
    /// each, then the beak flicks up on a huff. Episode 3, the answer after "We shouldn't go".
    Impatient,
}

impl Kind {
    /// Names on the cue wire (`padd/src/cue.rs`), one per kind.
    pub const NAMES: [(&'static str, Kind); 16] = [
        ("curious_silent", Kind::Curious),
        ("peck", Kind::Peck),
        ("startled", Kind::Startled),
        ("devastated", Kind::Devastated),
        ("sad", Kind::Sad),
        ("curious", Kind::CuriousQuacks),
        ("yes", Kind::Yes),
        ("no", Kind::No),
        ("angry", Kind::Angry),
        ("excited", Kind::Excited),
        ("mmh", Kind::Mmh),
        ("yes_fast", Kind::YesFast),
        ("laugh", Kind::Laugh),
        ("mock", Kind::Mock),
        ("defiant", Kind::Defiant),
        ("impatient", Kind::Impatient),
    ];

    pub fn from_name(name: &str) -> Option<Kind> {
        let name = name.trim().to_ascii_lowercase().replace('-', "_");
        Self::NAMES
            .iter()
            .find(|(n, _)| *n == name)
            .map(|(_, k)| *k)
    }
}

#[derive(Debug, Clone, Copy)]
pub struct Expression {
    kind: Kind,
    started: Instant,
}

/// One peck: down for this long, then back up for the rest of `PECK_PERIOD`.
const PECK_DOWN: f64 = 0.45;
const PECK_PERIOD: f64 = 0.85;
const PECK_COUNT: u32 = 2;
/// The peck's amplitudes: neck command (tracks to about -0.85 rad) and the head-pitch counter-tilt.
const PECK_NECK: f64 = 1.5;
const PECK_HEAD: f64 = 0.6;
/// Curious: tilt right, tilt left, centre. Each leg this long.
const CURIOUS_LEG: f64 = 0.7;
/// Startled: head up at once, then back away from `STARTLED_BACK_FROM` to `STARTLED_BACK_TO`
/// (the calmest backward walk command the alpha gait has), head settling by the end.
const STARTLED_LEN: f64 = 2.0;
const STARTLED_BACK_FROM: f64 = 0.3;
const STARTLED_BACK_TO: f64 = 1.5;
const STARTLED_BACK: proto::MoveParams = proto::MoveParams {
    vx: -0.35,
    vy: 0.0,
    vyaw: 0.22,
};
/// Devastated, seconds from the button press (numbers decided in simulation, see
/// notes/emotions/motion/sadness/REPORT.md): the sit lands by ~0.8 s; the head droops from
/// `DEV_DROOP` over `DEV_DROOP_LEN`; three yaw swings of `DEV_YAW` rad with extremes at
/// `DEV_SWING_AT` (+, -, +), half a second in and out; a hold; then the rise from `DEV_RISE`
/// over `DEV_DROOP_LEN`. Neck asks for -1.5 (tracks to about -1.0 seated), head pitch +1.0
/// (positive = beak down on these policies).
const DEV_LEN: f64 = 8.5;
const DEV_DROOP: f64 = 1.5;
const DEV_DROOP_LEN: f64 = 2.0;
const DEV_RISE: f64 = 6.5;
const DEV_NECK: f64 = 1.5;
const DEV_HEAD: f64 = 1.0;
const DEV_YAW: f64 = 0.4;
const DEV_SWING_AT: [f64; 3] = [3.0, 4.0, 5.0];
const DEV_YAW_FADE: f64 = 0.5;
/// The beak, 0..1 every 0.1 s from the press, traced from the sound's envelope (the `mouth`
/// channel of the simulation's keyframes, video clock minus the 0.3 s lead-in): the shock at
/// 0-0.5 s, the three sobs at 3.0 / 4.0 / 5.0 s dying out by 6.6 s. Zero after the table.
const DEV_MOUTH_STEP: f64 = 0.1;
const DEV_MOUTH: [f64; 67] = [
    0.269, 1.000, 1.000, 1.000, 1.000, 0.380, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000,
    0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000,
    0.000, 0.000, 0.000, 0.000, 0.074, 0.573, 1.000, 1.000, 1.000, 1.000, 1.000, 0.786, 0.369,
    0.016, 0.060, 0.481, 0.912, 1.000, 1.000, 1.000, 1.000, 0.663, 0.312, 0.013, 0.052, 0.396,
    0.756, 1.000, 1.000, 1.000, 1.000, 1.000, 0.885, 0.753, 0.632, 0.499, 0.373, 0.245, 0.117,
    0.005, 0.000,
];
/// Sad, seconds from the press: the droop below over the first 2.5 s, two yaw swings with
/// extremes at `SAD_SWING_AT` (+, -) and 0.6 s fades (window 2.5-4.9 s), hold, then the rise
/// from `SAD_RISE` over `SAD_RISE_LEN`; head level at 7.5 s. The body pitch rides the pose slot
/// (0.10 made the stand net shake the head one way only, hence 0.05).
const SAD_LEN: f64 = 7.5;
/// The droop, v7 (Rémi, on the robot: the full droop made the head so heavy the duck walked
/// forward to stay up). Same 2.5 s, half the depth: the head first LIFTS for `SAD_LIFT_LEN`
/// (beak up to `SAD_LIFT_PITCH`, neck still, a quarter of the bow), then descends for the rest
/// of the 2.5 s to half depth: head pitch `SAD_HEAD`, neck `SAD_NECK`, bow `SAD_BODY_PITCH`.
const SAD_LIFT_LEN: f64 = 0.625;
const SAD_LIFT_PITCH: f64 = -0.25;
const SAD_DESCEND_LEN: f64 = 1.875;
const SAD_NECK: f64 = 0.75;
const SAD_HEAD: f64 = 0.5;
const SAD_RISE: f64 = 5.5;
const SAD_RISE_LEN: f64 = 2.0;
const SAD_SWING_AT: [f64; 2] = [3.1, 4.3];
const SAD_YAW_FADE: f64 = 0.6;
const SAD_BODY_PITCH: f64 = 0.05;
/// The beak for the sad coo, 0..1 every 0.1 s: open through the droop, shut by 3.2 s.
const SAD_MOUTH: [f64; 33] = [
    0.000, 0.000, 0.018, 0.218, 0.428, 0.643, 0.875, 1.000, 1.000, 1.000, 1.000, 1.000, 1.000,
    1.000, 1.000, 1.000, 1.000, 1.000, 1.000, 1.000, 1.000, 1.000, 1.000, 1.000, 1.000, 1.000,
    0.934, 0.751, 0.567, 0.372, 0.188, 0.016, 0.000,
];
/// Curious with quacks, seconds from the press (simulation `curious_two_tilts_r35_leftboost`,
/// minus its head-forward phase, which made the real duck step forward): the head tilts right
/// to `CQ_TILT_RIGHT` from `CQ_TILT1`, then over to `CQ_TILT_LEFT` from `CQ_TILT2` (the left
/// side tracks weaker, so it asks the full range), holds, and ramps back from `CQ_BACK` over
/// `CQ_BACK_LEN`. The chirps land at 0.6 and 1.2 s.
const CQ_LEN: f64 = 3.0;
const CQ_TILT1: f64 = 0.4;
const CQ_TILT2: f64 = 1.0;
const CQ_TILT_LEN: f64 = 0.35;
const CQ_TILT_RIGHT: f64 = 0.35;
const CQ_TILT_LEFT: f64 = -0.44;
const CQ_BACK: f64 = 2.1;
const CQ_BACK_LEN: f64 = 0.5;
/// The beak, 0..1 every 0.1 s: a snap open on each chirp, shut otherwise.
const CQ_MOUTH: [f64; 17] = [
    0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 1.000, 0.030, 0.000, 0.000, 0.000,
    0.000, 1.000, 0.059, 0.000,
];

/// Episode 3 (2026-09-06). Numbers from the simulation picks: `notes/emotions/motion/<emotion>/REPORT.md`.
///
/// Yes: one nod. Standing, only head_pitch moves: down to `YES_PITCH` (beak down) from `YES_DOWN_AT`
/// over `YES_DOWN_LEN`, a short hold, back over `YES_UP_LEN`; the policies follow ~0.4 s late, so the
/// joint bottoms out at ~0.45 s, where the one quack lands (250 Hz falling 3 semitones).
const YES_LEN: f64 = 1.5;
const YES_PITCH: f64 = 0.7;
const YES_DOWN_AT: f64 = 0.05;
const YES_DOWN_LEN: f64 = 0.25;
const YES_HOLD: f64 = 0.10;
const YES_UP_LEN: f64 = 0.35;
/// The beak, 0..1 every 0.1 s (the simulation's mouth channel: the wav's envelope 0.15 s late).
const YES_MOUTH: [f64; 11] = [
    0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.819, 1.000, 0.638, 0.214, 0.000,
];
/// No: a head shake, yaw only: `swings` through +`NO_YAW` at 0.35 s and -`NO_YAW` at 0.85 s with
/// 0.25 s fades (0 until 0.10 s, centre at 1.10 s). The two notes ("no" 250 Hz flat at 0.60 s,
/// "ah" a fourth lower at 1.10 s) land on the joint's extremes, which lag the command by 0.25 s.
const NO_LEN: f64 = 1.8;
const NO_YAW: f64 = 0.55;
const NO_SWING_AT: [f64; 2] = [0.35, 0.85];
const NO_FADE: f64 = 0.25;
const NO_MOUTH: [f64; 17] = [
    0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 1.000, 0.580, 0.000, 0.000, 0.000,
    1.000, 0.820, 0.421, 0.000,
];
/// Angry: four snaps, one hard bark on each at `ANGRY_BARKS`. Standing, neck 0 throughout (the
/// stand net folds the whole duck forward from a body pitch of ~0.2, which is the head-forward
/// mass that makes the real robot walk: only small fast bow pulses are clean). A beak-up baseline
/// (`ANGRY_UP`), and on each bark, led by `ANGRY_LEAD`: a head-yaw snap to `ANGRY_YAW_AT` (0.12 s
/// ramps), a head jab (`ANGRY_JAB`: beak from up to just below level), and on the first three a
/// small fast bow on the pose slot (`ANGRY_BOW`). The beak is forced wide 0.30-0.70 s so a held
/// leash drops, then follows the wav.
const ANGRY_LEN: f64 = 2.6;
const ANGRY_BARKS: [f64; 4] = [0.30, 0.90, 1.50, 2.00];
const ANGRY_LEAD: f64 = 0.15;
const ANGRY_UP: f64 = -0.35;
const ANGRY_JAB: f64 = 0.45;
const ANGRY_YAW_AT: [f64; 4] = [0.7, -0.7, 0.7, 0.0];
const ANGRY_SNAP_LEN: f64 = 0.12;
const ANGRY_BOW: f64 = 0.14;
const ANGRY_MOUTH: [f64; 27] = [
    0.000, 0.000, 0.000, 1.000, 1.000, 1.000, 1.000, 0.000, 0.000, 0.000, 0.000, 1.000, 0.423,
    0.000, 0.000, 0.000, 0.000, 1.000, 0.459, 0.000, 0.000, 0.000, 1.000, 1.000, 1.000, 0.000,
    0.000,
];
/// Excited: six accelerating head swings of +-`EXCITED_YAW` with extremes at `EXCITED_Q` (a bank
/// chirp on each, in rising pitch order), the beak climbing from `EXCITED_UP_FROM` to `EXCITED_UP_TO`,
/// a body bob on each swing = a small fast bow pulse on the pose slot (the pose z slot does nothing
/// on the stand net), and a bow flourish at the end. Neck 0.
const EXCITED_LEN: f64 = 3.4;
const EXCITED_Q: [f64; 6] = [0.40, 0.95, 1.45, 1.90, 2.30, 2.65];
const EXCITED_YAW: f64 = 0.6;
const EXCITED_FADE: f64 = 0.3;
const EXCITED_UP_FROM: f64 = -0.15;
const EXCITED_UP_TO: f64 = -0.70;
const EXCITED_BOB: f64 = 0.12;
/// The beak for the X1 synth climb (Rémi's sound pick), from its simulation JSON.
const EXCITED_MOUTH: [f64; 31] = [
    0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 1.000, 0.622, 0.000, 0.000, 0.000, 0.974, 0.946,
    0.132, 0.000, 0.000, 0.952, 0.884, 0.075, 0.000, 0.000, 1.000, 0.421, 0.000, 0.000, 1.000,
    0.286, 0.000, 0.953, 0.713, 0.000,
];
/// Mmh: a roll tilt to `MMH_ROLL` from 0.45 s (0.3 s up, 0.5 s hold, 0.35 s down), the muffled
/// rising "mmh?" at 0.5 s.
const MMH_LEN: f64 = 2.0;
const MMH_ROLL: f64 = 0.22;
const MMH_MOUTH: [f64; 13] = [
    0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 1.000, 1.000, 1.000, 0.765, 0.345, 0.000,
];
/// Yes, fast: the nod of `Yes`, the curt "wak" at 0.45 s.
const YES_FAST_MOUTH: [f64; 10] = [
    0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.937, 0.757, 0.060, 0.000,
];
/// Laugh, v2 (Rémi: the head aimed up more, and a "dying of laughter" sound): beak up
/// (`LAUGH_UP`) through a gate (in 0.3 s, out from 2.5 s), yaw swings of +-`LAUGH_YAW` with
/// extremes at `LAUGH_SWINGS`, a bow pulse (`LAUGH_BOB`) on every ha at `LAUGH_HAS`: one long
/// "haaa" at 0.35 s, then seven short ha's getting shorter, softer and further apart.
const LAUGH_LEN: f64 = 3.0;
const LAUGH_UP: f64 = -0.7;
const LAUGH_YAW: f64 = 0.45;
const LAUGH_SWINGS: [f64; 5] = [0.35, 0.90, 1.30, 1.85, 2.30];
const LAUGH_HAS: [f64; 8] = [0.35, 0.90, 1.10, 1.30, 1.50, 1.85, 2.05, 2.30];
const LAUGH_BOB: f64 = 0.10;
/// Every 0.05 s (the ha's are 0.2 s apart, too fast for the 0.1 s tables).
const LAUGH_MOUTH_STEP: f64 = 0.05;
const LAUGH_MOUTH: [f64; 53] = [
    0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.881, 1.000, 1.000,
    0.962, 0.787, 0.630, 0.468, 0.366, 0.085, 0.000, 0.000, 0.776, 1.000, 0.465, 0.000, 0.754,
    1.000, 0.356, 0.000, 0.731, 1.000, 0.264, 0.000, 0.656, 0.865, 0.185, 0.000, 0.000, 0.000,
    0.000, 0.668, 0.718, 0.118, 0.000, 0.603, 0.592, 0.073, 0.000, 0.000, 0.464, 0.493, 0.033,
    0.000,
];
/// Mock ("gnagnagnagna", the duck mocking a scolding; cue only): the first laugh's staccato run
/// under a beak-up (`MOCK_UP`) with the head ROLLING +-`MOCK_ROLL` on every other ha instead of
/// yawing, a body bob on every ha at `MOCK_HAS`.
const MOCK_LEN: f64 = 2.6;
const MOCK_UP: f64 = -0.55;
const MOCK_ROLL: f64 = 0.35;
const MOCK_SWINGS: [f64; 4] = [0.35, 0.79, 1.45, 1.89];
const MOCK_HAS: [f64; 7] = [0.35, 0.57, 0.79, 1.01, 1.45, 1.67, 1.89];
const MOCK_MOUTH: [f64; 45] = [
    0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 1.000, 1.000, 0.529,
    0.050, 0.382, 1.000, 0.689, 0.165, 0.000, 0.987, 1.000, 0.350, 0.000, 0.643, 1.000, 0.543,
    0.089, 0.000, 0.000, 0.000, 0.000, 0.000, 0.754, 0.913, 0.372, 0.036, 0.265, 1.000, 0.481,
    0.114, 0.000, 0.846, 0.737, 0.245, 0.000,
];
/// Defiant: beak up (`DEF_UP`) through a gate (in 0.3 s, out from 1.6 s); yaw to +`DEF_YAW` from
/// 0.15 s, over to -`DEF_YAW` from 0.85 s (0.3 s ramps), back from 1.6 s; quacks at 0.45 / 1.15 s.
const DEF_LEN: f64 = 2.2;
const DEF_UP: f64 = -0.6;
const DEF_YAW: f64 = 0.6;
const DEF_MOUTH: [f64; 17] = [
    0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.945, 0.934, 0.199, 0.000, 0.000, 0.000, 0.000,
    0.995, 0.984, 0.207, 0.000,
];
/// Impatient: yaw `swings` through `IMP_SHAKES` (+-`IMP_YAW`, 0.25 s fades), a body bob
/// (`IMP_BOB`) on each shake, the beak flicking up (`IMP_UP`) from `IMP_HUFF` - 0.15 s (0.15 up,
/// 0.25 hold, 0.4 down); grumbles at 0.4 / 0.8 / 1.2 / 1.6 s, the huff at 1.95 s.
const IMP_LEN: f64 = 2.6;
const IMP_SHAKES: [f64; 4] = [0.35, 0.75, 1.15, 1.55];
const IMP_YAW: f64 = 0.4;
const IMP_BOB: f64 = 0.08;
const IMP_UP: f64 = -0.7;
const IMP_HUFF: f64 = 1.9;
const IMP_MOUTH: [f64; 26] = [
    0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 1.000, 0.261, 0.000, 0.000, 1.000, 0.279, 0.000,
    0.000, 1.000, 0.293, 0.000, 0.000, 1.000, 0.303, 0.000, 0.836, 1.000, 0.619, 0.206, 0.000,
];
impl Expression {
    pub fn start(kind: Kind, now: Instant) -> Self {
        Self { kind, started: now }
    }

    pub fn duration(kind: Kind) -> Duration {
        Duration::from_secs_f64(match kind {
            Kind::Peck => PECK_PERIOD * PECK_COUNT as f64,
            Kind::Curious => CURIOUS_LEG * 3.0,
            Kind::Startled => STARTLED_LEN,
            Kind::Devastated => DEV_LEN,
            Kind::Sad => SAD_LEN,
            Kind::CuriousQuacks => CQ_LEN,
            Kind::Yes => YES_LEN,
            Kind::No => NO_LEN,
            Kind::Angry => ANGRY_LEN,
            Kind::Excited => EXCITED_LEN,
            Kind::Mmh => MMH_LEN,
            Kind::YesFast => YES_LEN,
            Kind::Laugh => LAUGH_LEN,
            Kind::Mock => MOCK_LEN,
            Kind::Defiant => DEF_LEN,
            Kind::Impatient => IMP_LEN,
        })
    }

    pub fn kind(&self) -> Kind {
        self.kind
    }

    pub fn started(&self) -> Instant {
        self.started
    }

    /// Whether this expression drives the body-pose slot (and so must release it at the end).
    pub fn has_pose(kind: Kind) -> bool {
        matches!(
            kind,
            Kind::Sad | Kind::Angry | Kind::Excited | Kind::Laugh | Kind::Mock | Kind::Impatient
        )
    }

    /// The body pose this expression wants at `now`, if it drives the pose slot at all.
    pub fn pose_at(&self, now: Instant) -> Option<proto::PoseParams> {
        let t = now.duration_since(self.started).as_secs_f64();
        pose_at(self.kind, t)
    }

    /// The one-shot skill to fire as this expression starts, if any.
    pub fn skill_at_start(kind: Kind) -> Option<&'static str> {
        match kind {
            Kind::Devastated => Some("sit_toggle"),
            _ => None,
        }
    }

    /// The sound to play as this expression starts, if any.
    pub fn sound_at_start(kind: Kind) -> Option<&'static str> {
        match kind {
            Kind::Devastated => Some("devastated"),
            Kind::Sad => Some("sad"),
            Kind::CuriousQuacks => Some("curious"),
            Kind::Mmh => Some("mmh"),
            Kind::YesFast => Some("yes_fast"),
            Kind::Laugh => Some("laugh"),
            Kind::Mock => Some("mock"),
            Kind::Defiant => Some("defiant"),
            Kind::Impatient => Some("impatient"),
            Kind::Yes => Some("yes"),
            Kind::No => Some("no"),
            Kind::Angry => Some("angry"),
            Kind::Excited => Some("excited"),
            _ => None,
        }
    }

    /// The twist this expression wants at `now`: `None` when it leaves the sticks in charge.
    pub fn twist_at(&self, now: Instant) -> Option<proto::MoveParams> {
        let t = now.duration_since(self.started).as_secs_f64();
        twist_at(self.kind, t)
    }

    /// How open the beak is at `now`, 0..1. Zero for expressions with no voice, and after the end.
    pub fn mouth_at(&self, now: Instant) -> f64 {
        let t = now.duration_since(self.started).as_secs_f64();
        mouth_at(self.kind, t)
    }

    /// The head intent at `now`, or `None` once the expression is over.
    pub fn head_at(&self, now: Instant) -> Option<proto::HeadParams> {
        let t = now.duration_since(self.started).as_secs_f64();
        if t >= Self::duration(self.kind).as_secs_f64() {
            return None;
        }
        Some(head_at(self.kind, t))
    }
}

/// Smooth 0→1 ramp over `len` seconds (half a cosine): no snap for the servos to chase.
fn ramp(t: f64, len: f64) -> f64 {
    let x = (t / len).clamp(0.0, 1.0);
    0.5 - 0.5 * (std::f64::consts::PI * x).cos()
}

pub fn twist_at(kind: Kind, t: f64) -> Option<proto::MoveParams> {
    match kind {
        Kind::Startled if (STARTLED_BACK_FROM..STARTLED_BACK_TO).contains(&t) => {
            Some(STARTLED_BACK)
        }
        // Drooping: the sticks must not walk it. Zero twist for the whole thing.
        Kind::Devastated if t < DEV_LEN => Some(proto::MoveParams::default()),
        Kind::Sad if t < SAD_LEN => Some(proto::MoveParams::default()),
        Kind::CuriousQuacks if t < CQ_LEN => Some(proto::MoveParams::default()),
        Kind::Yes if t < YES_LEN => Some(proto::MoveParams::default()),
        Kind::No if t < NO_LEN => Some(proto::MoveParams::default()),
        Kind::Angry if t < ANGRY_LEN => Some(proto::MoveParams::default()),
        Kind::Excited if t < EXCITED_LEN => Some(proto::MoveParams::default()),
        Kind::Mmh if t < MMH_LEN => Some(proto::MoveParams::default()),
        Kind::YesFast if t < YES_LEN => Some(proto::MoveParams::default()),
        Kind::Laugh if t < LAUGH_LEN => Some(proto::MoveParams::default()),
        Kind::Mock if t < MOCK_LEN => Some(proto::MoveParams::default()),
        Kind::Defiant if t < DEF_LEN => Some(proto::MoveParams::default()),
        Kind::Impatient if t < IMP_LEN => Some(proto::MoveParams::default()),
        _ => None,
    }
}

/// A body pose on the pose slot, `None` for expressions that leave it alone.
pub fn pose_at(kind: Kind, t: f64) -> Option<proto::PoseParams> {
    match kind {
        Kind::Sad if (0.0..SAD_LEN).contains(&t) => Some(proto::PoseParams {
            pitch: sad_droop(t).2,
            active: true,
            ..Default::default()
        }),
        Kind::Angry if (0.0..ANGRY_LEN).contains(&t) => Some(proto::PoseParams {
            pitch: ANGRY_BOW * angry_bows(t),
            active: true,
            ..Default::default()
        }),
        Kind::Excited if (0.0..EXCITED_LEN).contains(&t) => Some(proto::PoseParams {
            pitch: excited_bobs(t),
            active: true,
            ..Default::default()
        }),
        Kind::Laugh if (0.0..LAUGH_LEN).contains(&t) => Some(proto::PoseParams {
            pitch: bobs(t, &LAUGH_HAS, LAUGH_BOB),
            active: true,
            ..Default::default()
        }),
        Kind::Mock if (0.0..MOCK_LEN).contains(&t) => Some(proto::PoseParams {
            pitch: bobs(t, &MOCK_HAS, LAUGH_BOB),
            active: true,
            ..Default::default()
        }),
        Kind::Impatient if (0.0..IMP_LEN).contains(&t) => Some(proto::PoseParams {
            pitch: bobs(t, &IMP_SHAKES, IMP_BOB),
            active: true,
            ..Default::default()
        }),
        _ => None,
    }
}

/// A pulse 0 -> 1 -> 0: up over `up` from `t0`, a `hold`, back down over `down`.
fn pulse(t: f64, t0: f64, up: f64, hold: f64, down: f64) -> f64 {
    ramp(t - t0, up) * (1.0 - ramp(t - t0 - up - hold, down))
}

/// Angry's bows, 0..1: a small fast pulse on the first three barks, led by `ANGRY_LEAD`.
fn angry_bows(t: f64) -> f64 {
    ANGRY_BARKS[..3]
        .iter()
        .map(|&b| pulse(t, b - ANGRY_LEAD, 0.15, 0.05, 0.25))
        .sum()
}

/// Angry's head jabs, in head-pitch units: a short pulse on each bark, led by `ANGRY_LEAD`.
fn angry_jabs(t: f64) -> f64 {
    ANGRY_BARKS
        .iter()
        .map(|&b| ANGRY_JAB * pulse(t, b - ANGRY_LEAD, 0.12, 0.05, 0.30))
        .sum()
}

/// Angry's yaw: a half-cosine snap to each target in `ANGRY_YAW_AT` starting `ANGRY_LEAD` before
/// its bark, over `ANGRY_SNAP_LEN`, holding until the next.
fn angry_yaw(t: f64) -> f64 {
    let mut yaw = 0.0;
    for (i, &b) in ANGRY_BARKS.iter().enumerate() {
        let prev = if i == 0 { 0.0 } else { ANGRY_YAW_AT[i - 1] };
        let t0 = b - ANGRY_LEAD;
        if t >= t0 {
            yaw = prev + (ANGRY_YAW_AT[i] - prev) * ramp(t - t0, ANGRY_SNAP_LEN);
        }
    }
    yaw
}

/// Body bobs on the pose slot: a bow pulse led 0.15 s before each beat, capped at the trained range.
fn bobs(t: f64, at: &[f64], amp: f64) -> f64 {
    at.iter()
        .map(|&h| amp * pulse(t, h - 0.15, 0.15, 0.0, 0.2))
        .sum::<f64>()
        .min(0.26)
}

/// Excited's body bobs: a bow pulse on the pose slot led 0.15 s before each swing extreme, and
/// the flourish after the last one; capped at the trained range.
fn excited_bobs(t: f64) -> f64 {
    let last = EXCITED_Q[EXCITED_Q.len() - 1];
    let bobs: f64 = EXCITED_Q
        .iter()
        .map(|&q| EXCITED_BOB * pulse(t, q - 0.15, 0.15, 0.0, 0.2))
        .sum();
    (bobs + EXCITED_BOB * pulse(t, last + 0.15, 0.2, 0.05, 0.3)).min(0.26)
}

/// Excited's yaw: `swings` with the extremes at `EXCITED_Q` (unevenly spaced, accelerating).
fn excited_yaw(t: f64) -> f64 {
    swings(t, &EXCITED_Q, EXCITED_YAW, EXCITED_FADE)
}

/// A 0..1 table sampled every `DEV_MOUTH_STEP`, linear in between; zero past its end (every
/// table ends on a zero).
fn table_at(table: &[f64], t: f64) -> f64 {
    table_at_step(table, t, DEV_MOUTH_STEP)
}

/// The same, with the table's own step.
fn table_at_step(table: &[f64], t: f64, step: f64) -> f64 {
    if t < 0.0 {
        return 0.0;
    }
    let x = t / step;
    let i = x.floor() as usize;
    match (table.get(i), table.get(i + 1)) {
        (Some(a), Some(b)) => a + (b - a) * (x - i as f64),
        _ => 0.0,
    }
}

pub fn mouth_at(kind: Kind, t: f64) -> f64 {
    match kind {
        Kind::Devastated => table_at(&DEV_MOUTH, t),
        Kind::Sad => table_at(&SAD_MOUTH, t),
        Kind::CuriousQuacks => table_at(&CQ_MOUTH, t),
        Kind::Yes => table_at(&YES_MOUTH, t),
        Kind::No => table_at(&NO_MOUTH, t),
        Kind::Angry => table_at(&ANGRY_MOUTH, t),
        Kind::Excited => table_at(&EXCITED_MOUTH, t),
        Kind::Mmh => table_at(&MMH_MOUTH, t),
        Kind::YesFast => table_at(&YES_FAST_MOUTH, t),
        Kind::Laugh => table_at_step(&LAUGH_MOUTH, t, LAUGH_MOUTH_STEP),
        Kind::Mock => table_at_step(&MOCK_MOUTH, t, LAUGH_MOUTH_STEP),
        Kind::Defiant => table_at(&DEF_MOUTH, t),
        Kind::Impatient => table_at(&IMP_MOUTH, t),
        // Open on the way down, shut at the floor: the leash grasp.
        // The shock on the press, shut through the fall, barely open for the death quack.
        _ => 0.0,
    }
}

/// Head-shake yaw: half-cosine swings through `extremes` (alternating +amp, -amp, ...), fading
/// in from centre over `fade` before the first and back to centre over `fade` after the last.
fn swings(t: f64, extremes: &[f64], amp: f64, fade: f64) -> f64 {
    let Some((&first, _)) = extremes.split_first() else {
        return 0.0;
    };
    let last = extremes[extremes.len() - 1];
    if t < first - fade {
        return 0.0;
    }
    if t < first {
        return amp * ramp(t - (first - fade), fade);
    }
    for (i, pair) in extremes.windows(2).enumerate() {
        let sign = if i % 2 == 0 { 1.0 } else { -1.0 };
        if t < pair[1] {
            return sign * amp * (1.0 - 2.0 * ramp(t - pair[0], pair[1] - pair[0]));
        }
    }
    let sign = if extremes.len() % 2 == 1 { 1.0 } else { -1.0 };
    sign * amp * (1.0 - ramp(t - last, fade))
}

/// The sad droop as (neck, head_pitch, body_pitch) at `t`: the beak lifts, then descends to
/// half depth; the neck and the bow follow the beak only once it is below level (as the v7
/// simulation has it: neck = -1.5 x head pitch, bow = 0.1 x head pitch, never above level), so
/// the neck stays still through the lift; everything comes back to level together over the rise.
fn sad_droop(t: f64) -> (f64, f64, f64) {
    let head = if t < SAD_LIFT_LEN {
        SAD_LIFT_PITCH * ramp(t, SAD_LIFT_LEN)
    } else {
        SAD_LIFT_PITCH + (SAD_HEAD - SAD_LIFT_PITCH) * ramp(t - SAD_LIFT_LEN, SAD_DESCEND_LEN)
    };
    let up = 1.0 - ramp(t - SAD_RISE, SAD_RISE_LEN);
    let head = head * up;
    let below = head.max(0.0);
    (
        -(SAD_NECK / SAD_HEAD) * below,
        head,
        (SAD_BODY_PITCH / SAD_HEAD) * below,
    )
}

pub fn head_at(kind: Kind, t: f64) -> proto::HeadParams {
    match kind {
        Kind::Devastated => {
            let down =
                ramp(t - DEV_DROOP, DEV_DROOP_LEN) * (1.0 - ramp(t - DEV_RISE, DEV_DROOP_LEN));
            proto::HeadParams {
                neck_pitch: -DEV_NECK * down,
                head_pitch: DEV_HEAD * down,
                head_yaw: swings(t, &DEV_SWING_AT, DEV_YAW, DEV_YAW_FADE),
                head_roll: 0.0,
            }
        }
        Kind::Sad => {
            let (neck_pitch, head_pitch, _) = sad_droop(t);
            proto::HeadParams {
                neck_pitch,
                head_pitch,
                head_yaw: swings(t, &SAD_SWING_AT, DEV_YAW, SAD_YAW_FADE),
                head_roll: 0.0,
            }
        }
        Kind::CuriousQuacks => {
            // Roll only. The head-forward phase of the simulation was dropped on the robot:
            // with the head that far out the stand net steps forward to stay under it.
            let back = 1.0 - ramp(t - CQ_BACK, CQ_BACK_LEN);
            let roll = if t < CQ_TILT2 {
                CQ_TILT_RIGHT * ramp(t - CQ_TILT1, CQ_TILT_LEN)
            } else {
                CQ_TILT_RIGHT + (CQ_TILT_LEFT - CQ_TILT_RIGHT) * ramp(t - CQ_TILT2, CQ_TILT_LEN)
            };
            proto::HeadParams {
                neck_pitch: 0.0,
                head_pitch: 0.0,
                head_yaw: 0.0,
                head_roll: roll * back,
            }
        }
        Kind::Yes => {
            let down = pulse(t, YES_DOWN_AT, YES_DOWN_LEN, YES_HOLD, YES_UP_LEN);
            proto::HeadParams {
                neck_pitch: 0.0,
                head_pitch: YES_PITCH * down,
                head_yaw: 0.0,
                head_roll: 0.0,
            }
        }
        Kind::No => proto::HeadParams {
            neck_pitch: 0.0,
            head_pitch: 0.0,
            head_yaw: swings(t, &NO_SWING_AT, NO_YAW, NO_FADE),
            head_roll: 0.0,
        },
        Kind::Angry => {
            // The beak-up glare fades in over 0.3 s and out from 2.1 s; the jabs ride on it.
            let up = ANGRY_UP * ramp(t, 0.3) * (1.0 - ramp(t - 2.1, 0.4));
            proto::HeadParams {
                neck_pitch: 0.0,
                head_pitch: up + angry_jabs(t),
                head_yaw: angry_yaw(t),
                head_roll: 0.0,
            }
        }
        Kind::Excited => {
            let (q0, q5) = (EXCITED_Q[0], EXCITED_Q[EXCITED_Q.len() - 1]);
            // The beak climbs over the swings, fades in over 0.25 s and back to level by 3.45 s.
            let up = (EXCITED_UP_FROM + (EXCITED_UP_TO - EXCITED_UP_FROM) * ramp(t - q0, q5 - q0))
                * ramp(t, 0.25)
                * (1.0 - ramp(t - (q5 + 0.35), 0.45));
            proto::HeadParams {
                neck_pitch: 0.0,
                head_pitch: up,
                head_yaw: excited_yaw(t),
                head_roll: 0.0,
            }
        }
        Kind::Mmh => proto::HeadParams {
            neck_pitch: 0.0,
            head_pitch: 0.0,
            head_yaw: 0.0,
            head_roll: MMH_ROLL * pulse(t, 0.45, 0.3, 0.5, 0.35),
        },
        Kind::YesFast => head_at(Kind::Yes, t),
        Kind::Laugh => {
            let gate = ramp(t, 0.3) * (1.0 - ramp(t - 2.5, 0.4));
            proto::HeadParams {
                neck_pitch: 0.0,
                head_pitch: LAUGH_UP * gate,
                head_yaw: swings(t, &LAUGH_SWINGS, LAUGH_YAW, 0.3),
                head_roll: 0.0,
            }
        }
        Kind::Mock => {
            let gate = ramp(t, 0.3) * (1.0 - ramp(t - 2.1, 0.4));
            proto::HeadParams {
                neck_pitch: 0.0,
                head_pitch: MOCK_UP * gate,
                head_yaw: 0.0,
                head_roll: swings(t, &MOCK_SWINGS, MOCK_ROLL, 0.3),
            }
        }
        Kind::Defiant => {
            let gate = ramp(t, 0.3) * (1.0 - ramp(t - 1.6, 0.4));
            let yaw = if t < 0.85 {
                DEF_YAW * ramp(t - 0.15, 0.25)
            } else {
                DEF_YAW + (-DEF_YAW - DEF_YAW) * ramp(t - 0.85, 0.3)
            };
            proto::HeadParams {
                neck_pitch: 0.0,
                head_pitch: DEF_UP * gate,
                head_yaw: yaw * (1.0 - ramp(t - 1.6, 0.4)),
                head_roll: 0.0,
            }
        }
        Kind::Impatient => proto::HeadParams {
            neck_pitch: 0.0,
            head_pitch: IMP_UP * pulse(t, IMP_HUFF - 0.15, 0.15, 0.25, 0.4),
            head_yaw: swings(t, &IMP_SHAKES, IMP_YAW, 0.25),
            head_roll: 0.0,
        },
        // The skill's network owns the head; a zero head intent underneath.
        Kind::Startled => {
            // Head pitch negative is beak up (measured on the shipped policies). Up fast, back
            // to level over the last half second.
            let up = ramp(t, 0.15) * (1.0 - ramp(t - (STARTLED_LEN - 0.5), 0.5));
            proto::HeadParams {
                neck_pitch: 0.0,
                head_pitch: -up,
                head_yaw: 0.0,
                head_roll: 0.0,
            }
        }
        Kind::Peck => {
            let phase = t % PECK_PERIOD;
            // Forward = the neck pitched down (it tracks only about half, so it is asked for
            // more than its range) while the head pitches the other way to keep the beak level:
            // a chicken's jab, about 3 cm of travel on this neck. Head pitch negative = beak up,
            // measured in simulation; the two together read as "the head went forward", not
            // "the beak dropped".
            let down = if phase < PECK_DOWN {
                ramp(phase, 0.12)
            } else {
                1.0 - ramp(phase - PECK_DOWN, 0.15)
            };
            proto::HeadParams {
                neck_pitch: -PECK_NECK * down,
                head_pitch: -PECK_HEAD * down,
                head_yaw: 0.0,
                head_roll: 0.0,
            }
        }
        Kind::Curious => {
            // Tilt one way, then the other, then back — with a small dip of the neck that reads
            // as "looking at it". Rolls are within the joint's ±0.27 rad.
            let roll = if t < CURIOUS_LEG {
                0.27 * ramp(t, 0.3)
            } else if t < 2.0 * CURIOUS_LEG {
                0.27 - 0.54 * ramp(t - CURIOUS_LEG, 0.35)
            } else {
                -0.27 + 0.27 * ramp(t - 2.0 * CURIOUS_LEG, 0.3)
            };
            let dip = ramp(t, 0.4) * (1.0 - ramp(t - 2.0 * CURIOUS_LEG, 0.4));
            proto::HeadParams {
                neck_pitch: -0.5 * dip,
                head_pitch: 0.0,
                head_yaw: 0.0,
                head_roll: roll,
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_peck_goes_forward_twice_and_comes_back() {
        let downs: Vec<f64> = (0..(PECK_PERIOD * PECK_COUNT as f64 * 100.0) as usize)
            .map(|i| -head_at(Kind::Peck, i as f64 / 100.0).neck_pitch / PECK_NECK)
            .collect();
        // two separate excursions past 0.9, and back near zero between them and at the end
        let mut excursions = 0;
        let mut inside = false;
        for &d in &downs {
            if d > 0.9 && !inside {
                excursions += 1;
                inside = true;
            } else if d < 0.1 {
                inside = false;
            }
        }
        assert_eq!(excursions, 2, "two pecks");
        assert!(
            downs.last().unwrap().abs() < 0.05,
            "ends with the head back up"
        );
        assert!(downs.iter().all(|d| (0.0..=1.0).contains(d)));
    }

    #[test]
    fn curious_tilts_both_ways_within_the_roll_range_and_ends_centred() {
        let rolls: Vec<f64> = (0..(CURIOUS_LEG * 3.0 * 100.0) as usize)
            .map(|i| head_at(Kind::Curious, i as f64 / 100.0).head_roll)
            .collect();
        assert!(rolls.iter().cloned().fold(f64::MIN, f64::max) > 0.25);
        assert!(rolls.iter().cloned().fold(f64::MAX, f64::min) < -0.25);
        assert!(rolls.iter().all(|r| r.abs() <= 0.27 + 1e-9));
        assert!(rolls.last().unwrap().abs() < 0.02);
        let e = Expression::start(Kind::Curious, Instant::now());
        assert!(
            e.head_at(e.started + Expression::duration(Kind::Curious))
                .is_none()
        );
        assert!(e.head_at(e.started).is_some());
    }

    #[test]
    fn startled_looks_up_then_backs_away_then_settles() {
        assert!(
            head_at(Kind::Startled, 0.2).head_pitch < -0.9,
            "head up at once"
        );
        assert_eq!(
            twist_at(Kind::Startled, 0.1),
            None,
            "no walking before the head is up"
        );
        assert_eq!(twist_at(Kind::Startled, 1.0), Some(STARTLED_BACK));
        assert_eq!(twist_at(Kind::Startled, 1.8), None);
        assert!(
            head_at(Kind::Startled, STARTLED_LEN - 0.01)
                .head_pitch
                .abs()
                < 0.05,
            "level at the end"
        );
        assert_eq!(twist_at(Kind::Peck, 0.5), None);
        assert_eq!(twist_at(Kind::Curious, 0.5), None);
    }

    #[test]
    fn no_expression_touches_the_yaw_or_the_body() {
        for kind in [Kind::Peck, Kind::Curious, Kind::Startled] {
            for i in 0..300 {
                let h = head_at(kind, i as f64 / 100.0);
                assert_eq!(h.head_yaw, 0.0);
                assert!(h.neck_pitch <= 0.0, "the neck only tracks downward");
            }
        }
    }

    #[test]
    fn devastated_sits_droops_shakes_three_times_sobs_and_comes_back_level() {
        assert_eq!(
            Expression::skill_at_start(Kind::Devastated),
            Some("sit_toggle")
        );
        assert_eq!(
            Expression::sound_at_start(Kind::Devastated),
            Some("devastated")
        );
        for kind in [Kind::Peck, Kind::Curious, Kind::Startled] {
            assert_eq!(Expression::skill_at_start(kind), None);
            assert_eq!(Expression::sound_at_start(kind), None);
            assert_eq!(mouth_at(kind, 0.2), 0.0);
        }
        // Head level while the duck sits, fully drooped by 3.5 s, level again at the end.
        let h = head_at(Kind::Devastated, 1.0);
        assert_eq!((h.neck_pitch, h.head_pitch, h.head_yaw), (0.0, 0.0, 0.0));
        let h = head_at(Kind::Devastated, 4.5);
        assert!((h.neck_pitch + 1.5).abs() < 1e-9 && (h.head_pitch - 1.0).abs() < 1e-9);
        let h = head_at(Kind::Devastated, DEV_LEN - 0.01);
        assert!(h.neck_pitch.abs() < 0.01 && h.head_pitch.abs() < 0.01 && h.head_yaw.abs() < 1e-9);
        // The swings: +0.4, -0.4, +0.4 at 3, 4, 5 s, centred at 3.5 / 4.5 and outside 2.5-5.5.
        for (t, want) in [(3.0, 0.4), (4.0, -0.4), (5.0, 0.4), (3.5, 0.0), (4.5, 0.0)] {
            assert!(
                (head_at(Kind::Devastated, t).head_yaw - want).abs() < 1e-9,
                "yaw at {t}"
            );
        }
        assert_eq!(head_at(Kind::Devastated, 2.4).head_yaw, 0.0);
        assert_eq!(head_at(Kind::Devastated, 5.6).head_yaw, 0.0);
        for i in 0..(DEV_LEN * 100.0) as usize {
            let h = head_at(Kind::Devastated, i as f64 / 100.0);
            assert!(h.neck_pitch <= 0.0 && h.head_pitch >= 0.0 && h.head_yaw.abs() <= 0.4 + 1e-9);
            assert_eq!(h.head_roll, 0.0);
            let m = mouth_at(Kind::Devastated, i as f64 / 100.0);
            assert!((0.0..=1.0).contains(&m));
        }
        // The beak: open on the shock, shut in the silence, open on each sob, shut at the end.
        assert!(mouth_at(Kind::Devastated, 0.2) > 0.9);
        assert_eq!(mouth_at(Kind::Devastated, 2.0), 0.0);
        for t in [3.3, 4.3, 5.3] {
            assert!(mouth_at(Kind::Devastated, t) > 0.9, "sob at {t}");
        }
        assert_eq!(mouth_at(Kind::Devastated, 7.0), 0.0);
        assert_eq!(mouth_at(Kind::Devastated, DEV_LEN + 1.0), 0.0);
        // Seated: the sticks are locked out for the whole expression, then handed back.
        assert_eq!(
            twist_at(Kind::Devastated, 4.0),
            Some(proto::MoveParams::default())
        );
        assert_eq!(twist_at(Kind::Devastated, DEV_LEN), None);
        let e = Expression::start(Kind::Devastated, Instant::now());
        assert!(
            e.head_at(e.started + Expression::duration(Kind::Devastated))
                .is_none()
        );
        assert_eq!(
            e.mouth_at(e.started + Expression::duration(Kind::Devastated)),
            0.0
        );
        for kind in [Kind::Peck, Kind::Curious, Kind::Startled, Kind::Devastated] {
            assert!(!Expression::has_pose(kind));
            assert_eq!(pose_at(kind, 1.0), None);
        }
    }

    #[test]
    fn sad_lifts_then_droops_to_half_depth_shakes_twice_coos_and_comes_back_level() {
        assert_eq!(Expression::skill_at_start(Kind::Sad), None, "no sit");
        assert_eq!(Expression::sound_at_start(Kind::Sad), Some("sad"));
        assert!(Expression::has_pose(Kind::Sad));
        // Keyframes from the v7 simulation JSON (t, neck, head_pitch, head_yaw, body_pitch).
        for (t, neck, pitch, yaw, body) in [
            (0.0, 0.0, 0.0, 0.0, 0.0),
            (0.3, 0.0, -0.117, 0.0, 0.0),
            (0.6, 0.0, -0.249, 0.0, 0.0),
            (1.0, 0.0, -0.178, 0.0, 0.0),
            (1.3, 0.0, -0.035, 0.0, 0.0),
            (1.4, -0.036, 0.024, 0.0, 0.002),
            (1.5, -0.129, 0.086, 0.0, 0.009),
            (1.9, -0.489, 0.326, 0.0, 0.033),
            (2.0, -0.564, 0.376, 0.0, 0.038),
            (2.3, -0.719, 0.479, 0.0, 0.048),
            (2.5, -0.75, 0.5, 0.0, 0.05),
            (2.6, -0.75, 0.5, 0.027, 0.05),
            (3.1, -0.75, 0.5, 0.4, 0.05),
            (3.7, -0.75, 0.5, 0.0, 0.05),
            (4.3, -0.75, 0.5, -0.4, 0.05),
            (4.6, -0.75, 0.5, -0.2, 0.05),
            (4.9, -0.75, 0.5, 0.0, 0.05),
            (5.5, -0.75, 0.5, 0.0, 0.05),
            (6.0, -0.640, 0.427, 0.0, 0.043),
            (6.5, -0.375, 0.25, 0.0, 0.025),
            (7.0, -0.110, 0.073, 0.0, 0.007),
            (7.4, -0.005, 0.003, 0.0, 0.0),
        ] {
            let h = head_at(Kind::Sad, t);
            let p = pose_at(Kind::Sad, t).expect("posing");
            assert!(
                (h.neck_pitch - neck).abs() < 0.003,
                "neck at {t}: {}",
                h.neck_pitch
            );
            assert!(
                (h.head_pitch - pitch).abs() < 0.003,
                "pitch at {t}: {}",
                h.head_pitch
            );
            assert!(
                (h.head_yaw - yaw).abs() < 0.003,
                "yaw at {t}: {}",
                h.head_yaw
            );
            assert!((p.pitch - body).abs() < 0.002, "body at {t}: {}", p.pitch);
            assert!(p.active && p.z == 0.0 && p.roll == 0.0);
            assert_eq!(h.head_roll, 0.0);
        }
        for i in 0..(SAD_LEN * 100.0) as usize {
            let t = i as f64 / 100.0;
            let h = head_at(Kind::Sad, t);
            assert!(
                h.neck_pitch <= 0.0 && h.head_pitch >= -0.25 - 1e-9 && h.head_pitch <= 0.5 + 1e-9
            );
            assert!(h.head_yaw.abs() <= 0.4 + 1e-9);
            assert!((0.0..=1.0).contains(&mouth_at(Kind::Sad, t)));
        }
        // The beak: open through the droop (the coo), shut from the first shake on.
        assert!(mouth_at(Kind::Sad, 1.5) > 0.9);
        assert_eq!(mouth_at(Kind::Sad, 0.0), 0.0);
        assert_eq!(mouth_at(Kind::Sad, 3.3), 0.0);
        assert_eq!(mouth_at(Kind::Sad, 6.0), 0.0);
        // Sticks locked for the whole thing, then everything released.
        assert_eq!(twist_at(Kind::Sad, 3.0), Some(proto::MoveParams::default()));
        assert_eq!(twist_at(Kind::Sad, SAD_LEN), None);
        assert_eq!(pose_at(Kind::Sad, SAD_LEN), None);
        let e = Expression::start(Kind::Sad, Instant::now());
        assert_eq!(e.kind(), Kind::Sad);
        assert!(
            e.head_at(e.started + Expression::duration(Kind::Sad))
                .is_none()
        );
        assert!(
            e.pose_at(e.started + Expression::duration(Kind::Sad))
                .is_none()
        );
    }

    #[test]
    fn curious_quacks_comes_forward_tilts_right_then_left_on_the_chirps_and_comes_back() {
        assert_eq!(Expression::skill_at_start(Kind::CuriousQuacks), None);
        assert_eq!(
            Expression::sound_at_start(Kind::CuriousQuacks),
            Some("curious")
        );
        assert!(!Expression::has_pose(Kind::CuriousQuacks));
        assert_eq!(pose_at(Kind::CuriousQuacks, 1.0), None);
        // Roll keyframes from the simulation; neck and head pitch are zero throughout (the
        // head-forward phase was dropped on the robot).
        for (t, roll) in [
            (0.0, 0.0),
            (0.3, 0.0),
            (0.4, 0.0),
            (0.5, 0.066),
            (0.7, 0.333),
            (0.8, 0.35),
            (1.1, 0.201),
            (1.2, -0.133),
            (1.4, -0.44),
            (2.1, -0.44),
            (2.3, -0.288),
            (2.5, -0.042),
            (2.6, 0.0),
            (2.9, 0.0),
        ] {
            let (neck, pitch) = (0.0, 0.0);
            let h = head_at(Kind::CuriousQuacks, t);
            assert!(
                (h.neck_pitch - neck).abs() < 0.003,
                "neck at {t}: {}",
                h.neck_pitch
            );
            assert!(
                (h.head_pitch - pitch).abs() < 0.003,
                "pitch at {t}: {}",
                h.head_pitch
            );
            assert!(
                (h.head_roll - roll).abs() < 0.003,
                "roll at {t}: {}",
                h.head_roll
            );
            assert_eq!(h.head_yaw, 0.0);
        }
        for i in 0..(CQ_LEN * 100.0) as usize {
            let t = i as f64 / 100.0;
            let h = head_at(Kind::CuriousQuacks, t);
            assert!(
                h.neck_pitch == 0.0 && h.head_pitch == 0.0,
                "head stays put at {t}"
            );
            assert!((-0.44 - 1e-9..=0.35 + 1e-9).contains(&h.head_roll));
            assert!((0.0..=1.0).contains(&mouth_at(Kind::CuriousQuacks, t)));
        }
        // The beak: a snap on each chirp, shut in between and after.
        assert!(mouth_at(Kind::CuriousQuacks, 0.8) > 0.99);
        assert!(mouth_at(Kind::CuriousQuacks, 1.4) > 0.99);
        assert_eq!(mouth_at(Kind::CuriousQuacks, 0.5), 0.0);
        assert_eq!(mouth_at(Kind::CuriousQuacks, 1.1), 0.0);
        assert_eq!(mouth_at(Kind::CuriousQuacks, 2.0), 0.0);
        assert_eq!(
            twist_at(Kind::CuriousQuacks, 1.0),
            Some(proto::MoveParams::default())
        );
        assert_eq!(twist_at(Kind::CuriousQuacks, CQ_LEN), None);
        let e = Expression::start(Kind::CuriousQuacks, Instant::now());
        assert!(
            e.head_at(e.started + Expression::duration(Kind::CuriousQuacks))
                .is_none()
        );
    }

    /// Keyframes (t, neck, head_pitch, head_yaw, body_pitch) from the simulation JSON of each
    /// episode 3 pick, every 0.2 s, to 0.003.
    fn check_keyframes(kind: Kind, keys: &[(f64, f64, f64, f64, f64)], with_pose: bool) {
        for &(t, neck, pitch, yaw, body) in keys {
            let h = head_at(kind, t);
            assert!(
                (h.neck_pitch - neck).abs() < 0.003,
                "{kind:?} neck at {t}: {}",
                h.neck_pitch
            );
            assert!(
                (h.head_pitch - pitch).abs() < 0.003,
                "{kind:?} pitch at {t}: {}",
                h.head_pitch
            );
            assert!(
                (h.head_yaw - yaw).abs() < 0.003,
                "{kind:?} yaw at {t}: {}",
                h.head_yaw
            );
            if with_pose {
                let p = pose_at(kind, t).expect("posing");
                assert!(
                    (p.pitch - body).abs() < 0.003,
                    "{kind:?} body at {t}: {}",
                    p.pitch
                );
                assert!(p.active);
            } else {
                assert_eq!(pose_at(kind, t), None);
            }
        }
        let e = Expression::start(kind, Instant::now());
        assert!(e.head_at(e.started + Expression::duration(kind)).is_none());
        assert_eq!(twist_at(kind, 0.5), Some(proto::MoveParams::default()));
        assert_eq!(
            twist_at(kind, Expression::duration(kind).as_secs_f64()),
            None
        );
        for i in 0..(Expression::duration(kind).as_secs_f64() * 100.0) as usize {
            assert!((0.0..=1.0).contains(&mouth_at(kind, i as f64 / 100.0)));
        }
    }

    #[test]
    fn yes_nods_once_and_quacks_at_the_bottom() {
        assert_eq!(Expression::sound_at_start(Kind::Yes), Some("yes"));
        assert_eq!(Expression::skill_at_start(Kind::Yes), None);
        check_keyframes(
            Kind::Yes,
            &[
                (0.0, 0.000, 0.000, 0.000, 0.000),
                (0.2, 0.000, 0.458, 0.000, 0.000),
                (0.4, 0.000, 0.700, 0.000, 0.000),
                (0.6, 0.000, 0.272, 0.000, 0.000),
                (0.8, 0.000, 0.000, 0.000, 0.000),
                (1.0, 0.000, 0.000, 0.000, 0.000),
                (1.2, 0.000, 0.000, 0.000, 0.000),
                (1.4, 0.000, 0.000, 0.000, 0.000),
            ],
            false,
        );
        assert!(mouth_at(Kind::Yes, 0.7) > 0.9);
        assert_eq!(mouth_at(Kind::Yes, 0.3), 0.0);
        assert_eq!(mouth_at(Kind::Yes, 1.2), 0.0);
    }

    #[test]
    fn no_shakes_once_with_two_notes() {
        assert_eq!(Expression::sound_at_start(Kind::No), Some("no"));
        check_keyframes(
            Kind::No,
            &[
                (0.0, 0.000, 0.000, 0.000, 0.000),
                (0.2, 0.000, 0.000, 0.190, 0.000),
                (0.4, 0.000, 0.000, 0.523, 0.000),
                (0.6, 0.000, 0.000, 0.000, 0.000),
                (0.8, 0.000, 0.000, -0.523, 0.000),
                (1.0, 0.000, 0.000, -0.190, 0.000),
                (1.2, 0.000, 0.000, -0.000, 0.000),
                (1.4, 0.000, 0.000, -0.000, 0.000),
                (1.6, 0.000, 0.000, -0.000, 0.000),
            ],
            false,
        );
        assert!(mouth_at(Kind::No, 0.8) > 0.9 && mouth_at(Kind::No, 1.3) > 0.9);
        assert_eq!(mouth_at(Kind::No, 1.1), 0.0);
    }

    #[test]
    fn angry_snaps_four_times_bows_on_three_and_opens_wide_first() {
        assert_eq!(Expression::sound_at_start(Kind::Angry), Some("angry"));
        assert!(Expression::has_pose(Kind::Angry));
        check_keyframes(
            Kind::Angry,
            &[
                (0.0, 0.000, 0.000, 0.000, 0.000),
                (0.2, 0.000, -0.096, 0.259, 0.035),
                (0.4, 0.000, 0.026, 0.700, 0.127),
                (0.6, 0.000, -0.345, 0.700, 0.000),
                (0.8, 0.000, -0.183, 0.181, 0.035),
                (1.0, 0.000, 0.026, -0.700, 0.127),
                (1.2, 0.000, -0.345, -0.700, 0.000),
                (1.4, 0.000, -0.183, -0.181, 0.035),
                (1.6, 0.000, 0.026, 0.700, 0.127),
                (1.8, 0.000, -0.345, 0.700, 0.000),
                (2.0, 0.000, 0.100, 0.000, 0.000),
                (2.2, 0.000, -0.143, 0.000, 0.000),
                (2.4, 0.000, -0.051, 0.000, 0.000),
            ],
            true,
        );
        // The leash release: wide open for 0.4 s around the first bark.
        for t in [0.3, 0.45, 0.6] {
            assert!(mouth_at(Kind::Angry, t) > 0.99, "wide at {t}");
        }
        assert_eq!(mouth_at(Kind::Angry, 0.1), 0.0);
        assert_eq!(pose_at(Kind::Angry, ANGRY_LEN), None);
        for i in 0..(ANGRY_LEN * 100.0) as usize {
            let h = head_at(Kind::Angry, i as f64 / 100.0);
            assert_eq!(h.neck_pitch, 0.0, "the neck never moves");
            assert!(h.head_yaw.abs() <= 0.7 + 1e-9);
        }
    }

    #[test]
    fn mmh_tilts_and_asks() {
        assert_eq!(Expression::sound_at_start(Kind::Mmh), Some("mmh"));
        check_keyframes(
            Kind::Mmh,
            &[
                (0.0, 0.000, 0.000, 0.000, 0.000),
                (0.2, 0.000, 0.000, 0.000, 0.000),
                (0.4, 0.000, 0.000, 0.000, 0.000),
                (0.6, 0.000, 0.000, 0.000, 0.000),
                (0.8, 0.000, 0.000, 0.000, 0.000),
                (1.0, 0.000, 0.000, 0.000, 0.000),
                (1.2, 0.000, 0.000, 0.000, 0.000),
                (1.4, 0.000, 0.000, 0.000, 0.000),
                (1.6, 0.000, 0.000, 0.000, 0.000),
                (1.8, 0.000, 0.000, 0.000, 0.000),
            ],
            false,
        );
        for (t, roll) in [(0.45, 0.0), (0.75, 0.22), (1.25, 0.22), (1.6, 0.0)] {
            assert!(
                (head_at(Kind::Mmh, t).head_roll - roll).abs() < 1e-9,
                "roll at {t}"
            );
        }
        assert!(mouth_at(Kind::Mmh, 0.8) > 0.99);
        assert_eq!(mouth_at(Kind::Mmh, 0.3), 0.0);
    }

    #[test]
    fn yes_fast_is_the_nod_with_a_curt_wak() {
        assert_eq!(Expression::sound_at_start(Kind::YesFast), Some("yes_fast"));
        assert_eq!(
            Expression::duration(Kind::YesFast),
            Expression::duration(Kind::Yes)
        );
        for i in 0..150 {
            let t = i as f64 / 100.0;
            assert_eq!(
                head_at(Kind::YesFast, t).head_pitch,
                head_at(Kind::Yes, t).head_pitch
            );
        }
        assert!(mouth_at(Kind::YesFast, 0.6) > 0.9);
        assert_eq!(mouth_at(Kind::YesFast, 1.0), 0.0);
    }

    #[test]
    fn laugh_wags_with_the_beak_up_and_bobs_on_every_ha() {
        assert_eq!(Expression::sound_at_start(Kind::Laugh), Some("laugh"));
        assert!(Expression::has_pose(Kind::Laugh));
        check_keyframes(
            Kind::Laugh,
            &[
                (0.0, 0.000, -0.000, 0.000, 0.000),
                (0.2, 0.000, -0.525, 0.225, 0.000),
                (0.4, 0.000, -0.700, 0.432, 0.085),
                (0.6, 0.000, -0.700, 0.064, 0.000),
                (0.8, 0.000, -0.700, -0.379, 0.025),
                (1.0, 0.000, -0.700, -0.318, 0.075),
                (1.2, 0.000, -0.700, 0.318, 0.075),
                (1.4, 0.000, -0.700, 0.379, 0.075),
                (1.6, 0.000, -0.700, -0.064, 0.050),
                (1.8, 0.000, -0.700, -0.432, 0.075),
                (2.0, 0.000, -0.700, -0.225, 0.090),
                (2.2, 0.000, -0.700, 0.345, 0.040),
                (2.4, 0.000, -0.700, 0.337, 0.050),
                (2.6, 0.000, -0.597, 0.000, 0.000),
                (2.8, 0.000, -0.103, 0.000, 0.000),
            ],
            true,
        );
        // The run dies out: the last ha's open the beak about halfway.
        for h in LAUGH_HAS {
            let peak = (0..=25)
                .map(|i| mouth_at(Kind::Laugh, h + 0.05 + i as f64 * 0.01))
                .fold(0.0, f64::max);
            assert!(peak > 0.45, "ha at {h}: {peak}");
        }
        assert_eq!(pose_at(Kind::Laugh, LAUGH_LEN), None);
    }

    #[test]
    fn mock_rolls_the_head_on_the_staccato_run() {
        assert_eq!(Expression::sound_at_start(Kind::Mock), Some("mock"));
        assert!(Expression::has_pose(Kind::Mock));
        check_keyframes(
            Kind::Mock,
            &[
                (0.0, 0.000, -0.000, 0.000, 0.000),
                (0.2, 0.000, -0.413, 0.000, 0.000),
                (0.4, 0.000, -0.550, 0.000, 0.085),
                (0.6, 0.000, -0.550, 0.000, 0.095),
                (0.8, 0.000, -0.550, 0.000, 0.099),
                (1.0, 0.000, -0.550, 0.000, 0.099),
                (1.2, 0.000, -0.550, 0.000, 0.001),
                (1.4, 0.000, -0.550, 0.000, 0.075),
                (1.6, 0.000, -0.550, 0.000, 0.070),
                (1.8, 0.000, -0.550, 0.000, 0.062),
                (2.0, 0.000, -0.550, 0.000, 0.042),
                (2.2, 0.000, -0.469, 0.000, 0.000),
                (2.4, 0.000, -0.081, 0.000, 0.000),
            ],
            true,
        );
        for i in 0..(MOCK_LEN * 100.0) as usize {
            let h = head_at(Kind::Mock, i as f64 / 100.0);
            assert_eq!(h.head_yaw, 0.0);
            assert!(h.head_roll.abs() <= MOCK_ROLL + 1e-9);
        }
        assert_eq!(pose_at(Kind::Mock, MOCK_LEN), None);
    }

    #[test]
    fn defiant_looks_up_left_then_up_right_with_a_quack_each() {
        assert_eq!(Expression::sound_at_start(Kind::Defiant), Some("defiant"));
        check_keyframes(
            Kind::Defiant,
            &[
                (0.0, 0.000, -0.000, 0.000, 0.000),
                (0.2, 0.000, -0.450, 0.057, 0.000),
                (0.4, 0.000, -0.600, 0.600, 0.000),
                (0.6, 0.000, -0.600, 0.600, 0.000),
                (0.8, 0.000, -0.600, 0.600, 0.000),
                (1.0, 0.000, -0.600, -0.000, 0.000),
                (1.2, 0.000, -0.600, -0.600, 0.000),
                (1.4, 0.000, -0.600, -0.600, 0.000),
                (1.6, 0.000, -0.600, -0.600, 0.000),
                (1.8, 0.000, -0.300, -0.300, 0.000),
                (2.0, 0.000, -0.000, -0.000, 0.000),
            ],
            false,
        );
        assert!(mouth_at(Kind::Defiant, 0.65) > 0.9 && mouth_at(Kind::Defiant, 1.35) > 0.9);
        assert_eq!(mouth_at(Kind::Defiant, 1.0), 0.0);
    }

    #[test]
    fn impatient_shakes_four_times_and_huffs() {
        assert_eq!(
            Expression::sound_at_start(Kind::Impatient),
            Some("impatient")
        );
        assert!(Expression::has_pose(Kind::Impatient));
        check_keyframes(
            Kind::Impatient,
            &[
                (0.0, 0.000, -0.000, 0.000, 0.000),
                (0.2, 0.000, -0.000, 0.138, 0.000),
                (0.4, 0.000, -0.000, 0.370, 0.068),
                (0.6, 0.000, -0.000, -0.153, 0.000),
                (0.8, 0.000, -0.000, -0.370, 0.068),
                (1.0, 0.000, -0.000, 0.153, 0.000),
                (1.2, 0.000, -0.000, 0.370, 0.068),
                (1.4, 0.000, -0.000, -0.153, 0.000),
                (1.6, 0.000, -0.000, -0.362, 0.068),
                (1.8, 0.000, -0.175, -0.000, 0.000),
                (2.0, 0.000, -0.700, -0.000, 0.000),
                (2.2, 0.000, -0.673, -0.000, 0.000),
                (2.4, 0.000, -0.216, -0.000, 0.000),
            ],
            true,
        );
        assert!(mouth_at(Kind::Impatient, 2.2) > 0.9, "the huff");
        assert_eq!(pose_at(Kind::Impatient, IMP_LEN), None);
    }

    #[test]
    fn excited_wags_six_times_bobbing_with_the_beak_climbing() {
        assert_eq!(Expression::sound_at_start(Kind::Excited), Some("excited"));
        assert!(Expression::has_pose(Kind::Excited));
        assert_eq!(Expression::skill_at_start(Kind::Excited), None);
        check_keyframes(
            Kind::Excited,
            &[
                (0.0, 0.000, -0.000, 0.000, 0.000),
                (0.2, 0.000, -0.136, 0.150, 0.000),
                (0.4, 0.000, -0.150, 0.600, 0.120),
                (0.6, 0.000, -0.161, 0.249, 0.000),
                (0.8, 0.000, -0.192, -0.393, 0.000),
                (1.0, 0.000, -0.241, -0.571, 0.102),
                (1.2, 0.000, -0.304, -0.000, 0.000),
                (1.4, 0.000, -0.377, 0.571, 0.090),
                (1.6, 0.000, -0.454, 0.300, 0.018),
                (1.8, 0.000, -0.528, -0.460, 0.030),
                (2.0, 0.000, -0.594, -0.424, 0.060),
                (2.2, 0.000, -0.647, 0.424, 0.030),
                (2.4, 0.000, -0.683, 0.374, 0.060),
                (2.6, 0.000, -0.699, -0.541, 0.090),
                (2.8, 0.000, -0.700, -0.300, 0.018),
                (3.0, 0.000, -0.700, 0.000, 0.120),
                (3.2, 0.000, -0.411, 0.000, 0.060),
            ],
            true,
        );
        for q in EXCITED_Q {
            let peak = (0..=20)
                .map(|i| mouth_at(Kind::Excited, q + 0.1 + i as f64 * 0.01))
                .fold(0.0, f64::max);
            assert!(peak > 0.9, "chirp at {q}: {peak}");
        }
        assert_eq!(mouth_at(Kind::Excited, 0.3), 0.0);
        assert_eq!(pose_at(Kind::Excited, EXCITED_LEN), None);
        for i in 0..(EXCITED_LEN * 100.0) as usize {
            let h = head_at(Kind::Excited, i as f64 / 100.0);
            assert_eq!(h.neck_pitch, 0.0);
            assert!(
                h.head_pitch <= 0.0 && h.head_pitch >= -0.7 - 1e-9,
                "beak never below level"
            );
            assert!(pose_at(Kind::Excited, i as f64 / 100.0).unwrap().pitch <= 0.26);
        }
    }
}

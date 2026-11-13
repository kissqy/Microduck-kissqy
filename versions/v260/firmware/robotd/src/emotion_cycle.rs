//! R3 selects one official expression. Playback has one owner: the control loop.
use crate::expressions::{Expression, Kind};
use std::time::Instant;

pub const CYCLE: [(&str, Kind); 13] = [
    ("sad", Kind::Sad),
    ("devastated", Kind::Devastated),
    ("curious", Kind::CuriousQuacks),
    ("mmh", Kind::Mmh),
    ("yes", Kind::Yes),
    ("yes_fast", Kind::YesFast),
    ("no", Kind::No),
    ("angry", Kind::Angry),
    ("excited", Kind::Excited),
    ("laugh", Kind::Laugh),
    ("mock", Kind::Mock),
    ("defiant", Kind::Defiant),
    ("impatient", Kind::Impatient),
];

#[derive(Default)]
pub struct Player {
    next: usize,
    pub playing: Option<Expression>,
}
impl Player {
    pub fn peek(&self) -> (&'static str, Kind) {
        CYCLE[self.next]
    }
    pub fn start(&mut self, now: Instant) -> (&'static str, Kind) {
        let selected = self.peek();
        self.playing = Some(Expression::start(selected.1, now));
        self.next = (self.next + 1) % CYCLE.len();
        selected
    }
    pub fn start_named(&mut self, index: usize, now: Instant) -> (&'static str, Kind) {
        let selected = CYCLE[index];
        self.playing = Some(Expression::start(selected.1, now));
        selected
    }
    pub fn stop(&mut self) {
        self.playing = None;
    }
}

pub fn allowed(
    walking: bool,
    driving: bool,
    fallen: bool,
    busy: bool,
    fresh: bool,
    still: bool,
) -> bool {
    walking && driving && !fallen && !busy && fresh && still
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn pending_and_playing_presses_cannot_queue_and_cancel_drops_pending() {
        crate::intents::Intents::test_emotion_slot();
    }
    #[test]
    fn thirteen_unique_emotions_wrap_without_play_dead_or_scene_commands() {
        let mut p = Player::default();
        let now = Instant::now();
        let names: std::collections::HashSet<_> = CYCLE.iter().map(|v| v.0).collect();
        assert_eq!(names.len(), 13);
        assert!(!names.contains("play_dead") && !names.contains("pick"));
        for &(name, kind) in &CYCLE {
            assert_eq!(p.start(now), (name, kind));
            p.stop();
        }
        assert_eq!(p.peek().0, "sad");
    }
    #[test]
    fn named_selection_does_not_advance_r3_cycle() {
        let mut p=Player::default();let now=Instant::now();
        assert_eq!(p.start_named(8,now).0,"excited");p.stop();
        assert_eq!(p.peek().0,"sad");
        p.start(now);p.stop();p.start_named(6,now);p.stop();
        assert_eq!(p.peek().0,"devastated");
    }

    #[test]
    fn refusals_and_cancel_do_not_consume_the_next_expression() {
        let mut p = Player::default();
        let now = Instant::now();
        assert_eq!(p.peek().0, "sad");
        assert_eq!(p.peek().0, "sad");
        p.start(now);
        p.stop();
        assert_eq!(p.peek().0, "devastated");
    }
    #[test]
    fn only_fresh_upright_idle_walking_policy_may_start() {
        assert!(allowed(true, true, false, false, true, true));
        for condition in 0..6 {
            let mut v = [true, true, false, false, true, true];
            v[condition] = !v[condition];
            assert!(!allowed(v[0], v[1], v[2], v[3], v[4], v[5]));
        }
    }
}

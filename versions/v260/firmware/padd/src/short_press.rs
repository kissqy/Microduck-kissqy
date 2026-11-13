//! Release-triggered tap: holding up must remain exclusively the drive-mode selector.
use std::time::{Duration, Instant};
#[derive(Default)]
pub struct ShortPress { since: Option<Instant> }
impl ShortPress {
    pub fn press(&mut self, now: Instant) { self.since.get_or_insert(now); }
    pub fn release(&mut self, now: Instant) -> bool {
        self.since.take().is_some_and(|since| now.saturating_duration_since(since) < Duration::from_millis(500))
    }
    pub fn reset(&mut self) { self.since = None; }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn tap_once_long_hold_never_starts_flamingo_and_reconnect_cannot_replay() {
        let mut tap = ShortPress::default(); let at = Instant::now();
        assert!(!tap.release(at));
        tap.press(at); tap.press(at+Duration::from_millis(100));
        assert!(tap.release(at+Duration::from_millis(200)));
        assert!(!tap.release(at+Duration::from_millis(201)));
        tap.press(at); assert!(!tap.release(at+Duration::from_secs(2)));
        tap.press(at); tap.reset(); assert!(!tap.release(at+Duration::from_millis(100)));
        tap.press(at); assert!(!tap.release(at+Duration::from_millis(500)));
    }
}

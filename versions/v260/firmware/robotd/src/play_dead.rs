//! Lifecycle of the independent play-dead policy. The policy owns all 14 joints;
//! normal completion hands back to Walk, while cancellation uses the existing relax path.
use std::time::{Duration, Instant};
use crate::intents::Snapshot;

pub const DURATION_SECONDS: f64 = 5.0;

pub struct Player {
    started: Instant,
    generation: u64,
    pub stopping: bool,
}
impl Player {
    pub fn new(started: Instant, generation: u64) -> Self {
        Self { started, generation, stopping: false }
    }
    pub fn finished(&self, now: Instant) -> bool {
        now.saturating_duration_since(self.started).as_secs_f64() >= DURATION_SECONDS
    }
    pub fn must_stop(&self, _now: Instant, snapshot: &Snapshot, running: bool, feedback_ok: bool) -> bool {
        self.stopping || !running || !snapshot.enabled
            || snapshot.enable_generation != self.generation || !feedback_ok
            || snapshot.twist_age > Duration::from_millis(300)
            || snapshot.command.twist.iter().any(|v| !v.is_finite() || v.abs() >= 1e-6)
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn five_seconds_complete_without_requesting_relax() {
        let i=crate::intents::Intents::new();i.set_enabled(true);i.set_twist([0.;3]);
        let s=i.snapshot();let now=Instant::now();let p=Player::new(now,s.enable_generation);
        assert!(!p.finished(now+Duration::from_millis(4999)));
        assert!(p.finished(now+Duration::from_secs(5)));
        assert!(!p.must_stop(now+Duration::from_secs(5),&s,true,true));
    }
    #[test]
    fn explicit_stop_or_stale_feedback_still_wins_at_completion() {
        let i=crate::intents::Intents::new();i.set_enabled(true);i.set_twist([0.;3]);
        let mut s=i.snapshot();let now=Instant::now();let p=Player::new(now,s.enable_generation);
        let end=now+Duration::from_secs(5);
        assert!(p.must_stop(end,&s,false,true));assert!(p.must_stop(end,&s,true,false));
        s.enabled=false;assert!(p.must_stop(end,&s,true,true));s.enabled=true;
        s.command.twist[0]=0.1;assert!(p.must_stop(end,&s,true,true));s.command.twist[0]=0.;
        s.enable_generation+=1;assert!(p.must_stop(end,&s,true,true));s.enable_generation-=1;
        s.twist_age=Duration::from_millis(301);assert!(p.must_stop(end,&s,true,true));
    }
}

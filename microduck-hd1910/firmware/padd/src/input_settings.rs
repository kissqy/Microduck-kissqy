//! R17 live input limits. These only cap mouth intent and head targets.
//! Sound thresholds, action mapping, policy and motor communication stay upstream.
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant, SystemTime};

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct Settings {
    pub mouth_percent: f64,
    pub head_rad: f64,
}
impl Settings {
    fn load(path: &Path) -> Result<Self, Box<dyn std::error::Error>> {
        let result: Self = serde_json::from_str(&std::fs::read_to_string(path)?)?;
        if !result.mouth_percent.is_finite()
            || !(0.0..=100.0).contains(&result.mouth_percent)
            || ![0.5, 1.0, 2.5].contains(&result.head_rad)
        {
            return Err("invalid R17 input limits".into());
        }
        Ok(result)
    }
    pub fn mouth(self, rt: f64, lt: f64) -> f64 {
        rt.max(lt) * self.mouth_percent / 100.0
    }
}
pub struct Live {
    pub settings: Settings,
    path: Option<PathBuf>,
    report: PathBuf,
    checked: Option<Instant>,
    loaded: Option<SystemTime>,
}
impl Live {
    pub fn new(path: Option<PathBuf>, report: PathBuf, max_head: f64) -> Self {
        Self {
            settings: Settings {
                mouth_percent: 100.0,
                head_rad: max_head,
            },
            path,
            report,
            checked: None,
            loaded: None,
        }
    }
    pub fn poll(&mut self, now: Instant) {
        if self
            .checked
            .is_some_and(|last| now.duration_since(last) < Duration::from_millis(100))
        {
            return;
        }
        self.checked = Some(now);
        let Some(path) = &self.path else {
            return;
        };
        let modified = std::fs::metadata(path).and_then(|m| m.modified()).ok();
        if modified.is_none() || self.loaded == modified {
            return;
        }
        match Settings::load(path) {
            Ok(settings) => {
                let report =
                    serde_json::json!({"pid":std::process::id(),"path":path,"settings":settings});
                let temp = self.report.with_extension("tmp");
                let saved = std::fs::write(&temp, report.to_string())
                    .and_then(|()| std::fs::rename(&temp, &self.report));
                if let Err(error) = saved {
                    tracing::warn!(%error,"R17 input limits acknowledgement failed");
                }
                self.settings = settings;
                self.loaded = modified;
            }
            Err(error) => {
                tracing::warn!(%error,"R17 input limits refused; previous values retained");
                self.loaded = modified;
            }
        }
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn mouth_cap_keeps_raw_triggers_for_sound_and_never_opens_at_idle() {
        let limits = Settings {
            mouth_percent: 20.0,
            head_rad: 0.5,
        };
        assert_eq!(limits.mouth(1.0, 0.0), 0.2);
        assert_eq!(limits.mouth(0.0, 0.0), 0.0);
        assert_eq!(limits.mouth(0.1, 0.5), 0.1);
    }
    #[test]
    fn live_changes_confirm_pid_and_keep_previous_on_invalid_file() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("settings.json");
        let report = dir.path().join("readback.json");
        std::fs::write(&path, r#"{"mouth_percent":60,"head_rad":0.5}"#).unwrap();
        let mut live = Live::new(Some(path.clone()), report.clone(), 2.5);
        let now = Instant::now();
        live.poll(now);
        assert_eq!(
            live.settings,
            Settings {
                mouth_percent: 60.0,
                head_rad: 0.5
            }
        );
        let feedback: serde_json::Value =
            serde_json::from_str(&std::fs::read_to_string(report).unwrap()).unwrap();
        assert_eq!(feedback["pid"], std::process::id());
        assert_eq!(feedback["settings"]["mouth_percent"], 60.0);
        std::fs::write(path, r#"{"mouth_percent":120,"head_rad":0.5}"#).unwrap();
        live.poll(now + Duration::from_secs(1));
        assert_eq!(live.settings.mouth_percent, 60.0);
    }
}

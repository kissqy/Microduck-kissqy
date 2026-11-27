//! The codec's output level and mute, behind [`proto::method::ROBOT_VOLUME`].
//!
//! **The controls and the curve are duckphone's, deliberately.** `duckphone/server.py` has read
//! and written `PCM Playback Volume` on the AIC3104 since the web page got a sound panel, and the
//! phone app is that panel on another transport. Two implementations that chose their own control
//! names or their own percent curve would disagree about what "60%" means on the same robot, and
//! the disagreement would be audible rather than visible — which is the worse kind.
//!
//! Reading and writing share one method because the answer is always the codec's actual state.
//! `{}` reads; `percent` and/or `muted` write first. Every write is followed by `alsactl store`,
//! because the codec comes up at the image's default level otherwise and a volume set from a
//! phone that does not survive a reboot reads as a bug.
//!
//! `robotd` runs as root, so unlike duckphone's `sudo -n` there is nothing to fail here on
//! permissions. The command runner is injectable so the tests can pin the sequence of `amixer`
//! calls without a sound card.

use duck_ipc_proto::{VolumeParams, VolumeResult};

/// The mixer control that carries the level. Two channels, hence the comma-separated readback.
const VOLUME_CONTROL: &str = "PCM Playback Volume";
/// Line output on/off — what the UI calls mute.
const MUTE_CONTROL: &str = "Line Playback Switch";

/// Where the installer records which card the voice codec is.
const VOICE_SETUP: &str = "/opt/robot/feetech-ft5-r5/voice-device.json";

/// Percent → the codec's 0–127 register. Same curve as duckphone and the R17 console.
pub fn percent_to_raw(percent: u8) -> i32 {
    if percent == 0 {
        return 0;
    }
    let percent = f64::from(percent.min(100));
    (127.0 + 40.0 * (percent / 100.0).log10())
        .round()
        .clamp(0.0, 127.0) as i32
}

/// The codec's register → percent, the inverse of [`percent_to_raw`].
pub fn raw_to_percent(raw: i32) -> u8 {
    let raw = f64::from(raw.clamp(0, 127));
    (100.0 * 10f64.powf((raw - 127.0) / 40.0))
        .round()
        .clamp(0.0, 100.0) as u8
}

/// Which ALSA card the voice codec is, from the installer's file.
///
/// Two shapes exist in the wild: an explicit `card` (`"aic3104"`, `"1"`), and only a
/// `slave` (`"plughw:aic3104"`) as this R17 writes. Falling back to card `0` when only
/// `slave` was given picks the HDMI card, where `PCM Playback Volume` does not exist —
/// that is exactly how `robot.volume` ended up failing the readback check on the robot.
///
/// The name is validated rather than trusted: it reaches a command line, and a file that said
/// `0; rm -rf /` would otherwise be handed to `amixer -c` as an argument.
fn alsa_card() -> String {
    match std::fs::read_to_string(VOICE_SETUP) {
        Ok(text) => card_from_setup(&text),
        Err(_) => "0".to_owned(),
    }
}

fn card_from_setup(text: &str) -> String {
    let Ok(value) = serde_json::from_str::<serde_json::Value>(text) else {
        return "0".to_owned();
    };
    value
        .get("card")
        .and_then(|card| card.as_str())
        .and_then(valid_card_id)
        .or_else(|| {
            value
                .get("slave")
                .and_then(|slave| slave.as_str())
                .and_then(card_from_slave)
        })
        .unwrap_or_else(|| "0".to_owned())
}

/// `plughw:aic3104` → `aic3104`；`hw:1,0` → `1`。
fn card_from_slave(slave: &str) -> Option<String> {
    let tail = slave.rsplit(':').next()?;
    valid_card_id(tail.split(',').next().unwrap_or(tail).trim())
}

fn valid_card_id(card: &str) -> Option<String> {
    let ok = !card.is_empty()
        && card
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || c == '_' || c == '-');
    ok.then(|| card.to_owned())
}

/// Runs `amixer` with the arguments given, returning stdout.
fn system_amixer(args: &[&str]) -> Result<String, String> {
    let output = std::process::Command::new("amixer")
        .args(args)
        .output()
        .map_err(|e| format!("amixer 无法启动：{e}"))?;
    if !output.status.success() {
        let why = String::from_utf8_lossy(&output.stderr);
        let why = why.trim();
        return Err(format!(
            "amixer 失败：{}",
            if why.is_empty() { "没有输出" } else { why }
        ));
    }
    Ok(String::from_utf8_lossy(&output.stdout).into_owned())
}

/// The `: values=…` line of an `amixer cget`/`cset` dump.
///
/// `amixer` also prints a type line — `; type=INTEGER,access=rw---R--,values=2,min=0,…` — which
/// contains `values=` too. Taking the first match there reads the **channel count** (2) instead
/// of the level, so every write looked like a mismatched readback on the AIC3104. Only the line
/// that begins with `:` carries the value.
fn values_line(output: &str) -> Option<&str> {
    output
        .lines()
        .map(str::trim_start)
        .find(|line| line.starts_with(':') && line.contains("values="))
}

/// The numeric value out of `  : values=100,100`.
fn value_of(output: &str) -> Option<i32> {
    values_line(output)?
        .split("values=")
        .nth(1)?
        .trim()
        .split(',')
        .next()?
        .trim()
        .parse()
        .ok()
}

/// Whether the switch's first channel reads off.
fn switch_is_off(output: &str) -> bool {
    values_line(output)
        .and_then(|line| line.split("values=").nth(1))
        .map(|rest| rest.trim().starts_with("off"))
        .unwrap_or(false)
}

/// `amixer` on one card, with persistence folded in.
///
/// The runner is a field rather than a free function for the tests' sake: they need to see the
/// exact arguments and to answer with canned output, and a test that shelled out to a real
/// `amixer` would pass or fail on whatever sound card the machine happens to have.
pub struct Mixer {
    card: String,
    amixer: Box<dyn Fn(&[&str]) -> Result<String, String>>,
    /// `alsactl store` after a write. Off in tests, where there is no card to store.
    persist: bool,
}

impl Mixer {
    /// The real one: this robot's card, the system `amixer`, and persistence on.
    pub fn system() -> Self {
        Self {
            card: alsa_card(),
            amixer: Box::new(system_amixer),
            persist: true,
        }
    }

    /// `cget`/`cset` one named control.
    fn control(&self, verb: &str, control: &str, value: Option<&str>) -> Result<String, String> {
        let name = format!("name={control}");
        let mut args = vec!["-c", self.card.as_str(), verb, name.as_str()];
        if let Some(value) = value {
            args.push(value);
        }
        (self.amixer)(&args)
    }

    fn set_switch(&self, muted: bool) -> Result<(), String> {
        let value = if muted { "off,off" } else { "on,on" };
        self.control("cset", MUTE_CONTROL, Some(value))?;
        Ok(())
    }

    /// What the codec is at now, as read back.
    pub fn status(&self) -> Result<VolumeResult, String> {
        let volume = self.control("cget", VOLUME_CONTROL, None)?;
        let raw = value_of(&volume).ok_or_else(|| "未取得声卡音量回读".to_owned())?;
        // A card without the switch is a card that cannot be muted, not a failure to read the
        // level — duckphone treats it the same way.
        let muted = self
            .control("cget", MUTE_CONTROL, None)
            .map(|switch| switch_is_off(&switch))
            .unwrap_or(false);
        Ok(VolumeResult {
            percent: if muted { 0 } else { raw_to_percent(raw) },
            muted,
        })
    }

    /// Apply the request's fields, in order, then report what the codec ended at.
    ///
    /// `percent` is applied before `muted` so that "60% and unmuted" is one call rather than two;
    /// a client that sends only `muted` leaves the level alone, which is what a mute button does.
    pub fn apply(&self, params: &VolumeParams) -> Result<VolumeResult, String> {
        let mut wrote = false;
        if let Some(percent) = params.percent {
            if percent > 100 {
                return Err("音量必须是 0～100 的整数".to_owned());
            }
            let raw = percent_to_raw(percent);
            let echoed = self.control("cset", VOLUME_CONTROL, Some(&raw.to_string()))?;
            if value_of(&echoed) != Some(raw) {
                return Err("音量实际回读不符".to_owned());
            }
            self.set_switch(percent == 0)?;
            wrote = true;
        }
        if let Some(muted) = params.muted {
            self.set_switch(muted)?;
            wrote = true;
        }
        if wrote && self.persist {
            // A failed store is not a failed call: the level is in effect now, and saying so is
            // more use than refusing a setting that already happened.
            match std::process::Command::new("alsactl")
                .args(["store", &self.card])
                .output()
            {
                Ok(output) if output.status.success() => {}
                Ok(output) => tracing::warn!(
                    card = %self.card,
                    why = %String::from_utf8_lossy(&output.stderr).trim(),
                    "音量已生效，但保存到 ALSA 失败（重启后可能恢复默认）"
                ),
                Err(e) => tracing::warn!(
                    card = %self.card,
                    error = %e,
                    "音量已生效，但保存到 ALSA 失败（重启后可能恢复默认）"
                ),
            }
        }
        self.status()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::cell::RefCell;
    use std::collections::VecDeque;

    #[test]
    fn the_type_line_is_not_the_value_line() {
        // 板上的真实输出：类型行里也有 values=2（声道数），先匹配它就会把 121 读成 2。
        let cset = "numid=26,iface=MIXER,name='PCM Playback Volume'\n  \
                    ; type=INTEGER,access=rw---R--,values=2,min=0,max=127,step=0\n  \
                    : values=121,121\n  \
                    | dBscale-min=-63.50dB,step=0.50dB,mute=0";
        assert_eq!(value_of(cset), Some(121));
        let switch = "numid=46,iface=MIXER,name='Line Playback Switch'\n  \
                      ; type=BOOLEAN,access=rw------,values=2\n  \
                      : values=off,off";
        assert!(switch_is_off(switch));
        assert!(!switch_is_off(&switch.replace("off,off", "on,on")));
    }

    #[test]
    fn the_codec_card_comes_from_card_or_slave() {
        assert_eq!(card_from_setup(r#"{"card":"aic3104"}"#), "aic3104");
        assert_eq!(card_from_setup(r#"{"card":"1"}"#), "1");
        // 本机（R17）只写了 slave：默认成 0 就会落到 HDMI 卡上，那里没有 PCM 音量控制。
        assert_eq!(card_from_setup(r#"{"slave":"plughw:aic3104"}"#), "aic3104");
        assert_eq!(card_from_setup(r#"{"slave":"hw:1,0"}"#), "1");
        assert_eq!(card_from_setup(r#"{"slave":"plughw:0,0"}"#), "0");
        assert_eq!(card_from_setup("{}"), "0");
        assert_eq!(card_from_setup("not json"), "0");
        assert_eq!(card_from_setup(r#"{"card":"0; rm -rf /"}"#), "0");
    }

    /// A mixer whose `amixer` answers from a queue and records what it was asked.
    fn mixer(answers: Vec<&'static str>) -> (Mixer, std::rc::Rc<RefCell<Vec<String>>>) {
        let asked = std::rc::Rc::new(RefCell::new(Vec::new()));
        let queue: std::rc::Rc<RefCell<VecDeque<&'static str>>> =
            std::rc::Rc::new(RefCell::new(answers.into()));
        let seen = std::rc::Rc::clone(&asked);
        let mixer = Mixer {
            card: "0".to_owned(),
            amixer: Box::new(move |args| {
                seen.borrow_mut().push(args.join(" "));
                queue
                    .borrow_mut()
                    .pop_front()
                    .map(str::to_owned)
                    .ok_or_else(|| "no canned answer left".to_owned())
            }),
            persist: false,
        };
        (mixer, asked)
    }

    /// The curve is duckphone's, and it has to stay its: the two clients show the same number.
    #[test]
    fn the_percent_curve_matches_the_web_page() {
        assert_eq!(percent_to_raw(0), 0);
        assert_eq!(percent_to_raw(100), 127);
        for percent in [1, 20, 50, 60, 99] {
            let raw = percent_to_raw(percent);
            assert!(
                (i32::from(raw_to_percent(raw)) - i32::from(percent)).abs() <= 1,
                "{percent}% → {raw} → {}%",
                raw_to_percent(raw)
            );
        }
    }

    /// A read is two `cget`s and no write.
    #[test]
    fn reading_asks_the_codec_and_writes_nothing() {
        let (mixer, asked) = mixer(vec!["  : values=100,100\n", "  : values=on,on\n"]);
        let status = mixer.status().expect("read");
        assert!(!status.muted);
        assert_eq!(status.percent, raw_to_percent(100));
        assert_eq!(
            *asked.borrow(),
            vec![
                "-c 0 cget name=PCM Playback Volume",
                "-c 0 cget name=Line Playback Switch",
            ]
        );
    }

    /// A muted codec reports zero, which is what the slider shows.
    #[test]
    fn a_muted_codec_reads_zero() {
        let (mixer, _) = mixer(vec!["  : values=100,100\n", "  : values=off,off\n"]);
        let status = mixer.status().expect("read");
        assert!(status.muted);
        assert_eq!(status.percent, 0);
    }

    /// Setting a level writes the register, verifies the echo, unmutes, and reads back.
    #[test]
    fn setting_a_level_writes_the_register_and_unmutes() {
        let raw = percent_to_raw(60);
        let echoed: &'static str = Box::leak(format!("  : values={raw},{raw}\n").into_boxed_str());
        let (mixer, asked) = mixer(vec![
            echoed,
            "  : values=on,on\n",
            echoed,
            "  : values=on,on\n",
        ]);
        let status = mixer
            .apply(&VolumeParams {
                percent: Some(60),
                muted: None,
            })
            .expect("write");
        assert_eq!(status.percent, 60);
        assert!(!status.muted);
        let asked = asked.borrow();
        assert_eq!(
            asked[0],
            format!("-c 0 cset name=PCM Playback Volume {raw}")
        );
        assert_eq!(asked[1], "-c 0 cset name=Line Playback Switch on,on");
    }

    /// Zero percent is mute, which is duckphone's behaviour and what the UI's slider end means.
    #[test]
    fn zero_percent_switches_the_line_off() {
        let (mixer, asked) = mixer(vec![
            "  : values=0,0\n",
            "  : values=off,off\n",
            "  : values=0,0\n",
            "  : values=off,off\n",
        ]);
        let status = mixer
            .apply(&VolumeParams {
                percent: Some(0),
                muted: None,
            })
            .expect("write");
        assert_eq!(status.percent, 0);
        assert!(status.muted);
        assert_eq!(
            asked.borrow()[1],
            "-c 0 cset name=Line Playback Switch off,off"
        );
    }

    /// A mute button must not have to name a level, and must not touch the register.
    #[test]
    fn muting_alone_leaves_the_level_alone() {
        let (mixer, asked) = mixer(vec![
            "  : values=off,off\n",
            "  : values=100,100\n",
            "  : values=off,off\n",
        ]);
        let status = mixer
            .apply(&VolumeParams {
                percent: None,
                muted: Some(true),
            })
            .expect("write");
        assert!(status.muted);
        let asked = asked.borrow();
        assert_eq!(asked.len(), 3);
        assert_eq!(asked[0], "-c 0 cset name=Line Playback Switch off,off");
        assert!(
            asked.iter().all(|call| !call.contains("cset name=PCM")),
            "{asked:?}"
        );
    }

    /// Above 100 is refused rather than clamped, before anything is written.
    #[test]
    fn an_impossible_level_is_refused_without_writing() {
        let (mixer, asked) = mixer(vec![]);
        let error = mixer
            .apply(&VolumeParams {
                percent: Some(101),
                muted: None,
            })
            .expect_err("101% is not a level");
        assert!(error.contains("0～100"), "{error}");
        assert!(asked.borrow().is_empty());
    }

    /// Unreadable output is an error, not a zero — a broken readback must not look like silence.
    #[test]
    fn a_card_that_does_not_answer_is_an_error() {
        let (mixer, _) = mixer(vec!["no values here\n"]);
        assert!(mixer.status().is_err());
    }
}

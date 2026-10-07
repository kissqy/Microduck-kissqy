//! What the *board* says about itself, as opposed to what the robot says.
//!
//! Deliberately not in `duck-control` and not behind [`crate::RobotIo`]: nothing here touches
//! the Dynamixel bus. It is a `sysfs` read, so it belongs to the daemon that runs on a Linux
//! board rather than to the crate that models a robot — and it keeps working when the motor
//! bus does not, which is exactly when a thermal reading is interesting.
//!
//! Absent everywhere but Linux, and absent on a Linux box with no thermal zones. Both answer
//! `None` by simply finding no files, which is why there is no `cfg` here: a laptop dev build
//! reports no board temperature and says so, rather than failing to compile.

use std::path::Path;

use duck_ipc_proto as proto;

/// Where the kernel exposes every thermal sensor it knows about.
const THERMAL_ROOT: &str = "/sys/class/thermal";

/// Where the kernel exposes each CPU cluster's frequency policy.
const CPUFREQ_ROOT: &str = "/sys/devices/system/cpu/cpufreq";

/// Millidegrees Celsius, per the kernel's thermal sysfs ABI.
const MILLI_PER_DEGREE: f64 = 1000.0;

/// The hottest thermal zone on the board, in °C.
///
/// **The maximum across zones, not the CPU's alone.** A Radxa Zero 3 exposes `soc-thermal` and
/// `gpu-thermal`; other boards add NPU and DDR zones. Reporting the hottest of them is the
/// conservative answer to "is this board too hot", and it cannot silently omit the zone that
/// was actually climbing — which picking one zone by name would, the first time a board wired
/// its sensors differently.
///
/// `None` when there are no readable zones: not Linux, or a kernel without thermal sysfs.
/// Never `Some(0.0)` — a zone that reads as nonsense is skipped rather than averaged in, since
/// 0 °C on a running board is a sensor fault, not a temperature.
pub fn hottest_zone_c() -> Option<f64> {
    let mut hottest: Option<f64> = None;

    // `read_dir` once per sample rather than a cached list of paths: it is a few microseconds
    // at 1 Hz, and a cache would go stale against a zone that appears when a driver loads.
    for entry in std::fs::read_dir(THERMAL_ROOT).ok()?.flatten() {
        let name = entry.file_name();
        if !name.to_string_lossy().starts_with("thermal_zone") {
            continue;
        }
        let Ok(raw) = std::fs::read_to_string(entry.path().join("temp")) else {
            continue;
        };
        let Ok(milli) = raw.trim().parse::<f64>() else {
            continue;
        };
        let celsius = milli / MILLI_PER_DEGREE;
        // A negative or zero reading is a sensor that is not working. Below-freezing is
        // physically possible for a board and pointless to chase; a fault is far likelier.
        if celsius <= 0.0 {
            continue;
        }
        if hottest.is_none_or(|high| celsius > high) {
            hottest = Some(celsius);
        }
    }

    hottest
}

/// How far the board's clock has been wound down, and by how much.
///
/// The pair, from two places, because the kernel keeps them apart: the cooling device says the
/// thermal governor is *acting*, and the cpufreq policy says what that costs. See
/// [`proto::CpuThrottle`] for why neither alone is an answer.
///
/// `None` when there is no `cpufreq` sysfs to read — not Linux, or a kernel without it. A
/// missing *cooling device* is not `None`: the ceiling is still worth reporting, and the level
/// comes back as `0 of 0`.
pub fn cpu_throttle() -> Option<proto::CpuThrottle> {
    throttle_in(Path::new(CPUFREQ_ROOT), Path::new(THERMAL_ROOT))
}

/// [`cpu_throttle`] against given roots, so the selection can be tested against a fixture.
/// A real board's numbers are whatever the room is doing, which is untestable by definition.
fn throttle_in(cpufreq_root: &Path, thermal_root: &Path) -> Option<proto::CpuThrottle> {
    let (khz, max_khz) = clock_ceiling(cpufreq_root)?;
    let (level, max_level) = cooling_level(thermal_root).unwrap_or((0, 0));
    Some(proto::CpuThrottle {
        level,
        max_level,
        khz,
        max_khz,
    })
}

/// The most-throttled cluster's ceiling: `(scaling_max_freq, cpuinfo_max_freq)` in kHz.
///
/// **The worst policy, not the first.** One cluster is all a Radxa Zero 3 has, but a big.LITTLE
/// board throttles its big cores first and hardest, and reporting `policy0` there would show a
/// board running freely while the cores the control loop is on are halved. Same argument as
/// [`hottest_zone_c`]: take the reading that is worst, and it cannot silently omit the one that
/// was moving.
fn clock_ceiling(root: &Path) -> Option<(u32, u32)> {
    let mut worst: Option<(u32, u32)> = None;

    for entry in std::fs::read_dir(root).ok()?.flatten() {
        if !entry.file_name().to_string_lossy().starts_with("policy") {
            continue;
        }
        let khz = read_u32(&entry.path().join("scaling_max_freq"));
        let max_khz = read_u32(&entry.path().join("cpuinfo_max_freq"));
        let (Some(khz), Some(max_khz)) = (khz, max_khz) else {
            continue;
        };
        // A hardware maximum of zero is a policy that cannot be reasoned about, and dividing
        // by it below is the bug that would follow.
        if max_khz == 0 {
            continue;
        }
        // Lowest fraction of its own maximum wins. Cross-multiplied in `u64` rather than
        // compared as floats: these are clock rates, the arithmetic is exact, and two clusters
        // throttled to the same fraction should not depend on rounding to order.
        let harder = worst.is_none_or(|(low, low_max)| {
            u64::from(khz) * u64::from(low_max) < u64::from(low) * u64::from(max_khz)
        });
        if harder {
            worst = Some((khz, max_khz));
        }
    }

    worst
}

/// The deepest cpufreq cooling state: `(cur_state, max_state)`.
///
/// Matched on the type *containing* `cpufreq` rather than equalling a name: this board calls it
/// `cpufreq-cpu0`, other kernels call the same thing `thermal-cpufreq-0`, and the devfreq
/// coolers beside it — GPU, DDR, the video codecs — must not be mistaken for the CPU's. Those
/// throttle too, and a GPU wound down to its floor says nothing about the control loop.
///
/// `None` when no such device exists; deepest wins, for the reason [`clock_ceiling`] gives.
fn cooling_level(root: &Path) -> Option<(u32, u32)> {
    let mut deepest: Option<(u32, u32)> = None;

    for entry in std::fs::read_dir(root).ok()?.flatten() {
        if !entry
            .file_name()
            .to_string_lossy()
            .starts_with("cooling_device")
        {
            continue;
        }
        let Ok(kind) = std::fs::read_to_string(entry.path().join("type")) else {
            continue;
        };
        if !kind.trim().contains("cpufreq") {
            continue;
        }
        let level = read_u32(&entry.path().join("cur_state"));
        let max_level = read_u32(&entry.path().join("max_state"));
        let (Some(level), Some(max_level)) = (level, max_level) else {
            continue;
        };
        if max_level == 0 {
            continue;
        }
        let harder = deepest.is_none_or(|(high, high_max)| {
            u64::from(level) * u64::from(high_max) > u64::from(high) * u64::from(max_level)
        });
        if harder {
            deepest = Some((level, max_level));
        }
    }

    deepest
}

/// One `sysfs` integer. Absent file, unreadable file and junk contents are all the same
/// answer here — there is no number — and every caller skips the entry either way.
fn read_u32(path: &Path) -> Option<u32> {
    std::fs::read_to_string(path).ok()?.trim().parse().ok()
}

#[cfg(test)]
mod tests {
    use super::*;

    /// On Linux CI this must find the host's own zones; on macOS it must answer `None` rather
    /// than panic. Either way the *shape* is what is asserted, because a test cannot know what
    /// temperature the machine running it is at.
    #[test]
    fn a_reading_is_plausible_or_absent() {
        match hottest_zone_c() {
            None => {} // No thermal sysfs. Correct on macOS, and on a container without it.
            Some(c) => assert!(
                (1.0..=150.0).contains(&c),
                "{c} °C is not a temperature a board reports; check the millidegree scale"
            ),
        }
    }

    /// A `sysfs` tree with the files a reader looks for. Values as strings, so a test can put
    /// junk in one and assert it is skipped rather than parsed into a number.
    fn write(dir: &std::path::Path, name: &str, value: &str) {
        std::fs::create_dir_all(dir).unwrap();
        std::fs::write(dir.join(name), value).unwrap();
    }

    fn policy(root: &std::path::Path, n: u32, scaling: &str, hardware: &str) {
        let dir = root.join(format!("policy{n}"));
        write(&dir, "scaling_max_freq", scaling);
        write(&dir, "cpuinfo_max_freq", hardware);
    }

    fn cooler(root: &std::path::Path, n: u32, kind: &str, cur: &str, max: &str) {
        let dir = root.join(format!("cooling_device{n}"));
        write(&dir, "type", kind);
        write(&dir, "cur_state", cur);
        write(&dir, "max_state", max);
    }

    /// The case this exists for, taken from a Radxa Zero 3 that had cooked itself: 95 °C, the
    /// governor at the bottom of its table, and the clock held at 408 MHz of 1800.
    #[test]
    fn a_cooked_board_reports_both_halves() {
        let tmp = tempfile::tempdir().unwrap();
        let (cpufreq, thermal) = (tmp.path().join("cpufreq"), tmp.path().join("thermal"));
        policy(&cpufreq, 0, "408000", "1800000");
        cooler(&thermal, 3, "cpufreq-cpu0", "6", "6");
        // The devfreq coolers a real board has beside it, at their own floors.
        cooler(&thermal, 2, "devfreq-dmc", "3", "3");
        cooler(&thermal, 4, "devfreq-fde60000.gpu", "5", "5");

        let t = throttle_in(&cpufreq, &thermal).expect("a cpufreq policy is present");
        assert_eq!(
            (t.level, t.max_level, t.khz, t.max_khz),
            (6, 6, 408_000, 1_800_000)
        );
        assert!(t.throttled());
    }

    /// The devfreq coolers must not be read as the CPU's. Both are at their floor here while
    /// the CPU is untouched — a board whose GPU is throttled and whose control loop is fine.
    #[test]
    fn a_devfreq_cooler_is_not_the_cpu() {
        let tmp = tempfile::tempdir().unwrap();
        let (cpufreq, thermal) = (tmp.path().join("cpufreq"), tmp.path().join("thermal"));
        policy(&cpufreq, 0, "1800000", "1800000");
        cooler(&thermal, 0, "devfreq-fde60000.gpu", "5", "5");
        cooler(&thermal, 1, "devfreq-dmc", "3", "3");

        let t = throttle_in(&cpufreq, &thermal).unwrap();
        assert_eq!((t.level, t.max_level), (0, 0), "no cpufreq cooler to read");
        assert!(!t.throttled(), "a throttled GPU is not a throttled CPU");
    }

    /// `thermal-cpufreq-0` is the same device under another kernel's naming. Matching the
    /// board's exact spelling would report every other board as unthrottled forever.
    #[test]
    fn the_other_kernel_spelling_is_the_same_device() {
        let tmp = tempfile::tempdir().unwrap();
        let (cpufreq, thermal) = (tmp.path().join("cpufreq"), tmp.path().join("thermal"));
        policy(&cpufreq, 0, "1104000", "1800000");
        cooler(&thermal, 0, "thermal-cpufreq-0", "2", "6");

        let t = throttle_in(&cpufreq, &thermal).unwrap();
        assert_eq!((t.level, t.max_level), (2, 6));
    }

    /// Worst cluster, not first. `policy0` is the untouched little cluster and `policy4` the
    /// big one cut in half — reporting the first would show a board running freely.
    #[test]
    fn the_hardest_throttled_cluster_is_the_one_reported() {
        let tmp = tempfile::tempdir().unwrap();
        let (cpufreq, thermal) = (tmp.path().join("cpufreq"), tmp.path().join("thermal"));
        policy(&cpufreq, 0, "1800000", "1800000");
        policy(&cpufreq, 4, "1200000", "2400000");

        let t = throttle_in(&cpufreq, &thermal).unwrap();
        assert_eq!((t.khz, t.max_khz), (1_200_000, 2_400_000));
        assert!(t.throttled());
    }

    /// A ceiling with nothing holding it down is the ordinary answer, and it must not read as
    /// throttled — otherwise every healthy robot wears the warning.
    #[test]
    fn an_unthrottled_board_says_so() {
        let tmp = tempfile::tempdir().unwrap();
        let (cpufreq, thermal) = (tmp.path().join("cpufreq"), tmp.path().join("thermal"));
        policy(&cpufreq, 0, "1800000", "1800000");
        cooler(&thermal, 3, "cpufreq-cpu0", "0", "6");

        let t = throttle_in(&cpufreq, &thermal).unwrap();
        assert!(!t.throttled());
        assert_eq!(t.max_level, 6, "the table is still worth reporting");
    }

    /// No `cpufreq` at all — a laptop dev build, or a kernel without it. `None`, not a zeroed
    /// reading, which would render as a board pinned to 0 MHz.
    #[test]
    fn no_cpufreq_sysfs_is_absent_not_zero() {
        let tmp = tempfile::tempdir().unwrap();
        assert!(throttle_in(&tmp.path().join("nothing"), &tmp.path().join("thermal")).is_none());
    }

    /// Junk in one file skips that policy rather than becoming a number. A `<unsupported>` in
    /// `scaling_max_freq` parsed as zero would report a stopped CPU.
    #[test]
    fn an_unreadable_policy_is_skipped() {
        let tmp = tempfile::tempdir().unwrap();
        let (cpufreq, thermal) = (tmp.path().join("cpufreq"), tmp.path().join("thermal"));
        policy(&cpufreq, 0, "<unsupported>", "1800000");
        policy(&cpufreq, 4, "1416000", "1800000");

        let t = throttle_in(&cpufreq, &thermal).unwrap();
        assert_eq!((t.khz, t.max_khz), (1_416_000, 1_800_000));
    }

    /// Shape only, on whatever machine runs the suite — the mirror of the temperature test
    /// above, and for the same reason: a real reading depends on the room.
    #[test]
    fn a_host_reading_is_plausible_or_absent() {
        match cpu_throttle() {
            None => {} // No cpufreq sysfs. Correct on macOS.
            Some(t) => {
                assert!(
                    t.khz > 0 && t.khz <= t.max_khz,
                    "{t:?} is not a clock ceiling"
                );
                assert!(
                    t.level <= t.max_level,
                    "{t:?} is past the bottom of its table"
                );
            }
        }
    }

    /// The scale is the whole risk here: the kernel reports millidegrees, and forgetting the
    /// divisor turns 47 °C into 47000, which would sail through any "is it hot" threshold
    /// anyone later writes against this.
    #[test]
    fn millidegrees_convert_to_degrees() {
        assert_eq!(47123.0 / MILLI_PER_DEGREE, 47.123);
    }
}

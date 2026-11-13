//! Does the duck detector run on this board, how fast, and at what cost to the control loop?
//!
//! ```text
//! sudo duck-bench --model duck.rknn --frames /var/tmp/frames
//! ```
//!
//! Three questions, in the order they matter:
//!
//! 1. **Does it run at all?** An NPU runtime that will not load, a model built for another
//!    platform, or a driver older than the runtime all fail here rather than in a daemon.
//! 2. **Does it still see ducks?** Quantisation is where a detector stops working, and a model that
//!    runs and detects nothing looks exactly like one that works. So it reports detections per
//!    frame, not just milliseconds.
//! 3. **What does it cost?** Latency percentiles, and the CPU this process burned — because the
//!    reason to put this on the NPU is to leave `robotd`'s 50 Hz loop alone, and "the NPU does it"
//!    is a claim to check rather than assume.
//!
//! It reads JPEGs rather than opening the camera: `mediad` holds the camera, the frames from a
//! capture session are already the right thing, and a benchmark that has to stop a daemon is a
//! benchmark nobody runs twice.

use std::path::{Path, PathBuf};
use std::time::{Duration, Instant};

use anyhow::{Context, Result, bail};
use clap::Parser;
use duck_detect::{decode, letterbox_rgb, rknn::Model};

#[derive(Parser)]
#[command(about = "Run the duck detector on this board and report what it costs")]
struct Args {
    /// The quantised model, as `scripts/to_rknn.py` in the duck_detector repo writes it.
    #[arg(long)]
    model: PathBuf,

    /// A directory of JPEGs — a capture session works, and so does anything else.
    #[arg(long)]
    frames: PathBuf,

    /// Skip this many timed runs before measuring, so the first-call costs are not the answer.
    #[arg(long, default_value_t = 5)]
    warmup: usize,

    /// Run the whole set this many times, for a stable percentile on a small session.
    #[arg(long, default_value_t = 3)]
    passes: usize,

    /// Detection threshold. **Tune this against the quantised model**: its output tensor carries
    /// its own scale, so the float model's 0.5 is not this model's 0.5.
    #[arg(long, default_value_t = 0.35)]
    threshold: f32,

    /// Inferences per second. **Paced by default, and that is not politeness.**
    ///
    /// Run flat out, this took a Radxa Zero 3 to 95 °C and the CPU throttled to 408 MHz — so the
    /// numbers a flat-out run reports are the numbers of a board that is already too hot to give
    /// them. 2 Hz is what the detector will actually run at. `--hz 0` removes the pacing, for
    /// finding the ceiling on a board with a fan or a heatsink.
    #[arg(long, default_value_t = 2.0)]
    hz: f64,

    /// Print a line per frame, for finding the one frame that behaves differently.
    #[arg(long)]
    verbose: bool,
}

/// CPU seconds this process has used, from `/proc/self/stat` — user + system, in seconds.
///
/// Measured rather than sampled with a tool, so the number belongs to this process and not to
/// whatever else the board was doing.
fn cpu_seconds() -> Result<f64> {
    let stat = std::fs::read_to_string("/proc/self/stat").context("cannot read /proc/self/stat")?;
    // The comm field can contain spaces and parentheses, so fields are counted from the last ')'.
    let tail = stat.rsplit_once(')').map(|(_, rest)| rest).unwrap_or(&stat);
    let fields: Vec<&str> = tail.split_whitespace().collect();
    // utime and stime are fields 14 and 15 of the full line, which are 11 and 12 after the comm.
    let utime: f64 = fields.get(11).unwrap_or(&"0").parse().unwrap_or(0.0);
    let stime: f64 = fields.get(12).unwrap_or(&"0").parse().unwrap_or(0.0);
    let ticks = unsafe { libc_sysconf_clk_tck() } as f64;
    Ok((utime + stime) / ticks)
}

/// `sysconf(_SC_CLK_TCK)`, without taking a dependency on libc for one constant that is 100
/// everywhere this runs — but asked for rather than assumed, because the arithmetic above is
/// meaningless if it is not.
unsafe fn libc_sysconf_clk_tck() -> i64 {
    unsafe extern "C" {
        fn sysconf(name: i32) -> i64;
    }
    // _SC_CLK_TCK is 2 on Linux.
    let value = unsafe { sysconf(2) };
    if value > 0 { value } else { 100 }
}

/// The SoC's own thermal zone, in °C. `None` where the board does not publish one.
///
/// Reported because it is a result: this detector is cheap at 2 Hz and cooks the board flat out,
/// and a benchmark that measured only speed would have said the second half was free.
fn soc_temperature() -> Option<f64> {
    for zone in 0..8 {
        let base = format!("/sys/class/thermal/thermal_zone{zone}");
        let kind = std::fs::read_to_string(format!("{base}/type")).ok()?;
        if kind.trim() == "soc-thermal" {
            let milli: f64 = std::fs::read_to_string(format!("{base}/temp"))
                .ok()?
                .trim()
                .parse()
                .ok()?;
            return Some(milli / 1000.0);
        }
    }
    None
}

fn percentile(sorted: &[Duration], fraction: f64) -> Duration {
    if sorted.is_empty() {
        return Duration::ZERO;
    }
    let index = ((sorted.len() - 1) as f64 * fraction).round() as usize;
    sorted[index]
}

fn jpegs(directory: &Path) -> Result<Vec<PathBuf>> {
    let mut found: Vec<PathBuf> = std::fs::read_dir(directory)
        .with_context(|| format!("cannot read {}", directory.display()))?
        .filter_map(|entry| entry.ok().map(|e| e.path()))
        .filter(|path| {
            path.extension().is_some_and(|ext| {
                ext.eq_ignore_ascii_case("jpg") || ext.eq_ignore_ascii_case("jpeg")
            })
        })
        .collect();
    found.sort();
    if found.is_empty() {
        bail!("no jpegs in {}", directory.display());
    }
    Ok(found)
}

fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env().unwrap_or_else(|_| "info".into()),
        )
        .init();
    let args = Args::parse();

    let paths = jpegs(&args.frames)?;
    let mut model = Model::open(&args.model)?;
    let (height, width, channels) = model.input;
    println!(
        "runtime api {} · driver {}\nmodel {}×{}×{}, {} outputs\n{} frames, {} passes\n",
        model.api_version,
        model.driver_version,
        width,
        height,
        channels,
        model.output_len,
        paths.len(),
        args.passes
    );
    if channels != 3 || width != height {
        bail!("this bench only knows a square RGB model, got {width}×{height}×{channels}");
    }

    // Decoded once, up front: JPEG decoding is not what is being measured, and doing it inside the
    // timed loop would hide the inference behind it.
    let mut frames = Vec::new();
    for path in &paths {
        let image = image::open(path)
            .with_context(|| format!("cannot decode {}", path.display()))?
            .to_rgb8();
        frames.push((path.clone(), image));
    }

    let mut square = Vec::new();
    let mut raw = Vec::new();

    for _ in 0..args.warmup.min(frames.len().max(1)) {
        let (_, image) = &frames[0];
        let fit = letterbox_rgb(
            image.as_raw(),
            image.width() as usize,
            image.height() as usize,
            width,
            &mut square,
        );
        model.infer(&square, &mut raw)?;
        let _ = decode(&raw, fit, args.threshold, 0.5);
    }

    let mut latencies: Vec<Duration> = Vec::with_capacity(frames.len() * args.passes);
    let mut with_a_duck = 0usize;
    let mut detections = 0usize;
    let cpu_before = cpu_seconds()?;
    let wall_before = Instant::now();

    let period = if args.hz > 0.0 {
        Some(Duration::from_secs_f64(1.0 / args.hz))
    } else {
        None
    };
    let mut next = Instant::now();

    for pass in 0..args.passes {
        for (path, image) in &frames {
            // Paced before the work, not after, so a slow inference eats into its own slot rather
            // than pushing the whole run later — the same shape as a control loop's tick.
            if let Some(period) = period {
                let now = Instant::now();
                if next > now {
                    std::thread::sleep(next - now);
                }
                next += period;
            }
            let fit = letterbox_rgb(
                image.as_raw(),
                image.width() as usize,
                image.height() as usize,
                width,
                &mut square,
            );
            let started = Instant::now();
            model.infer(&square, &mut raw)?;
            let found = decode(&raw, fit, args.threshold, 0.5);
            latencies.push(started.elapsed());

            if pass == 0 {
                detections += found.len();
                if !found.is_empty() {
                    with_a_duck += 1;
                }
                if args.verbose {
                    let best = found
                        .first()
                        .map(|d| format!("{:.2} at {:.0},{:.0}", d.score, d.box_[0], d.box_[1]))
                        .unwrap_or_else(|| "nothing".into());
                    println!(
                        "  {}: {} ({:.1} ms)",
                        path.file_name().unwrap_or_default().to_string_lossy(),
                        best,
                        latencies.last().unwrap().as_secs_f64() * 1e3
                    );
                }
            }
        }
    }

    let wall = wall_before.elapsed();
    let cpu = cpu_seconds()? - cpu_before;
    latencies.sort();
    let millis = |d: Duration| d.as_secs_f64() * 1e3;

    println!(
        "\nlatency   p50 {:.1} ms · p95 {:.1} ms · p99 {:.1} ms · max {:.1} ms",
        millis(percentile(&latencies, 0.50)),
        millis(percentile(&latencies, 0.95)),
        millis(percentile(&latencies, 0.99)),
        millis(*latencies.last().unwrap())
    );
    match period {
        Some(_) => println!(
            "paced at   {:.1} Hz — the rate the detector runs at, not the ceiling (--hz 0 for that)",
            args.hz
        ),
        None => println!(
            "throughput {:.1} fps flat out — watch the temperature, this is what cooks a board",
            latencies.len() as f64 / wall.as_secs_f64()
        ),
    }
    // The number that decides whether this can run beside the control loop: one core fully busy is
    // 100%, and the NPU doing the work should leave this well under it.
    let cpu_per_frame = 1e3 * cpu / latencies.len() as f64;
    println!(
        "cpu        {:.1} ms per frame — {:.0}% of one core at {:.1} Hz",
        cpu_per_frame,
        // What it would cost at the paced rate, which is the number that matters beside a 50 Hz
        // control loop. Flat out it is whatever the loop can push, and that is a different
        // question.
        0.1 * cpu_per_frame
            * if args.hz > 0.0 {
                args.hz
            } else {
                1000.0 / cpu_per_frame
            },
        if args.hz > 0.0 {
            args.hz
        } else {
            1000.0 / cpu_per_frame
        }
    );
    if let Some(temperature) = soc_temperature() {
        println!("soc temp   {temperature:.0} °C at the end of the run");
    }
    println!(
        "detections {} in {} frames, {} frames with at least one",
        detections,
        frames.len(),
        with_a_duck
    );
    if detections == 0 {
        println!(
            "\nNOTHING DETECTED. Either these frames have no duck in them, or the threshold is \n\
             wrong for a quantised model — try --threshold 0.2 before believing the model is broken."
        );
    }
    Ok(())
}

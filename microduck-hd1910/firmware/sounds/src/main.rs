//! `sounds` — render and audition the robot's voice bank.
//!
//! `ensure-bank` is what the release's postinstall hook runs: it replaces the prototype's
//! `generate_sounds.sh` (venv + numpy + ffmpeg) with one binary that renders the per-robot
//! bank in place, idempotently. Everything else is bench tooling: hear a seed before it
//! ships, regenerate a bank by hand, print the personality behind a voice.

use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

use anyhow::{Context, Result, bail};
use clap::{Parser, Subcommand};
use sounds::{BANK_VERSION, Personality, chorale, hardware_seed, render, render_all, to_wav};

#[derive(Parser)]
#[command(
    name = "sounds",
    about = "The robot's voice: seedable duck vocalisations",
    version
)]
struct Args {
    #[command(subcommand)]
    command: Cmd,
}

#[derive(Subcommand)]
enum Cmd {
    /// Print the personality traits behind a seed.
    Show {
        #[arg(long)]
        seed: Option<u32>,
    },
    /// Render one sound to a wav file.
    Render {
        tag: String,
        out: PathBuf,
        #[arg(long)]
        seed: Option<u32>,
        #[arg(long, default_value_t = 0)]
        variant: u32,
    },
    /// Render every tag × variant into a directory (the layout robotd plays from).
    RenderAll {
        out_dir: PathBuf,
        #[arg(long)]
        seed: Option<u32>,
    },
    /// Synthesize one sound and play it through aplay.
    Play {
        tag: String,
        #[arg(long)]
        seed: Option<u32>,
        #[arg(long, default_value_t = 0)]
        variant: u32,
        /// ALSA device; the robot's codec by default.
        #[arg(long, default_value = "plughw:aic3104")]
        device: String,
    },
    /// Audition the live theremin voice: a scripted hand sweep through the streaming synth.
    ///
    /// The theremin's pitch is a hand's distance and there is no hand on a bench, so this
    /// plays the gesture instead — approach, hold, wobble, retreat — driving
    /// [`sounds::Stream`] exactly as `robotd` does at the frame rate the ToF actually
    /// delivers. It is the only way to hear a voice change without a robot in front of you.
    Theremin {
        /// Write a wav here instead of playing it.
        #[arg(long)]
        out: Option<PathBuf>,
        #[arg(long)]
        seed: Option<u32>,
        #[arg(long, default_value_t = 0)]
        variant: u32,
        /// ALSA device; the robot's codec by default.
        #[arg(long, default_value = "plughw:aic3104")]
        device: String,
    },
    /// The duck chorale, on a laptop: several ducks singing one piece in four parts.
    ///
    /// Renders the ensemble offline and mixes it down, so the arrangement can be judged before
    /// any two ducks have to agree on a clock. Each duck keeps its own timbre; the *notes* are
    /// absolute, because four ducks each singing a chord in their own tuning is four ducks out
    /// of tune with each other.
    Chorale {
        /// How many ducks. 2 takes the outer voices, 3 drops the tenor, 4 is full SATB.
        #[arg(long, default_value_t = 4)]
        voices: usize,
        /// The ducks' seeds, comma-separated. Defaults to a spread that casts cleanly.
        #[arg(long, value_delimiter = ',')]
        seeds: Option<Vec<u32>>,
        /// A score to sing: a `.duckscore` text file, or a `.mid` exported from a notation
        /// editor. Defaults to the built-in piece.
        #[arg(long)]
        score: Option<PathBuf>,
        /// Write a wav here instead of playing it.
        #[arg(long)]
        out: Option<PathBuf>,
        /// Override the tempo, beats per minute.
        #[arg(long)]
        bpm: Option<f64>,
        /// Transpose, semitones. Default fits the piece to the cast's registers.
        #[arg(long)]
        transpose: Option<i32>,
        /// How much room, 0..1. Real ducks get this free by being objects in a room; a dry
        /// preview is harsher than the hardware will actually sound.
        #[arg(long, default_value_t = 0.25)]
        room: f64,
        /// Where the playback speaker stops reproducing, hertz. Defaults to the duck's own
        /// driver, which is the target; `--rolloff 0` renders for a full-range system instead.
        #[arg(long, default_value_t = 300.0)]
        rolloff: f64,
        /// ALSA device; the robot's codec by default.
        #[arg(long, default_value = "plughw:aic3104")]
        device: String,
    },
    /// Make sure this robot's voice bank exists and is current — render it if not.
    ///
    /// Idempotent: a marker records the seed and bank version, and a matching bank is left
    /// alone, so this can (and does) run on every release install.
    EnsureBank {
        /// Where the bank lives. robotd plays from here.
        #[arg(long, default_value = "/var/lib/robot/sounds")]
        dir: PathBuf,
        /// Regenerate even when the marker matches.
        #[arg(long)]
        force: bool,
        /// Override the hardware-derived seed (bench use).
        #[arg(long)]
        seed: Option<u32>,
    },
}

/// The seed to voice: given, or derived from the hardware.
fn resolve_seed(seed: Option<u32>) -> Result<u32> {
    match seed {
        Some(s) => Ok(s),
        None => hardware_seed().context("no --seed given and no hardware id to derive one"),
    }
}

fn show(p: &Personality) {
    println!("  seed               {}", p.seed);
    println!("  pitch_center_hz    {:.1}", p.pitch_center_hz);
    println!("  register           {:+.2}", p.register);
    println!("  pitch_spread       {:.2}", p.pitch_spread);
    println!("  glide_bias         {:+.2}", p.glide_bias);
    println!("  brightness         {:.2}", p.brightness);
    println!("  tilt               {:.2}", p.tilt);
    println!("  nasal              {:.2}", p.nasal);
    println!("  harmonic_skew      {:+.2}", p.harmonic_skew);
    println!("  formant_n          {}", p.formant_n);
    println!("  formant_gain       {:.2}", p.formant_gain);
    println!("  vibrato_rate_hz    {:.1}", p.vibrato_rate_hz);
    println!("  vibrato_depth      {:.2}", p.vibrato_depth);
    println!("  jitter_depth       {:.2}", p.jitter_depth);
    println!("  breath             {:.2}", p.breath);
    println!("  quackiness         {:.2}", p.quackiness);
    println!("  am_rate_hz         {:.1}", p.am_rate_hz);
    println!("  am_depth           {:.2}", p.am_depth);
    println!("  warble_hz          {:.1}", p.warble_hz);
    println!("  warble_depth       {:.2}", p.warble_depth);
    println!("  attack_sharpness   {:.2}", p.attack_sharpness);
    println!("  speed              {:.2}", p.speed);
}

/// Pipe a rendered buffer into `aplay`, falling back to the default device off the robot.
fn play_pcm(buf: &[f32], device: &str) -> Result<()> {
    let play = |device: Option<&str>| -> Result<bool> {
        let mut cmd = Command::new("aplay");
        cmd.args(["-q", "-t", "raw", "-f", "S16_LE", "-c", "1", "-r"])
            .arg(sounds::SR.to_string());
        if let Some(d) = device {
            cmd.args(["-D", d]);
        }
        let mut child = cmd.stdin(Stdio::piped()).spawn().context("running aplay")?;
        let pcm: Vec<u8> = sounds::synth::to_i16(buf)
            .iter()
            .flat_map(|s| s.to_le_bytes())
            .collect();
        if let Some(stdin) = child.stdin.as_mut() {
            stdin.write_all(&pcm)?;
        }
        Ok(child.wait()?.success())
    };
    if !play(Some(device))? && !play(None)? {
        bail!("aplay failed on both {device} and the default device");
    }
    Ok(())
}

/// A scripted hand gesture, rendered through the live synth at the real frame rate.
///
/// Every parameter update happens on a 15 Hz boundary and every block is one frame long,
/// because that is what `robotd` will do: auditioning at audio rate would hide exactly the
/// stair-stepping the stream's slews exist to smooth. `closeness` is what
/// `kinematics::hand` reports — 0 at the far end of the playable band, 1 at the near end —
/// and it drives pitch, level and mouth together, the same one gesture.
fn theremin_sweep(p: &Personality, variant: u32) -> Vec<f32> {
    /// The ToF's frame rate: how often a real hand's distance arrives.
    const FRAME_HZ: f64 = 15.0;
    // (seconds, closeness at the end of the leg, hand present) — an approach, a held note,
    // a hand wobbling around one spot, a retreat, and a hand leaving the frame entirely.
    const LEGS: [(f64, f64, bool); 6] = [
        (1.5, 0.05, true),
        (2.5, 0.95, true),
        (1.5, 0.95, true),
        (2.0, 0.55, true),
        (1.5, 0.05, true),
        (1.0, 0.0, false),
    ];

    let mut stream = sounds::Stream::wheee(p, variant);
    let samples_per_frame = (f64::from(sounds::SR) / FRAME_HZ) as usize;
    let mut out = Vec::new();
    let mut from = 0.0f64;
    let mut wobble_phase = 0.0f64;
    for (seconds, to, present) in LEGS {
        let frames = (seconds * FRAME_HZ).round() as usize;
        for frame in 0..frames {
            let progress = (frame as f64 + 1.0) / frames as f64;
            let mut closeness = from + (to - from) * progress;
            // The held leg gets a real hand's tremor, so the slews are auditioned against
            // something that moves the way a hand does rather than a clean ramp.
            if (to - from).abs() < 1e-9 {
                wobble_phase += std::f64::consts::TAU * 0.8 / FRAME_HZ;
                closeness += 0.04 * wobble_phase.sin();
            }
            let level = if present { 1.0 } else { 0.0 };
            stream.set(stream.hz_at(closeness), level, closeness);
            let mut block = vec![0.0f32; samples_per_frame];
            stream.block(&mut block);
            out.extend(block);
        }
        from = to;
    }
    out
}

/// Read a score from either front end, chosen by extension.
///
/// `.mid`/`.midi` goes through the MIDI importer, anything else through the text parser. The
/// import reports what it decided and what it dropped, on stdout, because "why is the tenor
/// singing the bass line" is a question about that decision and it is otherwise invisible.
fn load_score(path: &Path) -> Result<chorale::Score> {
    let is_midi = path
        .extension()
        .and_then(|e| e.to_str())
        .is_some_and(|e| e.eq_ignore_ascii_case("mid") || e.eq_ignore_ascii_case("midi"));
    if !is_midi {
        let source =
            std::fs::read_to_string(path).with_context(|| format!("reading {}", path.display()))?;
        return chorale::text::parse(&source)
            .map_err(|e| anyhow::anyhow!("{}: {e}", path.display()));
    }

    let bytes = std::fs::read(path).with_context(|| format!("reading {}", path.display()))?;
    let import =
        chorale::midi::parse(&bytes).map_err(|e| anyhow::anyhow!("{}: {e}", path.display()))?;
    println!(
        "imported {} — {} tracks: {}",
        path.display(),
        import.tracks.len(),
        import.tracks.join(", ")
    );
    for (part, why) in &import.casting {
        println!("  {:8} {why}", part.as_str());
    }
    for dropped in &import.dropped {
        println!("  dropped: {dropped}");
    }
    let mut score = import.score;
    // A MIDI file's name is the file's name; the importer has nothing better to call it.
    score.name = path
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("imported")
        .to_owned();
    Ok(score)
}

fn main() -> Result<()> {
    match Args::parse().command {
        Cmd::Show { seed } => {
            let p = Personality::from_seed(resolve_seed(seed)?);
            show(&p);
        }
        Cmd::Render {
            tag,
            out,
            seed,
            variant,
        } => {
            let p = Personality::from_seed(resolve_seed(seed)?);
            to_wav(&render(&tag, &p, variant)?, &out)?;
            println!("wrote {}", out.display());
        }
        Cmd::RenderAll { out_dir, seed } => {
            let p = Personality::from_seed(resolve_seed(seed)?);
            let paths = render_all(&p, &out_dir)?;
            println!("wrote {} files under {}", paths.len(), out_dir.display());
        }
        Cmd::Play {
            tag,
            seed,
            variant,
            device,
        } => {
            let p = Personality::from_seed(resolve_seed(seed)?);
            play_pcm(&render(&tag, &p, variant)?, &device)?;
        }
        Cmd::Theremin {
            out,
            seed,
            variant,
            device,
        } => {
            let p = Personality::from_seed(resolve_seed(seed)?);
            let buf = theremin_sweep(&p, variant);
            match out {
                Some(path) => {
                    to_wav(&buf, &path)?;
                    println!("wrote {}", path.display());
                }
                None => play_pcm(&buf, &device)?,
            }
        }
        Cmd::Chorale {
            voices,
            seeds,
            score: score_path,
            out,
            bpm,
            transpose,
            room,
            rolloff,
            device,
        } => {
            // A spread of seeds that casts to four clearly different registers, so the default
            // invocation demonstrates the thing rather than four ducks that sound alike.
            const DEFAULT_SEEDS: [u32; 8] = [100, 7, 313, 42, 9001, 1234, 55, 777];
            let seeds: Vec<u32> = match seeds {
                Some(given) => given,
                None => DEFAULT_SEEDS
                    .iter()
                    .copied()
                    .take(voices.clamp(1, DEFAULT_SEEDS.len()))
                    .collect(),
            };
            let personalities: Vec<Personality> =
                seeds.iter().copied().map(Personality::from_seed).collect();
            let singers = chorale::cast(&personalities);

            // Either front end, chosen by extension: a hand-written text score, or anything a
            // notation editor exported. Both land on the same `Score`.
            let mut score = match score_path.as_deref() {
                None => chorale::Score::wistful(),
                Some(path) => load_score(path)?,
            };
            if let Some(bpm) = bpm {
                score.bpm = bpm;
            }
            let shift = transpose.unwrap_or(0);

            println!(
                "{} · {} ducks · {:.0} bpm · {shift:+} semitones · {:.0}s",
                score.name,
                singers.len(),
                score.bpm,
                score.duration_s()
            );
            // Which parts the score actually has, against how many ducks turned up: a four-part
            // piece sung by two ducks is missing two lines, and that is worth saying rather than
            // leaving someone to wonder where the harmony went.
            let sung: Vec<chorale::Part> = singers.iter().map(|s| s.part).collect();
            let missing: Vec<&str> = score
                .parts()
                .into_iter()
                .filter(|p| !sung.contains(p))
                .map(|p| p.as_str())
                .collect();
            if !missing.is_empty() {
                println!("  (not sung by anyone: {})", missing.join(", "));
            }
            // Print the casting: which duck got which part is the first thing to sanity-check,
            // and on real hardware it is decided this same way with nobody in charge.
            let mut seated = singers.clone();
            seated.sort_by_key(|s| s.part);
            for singer in &seated {
                println!(
                    "  {:8} seed {:<6} centre {:5.1} Hz  {:+.1} cents  {:+.0} ms",
                    singer.part.as_str(),
                    singer.personality.seed,
                    singer.personality.pitch_center_hz,
                    singer.detune_cents,
                    singer.onset_offset_s * 1000.0,
                );
            }

            let options = chorale::Options {
                transpose: shift,
                room,
                speaker_rolloff_hz: Some(rolloff).filter(|hz| *hz > 0.0),
                ..chorale::Options::default()
            };
            let mix = chorale::render(&score, &singers, &options);
            match out {
                Some(path) => {
                    to_wav(&mix, &path)?;
                    println!("wrote {}", path.display());
                }
                None => play_pcm(&mix, &device)?,
            }
        }
        Cmd::EnsureBank { dir, force, seed } => {
            let seed = resolve_seed(seed)?;
            let marker = format!("{seed}:{BANK_VERSION}");
            let marker_path = dir.join(".seed");
            if !force && std::fs::read_to_string(&marker_path).is_ok_and(|m| m.trim() == marker) {
                println!(
                    "voice bank already generated for seed {seed} (v{BANK_VERSION}) — nothing to do (--force to regenerate)"
                );
                return Ok(());
            }
            let p = Personality::from_seed(seed);
            println!("voice seed {seed} (bank v{BANK_VERSION}) — this robot's personality:");
            show(&p);
            // Render beside the target and swap, so a power cut mid-render cannot leave a
            // half-bank that the marker calls complete.
            let staging = dir.with_extension("new");
            let _ = std::fs::remove_dir_all(&staging);
            let paths = render_all(&p, &staging)?;
            std::fs::write(staging.join(".seed"), &marker)?;
            let _ = std::fs::remove_dir_all(&dir);
            if let Some(parent) = dir.parent() {
                std::fs::create_dir_all(parent)?;
            }
            std::fs::rename(&staging, &dir)
                .with_context(|| format!("moving the bank into {}", dir.display()))?;
            println!("voice bank ({} sounds) at {}", paths.len(), dir.display());
        }
    }
    Ok(())
}

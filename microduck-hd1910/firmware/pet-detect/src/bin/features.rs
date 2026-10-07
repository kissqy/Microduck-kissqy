//! Dump log-mel features of a WAV to stdout as f32 LE, shape [N_MELS, WINDOW_FRAMES] per
//! block, sliding a 1-second window (50 % overlap by default).
//!
//! This is the training half of the train/infer parity contract: the Python training
//! script extracts features THROUGH this binary, so the model always trains on exactly what
//! the robot computes.

use std::io::Write;

use anyhow::Result;
use clap::Parser;
use pet_detect::{HOP, MelExtractor, N_MELS, WINDOW_FRAMES, WINDOW_SAMPLES, load_wav_mono_16k};

#[derive(Parser)]
#[command(
    name = "pet-features",
    about = "Log-mel features of a WAV, for training",
    version
)]
struct Args {
    /// A WAV file (any rate / channel count — resampled to 16 k mono).
    wav: String,
    /// Hop between windows in samples (default: 50 % overlap).
    #[arg(long)]
    stride: Option<usize>,
}

fn main() -> Result<()> {
    let args = Args::parse();
    let samples = load_wav_mono_16k(&args.wav)?;
    let stride = args.stride.unwrap_or(WINDOW_SAMPLES / 2);
    let extractor = MelExtractor::new();

    let stdout = std::io::stdout();
    let mut out = stdout.lock();
    let mut start = 0;
    let mut n_blocks = 0;
    while start + WINDOW_SAMPLES <= samples.len() {
        let mel = extractor.log_mel(&samples[start..start + WINDOW_SAMPLES]);
        let bytes: Vec<u8> = mel.iter().flat_map(|v| v.to_le_bytes()).collect();
        out.write_all(&bytes)?;
        n_blocks += 1;
        start += stride;
    }
    eprintln!(
        "wrote {n_blocks} blocks of [{N_MELS},{WINDOW_FRAMES}] f32 ({} bytes each, hop={HOP} samples)",
        N_MELS * WINDOW_FRAMES * 4,
    );
    Ok(())
}

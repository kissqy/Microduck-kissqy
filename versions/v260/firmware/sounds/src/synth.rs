//! DSP primitives — the Python `synth.py`, at 48 kHz.
//!
//! The original rendered at 22.05 kHz and the installer resampled every file with ffmpeg,
//! because the Radxa's I²S clock tree is pinned to the 48 k family (44.1 k-family rates play
//! ~9 % off). Rendering at 48 kHz natively removes the resample step and the ffmpeg
//! dependency. Two primitives had sample-rate-dependent constants tuned at 22.05 kHz — the
//! jitter smoothing window and the pink-noise pole — and both are rescaled by `SR / 22050`
//! here so they keep their *time-domain* character rather than their sample counts.

use crate::rng::Rng;

/// Output sample rate. See the module docs for why this is not the Python's 22 050.
pub const SR: u32 = 48_000;

/// The rate the Python recipes were tuned at, kept only to rescale the two
/// sample-count-based constants below.
const TUNED_SR: f64 = 22_050.0;

/// Time axis for a duration, one entry per sample.
pub fn t_axis(duration_s: f64) -> Vec<f32> {
    let n = ((duration_s * f64::from(SR)).round() as usize).max(1);
    (0..n).map(|i| i as f32 / SR as f32).collect()
}

/// Piecewise-linear curve through `(time_s, value)` points — numpy's `interp`, which clamps
/// to the first/last value outside the range.
pub fn lerp(t: &[f32], points: &[(f64, f64)]) -> Vec<f32> {
    t.iter()
        .map(|&x| {
            let x = f64::from(x);
            if x <= points[0].0 {
                return points[0].1 as f32;
            }
            for pair in points.windows(2) {
                let (x0, y0) = pair[0];
                let (x1, y1) = pair[1];
                if x <= x1 {
                    if x1 <= x0 {
                        return y1 as f32;
                    }
                    return (y0 + (y1 - y0) * (x - x0) / (x1 - x0)) as f32;
                }
            }
            points[points.len() - 1].1 as f32
        })
        .collect()
}

/// Fast attack, exponential decay envelope, peak ~1.0.
pub fn expdecay(t: &[f32], attack_s: f64, decay_s: f64) -> Vec<f32> {
    let attack = attack_s.max(1e-4) as f32;
    let decay = decay_s.max(1e-4) as f32;
    t.iter()
        .map(|&x| {
            let a = (x / attack).clamp(0.0, 1.0);
            let d = (-(x - attack).max(0.0) / decay).exp();
            a * d
        })
        .collect()
}

/// Soft attack, plateau, soft release.
pub fn bell(t: &[f32], attack_s: f64, release_s: f64) -> Vec<f32> {
    let total = f64::from(*t.last().unwrap_or(&0.0));
    let rel_start = (total - release_s).max(0.0);
    let attack = attack_s.max(1e-4);
    let release = release_s.max(1e-4);
    t.iter()
        .map(|&x| {
            let x = f64::from(x);
            let mut v = 1.0;
            if x < attack_s {
                v = x / attack;
            }
            if x > rel_start {
                v = (1.0 - (x - rel_start) / release).max(0.0);
            }
            v.clamp(0.0, 1.0) as f32
        })
        .collect()
}

/// Integrate instantaneous frequency to phase (radians).
pub fn phase_from_freq(freq: &[f32]) -> Vec<f32> {
    let mut acc = 0.0f64;
    freq.iter()
        .map(|&f| {
            acc += f64::from(f);
            (std::f64::consts::TAU * acc / f64::from(SR)) as f32
        })
        .collect()
}

/// Sum of sin(n·phase)·weight for each harmonic (n = 1..).
pub fn harmonic_osc(phase: &[f32], weights: &[f64]) -> Vec<f32> {
    let mut out = vec![0.0f32; phase.len()];
    for (n, &w) in weights.iter().enumerate() {
        if w == 0.0 {
            continue;
        }
        let n = (n + 1) as f32;
        let w = w as f32;
        for (o, &p) in out.iter_mut().zip(phase) {
            *o += w * (n * p).sin();
        }
    }
    out
}

/// Pitch multiplier from a slow LFO — multiply a frequency curve by it.
pub fn vibrato(t: &[f32], rate_hz: f64, depth_semitones: f64, phase: f64) -> Vec<f32> {
    if rate_hz <= 0.0 || depth_semitones <= 0.0 {
        return vec![1.0; t.len()];
    }
    t.iter()
        .map(|&x| {
            let lfo = (std::f64::consts::TAU * rate_hz * f64::from(x) + phase).sin();
            2.0f64.powf(depth_semitones * lfo / 12.0) as f32
        })
        .collect()
}

/// Random pitch wobble, smoothed white noise — the organic, alive feel.
///
/// The Python smoothed over a fixed 64 samples at 22.05 kHz (~2.9 ms); the window scales
/// with the rate here so the wobble keeps its speed rather than its sample count.
pub fn jitter(t: &[f32], depth_semitones: f64, rng: &mut Rng) -> Vec<f32> {
    if depth_semitones <= 0.0 {
        return vec![1.0; t.len()];
    }
    let raw = rng.standard_normal_vec(t.len());
    let window = ((64.0 * f64::from(SR) / TUNED_SR).round() as usize).max(1);
    let smoothed = moving_average_same(&raw, window);
    smoothed
        .iter()
        .map(|&x| 2.0f64.powf(depth_semitones * f64::from(x) / 12.0) as f32)
        .collect()
}

/// numpy `convolve(x, ones(k)/k, mode="same")`: centred moving average with zero padding.
fn moving_average_same(x: &[f32], k: usize) -> Vec<f32> {
    let n = x.len();
    let mut out = vec![0.0f32; n];
    // convolve('same') keeps the centre of the full convolution: output i sums
    // x[i - k + 1 + offset ..= i + offset] with offset = (k - 1) / 2.
    let offset = (k - 1) / 2;
    let inv = 1.0 / k as f32;
    let mut acc = 0.0f32;
    let mut hi = 0usize; // exclusive end of the window in x
    for (i, o) in out.iter_mut().enumerate() {
        let want_hi = (i + offset + 1).min(n);
        while hi < want_hi {
            acc += x[hi];
            hi += 1;
        }
        let lo = (i + offset + 1).saturating_sub(k);
        if i > 0 {
            let prev_lo = (i + offset).saturating_sub(k);
            for &v in &x[prev_lo..lo] {
                acc -= v;
            }
        }
        *o = acc * inv;
    }
    out
}

/// Cheap pink-ish noise via a leaky integrator over white. Soft, breathy.
///
/// The pole (0.985/sample at 22.05 kHz) is rescaled so the noise keeps its colour at 48 kHz
/// instead of getting brighter with the higher rate.
pub fn pink_noise(n: usize, rng: &mut Rng) -> Vec<f32> {
    let a = 0.985f64.powf(TUNED_SR / f64::from(SR)) as f32;
    let mut leak = 0.0f32;
    let mut pink: Vec<f32> = (0..n)
        .map(|_| {
            leak = a * leak + rng.standard_normal();
            leak
        })
        .collect();
    let peak = pink.iter().fold(0.0f32, |m, &v| m.max(v.abs())) + 1e-9;
    for v in &mut pink {
        *v /= peak;
    }
    pink
}

/// Short transient click — the `peck` attack.
pub fn click(n: usize, rng: &mut Rng, length: usize) -> Vec<f32> {
    let mut out = vec![0.0f32; n];
    let l = length.min(n);
    for (i, o) in out.iter_mut().take(l).enumerate() {
        let fade = 1.0 - i as f32 / l as f32;
        *o = rng.uniform(-1.0, 1.0) as f32 * fade * fade;
    }
    out
}

/// Scale to a peak level in dBFS.
pub fn normalise(x: &mut [f32], peak_dbfs: f64) {
    let peak = x.iter().fold(0.0f32, |m, &v| m.max(v.abs())) + 1e-9;
    let target = 10.0f64.powf(peak_dbfs / 20.0) as f32;
    let gain = target / peak;
    for v in x {
        *v *= gain;
    }
}

pub fn to_i16(x: &[f32]) -> Vec<i16> {
    x.iter()
        .map(|&v| (v * 32767.0).clamp(-32768.0, 32767.0) as i16)
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn lerp_matches_interp_semantics() {
        let t = [0.0f32, 0.5, 1.0, 2.0];
        let out = lerp(&t, &[(0.0, 1.0), (1.0, 3.0)]);
        assert_eq!(out, vec![1.0, 2.0, 3.0, 3.0], "clamps past the last point");
    }

    #[test]
    fn moving_average_matches_numpy_same_mode() {
        // numpy: convolve([1,2,3,4,5], ones(3)/3, 'same') = [1, 2, 3, 4, 3]
        let out = moving_average_same(&[1.0, 2.0, 3.0, 4.0, 5.0], 3);
        for (got, want) in out.iter().zip([1.0, 2.0, 3.0, 4.0, 3.0]) {
            assert!((got - want).abs() < 1e-6, "{out:?}");
        }
        // Even window: numpy keeps the centre with offset (k-1)/2 = 1 for k=4:
        // convolve([1,2,3,4,5], ones(4)/4, 'same') = [1.5, 2.5, 3.5, 3.0, 2.25]... trimmed
        // to length 5 starting at index 1: [0.75, 1.5, 2.5, 3.5, 3.0]
        let out = moving_average_same(&[1.0, 2.0, 3.0, 4.0, 5.0], 4);
        for (got, want) in out.iter().zip([0.75, 1.5, 2.5, 3.5, 3.0]) {
            assert!((got - want).abs() < 1e-6, "{out:?}");
        }
    }

    #[test]
    fn normalise_hits_the_target_peak() {
        let mut x = vec![0.1, -0.4, 0.2];
        normalise(&mut x, -3.0);
        let peak = x.iter().fold(0.0f32, |m, &v| m.max(v.abs()));
        assert!((f64::from(peak) - 10.0f64.powf(-3.0 / 20.0)).abs() < 1e-4);
    }

    #[test]
    fn envelopes_stay_in_unit_range() {
        let t = t_axis(0.3);
        for v in expdecay(&t, 0.01, 0.1)
            .iter()
            .chain(bell(&t, 0.05, 0.1).iter())
        {
            assert!((0.0..=1.0).contains(v));
        }
    }
}

//! A `Personality` derives stable per-robot vocal traits from a single seed.
//!
//! Two robots with different seeds sound recognisably different; the same robot is
//! consistent across runs. Variants within a tag re-roll a small sub-seed so the duck
//! doesn't sound like a stuck recording.
//!
//! The trait set is deliberately wide: register (octave shift), harmonic tilt, formant
//! emphasis, glide bias, quackiness — each one alone is enough to make two seeds feel like
//! different creatures.

use crate::rng::{Rng, crc32};

/// Every field is a stable function of the seed. `Copy`, because the recipes soften copies
/// of it per tag (the Python's `dataclasses.replace`).
#[derive(Debug, Clone, Copy)]
pub struct Personality {
    pub seed: u32,

    // --- pitch ---
    pub pitch_center_hz: f64,
    /// -1..+1, extra octave-ish shift on top of center.
    pub register: f64,
    /// 0..1, how dramatic glides are.
    pub pitch_spread: f64,
    /// -1..+1, negative = falls, positive = rises.
    pub glide_bias: f64,

    // --- timbre ---
    /// 0..1, harmonic rolloff (1 = bright/buzzy).
    pub brightness: f64,
    /// 1.4..2.8, exponent on harmonic decay (higher = darker).
    pub tilt: f64,
    /// 0..1, emphasis on 2nd/3rd harmonic.
    pub nasal: f64,
    /// -1..+1, negative = odd-only (square-ish), positive = even-leaning.
    pub harmonic_skew: f64,
    /// 1..5, which harmonic the formant boosts.
    pub formant_n: usize,
    /// 0..1.5, formant strength.
    pub formant_gain: f64,

    // --- modulation ---
    pub vibrato_rate_hz: f64,
    /// 0..0.7 semitones.
    pub vibrato_depth: f64,
    /// 0..0.4 semitones, random pitch wobble.
    pub jitter_depth: f64,
    /// 0..0.35, noise mix.
    pub breath: f64,
    /// 0.2..1, blends pure-tone vs am-buzz.
    pub quackiness: f64,
    /// 18..55, quack/croak-buzz rate (only matters with quackiness > 0).
    pub am_rate_hz: f64,
    /// 0..0.7, modulation depth.
    pub am_depth: f64,
    /// 7..18, trill on chirp.
    pub warble_hz: f64,
    /// 0..1.5 semitones.
    pub warble_depth: f64,

    // --- timing ---
    /// 0..1, 0 = soft pad, 1 = snappy.
    pub attack_sharpness: f64,
    /// 0.8..1.25, global tempo multiplier.
    pub speed: f64,
}

impl Personality {
    pub fn from_seed(seed: u32) -> Self {
        let mut rng = Rng::from_seed(seed);

        // Bimodal-ish register: some ducks smaller & higher, some big & low — but the whole
        // population sits low, duck/toad territory.
        let register = rng.choice(&[-1.0, 0.0, 0.0, 1.0]) + rng.uniform(-0.4, 0.4);
        let base = rng.uniform(160.0, 380.0);
        let pitch = (base * 2.0f64.powf(register * 0.45)).clamp(110.0, 620.0);

        Self {
            seed,
            pitch_center_hz: pitch,
            register,
            pitch_spread: rng.uniform(0.4, 1.2),
            glide_bias: rng.uniform(-1.0, 1.0),

            brightness: rng.uniform(0.05, 0.55),
            tilt: rng.uniform(1.4, 2.8),
            nasal: rng.uniform(0.1, 1.0),
            harmonic_skew: rng.uniform(-1.0, 1.0),
            formant_n: rng.integers(1, 6) as usize,
            formant_gain: rng.uniform(0.0, 1.4),

            vibrato_rate_hz: rng.uniform(3.5, 9.5),
            vibrato_depth: rng.uniform(0.0, 0.7),
            jitter_depth: rng.uniform(0.03, 0.35),
            breath: rng.uniform(0.0, 0.30),
            quackiness: rng.uniform(0.2, 1.0),
            am_rate_hz: rng.uniform(18.0, 55.0),
            am_depth: rng.uniform(0.15, 0.70),
            warble_hz: rng.uniform(7.0, 18.0),
            warble_depth: rng.uniform(0.0, 1.4),

            attack_sharpness: rng.uniform(0.0, 1.0),
            speed: rng.uniform(0.82, 1.22),
        }
    }

    /// Stable per-(seed, tag, variant) RNG for sub-randomisation.
    ///
    /// CRC-32 rather than a hasher from the standard library, whose hashing is salted per
    /// process — that would re-roll every variant on each regeneration of the bank.
    pub fn variant_rng(&self, tag: &str, variant: u32) -> Rng {
        let h = (u64::from(self.seed).wrapping_mul(1_000_003))
            ^ u64::from(crc32(tag.as_bytes()))
            ^ u64::from(variant).wrapping_mul(2_654_435_761);
        Rng::from_seed(h as u32)
    }

    /// Personality-shaped harmonic weights for the main oscillator.
    ///
    /// Combines: tilt (overall rolloff, darker → steeper), brightness (lifts the high-end
    /// tail), nasal (lifts 2nd/3rd), harmonic_skew (even-vs-odd preference), and a formant
    /// bump at one chosen harmonic.
    pub fn harmonics(&self) -> Vec<f64> {
        const N_HARM: usize = 7;
        let mut weights = Vec::with_capacity(N_HARM);
        for n in 1..=N_HARM {
            let base = 1.0 / (n as f64).powf(self.tilt);
            let high_lift = self.brightness * (n as f64 / N_HARM as f64).powf(1.5);
            let nasal = self.nasal * if n == 2 || n == 3 { 0.6 } else { 0.0 };
            let skew = if self.harmonic_skew >= 0.0 {
                self.harmonic_skew * if n % 2 == 0 { 0.4 } else { -0.2 }
            } else {
                -self.harmonic_skew * if n % 2 == 0 { -0.3 } else { 0.4 }
            };
            let formant = if n == self.formant_n {
                self.formant_gain
            } else {
                0.0
            };
            weights.push((base + high_lift + nasal + skew + formant * base * 1.5).max(0.0));
        }
        // Keep f0 dominant so pitch is always perceptible.
        weights[0] = weights[0].max(0.7);
        weights
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The same seed is the same duck, forever; different seeds are different ducks.
    #[test]
    fn a_seed_is_a_stable_identity() {
        let a = Personality::from_seed(100);
        let b = Personality::from_seed(100);
        assert_eq!(a.pitch_center_hz, b.pitch_center_hz);
        assert_eq!(a.speed, b.speed);

        let c = Personality::from_seed(101);
        assert_ne!(a.pitch_center_hz, c.pitch_center_hz);
    }

    /// Every trait must land inside its documented range — the recipes lean on that.
    #[test]
    fn traits_stay_in_their_ranges() {
        for seed in 0..500 {
            let p = Personality::from_seed(seed);
            assert!((110.0..=620.0).contains(&p.pitch_center_hz), "seed {seed}");
            assert!((1..=5).contains(&p.formant_n), "seed {seed}");
            assert!((0.82..1.22).contains(&p.speed), "seed {seed}");
            assert!((0.2..1.0).contains(&p.quackiness), "seed {seed}");
            let w = p.harmonics();
            assert_eq!(w.len(), 7);
            assert!(w[0] >= 0.7, "f0 must stay dominant");
        }
    }

    /// Variant RNGs must differ across variants and stay stable across calls.
    #[test]
    fn variant_rng_is_stable_and_distinct() {
        let p = Personality::from_seed(7);
        let a = p.variant_rng("chirp", 0).random();
        let b = p.variant_rng("chirp", 0).random();
        let c = p.variant_rng("chirp", 1).random();
        let d = p.variant_rng("greet", 0).random();
        assert_eq!(a, b);
        assert_ne!(a, c);
        assert_ne!(a, d);
    }
}

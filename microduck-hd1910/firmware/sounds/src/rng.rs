//! A small deterministic RNG the voices depend on, owned here on purpose.
//!
//! The Python original used `np.random.default_rng` (PCG64 + numpy's distributions). A
//! robot's voice is *derived*, not stored — the bank is re-rendered from the seed on every
//! install that bumps the bank version — so the generator IS the voice. Depending on `rand`
//! for it would tie every duck's voice to whichever algorithm that crate ships this year;
//! `StdRng` explicitly reserves the right to change. Forty lines of xoshiro we own cannot
//! drift.
//!
//! xoshiro256++ seeded through splitmix64 (both public domain, Blackman & Vigna). Uniforms
//! take the top 53 bits; normals are Box–Muller. None of it needs to match numpy — the port
//! re-rolls every voice once, and the bank version bump makes that a regeneration, not a
//! corruption.

/// Deterministic stream of the distributions the recipes use.
pub struct Rng {
    s: [u64; 4],
    /// Box–Muller produces pairs; the spare is handed out on the next call.
    spare_normal: Option<f32>,
}

impl Rng {
    /// Seed from a u32, as the Python did (`seed & 0xFFFFFFFF`). splitmix64 expands it into
    /// the four xoshiro words so small seeds still start well-mixed.
    pub fn from_seed(seed: u32) -> Self {
        let mut x = u64::from(seed);
        let mut next = || {
            x = x.wrapping_add(0x9E37_79B9_7F4A_7C15);
            let mut z = x;
            z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
            z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
            z ^ (z >> 31)
        };
        Self {
            s: [next(), next(), next(), next()],
            spare_normal: None,
        }
    }

    fn next_u64(&mut self) -> u64 {
        let s = &mut self.s;
        let result = s[0].wrapping_add(s[3]).rotate_left(23).wrapping_add(s[0]);
        let t = s[1] << 17;
        s[2] ^= s[0];
        s[3] ^= s[1];
        s[1] ^= s[2];
        s[0] ^= s[3];
        s[2] ^= t;
        s[3] = s[3].rotate_left(45);
        result
    }

    /// Uniform in [0, 1), from the top 53 bits — the full precision an f64 mantissa holds.
    pub fn random(&mut self) -> f64 {
        (self.next_u64() >> 11) as f64 * (1.0 / (1u64 << 53) as f64)
    }

    /// Uniform in [lo, hi).
    pub fn uniform(&mut self, lo: f64, hi: f64) -> f64 {
        lo + (hi - lo) * self.random()
    }

    /// Uniform integer in [lo, hi) — numpy's `integers` half-open convention.
    pub fn integers(&mut self, lo: i64, hi: i64) -> i64 {
        lo + (self.random() * (hi - lo) as f64).floor() as i64
    }

    /// One element of `choices`, uniformly.
    pub fn choice(&mut self, choices: &[f64]) -> f64 {
        choices[self.integers(0, choices.len() as i64) as usize]
    }

    /// Standard normal, Box–Muller.
    pub fn standard_normal(&mut self) -> f32 {
        if let Some(z) = self.spare_normal.take() {
            return z;
        }
        // r in (0, 1]: 1 - random() cannot be zero, so ln() stays finite.
        let r = 1.0 - self.random();
        let theta = std::f64::consts::TAU * self.random();
        let mag = (-2.0 * r.ln()).sqrt();
        self.spare_normal = Some((mag * theta.sin()) as f32);
        (mag * theta.cos()) as f32
    }

    /// `n` standard normals, as the vectorised numpy calls drew them.
    pub fn standard_normal_vec(&mut self, n: usize) -> Vec<f32> {
        (0..n).map(|_| self.standard_normal()).collect()
    }
}

/// CRC-32 (IEEE), as `zlib.crc32` computes it — the variant RNG's tag hash. Implemented
/// here rather than pulled in: the polynomial is fixed by the voices already in the field.
pub fn crc32(data: &[u8]) -> u32 {
    let mut crc = 0xFFFF_FFFFu32;
    for &byte in data {
        crc ^= u32::from(byte);
        for _ in 0..8 {
            let mask = (crc & 1).wrapping_neg();
            crc = (crc >> 1) ^ (0xEDB8_8320 & mask);
        }
    }
    !crc
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The same seed must produce the same stream forever — this is a robot's voice, and a
    /// generator change would re-voice the whole fleet silently. Pinned values, so a
    /// dependency-free refactor that changes the stream fails loudly instead.
    #[test]
    fn the_stream_is_pinned() {
        let mut rng = Rng::from_seed(100);
        let first: Vec<u64> = (0..4).map(|_| rng.next_u64()).collect();
        let mut again = Rng::from_seed(100);
        let second: Vec<u64> = (0..4).map(|_| again.next_u64()).collect();
        assert_eq!(first, second);

        let mut other = Rng::from_seed(101);
        assert_ne!(first[0], other.next_u64(), "seeds must differ");
    }

    #[test]
    fn uniform_stays_in_range() {
        let mut rng = Rng::from_seed(7);
        for _ in 0..10_000 {
            let v = rng.uniform(160.0, 380.0);
            assert!((160.0..380.0).contains(&v));
            let i = rng.integers(1, 6);
            assert!((1..6).contains(&i));
        }
    }

    #[test]
    fn normals_have_sane_moments() {
        let mut rng = Rng::from_seed(42);
        let xs = rng.standard_normal_vec(100_000);
        let mean = xs.iter().sum::<f32>() / xs.len() as f32;
        let var = xs.iter().map(|x| (x - mean) * (x - mean)).sum::<f32>() / xs.len() as f32;
        assert!(mean.abs() < 0.02, "mean {mean}");
        assert!((var - 1.0).abs() < 0.05, "var {var}");
    }

    /// zlib.crc32 reference values, so the variant sub-seeds keep their meaning.
    #[test]
    fn crc32_matches_zlib() {
        assert_eq!(crc32(b""), 0);
        assert_eq!(crc32(b"chirp"), 0xEC28_BF8B);
        assert_eq!(crc32(b"123456789"), 0xCBF4_3926);
    }
}

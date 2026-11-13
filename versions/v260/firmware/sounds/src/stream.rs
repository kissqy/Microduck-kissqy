//! The duck's voice, held open: a block-wise synth driven by live parameters.
//!
//! Every other sound in this crate is a *recipe* — a whole vocalisation rendered offline
//! from a frequency curve the recipe writes down in advance ([`crate::voices`]). That is
//! the right shape for a quack, and the wrong one for anything the robot must sing *while*
//! something outside it moves. The ToF theremin's pitch is a hand's distance, known only
//! 15 times a second and never in advance, so the frequency curve cannot be written down:
//! it has to be integrated as it arrives.
//!
//! So this is the same synth, turned inside out. [`Stream::block`] renders a short block
//! of audio from the parameters as they stand *now* and carries every piece of state that
//! spans blocks — oscillator phase, LFO phase, the jitter and breath filters, and the
//! slewed parameters themselves — across the call. Concatenating its blocks gives one
//! continuous signal with no seam, whatever the block sizes were.
//!
//! **It is the same duck.** Not a resample of the bank and not a second voice: the
//! harmonic weights are [`Personality::harmonics`], the vibrato, jitter, breath and quack-AM
//! are that personality's, and [`Stream::wheee`] applies the same softening the joy-ride
//! recipe does ([`crate::voices::wheee_segments`]). A duck's theremin sounds like that
//! duck's wheee, held for as long as the hand stays.
//!
//! ## What is different from the offline path, and why
//!
//! - **Normalisation is static.** A recipe normalises the finished buffer to a peak; a
//!   stream has no finished buffer, and a per-block normalise would pump the level with
//!   every block. The gain is derived from the harmonic weights instead — worst-case
//!   in-phase sum — and a `tanh` soft clip catches what the AM and breath add on top.
//! - **Parameters slew.** Depth arrives every ~67 ms and the mouth servo is slower still;
//!   stepping the frequency on frame boundaries would stair-step audibly. Each parameter
//!   glides toward its target with a one-pole filter at audio rate, so a 15 Hz input
//!   produces a continuous glide.
//! - **The jitter and breath filters are recursive.** The offline versions convolve a
//!   whole buffer (a centred moving average, a normalised leaky integrator); neither can
//!   see the future or the past here, so both become one-pole filters with the same time
//!   constant. The character is the same; the sample values are not, which is why nothing
//!   in this file is pinned against the bank.

use crate::personality::Personality;
use crate::rng::Rng;
use crate::synth::SR;

/// How fast a parameter reaches a new target, as a time constant in seconds.
///
/// Pitch glides slowest: it is the one a listener hears as a *slide*, and the ToF's 67 ms
/// between frames is long enough that a faster constant reintroduces the stair-step.
const PITCH_TAU_S: f64 = 0.045;
/// Level, and so the note's attack and release. Fast enough to feel keyed, slow enough that
/// a hand leaving the frame is a fade rather than a click.
const LEVEL_TAU_S: f64 = 0.030;
/// Timbre. Slower than the mouth servo can move anyway, which keeps the two in step.
const OPEN_TAU_S: f64 = 0.060;

/// The jitter filter's time constant — the offline `jitter`'s 64-sample window at 22.05 kHz.
const JITTER_TAU_S: f64 = 64.0 / 22_050.0;

/// How far a vowel may move the formant, in harmonics.
///
/// The synth has no filter — the formant is a boost on one harmonic of seven
/// ([`Personality::harmonics`]) — so a "vowel" here is that boost moving up and down the
/// series, plus the mouth opening. Crude against a real vocal tract, and enough: `oo` and
/// `ee` are unmistakably different sounds, which is the whole requirement for a chorale that
/// should sound like it is singing *something* rather than humming.
const FORMANT_RANGE: f64 = 3.0;

/// How much a wide-open mouth lifts the harmonic tilt.
///
/// The weights fall off as `n^-tilt`, so subtracting from the exponent raises every harmonic
/// above the fundamental: a closed beak is dark and a wide one is bright, which is what an
/// opening vocal tract does. 0.8 was picked by ear against the bank's own timbre spread —
/// audible as *the same duck opening its mouth*, not as a filter sweep.
const OPEN_TILT_LIFT: f64 = 0.8;

/// Headroom under full scale for the static gain, before the soft clip.
///
/// The worst case it bounds is every harmonic in phase, which is rare — so the *typical* peak sits
/// well below this and there is real headroom for the AM and the breath that go on top. Deliberately
/// under the bank's own −4 dBFS: a synthesized voice can be asked for a level a recorded one cannot.
const PEAK: f32 = 0.62;

/// How steeply a small speaker falls away below its useful range, in dB per octave.
///
/// A sealed driver the size of a coin rolls off at about this, and the exact figure matters less
/// than the shape: the point is that amplitude spent below it is not merely quiet, it is *gone*,
/// and spending it there is worse than not spending it.
const ROLLOFF_DB_PER_OCTAVE: f64 = 12.0;

/// The most [`Stream::set_speaker_rolloff`] may amplify what is left after it has given up on the
/// low harmonics.
///
/// A note whose *whole* series sits below the rolloff has nothing to redistribute to, and
/// renormalising it would turn a note the speaker cannot make into a loud note the speaker cannot
/// make. Clamped, so a bass note off the bottom of the instrument stays quiet instead of becoming
/// distortion.
///
/// Was 4×, which on the robot sounded saturated: a full redistribution piles the whole note onto
/// harmonics two to four, and that much upper-harmonic energy through a small driver is harsh rather
/// than loud. 2× recovers most of the audibility for a fraction of the harshness.
const MAX_BASS_LIFT: f64 = 2.0;

/// How often the harmonic weights are recomputed, in samples (~5 ms).
///
/// Not once per block, which is the obvious place for it and is wrong: the block size is
/// the audio sink's business, and refreshing on its boundaries would put the sink's buffer
/// length into the signal — a smaller buffer would track the mouth sooner and so sound
/// different. A fixed cadence in *samples rendered* depends on nothing but the stream
/// itself, and 5 ms is far faster than a servo or an ear can follow.
const REFRESH_SAMPLES: u32 = 256;

/// A voice that can be driven sample-accurately from parameters that arrive slowly.
///
/// Construct once per performance, call [`Stream::set`] whenever new parameters arrive, and
/// [`Stream::block`] as often as the audio sink needs samples. The two are independent: a
/// `set` between blocks, several `set`s between blocks, or none, all behave.
pub struct Stream {
    p: Personality,
    rng: Rng,

    /// Carrier phase, radians, wrapped to keep `sin` accurate over a long ride.
    phase: f64,
    /// Seconds of audio rendered — the LFOs' time axis.
    t: f64,

    /// One-pole state for the pitch wobble, in standard deviations.
    jitter: f32,
    /// Leaky-integrator state for the breath noise.
    pink: f32,

    // Slewed parameters: `_target` is what was asked for, the bare field is where the
    // glide has actually reached.
    freq: f64,
    freq_target: f64,
    level: f64,
    level_target: f64,
    open: f64,
    open_target: f64,

    /// Formant offset in harmonics, from the vowel being sung. See [`FORMANT_RANGE`].
    formant_shift: f64,
    formant_shift_target: f64,
    /// Where the speaker stops reproducing, if the caller has said. See
    /// [`Stream::set_speaker_rolloff`].
    speaker_rolloff_hz: Option<f64>,
    /// Harmonic weights for the current `open`, and the `open` they were computed at — 7
    /// `powf`s are not worth spending while the mouth has not moved.
    weights: Vec<f64>,
    weights_open: f64,
    /// The formant offset the weights were computed at, for the same reason.
    weights_formant: f64,
    /// And the frequency, which matters once a speaker rolloff is in play: the weights then depend
    /// on where the harmonics *land*, not only on their relative sizes.
    weights_freq: f64,
    /// Samples until the next weight refresh. See [`REFRESH_SAMPLES`].
    refresh_in: u32,
    /// Static gain, from the weights' worst-case sum.
    gain: f32,

    /// Per-voice softening (see [`Stream::wheee`], [`Stream::choral`]) folded into the
    /// modulation depths, rather than read off the personality — the ensemble voice needs
    /// less of all of these than the solo one.
    vibrato_depth: f64,
    quackiness: f64,
    jitter_depth: f64,
    /// Noise mix for this voice. A choir member breathes less audibly than a soloist.
    breath: f64,
    /// How much of the breath survives the speaker-rolloff rebalance, 0..1.
    ///
    /// The rolloff takes voiced energy away from a deep note; the noise, being broadband,
    /// would keep all of its — so an already-quiet bass note would be *proportionally*
    /// noisier. The breath is cut by the same fraction the harmonics lost.
    breath_rolloff: f64,
    /// Excitement wobble: the wheee's own, at full swell.
    wobble_hz: f64,
    wobble_depth: f64,
}

impl Stream {
    /// A stream in this duck's plain voice, silent until [`Stream::set`] gives it a level.
    ///
    /// `seed_tag` and `variant` pick the stable sub-randomisation, exactly as a recipe's
    /// [`Personality::variant_rng`] does, so two performances of the same tag on the same
    /// robot have the same wobble rate rather than re-rolling per press.
    pub fn new(p: &Personality, seed_tag: &str, variant: u32) -> Self {
        let mut rng = p.variant_rng(seed_tag, variant);
        let wobble_hz = 4.5 + 3.0 * rng.random();
        let mut s = Self {
            p: *p,
            rng,
            phase: 0.0,
            t: 0.0,
            jitter: 0.0,
            pink: 0.0,
            freq: p.pitch_center_hz,
            freq_target: p.pitch_center_hz,
            level: 0.0,
            level_target: 0.0,
            open: 0.0,
            open_target: 0.0,
            formant_shift: 0.0,
            formant_shift_target: 0.0,
            speaker_rolloff_hz: None,
            weights: Vec::new(),
            // Not any reachable `open`, so the first sample computes the weights.
            weights_open: f64::NAN,
            weights_formant: f64::NAN,
            weights_freq: f64::NAN,
            refresh_in: 0,
            gain: 1.0,
            vibrato_depth: p.vibrato_depth,
            quackiness: p.quackiness,
            jitter_depth: p.jitter_depth,
            breath: p.breath * 0.5,
            breath_rolloff: 1.0,
            wobble_hz,
            wobble_depth: 0.0,
        };
        s.refresh_weights();
        s
    }

    /// The joy-ride voice: the same softening [`crate::voices::wheee_segments`] applies.
    ///
    /// Less vibrato and less quack-buzz so a long glide stays clean, plus the ride's
    /// excitement wobble. This is the constructor the theremin uses — the point is that a
    /// held theremin note and a held `wheee` are recognisably the same sound.
    pub fn wheee(p: &Personality, variant: u32) -> Self {
        let mut s = Self::new(p, "wheee", variant);
        s.vibrato_depth = p.vibrato_depth * 0.5;
        s.quackiness = p.quackiness * 0.5;
        s.wobble_depth = 0.5;
        s
    }

    /// The ensemble voice: this duck's timbre with its tuning-wrecking modulation tamed.
    ///
    /// A solo duck's charm is partly that it wavers — vibrato, random jitter, the quack-buzz
    /// AM. In a chord all three fight the *tuning*: two voices wobbling independently around
    /// the same note beat against each other, and a chord that beats sounds sour rather than
    /// lush. So they are scaled down hard rather than off — the duck must still be
    /// recognisable, and a chorus of perfectly steady tones sounds like an organ.
    ///
    /// What is *not* touched is everything that makes this duck this duck: the harmonic
    /// weights, the formant, the nasality, the breath. Identity is timbre here; the pitch
    /// belongs to the score.
    pub fn choral(p: &Personality, variant: u32) -> Self {
        let mut s = Self::new(p, "chorale", variant);
        s.vibrato_depth = p.vibrato_depth * 0.30;
        s.quackiness = p.quackiness * 0.35;
        s.jitter_depth = p.jitter_depth * 0.30;
        s.breath = p.breath * 0.15;
        s.wobble_depth = 0.0;
        s
    }

    /// This duck's playable range — [`range_hz`], for the voice this stream is in.
    pub fn range_hz(&self) -> (f64, f64) {
        range_hz(&self.p)
    }

    /// Frequency for a 0..1 position in this stream's range — [`hz_at`].
    pub fn hz_at(&self, position: f64) -> f64 {
        hz_at(&self.p, position)
    }

    /// Tell the voice what the speaker can actually reproduce, in hertz — or `None` for a
    /// full-range one.
    ///
    /// **This makes low notes louder by making the fundamental quieter**, which sounds backwards
    /// and is the whole trick. A duck's speaker is a coin-sized driver that produces very little
    /// below a few hundred hertz, so a bass line's fundamental is not quiet — it is absent, and
    /// the amplitude allocated to it is spent on nothing while eating the headroom the rest of the
    /// note needs. Worse, pushing harder at it is how a small driver is made to distort.
    ///
    /// So the weight is taken *off* the harmonics the driver cannot produce and given to the ones
    /// it can. The pitch survives because pitch does not live in the fundamental: a series spaced
    /// 130 Hz apart is heard as a 130 Hz note whether or not there is anything at 130 Hz — the
    /// residue pitch every small speaker has always relied on.
    ///
    /// Off by default: on a laptop the fundamental is real and there is nothing to work around.
    pub fn set_speaker_rolloff(&mut self, hz: Option<f64>) {
        self.speaker_rolloff_hz = hz.filter(|hz| *hz > 0.0);
        // The weights depend on it, and it is set rarely enough that recomputing now is free.
        self.refresh_weights();
    }

    /// Set the vowel being sung: which harmonic the formant boosts, relative to this duck's
    /// own [`Personality::formant_n`].
    ///
    /// Separate from [`Stream::set`] because it is a different *kind* of parameter — the
    /// theremin has no vowels and passes only pitch, level and mouth. Slewed like the rest, so
    /// a change of syllable is a movement rather than a click.
    pub fn set_formant_shift(&mut self, harmonics: f64) {
        self.formant_shift_target = harmonics.clamp(-FORMANT_RANGE, FORMANT_RANGE);
    }

    /// Silence the voice without moving its pitch — a note ending, rather than a note falling over.
    ///
    /// The pitch is left where it was because a fade at the note you were singing is a release, and
    /// a fade on the way somewhere else is a slide out of a chord.
    pub fn set_level(&mut self, level: f64) {
        self.level_target = level.clamp(0.0, 1.0);
    }

    /// Set the targets the stream glides toward.
    ///
    /// - `hz`: carrier frequency. Clamped to something a voice can actually sing.
    /// - `level`: 0 silent, 1 full. This is the note's key: 0 fades out, and back up again
    ///   without a click, because the fade is a slew and not a gate.
    /// - `open`: 0..1, how open the mouth is. Brightens the timbre; pass the *same* value
    ///   the mouth servo is being sent, so what is seen and what is heard are one gesture.
    pub fn set(&mut self, hz: f64, level: f64, open: f64) {
        self.freq_target = hz.clamp(30.0, f64::from(SR) / 3.0);
        self.level_target = level.clamp(0.0, 1.0);
        self.open_target = open.clamp(0.0, 1.0);
    }

    /// True once the level has faded to silence and nothing is being asked for — the
    /// moment a caller can stop pulling blocks without cutting a note off.
    pub fn is_silent(&self) -> bool {
        self.level_target <= 0.0 && self.level < 1e-4
    }

    /// Render the next `out.len()` samples, advancing every piece of state.
    ///
    /// Block size is a caller's choice and changes nothing about the output: the signal
    /// depends only on how many samples have been rendered and what the parameters were
    /// when each one was.
    pub fn block(&mut self, out: &mut [f32]) {
        let dt = 1.0 / f64::from(SR);
        let a_pitch = pole(PITCH_TAU_S);
        let a_level = pole(LEVEL_TAU_S);
        let a_open = pole(OPEN_TAU_S);
        let a_jitter = pole(JITTER_TAU_S) as f32;
        // The offline pink noise's pole, rescaled to 48 kHz the same way.
        let a_pink_f32 = 0.985f64.powf(22_050.0 / f64::from(SR)) as f32;

        let am_depth = self.p.am_depth * 0.5 * self.quackiness;
        let breath = self.breath * self.breath_rolloff;
        // The integrator below has a steady-state deviation of 1/sqrt(1 - a²) ≈ 8.5, and the
        // first version scaled it by a guessed 0.15 — leaving the streamed breath five times
        // louder than the offline voice's, which a listener reported as a bass duck full of
        // white noise (that seed happened to roll a breathy personality). Normalised properly:
        // to unit deviation, then to the ~0.25 RMS the offline peak-normalised noise has.
        let a_pink = 0.985f64.powf(22_050.0 / f64::from(SR));
        let pink_gain = ((1.0 - a_pink * a_pink).sqrt() * 0.25) as f32;

        for sample in out.iter_mut() {
            // Timbre, on its own cadence — see `REFRESH_SAMPLES` for why not per block.
            if self.refresh_in == 0 {
                let moved_a_lot = |from: f64, to: f64| (to - from).abs() > from.abs() * 0.01;
                if (self.open - self.weights_open).abs() > 0.005
                    || (self.formant_shift - self.weights_formant).abs() > 0.02
                    || (self.speaker_rolloff_hz.is_some()
                        && moved_a_lot(self.weights_freq, self.freq))
                {
                    self.refresh_weights();
                }
                self.refresh_in = REFRESH_SAMPLES;
            }
            self.refresh_in -= 1;

            // Slew toward the targets.
            self.freq += (self.freq_target - self.freq) * a_pitch;
            self.level += (self.level_target - self.level) * a_level;
            self.open += (self.open_target - self.open) * a_open;
            self.formant_shift += (self.formant_shift_target - self.formant_shift) * a_open;

            // Pitch modulation: this duck's vibrato, its jitter, and the ride's wobble.
            let vib = semitones(
                self.vibrato_depth
                    * (std::f64::consts::TAU * self.p.vibrato_rate_hz * self.t).sin(),
            );
            self.jitter += (self.rng.standard_normal() - self.jitter) * a_jitter;
            let jit = semitones(self.jitter_depth * f64::from(self.jitter));
            let wob = semitones(
                self.wobble_depth * (std::f64::consts::TAU * self.wobble_hz * self.t).sin(),
            );

            // Integrate frequency to phase. Wrapped, not accumulated: an unbounded phase
            // loses `sin`'s precision over a ride that can last minutes.
            self.phase += std::f64::consts::TAU * self.freq * vib * jit * wob * dt;
            if self.phase >= std::f64::consts::TAU {
                self.phase -= std::f64::consts::TAU;
            }

            let mut v = 0.0f64;
            for (n, &w) in self.weights.iter().enumerate() {
                if w == 0.0 {
                    continue;
                }
                v += w * ((n + 1) as f64 * self.phase).sin();
            }
            let mut v = (v as f32) * self.gain;

            if am_depth > 0.01 {
                let am = 1.0
                    - am_depth
                        * (0.5 + 0.5 * (std::f64::consts::TAU * self.p.am_rate_hz * self.t).sin());
                v *= am as f32;
            }
            if breath > 0.0 {
                self.pink = a_pink_f32 * self.pink + self.rng.standard_normal();
                v += breath as f32 * self.pink * pink_gain;
            }

            // Level last, so a fade takes the breath and the buzz with it, and a soft clip
            // rather than a hard one: the static gain cannot know what the AM will add.
            *sample = (v * self.level as f32).tanh();
            self.t += dt;
        }
    }

    /// Harmonic weights at the current `open`, and the gain that keeps their sum in range.
    fn refresh_weights(&mut self) {
        let mut p = self.p;
        // A wider mouth is a shallower rolloff. Floored, so an extreme personality tilt
        // plus a wide mouth cannot invert into a weight set with no fundamental.
        p.tilt = (p.tilt - OPEN_TILT_LIFT * self.open.clamp(0.0, 1.0)).max(0.8);
        // The vowel moves the formant along the series. Rounded, because `harmonics` boosts
        // one whole harmonic and there is nothing between them to boost.
        p.formant_n =
            ((p.formant_n as f64 + self.formant_shift).round() as i64).clamp(1, 7) as usize;
        self.weights = p.harmonics();
        self.weights_open = self.open;
        self.weights_formant = self.formant_shift;
        self.weights_freq = self.freq;

        // The gain is set from the weights **before** the rolloff touches them. It used to be
        // set after — which silently renormalised whatever the rolloff had removed straight
        // back in, making `MAX_BASS_LIFT` a no-op and every deep note exactly as loud as a
        // high one, with all of that loudness piled onto the few harmonics the driver keeps.
        // Anchoring the gain first means the rolloff genuinely costs a deep note level, the
        // lift genuinely gives some back, and the cap genuinely caps it.
        let sum: f64 = self.weights.iter().sum();
        self.gain = PEAK / (sum.max(1e-6) as f32);
        self.breath_rolloff = 1.0;

        if let Some(rolloff) = self.speaker_rolloff_hz {
            // What the driver does to each harmonic, as a plain amplitude factor. Above the
            // rolloff it does nothing; below, the response falls at `ROLLOFF_DB_PER_OCTAVE`.
            let exponent = ROLLOFF_DB_PER_OCTAVE / 6.0206;
            let before: f64 = self.weights.iter().sum();
            for (n, weight) in self.weights.iter_mut().enumerate() {
                let harmonic_hz = self.freq * (n + 1) as f64;
                let response = (harmonic_hz / rolloff).min(1.0).powf(exponent);
                *weight *= response;
            }
            // Give back some of what was taken — so the note keeps most of its loudness while
            // its *balance* moves to harmonics the driver can make. Clamped: a note whose whole
            // series is under the rolloff has nothing to give it to, and must stay quiet
            // rather than become distortion.
            let after: f64 = self.weights.iter().sum();
            if after > 1e-9 {
                let lift = (before / after).min(MAX_BASS_LIFT);
                for weight in &mut self.weights {
                    *weight *= lift;
                }
                // The breath loses what the voice lost: noise is broadband and the driver
                // keeps it, so an uncut breath would leave the quietest notes the noisiest.
                self.breath_rolloff = (after * lift / before).clamp(0.0, 1.0);
            }
        }
    }
}

/// A duck's playable range, in hertz, low to high.
///
/// Anchored on the personality rather than fixed: a low duck plays low. The span is the
/// wheee's own — up to `top` times centre — so the theremin never asks the voice for a pitch
/// its recipes would not have used.
///
/// Free-standing, not only a [`Stream`] method, because the caller that needs to *map* a
/// distance to a note is not the one holding the stream: `robotd` computes the note in its
/// control loop and hands the stream a frequency, the stream itself having been moved into
/// the thread that renders it.
pub fn range_hz(p: &Personality) -> (f64, f64) {
    let lo = p.pitch_center_hz * 0.85;
    let top = 1.6 + 0.5 * p.pitch_spread;
    (lo, p.pitch_center_hz * top)
}

/// Frequency for a 0..1 position in [`range_hz`], geometric in the parameter.
///
/// Pitch perception is logarithmic, so a linear map from distance to hertz crowds every
/// interesting interval into the near end. Linear-in-semitones is what makes the far half of
/// the sweep playable at all.
pub fn hz_at(p: &Personality, position: f64) -> f64 {
    let (lo, hi) = range_hz(p);
    lo * (hi / lo).powf(position.clamp(0.0, 1.0))
}

/// One-pole coefficient for a time constant, at [`SR`].
fn pole(tau_s: f64) -> f64 {
    1.0 - (-1.0 / (tau_s * f64::from(SR))).exp()
}

/// A pitch offset in semitones, as a frequency multiplier.
fn semitones(offset: f64) -> f64 {
    if offset == 0.0 {
        return 1.0;
    }
    2.0f64.powf(offset / 12.0)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn render(s: &mut Stream, n: usize) -> Vec<f32> {
        let mut out = vec![0.0; n];
        s.block(&mut out);
        out
    }

    /// The property the whole design rests on: block boundaries are not in the signal.
    /// One block of N samples and K blocks summing to N must be the same audio, or the
    /// audio sink's buffer size would be audible.
    #[test]
    fn block_size_does_not_change_the_signal() {
        let p = Personality::from_seed(100);
        let mut a = Stream::wheee(&p, 0);
        a.set(300.0, 1.0, 0.5);
        let whole = render(&mut a, 4800);

        let mut b = Stream::wheee(&p, 0);
        b.set(300.0, 1.0, 0.5);
        let mut split = Vec::new();
        for chunk in [1usize, 7, 480, 1024, 3288] {
            split.extend(render(&mut b, chunk));
        }

        assert_eq!(whole.len(), split.len());
        for (i, (x, y)) in whole.iter().zip(&split).enumerate() {
            assert!((x - y).abs() < 1e-6, "sample {i}: {x} vs {y}");
        }
    }

    /// A long ride must stay finite and in range — the phase wrap and the soft clip are
    /// both load-bearing for that, and a theremin is held for minutes.
    #[test]
    fn a_long_ride_stays_finite_and_bounded() {
        for seed in [0u32, 100, 3_405_691_582] {
            let p = Personality::from_seed(seed);
            let mut s = Stream::wheee(&p, 0);
            // Sweep the whole range while rendering ~10 s.
            for i in 0..200 {
                let pos = f64::from(i % 100) / 100.0;
                s.set(s.hz_at(pos), 1.0, pos);
                let block = render(&mut s, 2400);
                assert!(
                    block.iter().all(|v| v.is_finite() && v.abs() <= 1.0),
                    "seed {seed} block {i}"
                );
            }
        }
    }

    /// Level 0 is silence, and going to it and back is a fade rather than a step — no
    /// click when a hand leaves the frame or re-enters it.
    #[test]
    fn keying_the_level_fades_instead_of_clicking() {
        let p = Personality::from_seed(100);
        let mut s = Stream::wheee(&p, 0);
        s.set(300.0, 1.0, 0.0);
        let loud = render(&mut s, 9600);
        let peak = loud.iter().fold(0.0f32, |m, &v| m.max(v.abs()));
        assert!(peak > 0.1, "a keyed voice must be audible, peak {peak}");

        s.set(300.0, 0.0, 0.0);
        let fading = render(&mut s, 24_000);
        // The step between adjacent samples bounds a click; a gated cut would show one
        // the size of the signal itself.
        let step = fading
            .windows(2)
            .fold(0.0f32, |m, w| m.max((w[1] - w[0]).abs()));
        assert!(step < 0.15, "fade step {step} looks like a click");
        let tail = fading[fading.len() - 480..]
            .iter()
            .fold(0.0f32, |m, &v| m.max(v.abs()));
        assert!(tail < 1e-3, "the fade must reach silence, tail {tail}");
        assert!(s.is_silent());
    }

    /// The mouth must actually change the timbre, not just move the servo: an open mouth
    /// puts more energy into the harmonics above the fundamental. Measured by projecting
    /// the block onto the 2nd and 3rd harmonics and comparing against the 1st.
    #[test]
    fn an_open_mouth_is_brighter() {
        let p = Personality::from_seed(100);
        let harmonic_ratio = |open: f64| {
            let mut s = Stream::wheee(&p, 0);
            s.set(300.0, 1.0, open);
            // Let every slew settle before measuring.
            render(&mut s, 48_000);
            let block = render(&mut s, 48_000);
            // Magnitude at n * 300 Hz, by quadrature projection.
            let magnitude = |n: f64| {
                let (mut re, mut im) = (0.0f64, 0.0f64);
                for (i, &v) in block.iter().enumerate() {
                    let ph = std::f64::consts::TAU * n * 300.0 * i as f64 / f64::from(SR);
                    re += f64::from(v) * ph.cos();
                    im += f64::from(v) * ph.sin();
                }
                (re * re + im * im).sqrt()
            };
            (magnitude(2.0) + magnitude(3.0)) / magnitude(1.0).max(1e-9)
        };
        let closed = harmonic_ratio(0.0);
        let open = harmonic_ratio(1.0);
        assert!(
            open > closed * 1.1,
            "an open mouth must be brighter: upper/f0 {closed} -> {open}"
        );
    }

    /// The bass fix, and it has to be checked the way the ear works rather than the way a level
    /// meter does: the compensation must move energy *above* the speaker's rolloff while leaving
    /// the harmonic spacing — and so the perceived pitch — exactly where it was.
    #[test]
    fn a_speaker_rolloff_moves_the_bass_into_the_harmonics() {
        const F0: f64 = 130.81; // C3, the shipped score's bass
        const ROLLOFF: f64 = 300.0;
        let p = Personality::from_seed(100);

        // Energy at n * F0, and the total below the rolloff, for a settled note.
        let measure = |rolloff: Option<f64>| {
            let mut s = Stream::choral(&p, 0);
            s.set_speaker_rolloff(rolloff);
            s.set(F0, 1.0, 0.6);
            let mut block = vec![0.0f32; 48_000];
            s.block(&mut block);
            s.block(&mut block);
            let magnitude = |hz: f64| {
                let (mut re, mut im) = (0.0f64, 0.0f64);
                for (i, &v) in block.iter().enumerate() {
                    let ph = std::f64::consts::TAU * hz * i as f64 / f64::from(SR);
                    re += f64::from(v) * ph.cos();
                    im += f64::from(v) * ph.sin();
                }
                (re * re + im * im).sqrt() / block.len() as f64
            };
            let harmonics: Vec<f64> = (1..=6).map(|n| magnitude(F0 * n as f64)).collect();
            let below: f64 = harmonics
                .iter()
                .enumerate()
                .filter(|(n, _)| (F0 * (n + 1) as f64) < ROLLOFF)
                .map(|(_, m)| m)
                .sum();
            let above: f64 = harmonics
                .iter()
                .enumerate()
                .filter(|(n, _)| (F0 * (n + 1) as f64) >= ROLLOFF)
                .map(|(_, m)| m)
                .sum();
            (harmonics, below, above)
        };

        let (plain, plain_below, plain_above) = measure(None);
        let (lifted, lifted_below, lifted_above) = measure(Some(ROLLOFF));

        // Less under the rolloff, more over it — the trade the whole thing is.
        assert!(
            lifted_below < plain_below * 0.8,
            "energy below {ROLLOFF} Hz barely moved: {plain_below} -> {lifted_below}"
        );
        assert!(
            lifted_above > plain_above * 1.2,
            "energy above {ROLLOFF} Hz barely moved: {plain_above} -> {lifted_above}"
        );
        // The pitch is unchanged, because it never lived in the fundamental: the series is still
        // spaced F0 apart, with every harmonic still present.
        for (n, magnitude) in lifted.iter().enumerate() {
            assert!(
                *magnitude > 0.0,
                "harmonic {} vanished, which would change the perceived pitch",
                n + 1
            );
        }
        // And it is a rebalance, not a volume knob: the note is not wildly louder overall.
        let plain_total: f64 = plain.iter().sum();
        let lifted_total: f64 = lifted.iter().sum();
        assert!(
            (lifted_total / plain_total) < 2.0,
            "the note got {:.1}x louder, which is a gain and not a rebalance",
            lifted_total / plain_total
        );
    }

    /// The breath at the scale the offline voice has — the streamed version was five times
    /// louder (a guessed constant where the integrator's steady-state deviation of ~8.5
    /// belonged), reported from the robot as a bass full of white noise.
    ///
    /// Measured by differencing against a zero-breath twin of the same personality, because a
    /// first-order high-pass cannot separate noise from harmonics — everything else about the
    /// two renders is identical, so what the breath adds in the band above the harmonics is
    /// the noise alone.
    #[test]
    fn the_breath_is_a_whisper_and_not_a_hiss() {
        // The breathiest personality in the first few hundred seeds, so the bound is tested
        // where the bug was audible.
        let breathiest = (0..500u32)
            .map(Personality::from_seed)
            .max_by(|a, b| a.breath.partial_cmp(&b.breath).expect("finite"))
            .expect("seeds");
        let mut silent_twin = breathiest;
        silent_twin.breath = 0.0;

        let high_band_rms = |p: &Personality| {
            let mut s = Stream::choral(p, 0);
            s.set(261.6, 1.0, 0.6);
            let mut block = vec![0.0f32; 48_000];
            s.block(&mut block);
            s.block(&mut block);
            let alpha = (-std::f64::consts::TAU * 4_000.0 / f64::from(SR)).exp() as f32;
            let (mut low, mut energy, mut total) = (0.0f32, 0.0f64, 0.0f64);
            for &v in &block {
                low = alpha * low + (1.0 - alpha) * v;
                let high = v - low;
                energy += f64::from(high) * f64::from(high);
                total += f64::from(v) * f64::from(v);
            }
            let n = block.len() as f64;
            ((energy / n).sqrt(), (total / n).sqrt())
        };
        let (with_breath, body) = high_band_rms(&breathiest);
        let (leakage, _) = high_band_rms(&silent_twin);
        // The noise is what the breath added over the twin's harmonic leakage.
        let noise = (with_breath * with_breath - leakage * leakage)
            .max(0.0)
            .sqrt();
        assert!(
            noise < body * 0.05,
            "breath noise {noise:.4} against a body of {body:.4} — the hiss is back"
        );
        // And it is not silence either: a duck with no breath at all is a different voice.
        assert!(
            noise > body * 0.001,
            "{noise:.5} — the breath vanished entirely"
        );
    }

    /// The speaker rolloff's lift cap genuinely caps now. It used to be renormalised straight
    /// back out — a note off the bottom of the driver came back exactly as loud as any other,
    /// all of it piled into the few harmonics the driver keeps, which is the saturation the
    /// robot run reported.
    #[test]
    fn the_bass_lift_cap_actually_caps() {
        let p = Personality::from_seed(100);
        let rms_at = |hz: f64, rolloff: Option<f64>| {
            let mut s = Stream::choral(&p, 0);
            s.set_speaker_rolloff(rolloff);
            s.set(hz, 1.0, 0.6);
            let mut block = vec![0.0f32; 48_000];
            s.block(&mut block);
            s.block(&mut block);
            (block
                .iter()
                .map(|v| f64::from(*v) * f64::from(*v))
                .sum::<f64>()
                / block.len() as f64)
                .sqrt()
        };
        // A moderately deep note (the chorale's bass range) keeps its loudness: the lift
        // restores what the driver takes, inside the cap. That is the design, not a bug —
        // only the *balance* moves.
        let plain = rms_at(130.8, None);
        let through = rms_at(130.8, Some(300.0));
        assert!(
            through < plain * 1.1,
            "{through} vs {plain}: louder through a rolloff?"
        );
        assert!(
            through > plain * 0.5,
            "{through} vs {plain}: the bass vanished"
        );
        // A note far below the driver hits the cap and is genuinely quieter — the case the
        // cap exists for, and the assertion the old renormalisation failed.
        let deep_plain = rms_at(55.0, None);
        let deep_through = rms_at(55.0, Some(300.0));
        assert!(
            deep_through < deep_plain * 0.8,
            "{deep_through} vs {deep_plain}: the cap is being renormalised away again"
        );
        // A note above the rolloff is untouched.
        let high_plain = rms_at(500.0, None);
        let high_through = rms_at(500.0, Some(300.0));
        assert!(
            (high_through / high_plain) > 0.9,
            "{high_through} vs {high_plain}"
        );
    }

    /// A note the driver cannot make at all must stay quiet rather than become distortion: there is
    /// nothing to redistribute to, so the lift is clamped.
    #[test]
    fn a_note_below_everything_is_not_amplified_into_distortion() {
        let p = Personality::from_seed(100);
        let mut s = Stream::choral(&p, 0);
        // A rolloff above the whole seven-harmonic series of a 40 Hz note.
        s.set_speaker_rolloff(Some(2000.0));
        s.set(40.0, 1.0, 0.5);
        let mut block = vec![0.0f32; 24_000];
        s.block(&mut block);
        s.block(&mut block);
        assert!(block.iter().all(|v| v.is_finite() && v.abs() <= 1.0));
    }

    /// The pitch map must be geometric and anchored on the duck: the same interval for the
    /// same step in position, wherever in the sweep it is taken.
    #[test]
    fn the_pitch_map_is_linear_in_semitones() {
        let p = Personality::from_seed(100);
        let s = Stream::wheee(&p, 0);
        let (lo, hi) = s.range_hz();
        assert!((s.hz_at(0.0) - lo).abs() < 1e-9);
        assert!((s.hz_at(1.0) - hi).abs() < 1e-9);
        let ratio = |a: f64, b: f64| s.hz_at(b) / s.hz_at(a);
        assert!((ratio(0.0, 0.25) - ratio(0.5, 0.75)).abs() < 1e-9);
        // Out-of-range positions clamp rather than run off.
        assert_eq!(s.hz_at(-1.0), lo);
        assert_eq!(s.hz_at(2.0), hi);
    }

    /// Two seeds are two instruments, and the range follows the duck's own register — the
    /// theremin must not flatten every duck onto one scale.
    #[test]
    fn the_range_follows_the_personality() {
        let a = Stream::wheee(&Personality::from_seed(100), 0).range_hz();
        let b = Stream::wheee(&Personality::from_seed(101), 0).range_hz();
        assert_ne!(a, b);
        for seed in 0..200u32 {
            let (lo, hi) = Stream::wheee(&Personality::from_seed(seed), 0).range_hz();
            assert!(
                lo > 50.0 && hi > lo && hi < 3000.0,
                "seed {seed}: {lo}..{hi}"
            );
        }
    }
}

//! Several ducks singing one thing: the score, who sings what, and the mix.
//!
//! This module is the *musical* half of the duck chorale, and it is deliberately separate from
//! the half that will be hard on real hardware (finding each other, agreeing on a clock). It
//! renders an ensemble offline, on a laptop, so the arrangement can be judged before a single
//! packet is sent between two ducks — and so that when the sync work starts, "does it sound
//! good" is already answered and only "is it together" is in question.
//!
//! ## Identity is timbre, not pitch
//!
//! Every duck's voice is derived from its SoC serial, and the loudest thing that varies is
//! [`Personality::pitch_center_hz`] — a duck is high or low. Letting that shift the *notes*
//! would be the obvious way to keep each duck sounding like itself, and it would wreck the
//! piece: four ducks singing a chord each in their own tuning is four ducks out of tune with
//! each other. Beating, not harmony.
//!
//! So the note is absolute, from one shared reference ([`A4_HZ`], equal temperament), and what
//! each duck keeps is everything else: harmonic weights, formant, nasality, breath, and the
//! tamed remains of its vibrato ([`Stream::choral`]). Register is used instead for **casting**
//! — the lowest duck sings bass — and for choosing what key the piece lands in, so nobody is
//! asked to sing outside the range their own voice was rolled for.
//!
//! ## Why a perfectly synchronised chorus is the wrong target
//!
//! Four voices starting a note on the same sample and holding the same frequency do not sound
//! like a choir; they sound like one organ with a thick stop. What makes an ensemble is that
//! its members are *almost* together and *almost* in tune: a few cents of pitch spread and a
//! few tens of milliseconds of onset spread. Both are added here on purpose, derived from each
//! duck's seed so a given group always sounds like that group ([`Singer::detune_cents`],
//! [`Singer::onset_offset_s`]).
//!
//! That is also the answer to how tightly real ducks will have to agree on a clock: the target
//! is ±20 ms, not ±1 ms, because ±15 ms is what we are deliberately adding. A chord's *tuning*
//! is what has to be exact, and that needs no synchronisation at all — only a shared reference
//! pitch, which is a constant.

pub mod beat;
pub mod midi;
pub mod text;

use crate::personality::Personality;
use crate::stream::Stream;
use crate::synth::SR;

/// The reference the whole ensemble tunes to. A constant, which is the point: tuning needs no
/// agreement at run time, only the same number compiled into every duck.
pub const A4_HZ: f64 = 440.0;

/// The four parts, low to high. `as usize` indexes a [`Chord`]'s voicing.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum Part {
    Bass,
    Tenor,
    Alto,
    Soprano,
}

impl Part {
    pub const ALL: [Part; 4] = [Part::Bass, Part::Tenor, Part::Alto, Part::Soprano];

    pub fn as_str(&self) -> &'static str {
        match self {
            Part::Bass => "bass",
            Part::Tenor => "tenor",
            Part::Alto => "alto",
            Part::Soprano => "soprano",
        }
    }

    /// Roughly where this part sits, as a MIDI number — the middle of the range the shipped
    /// voicings keep it inside. Used to seat a duck in the part nearest its own register.
    pub fn register(&self) -> f64 {
        match self {
            Part::Bass => 51.0,
            Part::Tenor => 58.0,
            Part::Alto => 63.0,
            Part::Soprano => 68.0,
        }
    }

    /// Which parts an ensemble of `n` ducks sings.
    ///
    /// Not simply the lowest `n`: a chord needs its outer voices most, so a duet is bass and
    /// soprano — melody over a bass line — rather than bass and tenor, which would be two
    /// ducks muttering in the same octave. A trio drops the tenor, the voice whose notes are
    /// most often doubled elsewhere in the chord.
    ///
    /// **These sets are nested**, and that is load-bearing rather than incidental:
    /// `{S} ⊂ {B,S} ⊂ {B,A,S} ⊂ {B,T,A,S}`. It is what makes a duck able to join a group that
    /// is already singing without anyone changing part — there is always exactly one free
    /// part to take. See [`seat`].
    pub fn ensemble(n: usize) -> Vec<Part> {
        match n {
            0 => Vec::new(),
            1 => vec![Part::Soprano],
            2 => vec![Part::Bass, Part::Soprano],
            3 => vec![Part::Bass, Part::Alto, Part::Soprano],
            _ => Part::ALL.to_vec(),
        }
    }
}

/// One part's note: which voice, when it enters, how long it holds.
///
/// The flat form everything downstream reads. [`Gesture`] is what a score is *written* in;
/// this is what it compiles to.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Note {
    pub part: Part,
    pub start_beat: f64,
    pub beats: f64,
    pub midi: u8,
    /// How loud, 0..1. A chorale that does not swell is flat, and this is where the swell
    /// lives — one value per note, since a note is the smallest thing anyone marks.
    pub level: f64,
    /// What is being sung on it. Ducks cannot pronounce words, but a vowel is most of what a
    /// listener hears as singing rather than humming — see [`Vowel`].
    pub vowel: Vowel,
}

impl Note {
    pub fn end_beat(&self) -> f64 {
        self.start_beat + self.beats
    }
}

/// A sung vowel: a mouth opening and a formant position.
///
/// Not phonetics — the synth has no vocal tract, only a boost on one harmonic of seven. But
/// `oo` and `ee` are unmistakably different sounds even at that resolution, and having the
/// ensemble move between them is the difference between four voices singing and four voices
/// humming. The mouth opening is the *same number* the beak servo gets, so the vowel is
/// visible as well as audible.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum Vowel {
    /// Full and open. The default, and what a chord wants when it lands.
    #[default]
    Ah,
    Eh,
    /// Bright and narrow.
    Ee,
    Oh,
    /// Dark and closed. The pad under a solo.
    Oo,
    /// A closed hum, quieter than the rest — a real choir's way of holding a chord without
    /// occupying the foreground.
    Mm,
}

impl Vowel {
    /// How far the beak opens on it, 0..1.
    /// Phonetically honest values were tried and looked broken on the robot: the shipped
    /// piece opens with six beats of `oo`, and an `oo` of 0.15 is a duck audibly singing
    /// through a closed beak. These are stage vowels — exaggerated open, ordered the same —
    /// because on a robot the mouth is *performance* first and phonetics second. Only the
    /// hum stays closed: humming through a shut beak is correct, and rather charming.
    pub fn open(&self) -> f64 {
        match self {
            Vowel::Ah => 0.90,
            Vowel::Eh => 0.65,
            Vowel::Ee => 0.45,
            Vowel::Oh => 0.55,
            Vowel::Oo => 0.35,
            Vowel::Mm => 0.05,
        }
    }

    /// Where it puts the formant, in harmonics relative to this duck's own.
    pub fn formant_shift(&self) -> f64 {
        match self {
            Vowel::Ah => 0.0,
            Vowel::Eh => 1.0,
            Vowel::Ee => 3.0,
            Vowel::Oh => -1.0,
            Vowel::Oo => -2.0,
            Vowel::Mm => -2.0,
        }
    }

    /// A hum sits back in the mix; everything else sings at its written dynamic.
    pub fn level_scale(&self) -> f64 {
        match self {
            Vowel::Mm => 0.65,
            _ => 1.0,
        }
    }

    pub fn as_str(&self) -> &'static str {
        match self {
            Vowel::Ah => "ah",
            Vowel::Eh => "eh",
            Vowel::Ee => "ee",
            Vowel::Oh => "oh",
            Vowel::Oo => "oo",
            Vowel::Mm => "mm",
        }
    }

    /// Parse a vowel name. Used by the text score format and by nothing else.
    pub fn parse(word: &str) -> Option<Self> {
        Some(match word.to_ascii_lowercase().as_str() {
            "ah" | "a" => Vowel::Ah,
            "eh" | "e" => Vowel::Eh,
            "ee" | "i" => Vowel::Ee,
            "oh" | "o" => Vowel::Oh,
            "oo" | "u" => Vowel::Oo,
            "mm" | "m" | "hum" => Vowel::Mm,
            _ => return None,
        })
    }
}

/// The classical dynamic marks, as levels.
///
/// A named ramp rather than raw numbers in the score, because `mf` is what anyone writing
/// music actually means, and because the mapping wants to be one decision in one place.
pub fn dynamic(mark: &str) -> Option<f64> {
    Some(match mark.to_ascii_lowercase().as_str() {
        "ppp" => 0.15,
        "pp" => 0.25,
        "p" => 0.40,
        "mp" => 0.55,
        "mf" => 0.70,
        "f" => 0.85,
        "ff" => 1.00,
        _ => return None,
    })
}

/// A voicing with a tacet voice allowed: `None` is a part that does not sing here.
pub type Voicing = [Option<u8>; 4];

/// Four voices in unison rhythm — the plain block chord.
///
/// A test convenience. Real scores arrive as text ([`text`]) or MIDI ([`midi`]), which is the
/// whole point of those two modules; nothing in the shipped path writes a voicing in Rust.
#[cfg(test)]
fn chord(bass: u8, tenor: u8, alto: u8, soprano: u8) -> Voicing {
    [Some(bass), Some(tenor), Some(alto), Some(soprano)]
}

/// One note of a solo line.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct SoloNote {
    pub midi: u8,
    pub beats: f64,
    pub vowel: Vowel,
}

/// A gesture a score is written in.
///
/// Not a list of block chords, which is where this started and which can only write one kind
/// of music: a real chorale breathes, assembles chords from below, and drops to one voice.
/// Each variant is a gesture an arranger actually thinks in, and they compile down to per-part
/// [`Note`]s — so a hand-written score reads as musical intent rather than as a table of
/// simultaneities.
///
/// This is one *front end*, not the score itself. [`Score`] holds notes, because the other way
/// in is a MIDI file ([`crate::chorale::midi`]) where staggered entries and solos are already
/// expressed as plain note timings and there are no gestures to recover.
#[derive(Debug, Clone, PartialEq)]
pub enum Gesture {
    /// Everyone together, one duration. The homophonic tread.
    Chord {
        voicing: Voicing,
        beats: f64,
        vowel: Vowel,
        level: f64,
    },
    /// Voices enter one at a time, `stagger` beats apart, and each holds to the end of the
    /// gesture — so the chord *assembles* and is then sustained whole.
    ///
    /// The single most effective thing a group of singers can do that a keyboard cannot, and
    /// on hardware it is also the most forgiving: a chord whose entries are deliberately
    /// half a second apart does not care whether two ducks disagree by 20 ms.
    Build {
        voicing: Voicing,
        beats: f64,
        stagger: f64,
        /// Enter from the top voice down instead of the bass up.
        from_top: bool,
        vowel: Vowel,
        level: f64,
    },
    /// One voice moves while the others hold a chord under it.
    ///
    /// The gesture lasts as long as the solo line does. Parts left `None` in `under` are silent
    /// for it — a solo over nothing at all is `under: [None; 4]`, which is what a genuinely
    /// unaccompanied entry is. The accompaniment usually wants a different vowel from the
    /// soloist, which is what `under_vowel` is for: `mm` under an `ah` is a choir holding a
    /// chord behind someone.
    Solo {
        part: Part,
        notes: Vec<SoloNote>,
        under: Voicing,
        under_vowel: Vowel,
        level: f64,
    },
    /// Silence for everyone. A breath, and the thing that makes the chord after it land.
    Rest { beats: f64 },
}

impl Gesture {
    /// How many beats this gesture occupies.
    pub fn beats(&self) -> f64 {
        match self {
            Gesture::Chord { beats, .. } | Gesture::Build { beats, .. } => *beats,
            Gesture::Solo { notes, .. } => notes.iter().map(|n| n.beats).sum(),
            Gesture::Rest { beats } => *beats,
        }
    }
}

/// A four-part score: per-part notes, and the tempo to read them at.
///
/// **Notes, not gestures.** This is the load-bearing shape in the whole module. A hand-written
/// score comes in as [`Gesture`]s and a MuseScore export comes in as MIDI, and only one of
/// those has gestures to recover — so the two converge here, and everything downstream
/// (rendering, casting, the eventual sync) reads one thing.
#[derive(Debug, Clone, PartialEq)]
pub struct Score {
    pub name: String,
    pub bpm: f64,
    /// Sorted by part, then by start. No part overlaps itself.
    pub notes: Vec<Note>,
}

impl Score {
    /// Compile gestures into a score.
    ///
    /// Ties are merged: a voice holding the same pitch, vowel and dynamic across a gesture
    /// boundary comes out as **one** note, which is how part-writing works and audibly the
    /// difference between a chorale and a sequence of chords. A change of *vowel* on the same
    /// pitch does re-articulate, because that is what a singer does with a new syllable, and a
    /// [`Gesture::Rest`] breaks a tie by leaving a gap — which is the whole point of writing
    /// one.
    pub fn from_gestures(name: &str, bpm: f64, gestures: &[Gesture]) -> Self {
        let mut notes: Vec<Note> = Vec::new();
        let mut at = 0.0f64;
        for gesture in gestures {
            match gesture {
                Gesture::Chord {
                    voicing,
                    beats,
                    vowel,
                    level,
                } => {
                    for part in Part::ALL {
                        if let Some(midi) = voicing[part as usize] {
                            notes.push(Note {
                                part,
                                start_beat: at,
                                beats: *beats,
                                midi,
                                level: *level,
                                vowel: *vowel,
                            });
                        }
                    }
                }
                Gesture::Build {
                    voicing,
                    beats,
                    stagger,
                    from_top,
                    vowel,
                    level,
                } => {
                    let mut order: Vec<Part> = Part::ALL
                        .into_iter()
                        .filter(|p| voicing[*p as usize].is_some())
                        .collect();
                    if *from_top {
                        order.reverse();
                    }
                    for (seat, part) in order.into_iter().enumerate() {
                        let offset = seat as f64 * stagger;
                        // A stagger long enough to run past the gesture would give the last
                        // voice a negative-length note; it simply does not get in.
                        let held = beats - offset;
                        if held <= 0.0 {
                            continue;
                        }
                        notes.push(Note {
                            part,
                            start_beat: at + offset,
                            beats: held,
                            midi: voicing[part as usize].expect("filtered"),
                            level: *level,
                            vowel: *vowel,
                        });
                    }
                }
                Gesture::Solo {
                    part,
                    notes: line,
                    under,
                    under_vowel,
                    level,
                } => {
                    let total = gesture.beats();
                    for other in Part::ALL {
                        if other == *part {
                            continue;
                        }
                        if let Some(midi) = under[other as usize] {
                            notes.push(Note {
                                part: other,
                                start_beat: at,
                                beats: total,
                                midi,
                                level: *level,
                                vowel: *under_vowel,
                            });
                        }
                    }
                    let mut solo_at = at;
                    for note in line {
                        notes.push(Note {
                            part: *part,
                            start_beat: solo_at,
                            beats: note.beats,
                            midi: note.midi,
                            level: *level,
                            vowel: note.vowel,
                        });
                        solo_at += note.beats;
                    }
                }
                Gesture::Rest { .. } => {}
            }
            at += gesture.beats();
        }
        Self::from_notes(name, bpm, notes)
    }

    /// A score from a bare note list — the MIDI importer's way in, and the tie merge both
    /// paths share.
    pub fn from_notes(name: &str, bpm: f64, mut notes: Vec<Note>) -> Self {
        notes.sort_by(|a, b| {
            a.part.cmp(&b.part).then(
                a.start_beat
                    .partial_cmp(&b.start_beat)
                    .expect("beats are finite"),
            )
        });
        let mut tied: Vec<Note> = Vec::new();
        for note in notes {
            match tied.last_mut() {
                // Pitch and vowel, but deliberately *not* the dynamic: a mark that arrives
                // over a note already sounding is a crescendo, and re-attacking the note
                // would be the one thing a crescendo is not. A tied note keeps the dynamic it
                // began on, so a mark applies to whatever *starts* after it — and an arranger
                // who wants the note sung again writes a rest or a new vowel, both of which do
                // break the tie.
                Some(previous)
                    if previous.part == note.part
                        && previous.midi == note.midi
                        && previous.vowel == note.vowel
                        // Contiguous, within a rounding error of a beat boundary.
                        && (note.start_beat - previous.end_beat()).abs() < 1e-6 =>
                {
                    previous.beats += note.beats;
                }
                _ => tied.push(note),
            }
        }
        Self {
            name: name.to_owned(),
            bpm,
            notes: tied,
        }
    }

    /// The default piece: an original arrangement, ours to ship.
    ///
    /// Parsed from `scores/wistful.duckscore`, embedded — deliberately the same text file that
    /// ships as the worked example, so the example cannot drift from the thing it is an example
    /// of. If it stops parsing, the tests say so.
    pub fn wistful() -> Self {
        text::parse(include_str!("../../scores/wistful.duckscore"))
            .expect("the embedded default score must parse")
    }

    /// TEST ONLY — an arrangement of Andrew Prahlow's Outer Wilds theme, for bench and living
    /// room. **Remove before anything ships**: unlike [`Score::wistful`] and
    /// [`Score::duck_strut`], which are original precisely because everything this idiom
    /// evokes is in copyright, this one *is* the copyrighted piece. It exists to exercise the
    /// piece registry with music people recognise; it must not ride a release.
    pub fn outer_wilds() -> Self {
        let mut score = midi::parse(include_bytes!("../../scores/outer_wilds.mid"))
            .expect("the embedded MIDI score must parse")
            .score;
        score.name = "outer-wilds".to_owned();
        score
    }

    /// The other piece: an upbeat one, through the MIDI front end.
    ///
    /// `scores/duck_strut.mid` is the source of truth and is deliberately a *MIDI file in the
    /// repo* rather than more Rust or another text score: it opens in MuseScore, and editing
    /// the arrangement there and committing the export is the whole workflow the importer was
    /// built for. D major, 126 bpm, an oom-pah bass, tenor backbeats, and a middle section
    /// where the tenor echoes the soprano an octave down — everything the wistful chorale
    /// is not, including per-voice rhythm the text format cannot write.
    pub fn duck_strut() -> Self {
        let mut score = midi::parse(include_bytes!("../../scores/duck_strut.mid"))
            .expect("the embedded MIDI score must parse")
            .score;
        score.name = "duck-strut".to_owned();
        score
    }

    /// Seconds per beat.
    pub fn beat_s(&self) -> f64 {
        60.0 / self.bpm.max(1.0)
    }

    /// How long the piece runs, seconds — to the end of the last note.
    pub fn duration_s(&self) -> f64 {
        self.notes.iter().map(|n| n.end_beat()).fold(0.0, f64::max) * self.beat_s()
    }

    /// One part's notes, in order.
    pub fn line(&self, part: Part) -> impl Iterator<Item = &Note> {
        self.notes.iter().filter(move |n| n.part == part)
    }

    /// The mean MIDI pitch of one part, weighted by how long each note is held — what "where
    /// does this part sit" has to mean when the notes are not equal length.
    pub fn mean_pitch(&self, part: Part) -> f64 {
        let beats: f64 = self.line(part).map(|n| n.beats).sum();
        if beats <= 0.0 {
            return 0.0;
        }
        self.line(part)
            .map(|n| f64::from(n.midi) * n.beats)
            .sum::<f64>()
            / beats
    }

    /// Which parts actually sing in this score.
    pub fn parts(&self) -> Vec<Part> {
        Part::ALL
            .into_iter()
            .filter(|p| self.line(*p).next().is_some())
            .collect()
    }
}

/// One duck in the ensemble.
#[derive(Debug, Clone)]
pub struct Singer {
    pub personality: Personality,
    pub part: Part,
    /// Pitch offset, cents. A few cents of spread is what makes four voices a choir rather
    /// than one thick organ stop. Derived from the seed, so a group sounds like that group.
    pub detune_cents: f64,
    /// How early or late this duck takes each note, seconds. Same reasoning as the detune, and
    /// the reason the eventual clock sync needs ±20 ms rather than ±1 ms.
    pub onset_offset_s: f64,
}

/// Cast an ensemble: lowest duck sings the lowest part.
///
/// Deterministic from the personalities alone, and that is worth more than it looks — it means
/// real ducks can agree on who sings what *without negotiating*, from a list of seeds they
/// already exchange. No leader has to assign parts.
pub fn cast(personalities: &[Personality]) -> Vec<Singer> {
    let parts = Part::ensemble(personalities.len());
    let mut order: Vec<usize> = (0..personalities.len()).collect();
    // By register, then by seed — the tie-break matters only for two ducks rolled to the same
    // pitch centre, and without it their parts could swap between runs.
    order.sort_by(|&a, &b| {
        personalities[a]
            .pitch_center_hz
            .partial_cmp(&personalities[b].pitch_center_hz)
            .expect("pitch centres are finite")
            .then(personalities[a].seed.cmp(&personalities[b].seed))
    });

    let mut singers: Vec<Option<Singer>> = vec![None; personalities.len()];
    for (rank, &index) in order.iter().enumerate() {
        let personality = personalities[index];
        let mut rng = personality.variant_rng("chorale-seat", rank as u32);
        singers[index] = Some(Singer {
            part: parts[rank.min(parts.len().saturating_sub(1))],
            detune_cents: rng.uniform(-5.0, 5.0),
            onset_offset_s: rng.uniform(-0.015, 0.015),
            personality,
        });
    }
    singers.into_iter().flatten().collect()
}

/// Seat one more duck alongside a group that is already singing.
///
/// **Nobody already singing changes part.** That is the whole point, and the alternative is
/// audibly bad: [`cast`] sorts by register, so a low duck arriving at a duet would take the
/// bass and shove the current bass up to alto — a part change in the middle of a piece. So a
/// joiner takes what is free, and because [`Part::ensemble`]'s sets are nested there is always
/// exactly one free part until the fourth duck has arrived.
///
/// Still decided by every duck independently, with nothing negotiated: the join order is what
/// each duck observed, and they all observed the same beacon.
///
/// Past four, the parts double up here — which is what a real choir does with more singers than
/// lines, and the doubling duck takes the part nearest its own register. Note that the *radio* does
/// not currently reach that: `ChoraleBeacon::MAX_ROSTER` is four, so a fifth duck in a real room
/// listens rather than joining. Doubling is reachable only by a caller that seats an ensemble
/// itself, such as the offline render.
pub fn seat(existing: &[Singer], newcomer: &Personality) -> Singer {
    let held: Vec<Part> = existing.iter().map(|s| s.part).collect();
    let part = seat_by_register(&held, newcomer.pitch_center_hz);
    // The seat number is what varies the detune and the onset, and it has to be stable for this
    // duck — so it is how many were already singing, not a re-roll of the whole group.
    let mut rng = newcomer.variant_rng("chorale-seat", existing.len() as u32);
    Singer {
        part,
        detune_cents: rng.uniform(-5.0, 5.0),
        onset_offset_s: rng.uniform(-0.015, 0.015),
        personality: *newcomer,
    }
}

/// The part a duck of this register takes, given the parts already held.
///
/// The register-only form of [`seat`], and the one the radio uses: a beacon carries a quantised
/// pitch centre and not a seed, because that is all seating consumes.
pub fn seat_by_register(held: &[Part], pitch_center_hz: f64) -> Part {
    let wanted = Part::ensemble(held.len() + 1);
    let free: Vec<Part> = wanted
        .iter()
        .copied()
        .filter(|part| !held.contains(part))
        .collect();
    // Where this duck's voice sits, as a MIDI number, so "nearest part" means something.
    let register = 69.0 + 12.0 * (pitch_center_hz / A4_HZ).log2();
    let choices = if free.is_empty() { &wanted } else { &free };
    choices
        .iter()
        .copied()
        .min_by(|a, b| {
            (a.register() - register)
                .abs()
                .partial_cmp(&(b.register() - register).abs())
                .expect("registers are finite")
                .then(a.cmp(b))
        })
        .unwrap_or(Part::Soprano)
}

/// The spread one duck brings to an ensemble: a few cents and a few milliseconds.
///
/// Split out from [`seat`] because a duck singing on real hardware learns its *part* from the
/// conductor's roster rather than by seating itself, and still needs its own detune and onset — the
/// two things that make four voices a choir rather than one thick organ stop. Derived from the seed
/// and the part, so a given duck always brings the same spread to the same line.
pub fn seat_for(personality: &Personality, part: Part) -> Singer {
    let mut rng = personality.variant_rng("chorale-seat", part as u32);
    Singer {
        part,
        detune_cents: rng.uniform(-5.0, 5.0),
        onset_offset_s: rng.uniform(-0.015, 0.015),
        personality: *personality,
    }
}

/// Every duck's part, from a roster of registers — the roster's own order in, parts out.
///
/// **This is what stops two ducks singing each other's line.** A duck that seats itself from
/// whatever it happens to have heard disagrees with a duck that heard a different subset, and the
/// two then both sing alto. So the *conductor* keeps the roster, broadcasts it, and everyone
/// replays this function over it: one source of truth, which is what a conductor is for.
///
/// **By register, not by roster position.** This was a fold of [`seat_by_register`] down the roster
/// in join order, which preserved a lovely invariant — a duck joining moved nobody — and got the
/// parts wrong, which matters more. `Part::ensemble(1)` is `[Soprano]`, so the fold gave the *first*
/// duck the soprano line whatever its voice was, and the second the bass: parts by arrival order,
/// with the register ignored entirely. On two real ducks the low one sang soprano.
///
/// So the parts of `Part::ensemble(n)` are handed out in register order, lowest voice to lowest
/// part. Because those sets are nested, a duck arriving at the register the ensemble was missing
/// still moves nobody; a duck arriving *below* the current bass does shift one part, and that is the
/// price of having everybody on the right line to begin with.
pub fn seat_all(registers: &[f64]) -> Vec<Part> {
    let parts = Part::ensemble(registers.len());
    // Roster positions, ordered by the voice at each — so the answer comes back in roster order
    // while the *parts* are assigned by register.
    let mut order: Vec<usize> = (0..registers.len()).collect();
    order.sort_by(|a, b| {
        registers[*a]
            .partial_cmp(&registers[*b])
            .expect("registers are finite")
            // Two ducks on the same register keep roster order between them, so the answer does not
            // depend on the sort's stability.
            .then(a.cmp(b))
    });
    let mut seated = vec![Part::Soprano; registers.len()];
    for (rank, position) in order.into_iter().enumerate() {
        // More ducks than parts double the top line, which is what `Part::ensemble` runs out at.
        seated[position] = parts.get(rank).copied().unwrap_or(Part::Soprano);
    }
    seated
}

/// Equal-temperament frequency of a MIDI note, from [`A4_HZ`].
pub fn midi_hz(midi: f64) -> f64 {
    A4_HZ * 2.0f64.powf((midi - 69.0) / 12.0)
}

// **Why there is no automatic transposition.**
//
// The obvious idea, and it was tried: shift the whole piece so each duck's part sits near its
// own `pitch_center_hz`, since a duck rolled high should get high notes. Every ensemble came
// out pinned at the maximum shift, dragging the piece up and thinning the bass, and the
// heuristic turns out to be measuring the wrong thing. A duck's pitch centre is where its
// *quacks* sit; the synth's harmonic weights are relative to f0, so a duck singing well below
// its centre sounds like itself an octave down rather than like a duck out of its depth.
// Register already does its job in `cast` — the low duck gets the low part — and a second
// mechanism chasing the same goal only fought the voicings, which were written for what the
// hardware can reproduce. `Options::transpose` stays as a knob for taste.

/// What to render, and how.
#[derive(Debug, Clone, Copy)]
pub struct Options {
    /// Transposition in semitones. See the note above on why this is not chosen for you.
    pub transpose: i32,
    /// Wet mix of the room, 0..1.
    ///
    /// Real ducks get this for free by being four objects in a room, and the dry sum of four
    /// synths is harsher than what the hardware will actually produce — so a preview with no
    /// room in it misrepresents the arrangement in the pessimistic direction.
    pub room: f64,
    /// Peak of the finished mix, dBFS.
    pub peak_dbfs: f64,
    /// Where the playback speaker stops reproducing, hertz — or `None` for a full-range one.
    ///
    /// Defaults to the duck's own driver, because the duck is the target. A coin-sized speaker
    /// produces almost nothing below a few hundred hertz, so the bass line's fundamental is not
    /// quiet but *absent*, and `Stream::set_speaker_rolloff` moves the note into harmonics the
    /// driver can actually make. Set `None` to hear the arrangement on a full-range system.
    pub speaker_rolloff_hz: Option<f64>,
}

impl Default for Options {
    fn default() -> Self {
        Self {
            transpose: 0,
            room: 0.25,
            peak_dbfs: -3.0,
            // Measured by ear on the duck rather than from a datasheet: the shipped score's
            // 130 Hz bass line did not come through, and this is where it starts to.
            speaker_rolloff_hz: Some(300.0),
        }
    }
}

/// Render the ensemble to one mono buffer at [`SR`].
///
/// Each singer is rendered whole and then summed, rather than the parts being interleaved
/// block by block, because that is what will actually happen: on real hardware these are four
/// separate machines, and anything that needed them to share a buffer would be a preview of
/// something we cannot build.
pub fn render(score: &Score, singers: &[Singer], options: &Options) -> Vec<f32> {
    let shift = options.transpose;
    // Tail enough for the last release and the room to decay.
    let total = ((score.duration_s() + 2.5) * f64::from(SR)) as usize;
    let mut mix = vec![0.0f32; total];

    for singer in singers {
        for (sample, value) in sing(score, singer, shift, total, options)
            .iter()
            .enumerate()
        {
            mix[sample] += value;
        }
    }
    // Not 1/n: uncorrelated voices sum closer to sqrt(n), and dividing by n would make every
    // added duck quieter rather than fuller.
    let gain = 1.0 / (singers.len().max(1) as f32).sqrt();
    for sample in &mut mix {
        *sample *= gain;
    }

    if options.room > 0.0 {
        reverb(&mut mix, options.room as f32);
    }
    crate::synth::normalise(&mut mix, options.peak_dbfs);
    mix
}

/// One duck's part, as it would come out of that duck's speaker.
fn sing(score: &Score, singer: &Singer, shift: i32, total: usize, options: &Options) -> Vec<f32> {
    /// Control-rate block. Short enough that a note change lands within a couple of
    /// milliseconds; the stream's own slews do the shaping from there.
    const BLOCK: usize = 128;

    let mut stream = Stream::choral(&singer.personality, singer.part as u32);
    stream.set_speaker_rolloff(options.speaker_rolloff_hz);
    let detune = 2.0f64.powf(singer.detune_cents / 1200.0);
    let beat_s = score.beat_s();

    // This part's line, in seconds. Ties are already merged by `Score::from_notes`, so a common
    // tone held across a chord change arrives here as one note and is not re-attacked — while a
    // change of *vowel* on the same pitch does arrive as two, which is what a new syllable is.
    let line: Vec<Note> = score.line(singer.part).copied().collect();
    if line.is_empty() {
        return vec![0.0; total];
    }

    // Where in its own part a note sits, for the mouth-and-timbre shape below.
    let (low, high) = line.iter().fold((127.0f64, 0.0f64), |(lo, hi), note| {
        (lo.min(f64::from(note.midi)), hi.max(f64::from(note.midi)))
    });

    let mut out = vec![0.0f32; total];
    let mut note_index = 0usize;
    // Held across rests: a silent voice keeps its last pitch so the next entry does not glide up
    // from nowhere. The level is what makes it silent.
    let mut last_hz = midi_hz(f64::from(line[0].midi) + f64::from(shift));

    for start in (0..total).step_by(BLOCK) {
        let now = start as f64 / f64::from(SR) - singer.onset_offset_s;
        while note_index < line.len() && now >= line[note_index].end_beat() * beat_s {
            note_index += 1;
        }
        let (level, open, formant) = match line.get(note_index) {
            Some(note) if now >= note.start_beat * beat_s => {
                last_hz = midi_hz(f64::from(note.midi) + f64::from(shift)) * detune;
                // A breath before the next entry: the note releases a little early, so a change
                // of chord re-articulates instead of sliding into the next one.
                let begin = note.start_beat * beat_s;
                let sustain = note.beats * beat_s * 0.92;
                let singing = now - begin < sustain;
                // The written dynamic, and a hum sits back behind everything else.
                let level = if singing {
                    note.level * note.vowel.level_scale()
                } else {
                    0.0
                };
                // The vowel decides the beak; reaching up in your own part opens it a little
                // further, which is what a singer actually does. One number, so what is heard
                // and what is seen are the same gesture.
                let reach = ((f64::from(note.midi) - low) / (high - low).max(1.0)).clamp(0.0, 1.0);
                let open = (note.vowel.open() + 0.12 * reach).clamp(0.0, 1.0);
                (level, open, note.vowel.formant_shift())
            }
            // Before the first entry, or after the last release.
            _ => (0.0, Vowel::default().open(), 0.0),
        };
        stream.set_formant_shift(formant);
        stream.set(last_hz, level, open);
        let end = (start + BLOCK).min(total);
        stream.block(&mut out[start..end]);
    }
    out
}

/// A small room, so a preview is not drier than the hardware.
///
/// Schroeder's arrangement — four parallel combs into two series allpasses — which is the
/// cheapest thing that sounds like a space rather than like an echo. The delays are the
/// classic mutually-prime lengths, scaled from the 25 kHz they were published at to [`SR`] so
/// the room keeps its *size* rather than its sample counts.
fn reverb(buffer: &mut [f32], wet: f32) {
    const COMB_MS: [f64; 4] = [29.7, 37.1, 41.1, 43.7];
    const COMB_FEEDBACK: [f32; 4] = [0.78, 0.76, 0.74, 0.72];
    const ALLPASS_MS: [f64; 2] = [5.0, 1.7];
    const ALLPASS_GAIN: f32 = 0.7;

    let samples = |ms: f64| ((ms / 1000.0) * f64::from(SR)) as usize;
    let dry = buffer.to_vec();
    let mut wet_sum = vec![0.0f32; buffer.len()];

    for (delay_ms, feedback) in COMB_MS.iter().zip(COMB_FEEDBACK) {
        let delay = samples(*delay_ms).max(1);
        let mut line = vec![0.0f32; delay];
        for (i, &input) in dry.iter().enumerate() {
            let slot = i % delay;
            let delayed = line[slot];
            line[slot] = input + delayed * feedback;
            wet_sum[i] += delayed * 0.25;
        }
    }
    for delay_ms in ALLPASS_MS {
        let delay = samples(delay_ms).max(1);
        let mut line = vec![0.0f32; delay];
        for (i, sample) in wet_sum.iter_mut().enumerate() {
            let slot = i % delay;
            let delayed = line[slot];
            let input = *sample;
            line[slot] = input + delayed * ALLPASS_GAIN;
            *sample = delayed - input * ALLPASS_GAIN;
        }
    }
    let wet = wet.clamp(0.0, 1.0);
    for (out, w) in buffer.iter_mut().zip(&wet_sum) {
        *out = *out * (1.0 - 0.5 * wet) + w * wet;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cast_of(seeds: &[u32]) -> Vec<Singer> {
        let personalities: Vec<Personality> =
            seeds.iter().copied().map(Personality::from_seed).collect();
        cast(&personalities)
    }

    /// The lowest duck sings bass, and nobody has to be told — real ducks agree on the casting
    /// from the seeds they already know, with no leader and no negotiation.
    #[test]
    fn the_lowest_duck_sings_bass() {
        for seeds in [
            vec![100u32, 101, 102, 103],
            vec![7, 42, 313, 9001],
            vec![0, 1, 2, 3],
        ] {
            let singers = cast_of(&seeds);
            let mut by_part = singers.clone();
            by_part.sort_by_key(|s| s.part);
            for pair in by_part.windows(2) {
                assert!(
                    pair[0].personality.pitch_center_hz <= pair[1].personality.pitch_center_hz,
                    "{:?} sings under {:?} but is higher",
                    pair[0].part,
                    pair[1].part
                );
            }
            // And the casting is a function of the seeds alone, so two ducks reach it
            // independently.
            let again = cast_of(&seeds);
            let parts: Vec<Part> = singers.iter().map(|s| s.part).collect();
            let parts_again: Vec<Part> = again.iter().map(|s| s.part).collect();
            assert_eq!(parts, parts_again);
        }
    }

    /// The order the ducks are listed in must not change who sings what — on real hardware the
    /// list arrives in whatever order discovery produced.
    #[test]
    fn casting_does_not_depend_on_the_order_the_ducks_arrive_in() {
        let forward = cast_of(&[100, 101, 102, 103]);
        let backward = cast_of(&[103, 102, 101, 100]);
        for singer in &forward {
            let same = backward
                .iter()
                .find(|s| s.personality.seed == singer.personality.seed)
                .expect("same ducks");
            assert_eq!(singer.part, same.part, "seed {}", singer.personality.seed);
            assert_eq!(singer.detune_cents, same.detune_cents);
        }
    }

    /// The embedded upbeat piece must parse, be a full quartet, stay inside the duck part
    /// ranges, and keep its tempo — the properties the ducks depend on, pinned so an edited
    /// MuseScore export cannot silently break them.
    #[test]
    fn duck_strut_is_a_quartet_a_duck_can_sing() {
        let score = Score::duck_strut();
        assert_eq!(score.name, "duck-strut");
        assert!((score.bpm - 126.0).abs() < 0.5, "{}", score.bpm);
        assert_eq!(score.parts().len(), 4, "full SATB");
        assert!(
            (40.0..90.0).contains(&score.duration_s()),
            "{}s",
            score.duration_s()
        );
        // Bass A2..A3, tenor E3..E4, alto A3..A4, soprano D4..D5.
        let bounds = [(45u8, 57u8), (52, 64), (57, 69), (62, 74)];
        for note in &score.notes {
            let (low, high) = bounds[note.part as usize];
            assert!(
                (low..=high).contains(&note.midi),
                "{:?} sings {}, outside {low}..={high}",
                note.part,
                note.midi
            );
        }
        // It is genuinely rhythmically independent — the thing the MIDI path exists for: the
        // voices do not all move together.
        let mut starts: Vec<f64> = score.notes.iter().map(|n| n.start_beat).collect();
        starts.sort_by(|a, b| a.partial_cmp(b).expect("finite"));
        starts.dedup();
        assert!(starts.len() > 60, "{} distinct onsets", starts.len());
        // And the dynamics vary — velocity became level.
        let levels: Vec<f64> = score.notes.iter().map(|n| n.level).collect();
        assert!(levels.iter().any(|l| (*l - levels[0]).abs() > 0.05));
    }

    /// Joining a group that is already singing must not move anyone who is: the whole reason
    /// `seat` exists alongside `cast`. With `cast` alone, a low duck arriving at a duet would take
    /// the bass and shove the current bass up to alto — a part change mid-piece.
    #[test]
    fn a_duck_joining_does_not_move_anyone_already_singing() {
        let personalities: Vec<Personality> = [100u32, 7, 313, 42]
            .iter()
            .copied()
            .map(Personality::from_seed)
            .collect();
        // Two ducks start together, then two more arrive one at a time.
        let mut ensemble = cast(&personalities[..2]);
        let opening: Vec<(u32, Part)> = ensemble
            .iter()
            .map(|s| (s.personality.seed, s.part))
            .collect();

        for newcomer in &personalities[2..] {
            let joined = seat(&ensemble, newcomer);
            ensemble.push(joined);
            // Everyone who was singing is still singing the same part.
            for (seed, part) in &opening {
                let now = ensemble
                    .iter()
                    .find(|s| s.personality.seed == *seed)
                    .expect("still here");
                assert_eq!(
                    now.part, *part,
                    "seed {seed} changed part when someone joined"
                );
            }
            // And no two ducks are doubling while a part is still free.
            let mut parts: Vec<Part> = ensemble.iter().map(|s| s.part).collect();
            parts.sort();
            let unique = {
                let mut p = parts.clone();
                p.dedup();
                p.len()
            };
            assert_eq!(unique, parts.len(), "doubled up early: {parts:?}");
        }
        assert_eq!(ensemble.len(), 4);
    }

    /// Parts go by *voice*, not by who arrived first. The bug this replaced gave the first duck in
    /// the roster the soprano line whatever its register was — on two real ducks, the low one sang
    /// soprano — because `Part::ensemble(1)` is `[Soprano]` and the seating was a fold down the
    /// roster.
    #[test]
    fn the_lowest_voice_in_the_roster_gets_the_lowest_part() {
        // Roster order deliberately opposite to register order: the high duck arrived first.
        let high_first = seat_all(&[520.0, 214.0]);
        assert_eq!(
            high_first,
            vec![Part::Soprano, Part::Bass],
            "{high_first:?}"
        );
        let low_first = seat_all(&[214.0, 520.0]);
        assert_eq!(low_first, vec![Part::Bass, Part::Soprano], "{low_first:?}");

        // Three and four, in a shuffled roster: the answer is in roster order, the parts are by
        // register.
        let parts = seat_all(&[490.0, 214.0, 519.0, 389.0]);
        assert_eq!(
            parts,
            vec![Part::Alto, Part::Bass, Part::Soprano, Part::Tenor],
            "{parts:?}"
        );
        // Every part used exactly once.
        let mut sorted = parts.clone();
        sorted.sort();
        assert_eq!(sorted, Part::ALL.to_vec());
    }

    /// A duck arriving at the register the ensemble was missing moves nobody — the nested sets are
    /// what make that true, and it is the common case. One arriving *below* the current bass does
    /// shift a part, which is the price of everyone being on the right line to begin with.
    #[test]
    fn a_joiner_in_the_gap_moves_nobody() {
        let duet = seat_all(&[214.0, 520.0]);
        assert_eq!(duet, vec![Part::Bass, Part::Soprano]);
        // A middle voice joins: it takes the alto and the other two keep their parts.
        let trio = seat_all(&[214.0, 520.0, 390.0]);
        assert_eq!(&trio[..2], &duet[..], "{trio:?}");
        assert_eq!(trio[2], Part::Alto);
        // A fourth in the remaining gap, likewise.
        let quartet = seat_all(&[214.0, 520.0, 390.0, 300.0]);
        assert_eq!(&quartet[..3], &trio[..], "{quartet:?}");
        assert_eq!(quartet[3], Part::Tenor);
    }

    /// The nesting of `Part::ensemble` is what makes that possible — there is always exactly one
    /// free part for a joiner until the fourth duck has arrived. If someone reorders those sets,
    /// this is what notices.
    #[test]
    fn the_ensemble_sets_are_nested() {
        for n in 1..4 {
            let smaller = Part::ensemble(n);
            let larger = Part::ensemble(n + 1);
            for part in &smaller {
                assert!(
                    larger.contains(part),
                    "ensemble({n}) is not inside ensemble({}) — {smaller:?} vs {larger:?}",
                    n + 1
                );
            }
            assert_eq!(larger.len(), smaller.len() + 1, "exactly one part opens up");
        }
    }

    /// Past four ducks the parts double, which is what a real choir does with more singers than
    /// lines — and the doubling duck takes the part nearest its own register rather than an
    /// arbitrary one.
    #[test]
    fn a_fifth_duck_doubles_the_part_nearest_its_voice() {
        let quartet = cast(
            &[100u32, 7, 313, 42]
                .iter()
                .copied()
                .map(Personality::from_seed)
                .collect::<Vec<_>>(),
        );
        // A very low duck: seed chosen by searching for one at the bottom of the population.
        let low = (0u32..2000)
            .map(Personality::from_seed)
            .min_by(|a, b| {
                a.pitch_center_hz
                    .partial_cmp(&b.pitch_center_hz)
                    .expect("finite")
            })
            .expect("some duck");
        let fifth = seat(&quartet, &low);
        assert_eq!(
            fifth.part,
            Part::Bass,
            "a {} Hz duck doubles the bass",
            low.pitch_center_hz
        );

        let high = (0u32..2000)
            .map(Personality::from_seed)
            .max_by(|a, b| {
                a.pitch_center_hz
                    .partial_cmp(&b.pitch_center_hz)
                    .expect("finite")
            })
            .expect("some duck");
        assert_eq!(seat(&quartet, &high).part, Part::Soprano);
    }

    /// A duet takes the outer voices. Two ducks muttering a bass and a tenor in the same octave
    /// is not a duet, it is a thick unison.
    #[test]
    fn small_ensembles_take_the_voices_a_chord_needs_most() {
        assert_eq!(Part::ensemble(2), vec![Part::Bass, Part::Soprano]);
        assert_eq!(
            Part::ensemble(3),
            vec![Part::Bass, Part::Alto, Part::Soprano]
        );
        assert_eq!(Part::ensemble(4), Part::ALL.to_vec());
        // More ducks than parts still produces a valid cast rather than a panic — the extras
        // double a part, which is what a real choir does.
        let singers = cast_of(&[1, 2, 3, 4, 5, 6]);
        assert_eq!(singers.len(), 6);
    }

    /// Tuning is absolute and shared. This is the property that makes a chord a chord, and the
    /// one a "keep each duck's own register" design would have broken.
    #[test]
    fn every_duck_sings_the_same_pitch_for_the_same_note() {
        assert!((midi_hz(69.0) - A4_HZ).abs() < 1e-9);
        assert!((midi_hz(81.0) - 2.0 * A4_HZ).abs() < 1e-9);
        assert!((midi_hz(60.0) - 261.6255653).abs() < 1e-6, "middle C");

        // The detune spread is small enough to be a chorus and not a wrong note: five cents is
        // a third of the way to the smallest interval anyone would call out of tune.
        for singer in cast_of(&[100, 101, 102, 103]) {
            assert!(
                singer.detune_cents.abs() <= 5.0,
                "{} cents is audible as flat",
                singer.detune_cents
            );
            assert!(singer.onset_offset_s.abs() <= 0.015);
        }
    }

    fn score_of(gestures: Vec<Gesture>) -> Score {
        Score::from_gestures("test", 60.0, &gestures)
    }

    fn plain(voicing: Voicing, beats: f64) -> Gesture {
        Gesture::Chord {
            voicing,
            beats,
            vowel: Vowel::Ah,
            level: 1.0,
        }
    }

    /// Common tones are tied, not re-attacked — the audible difference between a chorale and a
    /// list of chords, and the reason both front ends merge rather than emitting one note per
    /// gesture or per MIDI event.
    #[test]
    fn common_tones_come_out_as_one_note() {
        let score = Score::wistful();
        let alto: Vec<&Note> = score.line(Part::Alto).collect();
        // The alto's C4 is the thread the opening hangs on: it is held right through the tread
        // as one note, across four chord changes and a change of dynamic, and re-articulates
        // only where the *vowel* changes.
        let longest = alto.iter().map(|n| n.beats).fold(0.0, f64::max);
        assert!(
            longest >= 9.0,
            "the alto's C4 through the tread should be one long tie, longest is {longest} beats"
        );
        // And the opening is a *shorter* note, because the vowel opens when the harmony starts
        // to move — a new syllable is a new note even on the same pitch.
        assert!(alto[0].beats < longest, "{:?}", alto[0]);
        for note in &score.notes {
            assert!(note.beats > 0.0, "{note:?}");
            assert!(note.start_beat >= 0.0, "{note:?}");
            assert!((0.0..=1.0).contains(&note.level), "{note:?}");
        }
        // And a part's notes never overlap themselves — one voice, one note at a time.
        for part in Part::ALL {
            let line: Vec<&Note> = score.line(part).collect();
            for pair in line.windows(2) {
                assert!(
                    pair[1].start_beat + 1e-9 >= pair[0].end_beat(),
                    "{part:?} overlaps itself: {:?} then {:?}",
                    pair[0],
                    pair[1]
                );
            }
        }
    }

    /// A `Build` assembles the chord: voices enter apart and end together. This is the gesture a
    /// keyboard cannot make, and the one most forgiving of imperfect sync between real ducks.
    #[test]
    fn a_build_staggers_the_entries_and_lands_them_together() {
        let score = score_of(vec![Gesture::Build {
            voicing: chord(48, 55, 60, 64),
            beats: 6.0,
            stagger: 0.75,
            from_top: false,
            vowel: Vowel::Ah,
            level: 1.0,
        }]);
        assert_eq!(score.notes.len(), 4, "one note per voice");
        for part in Part::ALL {
            let note = score.line(part).next().expect("sings");
            // Entries are ordered low to high...
            assert!(
                (note.start_beat - part as usize as f64 * 0.75).abs() < 1e-9,
                "{part:?} entered at {}",
                note.start_beat
            );
            // ...and everyone finishes at the end of the gesture.
            assert!((note.end_beat() - 6.0).abs() < 1e-9, "{part:?} {note:?}");
        }

        // From the top, the soprano is first in and the bass last.
        let flipped = score_of(vec![Gesture::Build {
            voicing: chord(48, 55, 60, 64),
            beats: 6.0,
            stagger: 0.75,
            from_top: true,
            vowel: Vowel::Ah,
            level: 1.0,
        }]);
        assert!(
            flipped
                .line(Part::Soprano)
                .next()
                .expect("sings")
                .start_beat
                < flipped.line(Part::Bass).next().expect("sings").start_beat
        );

        // A stagger too long for the gesture drops the late voices rather than emitting a
        // negative-length note.
        let crowded = score_of(vec![Gesture::Build {
            voicing: chord(48, 55, 60, 64),
            beats: 1.0,
            stagger: 0.75,
            from_top: false,
            vowel: Vowel::Ah,
            level: 1.0,
        }]);
        assert_eq!(
            crowded.notes.len(),
            2,
            "only two voices fit: {:?}",
            crowded.notes
        );
        assert!(crowded.notes.iter().all(|n| n.beats > 0.0));
    }

    /// A solo is one voice moving over a held chord, and the voices left out of `under` are
    /// genuinely silent — which is what makes an unaccompanied entry possible.
    #[test]
    fn a_solo_moves_over_what_is_held_under_it() {
        let solo = Gesture::Solo {
            part: Part::Soprano,
            notes: vec![
                SoloNote {
                    midi: 64,
                    beats: 1.0,
                    vowel: Vowel::Ah,
                },
                SoloNote {
                    midi: 65,
                    beats: 1.0,
                    vowel: Vowel::Ah,
                },
                SoloNote {
                    midi: 67,
                    beats: 2.0,
                    vowel: Vowel::Ee,
                },
            ],
            under: [Some(48), None, Some(60), None],
            under_vowel: Vowel::Mm,
            level: 0.7,
        };
        assert_eq!(solo.beats(), 4.0, "the solo line sets the length");
        let score = score_of(vec![solo]);
        assert_eq!(score.line(Part::Soprano).count(), 3, "the soloist moves");
        assert_eq!(score.line(Part::Tenor).count(), 0, "tacet under this solo");
        let alto: Vec<&Note> = score.line(Part::Alto).collect();
        assert_eq!(alto.len(), 1, "the accompaniment is one held note");
        assert_eq!(alto[0].beats, 4.0);
        assert_eq!(alto[0].vowel, Vowel::Mm, "and it hums");
        // A soloist's own pitch is theirs, not `under`'s.
        assert_eq!(score.line(Part::Bass).next().expect("sings").midi, 48);
        assert_eq!(score.line(Part::Soprano).next().expect("sings").midi, 64);
    }

    /// A rest breaks the tie. Without that, a breath written between two chords the voices were
    /// already holding would be silently swallowed by the merge.
    #[test]
    fn a_rest_is_a_real_gap() {
        let score = score_of(vec![
            plain(chord(48, 55, 60, 64), 2.0),
            Gesture::Rest { beats: 1.0 },
            plain(chord(48, 55, 60, 64), 2.0),
        ]);
        let bass: Vec<&Note> = score.line(Part::Bass).collect();
        assert_eq!(
            bass.len(),
            2,
            "the same note either side of a breath is two notes"
        );
        assert_eq!(bass[0].end_beat(), 2.0);
        assert_eq!(bass[1].start_beat, 3.0);
        assert_eq!(score.duration_s(), 5.0, "the rest occupies time");

        // Whereas without the rest, it is one tied note.
        let tied = score_of(vec![
            plain(chord(48, 55, 60, 64), 2.0),
            plain(chord(48, 55, 60, 64), 2.0),
        ]);
        assert_eq!(tied.line(Part::Bass).count(), 1);
        assert_eq!(tied.line(Part::Bass).next().expect("sings").beats, 4.0);
    }

    /// A new vowel or a new dynamic on the same pitch re-articulates: that is what a singer does
    /// with a new syllable, and what a `<` in a score means.
    #[test]
    fn a_change_of_syllable_or_dynamic_is_a_new_note() {
        let resung = score_of(vec![
            plain(chord(48, 55, 60, 64), 1.0),
            Gesture::Chord {
                voicing: chord(48, 55, 60, 64),
                beats: 1.0,
                vowel: Vowel::Ee,
                level: 1.0,
            },
        ]);
        assert_eq!(resung.line(Part::Bass).count(), 2, "a new syllable");

        // A dynamic, by contrast, does *not* re-attack — a mark over a sounding note is a
        // crescendo, and the note keeps the dynamic it began on.
        let louder = score_of(vec![
            plain(chord(48, 55, 60, 64), 1.0),
            Gesture::Chord {
                voicing: chord(48, 55, 60, 64),
                beats: 1.0,
                vowel: Vowel::Ah,
                level: 0.4,
            },
        ]);
        let bass: Vec<&Note> = louder.line(Part::Bass).collect();
        assert_eq!(bass.len(), 1, "a crescendo is not a new note");
        assert_eq!(bass[0].beats, 2.0);
        assert_eq!(bass[0].level, 1.0, "it keeps the dynamic it started on");
    }

    /// The shipped piece uses all of it — a chord assembling, a solo, a breath, a change of
    /// dynamic and a hum. If someone flattens it back to block chords, this notices.
    #[test]
    fn the_default_piece_is_more_than_block_chords() {
        let score = Score::wistful();
        assert!(
            score.notes.iter().any(|n| n.vowel == Vowel::Mm),
            "nobody ever hums"
        );
        let levels: Vec<f64> = score.notes.iter().map(|n| n.level).collect();
        assert!(
            levels.iter().any(|l| *l != levels[0]),
            "the dynamic never moves"
        );
        // Voices enter at different times somewhere, which is what a build is.
        let mut starts: Vec<f64> = score.notes.iter().map(|n| n.start_beat).collect();
        starts.sort_by(|a, b| a.partial_cmp(b).expect("finite"));
        starts.dedup();
        assert!(
            starts.len() > score.notes.len() / 2,
            "everything is simultaneous"
        );
        assert!(
            (30.0..90.0).contains(&score.duration_s()),
            "{}s",
            score.duration_s()
        );
    }

    /// Every note has to be singable by a duck and audible on its speaker: a chorale whose bass
    /// is below what the hardware reproduces is a trio.
    #[test]
    fn the_default_score_stays_inside_ranges_a_duck_can_sing() {
        // Bass A2..A3, tenor E3..E4, alto A3..A4, soprano D4..D5.
        let bounds = [(45u8, 57u8), (52, 64), (57, 69), (62, 74)];
        for note in &Score::wistful().notes {
            let (low, high) = bounds[note.part as usize];
            assert!(
                (low..=high).contains(&note.midi),
                "{:?} sings {}, outside {low}..={high}",
                note.part,
                note.midi
            );
        }
    }

    /// The whole ensemble must render to finite, audible, non-clipping audio for any number of
    /// ducks and any seeds — this is the thing a laptop preview exists to produce.
    #[test]
    fn an_ensemble_of_any_size_renders_sane_audio() {
        let score = Score::wistful();
        for count in 2..=4 {
            let seeds: Vec<u32> = (0..count).map(|i| 100 + i as u32).collect();
            let singers = cast_of(&seeds);
            let mix = render(&score, &singers, &Options::default());
            assert!(
                mix.len() as f64 / f64::from(SR) > score.duration_s(),
                "the tail must outlast the last note"
            );
            assert!(
                mix.iter().all(|v| v.is_finite()),
                "{count} ducks: not finite"
            );
            let peak = mix.iter().fold(0.0f32, |m, &v| m.max(v.abs()));
            assert!((0.5..=1.0).contains(&peak), "{count} ducks: peak {peak}");
            // And it is not silence in the middle of the piece.
            let middle = mix.len() / 2;
            let rms: f32 = mix[middle..middle + 4800]
                .iter()
                .map(|v| v * v)
                .sum::<f32>();
            assert!(rms > 1e-3, "{count} ducks: silent mid-piece");
        }
    }

    /// A dry render is still a render: the room is a preview convenience, not load-bearing, and
    /// turning it off must not change the level or blow up.
    #[test]
    fn the_room_is_optional() {
        let score = Score::wistful();
        let singers = cast_of(&[100, 101, 102, 103]);
        let dry = render(
            &score,
            &singers,
            &Options {
                room: 0.0,
                ..Options::default()
            },
        );
        assert!(dry.iter().all(|v| v.is_finite()));
        let peak = dry.iter().fold(0.0f32, |m, &v| m.max(v.abs()));
        assert!((0.5..=1.0).contains(&peak), "dry peak {peak}");
    }
}

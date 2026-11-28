"""Song form: picks progressions for each section, lays them out in time and
renders the parts:

  Melody  motif-based phrases for every section (see melody.py)
  Chords  one voiced chord per change (held chords, with bass, or arpeggio;
          see _chords_part)
  Bass    optional guide track (see groove.py)
  Drums   optional guide track, General MIDI drum map on channel 10

A mood (moods.py) swaps in its own progressions, melody style and groove;
mood "none" is the original behaviour.

Times are in quarter notes from the start of the song.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from .groove import bass_part, drum_part
from .melody import generate_melody
from .moods import MOODS, NONE, check_mood, mood_progressions, mood_substitutions
from .progressions import (MODAL_LEVELS, MODAL_SUBSTITUTIONS, PROGRESSIONS, SUBSTITUTIONS, fill_bars,
                           parse_progression, substitute)
from .rhythm import TimeSig, arpeggio_pattern
from .theory import Chord, Key, parse_roman
from .voicing import left_hand_root, voice_chord, voice_root_position

SECTION_KINDS = ("intro", "verse", "chorus", "verse2", "chorus2", "ending")
SECTION_BARS = {"intro": 4, "verse": 8, "chorus": 8, "verse2": 8, "chorus2": 8}  # ending: its progression
LABELS = {"intro": "Intro", "verse": "Verse 1", "chorus": "Chorus", "verse2": "Verse 2",
          "chorus2": "Chorus 2", "ending": "Ending"}
DEFAULT_FORM = ("intro", "verse", "chorus", "verse2", "ending")
CHORD_VELOCITY = {"intro": 60, "verse": 66, "verse2": 68, "chorus": 78, "chorus2": 80, "ending": 70}
CHORD_STYLES = ("chords", "block", "arpeggio")
DEFAULT_CHORD_STYLE = "chords"
STYLE_ALIASES = {"block-no-root": "chords"}  # older name for "chords"
EPS = 1e-6


@dataclass
class ChordSlot:
    chord: Chord
    start: float
    length: float


@dataclass
class Section:
    kind: str
    label: str
    start: float
    bars: float
    slots: list = field(default_factory=list)


@dataclass
class Note:
    start: float
    dur: float
    pitch: int
    velocity: int


@dataclass
class Track:
    name: str
    channel: int
    program: int
    notes: list


@dataclass
class Song:
    key: Key
    tempo: int
    timesig: TimeSig
    level: str
    seed: int
    sections: list
    tracks: list
    chord_style: str = DEFAULT_CHORD_STYLE
    mood: str = NONE

    @property
    def total_quarters(self) -> float:
        last = self.sections[-1]
        return last.start + last.bars * self.timesig.bar_quarters

    def track(self, name: str) -> Track:
        return next(t for t in self.tracks if t.name == name)

    def has_track(self, name: str) -> bool:
        return any(t.name == name for t in self.tracks)


def _section_plan(kind: str, progs: dict, subs: dict, rng: random.Random, modal: dict = None,
                  modal_rng: random.Random = None) -> list:
    if kind in ("intro", "verse"):
        return fill_bars(progs[kind], SECTION_BARS[kind])
    if kind == "verse2":
        # First half as before, second half with one chord changed.
        half = SECTION_BARS["verse2"] / 2
        varied = substitute(progs["verse"], subs, rng)  # always drawn, so the song's random stream stays put
        if modal:
            borrowed = substitute(progs["verse"], modal, modal_rng, keep_resolutions=True)
            if borrowed != progs["verse"]:
                varied = borrowed
        return fill_bars(progs["verse"], half) + fill_bars(varied, half)
    if kind in ("chorus", "chorus2"):
        return fill_bars(progs["chorus"], SECTION_BARS[kind])
    return list(progs["ending"])


def compose(key: Key, tempo: int, timesig: TimeSig, level: str = "basic", seed: int = None,
            form=DEFAULT_FORM, chord_style: str = DEFAULT_CHORD_STYLE, mood: str = NONE,
            bass: bool = False, drums: bool = False) -> Song:
    chord_style = STYLE_ALIASES.get(chord_style, chord_style)
    mood = check_mood(mood)
    if level not in PROGRESSIONS:
        raise ValueError(f"Level {level!r} is not available yet; choose from {', '.join(PROGRESSIONS)}")
    if chord_style not in CHORD_STYLES:
        raise ValueError(f"Unknown chord style {chord_style!r}; use one of {', '.join(CHORD_STYLES)}")
    if not form:
        raise ValueError("The song form is empty")
    for kind in form:
        if kind not in SECTION_KINDS:
            raise ValueError(f"Unknown section {kind!r}; use any of {', '.join(SECTION_KINDS)}")
    if seed is None:
        seed = random.randrange(1_000_000)
    rng = random.Random(seed)

    mood_lib = mood_progressions(mood, level, key.mode)
    lib = mood_lib or PROGRESSIONS[level][key.mode]
    progs = {k: parse_progression(rng.choice(lib[k])) for k in ("intro", "verse", "chorus", "ending")}
    if mood_lib:
        subs, modal = mood_substitutions(mood, key.mode), None  # the mood's own Verse 2 changes
    else:
        subs = SUBSTITUTIONS[level][key.mode]
        # Modal interchange uses its own random stream, so adding it didn't change any song's melody.
        modal = MODAL_SUBSTITUTIONS[key.mode] if level in MODAL_LEVELS else None
    modal_rng = random.Random(f"modal-{seed}")

    bar_q = timesig.bar_quarters
    sections, t = [], 0.0
    for kind in form:
        plan = _section_plan(kind, progs, subs, rng, modal, modal_rng)
        section = Section(kind, LABELS[kind], t, sum(b for _, b in plan))
        for roman, bars in plan:
            section.slots.append(ChordSlot(parse_roman(roman, key), t, bars * bar_q))
            t += bars * bar_q
        sections.append(section)

    # Separate random streams, so changing the chord style never changes the melody, and
    # adding the guide tracks never changes the melody or the chords.
    melody_rng, chords_rng = random.Random(rng.randrange(2**32)), random.Random(rng.randrange(2**32))
    m = MOODS[mood]
    melody = [Note(*n) for n in generate_melody(sections, key, timesig, melody_rng, m["melody"])]
    chords = _chords_part(sections, timesig, chord_style, chords_rng, m["chord_velocity"])
    tracks = [Track("Melody", 0, 0, melody), Track("Chords", 1, 0, chords)]
    if bass:
        notes = bass_part(sections, key, timesig, m["bass"], random.Random(f"bass-{seed}"), m["chord_velocity"])
        tracks.append(Track("Bass", 2, 33, [Note(*n) for n in notes]))  # GM 34: Electric Bass (finger)
    if drums:
        notes = drum_part(sections, timesig, m["drums"], random.Random(f"drums-{seed}"))
        tracks.append(Track("Drums", 9, 0, [Note(*n) for n in notes]))  # channel 10: GM drums
    return Song(key, tempo, timesig, level, seed, sections, tracks, chord_style, mood)


def _chords_part(sections: list, ts: TimeSig, style: str, rng: random.Random, velocity_shift: int = 0) -> list:
    """chords    held root-position chords only, steady velocity: the layout Logic's
                 Arpeggiator and chord detection handle best (default)
       block     root in the left hand + a voice-led right-hand chord
       arpeggio  root held in the left hand + the right-hand chord broken into eighths
    The final chord is always a held chord so the song ends cleanly."""
    notes, previous = [], None
    all_slots = [(sec, slot) for sec in sections for slot in sec.slots]

    def add(start, dur, pitch, vel):
        notes.append(Note(start, dur, pitch, max(1, min(127, vel + rng.randint(-3, 3)))))

    for i, (sec, slot) in enumerate(all_slots):
        last = i == len(all_slots) - 1
        dur = slot.length if last else slot.length * 0.98  # tiny gap so repeated notes re-strike
        base = CHORD_VELOCITY[sec.kind] + velocity_shift
        end = slot.start + slot.length

        if style == "chords":
            for pitch in voice_root_position(slot.chord):
                notes.append(Note(slot.start, dur, pitch, base))
            continue

        voicing = voice_chord(slot.chord, previous, rootless=True)
        previous = voicing
        add(slot.start, dur, left_hand_root(slot.chord), base)
        if style == "arpeggio" and not last:
            tones = voicing + [voicing[0] + 12]
            step, order = arpeggio_pattern(ts, len(tones))
            t, k = slot.start, 0
            while t < end - EPS:
                ring = min(2 * step, end - t)  # each note rings into the next one
                accent = 8 if k == 0 else 0
                add(t, ring * 0.98, tones[order[k % len(order)] % len(tones)], base - 4 + accent)
                t += step
                k += 1
        else:
            for pitch in voicing:
                add(slot.start, dur, pitch, base)
    return notes

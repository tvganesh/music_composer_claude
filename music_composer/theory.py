"""Music theory core: note spelling, keys, scales and chords built from Roman numerals.

Roman numerals are interpreted against the key's own scale (natural minor for
minor keys). The *case* of the numeral sets the chord quality, so in C minor
"v" is G minor and "V" is G major (the harmonic-minor dominant).

Supported examples: I, vi, V7, ii7, Imaj7, vii°, ii°7, viiø7, IVsus2, V7sus4,
Iadd9, bVI, bVII, #iv°7, and secondary chords such as V7/vi or vii°7/V.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

LETTERS = "CDEFGAB"
LETTER_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

SCALES = {
    "major": (0, 2, 4, 5, 7, 9, 11),
    "minor": (0, 2, 3, 5, 7, 8, 10),  # natural minor
}
MAJOR = SCALES["major"]

# Key signatures along the circle of fifths (index - 7 = number of sharps/flats).
_MAJOR_FIFTHS = ["Cb", "Gb", "Db", "Ab", "Eb", "Bb", "F", "C", "G", "D", "A", "E", "B", "F#", "C#"]
_MINOR_FIFTHS = ["Ab", "Eb", "Bb", "F", "C", "G", "D", "A", "E", "B", "F#", "C#", "G#", "D#", "A#"]


def normalize_note(name: str) -> str:
    """'f#' -> 'F#', 'bb' -> 'Bb', 'E♭' -> 'Eb'."""
    m = re.fullmatch(r"\s*([A-Ga-g])([#b♯♭]*)\s*", name)
    if not m:
        raise ValueError(f"Not a note name: {name!r}")
    acc = m.group(2).replace("♯", "#").replace("♭", "b")
    if "#" in acc and "b" in acc:
        raise ValueError(f"Mixed accidentals in note name: {name!r}")
    return m.group(1).upper() + acc


def note_pc(name: str) -> int:
    """Pitch class (0-11) of a note name."""
    name = normalize_note(name)
    pc = LETTER_PC[name[0]]
    for ch in name[1:]:
        pc += 1 if ch == "#" else -1
    return pc % 12


def spell(letter_idx: int, pc: int) -> str:
    """Spell pitch class `pc` using the given letter (index into LETTERS)."""
    letter = LETTERS[letter_idx % 7]
    diff = (pc - LETTER_PC[letter] + 6) % 12 - 6  # -6..5
    if diff > 2 or diff < -2:  # should not happen for tonal material
        raise ValueError(f"Cannot spell pitch class {pc} on letter {letter}")
    return letter + ("#" * diff if diff > 0 else "b" * -diff)


@dataclass(frozen=True)
class Key:
    tonic: str
    mode: str = "major"

    def __post_init__(self):
        object.__setattr__(self, "tonic", normalize_note(self.tonic))
        if self.mode not in SCALES:
            raise ValueError(f"Unknown mode {self.mode!r}; use one of {sorted(SCALES)}")

    @property
    def tonic_pc(self) -> int:
        return note_pc(self.tonic)

    @property
    def letter_idx(self) -> int:
        return LETTERS.index(self.tonic[0])

    @property
    def scale(self) -> tuple:
        return SCALES[self.mode]

    @property
    def name(self) -> str:
        return f"{self.tonic} {self.mode}"

    def key_signature(self) -> int:
        """Number of sharps (positive) or flats (negative), as used by MIDI."""
        table = _MAJOR_FIFTHS if self.mode == "major" else _MINOR_FIFTHS
        if self.tonic in table:
            return table.index(self.tonic) - 7
        # Theoretical key such as D# major: use the enharmonic key with fewest accidentals.
        candidates = [i - 7 for i, n in enumerate(table) if note_pc(n) == self.tonic_pc]
        return min(candidates, key=abs)


# suffix -> (intervals for upper-case numeral, intervals for lower-case, symbol upper, symbol lower)
_QUALITIES = {
    "":      ((0, 4, 7),         (0, 3, 7),         "",      "m"),
    "°":     ((0, 3, 6),         (0, 3, 6),         "dim",   "dim"),
    "+":     ((0, 4, 8),         (0, 4, 8),         "aug",   "aug"),
    "7":     ((0, 4, 7, 10),     (0, 3, 7, 10),     "7",     "m7"),
    "maj7":  ((0, 4, 7, 11),     (0, 3, 7, 11),     "maj7",  "m(maj7)"),
    "°7":    ((0, 3, 6, 9),      (0, 3, 6, 9),      "dim7",  "dim7"),
    "ø7":    ((0, 3, 6, 10),     (0, 3, 6, 10),     "m7b5",  "m7b5"),
    "6":     ((0, 4, 7, 9),      (0, 3, 7, 9),      "6",     "m6"),
    "9":     ((0, 4, 7, 10, 14), (0, 3, 7, 10, 14), "9",     "m9"),
    "maj9":  ((0, 4, 7, 11, 14), (0, 3, 7, 11, 14), "maj9",  "m(maj9)"),
    "add9":  ((0, 4, 7, 14),     (0, 3, 7, 14),     "add9",  "madd9"),
    "sus2":  ((0, 2, 7),         (0, 2, 7),         "sus2",  "sus2"),
    "sus4":  ((0, 5, 7),         (0, 5, 7),         "sus4",  "sus4"),
    "7sus4": ((0, 5, 7, 10),     (0, 5, 7, 10),     "7sus4", "7sus4"),
}
_ALIASES = {"o": "°", "o7": "°7", "dim": "°", "dim7": "°7", "m7b5": "ø7", "M7": "maj7"}

# Generic (letter) step for each interval; a diminished 7th's 9 semitones is a 7th, not a 6th.
_STEP = {0: 0, 2: 1, 3: 2, 4: 2, 5: 3, 6: 4, 7: 4, 8: 4, 9: 5, 10: 6, 11: 6, 14: 1}

_DEGREE = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7}
_RN_RE = re.compile(r"([b#]?)(VII|VI|V|IV|III|II|I|vii|vi|v|iv|iii|ii|i)(.*)")


@dataclass(frozen=True)
class Chord:
    roman: str
    root_pc: int
    root_name: str
    intervals: tuple
    suffix: str
    root_letter: int = 0   # index into LETTERS
    steps: tuple = ()      # letter steps above the root for each interval (3rd = 2, 5th = 4 ...)

    @property
    def symbol(self) -> str:
        return self.root_name + self.suffix

    @property
    def pitch_classes(self) -> tuple:
        return tuple((self.root_pc + i) % 12 for i in self.intervals)

    @property
    def tone_letters(self) -> tuple:
        """(letter_idx, pitch_class) for every chord tone, e.g. E major -> E, G#, B."""
        return tuple(((self.root_letter + st) % 7, pc) for st, pc in zip(self.steps, self.pitch_classes))

    @property
    def fifth_interval(self) -> int:
        for i in (7, 6, 8):
            if i in self.intervals:
                return i
        return 7


def _split_numeral(text: str):
    m = _RN_RE.fullmatch(text)
    if not m:
        raise ValueError(f"Not a Roman numeral chord: {text!r}")
    return m.group(1), m.group(2), m.group(3)


def _root(acc: str, numeral: str, base_letter: int, base_pc: int, scale: tuple):
    d = _DEGREE[numeral.upper()]
    shift = 1 if acc == "#" else -1 if acc == "b" else 0
    return base_letter + d - 1, (base_pc + scale[d - 1] + shift) % 12


def parse_roman(token: str, key: Key) -> Chord:
    """Build a Chord from a Roman-numeral token in the given key."""
    main, _, target = token.partition("/")
    acc, numeral, suffix = _split_numeral(main)
    suffix = _ALIASES.get(suffix, suffix)
    if suffix not in _QUALITIES:
        raise ValueError(f"Unknown chord quality {suffix!r} in {token!r}")

    if target:
        # Secondary chord: numeral is relative to the major scale of the target's root.
        t_acc, t_num, _ = _split_numeral(target)
        t_letter, t_pc = _root(t_acc, t_num, key.letter_idx, key.tonic_pc, key.scale)
        letter, pc = _root(acc, numeral, t_letter, t_pc, MAJOR)
    else:
        letter, pc = _root(acc, numeral, key.letter_idx, key.tonic_pc, key.scale)

    upper_iv, lower_iv, upper_sym, lower_sym = _QUALITIES[suffix]
    is_upper = numeral.isupper()
    intervals = upper_iv if is_upper else lower_iv
    steps = tuple(6 if (suffix == "°7" and i == 9) else _STEP[i] for i in intervals)
    return Chord(
        roman=token,
        root_pc=pc,
        root_name=spell(letter, pc),
        intervals=intervals,
        suffix=upper_sym if is_upper else lower_sym,
        root_letter=letter % 7,
        steps=steps,
    )

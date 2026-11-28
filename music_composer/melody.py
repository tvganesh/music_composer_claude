"""Melody generator: motif-based phrases that follow the chords.

Every section is built from 2-bar units:

  Intro    I  I'          a sparse preview of the chorus hook's shape, ending open
  Verse    A  A'  B  A'   A' = A's first bar + a cadence bar (same start, new ending)
  Chorus   H  H'  C  H'   H is the hook: busier, higher, often with a repeated bar
  Verse 2  the verse motifs with small ornaments, over the verse-2 chords
  Chorus 2 the chorus again (repetition is what makes a hook stick)
  Ending   the hook, then a cadence that lands on the tonic and rings

Pitch rules:
  * notes on strong beats, and long notes, are chord tones
  * other notes move by scale step along the motif's contour (its up/down shape)
  * a non-chord tone is always left by step; after a leap the line steps back
  * phrase ends land on stable notes: an open chord tone mid-section
    (a "half cadence"), the tonic at the very end
  * the scale adapts to each chord, e.g. G# (not G) over E major in A minor
"""
from __future__ import annotations

import bisect
import random
from dataclasses import dataclass, field

from .rhythm import TimeSig, rhythm_cells
from .theory import Chord, Key

EPS = 1e-6

# Register centre for each section, in semitones above the tonic reference note.
REGISTER = {"intro": 5, "verse": 4, "verse2": 4, "chorus": 9, "chorus2": 9, "ending": 7}
UNIT_LIFT = {"A": 0, "B": 2, "H": 0, "C": 3, "I": 0, "END": 0}
VELOCITY = {"intro": 70, "verse": 78, "verse2": 80, "chorus": 92, "chorus2": 95, "ending": 84}

PLANS = {
    "intro":   [("I", None), ("I", "half")],
    "verse":   [("A", None), ("A", "half"), ("B", None), ("A", "full")],
    "verse2":  [("A", None), ("A", "half"), ("B", None), ("A", "full")],
    "chorus":  [("H", None), ("H", "half"), ("C", None), ("H", "full")],
    "chorus2": [("H", None), ("H", "half"), ("C", None), ("H", "full")],
    "ending":  [("H", None), ("END", "final")],
}


@dataclass(frozen=True)
class MelodyStyle:
    """How the melody is shaped; moods.py supplies one per mood. The defaults are
    the original melody, drawn from the random stream in the original order."""
    density: dict = field(default_factory=lambda: {"A": "medium", "B": ("sparse", "busy"), "H": "busy",
                                                   "C": "medium"})  # B: picked at random from the tuple
    shapes: dict = field(default_factory=lambda: {"A": "arch", "B": "rise", "H": "arch", "C": "fall"})
    step_weights: tuple = (0.12, 0.5, 0.24, 0.1, 0.04)  # contour move sizes 0..4 scale steps
    register_shift: int = 0     # semitones added to every section's register centre
    velocity_shift: int = 0
    gate: float = 0.95          # sounding fraction of each note (the last note always rings)
    hook_repeat: float = 0.6    # chance the hook repeats its first bar


DEFAULT_STYLE = MelodyStyle()


@dataclass
class Motif:
    bars: list         # one-bar rhythm cells, cycled across the unit
    cadence_bar: list  # replaces the unit's last bar when the unit ends a phrase
    contour: list      # scale-step moves between successive notes


# ------------------------------------------------------------------ pitch helpers

def tonic_reference(key: Key) -> int:
    """The tonic note the melody is built around (between A3 and Ab4)."""
    pc = key.tonic_pc
    return 60 + pc if pc <= 8 else 48 + pc


def chord_scale(key: Key, chord: Chord) -> set:
    """Key scale with each letter adjusted to agree with the chord's tones."""
    by_letter = {(key.letter_idx + k) % 7: (key.tonic_pc + key.scale[k]) % 12 for k in range(7)}
    for letter, pc in chord.tone_letters:
        by_letter[letter] = pc
    return set(by_letter.values())


def _pitches(pcs, lo, hi) -> list:
    return [p for p in range(lo, hi + 1) if p % 12 in pcs]


def _step(prev: int, move: int, pcs: set, lo: int, hi: int) -> int:
    ladder = _pitches(pcs, lo, hi)
    idx = min(range(len(ladder)), key=lambda i: abs(ladder[i] - prev))
    new = idx + move
    if not 0 <= new < len(ladder):
        new = idx - move  # bounce off the edge of the range
    return ladder[max(0, min(len(ladder) - 1, new))]


def _nearest(pitch: int, pcs: set, lo: int, hi: int, direction: int = 0, avoid: int = None) -> int:
    def cost(p):
        d = p - pitch
        return abs(d) + (0.5 if direction and d * direction < 0 else 0)
    options = [p for p in _pitches(pcs, lo, hi) if p != avoid] or _pitches(pcs, lo, hi)
    return min(options, key=cost)


def _cadence_pitch(prev: int, kind: str, chord: Chord, key: Key, lo: int, hi: int) -> int:
    tones, tonic = set(chord.pitch_classes), key.tonic_pc
    if kind == "final":
        targets = {tonic}
    elif kind == "full":
        targets = {tonic} if tonic in tones else tones
    else:  # half cadence: an open-sounding chord tone, avoiding the tonic
        targets = (tones - {tonic}) or tones
    return _nearest(prev, targets, lo, hi, avoid=prev)  # approach the goal, don't just repeat


# ------------------------------------------------------------------ motifs

def _contour(rng: random.Random, shape: str, n: int = 24, weights=DEFAULT_STYLE.step_weights) -> list:
    moves = []
    for i in range(n):
        if moves and abs(moves[-1]) >= 2 and rng.random() < 0.75:
            moves.append(-1 if moves[-1] > 0 else 1)  # gap fill: step back after a leap
            continue
        size = rng.choices([0, 1, 2, 3, 4], weights)[0]
        frac = i / (n - 1)
        p_up = {"arch": 0.72 if frac < 0.35 else 0.32, "rise": 0.68, "fall": 0.32}[shape]
        moves.append(size if rng.random() < p_up else -size)
    return moves


def _make_motif(cells: dict, density: str, shape: str, rng: random.Random, repeat_bar: float = 0.0,
                weights=DEFAULT_STYLE.step_weights) -> Motif:
    first = rng.choice(cells[density])
    second = first if rng.random() < repeat_bar else rng.choice(cells[density])
    return Motif([first, second], rng.choice(cells["cadence"]), _contour(rng, shape, weights=weights))


def _ornament(motif: Motif, rng: random.Random) -> Motif:
    """Verse-2 variation: split one longer note into two, adding a neighbour note."""
    flat = [(b, j) for b, cell in enumerate(motif.bars) for j, (_, d, rest) in enumerate(cell)]
    note_index, options = 0, []
    for b, j in flat:
        s, d, rest = motif.bars[b][j]
        if not rest:
            if d >= 1 - EPS:
                options.append((b, j, note_index))
            note_index += 1
    if not options:
        return motif
    b, j, n = rng.choice(options)
    s, d, _ = motif.bars[b][j]
    bars = [list(cell) for cell in motif.bars]
    bars[b][j:j + 1] = [(s, d / 2, False), (s + d / 2, d / 2, False)]
    if len(motif.bars) > 1 and motif.bars[0] is motif.bars[1]:
        bars[1 - b] = list(bars[b])  # keep a repeated bar repeated
    m = rng.choice((1, -1))
    c = list(motif.contour)
    nxt = c[n] if n < len(c) else 0
    contour = c[:n] + [m, nxt - m] + c[n + 1:]
    return Motif(bars, motif.cadence_bar, contour)


# ------------------------------------------------------------------ realisation

def _unit_events(motif: Motif, bars: int, bar_q: float, cadence) -> list:
    cells = [motif.bars[i % len(motif.bars)] for i in range(bars)]
    if cadence:
        cells[-1] = motif.cadence_bar
    return [(i * bar_q + s, d, rest) for i, cell in enumerate(cells) for s, d, rest in cell]


def _realize(events, unit_start, chord_at, key, ts, lo, hi, center, contour, cadence, rng) -> list:
    bar_q = ts.bar_quarters
    sounding = [(s, d) for s, d, rest in events if not rest]
    notes, prev, prev2, leave_by_step = [], None, None, False
    for idx, (s, d) in enumerate(sounding):
        t = unit_start + s
        chord = chord_at(t)
        tones = set(chord.pitch_classes)
        pos = s % bar_q
        strong = any(abs(pos - sp) < EPS for sp in ts.strong_positions) or d >= ts.group_quarters - EPS

        if prev is None:
            pitch = _nearest(center, tones, lo, hi)
        else:
            move = contour[(idx - 1) % len(contour)]
            if leave_by_step and abs(move) != 1:
                move = 1 if move > 0 else -1 if move < 0 else rng.choice((1, -1))
            if move == 0 and prev == prev2:
                move = rng.choice((1, -1))  # no more than two repeated notes
            pitch = _step(prev, move, chord_scale(key, chord), lo, hi)
            if strong and pitch % 12 not in tones:
                # Snap to a chord tone, but keep the line moving if the contour says move.
                pitch = _nearest(pitch, tones, lo, hi, direction=(move > 0) - (move < 0),
                                 avoid=prev if move else None)
        if idx == len(sounding) - 1 and cadence:
            pitch = _cadence_pitch(prev if prev is not None else pitch, cadence, chord, key, lo, hi)

        leave_by_step = pitch % 12 not in tones
        notes.append((t, d, pitch, strong))
        prev2, prev = prev, pitch
    return notes


def _split_units(bars: float) -> list:
    whole = int(round(bars))
    units = [2] * (whole // 2) + ([1] if whole % 2 else [])
    return units or [1]


def _plan(kind: str, n: int) -> list:
    template = PLANS[kind]
    if n == len(template):
        return list(template)
    if kind == "ending":
        return [("H", None)] * (n - 1) + [("END", "final")]
    plan = [(template[i % len(template)][0], None) for i in range(n)]
    if n >= 4:
        plan[n // 2 - 1] = (plan[n // 2 - 1][0], "half")
    plan[-1] = (plan[-1][0], template[-1][1])
    return plan


def generate_melody(sections: list, key: Key, ts: TimeSig, rng: random.Random,
                    style: MelodyStyle = DEFAULT_STYLE) -> list:
    """Returns (start, duration, pitch, velocity) tuples for the whole song."""
    cells = rhythm_cells(ts)
    bar_q = ts.bar_quarters
    dens, shape, w = style.density, style.shapes, style.step_weights

    hook = _make_motif(cells, dens["H"], shape["H"], rng, repeat_bar=style.hook_repeat, weights=w)
    motifs = {
        "A": _make_motif(cells, dens["A"], shape["A"], rng, weights=w),
        "B": _make_motif(cells, rng.choice(dens["B"]), shape["B"], rng, weights=w),
        "H": hook,
        "C": _make_motif(cells, dens["C"], shape["C"], rng, weights=w),
        "I": Motif([rng.choice(cells["sparse"]), rng.choice(cells["sparse"])],
                   rng.choice(cells["cadence"]), hook.contour),
        "END": Motif([rng.choice(cells["medium"])], [(0.0, bar_q, False)], _contour(rng, "fall", weights=w)),
    }
    verse2_motifs = {"A": _ornament(motifs["A"], rng), "B": _ornament(motifs["B"], rng)}

    slots = [(sl.start, sl.chord) for sec in sections for sl in sec.slots]
    starts = [s for s, _ in slots]

    def chord_at(t):
        return slots[max(0, bisect.bisect_right(starts, t + EPS) - 1)][1]

    ref = tonic_reference(key)
    lo, hi = ref - 3, ref + 17
    out = []
    for sec in sections:
        units = _split_units(sec.bars)
        t = sec.start
        for (label, cadence), unit_bars in zip(_plan(sec.kind, len(units)), units):
            motif = verse2_motifs.get(label, motifs[label]) if sec.kind == "verse2" else motifs[label]
            center = ref + REGISTER[sec.kind] + UNIT_LIFT[label] + style.register_shift
            events = _unit_events(motif, unit_bars, bar_q, cadence)
            for start, dur, pitch, strong in _realize(events, t, chord_at, key, ts, lo, hi,
                                                      center, motif.contour, cadence, rng):
                vel = VELOCITY[sec.kind] + (6 if strong else 0) + rng.randint(-4, 4) + style.velocity_shift
                out.append([start, dur * style.gate, pitch, max(1, min(127, vel))])
            t += unit_bars * bar_q

    if out:  # let the final note ring to the end of the song
        last = sections[-1]
        out[-1][1] = last.start + last.bars * bar_q - out[-1][0]
    return [tuple(n) for n in out]

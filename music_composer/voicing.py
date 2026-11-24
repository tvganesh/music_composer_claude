"""Chord voicing with simple voice leading.

The right hand plays the chord in close position below the melody; of all
inversions that fit the register, we pick the one that moves least from the
previous chord (with a small pull toward the centre so the part doesn't drift).
The left hand plays the root, so Logic's chord detection and Session Players
always read the intended chord.
"""
from __future__ import annotations

from .theory import Chord

CHORD_LOW, CHORD_HIGH, CHORD_CENTER = 48, 67, 58   # C3..G4, centred around Bb3
ROOT_OCTAVE_BASE = 36                              # left-hand root in C2..B2


def _chord_pcs(chord: Chord, rootless: bool = False) -> list:
    pcs = []
    for pc in chord.pitch_classes:
        if pc not in pcs:
            pcs.append(pc)
    if len(pcs) > 4:
        # 9th chords keep 4 voices. With the root in the left hand the right hand
        # plays 3-5-7-9 (Am9 -> C E G B), the usual piano voicing; without it,
        # the root stays (so Logic still detects the chord) and the fifth goes.
        drop = chord.root_pc if rootless else (chord.root_pc + chord.fifth_interval) % 12
        pcs = [p for p in pcs if p != drop][:4]
    return pcs


def _candidates(pcs: list) -> list:
    """Close-position voicings: each chord tone in turn as the bottom note, the
    others stacked as tightly as possible above it (so a 9th chord's 9th sits
    a step above the root rather than an octave and a step)."""
    out = []
    for bottom in pcs:
        order = [bottom] + sorted((pc for pc in pcs if pc != bottom), key=lambda pc: (pc - bottom) % 12)
        for octave in range(2, 8):
            notes = [order[0] + 12 * octave]
            for pc in order[1:]:
                notes.append(notes[-1] + ((pc - notes[-1]) % 12 or 12))
            if notes[0] >= CHORD_LOW and notes[-1] <= CHORD_HIGH:
                out.append(notes)
    return out


def _movement(a: list, b: list) -> int:
    return sum(min(abs(x - y) for y in b) for x in a) + sum(min(abs(y - x) for x in a) for y in b)


def voice_chord(chord: Chord, previous: list = None, rootless: bool = False) -> list:
    """rootless=True when the left hand plays the root, so 9th chords can leave it out."""
    candidates = _candidates(_chord_pcs(chord, rootless))
    if not candidates:
        raise ValueError(f"No voicing fits the register for {chord.symbol}")

    def drift(notes):
        return abs(sum(notes) / len(notes) - CHORD_CENTER)

    if previous is None:
        return min(candidates, key=drift)
    return min(candidates, key=lambda n: _movement(previous, n) + 0.5 * drift(n))


ROOT_POSITION_LOW = 48   # "Chords only" style: the root sits in C3..B3


def voice_root_position(chord: Chord) -> list:
    """Close root-position chord with the root in C3..B3 (A3 C4 E4, E3 G#3 B3 D4).
    Used by the "Chords only" style: the same layout as a hand-entered chord
    track, which Logic's Arpeggiator and chord detection read directly."""
    root = ROOT_POSITION_LOW + (chord.root_pc - ROOT_POSITION_LOW) % 12
    notes = [root]
    for pc in _chord_pcs(chord)[1:]:
        notes.append(notes[-1] + ((pc - notes[-1]) % 12 or 12))
    return notes


def left_hand_root(chord: Chord) -> int:
    return ROOT_OCTAVE_BASE + chord.root_pc

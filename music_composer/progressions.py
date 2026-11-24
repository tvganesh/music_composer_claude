"""Chord progression library, organised by level -> mode -> section.

Each progression is a space-separated string of Roman numerals. A chord lasts
one bar unless it carries a length suffix, e.g. "I:2" (two bars) or "V:0.5".

Verse 2 reuses the verse progression; its second half changes one chord so it
sounds familiar but not identical. At Basic that is a diatonic substitution from
SUBSTITUTIONS; at Intermediate and Advanced it is modal interchange (a chord
borrowed from the parallel key, MODAL_SUBSTITUTIONS) whenever the verse allows.
Chorus 2 repeats the chorus progression.
"""
from __future__ import annotations

import random
import re

PROGRESSIONS = {
    "basic": {
        "major": {
            "intro":  ["I IV I V", "vi IV I V", "I vi IV V", "IV I IV V"],
            "verse":  ["I vi IV V", "I IV vi V", "I iii IV V", "I vi ii V"],
            "chorus": ["IV V iii vi", "IV I V vi", "vi IV I V", "IV V I vi"],
            "ending": ["IV V I:2", "ii V I:2", "vi IV V I"],
        },
        "minor": {
            # Upper-case V is the harmonic-minor dominant (raised 7th).
            "intro":  ["i VI III VII", "i iv i V", "i VII VI V", "i VI iv V"],
            "verse":  ["i VI III VII", "i iv VII III", "i VII VI V", "i VI iv V"],
            "chorus": ["VI VII i V", "VI III VII V", "iv VII III VI", "VI iv i V"],
            "ending": ["iv V i:2", "VI VII i:2", "VI iv V i"],
        },
    },
    # Sevenths, ii-V-I, sus chords and simple modal changes: borrowed iv and bVII
    # in major (Mixolydian colour), the Dorian IV and v7 in minor.
    "intermediate": {
        "major": {
            "intro":  ["Imaj7 IVmaj7 Imaj7 V7sus4", "vi7 IVmaj7 Imaj7 V7", "Imaj7 iii7 IVmaj7 Vsus4",
                       "IVmaj7 Imaj7 ii7 V7"],
            "verse":  ["Imaj7 vi7 ii7 V7", "Imaj7 iii7 IVmaj7 V7sus4", "Imaj7 IVmaj7 vi7 V7",
                       "Isus2 vi7 IVmaj7 V7"],
            "chorus": ["IVmaj7 V7 iii7 vi7", "IVmaj7 Imaj7 bVII IV", "ii7 V7 Imaj7 vi7",
                       "IVmaj7 iv Imaj7 V7"],
            "ending": ["ii7 V7 Imaj7:2", "IVmaj7 iv Imaj7:2", "ii7 V7sus4 V7 Imaj7:2"],
        },
        "minor": {
            "intro":  ["i7 VImaj7 IIImaj7 VII7", "i7 iv7 i7 V7", "i7 IV i7 IV", "VImaj7 VII7 i7 V7sus4"],
            "verse":  ["i7 iv7 VII7 IIImaj7", "i7 VImaj7 iiø7 V7", "i7 IV VImaj7 V7", "i7 v7 VImaj7 VII7"],
            "chorus": ["VImaj7 VII7 i7 V7", "iv7 VII7 IIImaj7 VImaj7", "VImaj7 iv7 i7 V7",
                       "IIImaj7 VII7 VImaj7 V7sus4"],
            "ending": ["iiø7 V7 i:2", "iv7 V7sus4 V7 i:2", "VImaj7 VII7 i:2"],
        },
    },
    # Modal interchange (bVI, bVII, iv6), secondary dominants (V7/vi, V7/ii, V7/iv),
    # diminished passing chords (#i°7, #vii°7), 9ths and add9, the Neapolitan (bII),
    # the minor line cliché (i, i(maj7), i7, i6) and the Picardy third (minor song ending on I).
    "advanced": {
        "major": {
            "intro":  ["Imaj9 IVmaj7 bVImaj7 V7sus4", "Imaj7 V7/vi vi7 IVmaj7", "IVmaj9 iv6 Imaj7 V7sus4",
                       "Iadd9 bVII IVadd9 V7sus4"],
            "verse":  ["Imaj7 V7/vi vi7 ii7:0.5 V7:0.5", "Imaj7 #i°7 ii7 V7", "Imaj9 vi7 bVImaj7 V7sus4",
                       "Imaj7 iii7 V7/ii ii7:0.5 V7:0.5"],
            "chorus": ["IVmaj7 V7/vi vi7 bVII9", "IVmaj7 iv6 iii7 vi7", "ii7 V7 iii7 V7/ii",
                       "bVImaj7 bVII9 Imaj7 V7sus4"],
            "ending": ["bVImaj7 bVII Imaj9:2", "IVmaj7 iv6 Imaj9:2", "V7/V V7sus4 V7 Imaj9:2"],
        },
        "minor": {
            "intro":  ["i imaj7 i7 i6", "i9 VImaj7 IIImaj7 VII7", "i7 bII i7 V7sus4", "VImaj7 IV i9 V7"],
            "verse":  ["i imaj7 i7 i6", "i7 V7/iv iv7 V7", "i7 iv7 bII V7", "i9 VImaj7 iiø7 V7"],
            "chorus": ["VImaj7 VII7 i9 V7", "iv7 VII9 IIImaj7 V7/iv", "VImaj7 IV i7 V7",
                       "i7 bII VImaj7 #vii°7"],
            "ending": ["iv6 V7 I:2", "bII V7 i:2", "VImaj7 #vii°7 i:2", "iiø7 V7 I:2"],
        },
    },
}

LEVEL_INFO = {
    "basic": "Triads from the key, with the major V in minor keys.",
    "intermediate": "Seventh chords, ii–V–I, sus chords and modal colour: borrowed iv and ♭VII in major, "
                    "the Dorian IV in minor. Verse 2 borrows a chord from the parallel key.",
    "advanced": "Modal interchange (♭VI, ♭VII, iv6), secondary dominants, diminished passing chords, "
                "9ths, the Neapolitan ♭II, the minor line cliché and the Picardy third. "
                "Verse 2 borrows a chord from the parallel key.",
}

# Chords that can stand in for each other (shared tones / same function).
SUBSTITUTIONS = {
    "basic": {
        "major": {"I": ["vi"], "ii": ["IV"], "iii": ["vi"], "IV": ["ii"], "V": ["iii"], "vi": ["iii", "IV"]},
        "minor": {"i": ["III"], "III": ["VI"], "iv": ["VI"], "VI": ["iv", "III"], "VII": ["v"]},
    },
    "intermediate": {
        "major": {"Imaj7": ["vi7"], "vi7": ["iii7", "IVmaj7"], "iii7": ["vi7"], "ii7": ["IVmaj7"],
                  "IVmaj7": ["ii7", "iv"], "V7": ["V7sus4"], "Isus2": ["Imaj7"]},
        "minor": {"i7": ["IIImaj7"], "iv7": ["IV", "iiø7"], "VII7": ["v7"], "IIImaj7": ["VImaj7"],
                  "VImaj7": ["iv7", "IIImaj7"], "iiø7": ["iv7"], "v7": ["VII7"], "IV": ["iv7"]},
    },
    "advanced": {
        "major": {"V7/vi": ["iii7"], "vi7": ["bVImaj7", "iii7"], "#i°7": ["V7/ii"], "ii7": ["IVmaj7"],
                  "iii7": ["V7/vi"], "V7/ii": ["#i°7"], "IVmaj7": ["iv6", "ii7"], "bVImaj7": ["iv6"]},
        "minor": {"i7": ["V7/iv", "VImaj7"], "V7/iv": ["VII7"], "iv7": ["bII", "iiø7"],
                  "bII": ["iiø7"], "VImaj7": ["IV", "bII"], "iiø7": ["bII"]},
    },
}

# Modal interchange for Verse 2: the same chord function, borrowed from the parallel key.
#   major <- parallel minor: vi7 -> bVImaj7 or iv7, ii7 -> iiø7, iii7 -> bIIImaj7, IVmaj7 -> iv7
#                            (in C: Am7 -> Abmaj7/Fm7, Dm7 -> Dm7b5, Em7 -> Ebmaj7, Fmaj7 -> Fm7)
#   minor <- Dorian / melodic and harmonic minor / Phrygian:
#            iv7 -> IV7, iiø7 -> ii7, v7 -> V7, VImaj7 -> bIImaj7
#            (in D minor: Gm7 -> G7, Em7b5 -> Em7, Am7 -> A7, Bbmaj7 -> Ebmaj7)
MODAL_SUBSTITUTIONS = {
    "major": {"vi7": ["bVImaj7", "iv7"], "ii7": ["iiø7"], "iii7": ["bIIImaj7"], "IVmaj7": ["iv7"]},
    "minor": {"iv7": ["IV7"], "iiø7": ["ii7"], "v7": ["V7"], "VImaj7": ["bIImaj7"]},
}
MODAL_LEVELS = ("intermediate", "advanced")

LEVELS = tuple(PROGRESSIONS)


def parse_progression(spec: str) -> list:
    """'IV V I:2' -> [('IV', 1.0), ('V', 1.0), ('I', 2.0)]"""
    out = []
    for token in spec.split():
        roman, _, bars = token.partition(":")
        out.append((roman, float(bars) if bars else 1.0))
    return out


def _degree(token: str) -> str:
    """'bVImaj7' -> 'bVI', 'iv7' -> 'IV': the chord's root as a scale degree."""
    m = re.match(r"([b#]?)(VII|VI|V|IV|III|II|I)", token, re.IGNORECASE)
    return m.group(1) + m.group(2).upper() if m else token


def substitute(prog: list, table: dict, rng: random.Random, keep_resolutions: bool = False) -> list:
    """Replace one inner chord (not the first or last) with a substitute that
    doesn't duplicate its neighbours. Returns the progression unchanged if no
    substitution is possible. keep_resolutions: the chord a secondary dominant
    resolves to keeps its root (E7 -> Am7 may become E7 -> A7, never E7 -> Fm7)."""
    options = []
    for i in range(1, len(prog) - 1):
        roman, bars = prog[i]
        resolves_here = keep_resolutions and "/" in prog[i - 1][0]
        for alt in table.get(roman, []):
            if resolves_here and _degree(alt) != _degree(roman):
                continue  # A7 -> Dm7 may become A7 -> D7, but not A7 -> something else
            if alt not in (prog[i - 1][0], prog[i + 1][0]):
                options.append((i, alt, bars))
    if not options:
        return list(prog)
    i, alt, bars = rng.choice(options)
    new = list(prog)
    new[i] = (alt, bars)
    return new


def fill_bars(prog: list, bars: float) -> list:
    """Repeat a progression until it covers `bars` bars (truncating the last chord)."""
    out, total = [], 0.0
    while total < bars - 1e-9:
        for roman, length in prog:
            if total >= bars - 1e-9:
                break
            length = min(length, bars - total)
            out.append((roman, length))
            total += length
    return out

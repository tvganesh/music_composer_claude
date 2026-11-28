"""Moods: a preset over the generator's musical choices.

A mood sets
  * the chord progressions (its own library, per key mode and level tier),
  * the Verse 2 substitutions that go with them,
  * the melody's shape, density, leaps, register, articulation and loudness,
  * how loud the chords are,
  * the patterns of the optional Bass and Drums guide tracks (see groove.py),
  * a suggested scale and tempo (the UI and CLI apply them; you can override).

Mood "none" is the original behaviour: the level's progressions and the default
melody style, so every existing seed gives exactly the same song.

Progressions follow the rules in progressions.py ("I:2" lasts two bars).
Level "basic" uses the mood's "basic" tier (triads); "intermediate" and
"advanced" use its "rich" tier (sevenths and colour chords).
"""
from __future__ import annotations

from .melody import DEFAULT_STYLE, MelodyStyle

NONE = "none"


def _tier(level: str) -> str:
    return "basic" if level == "basic" else "rich"


MOODS = {
    NONE: {
        "label": "None",
        "hint": "No mood: the level's own chord library and the standard melody.",
        "scale": None, "tempo": None,
        "melody": DEFAULT_STYLE,
        "chord_velocity": 0,
        "bass": "root-fifth",
        "drums": "straight",
    },

    # Bright major chords, rising lines with some leaps, detached notes, brisk tempo.
    "happy": {
        "label": "Happy",
        "hint": "Bright major harmony, rising and bouncy melody, brisk tempo. In minor keys it "
                "leans on the Dorian IV and ends on a major tonic.",
        "scale": "major", "tempo": 120,
        "progressions": {
            "major": {
                "basic": {
                    "intro":  ["I IV I V", "I V IV V", "I IV V IV"],
                    "verse":  ["I V vi IV", "I IV V IV", "I vi IV V", "I IV ii V"],
                    "chorus": ["IV V I vi", "I V IV V", "IV I V I"],
                    "ending": ["IV V I:2", "ii V I:2", "IV I V I"],
                },
                "rich": {
                    "intro":  ["Iadd9 IVadd9 Iadd9 V7sus4", "Imaj7 IVmaj7 Imaj7 V7"],
                    "verse":  ["Iadd9 V vi7 IVadd9", "Imaj7 IVmaj7 ii7 V7", "Imaj7 V7/vi vi7 IVmaj7",
                               "Iadd9 iii7 IVmaj7 V7sus4"],
                    "chorus": ["IVmaj7 V7 iii7 vi7", "IVadd9 V Iadd9 vi7", "ii7 V7 Imaj7 IVmaj7"],
                    "ending": ["ii7 V7 Iadd9:2", "IVmaj7 V7sus4 Imaj7:2", "IVadd9 V7 Imaj9:2"],
                },
            },
            "minor": {
                "basic": {
                    "intro":  ["i IV i IV", "III VII i IV"],
                    "verse":  ["i IV VII III", "i VII VI VII", "i IV III VII", "III VII i IV"],
                    "chorus": ["III VII IV i", "VI VII III IV", "III VII VI VII"],
                    "ending": ["VI VII I:2", "IV V I:2", "VII IV i:2"],
                },
                "rich": {
                    "intro":  ["i7 IV i7 IV", "IIImaj7 VII i7 IV"],
                    "verse":  ["i7 IV VII IIImaj7", "i9 IV9 VIIadd9 IIImaj7", "i7 v7 IV VII",
                               "IIImaj7 VII7 i7 IV"],
                    "chorus": ["IIImaj7 VII IV7 i7", "VImaj7 VII7 IIImaj7 IV", "IIIadd9 VII IV i7"],
                    "ending": ["VImaj7 VII7 Imaj7:2", "iv7 V7 I:2", "IV7 VII Iadd9:2"],
                },
            },
        },
        "substitutions": {
            "major": {"V": ["iii"], "vi": ["IV", "iii"], "IV": ["ii", "vi"], "ii": ["IV"],
                      "vi7": ["iii7"], "IVadd9": ["ii7"], "IVmaj7": ["ii7", "IVadd9"], "ii7": ["IVmaj7"],
                      "iii7": ["V7/vi"], "V7/vi": ["iii7"]},
            "minor": {"IV": ["VI"], "VII": ["v"], "VI": ["IV"], "i": ["III"],
                      "IV9": ["IV7"], "VIIadd9": ["VII7"], "v7": ["VII7"], "VII7": ["v7"], "i7": ["IIImaj7"]},
        },
        "melody": MelodyStyle(
            density={"A": "medium", "B": ("busy",), "H": "busy", "C": "medium"},
            shapes={"A": "arch", "B": "rise", "H": "rise", "C": "arch"},
            step_weights=(0.10, 0.44, 0.28, 0.13, 0.05),
            register_shift=2, velocity_shift=4, gate=0.82, hook_repeat=0.7,
        ),
        "chord_velocity": 2,
        "bass": "bounce",
        "drums": "pop",
    },

    # Minor colour, falling stepwise lines, sparse and legato, slow and soft.
    "sad": {
        "label": "Sad",
        "hint": "Minor colour (vi, borrowed iv in major), falling stepwise melody, long soft notes, "
                "slow half-time feel.",
        "scale": "minor", "tempo": 72,
        "progressions": {
            "major": {
                "basic": {
                    "intro":  ["vi IV I V", "I iii vi IV", "IV iv I V"],
                    "verse":  ["vi IV I V", "I iii vi IV", "vi iii IV I", "I V vi iii"],
                    "chorus": ["IV I V vi", "IV iv I vi", "ii V vi IV"],
                    "ending": ["IV iv I:2", "vi IV I:2", "ii iv I:2"],
                },
                "rich": {
                    "intro":  ["vi7 IVmaj7 Imaj7 V7sus4", "IVmaj7 iv6 Imaj7 V7sus4"],
                    "verse":  ["vi7 IVmaj7 Imaj7 V7sus4", "Imaj7 iii7 vi7 IVmaj7", "vi7 iii7 IVmaj7 Imaj7",
                               "Imaj7 V7/vi vi7 iv6"],
                    "chorus": ["IVmaj7 Imaj7 V7 vi7", "IVmaj7 iv6 iii7 vi7", "ii7 V7 vi7 IVmaj7"],
                    "ending": ["IVmaj7 iv6 Imaj7:2", "ii7 iv6 Imaj7:2", "vi7 IVmaj7 iv6 Imaj7"],
                },
            },
            "minor": {
                "basic": {
                    "intro":  ["i VI iv V", "i iv VI V"],
                    "verse":  ["i VI III VII", "i iv VI V", "i VII VI V", "i v iv V"],
                    "chorus": ["VI III VII i", "iv i VI V", "VI iv i V"],
                    "ending": ["iv V i:2", "VI iv V i", "iv VI i:2"],
                },
                "rich": {
                    "intro":  ["i imaj7 i7 i6", "i7 VImaj7 iv7 V7sus4"],
                    "verse":  ["i7 VImaj7 IIImaj7 VII7", "i imaj7 i7 i6", "i7 iv7 VImaj7 V7",
                               "i9 iv7 VII7 IIImaj7"],
                    "chorus": ["VImaj7 IIImaj7 VII7 i7", "iv7 i7 VImaj7 V7", "VImaj7 iv7 i9 V7sus4"],
                    "ending": ["iv6 V7 i:2", "iiø7 V7 i:2", "VImaj7 iv6 i:2"],
                },
            },
        },
        "substitutions": {
            "major": {"IV": ["ii", "iv"], "I": ["vi"], "iii": ["V"], "vi": ["iii"], "V": ["iii"],
                      "IVmaj7": ["ii7", "iv6"], "Imaj7": ["vi7"], "iii7": ["V7/vi"], "vi7": ["iii7"],
                      "V7/vi": ["iii7"]},
            "minor": {"VI": ["iv", "III"], "III": ["VI"], "iv": ["VI"], "VII": ["v"], "v": ["VII"],
                      "VImaj7": ["iv7"], "IIImaj7": ["VImaj7"], "imaj7": ["i"], "i7": ["imaj7", "VImaj7"],
                      "iv7": ["iiø7", "VImaj7"]},
        },
        "melody": MelodyStyle(
            density={"A": "medium", "B": ("sparse",), "H": "medium", "C": "sparse"},
            shapes={"A": "fall", "B": "arch", "H": "arch", "C": "fall"},
            step_weights=(0.10, 0.62, 0.20, 0.06, 0.02),
            register_shift=-3, velocity_shift=-10, gate=0.99, hook_repeat=0.5,
        ),
        "chord_velocity": -8,
        "bass": "walk",
        "drums": "halftime",
    },

    # Phrygian bII, rock bVI-bVII-I, repeated notes and leaps, short loud notes, fast.
    "angry": {
        "label": "Angry",
        "hint": "Dark, driving harmony (Phrygian ♭II, ♭VI–♭VII–I), riff-like melody with repeated notes "
                "and leaps, short loud notes, fast tempo.",
        "scale": "minor", "tempo": 140,
        "progressions": {
            "major": {
                "basic": {
                    "intro":  ["I bVII I bVII", "I bVI bVII I", "I bIII IV I"],
                    "verse":  ["I bVII IV I", "I bVI bVII I", "I bIII bVII IV", "I bII I bVII"],
                    "chorus": ["bVI bVII I bVII", "IV bVII I bIII", "bIII IV bVI bVII"],
                    "ending": ["IV bVII I:2", "bVI bVII I:2", "bIII IV I:2"],
                },
                "rich": {
                    "intro":  ["I7 bVII I7 bVII", "I7 bVI bVII I7"],
                    "verse":  ["I7 bVII IV7 I7", "I7 bVI bVII7 I7", "Isus4 bIII bVII IV7", "I7 bII I7 bVII"],
                    "chorus": ["bVImaj7 bVII7 I7 bVII", "IV7 bVII I7 bIII", "bIII IV7 bVI bVII7"],
                    "ending": ["bVI bVII7 I7:2", "IV7 bVII7 I:2", "bII bVII Isus4 I"],
                },
            },
            "minor": {
                "basic": {
                    "intro":  ["i bII i bII", "i VI VII i", "i iv V i"],
                    "verse":  ["i bII i VII", "i VI VII i", "i iv bII V", "i VII VI V"],
                    "chorus": ["VI VII i V", "i bII VI V", "iv VI bII V"],
                    "ending": ["bII V i:2", "VI VII i:2", "iv bII i:2"],
                },
                "rich": {
                    "intro":  ["i7 bII i7 bII", "i VImaj7 VII7 i", "i iv7 V7 i"],
                    "verse":  ["i7 bII i7 VII7", "i VImaj7 VII7 i7", "i7 iv7 bIImaj7 V7", "i V7/iv iv7 V7"],
                    "chorus": ["VImaj7 VII7 i7 V7", "i7 bII VImaj7 V7", "iv7 VImaj7 bII V7"],
                    "ending": ["bII V7 i:2", "VImaj7 VII7 i:2", "iv7 bII V7 i"],
                },
            },
        },
        "substitutions": {
            "major": {"bVII": ["bIII"], "IV": ["bVI"], "bVI": ["IV"], "bIII": ["bVI"], "bII": ["bVII"],
                      "I": ["bVI"],
                      "IV7": ["bVI"], "bVII7": ["bIII"], "I7": ["bVI"]},
            "minor": {"bII": ["VI"], "i": ["VI"], "VI": ["iv", "bII"], "VII": ["v"], "iv": ["bII"],
                      "VImaj7": ["iv7"], "VII7": ["bII"], "i7": ["VImaj7"], "iv7": ["bII"],
                      "bIImaj7": ["VImaj7"], "V7/iv": ["VII7"]},
        },
        "melody": MelodyStyle(
            density={"A": "busy", "B": ("busy",), "H": "busy", "C": "medium"},
            shapes={"A": "arch", "B": "rise", "H": "arch", "C": "fall"},
            step_weights=(0.28, 0.30, 0.20, 0.14, 0.08),
            register_shift=0, velocity_shift=14, gate=0.6, hook_repeat=0.9,
        ),
        "chord_velocity": 12,
        "bass": "drive",
        "drums": "drive",
    },

    # Chromatic mediants, augmented and minor-major chords, high sparse lines, slow and very soft.
    "eerie": {
        "label": "Eerie",
        "hint": "Haunting chromatic harmony (chromatic mediants, augmented and minor-major chords), "
                "a thin, sparse melody, a low pedal bass and ritual-like percussion, slow and quiet.",
        "scale": "minor", "tempo": 64,
        "progressions": {
            "major": {
                "basic": {
                    "intro":  ["I bVI I bVI", "I bIII bVI I"],
                    "verse":  ["I bVI iv I", "I I+ vi bVI", "I bIII bVI iv", "I bII bVI iv"],
                    "chorus": ["bVI iv I I+", "bIII bVI iv I", "iv bVI bIII I+"],
                    "ending": ["iv bVI I:2", "bVI bII I:2", "iv bII I:2"],
                },
                "rich": {
                    "intro":  ["I bVImaj7 I bVImaj7", "I #iv° iv6 I"],
                    "verse":  ["I bVImaj7 iv6 I", "I I+ vi7 bVImaj7", "Imaj7 bIIImaj7 bVImaj7 iv6",
                               "I #iv°7 iv6 I"],
                    "chorus": ["bVImaj7 iv6 I I+", "bIIImaj7 bVImaj7 iv6 I", "iv6 bVImaj7 bII I+"],
                    "ending": ["bVImaj7 bII I:2", "iv6 bII I:2", "iv6 #iv°7 I:2"],
                },
            },
            "minor": {
                "basic": {
                    "intro":  ["i vi i vi", "i iv i bII"],
                    "verse":  ["i III+ VI iv", "i vi iv i", "i bII i V", "i iv vi V"],
                    "chorus": ["VI vi i V", "iv vi bII V", "i III+ iv V"],
                    "ending": ["iv vi i:2", "bII V i:2", "VI vi i:2"],
                },
                "rich": {
                    "intro":  ["i imaj7 i6 imaj7", "imaj9 VImaj7 imaj9 bII"],
                    "verse":  ["i imaj7 VImaj7 iv6", "imaj7 III+ vi iiø7", "i9 vi iv6 V7", "i bII imaj7 #vii°7"],
                    "chorus": ["VImaj7 vi imaj7 V7", "iv6 vi bII V7", "iiø7 III+ imaj7 #vii°7"],
                    "ending": ["vi bII i:2", "iiø7 V7 imaj7:2", "iv6 #vii°7 i:2"],
                },
            },
        },
        "substitutions": {
            "major": {"bVI": ["bIII", "bII"], "iv": ["bVI", "bII"], "I+": ["bIII"], "vi": ["iv"], "bIII": ["bVI"],
                      "bII": ["bIII"],
                      "bVImaj7": ["bIIImaj7", "bII"], "iv6": ["bVImaj7"], "vi7": ["bIIImaj7"],
                      "bIIImaj7": ["bVImaj7"], "#iv°7": ["bII"]},
            "minor": {"III+": ["vi"], "VI": ["vi"], "vi": ["VI", "bII"], "iv": ["vi"], "bII": ["vi"],
                      "i": ["vi"],
                      "imaj7": ["i6"], "VImaj7": ["vi"], "iv6": ["bII"],
                      "iiø7": ["iv6"], "#vii°7": ["V7"]},
        },
        "melody": MelodyStyle(
            density={"A": "sparse", "B": ("sparse",), "H": "medium", "C": "sparse"},
            shapes={"A": "fall", "B": "fall", "H": "arch", "C": "fall"},
            step_weights=(0.20, 0.60, 0.12, 0.06, 0.02),
            register_shift=5, velocity_shift=-16, gate=0.99, hook_repeat=0.8,
        ),
        "chord_velocity": -14,
        "bass": "pedal",
        "drums": "ritual",
    },
}

MOOD_IDS = tuple(MOODS)


def check_mood(mood) -> str:
    mood = NONE if mood in (None, "") else str(mood)
    if mood not in MOODS:
        raise ValueError(f"Unknown mood {mood!r}; use one of {', '.join(MOOD_IDS)}")
    return mood


def mood_progressions(mood: str, level: str, mode: str):
    """The mood's section -> progressions table, or None to use the level's own."""
    m = MOODS[mood]
    return m["progressions"][mode][_tier(level)] if "progressions" in m else None


def mood_substitutions(mood: str, mode: str) -> dict:
    return MOODS[mood]["substitutions"][mode]

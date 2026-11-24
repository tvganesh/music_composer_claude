"""Command-line entry point.

    python3 -m music_composer --key D --scale minor --tempo 92 --time 6/8 --level basic
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .arranger import CHORD_STYLES, DEFAULT_CHORD_STYLE, DEFAULT_FORM, SECTION_KINDS, STYLE_ALIASES, compose
from .midi_export import write_midi
from .progressions import LEVELS
from .rhythm import TimeSig
from .sheet import chord_sheet, file_stem, song_json, song_title
from .theory import Key


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python3 -m music_composer",
        description="Generate a song (chord sequence + melody) as a two-track MIDI file for Logic Pro.",
    )
    p.add_argument("--key", default="C", help="tonic note, e.g. C, F#, Bb (default C)")
    p.add_argument("--scale", choices=["major", "minor"], default="major")
    p.add_argument("--tempo", type=int, default=100, help="BPM (default 100)")
    p.add_argument("--time", default="4/4", help="time signature: 4/4, 3/4, 6/8 (others use a generic feel)")
    p.add_argument("--level", choices=["basic", "intermediate", "advanced"], default="basic",
                   help="basic: triads; intermediate: sevenths, ii-V-I, sus, borrowed iv/bVII; "
                        "advanced: modal interchange, secondary dominants, diminished, Neapolitan, Picardy")
    p.add_argument("--seed", type=int, help="repeatable result; omit for a random song")
    p.add_argument("--form", default=",".join(DEFAULT_FORM),
                   help=f"comma-separated sections from: {', '.join(SECTION_KINDS)} "
                        f"(default {','.join(DEFAULT_FORM)})")
    p.add_argument("--chord-style", choices=CHORD_STYLES + tuple(STYLE_ALIASES), default=DEFAULT_CHORD_STYLE,
                   help="chords: held root-position chords only, best for Logic's Arpeggiator (default); "
                        "block: held chords with a low root in the left hand; "
                        "arpeggio: broken chords written into the MIDI")
    p.add_argument("--out", default="output", help="output folder (default ./output)")
    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.level not in LEVELS:
        parser.error(f"level '{args.level}' isn't built yet; available now: {', '.join(LEVELS)}")
    if not 30 <= args.tempo <= 300:
        parser.error("tempo must be between 30 and 300 BPM")
    try:
        key = Key(args.key, args.scale)
        ts = TimeSig.parse(args.time)
        form = tuple(s.strip().lower() for s in args.form.split(",") if s.strip())
        song = compose(key, args.tempo, ts, args.level, args.seed, form, args.chord_style)
    except ValueError as e:
        parser.error(str(e))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = file_stem(song)
    sheet = chord_sheet(song)
    mid = write_midi(song, out / f"{stem}.mid", song_title(song))
    (out / f"{stem}.txt").write_text(sheet + "\n", encoding="utf-8")
    (out / f"{stem}.json").write_text(song_json(song) + "\n", encoding="utf-8")

    print(sheet)
    print(f"MIDI:        {mid}")
    print(f"Chord sheet: {out / (stem + '.txt')}")
    print(f"JSON:        {out / (stem + '.json')}")
    return 0

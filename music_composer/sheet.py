"""Human-readable chord sheet and a JSON description of the song."""
from __future__ import annotations

import json
import math

EPS = 1e-6


def _mood_label(song) -> str:
    return "" if song.mood == "none" else song.mood


def song_title(song) -> str:
    mood = f", {_mood_label(song)}" if _mood_label(song) else ""
    return f"{song.key.name}, {song.tempo} BPM, {song.timesig.label}, {song.level}{mood}"


def file_stem(song) -> str:
    ts = song.timesig
    mood = f"_{_mood_label(song)}" if _mood_label(song) else ""
    extras = "".join(f"_{name.lower()}" for name in ("Bass", "Drums") if song.has_track(name))
    return (f"{song.key.tonic.replace('#', 's')}_{song.key.mode}_{song.tempo}bpm_"
            f"{ts.num}-{ts.den}_{song.level}{mood}_seed{song.seed}"
            + ("" if song.chord_style == "chords" else f"_{song.chord_style}") + extras)


def chord_sheet(song) -> str:
    bar_q = song.timesig.bar_quarters
    lines = [
        f"Key: {song.key.name} | Tempo: {song.tempo} BPM | Time: {song.timesig.label} | "
        f"Level: {song.level}" + (f" | Mood: {_mood_label(song)}" if _mood_label(song) else "")
        + f" | Seed: {song.seed}",
        "Form: " + " -> ".join(f"{s.label} ({s.bars:g} bars)" for s in song.sections),
        "",
    ]
    for sec in song.sections:
        first = int(round(sec.start / bar_q)) + 1
        nbars = int(math.ceil(sec.bars - EPS))
        lines.append(f"[{sec.label}]  bars {first}-{first + nbars - 1}")
        cells = []
        for b in range(nbars):
            bs = sec.start + b * bar_q
            names = [f"{sl.chord.symbol} ({sl.chord.roman})" for sl in sec.slots
                     if bs - EPS <= sl.start < bs + bar_q - EPS]
            cells.append("  ".join(names) if names else "   -")
        width = max(len(c) for c in cells)
        for i in range(0, len(cells), 4):
            lines.append("| " + " | ".join(c.ljust(width) for c in cells[i:i + 4]) + " |")
        lines.append("")
    return "\n".join(lines)


def song_json(song) -> str:
    bar_q = song.timesig.bar_quarters
    data = {
        "key": song.key.tonic, "scale": song.key.mode, "tempo": song.tempo,
        "time_signature": song.timesig.label, "level": song.level, "mood": song.mood, "seed": song.seed,
        "tracks": [t.name for t in song.tracks],
        "sections": [
            {
                "kind": sec.kind, "label": sec.label,
                "start_bar": round(sec.start / bar_q) + 1, "bars": sec.bars,
                "chords": [
                    {"roman": sl.chord.roman, "symbol": sl.chord.symbol,
                     "start_bar": round(sl.start / bar_q + 1, 3), "bars": round(sl.length / bar_q, 3)}
                    for sl in sec.slots
                ],
            }
            for sec in song.sections
        ],
    }
    return json.dumps(data, indent=2)

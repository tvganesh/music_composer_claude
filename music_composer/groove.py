"""Bass and Drums guide tracks.

These are reference parts so you can hear the groove while you write. They are
easy to delete in Logic before you put Session Players on the song. Both follow
the song's chords and sections, and the mood picks their style (moods.py):

  bass    root-fifth  root on the downbeat, fifth halfway (no mood)
          bounce      a note on every beat (root, fifth, octave), stepping into the next chord (happy)
          walk        long roots and fifths, walking down into the next chord (sad)
          drive       driving eighth-note roots with an octave at the end of the bar (angry)
          pedal       held notes, the tonic sustained under the intro and verses (eerie)
  drums   straight    kick, backbeat snare, eighth-note hi-hats (no mood)
          pop         straight, with a pushed kick, claps and open hats in the chorus (happy)
          halftime    kick on 1, cross-stick or snare on 3, soft hats or ride (sad)
          drive       kick on every beat (every eighth in the chorus), loud snare, tom fills (angry)
          ritual      floor tom and kick pulses, pedal hi-hat, low toms and ride bell (eerie)

The intro is lighter and the chorus fuller. The last bar of each section has a
fill, the next section starts with a crash, and the final chord gets one hit.
Drums use the General MIDI drum map on channel 10, which Logic's drum kits read.
All times are in quarter notes.
"""
from __future__ import annotations

import math
import random

from .melody import chord_scale
from .rhythm import TimeSig
from .theory import Key

EPS = 1e-6

# General MIDI percussion notes
KICK, STICK, SNARE, CLAP, FLOOR_TOM, CLOSED_HAT, PEDAL_HAT = 36, 37, 38, 39, 41, 42, 44
LOW_TOM, OPEN_HAT, MID_TOM, CRASH, HIGH_TOM, RIDE, RIDE_BELL = 45, 46, 47, 49, 50, 51, 53

BASS_STYLES = ("root-fifth", "bounce", "walk", "drive", "pedal")
DRUM_STYLES = ("straight", "pop", "halftime", "drive", "ritual")

BASS_LOW = 28  # roots sit in E1..D#2
BASS_VELOCITY = {"intro": 64, "verse": 74, "verse2": 76, "chorus": 86, "chorus2": 88, "ending": 80}
INTENSITY = {"intro": "light", "verse": "main", "verse2": "main",
             "chorus": "full", "chorus2": "full", "ending": "full"}
LOUDNESS = {"light": 0.82, "main": 1.0, "full": 1.06}
CRASH_SECTIONS = ("verse2", "chorus", "chorus2", "ending")
GATE = {"root-fifth": 0.96, "bounce": 0.82, "walk": 0.98, "drive": 0.72, "pedal": 0.98}


def _bass_root(chord) -> int:
    return BASS_LOW + (chord.root_pc - BASS_LOW) % 12


def _approach(key: Key, chord, root: int) -> int:
    """A scale step above the next chord's root, to walk down into it."""
    pcs = chord_scale(key, chord)
    for up in (2, 1):
        if (root + up) % 12 in pcs:
            return root + up
    return root + 2


def _bass_bar(style: str, ts: TimeSig, intensity: str, root: int, fifth: int) -> list:
    """One bar of (offset, length, pitch), offsets from the chord's start."""
    G, g, bar = ts.groups, ts.group_quarters, ts.bar_quarters
    octave = root + 12
    if style == "pedal":
        return [(0.0, bar, root)]
    if style == "drive":
        if intensity == "light":
            return [(k * g, g, root) for k in range(G)]
        step = g / (3 if ts.compound else 2)
        n = int(round(bar / step))
        return [(k * step, step, octave if k == n - 1 else root) for k in range(n)]
    if style == "bounce":
        if ts.compound:
            out = []
            for k in range(G):
                out += [(k * g, g * 2 / 3, octave if k % 2 else root), (k * g + g * 2 / 3, g / 3, fifth)]
            return out
        cycle = [root, fifth, octave, fifth] if G >= 4 else [root, fifth, octave][:max(G, 1)]
        return [(k * g, g, cycle[k % len(cycle)]) for k in range(G)]
    # root-fifth and walk: root for the first half of the bar, fifth for the rest
    if G == 1:
        return [(0.0, bar, root)]
    split = (G + 1) // 2 * g
    return [(0.0, split, root), (split, bar - split, fifth)]


def bass_part(sections: list, key: Key, ts: TimeSig, style: str, rng: random.Random,
              velocity_shift: int = 0) -> list:
    """(start, duration, pitch, velocity) tuples for the Bass track."""
    if style not in BASS_STYLES:
        raise ValueError(f"Unknown bass style {style!r}")
    slots = [(sec, sl) for sec in sections for sl in sec.slots]
    bar, g = ts.bar_quarters, ts.group_quarters
    tonic = BASS_LOW + (key.tonic_pc - BASS_LOW) % 12
    out = []
    for i, (sec, sl) in enumerate(slots):
        root = _bass_root(sl.chord)
        if style == "pedal" and sec.kind in ("intro", "verse", "verse2"):
            root = tonic  # tonic pedal: the chords move above a note that doesn't
        fifth = root + sl.chord.fifth_interval
        last = i == len(slots) - 1
        if last:
            notes = [(0.0, sl.length, root)]
        else:
            notes = []
            for b in range(int(math.ceil(sl.length / bar - EPS))):
                for off, length, pitch in _bass_bar(style, ts, INTENSITY[sec.kind], root, fifth):
                    o = b * bar + off
                    if o < sl.length - EPS:
                        notes.append((o, min(length, sl.length - o), pitch))
            nxt = slots[i + 1][1].chord
            if style in ("bounce", "walk") and sl.length > g + EPS and nxt.root_pc != sl.chord.root_pc:
                at = sl.length - g
                notes = [(o, min(d, at - o), p) for o, d, p in notes if o < at - EPS]
                target = _bass_root(nxt)
                notes.append((at, g, _approach(key, nxt, target) if style == "walk" else target - 1))
        base = BASS_VELOCITY[sec.kind] + velocity_shift
        for o, d, p in notes:
            t = sl.start + o
            accent = 8 if abs((t + EPS) % bar) < 2 * EPS else 0
            vel = max(1, min(127, base + accent + rng.randint(-3, 3)))
            out.append((t, d if last else d * GATE[style], p, vel))
    return out


# ------------------------------------------------------------------ drums

def _backbeats(G: int) -> list:
    return [1, 2] if G == 3 else list(range(1, G, 2))


def _drum_bar(style: str, ts: TimeSig, intensity: str, bar_no: int) -> list:
    """One bar of (offset, note, velocity)."""
    G, gq = ts.groups, ts.group_quarters
    n = 3 if ts.compound else 2
    st = gq / n
    back, mid = _backbeats(G), (G // 2 if G >= 2 else None)
    hits = []

    def hit(group, sub, note, vel):
        hits.append((group * gq + sub * st, note, vel))

    def hats(note=CLOSED_HAT, down=78, off=62, every_sub=True):
        for k in range(G):
            for s in range(n if every_sub else 1):
                hit(k, s, note, down if s == 0 else off)

    light, full = intensity == "light", intensity == "full"
    if style in ("straight", "pop"):
        hats()
        hit(0, 0, KICK, 96)
        if G >= 4:
            hit(G // 2, 0, KICK, 88)
        if light:
            return hits
        for b in back:
            hit(b, 0, SNARE, 70 if G == 3 else 96)
            if style == "pop" and full:
                hit(b, 0, CLAP, 80)
        if G >= 4 and (style == "pop" or full):
            hit(G // 2 - 1, n - 1, KICK, 80)  # pushed kick on the "and" before the middle of the bar
        if full:
            hits = [h for h in hits if not (h[1] == CLOSED_HAT and abs(h[0] - ((G - 1) * gq + (n - 1) * st)) < EPS)]
            hit(G - 1, n - 1, OPEN_HAT, 72)
    elif style == "halftime":
        if light:
            hats(down=50, every_sub=False)
            return hits
        hit(0, 0, KICK, 82)
        if full:
            hats(RIDE, down=62, off=50)
            if mid is not None:
                hit(mid, 0, SNARE, 88)
            hit(G - 1, n - 1, KICK, 60)
        else:
            hats(down=56, every_sub=False)
            if mid is not None:
                hit(mid, 0, STICK, 72)
    elif style == "drive":
        if light:
            hats(down=88, off=76)
            for k in range(G):
                hit(k, 0, KICK, 96)
            return hits
        if full:
            for k in range(G):
                for s in range(n):
                    if not (s == 0 and k in back):
                        hit(k, s, KICK, 104 if s == 0 else 92)
                hit(k, 0, RIDE, 96)
            if bar_no % 2 == 0:
                hit(0, 0, CRASH, 108)
        else:
            hats(down=100, off=86)
            for k in range(G):
                hit(k, 0, KICK, 104)
            hit(G - 1, n - 1, KICK, 90)
        for b in back:
            hit(b, 0, SNARE, 118 if full else 112)
    elif style == "ritual":
        if light:
            if bar_no % 2 == 0:
                hit(0, 0, FLOOR_TOM, 52)
            return hits
        hit(0, 0, FLOOR_TOM, 68 if full else 60)
        if full or bar_no % 2 == 0:
            hit(0, 0, KICK, 66 if full else 58)
        for b in back:
            hit(b, 0, LOW_TOM if full else PEDAL_HAT, 58 if full else 40)
        if full:
            hit(0, 0, RIDE_BELL, 54)
            for k in range(1, G):
                if k not in back:
                    hit(k, 0, PEDAL_HAT, 42)
    else:
        raise ValueError(f"Unknown drum style {style!r}")
    return hits


def _fill_step(ts: TimeSig) -> float:
    gq = ts.group_quarters
    return gq / 3 if ts.compound else gq / 4


def _with_fill(style: str, ts: TimeSig, hits: list) -> list:
    """Replace the last beat of a section's final bar with a fill into the next section."""
    G, gq = ts.groups, ts.group_quarters
    n = 3 if ts.compound else 2
    at = (G - 1) * gq
    if style == "halftime":  # a gentle pickup, no fill
        return hits + [(at + (n - 1) * gq / n, SNARE, 60)]
    step = _fill_step(ts)
    k = int(round(gq / step))
    kept = [h for h in hits if h[0] < at - EPS]
    if style == "drive":
        toms = [HIGH_TOM, MID_TOM, LOW_TOM, FLOOR_TOM]
        fill = [(at + i * step, toms[i * len(toms) // k], 100 + 18 * i // max(1, k - 1)) for i in range(k)]
    elif style == "ritual":
        fill = [(at + i * (gq / n), FLOOR_TOM if i % 2 == 0 else LOW_TOM, 48 + 24 * i // max(1, n - 1))
                for i in range(n)]
    else:
        fill = [(at + i * step, SNARE, 64 + 36 * i // max(1, k - 1)) for i in range(k)]
    return kept + fill + [(at, KICK, 90)]


def drum_part(sections: list, ts: TimeSig, style: str, rng: random.Random) -> list:
    """(start, duration, note, velocity) tuples for the Drums track."""
    if style not in DRUM_STYLES:
        raise ValueError(f"Unknown drum style {style!r}")
    bar = ts.bar_quarters
    final = [sl for sec in sections for sl in sec.slots][-1].start
    soft = style in ("halftime", "ritual")
    crash_vel = {"halftime": 72, "ritual": 58}.get(style, 104)
    raw = []
    for si, sec in enumerate(sections):
        end = sec.start + sec.bars * bar
        intensity = INTENSITY[sec.kind]
        nbars = int(math.ceil(sec.bars - EPS))
        for b in range(nbars):
            hits = _drum_bar(style, ts, intensity, b)
            if b == nbars - 1 and si < len(sections) - 1 and nbars >= 2:
                hits = _with_fill(style, ts, hits)
            for off, note, vel in hits:
                t = sec.start + b * bar + off
                if t < min(end, final) - EPS:
                    raw.append((t, note, vel * LOUDNESS[intensity]))
        if sec.kind in CRASH_SECTIONS and sec.start < final - EPS:
            raw += [(sec.start, CRASH, crash_vel), (sec.start, FLOOR_TOM if style == "ritual" else KICK, crash_vel)]
    # the final chord: one hit, then let it ring
    raw += [(final, CRASH, crash_vel + (0 if soft else 8)), (final, FLOOR_TOM if style == "ritual" else KICK, 96)]

    loudest = {}
    for t, note, vel in raw:  # the same drum twice at one time: keep the louder hit
        k = (round(t, 6), note)
        loudest[k] = max(loudest.get(k, 0), vel)
    short = min(0.2, 0.8 * _fill_step(ts), 0.8 * ts.group_quarters / (3 if ts.compound else 2))
    out = []
    for (t, note), vel in sorted(loudest.items()):
        dur = min(1.5, bar) if note == CRASH else short
        out.append((t, dur, note, max(1, min(127, int(round(vel)) + rng.randint(-4, 4)))))
    return out

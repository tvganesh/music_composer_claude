"""Time signatures and the rhythm vocabulary used by the melody generator.

A rhythm cell is one bar, written as durations in quarter notes; "r" marks a
rest. In 6/8, 0.5 is an eighth note and 1.5 a dotted quarter.

Cells are grouped by density:
  sparse  - long notes (intro, contrast phrases)
  medium  - verse-style phrases
  busy    - chorus hooks
  cadence - the last bar of a phrase: settles on a longer note
4/4, 3/4 and 6/8 have hand-picked cells; other signatures get cells built
from their beat groups.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TimeSig:
    num: int
    den: int

    @classmethod
    def parse(cls, text: str) -> "TimeSig":
        try:
            num, den = (int(x) for x in text.split("/"))
        except ValueError:
            raise ValueError(f"Time signature must look like 4/4, got {text!r}")
        if num < 1 or den not in (2, 4, 8, 16):
            raise ValueError(f"Unsupported time signature {text!r}")
        return cls(num, den)

    @property
    def label(self) -> str:
        return f"{self.num}/{self.den}"

    @property
    def bar_quarters(self) -> float:
        return self.num * 4 / self.den

    @property
    def compound(self) -> bool:
        return self.den == 8 and self.num % 3 == 0 and self.num >= 6

    @property
    def group_quarters(self) -> float:
        """Length of one felt beat (a dotted quarter in 6/8)."""
        unit = 4 / self.den
        return unit * 3 if self.compound else unit

    @property
    def groups(self) -> int:
        return max(1, int(round(self.bar_quarters / self.group_quarters)))

    @property
    def strong_positions(self) -> tuple:
        """Positions in the bar that carry metric weight (1 and 3 in 4/4, 1 and 4 in 6/8)."""
        if self.groups % 2 == 0:
            return (0.0, self.bar_quarters / 2)
        return (0.0,)

    @property
    def midi_clocks_per_click(self) -> int:
        return int(24 * self.group_quarters)


_CELLS = {
    "4/4": {
        "sparse":  ["2 2", "3 1", "1.5 2.5", "r1 3", "1 3"],
        "medium":  ["1 1 2", "1.5 0.5 1 1", "1 0.5 0.5 2", "r1 1 1 1", "0.5 1 0.5 2", "1 1 1 1",
                    "r0.5 0.5 1 2"],
        "busy":    ["0.5 0.5 1 0.5 0.5 1", "1 0.5 0.5 1 1", "0.5 0.5 0.5 0.5 1 1",
                    "r0.5 0.5 0.5 0.5 1 1", "0.5 1 0.5 0.5 0.5 1"],
        "cadence": ["2 2", "1 3", "1 1 2", "3 r1", "2 1 r1", "0.5 0.5 3"],
    },
    "3/4": {
        "sparse":  ["3", "2 1", "r1 2"],
        "medium":  ["1 1 1", "2 0.5 0.5", "1.5 0.5 1", "1 2", "r1 1 1"],
        "busy":    ["0.5 0.5 1 1", "1 0.5 0.5 1", "0.5 0.5 0.5 0.5 1", "r0.5 0.5 1 1"],
        "cadence": ["3", "2 r1", "1 2", "0.5 0.5 2"],
    },
    "6/8": {
        "sparse":  ["3", "1.5 1.5", "r1.5 1.5"],
        "medium":  ["1 0.5 1 0.5", "1.5 1 0.5", "0.5 0.5 0.5 1.5", "1 0.5 1.5"],
        "busy":    ["0.5 0.5 0.5 0.5 0.5 0.5", "1 0.5 0.5 0.5 0.5", "0.5 0.5 0.5 1 0.5"],
        "cadence": ["3", "1 0.5 1.5", "1.5 r1.5", "0.5 0.5 0.5 1.5"],
    },
}


def _fmt(values) -> str:
    return " ".join(f"{v:g}" for v in values)


def _generic_cells(ts: TimeSig) -> dict:
    bar, g, n = ts.bar_quarters, ts.group_quarters, ts.groups
    sub = g / 3 if ts.compound else g / 2
    per_group = int(round(g / sub))
    medium = _fmt([g] * n)
    busy = _fmt([sub] * per_group + [g] * (n - 1))
    return {
        "sparse": [_fmt([bar])] if n == 1 else [_fmt([bar]), _fmt([g * (n - 1), g])],
        "medium": [medium],
        "busy": [busy],
        "cadence": [_fmt([bar])] if n == 1 else [_fmt([bar]), _fmt([g * (n - 1), g])],
    }


def parse_cell(text: str) -> list:
    """'1 r0.5 0.5 2' -> [(0, 1, False), (1, 0.5, True), (1.5, 0.5, False), (2, 2, False)]"""
    out, t = [], 0.0
    for tok in text.split():
        rest = tok.startswith("r")
        dur = float(tok[1:] if rest else tok)
        out.append((t, dur, rest))
        t += dur
    return out


def rhythm_cells(ts: TimeSig) -> dict:
    """density -> list of parsed one-bar cells."""
    table = _CELLS.get(ts.label) or _generic_cells(ts)
    return {density: [parse_cell(c) for c in cells] for density, cells in table.items()}


# Right-hand arpeggio orders (indices into chord tones + the bottom note an octave up).
_ARP_ORDERS = {"4/4": [0, 1, 2, 3, 2, 1, 2, 1], "3/4": [0, 1, 2, 3, 2, 1], "6/8": [0, 1, 2, 3, 2, 1]}


def arpeggio_pattern(ts: TimeSig, n_tones: int):
    """(step in quarters, index order) for broken-chord accompaniment in eighth notes."""
    order = _ARP_ORDERS.get(ts.label)
    if order is None:
        order = list(range(n_tones)) + list(range(n_tones - 2, 0, -1))  # up-down
    return 0.5, order

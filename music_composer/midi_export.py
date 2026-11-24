"""Standard MIDI File (format 1) writer — no third-party dependencies.

Track 0 (conductor) carries the tempo, time signature, key signature and one
marker per section, which Logic Pro shows in its Marker track. Every part gets
its own track and channel.
"""
from __future__ import annotations

import struct
from pathlib import Path

PPQ = 480


def _vlq(n: int) -> bytes:
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(out))


def _meta(kind: int, data: bytes) -> bytes:
    return bytes([0xFF, kind]) + _vlq(len(data)) + data


def _tick(quarters: float) -> int:
    return int(round(quarters * PPQ))


def _chunk(events: list, end_tick: int) -> bytes:
    """events: (tick, order, bytes). Lower order sorts first at the same tick,
    so note-offs (2) come before note-ons (3)."""
    events = sorted(events, key=lambda e: (e[0], e[1]))
    body, last = bytearray(), 0
    for tick, _, data in events:
        body += _vlq(tick - last) + data
        last = tick
    body += _vlq(max(0, end_tick - last)) + _meta(0x2F, b"")
    return b"MTrk" + struct.pack(">I", len(body)) + bytes(body)


def song_to_midi(song, title: str = "") -> bytes:
    ts, key = song.timesig, song.key
    end_tick = _tick(song.total_quarters)

    conductor = [
        (0, 0, _meta(0x03, (title or key.name).encode("utf-8"))),
        (0, 1, _meta(0x51, int(round(60_000_000 / song.tempo)).to_bytes(3, "big"))),
        (0, 1, _meta(0x58, bytes([ts.num, ts.den.bit_length() - 1, ts.midi_clocks_per_click, 8]))),
        (0, 1, _meta(0x59, struct.pack(">bB", key.key_signature(), 0 if key.mode == "major" else 1))),
    ]
    for sec in song.sections:
        conductor.append((_tick(sec.start), 1, _meta(0x06, sec.label.encode("utf-8"))))
    chunks = [_chunk(conductor, end_tick)]

    for track in song.tracks:
        ch = track.channel
        events = [(0, 0, _meta(0x03, track.name.encode("utf-8")))]
        if ch != 9:
            events.append((0, 1, bytes([0xC0 | ch, track.program])))
        for n in track.notes:
            on = _tick(n.start)
            off = max(on + 1, _tick(n.start + n.dur))
            events.append((on, 3, bytes([0x90 | ch, n.pitch, n.velocity])))
            events.append((off, 2, bytes([0x80 | ch, n.pitch, 0])))
        chunks.append(_chunk(events, end_tick))

    header = b"MThd" + struct.pack(">IHHH", 6, 1, len(chunks), PPQ)
    return header + b"".join(chunks)


def write_midi(song, path, title: str = "") -> Path:
    path = Path(path)
    path.write_bytes(song_to_midi(song, title))
    return path

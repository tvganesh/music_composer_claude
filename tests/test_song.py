import bisect
import itertools
import random
import struct
import unittest

from music_composer.arranger import compose
from music_composer.melody import chord_scale, tonic_reference
from music_composer.midi_export import PPQ, song_to_midi
from music_composer.progressions import PROGRESSIONS, SUBSTITUTIONS, LEVELS, _degree, parse_progression, substitute
from music_composer.rhythm import TimeSig, rhythm_cells
from music_composer.theory import Key, parse_roman
from music_composer.voicing import CHORD_HIGH, CHORD_LOW, voice_chord

KEYS = ["C", "G", "D", "A", "E", "B", "F#", "Db", "Ab", "Eb", "Bb", "F"]
SIGS = ["4/4", "3/4", "6/8", "5/4", "12/8", "2/4"]
FULL_FORM = ("intro", "verse", "chorus", "verse2", "chorus2", "ending")


def read_vlq(data, i):
    n = 0
    while True:
        b = data[i]
        i += 1
        n = (n << 7) | (b & 0x7F)
        if not b & 0x80:
            return n, i


def parse_midi(data):
    """Minimal SMF reader: returns (format, ppq, tracks); each track is a list of
    (abs_tick, kind, payload)."""
    assert data[:4] == b"MThd"
    _, fmt, ntrks, ppq = struct.unpack(">IHHH", data[4:14])
    i, tracks = 14, []
    for _ in range(ntrks):
        assert data[i:i + 4] == b"MTrk"
        (length,) = struct.unpack(">I", data[i + 4:i + 8])
        j, end, tick, events = i + 8, i + 8 + length, 0, []
        while j < end:
            delta, j = read_vlq(data, j)
            tick += delta
            status = data[j]
            if status == 0xFF:
                kind, (mlen, k) = data[j + 1], read_vlq(data, j + 2)
                events.append((tick, ("meta", kind), data[k:k + mlen]))
                j = k + mlen
            elif status & 0xF0 in (0x80, 0x90):
                events.append((tick, ("note", status & 0xF0, status & 0x0F), data[j + 1:j + 3]))
                j += 3
            elif status & 0xF0 == 0xC0:
                events.append((tick, ("program", status & 0x0F), data[j + 1:j + 2]))
                j += 2
            else:
                raise AssertionError(f"unexpected status byte {status:#x}")
        assert j == end, "track length mismatch"
        assert events[-1][1] == ("meta", 0x2F), "missing end-of-track"
        tracks.append(events)
        i = end
    assert i == len(data)
    return fmt, ppq, tracks


def chord_at(song, t):
    slots = [sl for sec in song.sections for sl in sec.slots]
    starts = [sl.start for sl in slots]
    return slots[bisect.bisect_right(starts, t + 1e-6) - 1].chord


class SongTests(unittest.TestCase):
    def test_form_and_lengths(self):
        song = compose(Key("C"), 100, TimeSig.parse("4/4"), seed=1)
        self.assertEqual([s.label for s in song.sections], ["Intro", "Verse 1", "Chorus", "Verse 2", "Ending"])
        self.assertEqual([s.bars for s in song.sections], [4, 8, 8, 8, 4])
        self.assertEqual(song.total_quarters, 32 * 4)
        self.assertEqual([t.name for t in song.tracks], ["Melody", "Chords"])

    def test_same_seed_same_song(self):
        a = song_to_midi(compose(Key("Eb", "minor"), 90, TimeSig.parse("3/4"), seed=99))
        b = song_to_midi(compose(Key("Eb", "minor"), 90, TimeSig.parse("3/4"), seed=99))
        self.assertEqual(a, b)

    def test_verse2_varies_verse(self):
        song = compose(Key("G"), 100, TimeSig.parse("4/4"), seed=3)
        verse = [s.chord.roman for s in song.sections[1].slots]
        verse2 = [s.chord.roman for s in song.sections[3].slots]
        self.assertEqual(verse2[:4], verse[:4])
        self.assertEqual(sum(a != b for a, b in zip(verse, verse2)), 1)

    def test_verse2_varies_verse_at_every_level(self):
        for level in LEVELS:
            for mode in ("major", "minor"):
                for seed in range(6):
                    song = compose(Key("D", mode), 100, TimeSig.parse("4/4"), level, seed=seed)
                    verse = [s.chord.roman for s in song.sections[1].slots]
                    verse2 = [s.chord.roman for s in song.sections[3].slots]
                    self.assertEqual(sum(a != b for a, b in zip(verse, verse2)), 1, (level, mode, seed))

    def test_verse2_borrows_a_chord_at_higher_levels(self):
        from music_composer import arranger
        from music_composer.progressions import MODAL_SUBSTITUTIONS
        for level in ("intermediate", "advanced"):
            for mode in ("major", "minor"):
                borrowed_tokens = {x for alts in MODAL_SUBSTITUTIONS[mode].values() for x in alts}
                for seed in range(12):
                    song = compose(Key("Bb", mode), 100, TimeSig.parse("4/4"), level, seed=seed, form=FULL_FORM)
                    verse = [sl.chord.roman for sl in song.sections[1].slots]
                    verse2 = [sl.chord.roman for sl in song.sections[3].slots]
                    changed = [(i, b) for i, (a, b) in enumerate(zip(verse, verse2)) if a != b]
                    self.assertEqual(len(changed), 1)
                    i, new = changed[0]
                    if verse[:4] != ["i", "imaj7", "i7", "i6"]:  # the line cliché keeps its own colour
                        self.assertIn(new, borrowed_tokens, (level, mode, seed, verse2))
                    if "/" in verse2[i - 1]:  # a secondary dominant must still resolve to the same root
                        self.assertEqual(_degree(new), _degree(verse[i]), (level, mode, seed, verse2))
                    # Only Verse 2's melody may change; everything after it is untouched.
                    keep = arranger.MODAL_LEVELS
                    arranger.MODAL_LEVELS = ()
                    try:
                        plain = compose(Key("Bb", mode), 100, TimeSig.parse("4/4"), level, seed=seed, form=FULL_FORM)
                    finally:
                        arranger.MODAL_LEVELS = keep
                    v2_end = song.sections[3].start + song.sections[3].bars * 4
                    tail = lambda s_: [(n.start, n.dur, n.pitch) for n in s_.track("Melody").notes if n.start >= v2_end]
                    head = lambda s_: [(n.start, n.dur, n.pitch) for n in s_.track("Melody").notes
                                       if n.start < song.sections[3].start]
                    self.assertEqual(tail(song), tail(plain))
                    self.assertEqual(head(song), head(plain))

    def test_basic_verse2_stays_diatonic(self):
        for seed in range(12):
            song = compose(Key("G"), 100, TimeSig.parse("4/4"), "basic", seed=seed)
            for sl in song.sections[3].slots:
                self.assertNotIn("b", sl.chord.roman)
                self.assertFalse(sl.chord.roman.startswith("iv") and song.key.mode == "major")

    def test_every_progression_chord_builds_in_every_key(self):
        keys = ["C", "C#", "Db", "D", "Eb", "E", "F", "F#", "Gb", "G", "Ab", "A", "Bb", "B"]
        for level, modes in PROGRESSIONS.items():
            for mode, sections in modes.items():
                tokens = {t for specs in sections.values() for spec in specs for t, _ in parse_progression(spec)}
                tokens |= {alt for alts in SUBSTITUTIONS[level][mode].values() for alt in alts}
                for tonic in keys:
                    key = Key(tonic, mode)
                    for token in tokens:
                        notes = voice_chord(parse_roman(token, key))
                        self.assertTrue(CHORD_LOW <= min(notes) and max(notes) <= CHORD_HIGH, (token, tonic))
                for spec in sections["verse"]:  # Verse 2 can always vary the verse
                    prog = parse_progression(spec)
                    self.assertNotEqual(substitute(prog, SUBSTITUTIONS[level][mode], random.Random(0)), prog,
                                        (level, mode, spec))

    def test_levels_use_their_chord_vocabulary(self):
        def symbols(level, mode):
            out = set()
            for seed in range(40):
                song = compose(Key("C" if mode == "major" else "A", mode), 100, TimeSig.parse("4/4"),
                               level, seed=seed, form=FULL_FORM)
                out |= {sl.chord.symbol for sec in song.sections for sl in sec.slots}
            return out
        basic = symbols("basic", "major")
        self.assertFalse(any("7" in s for s in basic))
        inter = symbols("intermediate", "major")
        self.assertTrue({"Cmaj7", "Dm7", "G7"} <= inter)
        self.assertTrue({"Fm", "Bb"} & inter)            # borrowed iv / bVII
        adv_major, adv_minor = symbols("advanced", "major"), symbols("advanced", "minor")
        self.assertIn("E7", adv_major)                   # V7/vi
        self.assertIn("Abmaj7", adv_major)               # bVI from C minor
        self.assertIn("C#dim7", adv_major)               # diminished passing chord
        self.assertIn("Bb", adv_minor)                   # Neapolitan in A minor
        self.assertIn("A", adv_minor)                    # Picardy third

    def test_every_section_has_a_melody(self):
        song = compose(Key("C"), 100, TimeSig.parse("4/4"), seed=4, form=FULL_FORM)
        mel = song.track("Melody").notes
        bar_q = song.timesig.bar_quarters
        for sec in song.sections:
            inside = [n for n in mel if sec.start <= n.start < sec.start + sec.bars * bar_q]
            self.assertGreaterEqual(len(inside), sec.bars, sec.label)

    def test_chorus2_repeats_chorus_melody(self):
        song = compose(Key("F"), 100, TimeSig.parse("4/4"), seed=8, form=FULL_FORM)
        mel = song.track("Melody").notes
        by_kind = {s.kind: s for s in song.sections}

        def phrase(sec):
            end = sec.start + sec.bars * song.timesig.bar_quarters
            return [(n.start - sec.start, n.pitch) for n in mel if sec.start <= n.start < end]

        self.assertEqual(phrase(by_kind["chorus"]), phrase(by_kind["chorus2"]))

    def test_melody_rules_across_keys_and_meters(self):
        for mode in ("major", "minor"):
            for tonic in KEYS:
                key = Key(tonic, mode)
                ref = tonic_reference(key)
                for sig in SIGS:
                    ts = TimeSig.parse(sig)
                    for seed, level in itertools.product(range(3), LEVELS):
                        song = compose(key, 120, ts, level, seed=seed, form=FULL_FORM)
                        mel = song.track("Melody").notes
                        bar_q = ts.bar_quarters
                        for a, b in zip(mel, mel[1:]):
                            self.assertLessEqual(a.start + a.dur, b.start + 1e-6, "melody notes overlap")
                        for n in mel:
                            self.assertTrue(ref - 3 <= n.pitch <= ref + 17)
                            self.assertTrue(1 <= n.velocity <= 127)
                            pos = (n.start % bar_q)
                            if any(abs(pos - sp) < 1e-6 for sp in ts.strong_positions):
                                self.assertIn(n.pitch % 12, chord_at(song, n.start).pitch_classes,
                                              f"{key.name} {sig} {level} seed {seed}: non-chord tone on a strong beat")
                        self.assertEqual(mel[-1].pitch % 12, key.tonic_pc, "melody ends on the tonic")
                        self.assertAlmostEqual(mel[-1].start + mel[-1].dur, song.total_quarters)
                        for n in song.track("Chords").notes:
                            self.assertTrue(48 <= n.pitch <= 73)
                        song_to_midi(song)  # must not raise

    def test_chord_scale_follows_borrowed_tones(self):
        a_minor = Key("A", "minor")
        self.assertIn(8, chord_scale(a_minor, parse_roman("V", a_minor)))      # G#
        self.assertNotIn(7, chord_scale(a_minor, parse_roman("V", a_minor)))   # not G
        self.assertIn(7, chord_scale(a_minor, parse_roman("VII", a_minor)))    # G over G major
        c = Key("C")
        self.assertIn(8, chord_scale(c, parse_roman("bVI", c)))                # Ab over Ab major

    def test_rhythm_cells_fill_the_bar(self):
        for sig in SIGS + ["7/8", "9/8"]:
            ts = TimeSig.parse(sig)
            for density, cells in rhythm_cells(ts).items():
                for cell in cells:
                    self.assertAlmostEqual(sum(d for _, d, _ in cell), ts.bar_quarters, msg=f"{sig} {density}")

    def test_midi_file_structure(self):
        song = compose(Key("D", "minor"), 92, TimeSig.parse("6/8"), seed=7)
        fmt, ppq, tracks = parse_midi(song_to_midi(song))
        self.assertEqual((fmt, ppq, len(tracks)), (1, PPQ, 3))

        conductor = {kind: payload for _, kind, payload in tracks[0] if kind[0] == "meta"}
        self.assertEqual(int.from_bytes(conductor[("meta", 0x51)], "big"), round(60_000_000 / 92))
        self.assertEqual(bytes(conductor[("meta", 0x58)]), bytes([6, 3, 36, 8]))
        self.assertEqual(struct.unpack(">bB", conductor[("meta", 0x59)]), (-1, 1))
        markers = [p.decode() for _, k, p in tracks[0] if k == ("meta", 0x06)]
        self.assertEqual(markers, ["Intro", "Verse 1", "Chorus", "Verse 2", "Ending"])
        names = [p.decode() for t in tracks[1:] for _, k, p in t if k == ("meta", 0x03)]
        self.assertEqual(names, ["Melody", "Chords"])

        end_tick = int(song.total_quarters * PPQ)
        for events in tracks:
            self.assertEqual(events[-1][0], end_tick)
        for events in tracks[1:]:
            ons = sum(1 for _, k, _ in events if k[0] == "note" and k[1] == 0x90)
            offs = sum(1 for _, k, _ in events if k[0] == "note" and k[1] == 0x80)
            self.assertEqual(ons, offs)
            self.assertGreater(ons, 0)

    def test_unknown_section_rejected(self):
        with self.assertRaises(ValueError):
            compose(Key("C"), 100, TimeSig.parse("4/4"), form=("intro", "bridge"))


if __name__ == "__main__":
    unittest.main()

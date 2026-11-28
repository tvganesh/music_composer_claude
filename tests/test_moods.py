import contextlib
import io
import itertools
import random
import tempfile
import unittest
from pathlib import Path

from music_composer import cli
from music_composer.arranger import compose
from music_composer.groove import CRASH, KICK, drum_part
from music_composer.melody import tonic_reference
from music_composer.midi_export import song_to_midi
from music_composer.moods import MOOD_IDS, MOODS, NONE
from music_composer.progressions import parse_progression, substitute
from music_composer.rhythm import TimeSig
from music_composer.theory import Key, parse_roman
from music_composer.ui import build_song, song_payload
from music_composer.voicing import CHORD_HIGH, CHORD_LOW, voice_chord
from tests.test_song import FULL_FORM, chord_at, parse_midi

MOODS_ONLY = [m for m in MOOD_IDS if m != NONE]
SIGS = ["4/4", "3/4", "6/8", "5/4", "12/8", "2/4"]


def notes_of(song, name):
    return [(n.start, n.dur, n.pitch, n.velocity) for n in song.track(name).notes]


def overlaps(notes):
    by_pitch = {}
    for n in notes:
        by_pitch.setdefault(n.pitch, []).append((n.start, n.start + n.dur))
    for spans in by_pitch.values():
        spans.sort()
        if any(e1 > s2 + 1e-6 for (_, e1), (s2, _) in zip(spans, spans[1:])):
            return True
    return False


class MoodLibraryTests(unittest.TestCase):
    def test_every_mood_chord_builds_in_every_key(self):
        keys = ["C", "C#", "Db", "D", "Eb", "E", "F", "F#", "Gb", "G", "Ab", "A", "Bb", "B"]
        for mood in MOODS_ONLY:
            for mode, tiers in MOODS[mood]["progressions"].items():
                subs = MOODS[mood]["substitutions"][mode]
                for tier, sections in tiers.items():
                    tokens = {t for specs in sections.values() for spec in specs for t, _ in parse_progression(spec)}
                    tokens |= {alt for alts in subs.values() for alt in alts}
                    for tonic, token in itertools.product(keys, tokens):
                        notes = voice_chord(parse_roman(token, Key(tonic, mode)))
                        self.assertTrue(CHORD_LOW <= min(notes) and max(notes) <= CHORD_HIGH, (mood, token, tonic))
                    for spec in sections["verse"]:  # Verse 2 can always vary the verse
                        prog = parse_progression(spec)
                        self.assertNotEqual(substitute(prog, subs, random.Random(0)), prog, (mood, mode, tier, spec))
                    for spec in sections["ending"]:  # the song ends on a tonic chord
                        last = parse_roman(parse_progression(spec)[-1][0], Key("C", mode))
                        self.assertIn(0, last.pitch_classes, (mood, mode, spec))

    def test_verse2_changes_one_chord(self):
        for mood, mode, level, seed in itertools.product(MOODS_ONLY, ("major", "minor"),
                                                         ("basic", "advanced"), range(6)):
            song = compose(Key("E", mode), 100, TimeSig.parse("4/4"), level, seed, mood=mood)
            verse = [sl.chord.roman for sl in song.sections[1].slots]
            verse2 = [sl.chord.roman for sl in song.sections[3].slots]
            self.assertEqual(sum(a != b for a, b in zip(verse, verse2)), 1, (mood, mode, level, seed))

    def test_moods_use_their_harmony(self):
        def symbols(mood, mode, level="basic"):
            out = set()
            for seed in range(30):
                song = compose(Key("A", mode), 100, TimeSig.parse("4/4"), level, seed, FULL_FORM, mood=mood)
                out |= {sl.chord.symbol for sec in song.sections for sl in sec.slots}
            return out
        self.assertIn("Bb", symbols("angry", "minor"))         # Phrygian bII in A minor
        self.assertTrue({"F", "G"} <= symbols("angry", "major"))  # bVI, bVII in A major
        eerie = symbols("eerie", "minor")
        self.assertTrue({"Caug", "Fm"} <= eerie)                # III+ and the chromatic mediant vi
        self.assertIn("Am(maj7)", symbols("eerie", "minor", "advanced"))
        self.assertIn("D", symbols("happy", "minor"))           # Dorian IV
        self.assertIn("Dm", symbols("sad", "major"))            # borrowed iv

    def test_melody_character(self):
        def stats(mood):
            vel, gate = [], []
            for seed in range(5):
                song = compose(Key("C", "minor"), 100, TimeSig.parse("4/4"), "basic", seed, mood=mood)
                mel = song.track("Melody").notes
                vel += [n.velocity for n in mel]
                gate += [a.dur / (b.start - a.start) for a, b in zip(mel, mel[1:])]  # sounding fraction
            return sum(vel) / len(vel), sum(gate) / len(gate)
        sad, angry, eerie = stats("sad"), stats("angry"), stats("eerie")
        self.assertGreater(angry[0], sad[0] + 15)    # louder
        self.assertGreater(sad[0], eerie[0])         # eerie is the quietest
        self.assertLess(angry[1], sad[1] - 0.2)      # angry notes are short, sad ones legato

    def test_melody_rules_hold_for_every_mood(self):
        for mood, mode, tonic, sig in itertools.product(MOODS_ONLY, ("major", "minor"), ("C", "F#", "Bb"), SIGS):
            key, ts = Key(tonic, mode), TimeSig.parse(sig)
            ref = tonic_reference(key)
            for seed, level in itertools.product(range(2), ("basic", "intermediate", "advanced")):
                song = compose(key, 100, ts, level, seed, FULL_FORM, mood=mood)
                mel = song.track("Melody").notes
                for a, b in zip(mel, mel[1:]):
                    self.assertLessEqual(a.start + a.dur, b.start + 1e-6)
                for n in mel:
                    self.assertTrue(ref - 3 <= n.pitch <= ref + 17)
                    if any(abs(n.start % ts.bar_quarters - sp) < 1e-6 for sp in ts.strong_positions):
                        self.assertIn(n.pitch % 12, chord_at(song, n.start).pitch_classes, (mood, sig, seed))
                self.assertEqual(mel[-1].pitch % 12, key.tonic_pc)


class GuideTrackTests(unittest.TestCase):
    def test_no_mood_and_no_guides_is_the_original_song(self):
        for seed in range(5):
            a = compose(Key("Eb", "minor"), 90, TimeSig.parse("3/4"), "advanced", seed)
            b = compose(Key("Eb", "minor"), 90, TimeSig.parse("3/4"), "advanced", seed, mood=NONE,
                        bass=False, drums=False)
            self.assertEqual(song_to_midi(a), song_to_midi(b))
            self.assertEqual([t.name for t in a.tracks], ["Melody", "Chords"])

    def test_guides_never_change_melody_or_chords(self):
        for mood, sig, seed in itertools.product(MOOD_IDS, ("4/4", "6/8"), range(3)):
            ts = TimeSig.parse(sig)
            plain = compose(Key("G"), 100, ts, "intermediate", seed, FULL_FORM, mood=mood)
            full = compose(Key("G"), 100, ts, "intermediate", seed, FULL_FORM, mood=mood, bass=True, drums=True)
            for name in ("Melody", "Chords"):
                self.assertEqual(notes_of(plain, name), notes_of(full, name), (mood, sig, seed, name))
            self.assertEqual([t.name for t in full.tracks], ["Melody", "Chords", "Bass", "Drums"])

    def test_bass_follows_the_chords(self):
        for mood, sig, mode in itertools.product(MOOD_IDS, SIGS, ("major", "minor")):
            key, ts = Key("D", mode), TimeSig.parse(sig)
            song = compose(key, 100, ts, "advanced", 4, FULL_FORM, mood=mood, bass=True)
            bass = song.track("Bass").notes
            self.assertFalse(overlaps(bass), (mood, sig))
            self.assertTrue(all(26 <= n.pitch <= 52 and 1 <= n.velocity <= 127 for n in bass))
            for sec in song.sections:
                pedal = MOODS[mood]["bass"] == "pedal" and sec.kind in ("intro", "verse", "verse2")
                for sl in sec.slots:
                    first = [n for n in bass if abs(n.start - sl.start) < 1e-6]
                    self.assertEqual(len(first), 1, (mood, sig, sl.chord.symbol))
                    want = key.tonic_pc if pedal else sl.chord.root_pc
                    self.assertEqual(first[0].pitch % 12, want, (mood, sig, sec.kind, sl.chord.symbol))
            last = bass[-1]
            self.assertAlmostEqual(last.start + last.dur, song.total_quarters)

    def test_drums(self):
        for mood, sig in itertools.product(MOOD_IDS, SIGS + ["7/8"]):
            ts = TimeSig.parse(sig)
            song = compose(Key("A", "minor"), 100, ts, "basic", 2, FULL_FORM, mood=mood, drums=True)
            drums = song.track("Drums")
            self.assertEqual(drums.channel, 9)
            self.assertFalse(overlaps(drums.notes), (mood, sig))
            final = song.sections[-1].slots[-1].start
            self.assertTrue(all(n.start <= final + 1e-6 for n in drums.notes))         # nothing after the last hit
            self.assertIn(CRASH, [n.pitch for n in drums.notes if abs(n.start - final) < 1e-6])
            for sec in song.sections:
                if sec.kind in ("chorus", "chorus2", "verse2"):
                    self.assertIn(CRASH, [n.pitch for n in drums.notes if abs(n.start - sec.start) < 1e-6])
                inside = [n for n in drums.notes if sec.start - 1e-6 <= n.start < sec.start + sec.bars * ts.bar_quarters]
                self.assertGreater(len(inside), 0, (mood, sig, sec.kind))
            self.assertTrue(all(1 <= n.velocity <= 127 and n.dur > 0 for n in drums.notes))

    def test_drum_styles_differ(self):
        song = compose(Key("C"), 100, TimeSig.parse("4/4"), seed=1)
        ts = song.timesig
        kicks = {}
        for mood in MOOD_IDS:
            hits = drum_part(song.sections, ts, MOODS[mood]["drums"], random.Random(0))
            chorus = song.sections[2]
            kicks[mood] = sum(1 for t, _, p, _ in hits if p == KICK and chorus.start <= t < chorus.start + 4)
        self.assertGreater(kicks["angry"], kicks["none"])
        self.assertGreater(kicks["none"], kicks["sad"])

    def test_midi_with_guides(self):
        song = compose(Key("F"), 110, TimeSig.parse("4/4"), seed=9, mood="happy", bass=True, drums=True)
        _, _, tracks = parse_midi(song_to_midi(song))
        self.assertEqual(len(tracks), 5)
        names = [p.decode() for t in tracks[1:] for _, k, p in t if k == ("meta", 0x03)]
        self.assertEqual(names, ["Melody", "Chords", "Bass", "Drums"])
        bass_channels = {k[2] for _, k, _ in tracks[3] if k[0] == "note"}
        drum_channels = {k[2] for _, k, _ in tracks[4] if k[0] == "note"}
        self.assertEqual((bass_channels, drum_channels), ({2}, {9}))
        self.assertFalse(any(k[0] == "program" for _, k, _ in tracks[4]))  # no program change on drums


class InterfaceTests(unittest.TestCase):
    def test_build_song_options(self):
        song = build_song({"key": "A", "scale": "minor", "seed": 3, "mood": "eerie", "bass": True, "drums": True})
        data = song_payload(song)
        self.assertEqual(data["mood"], "eerie")
        self.assertEqual([t["name"] for t in data["tracks"]], ["Melody", "Chords", "Bass", "Drums"])
        self.assertTrue(data["filename"].endswith("_eerie_seed3_bass_drums.mid"), data["filename"])
        self.assertEqual(song_payload(build_song({"seed": 3}))["mood"], "none")
        for bad in ({"mood": "grumpy"}, {"bass": "yes"}, {"drums": 1}):
            with self.assertRaises(ValueError, msg=bad):
                build_song(bad)

    def test_cli_applies_the_mood_presets(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(cli.main(["--mood", "sad", "--bass", "--drums", "--seed", "1", "--out", tmp]), 0)
            files = sorted(p.name for p in Path(tmp).iterdir())
        self.assertEqual(files, [f"C_minor_72bpm_4-4_basic_sad_seed1_bass_drums.{ext}" for ext in ("json", "mid", "txt")])
        self.assertIn("Mood: sad", out.getvalue())
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            cli.main(["--mood", "angry", "--scale", "major", "--tempo", "150", "--seed", "1", "--out", tmp])
            self.assertEqual([p.name for p in Path(tmp).glob("*.mid")], ["C_major_150bpm_4-4_basic_angry_seed1.mid"])


if __name__ == "__main__":
    unittest.main()

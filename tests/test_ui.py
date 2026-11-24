import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from music_composer.arranger import CHORD_STYLES, compose
from music_composer.rhythm import TimeSig
from music_composer.theory import Key
from music_composer.ui import Handler, build_song, song_payload


def no_same_pitch_overlap(notes):
    by_pitch = {}
    for n in notes:
        by_pitch.setdefault(n.pitch, []).append((n.start, n.start + n.dur))
    for spans in by_pitch.values():
        spans.sort()
        for (s1, e1), (s2, _) in zip(spans, spans[1:]):
            if e1 > s2 + 1e-6:
                return False
    return True


class ChordStyleTests(unittest.TestCase):
    def test_styles(self):
        for sig in ("4/4", "3/4", "6/8", "5/4"):
            ts = TimeSig.parse(sig)
            songs = {s: compose(Key("G"), 100, ts, seed=11, chord_style=s) for s in CHORD_STYLES}
            block = songs["block"].track("Chords").notes
            arp = songs["arpeggio"].track("Chords").notes
            self.assertGreater(len(arp), len(block) * 1.5, sig)
            self.assertTrue(any(n.pitch < 48 for n in block))
            for s in songs.values():
                self.assertTrue(no_same_pitch_overlap(s.track("Chords").notes), sig)
                end = max(n.start + n.dur for n in s.track("Chords").notes)
                self.assertAlmostEqual(end, s.total_quarters)
            # the melody doesn't depend on the chord style
            self.assertEqual([(n.start, n.pitch) for n in songs["block"].track("Melody").notes],
                             [(n.start, n.pitch) for n in songs["arpeggio"].track("Melody").notes])


class ChordsOnlyStyleTests(unittest.TestCase):
    """The default style must look like a hand-entered chord track: every chord held,
    in root position, no extra bass note, steady velocity."""

    def test_root_position_chords_only(self):
        for level in ("basic", "intermediate", "advanced"):
            for mode in ("major", "minor"):
                for tonic in ("C", "F#", "Bb", "E"):
                    song = compose(Key(tonic, mode), 100, TimeSig.parse("3/4"), level, seed=5)
                    self.assertEqual(song.chord_style, "chords")
                    notes = song.track("Chords").notes
                    for sec in song.sections:
                        for sl in sec.slots:
                            chord = [n for n in notes if abs(n.start - sl.start) < 1e-6]
                            pitches = sorted(n.pitch for n in chord)
                            self.assertEqual(pitches[0] % 12, sl.chord.root_pc, sl.chord.symbol)  # root at the bottom
                            self.assertTrue(48 <= pitches[0] <= 59 and pitches[-1] <= 73, pitches)
                            self.assertTrue(set(p % 12 for p in pitches) <= set(sl.chord.pitch_classes))
                            self.assertEqual(len({n.velocity for n in chord}), 1)
                            self.assertEqual(len({n.dur for n in chord}), 1)

    def test_old_style_name_still_works(self):
        song = build_song({"key": "C", "seed": 1, "chord_style": "block-no-root"})
        self.assertEqual(song.chord_style, "chords")


class UiTests(unittest.TestCase):
    def test_build_song_validation(self):
        for bad in ({"key": "H"}, {"tempo": "fast"}, {"tempo": 999}, {"level": "expert"},
                    {"time": "4/3"}, {"form": ["bridge"]}, {"seed": -4}, {"chord_style": "strum"}, []):
            with self.assertRaises(ValueError, msg=bad):
                build_song(bad)

    def test_payload_is_json(self):
        song = build_song({"key": "Eb", "scale": "minor", "time": "6/8", "seed": 3, "chord_style": "arpeggio"})
        data = json.loads(json.dumps(song_payload(song)))
        self.assertEqual(data["seed"], 3)
        self.assertEqual([t["name"] for t in data["tracks"]], ["Melody", "Chords"])
        self.assertTrue(data["filename"].endswith("_arpeggio.mid"))

    def test_http_endpoints(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            for path in ("/", "/app.js", "/style.css", "/api/options"):
                with urllib.request.urlopen(base + path) as r:
                    self.assertEqual(r.status, 200, path)

            def post(path, body):
                req = urllib.request.Request(base + path, data=json.dumps(body).encode(),
                                             headers={"Content-Type": "application/json"})
                return urllib.request.urlopen(req)

            with post("/api/compose", {"key": "D", "seed": 5}) as r:
                self.assertEqual(json.loads(r.read())["seed"], 5)
            with post("/api/midi", {"key": "D", "seed": 5}) as r:
                self.assertEqual(r.read()[:4], b"MThd")
                self.assertIn("attachment", r.headers["Content-Disposition"])
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                post("/api/compose", {"key": "Q"})
            self.assertEqual(ctx.exception.code, 400)
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(base + "/../ui.py")
            self.assertEqual(ctx.exception.code, 404)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()

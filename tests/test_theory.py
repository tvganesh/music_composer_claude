import unittest

from music_composer.theory import Key, note_pc, parse_roman


def names(token, key):
    return parse_roman(token, key).symbol


class TheoryTests(unittest.TestCase):
    def test_note_parsing(self):
        self.assertEqual(note_pc("C"), 0)
        self.assertEqual(note_pc("f#"), 6)
        self.assertEqual(note_pc("Bb"), 10)
        self.assertEqual(note_pc("Cb"), 11)
        with self.assertRaises(ValueError):
            note_pc("H")

    def test_diatonic_triads_in_c_major(self):
        c = Key("C")
        got = [names(n, c) for n in ["I", "ii", "iii", "IV", "V", "vi", "vii°"]]
        self.assertEqual(got, ["C", "Dm", "Em", "F", "G", "Am", "Bdim"])

    def test_minor_key_uses_case_for_quality(self):
        a = Key("A", "minor")
        self.assertEqual(names("v", a), "Em")
        self.assertEqual(names("V", a), "E")      # harmonic-minor dominant
        self.assertEqual(names("VI", a), "F")
        self.assertEqual(names("VII", a), "G")
        self.assertEqual(parse_roman("V", a).pitch_classes, (4, 8, 11))  # E G# B

    def test_spelling_follows_key(self):
        self.assertEqual(names("IV", Key("F")), "Bb")
        self.assertEqual(names("vii°", Key("F#")), "E#dim")
        self.assertEqual(names("bVI", Key("C")), "Ab")   # borrowed, spelled with a flat
        self.assertEqual(names("III", Key("C", "minor")), "Eb")

    def test_extended_qualities(self):
        c = Key("C")
        self.assertEqual(parse_roman("V7", c).pitch_classes, (7, 11, 2, 5))
        self.assertEqual(names("Imaj7", c), "Cmaj7")
        self.assertEqual(names("ii7", c), "Dm7")
        self.assertEqual(names("viiø7", c), "Bm7b5")
        self.assertEqual(names("V7sus4", c), "G7sus4")
        self.assertEqual(parse_roman("#iv°7", c).pitch_classes, (6, 9, 0, 3))

    def test_secondary_dominants(self):
        c = Key("C")
        self.assertEqual(names("V7/vi", c), "E7")
        self.assertEqual(names("V/V", c), "D")
        self.assertEqual(names("vii°7/V", c), "F#dim7")

    def test_key_signatures(self):
        self.assertEqual(Key("C").key_signature(), 0)
        self.assertEqual(Key("D").key_signature(), 2)
        self.assertEqual(Key("Eb").key_signature(), -3)
        self.assertEqual(Key("D", "minor").key_signature(), -1)
        self.assertEqual(Key("F#", "minor").key_signature(), 3)
        self.assertEqual(Key("D#").key_signature(), -3)  # enharmonic Eb major


if __name__ == "__main__":
    unittest.main()

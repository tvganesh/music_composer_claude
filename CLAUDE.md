# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Melodic Chordal Sequencer: generates a chord sequence and a melody for a whole song (Intro → Verse 1 → Chorus → Verse 2 → Ending by default) and writes a MIDI file (Melody, Chords) for Logic Pro. An optional mood (happy, sad, angry, eerie) reshapes chords, melody and groove. Optional Bass and Drums tracks are *guide* parts only: the user replaces them with Logic's Session Players.

**Pure Python 3 standard library, with no third-party dependencies** (it must run on the Python that ships with macOS). The MIDI writer, HTTP server and in-browser synth are all hand-written. Don't add packages.

## Commands

```bash
python3 -m music_composer.ui                    # web app at http://127.0.0.1:8765 (tries the next 19 ports if busy)
python3 -m music_composer.ui --port 9000 --no-browser
python3 -m music_composer --key D --scale minor --tempo 92 --time 6/8 --level advanced --seed 7   # CLI → output/*.mid/.txt/.json
python3 -m music_composer --key A --mood eerie --bass --drums

python3 -m unittest discover -s tests -t .                                      # all tests
python3 -m unittest tests.test_song                                             # one file
python3 -m unittest tests.test_song.SongTests.test_same_seed_same_song          # one test
```

There is no build step, linter config or packaging.

## Architecture

The pipeline is driven by `arranger.compose()`, which the CLI (`cli.py`) and the web server (`ui.py`) both call:

1. **`progressions.py`**: `PROGRESSIONS[level][mode][section]` lists Roman-numeral strings. A chord lasts one bar unless it has a `:bars` suffix (`"IV V I:2"`, `"V:0.5"`). `SUBSTITUTIONS` (diatonic, per level) and `MODAL_SUBSTITUTIONS` (modal interchange, Intermediate and Advanced only) drive the one-chord change in Verse 2's second half.
2. **`theory.py`**: `parse_roman(token, key)` turns a numeral into a correctly spelled `Chord`. It handles accidentals (`bVI`, `#i°7`), qualities (`maj7`, `ø7`, `sus4`, `add9`, `6` …) and secondary dominants (`V7/vi`). Any new chord token used in a progression has to parse here in every key; `test_every_progression_chord_builds_in_every_key` checks this.
3. **`arranger.py`** lays out `Section`s of `ChordSlot`s in time, where **all times are in quarter notes** from the start of the song. It then renders the Chords track in one of three styles (`chords`, `block`, `arpeggio`) using `voicing.py`, and the Melody track using `melody.py`.
4. **`melody.py`** builds each section from 2-bar units with phrase plans (verse `A A′ B A′`, chorus `H H′ C H′` …) out of rhythm cells from `rhythm.py`. Pitch rules: chord tones on strong beats and long notes, and stepwise motion otherwise. The scale is adjusted per chord (`chord_scale`), so borrowed or chromatic chords get the right accidentals.
5. **Moods** (`moods.py`): mood `none` means the level's own library and `DEFAULT_STYLE`. Any other mood replaces the progressions (tier `basic` for the Basic level, `rich` for Intermediate and Advanced) and the Verse 2 substitutions (no modal interchange). It also supplies a `MelodyStyle` (`melody.py`), a chord velocity offset, and bass and drum style names. Every verse progression must have a valid substitution; `tests/test_moods.py` checks this.
6. **Guide tracks** (`groove.py`): `bass_part` and `drum_part` work from the same sections and slots. Bass is on channel 3 and Drums on channel 10 (index 9, GM drum notes, no program change).
7. **Output**: `midi_export.py` writes format 1 MIDI at 480 PPQ (conductor track with tempo, time signature, key and section markers). `sheet.py` writes the chord sheet, JSON and file stem.

### Determinism (important invariant)

The same seed and options must always give the same song, and the tests check this. `compose()` deliberately uses **separate random streams**:
- the main `rng` picks the progressions and always draws the diatonic Verse 2 substitution, even when a modal substitution replaces it, so that later draws don't shift;
- `modal_rng` (seeded `f"modal-{seed}"`) is used only for modal interchange, so adding it didn't change existing songs;
- `melody_rng` and `chords_rng` are split off so that changing the chord style never changes the melody.
- Bass and Drums use string-seeded streams (`f"bass-{seed}"`, `f"drums-{seed}"`), so turning them on never changes the melody or the chords.
- `MelodyStyle()` defaults reproduce the original draws exactly. When changing `melody.py`, check that a song with no mood still matches the earlier version byte for byte.

When adding randomness, give it its own stream or append draws after the existing ones. Don't insert draws into an existing stream.

### Web app and deployment

- `ui.py` is a stdlib `BaseHTTPRequestHandler`. Endpoints: `GET /api/options` (the `OPTIONS` dict that populates the UI), `POST /api/compose` (JSON song payload for the piano roll and chord sheet), `POST /api/midi` (the `.mid` file). `build_song()` validates the UI parameters and raises `ValueError`, which becomes an HTTP 400.
- Static files are served only if they're listed in `STATIC_FILES` in `ui.py`. A new file in `static/` must be added there too.
- `static/app.js` is plain JS with no build step. It handles settings, piano roll, chord sheet and a Web Audio preview synth.
- **Vercel**: `api/index.py` subclasses `ui.Handler` as `handler`, and `vercel.json` rewrites every path except `/_vercel/*` to it. Local and deployed behaviour therefore come from the same code. `.vercelignore` excludes `output/` and `tests/`. Vercel Analytics is loaded in `index.html` only when the host isn't localhost.

### Option lists live in several places

Levels, chord styles, section kinds, the default form and moods are defined in `arranger.py`, `progressions.py` and `moods.py`. They are re-exposed by `cli.py` (argparse choices; `--level` choices are hardcoded) and by `ui.py`'s `OPTIONS` (which also hardcodes the keys, time signatures and chord style labels). Adding a new option means updating all of these. `STYLE_ALIASES` keeps the old `block-no-root` name working as `chords`. The front end (`app.js`) has its own lists too: `TRACKS` and the `track<Name>` checkboxes in `index.html`, and the drum synth and `DRUM_LANE`, which are keyed by GM note number. A new drum note or track needs changes there as well.

## Repo notes

- `output/` holds committed example outputs generated by the CLI. `output/*.logicx/` and `output/video/` are gitignored.
- `README.md` is the user-facing documentation (levels, chord styles, Logic Pro workflow). Update it when user-visible behaviour changes.

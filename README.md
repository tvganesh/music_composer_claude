# Melodic Chordal Sequencer

Generates a **chord sequence and a melody** for a whole song and writes them as a MIDI file
for Logic Pro. You choose the key, scale, tempo, time signature, level and, if you like, a
**mood** (happy, sad, angry, eerie). The song form is Intro → Verse 1 → Chorus → Verse 2 → Ending.

You can also add **Bass and Drums guide tracks** to hear the groove while you write. They're
meant to be replaced: delete them in Logic and let the Session Players play bass and drums
from your chords.

The only requirement is Python 3 (the version built into macOS works). There are no other dependencies.

## The app (recommended)

```bash
python3 -m music_composer.ui
```

This opens the composer in your browser at http://127.0.0.1:8765. Press **Ctrl+C** in the terminal to stop it.

- **Settings** (left): mood, key, scale, tempo, time signature, level, chord style, guide tracks,
  song form and seed. Every change regenerates the song instantly. Picking a mood also sets its
  suggested scale and tempo, which you can then change.
- **Play** previews the song in the browser:
  - **Space** plays or pauses.
  - **Stop** (■, or **Esc**) returns to where you pressed Play. Press it again to go back to bar 1.
  - **Home** goes back to the start.
  - Click the piano roll or any bar in the chord sheet to jump there.
  - Turn on **Loop section** to repeat the part you're working on.
  - Mute a track (Melody, Chords, Bass, Drums) with its checkbox.
- **New song** rolls a fresh seed. Typing a seed brings back a song you liked.
- **Download MIDI** saves the `.mid` file for Logic Pro.

The browser preview uses a simple built-in synth. It's for judging the notes; the real sound comes from Logic.

### Online (Vercel)

The same app can run on Vercel. `api/index.py` reuses the local server's request handler, and
`vercel.json` sends every request to it.

1. On [vercel.com](https://vercel.com), choose **Add New › Project** and import this GitHub repository.
2. Leave the framework preset as **Other**, with no build command, and click **Deploy**.

Every push to `main` then redeploys automatically.

**Analytics:** in the project on Vercel, open **Analytics** and click **Enable**. The page
already loads Vercel's analytics script, but only on the deployed site, not when it runs locally.

### Levels

| Level | Chords you get | Example (C major / A minor) |
|---|---|---|
| **Basic** | Triads from the key; the major V in minor keys | C Am F G · Am F C G |
| **Intermediate** | Seventh chords, ii–V–I, sus chords, and modal colour: borrowed iv and ♭VII in major, the Dorian IV in minor | Cmaj7 Am7 Dm7 G7 · Fmaj7 **Fm** Cmaj7 · Fmaj7 Cmaj7 **B♭** F · Am7 **D** Fmaj7 E7 |
| **Advanced** | Modal interchange (♭VI, ♭VII, iv6), secondary dominants (V7/vi, V7/ii, V7/iv), diminished passing chords, 9ths and add9, the Neapolitan ♭II, the minor line cliché and the Picardy third | Cmaj7 **E7** Am7 Dm7 G7 · Cmaj7 **C♯dim7** Dm7 G7 · **A♭maj7 B♭** Cmaj9 · Am Am(maj7) Am7 Am6 · Am7 Dm7 **B♭** E7 · Dm6 E7 **A** |

The melody follows every chord, including borrowed and chromatic ones. Over E7 in A minor it
uses G♯, and over Fm in C major it uses A♭.

**Verse 2** repeats the verse, then changes one chord in its second half so it sounds familiar
but new:

- **Basic:** a close relative from the same key (Am → Em).
- **Intermediate and Advanced:** **modal interchange**, a chord borrowed from the parallel key with the same job.

| Key | Borrowed swaps (examples in C major / D minor) |
|---|---|
| Major, from the parallel minor | Am7 → A♭maj7 or Fm7 · Dm7 → Dm7♭5 · Em7 → E♭maj7 · Fmaj7 → Fm7 |
| Minor, from Dorian, harmonic minor and Phrygian | Gm7 → G7 · Em7♭5 → Em7 · Am7 → A7 · B♭maj7 → E♭maj7 |

The melody keeps its rhythm and shape. Only the notes over the borrowed chord, and the few
that follow on from them, change (E → E♭ over A♭maj7, for example). Everything after Verse 2
stays the same.

### Moods

A mood changes the chords, the melody and the guide tracks together. **None** is the original
generator; every seed still gives the same song as before.

| Mood | Suggested | Chords | Melody | Bass / Drums |
|---|---|---|---|---|
| **Happy** | major, 120 BPM | Bright major chords, add9 and maj7 colour; in minor keys the Dorian IV and a major final chord | Rising, bouncy, some leaps, detached notes | A note on every beat (root, fifth, octave) stepping into the next chord · pop beat with a pushed kick, claps and open hats in the chorus |
| **Sad** | minor, 72 BPM | vi-centred major, borrowed iv and iv6; in minor the line cliché (Am Am(maj7) Am7 Am6) | Falling, stepwise, sparse, long and soft | Long roots and fifths walking down into the next chord · half-time: kick on 1, cross-stick (verse) or snare (chorus) on 3 |
| **Angry** | minor, 140 BPM | Phrygian ♭II (B♭ in A minor), ♭VI–♭VII–I, dominant 7ths | Riff-like: repeated notes, leaps, short and loud | Driving eighth-note roots · kick on every beat (every eighth in the chorus), loud snare, tom fills |
| **Eerie** | minor, 64 BPM | Chromatic mediants (Am → Fm), augmented and minor-major chords, diminished 7ths | Thin, high, very sparse, quiet | Tonic pedal under the intro and verses · ritual pulse: floor tom, kick, pedal hi-hat, low toms and ride bell |

Moods use their own chord library, so the **Level** only chooses between triads (Basic) and
sevenths and colour chords (Intermediate and Advanced). Verse 2 still changes one chord.

### Guide tracks: Bass and Drums

Turn on **Bass** and/or **Drums** under *Guide tracks*. They follow the song's chords and
sections: a lighter intro, a fuller chorus, a fill in the last bar of each section, a crash
where the next one starts, and one hit on the final chord. Their style comes from the mood
(see the table above; with no mood you get root–fifth bass and a straight rock beat).

Adding or removing them never changes the melody or the chords.

### Chord styles

| Style | What's in the Chords track | Use it when |
|---|---|---|
| **Chords only** (default) | Held chords in root position (A C E, E G♯ B D), steady velocity, nothing else | Almost always: Logic's Arpeggiator, the Chord track and Session Players all read these directly |
| **With bass** | A voice-led chord plus a low root note in the left hand | You want a fuller piano part to play as it is |
| **Arpeggio** | The low root plus the chord broken into eighth notes, written into the MIDI | You want a simple arpeggio without any Logic setup |

Changing the chord style never changes the melody.

For Logic's own arpeggio styles, use **Chords only** and put Logic's Arpeggiator on the track
(step 4 under *In Logic Pro*). With Bass, the low root note would be arpeggiated along with the
chord. The built-in Arpeggio style is one fixed pattern.

## Command line

```bash
python3 -m music_composer --key C --scale major --tempo 100 --time 4/4 --level basic
python3 -m music_composer --key D --scale minor --tempo 92 --time 6/8 --seed 7
python3 -m music_composer --key Bb --time 3/4 --form intro,verse,chorus,verse2,chorus2,ending
python3 -m music_composer --key A --mood eerie --bass --drums
python3 -m music_composer --help
```

| Option | Meaning |
|---|---|
| `--key` | Tonic: C, F#, Bb … |
| `--scale` | `major` or `minor`. Minor uses natural minor plus a major V chord (with the leading tone) at cadences. |
| `--tempo` | BPM (30–300) |
| `--time` | `4/4`, `3/4` and `6/8` have hand-picked melody rhythms. Others (5/4, 12/8 …) use rhythms built from their beats. |
| `--level` | `basic`, `intermediate` or `advanced`; see Levels above |
| `--seed` | Same seed and options give the same song. Every run prints the seed it used. |
| `--form` | Comma-separated list of sections: `intro, verse, chorus, verse2, chorus2, ending` |
| `--chord-style` | `chords` (default; Chords only), `block` (With bass) or `arpeggio`. The older name `block-no-root` still works and means `chords`. |
| `--mood` | `none` (default), `happy`, `sad`, `angry` or `eerie`. Without `--scale` or `--tempo`, the mood's suggested ones are used. |
| `--bass`, `--drums` | Add the Bass and/or Drums guide track |
| `--out` | Output folder (default `./output`) |

Each run writes three files to the output folder:

- `.mid` containing:
  - a conductor track with tempo, time signature, key signature and section markers
  - **Melody** (channel 1)
  - **Chords** (channel 2): one chord per change, in the chosen style (see Chord styles above)
  - **Bass** (channel 3), if `--bass`
  - **Drums** (channel 10, General MIDI drum map), if `--drums`
- `.txt`: a chord sheet with chord symbols and Roman numerals, bar by bar
- `.json`: the same structure in machine-readable form

## How the melody is written

Each section is made of 2-bar phrases:

| Section | Phrase plan |
|---|---|
| Intro | A sparse preview of the chorus hook's shape, ending open |
| Verse | **A A′ B A′**. A′ starts like A but ends with a cadence. B gives contrast and rises toward the chorus. |
| Chorus | **H H′ C H′**. H is the hook: higher, busier, often repeating its rhythm. |
| Verse 2 | The verse phrases with small ornaments, over the Verse 2 chords (one borrowed chord at Intermediate and Advanced) |
| Chorus 2 | The chorus again, unchanged, so the hook sticks |
| Ending | The hook, then a cadence that lands on the tonic and rings out |

Pitch rules:

- Strong beats and long notes are chord tones.
- In-between notes move by scale step. A non-chord tone is always left by step.
- After a leap, the line steps back the other way.
- Phrase endings land on stable notes: an open chord tone mid-section, the tonic at the end.
- The scale follows each chord, so you get G♯ rather than G over E major in A minor.

## In Logic Pro (11 or later)

1. **File › Open…** and choose the `.mid` file. You get the **Melody** and **Chords** tracks, plus
   the tempo, time signature and section markers.
2. Pick instruments in the Library, for example a piano or pad for Chords and a lead, strings or
   flute for Melody. If you added guide tracks, give Bass a bass instrument and Drums a
   **Drum Kit Designer** kit (it reads the General MIDI drum notes).
3. **Give the Session Players the chords.** Show the Chord track
   (**Track › Global Tracks › Chord**), then drag the **Chords** region onto it. Logic detects
   the chords from the region. With Chords only or With bass, the root is the lowest note, so
   Logic reads them as the right chords. You can also type the chords in from the `.txt` chord sheet.
4. **Arpeggiate the chords with Logic** (optional). Use a file made with the **Chords only** style.
   On the Chords track's channel strip, click the **MIDI FX** slot (above the instrument slot)
   and choose **Arpeggiator**. It now arpeggiates the chords in the region on playback, so you
   don't need to play anything live. Choose a preset or set the style yourself:
   - note order: up, down, up/down, outside-in, random, as played
   - rate (1/8, 1/16, triplets)
   - octave range
   - gate and swing
   - Latch mode

   The Play Surface's arpeggiator only acts on notes you play live, not on a region. Files made
   with the With bass style also arpeggiate the low root note, which breaks up the pattern;
   Chords only avoids that.
5. **Add bass and drums:** **Track › New Track › Session Player**. Choose Bass Player and
   Drummer (and Keyboard Player if you want comping). They follow the Chord track automatically.
   Choose a style per section using the markers.
6. You can then mute the Chords track if the Keyboard Player covers it. Delete (or mute) the
   Bass and Drums guide tracks once the Session Players are in.
7. Mix and master:
   - Channel EQ and compression per track, plus shared reverb and delay sends
   - Mastering Assistant on the Stereo Out, aiming for about −14 LUFS integrated and −1 dBTP true peak

## Code layout

| Module | Role |
|---|---|
| `theory.py` | Keys, scales and correct note spelling. Builds chords from Roman numerals (`I`, `vi`, `V7`, `bVI`, `V7/vi`, `#iv°7`, `Isus4` …). |
| `progressions.py` | Progression library by level, mode and section, plus the Verse 2 substitution rules (diatonic and modal interchange) |
| `moods.py` | Moods: each mood's progressions and Verse 2 substitutions, melody style, chord loudness, bass and drum styles, and suggested scale and tempo |
| `groove.py` | Bass and Drums guide tracks |
| `voicing.py` | Picks the close-position voicing that moves least from the previous chord, and adds the left-hand root. 9th chords leave the root to the left hand (Am9 → A + C E G B). |
| `rhythm.py` | Time signatures and the melody rhythm cells (sparse, medium, busy, cadence) |
| `melody.py` | Motifs, contours, phrase plans and cadences, shaped by a `MelodyStyle` |
| `arranger.py` | Song form, timing and the Chords part |
| `midi_export.py` | MIDI file writer (format 1, 480 PPQ) |
| `sheet.py` | Chord sheet and JSON output |
| `ui.py`, `static/` | Local web app: HTTP server, page, piano roll and preview synth |

Run the tests with:

```bash
python3 -m unittest discover -s tests -t .
```

## Roadmap

1. ✅ Theory core, Basic level, MIDI export
2. ✅ Melody generator
3. ✅ Intermediate level: sevenths, ii–V–I, sus chords, borrowed iv and ♭VII
4. ✅ Advanced level: modal interchange, secondary dominants, diminished passing chords, Neapolitan, Picardy third
5. ✅ Web UI with preview playback
6. ✅ Moods, and Bass and Drums guide tracks
7. Polish: more melody rhythms, modes (Dorian, Phrygian, Lydian) as scales, and an optional bridge

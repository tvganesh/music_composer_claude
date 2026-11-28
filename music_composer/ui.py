"""Local web UI for the composer (standard library only).

    python3 -m music_composer.ui            # opens http://127.0.0.1:8765 in your browser
    python3 -m music_composer.ui --port 9000 --no-browser

The page talks to three JSON endpoints:
    GET  /api/options  the choices shown in the settings panel
    POST /api/compose  settings -> song (sections, chords, notes, chord sheet)
    POST /api/midi     settings -> the .mid file
The server only listens on 127.0.0.1, so it isn't reachable from other machines.
"""
from __future__ import annotations

import argparse
import json
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .arranger import CHORD_STYLES, DEFAULT_CHORD_STYLE, DEFAULT_FORM, LABELS, SECTION_KINDS, STYLE_ALIASES, compose
from .midi_export import song_to_midi
from .moods import MOOD_IDS, MOODS, check_mood
from .progressions import LEVEL_INFO, LEVELS
from .rhythm import TimeSig
from .sheet import chord_sheet, file_stem, song_title
from .theory import Key

STATIC = Path(__file__).parent / "static"
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
}
MAX_BODY = 64 * 1024

OPTIONS = {
    "keys": ["C", "C#", "Db", "D", "Eb", "E", "F", "F#", "Gb", "G", "Ab", "A", "Bb", "B"],
    "scales": ["major", "minor"],
    "times": ["4/4", "3/4", "6/8", "2/4", "5/4", "12/8"],
    "levels": [{"id": lvl, "label": lvl.capitalize(), "available": lvl in LEVELS, "hint": LEVEL_INFO[lvl]}
               for lvl in ("basic", "intermediate", "advanced")],
    "chord_styles": [{"id": "chords", "label": "Chords only"},
                     {"id": "block", "label": "With bass"},
                     {"id": "arpeggio", "label": "Arpeggio"}],
    "default_chord_style": DEFAULT_CHORD_STYLE,
    "sections": [{"id": k, "label": LABELS[k]} for k in SECTION_KINDS],
    "default_form": list(DEFAULT_FORM),
    "moods": [{"id": k, "label": MOODS[k]["label"], "hint": MOODS[k]["hint"],
               "scale": MOODS[k]["scale"], "tempo": MOODS[k]["tempo"]} for k in MOOD_IDS],
    "guide_tracks": [{"id": "bass", "label": "Bass"}, {"id": "drums", "label": "Drums"}],
    "tempo": {"min": 40, "max": 220, "default": 100},
}


def build_song(params: dict):
    """Validate UI settings and compose. Raises ValueError with a readable message."""
    if not isinstance(params, dict):
        raise ValueError("Settings must be a JSON object")
    key = Key(str(params.get("key", "C")), str(params.get("scale", "major")))
    ts = TimeSig.parse(str(params.get("time", "4/4")))
    try:
        tempo = int(params.get("tempo", 100))
    except (TypeError, ValueError):
        raise ValueError("Tempo must be a whole number")
    if not 30 <= tempo <= 300:
        raise ValueError("Tempo must be between 30 and 300 BPM")
    level = str(params.get("level", "basic"))
    if level not in LEVELS:
        raise ValueError(f"The {level} level isn't built yet")
    seed = params.get("seed")
    if seed in (None, ""):
        seed = None
    else:
        try:
            seed = int(seed)
        except (TypeError, ValueError):
            raise ValueError("Seed must be a whole number")
        if not 0 <= seed <= 999_999_999:
            raise ValueError("Seed must be between 0 and 999999999")
    form = params.get("form") or list(DEFAULT_FORM)
    if not isinstance(form, list):
        raise ValueError("Form must be a list of sections")
    style = str(params.get("chord_style", DEFAULT_CHORD_STYLE))
    style = STYLE_ALIASES.get(style, style)
    if style not in CHORD_STYLES:
        raise ValueError(f"Unknown chord style {style!r}")
    mood = check_mood(params.get("mood"))
    extras = {}
    for name in ("bass", "drums"):
        value = params.get(name, False)
        if not isinstance(value, bool):
            raise ValueError(f"{name.capitalize()} must be true or false")
        extras[name] = value
    return compose(key, tempo, ts, level, seed, tuple(str(k) for k in form), style, mood, **extras)


def song_payload(song) -> dict:
    ts = song.timesig
    return {
        "seed": song.seed,
        "title": song_title(song),
        "key": song.key.name,
        "tempo": song.tempo,
        "time": ts.label,
        "bar_quarters": ts.bar_quarters,
        "group_quarters": ts.group_quarters,
        "total_quarters": song.total_quarters,
        "level": song.level,
        "chord_style": song.chord_style,
        "mood": song.mood,
        "filename": file_stem(song) + ".mid",
        "sections": [
            {"kind": sec.kind, "label": sec.label, "start": sec.start, "bars": sec.bars,
             "chords": [{"symbol": sl.chord.symbol, "roman": sl.chord.roman,
                         "start": sl.start, "length": sl.length} for sl in sec.slots]}
            for sec in song.sections
        ],
        "tracks": [
            {"name": t.name, "notes": [[round(n.start, 4), round(n.dur, 4), n.pitch, n.velocity]
                                       for n in t.notes]}
            for t in song.tracks
        ],
        "sheet": chord_sheet(song),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "MelodicChordalSequencer/1.0"

    def log_message(self, fmt, *args):  # keep the terminal quiet
        pass

    def _send(self, status, body: bytes, content_type: str, extra: dict = None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status, obj):
        self._send(status, json.dumps(obj).encode("utf-8"), "application/json")

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/options":
            return self._json(HTTPStatus.OK, OPTIONS)
        if path in STATIC_FILES:
            name, ctype = STATIC_FILES[path]
            return self._send(HTTPStatus.OK, (STATIC / name).read_bytes(), ctype)
        self._json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path not in ("/api/compose", "/api/midi"):
            return self._json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > MAX_BODY:
                raise ValueError("Request too large")
            params = json.loads(self.rfile.read(length) or b"{}")
            song = build_song(params)
        except (ValueError, json.JSONDecodeError) as e:
            return self._json(HTTPStatus.BAD_REQUEST, {"error": str(e)})

        if path == "/api/compose":
            return self._json(HTTPStatus.OK, song_payload(song))
        name = file_stem(song) + ".mid"
        self._send(HTTPStatus.OK, song_to_midi(song, song_title(song)), "audio/midi",
                   {"Content-Disposition": f'attachment; filename="{name}"'})


def serve(port: int = 8765, open_browser: bool = True):
    server = None
    for p in range(port, port + 20):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", p), Handler)
            break
        except OSError:
            continue
    if server is None:
        raise SystemExit(f"No free port between {port} and {port + 19}")
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"Melodic Chordal Sequencer is running at {url}  (press Ctrl+C to stop)")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


def main(argv=None):
    p = argparse.ArgumentParser(prog="python3 -m music_composer.ui", description="Melodic Chordal Sequencer web UI")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--no-browser", action="store_true", help="don't open a browser window")
    args = p.parse_args(argv)
    serve(args.port, not args.no_browser)


if __name__ == "__main__":
    main()

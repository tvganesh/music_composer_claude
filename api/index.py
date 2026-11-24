"""Vercel entry point: every request is routed here (see vercel.json).

It reuses the local app's request handler, so the page, /api/options,
/api/compose and /api/midi behave exactly as with `python3 -m music_composer.ui`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from music_composer.ui import Handler  # noqa: E402


class handler(Handler):  # Vercel looks for a class named `handler`
    pass

"""
Vercel's entrypoint.

Vercel's Python runtime looks for handlers under `api/`, imports the module,
and serves whatever ASGI application it finds exported as `app`. There is no
Procfile, no uvicorn and no port: the platform owns the server, and this file
is only here to point it at the application that already exists.

The parent directory goes on sys.path because the modules this app is built
from — extraction, parsing, prompt — sit next to app.py in the repository root,
and the bundle is unpacked with `api/` as the handler's own directory. Without
this line the import fails and every route 500s identically, which is exactly
the failure that is hardest to read from a browser.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import app  # noqa: E402

__all__ = ["app"]

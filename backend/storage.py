"""Where uploaded audio and extracted artwork live on disk.

Resolved at call time rather than import time, the same way DATABASE_URL is
handled, so a fresh clone with no .env works and the test suite can point the
app at a temporary directory instead of the developer's real uploads folder.
"""

import os
from pathlib import Path

DEFAULT_UPLOAD_DIR = "uploads"

# Read at call time, not import time, so tests and the CLI can set it.
UPLOAD_DIR_ENV = "HARMONIA_UPLOAD_DIR"


def resolve_upload_dir(explicit: str | os.PathLike | None = None) -> Path:
    """An explicit argument wins, then HARMONIA_UPLOAD_DIR, then the default."""
    if explicit is not None:
        return Path(explicit)
    return Path(os.getenv(UPLOAD_DIR_ENV, DEFAULT_UPLOAD_DIR))


def resolve_artwork_dir(upload_dir: str | os.PathLike | None = None) -> Path:
    """Extracted cover art lives alongside the audio it came from."""
    return resolve_upload_dir(upload_dir) / "artwork"

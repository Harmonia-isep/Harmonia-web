"""Folder scanner: register (and optionally analyze) local audio files.

Local-first ingestion. Unlike the web upload (which copies into uploads/), this
references files IN PLACE: Track.file_path is the absolute original path. Dedup
is by content hash - blake2b over the file size plus its first and last 1 MB, not
a full read - with file_path as a secondary key, so the library survives
reorganisation: a moved file relinks instead of duplicating.

Registration is the default; analysis is opt-in (it is CPU-bound and a large
library would otherwise start a long job silently).

    python -m backend.scan PATH [--analyze] [--reanalyze] [--no-recursive]
                                [--dry-run] [--ext .mp3,.flac,...]

Assumes the schema is migrated (alembic upgrade head), same as the app.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys

from mutagen import File as MutagenFile

from backend.api.analysis import run_analysis
from backend.audio.artwork import extract_artwork
from backend.models.database import create_database_engine, create_session_factory
from backend.models.models import Analysis, Track

DEFAULT_EXTS = (".mp3", ".flac", ".wav", ".m4a", ".aac", ".ogg", ".opus")
_CHUNK = 1024 * 1024        # 1 MB
_SECS_PER_TRACK = 1.5       # rough analyze estimate for the pre-run message


def content_hash(path: str) -> str:
    """blake2b over the file size plus its first and last 1 MB (not a full read)."""
    size = os.path.getsize(path)
    h = hashlib.blake2b()
    h.update(str(size).encode())
    with open(path, "rb") as f:
        h.update(f.read(_CHUNK))
        if size > _CHUNK:
            f.seek(max(0, size - _CHUNK))
            h.update(f.read(_CHUNK))
    return h.hexdigest()


def read_metadata(path: str):
    """(title, artist, album, duration) via mutagen; title falls back to filename."""
    title = artist = album = None
    duration = None
    try:
        easy = MutagenFile(path, easy=True)
        if easy is not None:
            title = (easy.get("title") or [None])[0]
            artist = (easy.get("artist") or [None])[0]
            album = (easy.get("album") or [None])[0]
            info = getattr(easy, "info", None)
            if info is not None and getattr(info, "length", 0):
                duration = float(info.length)
    except Exception:
        pass
    if not title:
        title = os.path.splitext(os.path.basename(path))[0]
    return title, artist, album, duration


def _iter_files(root: str, recursive: bool):
    if os.path.isfile(root):
        yield root
        return
    if recursive:
        for dirpath, _dirs, files in os.walk(root):
            for name in sorted(files):
                yield os.path.join(dirpath, name)
    else:
        for name in sorted(os.listdir(root)):
            p = os.path.join(root, name)
            if os.path.isfile(p):
                yield p


def scan(path, *, analyze=False, reanalyze=False, recursive=True, dry_run=False,
         exts=DEFAULT_EXTS, session_factory=None):
    """Scan `path`, registering new audio files. Returns a counts dict."""
    exts = tuple(e.lower() for e in exts)
    owns_engine = session_factory is None
    engine = create_database_engine() if owns_engine else None
    if session_factory is None:
        session_factory = create_session_factory(engine)

    counts = {"scanned": 0, "added": 0, "relinked": 0, "present": 0,
              "unsupported": 0, "errored": 0}
    touched_ids: list[int] = []
    session = session_factory()
    try:
        for fpath in _iter_files(path, recursive):
            if os.path.splitext(fpath)[1].lower() not in exts:
                counts["unsupported"] += 1
                continue
            counts["scanned"] += 1
            abspath = os.path.realpath(fpath)
            try:
                digest = content_hash(abspath)
                existing = session.query(Track).filter(Track.content_hash == digest).first()
                if existing is not None:
                    if existing.file_path == abspath:
                        counts["present"] += 1
                    else:
                        counts["relinked"] += 1
                        print(f"  relinked: {os.path.basename(abspath)}")
                        if not dry_run:
                            existing.file_path = abspath
                            session.commit()
                    # Every scanned track is a candidate for --analyze, so a
                    # register-then-analyze workflow picks up already-registered
                    # tracks. The analyze pass filters to those lacking an
                    # Analysis (or all of them under --reanalyze).
                    touched_ids.append(existing.id)
                    continue
                # new content
                if dry_run:
                    counts["added"] += 1
                    print(f"  would add: {abspath}")
                    continue
                title, artist, album, duration = read_metadata(abspath)
                track = Track(title=title, artist=artist, album=album, file_path=abspath,
                              artwork_path=extract_artwork(abspath), duration=duration,
                              content_hash=digest)
                session.add(track)
                session.commit()
                session.refresh(track)
                counts["added"] += 1
                touched_ids.append(track.id)
            except Exception as e:
                session.rollback()
                counts["errored"] += 1
                print(f"  ERROR {os.path.basename(fpath)}: {e}")
    finally:
        session.close()

    _print_summary(counts, analyze)
    if analyze and not dry_run:
        _analyze_pass(session_factory, touched_ids, reanalyze)
    if owns_engine and engine is not None:
        engine.dispose()
    return counts


def _print_summary(counts, analyze):
    print(f"\nScanned {counts['scanned']} audio files: added {counts['added']}, "
          f"relinked {counts['relinked']}, already present {counts['present']}, "
          f"unsupported {counts['unsupported']}, errored {counts['errored']}.")
    if not analyze:
        print("Registered only. Re-run with --analyze to compute BPM/key/energy/etc.")


def _analyze_pass(session_factory, touched_ids, reanalyze):
    session = session_factory()
    try:
        ids = list(dict.fromkeys(touched_ids))
        if not reanalyze:
            ids = [tid for tid in ids
                   if session.query(Analysis).filter(Analysis.track_id == tid).first() is None]
        targets = {t.id: t.file_path
                   for t in session.query(Track).filter(Track.id.in_(ids)).all()} if ids else {}
    finally:
        session.close()

    n = len(targets)
    if n == 0:
        print("Nothing to analyze.")
        return
    print(f"Analyzing {n} tracks (~{n * _SECS_PER_TRACK / 60:.0f} min "
          f"at ~{_SECS_PER_TRACK:.1f}s/track)...")
    done = failed = 0
    for i, (tid, fpath) in enumerate(targets.items(), 1):
        try:
            run_analysis(tid, fpath, session_factory)
            done += 1
        except Exception as e:
            failed += 1
            print(f"  analysis failed for track {tid}: {e}")
        if i % 25 == 0 or i == n:
            print(f"  {i}/{n}")
    print(f"Analyzed {done} tracks ({failed} failed).")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("path", help="folder (or single file) to scan")
    p.add_argument("--analyze", action="store_true", help="also run DSP analysis (CPU-bound)")
    p.add_argument("--reanalyze", action="store_true",
                   help="re-run analysis on tracks that already have one")
    p.add_argument("--no-recursive", dest="recursive", action="store_false",
                   help="do not descend into subfolders")
    p.add_argument("--dry-run", action="store_true", help="report what would happen; write nothing")
    p.add_argument("--ext", default=None,
                   help="comma-separated extension whitelist (default: %s)" % ",".join(DEFAULT_EXTS))
    args = p.parse_args(argv)
    if not os.path.exists(args.path):
        p.error(f"path not found: {args.path}")
    exts = (tuple(e if e.startswith(".") else "." + e for e in args.ext.split(","))
            if args.ext else DEFAULT_EXTS)
    scan(args.path, analyze=args.analyze, reanalyze=args.reanalyze,
         recursive=args.recursive, dry_run=args.dry_run, exts=exts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

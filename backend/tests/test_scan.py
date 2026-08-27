"""Folder scanner: registration, dedup/idempotency, relink-on-move, extension
filtering, and the analyze opt-in.

The suite shares one session-scoped DB, so each test uses distinct audio content
(so content hashes do not collide across tests) and scopes its assertions to its
own tmp_path.
"""
import os

import numpy as np
import soundfile as sf

from backend import scan as scanmod
from backend.models.models import Analysis, Track


def _wav(path, freq, sr=22050, dur=2.0):
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)
    sf.write(str(path), (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float32), sr)
    return str(path)


def _under(db, tmp_path):
    prefix = os.path.realpath(str(tmp_path))
    return db.query(Track).filter(Track.file_path.like(f"{prefix}%"))


def test_scan_registers_new_and_skips_unsupported(client, db, tmp_path):
    _wav(tmp_path / "a.wav", 101.0)
    _wav(tmp_path / "b.wav", 103.0)
    (tmp_path / "notes.txt").write_text("not audio")

    counts = scanmod.scan(str(tmp_path), session_factory=client.app.state.sessionmaker)

    assert counts["added"] == 2
    assert counts["unsupported"] == 1
    assert counts["errored"] == 0
    db.expire_all()
    tracks = _under(db, tmp_path).all()
    assert len(tracks) == 2
    # register-only by default: no analysis rows
    assert all(db.query(Analysis).filter(Analysis.track_id == t.id).first() is None for t in tracks)
    # content_hash set; absolute in-place path stored (not copied into uploads/)
    assert all(t.content_hash for t in tracks)
    assert all(os.path.isabs(t.file_path) and "uploads" not in t.file_path for t in tracks)


def test_scan_is_idempotent(client, db, tmp_path):
    _wav(tmp_path / "a.wav", 107.0)
    _wav(tmp_path / "b.wav", 109.0)
    factory = client.app.state.sessionmaker

    first = scanmod.scan(str(tmp_path), session_factory=factory)
    second = scanmod.scan(str(tmp_path), session_factory=factory)

    assert first["added"] == 2
    assert second["added"] == 0
    assert second["present"] == 2
    db.expire_all()
    assert _under(db, tmp_path).count() == 2


def test_scan_relinks_moved_file_without_duplicating(client, db, tmp_path):
    src = _wav(tmp_path / "orig.wav", 113.0)
    factory = client.app.state.sessionmaker
    scanmod.scan(str(tmp_path), session_factory=factory)
    db.expire_all()
    track = db.query(Track).filter(Track.file_path == os.path.realpath(src)).first()
    assert track is not None

    os.rename(src, tmp_path / "renamed.wav")  # same content, new path

    counts = scanmod.scan(str(tmp_path), session_factory=factory)
    assert counts["relinked"] == 1
    assert counts["added"] == 0
    db.expire_all()
    assert _under(db, tmp_path).count() == 1  # still one track, not duplicated
    assert db.query(Track).filter(Track.id == track.id).first().file_path == \
        os.path.realpath(str(tmp_path / "renamed.wav"))


def test_scan_analyze_flag_creates_analysis(client, db, tmp_path):
    _wav(tmp_path / "a.wav", 127.0, dur=3.0)
    scanmod.scan(str(tmp_path), analyze=True, session_factory=client.app.state.sessionmaker)
    db.expire_all()
    track = _under(db, tmp_path).first()
    assert track is not None
    assert db.query(Analysis).filter(Analysis.track_id == track.id).first() is not None


def test_scan_register_then_analyze_picks_up_existing(client, db, tmp_path):
    # The documented flow: register first, then re-run with --analyze. The
    # already-registered track must get analyzed, not skipped as "present".
    _wav(tmp_path / "a.wav", 131.0, dur=3.0)
    factory = client.app.state.sessionmaker
    scanmod.scan(str(tmp_path), session_factory=factory)  # register only
    db.expire_all()
    track = _under(db, tmp_path).first()
    assert db.query(Analysis).filter(Analysis.track_id == track.id).first() is None

    scanmod.scan(str(tmp_path), analyze=True, session_factory=factory)  # now analyze
    db.expire_all()
    assert db.query(Analysis).filter(Analysis.track_id == track.id).first() is not None

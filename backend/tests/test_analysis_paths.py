# Extra coverage for backend/api/analysis.py: the background analysis task
# (run_analysis) and the spectrum endpoint, plus analyze_track's guard paths.
# All audio is real audio generated on disk - the DSP is never mocked.

import numpy as np
import soundfile as sf

from backend.api.analysis import run_analysis
from backend.audio.analyzer import KEYS
from backend.models.models import Analysis, Track
from conftest import TestingSessionLocal


def _write_tone(path, freq=220.0, sr=22050, dur=4.0):
    """A few seconds of a real tone (fundamental + harmonic) written to WAV."""
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)
    y = 0.6 * np.sin(2 * np.pi * freq * t) + 0.2 * np.sin(2 * np.pi * 2 * freq * t)
    sf.write(str(path), y.astype(np.float32), sr)


def _make_track(db, file_path):
    track = Track(title="Real Song", file_path=str(file_path))
    db.add(track)
    db.commit()
    db.refresh(track)
    return track


def test_run_analysis_writes_bounded_descriptors(db, tmp_path):
    wav = tmp_path / "song.wav"
    _write_tone(wav)
    track = _make_track(db, wav)

    # Hand run_analysis the test session factory so the Track and the Analysis
    # it writes live in the same database.
    run_analysis(track.id, str(wav), TestingSessionLocal)  # real DSP over the audio

    verify = TestingSessionLocal()
    written = verify.query(Analysis).filter(Analysis.track_id == track.id).first()
    assert written is not None
    assert written.bpm is not None
    assert written.key in KEYS
    assert written.scale in ("major", "minor")
    assert 0.0 <= written.energy <= 1.0
    assert 0.0 <= written.danceability <= 1.0
    verify.close()


def test_run_analysis_updates_existing_row(db, tmp_path):
    # A second run over the same track must update the existing Analysis,
    # not create a duplicate (covers run_analysis' "existing" branch).
    wav = tmp_path / "song2.wav"
    _write_tone(wav, freq=330.0)
    track = _make_track(db, wav)

    run_analysis(track.id, str(wav), TestingSessionLocal)
    run_analysis(track.id, str(wav), TestingSessionLocal)

    verify = TestingSessionLocal()
    rows = verify.query(Analysis).filter(Analysis.track_id == track.id).all()
    assert len(rows) == 1
    verify.close()


def test_spectrum_endpoint_returns_bands(client, db, tmp_path):
    wav = tmp_path / "spectrum.wav"
    _write_tone(wav, freq=440.0)
    track = _make_track(db, wav)

    r = client.get(f"/api/analysis/{track.id}/spectrum")
    assert r.status_code == 200
    body = r.json()
    assert body["track_id"] == track.id
    bands = body["bands"]
    assert isinstance(bands, list) and len(bands) == 64
    assert all(0.0 <= b <= 1.0 for b in bands)


def test_analyze_track_404_when_track_missing(client):
    r = client.post("/api/analysis/analyze/999999")
    assert r.status_code == 404
    assert r.json()["detail"] == "Track not found"


def test_analyze_track_404_when_file_missing(client, db):
    # Track row exists but points at a file that isn't on disk.
    track = _make_track(db, "uploads/does_not_exist.mp3")
    r = client.post(f"/api/analysis/analyze/{track.id}")
    assert r.status_code == 404
    assert r.json()["detail"] == "Audio file not found"


def test_get_analysis_404_when_absent(client):
    r = client.get("/api/analysis/999999")
    assert r.status_code == 404


def test_recommendations_404_when_no_analysis(client):
    r = client.get("/api/analysis/999999/recommendations")
    assert r.status_code == 404

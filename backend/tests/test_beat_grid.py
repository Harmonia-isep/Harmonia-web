"""Beat-grid persistence: JSON round-trip, delete-cascade, the run_analysis
pipeline, and the GET /beats endpoint."""

from backend.api.analysis import run_analysis
from backend.audio.analyzer import analyze_audio
from backend.models.models import Analysis, Track


def test_beat_grid_json_round_trips(db):
    # A list of floats survives the generic JSON column unchanged.
    track = Track(title="Grid", file_path="uploads/grid.mp3")
    db.add(track)
    db.commit()
    db.refresh(track)

    grid = [0.5, 1.0, 1.5, 2.0]
    db.add(Analysis(track_id=track.id, bpm=120, key="A", scale="minor", beat_grid=grid))
    db.commit()
    db.expire_all()

    stored = db.query(Analysis).filter(Analysis.track_id == track.id).first()
    assert stored.beat_grid == grid


def test_beat_grid_cascades_when_track_deleted(db):
    # Deleting the track removes the analysis row, and the beat grid with it.
    track = Track(title="Cascade grid", file_path="uploads/cg.mp3")
    db.add(track)
    db.commit()
    db.refresh(track)

    analysis = Analysis(track_id=track.id, bpm=128, key="C", scale="major",
                        beat_grid=[0.4, 0.9, 1.4])
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    analysis_id = analysis.id

    db.delete(track)
    db.commit()
    db.expire_all()
    assert db.query(Analysis).filter(Analysis.id == analysis_id).first() is None


def test_analyze_audio_returns_beats(make_tone):
    out = analyze_audio(make_tone(freq=440.0))
    assert "beats" in out
    assert isinstance(out["beats"], list)
    assert all(isinstance(t, (int, float)) for t in out["beats"])


def test_run_analysis_persists_beat_grid(client, db, make_tone):
    # The full pipeline: run_analysis stores the grid via the explicit mapping.
    track = Track(title="Pipeline", file_path=make_tone(freq=261.63))
    db.add(track)
    db.commit()
    db.refresh(track)
    track_id = track.id

    run_analysis(track_id, track.file_path, client.app.state.sessionmaker)

    db.expire_all()
    stored = db.query(Analysis).filter(Analysis.track_id == track_id).first()
    assert stored is not None
    assert isinstance(stored.beat_grid, list)
    assert len(stored.beat_grid) > 0
    assert all(isinstance(t, (int, float)) for t in stored.beat_grid)


def test_get_beats_endpoint(client, db):
    track = Track(title="Endpoint", file_path="uploads/ep.mp3")
    db.add(track)
    db.commit()
    db.refresh(track)

    grid = [0.5, 1.0, 1.5]
    db.add(Analysis(track_id=track.id, bpm=120, key="A", scale="minor", beat_grid=grid))
    db.commit()

    r = client.get(f"/api/analysis/{track.id}/beats")
    assert r.status_code == 200
    assert r.json() == {"track_id": track.id, "beats": grid}

    # 404 when the track has no analysis.
    track2 = Track(title="No analysis", file_path="uploads/na.mp3")
    db.add(track2)
    db.commit()
    db.refresh(track2)
    assert client.get(f"/api/analysis/{track2.id}/beats").status_code == 404


def test_analyze_audio_returns_mix_points(make_tone):
    out = analyze_audio(make_tone(freq=440.0))
    assert isinstance(out["intro_end"], float)
    assert isinstance(out["outro_start"], float)
    assert 0.0 <= out["intro_end"] <= out["outro_start"]


def test_run_analysis_persists_mix_points(client, db, make_tone):
    track = Track(title="Mix points", file_path=make_tone(freq=329.63))
    db.add(track)
    db.commit()
    db.refresh(track)
    track_id = track.id

    run_analysis(track_id, track.file_path, client.app.state.sessionmaker)

    db.expire_all()
    stored = db.query(Analysis).filter(Analysis.track_id == track_id).first()
    assert isinstance(stored.intro_end, float)
    assert isinstance(stored.outro_start, float)
    assert stored.intro_end <= stored.outro_start

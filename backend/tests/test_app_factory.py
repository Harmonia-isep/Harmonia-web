# Tests for the application/config factory (Phase 2 chunk 1): the SQLite default,
# foreign-key enforcement, and that the app builds and serves without any env.

from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.main import create_app
from backend.models.database import DEFAULT_DATABASE_URL, create_database_engine


def test_default_database_url_is_local_sqlite():
    assert DEFAULT_DATABASE_URL == "sqlite:///./harmonia.db"


def test_sqlite_foreign_keys_enabled():
    # SQLite silently ignores foreign keys unless PRAGMA foreign_keys=ON is set,
    # once per connection. That silence is exactly what let the hand-rolled
    # cascade deletes pass unnoticed, so guard it against regression.
    engine = create_database_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_app_serves_docs_without_frontend_build(tmp_path):
    # CI has no npm build. The app must still construct and serve /docs (and the
    # API-only JSON health at /), not raise at startup on a missing build directory.
    missing = tmp_path / "no_build"
    app = create_app(database_url="sqlite:///:memory:", frontend_dir=str(missing))
    with TestClient(app) as client:
        assert client.get("/docs").status_code == 200
        assert client.get("/").json() == {"message": "Harmonia API is running"}


def test_frontend_served_and_catch_all_scoped(tmp_path):
    # With a build present the SPA is served at / and at client-side routes, but the
    # catch-all must not shadow the API or the docs endpoints.
    build = tmp_path / "build"
    (build / "static").mkdir(parents=True)
    (build / "index.html").write_text("<!doctype html><title>Harmonia SPA</title>")
    app = create_app(database_url="sqlite:///:memory:", frontend_dir=str(build))
    with TestClient(app) as client:
        assert "Harmonia SPA" in client.get("/").text          # SPA at root
        assert "Harmonia SPA" in client.get("/library").text   # client route resolves
        assert client.get("/docs").status_code == 200          # docs not shadowed
        r = client.get("/api/does-not-exist")
        assert r.status_code == 404                            # api not shadowed
        assert "Harmonia SPA" not in r.text


def test_deleting_track_cascades_to_children_at_db_level(db):
    from backend.models.models import Analysis, Playlist, PlaylistTrack, Track

    track = Track(title="Cascade", file_path="uploads/cascade.mp3")
    db.add(track)
    db.commit()
    db.refresh(track)

    analysis = Analysis(track_id=track.id, bpm=120, key="A", scale="minor")
    playlist = Playlist(name="Cascade PL", share_token="cascadetok")
    db.add_all([analysis, playlist])
    db.commit()
    db.refresh(analysis)
    db.refresh(playlist)
    entry = PlaylistTrack(playlist_id=playlist.id, track_id=track.id, position=0)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    analysis_id, entry_id = analysis.id, entry.id

    # Delete only the track through the ORM, with no manual child cleanup. The
    # database's ON DELETE CASCADE must remove the analysis row and the playlist
    # entry. This fails (leftover rows, or an IntegrityError) if ondelete is
    # dropped, which the old manual-loop tests could not detect. Assert by primary
    # key so orphaned-but-nulled children would also fail it.
    db.delete(track)
    db.commit()

    db.expire_all()
    assert db.query(Analysis).filter(Analysis.id == analysis_id).first() is None
    assert db.query(PlaylistTrack).filter(PlaylistTrack.id == entry_id).first() is None

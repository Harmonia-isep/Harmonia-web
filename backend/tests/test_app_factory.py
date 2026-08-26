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


def test_app_builds_and_serves_without_env():
    # No DATABASE_URL and no .env required: the factory defaults to SQLite and the
    # app comes up. This is the fresh-clone path that used to fail at import.
    app = create_app(database_url="sqlite:///:memory:", cors_origins=["http://testserver"])
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert client.get("/docs").status_code == 200


def test_deleting_track_cascades_to_children_at_db_level(db):
    from backend.models.models import Analysis, Playlist, PlaylistTrack, Track, User

    user = User(username="cascade_user", password_hash="x")
    db.add(user)
    db.commit()
    db.refresh(user)

    track = Track(title="Cascade", file_path="uploads/cascade.mp3", user_id=user.id)
    db.add(track)
    db.commit()
    db.refresh(track)

    analysis = Analysis(track_id=track.id, bpm=120, key="A", scale="minor")
    playlist = Playlist(name="Cascade PL", user_id=user.id, share_token="cascadetok")
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

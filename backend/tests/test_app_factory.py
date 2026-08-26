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

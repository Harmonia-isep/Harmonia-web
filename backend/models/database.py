import os

from fastapi import Request
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

# Local-first default: a SQLite file in the working directory. Override with the
# DATABASE_URL environment variable (e.g. a Postgres URL) when needed.
DEFAULT_DATABASE_URL = "sqlite:///./harmonia.db"


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def resolve_database_url(database_url: str | None = None) -> str:
    """Resolve the database URL the one way everywhere: argument, then the
    DATABASE_URL environment variable, then the local SQLite default. Alembic's
    env.py uses this too, so the app and migrations share a single config path."""
    return database_url or os.getenv("DATABASE_URL") or DEFAULT_DATABASE_URL


def create_database_engine(database_url: str | None = None, **engine_kwargs) -> Engine:
    """Build a SQLAlchemy engine, resolving configuration at call time.

    The URL comes from the argument, then DATABASE_URL, then a local SQLite file.
    SQLite gets check_same_thread=False (so the request thread pool can share the
    connection) and per-connection foreign-key enforcement; Postgres gets neither.
    """
    url = resolve_database_url(database_url)
    connect_args = {"check_same_thread": False} if _is_sqlite(url) else {}
    engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True, **engine_kwargs)
    if _is_sqlite(url):
        _enable_sqlite_foreign_keys(engine)
    return engine


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    """SQLite ignores foreign keys unless asked, once per connection. Without this
    ON DELETE and FK constraints are silently skipped."""

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def create_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db(request: Request):
    """FastAPI dependency: yield a session from the app's session factory, which
    create_app stores on app.state. Nothing is bound at import time."""
    session_factory = request.app.state.sessionmaker
    db = session_factory()
    try:
        yield db
    finally:
        db.close()

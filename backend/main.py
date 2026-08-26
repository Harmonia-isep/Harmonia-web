import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.engine import Engine

from backend.api import analysis, playlists, tracks, users
from backend.models.database import create_database_engine, create_session_factory
from backend.models.models import Base

DEFAULT_CORS_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"


def _resolve_cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS)
    return [o.strip() for o in raw.split(",") if o.strip()]


def create_app(
    database_url: str | None = None,
    *,
    engine: Engine | None = None,
    create_tables: bool = True,
    cors_origins: list[str] | None = None,
) -> FastAPI:
    """Build the Harmonia FastAPI application.

    All configuration (database URL, CORS origins) is read here, at call time,
    not at import time, so a fresh clone with no .env can still import and run.
    Pass ``engine`` to reuse a prepared engine (the test suite does this).
    """
    load_dotenv()  # load a local .env if present; a no-op on a fresh clone

    if engine is None:
        engine = create_database_engine(database_url)
    session_factory = create_session_factory(engine)

    if create_tables:
        Base.metadata.create_all(bind=engine)
    os.makedirs("uploads", exist_ok=True)

    app = FastAPI(title="Harmonia API", version="1.0.0")
    app.state.engine = engine
    app.state.sessionmaker = session_factory

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins if cors_origins is not None else _resolve_cors_origins(),
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )

    app.include_router(users.router, prefix="/api/users", tags=["users"])
    app.include_router(tracks.router, prefix="/api/tracks", tags=["tracks"])
    app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])
    app.include_router(playlists.router, prefix="/api/playlists", tags=["playlists"])

    @app.get("/")
    def root():
        return {"message": "Harmonia API is running"}

    return app

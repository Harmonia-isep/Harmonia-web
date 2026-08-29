import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.engine import Engine

from backend.api import analysis, playlists, tracks
from backend.models.database import create_database_engine, create_session_factory
from backend.storage import resolve_upload_dir

logger = logging.getLogger("harmonia")

DEFAULT_CORS_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"

# The Create React App build output, resolved relative to the repo so it works
# regardless of the process working directory.
DEFAULT_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend" / "build"

# Paths the SPA catch-all must never serve index.html for.
_RESERVED_PREFIXES = ("api/",)
_RESERVED_PATHS = {"docs", "redoc", "openapi.json"}


def _resolve_cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS)
    return [o.strip() for o in raw.split(",") if o.strip()]


def create_app(
    database_url: str | None = None,
    *,
    engine: Engine | None = None,
    cors_origins: list[str] | None = None,
    frontend_dir: str | os.PathLike | None = None,
    upload_dir: str | os.PathLike | None = None,
) -> FastAPI:
    """Build the Harmonia FastAPI application.

    All configuration (database URL, CORS origins, frontend build directory) is read
    here, at call time, not at import time, so a fresh clone with no .env can still
    import and run. The database schema is owned by Alembic (run ``alembic upgrade
    head``). Pass ``engine`` to reuse a prepared engine (the test suite does this).

    If the frontend build directory exists it is served (single-process UI); if not,
    the app serves the API only, so tests and CI (which have no npm build) still work.
    """
    load_dotenv()  # load a local .env if present; a no-op on a fresh clone

    if engine is None:
        engine = create_database_engine(database_url)
    session_factory = create_session_factory(engine)

    app = FastAPI(title="Harmonia API", version="1.0.0")
    app.state.engine = engine
    app.state.sessionmaker = session_factory

    # Uploaded audio and the artwork extracted from it. Resolved here, at call
    # time, so a test or a second instance can be pointed at a temp directory
    # instead of writing into the developer's real uploads folder.
    upload_path = resolve_upload_dir(upload_dir)
    upload_path.mkdir(parents=True, exist_ok=True)
    app.state.upload_dir = upload_path

    # CORS is only needed for the split-origin dev flow (CRA on :3000 calling the
    # backend on :8000). The single-process build is same-origin and needs none.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins if cors_origins is not None else _resolve_cors_origins(),
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )

    app.include_router(tracks.router, prefix="/api/tracks", tags=["tracks"])
    app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])
    app.include_router(playlists.router, prefix="/api/playlists", tags=["playlists"])

    # Registered LAST so it can never shadow the API routers or FastAPI's /docs,
    # /openapi.json and /redoc, which are all added earlier.
    _serve_frontend(app, Path(frontend_dir) if frontend_dir is not None else DEFAULT_FRONTEND_DIR)

    return app


def _serve_frontend(app: FastAPI, frontend_dir: Path) -> None:
    index_file = frontend_dir / "index.html"
    if not index_file.is_file():
        logger.warning(
            "Frontend build not found at %s; serving the API only. Run `npm run build` "
            "in frontend/ to enable the single-process UI.",
            frontend_dir,
        )

        @app.get("/")
        def root():
            return {"message": "Harmonia API is running"}

        return

    static_dir = frontend_dir / "static"
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    root_dir = frontend_dir.resolve()

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        # Never shadow the API or the docs endpoints: let them 404 as themselves.
        if full_path.startswith(_RESERVED_PREFIXES) or full_path in _RESERVED_PATHS:
            raise HTTPException(status_code=404)
        # Serve a real build file if the path points at one (favicon, manifest, ...),
        # guarding against path traversal; otherwise fall back to index.html so client
        # side routes resolve on refresh.
        if full_path:
            candidate = (frontend_dir / full_path).resolve()
            if candidate.is_file() and candidate.is_relative_to(root_dir):
                return FileResponse(candidate)
        return FileResponse(index_file)

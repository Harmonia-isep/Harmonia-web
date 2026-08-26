# Shared pytest fixtures for the Harmonia backend test suite.
#
# The app is built by create_app() against a temporary SQLite file. StaticPool keeps
# a single shared connection so the FastAPI TestClient's worker thread and the fixtures
# see the same rows. The schema is created by running the real Alembic migration chain,
# not Base.metadata.create_all, so a broken migration fails the suite here rather than
# in production. All configuration flows through the one config path (DATABASE_URL).

import os
import tempfile

import numpy as np
import pytest
import soundfile as sf
from alembic.config import Config
from sqlalchemy.pool import StaticPool

from alembic import command
from backend.main import create_app
from backend.models.database import create_database_engine, create_session_factory

# Point both the app engine and Alembic at one temp SQLite file via DATABASE_URL.
_db_fd, _DB_PATH = tempfile.mkstemp(suffix=".db")
os.close(_db_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"

test_engine = create_database_engine(poolclass=StaticPool)
TestingSessionLocal = create_session_factory(test_engine)

app = create_app(
    engine=test_engine,
    cors_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8098",
    ],
)

_ALEMBIC_INI = os.path.join(os.path.dirname(__file__), "alembic.ini")


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    # Run the real migration chain against the temp database (Alembic resolves the
    # same DATABASE_URL through env.py), so tests exercise the schema Alembic ships.
    command.upgrade(Config(_ALEMBIC_INI), "head")
    yield
    test_engine.dispose()
    os.remove(_DB_PATH)


@pytest.fixture
def db():
    """Direct DB session for seeding rows the endpoints will read back."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c


@pytest.fixture
def make_tone(tmp_path):
    """Factory that writes a short musical tone to a WAV file and returns its path.

    A fundamental plus two harmonics makes the chroma (and therefore the
    detected key) robust, while staying tiny, so no large audio fixtures needed.
    """
    def _make(freq=440.0, sr=22050, dur=5.0):
        t = np.linspace(0, dur, int(sr * dur), endpoint=False)
        y = (0.6 * np.sin(2 * np.pi * freq * t)
             + 0.2 * np.sin(2 * np.pi * 2 * freq * t)
             + 0.1 * np.sin(2 * np.pi * 3 * freq * t))
        path = tmp_path / f"tone_{int(freq)}.wav"
        sf.write(str(path), y.astype(np.float32), sr)
        return str(path)
    return _make

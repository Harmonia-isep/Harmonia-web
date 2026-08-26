# Shared pytest fixtures for the Harmonia backend test suite.
#
# The backend normally talks to PostgreSQL (Neon). For tests we point it at an
# in-memory SQLite database instead: the models use only generic SQLAlchemy
# column types, so they map cleanly onto SQLite. A single shared connection
# (StaticPool) means the FastAPI TestClient's worker thread sees the same rows
# the fixtures insert.

import os

# Must be set before any backend module is imported, because
# backend/models/database.py reads DATABASE_URL at import time.
os.environ.setdefault("DATABASE_URL", "sqlite://")

# The CORS middleware reads CORS_ORIGINS when backend.main is imported (below),
# so it must be set before that import - a fixture would run too late. Include
# the e2e browser origin: test_e2e.py serves the built frontend on
# 127.0.0.1:8098, and the headless browser's cross-origin API calls need it.
os.environ.setdefault(
    "CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,http://127.0.0.1:8098",
)

import numpy as np
import pytest
import soundfile as sf
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import app
from backend.models.database import get_db
from backend.models.models import Base

# One in-memory SQLite engine shared across the whole test session.
test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Route every request's DB dependency to the test database.
app.dependency_overrides[get_db] = _override_get_db


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
    detected key) robust, while staying tiny — no large audio fixtures needed.
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

# Shared pytest fixtures for the Harmonia backend test suite.
#
# The app is built by create_app() against an in-memory SQLite database. A single
# shared connection (StaticPool) means the FastAPI TestClient's worker thread sees
# the same rows the fixtures insert. All configuration is passed to the factory
# explicitly, so no environment variables need to be set before import.

import numpy as np
import pytest
import soundfile as sf
from sqlalchemy.pool import StaticPool

from backend.main import create_app
from backend.models.database import create_database_engine, create_session_factory
from backend.models.models import Base

# One in-memory SQLite engine shared across the whole test session. Built through
# the same factory helper as production, so it gets the foreign-key PRAGMA too.
test_engine = create_database_engine("sqlite://", poolclass=StaticPool)
TestingSessionLocal = create_session_factory(test_engine)

# The app reads its config from these explicit arguments. The CORS list includes
# the e2e browser origin (test_e2e.py serves the built frontend on
# 127.0.0.1:8098), which replaces the old CORS_ORIGINS env-var workaround.
app = create_app(
    engine=test_engine,
    create_tables=False,
    cors_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8098",
    ],
)


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


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

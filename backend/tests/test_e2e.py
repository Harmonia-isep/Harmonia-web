# End-to-end tests: a real headless Chromium (Playwright) driving the built React UI
# served by the FastAPI app itself.
#
# One uvicorn process serves both the built frontend (via StaticFiles + the SPA
# catch-all) and the API, on a single origin, sharing conftest's SQLite test database.
# Same-origin means no CORS is involved. The React build is produced once in the
# fixture if frontend/build is missing.

import os
import socket
import subprocess
import threading
import time

import pytest

# This drives a real browser, so it is excluded from the default CI run with
# -m "not e2e" (CI has no browser). Run locally with the e2e extra installed.
# The login e2e was removed with auth in Phase 3. Phase 7 replaced the login gate
# with a front door: "/" is the landing page and "/library" is the app.
pytestmark = pytest.mark.e2e

PORT = 8099
BASE = f"http://127.0.0.1:{PORT}"

_HERE = os.path.dirname(os.path.abspath(__file__))
_FRONTEND = os.path.abspath(os.path.join(_HERE, "..", "..", "frontend"))
_BUILD_DIR = os.path.join(_FRONTEND, "build")


def _wait_for_port(port, timeout=30.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.2)
    return False


# Everything Vite reads as build input. If any is newer than the built
# index.html, the bundle on disk is stale and must be rebuilt.
_BUILD_INPUTS = (
    "src",
    "public",
    "index.html",
    "vite.config.js",
    "package.json",
    "package-lock.json",
)
_STAMP = os.path.join(_BUILD_DIR, ".e2e-build-stamp")

# Build the bundle same-origin (relative URLs) rather than baking in an absolute
# host:port. Every e2e server serves the API and the UI together, so a relative
# base is correct, and it lets a second server on a different port reuse this
# one build instead of needing its own.
_E2E_API_BASE = ""


def _newest_input_mtime():
    """Newest mtime across every Vite build input."""
    newest = 0.0
    for rel in _BUILD_INPUTS:
        path = os.path.join(_FRONTEND, rel)
        if os.path.isfile(path):
            newest = max(newest, os.path.getmtime(path))
            continue
        for root, _dirs, files in os.walk(path):
            newest = max(newest, os.path.getmtime(root))
            for name in files:
                newest = max(newest, os.path.getmtime(os.path.join(root, name)))
    return newest


def _ensure_build():
    """Build the React app unless the bundle on disk is already current.

    Current means the output exists, is newer than every build input, and was
    built with the same VITE_API_URL. Returning early on the mere existence of
    build/ would silently test a stale bundle, letting a frontend change pass
    e2e without ever having been compiled.
    """
    built = os.path.join(_BUILD_DIR, "index.html")
    stamp = "VITE_API_URL=" + _E2E_API_BASE
    if os.path.isfile(built) and os.path.isfile(_STAMP):
        with open(_STAMP, encoding="utf-8") as fh:
            same_env = fh.read() == stamp
        if same_env and os.path.getmtime(built) >= _newest_input_mtime():
            return
    # Vite exposes only VITE_-prefixed vars to client code. The CRA-era
    # REACT_APP_API_URL was silently ignored after the Vite migration.
    env = dict(os.environ, CI="false", VITE_API_URL=_E2E_API_BASE)
    subprocess.run(
        ["npm", "run", "build"],
        cwd=_FRONTEND, env=env, check=True,
        capture_output=True, text=True, timeout=600,
    )
    # Written after the build: vite empties outDir, which would remove it.
    with open(_STAMP, "w", encoding="utf-8") as fh:
        fh.write(stamp)


@pytest.fixture(scope="session")
def server():
    import uvicorn

    from backend.main import create_app
    from conftest import test_engine

    _ensure_build()
    if not os.path.isfile(os.path.join(_BUILD_DIR, "index.html")):
        pytest.fail(f"React build missing at {_BUILD_DIR}; `npm run build` did not produce it.")

    # One app serving both the frontend and the API, on conftest's test database.
    app = create_app(engine=test_engine, frontend_dir=_BUILD_DIR)
    config = uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning")
    uv = uvicorn.Server(config)
    uv.install_signal_handlers = lambda: None  # required off the main thread
    thread = threading.Thread(target=uv.run, daemon=True)
    thread.start()

    assert _wait_for_port(PORT), "uvicorn did not start"

    yield BASE

    uv.should_exit = True


@pytest.fixture(scope="session")
def browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.fixture
def page(browser):
    context = browser.new_context()
    pg = context.new_page()
    yield pg
    context.close()


def test_landing_renders_and_opens_the_library(server, page):
    """The front door renders and its single entry action routes to /library."""
    page.goto(server, wait_until="networkidle")
    assert "Harmonia" in page.content()

    open_btn = page.locator("button.hero-btn-primary")
    open_btn.wait_for(state="visible", timeout=15000)
    assert "Open Library" in open_btn.inner_text()

    # Clicking it is a client-side route change, not a full page load.
    open_btn.click()
    page.wait_for_url("**/library", timeout=15000)

    # The library view replaced the landing page: its nav is present and the
    # landing hero is gone.
    page.locator("nav.nav-center button", has_text="Compare").wait_for(
        state="visible", timeout=15000
    )
    assert page.locator("button.hero-btn-primary").count() == 0


def test_library_deep_link_is_served_by_the_spa_catch_all(server, page):
    """Loading /library directly must serve index.html rather than 404.

    The SPA catch-all landed in Phase 2 with no real client-side routes to
    exercise it. /library is the first one, so this is the first test that
    actually proves a deep link resolves instead of falling through.
    """
    response = page.goto(f"{server}/library", wait_until="networkidle")
    assert response is not None, "no response for /library"
    assert response.status == 200, f"/library returned {response.status}, expected 200"

    # It really is the SPA, booted straight into the library view.
    page.locator("nav.nav-center button", has_text="Compare").wait_for(
        state="visible", timeout=15000
    )
    assert page.locator("button.hero-btn-primary").count() == 0


# ---------------------------------------------------------------------------
# Smoke test: the release bar from the Phase 7 definition of done. A file on
# disk becomes a harmonic recommendation on screen, driven through the UI. The
# recommendation ALGORITHM is already covered at the API level with seeded rows
# (test_integration.py, acceptance US15); what is covered here is that a person
# can actually get there.
# ---------------------------------------------------------------------------

SMOKE_PORT = 8098
SMOKE_BASE = f"http://127.0.0.1:{SMOKE_PORT}"

# The two tones are chosen by measurement, not guesswork. Running the analyzer
# over C4..C5 (the same recipe as conftest's make_tone: fundamental plus two
# harmonics, 5 s, 22050 Hz) produced:
#
#   NOTE  FREQ     BPM  KEY  SCALE  CAMELOT
#   C4    261.63    96  C    minor  5A
#   D4    293.66   117  D    minor  7A
#   E4    329.63   112  E    minor  9A   <- chosen
#   F4    349.23   144  F    minor  4A
#   G4    392.00   129  G    minor  6A
#   A4    440.00   112  A    minor  8A   <- chosen
#   B4    493.88   152  B    minor  10A
#   C5    523.25   129  C    minor  5A
#
# Only 3 of the 28 possible pairs are BOTH inside the +/-5 BPM window and
# Camelot compatible. E4 + A4 was picked because dBPM is 0 and 9A/8A are
# adjacent on the wheel, so a future librosa tempo shift of up to 5 BPM in
# either direction is absorbed without the recommendation going empty. The
# mapping was verified deterministic across three runs with fresh files.
#
# The BPM column is ARBITRARY, and that is expected rather than a defect. Pure
# tones have no percussive content, so the beat tracker is reading noise in the
# onset envelope; the numbers bear no relationship to the input frequency. This
# is not a bug in the analyzer and nobody should try to "fix" it on the
# strength of this table.
#
# If this test goes red on an empty recommendation list, re-run the tone
# measurement and pick a new pair. Do not widen the assertion.
SMOKE_TONES = {"SmokeE4": 329.63, "SmokeA4": 440.00}


def _write_tone(directory, name, freq, sr=22050, dur=5.0):
    """conftest's make_tone recipe, written where Playwright can upload it."""
    import numpy as np
    import soundfile as sf

    t = np.linspace(0, dur, int(sr * dur), endpoint=False)
    y = (0.6 * np.sin(2 * np.pi * freq * t)
         + 0.2 * np.sin(2 * np.pi * 2 * freq * t)
         + 0.1 * np.sin(2 * np.pi * 3 * freq * t))
    path = directory / f"{name}.wav"
    sf.write(str(path), y.astype(np.float32), sr)
    return str(path)


def _wait_for_analyses(base, track_ids, timeout=180.0):
    """Poll GET /api/analysis/{id}, the same endpoint the Library view polls.

    On timeout the message carries the LAST OBSERVED STATUS for every track,
    because this is the assertion most likely to go flaky and the status is the
    whole diagnosis.
    """
    import httpx

    deadline = time.time() + timeout
    last = {tid: "never polled" for tid in track_ids}
    while time.time() < deadline:
        pending = []
        for tid in track_ids:
            try:
                r = httpx.get(f"{base}/api/analysis/{tid}", timeout=10.0)
                last[tid] = f"HTTP {r.status_code}"
                if r.status_code != 200:
                    pending.append(tid)
            except Exception as exc:
                last[tid] = f"{type(exc).__name__}: {exc}"
                pending.append(tid)
        if not pending:
            return
        time.sleep(1.0)

    # pytest.fail rather than raise: the linter's TRY003 rule bans long literal
    # messages at a raise, and this message is the entire point of the helper.
    pytest.fail(
        f"analysis did not finish within {timeout:.0f}s. "
        f"Last observed status per track id: {last}. "
        "There is nothing better to poll: the analyze endpoint queues a "
        "BackgroundTask and returns immediately, with no job table to report "
        "progress. See the Phase 5 note under the plan's open questions."
    )


@pytest.fixture(scope="module")
def smoke_server(tmp_path_factory):
    """A second app with its OWN database and upload directory.

    Deliberately not the session-scoped `server` fixture. This test ingests and
    analyzes real audio, so sharing a database with the other e2e tests would
    make each outcome depend on whether the other ran first. The fix for
    cross-test pollution is isolation, not test ordering.
    """
    import uvicorn
    from alembic.config import Config

    from alembic import command
    from backend.main import create_app
    from conftest import _ALEMBIC_INI

    root = tmp_path_factory.mktemp("smoke")
    url = f"sqlite:///{root}/smoke.db"

    # Alembic's env.py resolves DATABASE_URL from the environment, the same path
    # create_app uses, so point it at this database for the upgrade only and put
    # the session-wide value back afterwards.
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    try:
        command.upgrade(Config(_ALEMBIC_INI), "head")
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous

    _ensure_build()
    app = create_app(
        database_url=url, frontend_dir=_BUILD_DIR, upload_dir=f"{root}/uploads"
    )
    config = uvicorn.Config(app, host="127.0.0.1", port=SMOKE_PORT, log_level="warning")
    uv = uvicorn.Server(config)
    uv.install_signal_handlers = lambda: None
    threading.Thread(target=uv.run, daemon=True).start()

    assert _wait_for_port(SMOKE_PORT), "smoke uvicorn did not start"
    yield SMOKE_BASE
    uv.should_exit = True


def test_smoke_ingest_analyze_recommend(smoke_server, page, tmp_path):
    """Ingest two tracks, analyze them, and see one recommend the other."""
    import httpx

    # Front door into the app.
    page.goto(smoke_server, wait_until="networkidle")
    page.locator("button.hero-btn-primary").click()
    page.wait_for_url("**/library", timeout=15000)

    # INGEST: both tones through the real upload UI, not a seeded row.
    files = [_write_tone(tmp_path, n, f) for n, f in SMOKE_TONES.items()]
    page.locator("nav.nav-center button", has_text="Upload").click()
    page.locator("input#fileInput").set_input_files(files)
    page.locator("button.upload-btn").click()

    summary = page.locator("p.summary-text")
    summary.wait_for(state="visible", timeout=60000)
    assert "2 of 2 succeeded" in summary.inner_text(), summary.inner_text()

    # ANALYZE: the UI marks an item done as soon as the analyze call returns,
    # but that endpoint only QUEUES the work, so done means started. Wait on the
    # API, which is what the Library view polls too.
    rows = httpx.get(f"{smoke_server}/api/tracks/", timeout=10.0).json()
    assert len(rows) == 2, f"expected 2 tracks after upload, got {rows}"
    _wait_for_analyses(smoke_server, [r["id"] for r in rows])

    # RECOMMEND: read it back through the UI.
    page.locator("nav.nav-center button", has_text="Library").click()
    page.locator(".track-item", has_text="SmokeE4").click()

    page.locator(".recs").wait_for(state="visible", timeout=60000)
    if page.locator("p.recs-empty").count():
        pytest.fail(
            "recommendations came back empty: E4 and A4 are no longer both "
            "within +/-5 BPM and Camelot compatible. Re-run the tone "
            "measurement documented at SMOKE_TONES and choose a new pair."
        )

    recs = page.locator(".rec-item")
    assert recs.count() == 1, f"expected exactly one recommendation, got {recs.count()}"
    assert "SmokeA4" in recs.first.inner_text()
    assert "8A" in recs.first.locator(".rec-camelot").inner_text()

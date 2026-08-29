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

import pytest

# This drives a real browser, so it is excluded from the default CI run with
# -m "not e2e" (CI has no browser). Run locally with the e2e extra installed.
# The login e2e was removed with auth in Phase 3; a no-auth "app opens straight to
# the library" flow awaits the frontend rewrite (Phase 7).
pytestmark = pytest.mark.e2e

PORT = 8099
BASE = f"http://127.0.0.1:{PORT}"

_HERE = os.path.dirname(os.path.abspath(__file__))
_FRONTEND = os.path.abspath(os.path.join(_HERE, "..", "..", "frontend"))
_BUILD_DIR = os.path.join(_FRONTEND, "build")


def _wait_for_port(port, timeout=30.0):
    import time
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
    stamp = "VITE_API_URL=" + BASE
    if os.path.isfile(built) and os.path.isfile(_STAMP):
        with open(_STAMP, encoding="utf-8") as fh:
            same_env = fh.read() == stamp
        if same_env and os.path.getmtime(built) >= _newest_input_mtime():
            return
    # Vite exposes only VITE_-prefixed vars to client code. The CRA-era
    # REACT_APP_API_URL was silently ignored after the Vite migration.
    env = dict(os.environ, CI="false", VITE_API_URL=BASE)
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


def test_landing_page_loads_and_shows_guest_entry(server, page):
    page.goto(server, wait_until="networkidle")
    # The real browser rendered the React landing page...
    assert "Harmonia" in page.content()
    # ...and the guest entry point (Landing's onTryFree button) is visible.
    guest_btn = page.locator("button.hero-btn-primary")
    guest_btn.wait_for(state="visible", timeout=15000)
    assert "Try it free" in guest_btn.inner_text()

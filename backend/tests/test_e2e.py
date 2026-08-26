# End-to-end tests: a real headless Chromium (Playwright) driving the built
# React UI against a real backend.
#
# The session fixture stands up two servers once:
#   * uvicorn serving backend.main.app on API_PORT. It reuses the SQLite test
#     database wired up in conftest.py (get_db is overridden there), so no
#     Postgres is needed and the browser and the test see the same rows.
#   * a threaded http.server serving the static React build (frontend/build)
#     on WEB_PORT.
#
# The React build must be produced with REACT_APP_API_URL pointing at API_PORT
# so the browser's XHR calls reach our uvicorn. The build step is done once, in
# the fixture, if frontend/build is missing.

import functools
import http.server
import os
import socket
import subprocess
import threading

import pytest

# Both tests here drive a real browser, so exclude them from the default CI run
# with -m "not e2e" (CI has no browser). Run locally with the e2e extra installed.
pytestmark = pytest.mark.e2e

API_PORT = 8099
WEB_PORT = 8098
API_BASE = f"http://127.0.0.1:{API_PORT}"
WEB_BASE = f"http://127.0.0.1:{WEB_PORT}"

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


def _ensure_build():
    """Build the React app if needed, with the API URL baked in for our port."""
    if os.path.isfile(os.path.join(_BUILD_DIR, "index.html")):
        return
    env = dict(os.environ, CI="false", REACT_APP_API_URL=API_BASE)
    subprocess.run(
        ["npm", "run", "build"],
        cwd=_FRONTEND, env=env, check=True,
        capture_output=True, text=True, timeout=600,
    )


@pytest.fixture(scope="session")
def servers():
    import uvicorn

    _ensure_build()
    if not os.path.isfile(os.path.join(_BUILD_DIR, "index.html")):
        pytest.fail(f"React build missing at {_BUILD_DIR}; `npm run build` did not produce it.")

    # Static server for the built React UI.
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=_BUILD_DIR)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", WEB_PORT), handler)
    httpd.daemon_threads = True
    web_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    web_thread.start()

    # Backend via uvicorn, in-process, sharing conftest's SQLite test DB.
    from backend.main import app
    config = uvicorn.Config(app, host="127.0.0.1", port=API_PORT, log_level="warning")
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None  # required off the main thread
    api_thread = threading.Thread(target=server.run, daemon=True)
    api_thread.start()

    assert _wait_for_port(WEB_PORT), "static web server did not start"
    assert _wait_for_port(API_PORT), "uvicorn backend did not start"

    yield {"web": WEB_BASE, "api": API_BASE}

    httpd.shutdown()
    server.should_exit = True


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


def test_landing_page_loads_and_shows_guest_entry(servers, page):
    page.goto(servers["web"], wait_until="networkidle")
    # The real browser rendered the React landing page...
    assert "Harmonia" in page.content()
    # ...and the guest entry point (Landing's onTryFree button) is visible.
    guest_btn = page.locator("button.hero-btn-primary")
    guest_btn.wait_for(state="visible", timeout=15000)
    assert "Try it free" in guest_btn.inner_text()


def test_login_then_view_library(servers, page):
    import httpx
    # Seed a user through the same API the browser will call.
    httpx.post(f"{servers['api']}/api/users/register",
               json={"username": "e2e_user", "password": "e2e_pw"}, timeout=10)

    page.goto(servers["web"], wait_until="networkidle")
    page.locator("button.nav-login").click()          # opens the Auth modal
    page.get_by_placeholder("Username").fill("e2e_user")
    page.get_by_placeholder("Password").fill("e2e_pw")
    page.locator("button.submit").click()             # submit login

    # After a successful login the app switches to the Library view.
    page.get_by_placeholder("Search by title or artist...").wait_for(timeout=15000)
    assert "Your Library" in page.content()

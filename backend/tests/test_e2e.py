# End-to-end tests (Playwright, headless Chromium against the running React app).
#
# STATUS IN THIS ENVIRONMENT: NOT AUTOMATED.
#
# Playwright and its Chromium build install fine, but the headless browser
# cannot launch here: it aborts at startup with
#     error while loading shared libraries: libnspr4.so: cannot open shared
#     object file: No such file or directory
# The fix is the system packages installed by `playwright install-deps`
# (libnspr4, libnss3, libatk1.0, ...), which require root/apt. `sudo` in this
# WSL Ubuntu is password-gated and non-interactive installs fail, so the
# browser genuinely cannot run. Rather than fake a pass, both flows below are
# skipped with this reason and documented as manual steps.
#
# The tests are written out in full so they can be run unchanged on a machine
# where `playwright install --with-deps chromium` succeeds and the frontend
# dev server (npm start) is running on http://localhost:3000.

import pytest

E2E_BLOCKED = "E2E not automated: headless Chromium missing system libs (libnspr4.so); needs root `playwright install-deps`, sudo is password-gated here."


@pytest.mark.skip(reason=E2E_BLOCKED)
def test_landing_page_loads_and_shows_guest_entry():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://localhost:3000")
        # Landing page renders the Harmonia name and a way in as a guest.
        assert "Harmonia" in page.content()
        page.get_by_text("Guest", exact=False).click()
        browser.close()


@pytest.mark.skip(reason=E2E_BLOCKED)
def test_login_then_view_library():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://localhost:3000")
        page.get_by_placeholder("Username").fill("e2e_user")
        page.get_by_placeholder("Password").fill("e2e_pw")
        page.get_by_role("button", name="Login").click()
        # After login the library view should be reachable.
        page.wait_for_url("**/library**", timeout=5000)
        browser.close()

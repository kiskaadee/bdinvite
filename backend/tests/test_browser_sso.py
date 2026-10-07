import contextlib
import threading
import time
from collections.abc import Generator

import pytest
import uvicorn
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from app.main import app

APP_HOST = "127.0.0.1"
APP_PORT = 8000
BASE_URL = f"http://{APP_HOST}:{APP_PORT}"


@pytest.fixture(scope="module")
def live_server() -> Generator[str, None, None]:
    """Start uvicorn server in a background thread for browser testing."""
    config = uvicorn.Config(
        app,
        host=APP_HOST,
        port=APP_PORT,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for server readiness
    import httpx

    ready = False
    for _ in range(50):
        with contextlib.suppress(Exception):
            r = httpx.get(f"{BASE_URL}/birthday/api/docs", timeout=0.5)
            if r.status_code == 200:
                ready = True
                break
        time.sleep(0.1)

    assert ready, "Server failed to start in time"
    yield BASE_URL
    server.should_exit = True
    thread.join(timeout=2)


@pytest.fixture(scope="module")
def browser_instance() -> Generator[Browser, None, None]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def browser_context(browser_instance: Browser) -> Generator[BrowserContext, None, None]:
    context = browser_instance.new_context()
    yield context
    context.close()


@pytest.fixture
def page(browser_context: BrowserContext) -> Generator[Page, None, None]:
    pg = browser_context.new_page()
    yield pg
    pg.close()


def test_browser_sso_complete_interactive_loop(
    live_server: str,
    browser_context: BrowserContext,
    page: Page,
):
    """Complete browser SSO acceptance test (CP7).

    Verifies:
    1. Browser navigates to /birthday/admin -> redirected to OIDC login form.
    2. Form submitted with admin@example.com / password123.
    3. Browser redirects back through callback -> receives HttpOnly cookie -> arrives on Admin Dashboard.
    4. Admin Dashboard renders RSVPs table and authenticated user info.
    5. Clicking 'Logout' button revokes session -> returns to unauthenticated state.
    """
    # 1. Unauthenticated navigation to /birthday/admin -> redirected to OIDC login form
    admin_url = f"{live_server}/birthday/admin"
    page.goto(admin_url)
    page.wait_for_url("**/authorize**", timeout=10000)
    assert "8088" in page.url or "authorize" in page.url

    # 2. Submit test credentials
    page.fill("input[name='username']", "admin@example.com")
    if page.query_selector("input[name='password']"):
        page.fill("input[name='password']", "password123")
    page.click("input[type='submit']")

    # 3. Callback completes, sets HttpOnly cookie, and lands on Admin Dashboard
    page.wait_for_url("**/birthday/admin", timeout=10000)
    assert page.url.endswith("/birthday/admin")

    cookies = browser_context.cookies()
    session_cookie = next(
        (c for c in cookies if c.get("name") == "bdinvite_session"), None
    )
    assert session_cookie is not None, "bdinvite_session cookie must be set"
    assert session_cookie.get("httpOnly") is True, "Session cookie must be HttpOnly"

    # 4. Admin Dashboard renders RSVPs table and user info
    page.wait_for_selector("text=Respuestas", timeout=10000)
    user_info_elem = page.locator("[data-testid='user-info']")
    user_info_elem.wait_for(state="visible", timeout=10000)
    user_text = user_info_elem.text_content() or ""
    assert "admin" in user_text.lower(), f"Expected admin user info, got: {user_text}"

    # Verify RSVPs table / UI content is visible
    assert page.locator("nav").is_visible()

    # 5. Clicking 'Logout' button revokes session -> returns to unauthenticated state
    logout_btn = page.locator("button:has-text('Logout')")
    assert logout_btn.is_visible()
    logout_btn.click()

    # UI displays unauthenticated state screen
    page.wait_for_selector("[data-testid='unauthenticated-state']", timeout=10000)
    assert page.locator("[data-testid='unauthenticated-state']").is_visible()
    assert page.locator("text=Sesión Finalizada").is_visible()

    # Re-clicking login initiates fresh OIDC flow
    page.locator("[data-testid='login-btn']").click()
    page.wait_for_url("**/authorize**", timeout=10000)
    assert "authorize" in page.url

    # Attempting to access /birthday/admin again redirects to login
    page.goto(admin_url)
    page.wait_for_url("**/authorize**", timeout=10000)
    assert "authorize" in page.url

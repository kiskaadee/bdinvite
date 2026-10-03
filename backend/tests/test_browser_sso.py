"""Automated Browser Acceptance Tests for Single Sign-On (SSO) Flow via Playwright.

Verifies Checkpoint 7 (CP7) requirements:
1. Browser navigates to /birthday/admin -> redirected to OIDC login form.
2. Form submitted with admin@example.com / password123.
3. Browser redirects back through callback -> receives HttpOnly cookie -> arrives on Admin Dashboard.
4. Admin Dashboard renders RSVPs table and authenticated user information.
5. Clicking Logout button revokes session -> returns to unauthenticated state.
"""

import json
import threading
import time
from typing import Generator

import httpx
import pytest
import uvicorn
from playwright.sync_api import BrowserContext, Page, sync_playwright

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import RSVP
from app.services.config import seed_default_config


@pytest.fixture(scope="module")
def live_server() -> Generator[str, None, None]:
    """Start uvicorn server running FastAPI application in background daemon thread."""
    # Ensure fresh DB tables and seed data
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_default_config(db)
        # Seed an RSVP item to guarantee the table renders records
        test_rsvp = db.query(RSVP).filter_by(phone="3009998877").first()
        if not test_rsvp:
            test_rsvp = RSVP(
                name="Invitado de Prueba",
                phone="3009998877",
                email="invitado@test.com",
            )
            db.add(test_rsvp)
            db.commit()

    config = uvicorn.Config(
        "app.main:app",
        host="127.0.0.1",
        port=settings.APP_PORT,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    base_url = f"http://localhost:{settings.APP_PORT}"

    # Poll until server is responding
    ready = False
    for _ in range(50):
        try:
            with httpx.Client() as client:
                res = client.get(f"{base_url}/birthday/api/config", timeout=1.0)
                if res.status_code == 200:
                    ready = True
                    break
        except Exception:
            time.sleep(0.1)

    assert ready, f"Live server failed to start on {base_url}"

    yield base_url

    server.should_exit = True
    thread.join(timeout=3.0)


@pytest.fixture(scope="module")
def browser_context():
    """Launch headless Chromium browser and provide an isolated context."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        yield context
        context.close()
        browser.close()


def test_browser_sso_complete_flow(live_server: str, browser_context: BrowserContext):
    """Execute complete end-to-end interactive browser authentication flow."""
    page: Page = browser_context.new_page()

    # 1. Unauthenticated navigation to /birthday/admin initiates login redirect
    page.goto(f"{live_server}/birthday/admin")

    # 2. Browser is redirected to OIDC provider login page
    page.wait_for_url(lambda u: "8088" in u and "/authorize" in u, timeout=10000)
    assert "8088" in page.url

    # 3. Submit credentials on Mock OAuth2 Server login form
    page.wait_for_selector("input[name='username']", timeout=5000)
    page.fill("input[name='username']", "admin@example.com")

    if page.locator("input[type='password']").count() > 0:
        page.fill("input[type='password']", "password123")

    if page.locator("textarea[name='claims']").count() > 0:
        page.fill(
            "textarea[name='claims']",
            json.dumps({
                "sub": "admin-001",
                "email": "admin@example.com",
                "name": "Admin User",
                "groups": ["bdinvite_admins"],
            }),
        )

    page.click("input[type='submit']")

    # 4. Redirects through callback -> receives HttpOnly cookie -> arrives on Admin Dashboard
    page.wait_for_url(lambda u: "/birthday/admin" in u and "8088" not in u, timeout=10000)
    assert "/birthday/admin" in page.url

    # Verify HttpOnly session cookie
    cookies = browser_context.cookies("http://localhost:8000")
    session_cookies = [c for c in cookies if c.get("name") == settings.SESSION_COOKIE_NAME]
    assert len(session_cookies) >= 1, f"Missing {settings.SESSION_COOKIE_NAME} cookie"
    session_cookie = session_cookies[0]
    assert session_cookie.get("httpOnly") is True, "Session cookie must be HttpOnly"
    same_site = session_cookie.get("sameSite")
    assert same_site is not None and same_site.lower() in ["lax", "strict"]

    # 5. Admin navigation header displays authenticated user info and working Logout button
    page.wait_for_selector("[data-testid='user-info']", timeout=5000)
    user_info_text = page.locator("[data-testid='user-info']").inner_text()
    assert "admin@example.com" in user_info_text or "Admin User" in user_info_text

    # 6. Admin Dashboard renders RSVPs table with live data
    page.wait_for_selector("table", timeout=5000)
    assert page.locator("table").is_visible()
    # Confirm seeded attendee appears in the table
    page.wait_for_selector("text=Invitado de Prueba", timeout=5000)
    assert page.locator("text=Invitado de Prueba").is_visible()

    # 7. Clicking "Logout" button revokes session and returns UI to unauthenticated state
    logout_btn = page.locator("[data-testid='logout-btn']")
    assert logout_btn.is_visible()
    logout_btn.click()

    # UI displays unauthenticated state
    page.wait_for_selector("[data-testid='unauthenticated-state']", timeout=5000)
    assert page.locator("[data-testid='unauthenticated-state']").is_visible()

    # RSVPs table is no longer displayed
    assert page.locator("table").count() == 0

    page.close()

"""Tests for Browser Session Management and Session Fixation Protection (Checkpoint 4)."""

import time
from collections.abc import Generator
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi import Response
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.auth import (
    Identity,
    OIDCAuthAdapter,
    OIDCClient,
    OIDCConfig,
    SessionRecord,
)
from app.routes.auth import get_auth_adapter, set_auth_adapter

FIXTURE_ISSUER = "http://localhost:8088/default"
FIXTURE_CLIENT_ID = "bdinvite-client"
FIXTURE_CLIENT_SECRET = "bdinvite-secret"
FIXTURE_REDIRECT_URI = "http://localhost:8000/birthday/api/auth/callback"


@pytest.fixture
def oidc_config() -> OIDCConfig:
    return OIDCConfig(
        issuer=FIXTURE_ISSUER,
        client_id=FIXTURE_CLIENT_ID,
        client_secret=FIXTURE_CLIENT_SECRET,
        redirect_uri=FIXTURE_REDIRECT_URI,
    )


@pytest.fixture
def oidc_client(oidc_config: OIDCConfig) -> OIDCClient:
    return OIDCClient(oidc_config)


@pytest.fixture
def auth_adapter(oidc_client: OIDCClient) -> Generator[OIDCAuthAdapter, None, None]:
    adapter = OIDCAuthAdapter(
        client=oidc_client,
        session_cookie_name="bdinvite_session",
        cookie_secure=False,
        cookie_samesite="lax",
        session_lifetime=3600.0,
    )
    set_auth_adapter(adapter)
    yield adapter
    set_auth_adapter(None)


def create_request(
    headers: dict[str, str] | None = None,
    cookies: dict[str, str] | None = None,
) -> Request:
    header_list: list[tuple[bytes, bytes]] = []
    if headers:
        for k, v in headers.items():
            header_list.append((k.lower().encode("latin-1"), v.encode("latin-1")))
    if cookies:
        cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())
        header_list.append((b"cookie", cookie_header.encode("latin-1")))

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/birthday/api/auth/session",
        "headers": header_list,
        "query_string": b"",
    }
    return Request(scope)


def obtain_auth_code_from_fixture(authorization_url: str, username: str) -> tuple[str, str]:
    parsed_url = urlparse(authorization_url)
    auth_endpoint = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
    query_params = parse_qs(parsed_url.query)
    flat_params = {k: v[0] for k, v in query_params.items()}

    with httpx.Client() as client:
        resp = client.post(
            auth_endpoint,
            params=flat_params,
            data={"username": username},
            follow_redirects=False,
        )
        assert resp.status_code == 302, f"Failed auth code post: {resp.text}"
        location = resp.headers["location"]

    redirect_parsed = urlparse(location)
    callback_params = parse_qs(redirect_parsed.query)
    return callback_params["code"][0], callback_params["state"][0]


# ============================================================================
# 1. Browser Session Contract & Security Invariant Tests
# ============================================================================


def test_session_cookie_issued_with_httponly_and_samesite(auth_adapter: OIDCAuthAdapter):
    """Security Invariant: The session cookie MUST have HttpOnly=True and SameSite.

    Client-side JavaScript must never have access to raw tokens or session identifiers.
    """
    identity = Identity(
        subject="admin-001",
        email="admin@example.com",
        name="Admin User",
        groups=["bdinvite_admins"],
    )
    response = Response()
    session_id = auth_adapter.establish_session(identity)
    auth_adapter.set_session_cookie(response, session_id)

    set_cookie = response.headers.get("set-cookie", "")
    assert auth_adapter.session_cookie_name in set_cookie
    assert session_id in set_cookie
    assert "HttpOnly" in set_cookie, "Session cookie MUST enforce HttpOnly=True"
    assert "SameSite=lax" in set_cookie or "samesite=lax" in set_cookie.lower()


def test_configurable_secure_flag():
    """Verify configurable Secure cookie flag: False in test/dev, True in production."""
    # 1. Development/test environment: Secure=False allows HTTP testing
    dev_adapter = OIDCAuthAdapter(
        client=OIDCClient(OIDCConfig(issuer=FIXTURE_ISSUER, client_id=FIXTURE_CLIENT_ID)),
        cookie_secure=False,
    )
    resp_dev = Response()
    s_dev = dev_adapter.establish_session(Identity(subject="dev", email="dev@local"))
    dev_adapter.set_session_cookie(resp_dev, s_dev)
    assert "secure" not in resp_dev.headers.get("set-cookie", "").lower()

    # 2. Production environment: Secure=True enforces HTTPS transmission
    prod_adapter = OIDCAuthAdapter(
        client=OIDCClient(OIDCConfig(issuer=FIXTURE_ISSUER, client_id=FIXTURE_CLIENT_ID)),
        cookie_secure=True,
    )
    resp_prod = Response()
    s_prod = prod_adapter.establish_session(Identity(subject="prod", email="prod@local"))
    prod_adapter.set_session_cookie(resp_prod, s_prod)
    set_cookie_prod = resp_prod.headers.get("set-cookie", "").lower()
    assert "secure" in set_cookie_prod, "Production session cookie MUST enforce Secure=True"


# ============================================================================
# 2. Session Fixation Barrier Tests
# ============================================================================


def test_session_fixation_barrier_rotates_session_id(auth_adapter: OIDCAuthAdapter):
    """Session Fixation Barrier:

    Successful authentication MUST generate a fresh, new session identifier.
    An existing pre-authentication session identifier must NEVER be promoted into an
    authenticated session (pre_auth_session_id != post_auth_session_id).
    """
    # 1. Pre-authentication state: client possesses an anonymous or pre-auth session ID
    pre_auth_session_id = auth_adapter.create_anonymous_session()
    assert pre_auth_session_id is not None
    # Pre-auth request resolves to anonymous
    req_pre = create_request(cookies={auth_adapter.session_cookie_name: pre_auth_session_id})
    assert auth_adapter.current_identity(req_pre) is None

    # 2. User successfully authenticates
    identity = Identity(
        subject="admin-001",
        email="admin@example.com",
        name="Admin User",
        groups=["bdinvite_admins"],
    )
    post_auth_session_id = auth_adapter.establish_session(
        identity=identity,
        pre_auth_session_id=pre_auth_session_id,
    )

    # 3. Assert Session Fixation Barrier guarantees
    assert post_auth_session_id != pre_auth_session_id, (
        f"Session Fixation violation: pre-auth ID was promoted! "
        f"{pre_auth_session_id} == {post_auth_session_id}"
    )

    # 4. Old pre-auth session ID is strictly invalid and resolves to None
    assert auth_adapter.current_identity(req_pre) is None

    # 5. New post-auth session ID resolves to the authenticated user
    req_post = create_request(cookies={auth_adapter.session_cookie_name: post_auth_session_id})
    resolved = auth_adapter.current_identity(req_post)
    assert resolved == identity


def test_session_fixation_barrier_via_callback(
    auth_adapter: OIDCAuthAdapter,
    oidc_client: OIDCClient,
):
    """Verify session fixation barrier through complete callback processing."""
    auth_url, _ = oidc_client.create_authorization_url()
    code, returned_state = obtain_auth_code_from_fixture(auth_url, username="guest@example.com")

    # Attacker sets fixed pre-auth session cookie on victim
    pre_auth_session_id = "pre_auth_attacker_fixed_session_key"
    req = create_request(cookies={auth_adapter.session_cookie_name: pre_auth_session_id})
    resp = Response()

    identity, post_auth_session_id = auth_adapter.handle_callback(
        code=code,
        state=returned_state,
        response=resp,
        request=req,
        extra_params={"username": "guest@example.com"},
    )

    # Assert fixation barrier
    assert post_auth_session_id != pre_auth_session_id
    assert identity.subject == "guest-001"

    # Attacker's pre-auth session resolves to nothing
    assert auth_adapter.current_identity(req) is None

    # Authenticated user's new cookie resolves to identity
    req_valid = create_request(cookies={auth_adapter.session_cookie_name: post_auth_session_id})
    assert auth_adapter.current_identity(req_valid) == identity


# ============================================================================
# 3. Session Lifecycle & Invalidation Tests
# ============================================================================


def test_valid_session_cookie_resolves_to_identity(auth_adapter: OIDCAuthAdapter):
    """Returning requests presenting a valid session cookie must resolve to Identity."""
    identity = Identity(
        subject="guest-001",
        email="guest@example.com",
        name="Guest User",
        groups=["guests"],
    )
    session_id = auth_adapter.establish_session(identity)

    req = create_request(cookies={auth_adapter.session_cookie_name: session_id})
    resolved = auth_adapter.current_identity(req)
    assert resolved == identity


def test_anonymous_request_resolves_to_none(auth_adapter: OIDCAuthAdapter):
    """Anonymous requests (no cookie or unknown session) resolve to None."""
    # 1. No cookies
    req_empty = create_request(cookies={})
    assert auth_adapter.current_identity(req_empty) is None

    # 2. Unknown session ID
    req_unknown = create_request(cookies={auth_adapter.session_cookie_name: "unknown_random_session_token"})
    assert auth_adapter.current_identity(req_unknown) is None


def test_expired_session_is_rejected_and_evicted(auth_adapter: OIDCAuthAdapter):
    """Expired sessions are rejected, treated as unauthenticated, and evicted."""
    identity = Identity(subject="usr_exp", email="exp@local")
    # Establish session with very short TTL
    session_id = auth_adapter.establish_session(identity, ttl=0.05)

    req = create_request(cookies={auth_adapter.session_cookie_name: session_id})
    # Initially valid
    assert auth_adapter.current_identity(req) == identity

    # Wait for expiration
    time.sleep(0.06)

    # Now expired: resolves to None and is evicted from memory
    assert auth_adapter.current_identity(req) is None
    assert session_id not in auth_adapter.sessions


def test_tampered_and_malformed_cookies_safely_rejected(auth_adapter: OIDCAuthAdapter):
    """Requests presenting tampered, malformed, or forged cookies must be safely rejected (not crash)."""
    malicious_inputs = [
        "tampered!@#$%^&*()",
        "valid_part\x00malicious_bytes",
        "a" * 1000,
        "session\r\nSet-Cookie: evil=1",
        "' OR '1'='1",
        "  \t\n  ",
        "../../etc/passwd",
        "{'session': 'eval'}",
    ]

    for bad_input in malicious_inputs:
        req = create_request(cookies={auth_adapter.session_cookie_name: bad_input})
        try:
            resolved = auth_adapter.current_identity(req)
            assert resolved is None, f"Expected None for malicious cookie: {bad_input!r}"
        except Exception as exc:
            pytest.fail(f"Application crashed on tampered cookie {bad_input!r}: {exc}")


def test_logout_invalidates_session_and_clears_cookie(auth_adapter: OIDCAuthAdapter):
    """Logout invalidates the session on the server and clears the browser cookie (Max-Age=0)."""
    identity = Identity(subject="admin-001", email="admin@example.com")
    session_id = auth_adapter.establish_session(identity)

    req = create_request(cookies={auth_adapter.session_cookie_name: session_id})
    assert auth_adapter.current_identity(req) == identity

    # Perform logout
    logout_resp = auth_adapter.logout(req)

    # 1. Server-side session revoked
    assert session_id not in auth_adapter.sessions
    assert auth_adapter.current_identity(req) is None

    # 2. Browser cookie cleared with Max-Age=0
    set_cookie = logout_resp.headers.get("set-cookie", "")
    assert auth_adapter.session_cookie_name in set_cookie
    assert "Max-Age=0" in set_cookie or "max-age=0" in set_cookie
    assert "HttpOnly" in set_cookie


# ============================================================================
# 4. FastAPI HTTP Integration Tests (Endpoints & TestClient)
# ============================================================================


def test_http_auth_session_and_logout_endpoints(
    client: TestClient,
    auth_adapter: OIDCAuthAdapter,
):
    """Integration test: /birthday/api/auth/session, /logout endpoints via HTTP TestClient."""
    # 1. Anonymous session check
    res_anon = client.get("/birthday/api/auth/session")
    assert res_anon.status_code == 200
    assert res_anon.json() == {"authenticated": False, "identity": None}

    # 2. Establish valid session for fixture admin user
    identity = Identity(
        subject="admin-001",
        email="admin@example.com",
        name="Admin User",
        groups=["bdinvite_admins"],
    )
    session_id = auth_adapter.establish_session(identity)

    # 3. Present session cookie to /session
    client.cookies.set(auth_adapter.session_cookie_name, session_id)
    res_auth = client.get("/birthday/api/auth/session")
    assert res_auth.status_code == 200
    auth_data = res_auth.json()
    assert auth_data["authenticated"] is True
    assert auth_data["identity"]["subject"] == "admin-001"
    assert auth_data["identity"]["email"] == "admin@example.com"
    assert auth_data["identity"]["groups"] == ["bdinvite_admins"]

    # 4. Admin endpoint accessed via session cookie
    res_admin = client.get("/birthday/api/admin/rsvps")
    assert res_admin.status_code == 200

    # 5. Logout via API POST
    res_logout = client.post("/birthday/api/auth/logout")
    assert res_logout.status_code == 200
    assert res_logout.json()["result"] == "SUCCESS"
    assert session_id not in auth_adapter.sessions

    # 6. Session cookie cleared on client
    set_cookie_header = res_logout.headers.get("set-cookie", "")
    assert "Max-Age=0" in set_cookie_header or "max-age=0" in set_cookie_header

    # 7. Subsequent request is unauthenticated
    res_after = client.get("/birthday/api/auth/session")
    assert res_after.json()["authenticated"] is False


def test_fixture_live_users_password_grant_session_flow(auth_adapter: OIDCAuthAdapter):
    """Test full login session lifecycle against pre-seeded fixture users."""
    # 1. Admin user authentication and session establishment
    admin_id, admin_session_id = auth_adapter.authenticate_and_establish_session(
        username="admin@example.com",
        password="password123",
    )
    assert admin_id.subject == "admin-001"
    assert "bdinvite_admins" in admin_id.groups

    req_admin = create_request(cookies={auth_adapter.session_cookie_name: admin_session_id})
    assert auth_adapter.current_identity(req_admin) == admin_id

    # 2. Guest user authentication and session establishment
    guest_id, guest_session_id = auth_adapter.authenticate_and_establish_session(
        username="guest@example.com",
        password="password123",
    )
    assert guest_id.subject == "guest-001"
    assert "guests" in guest_id.groups

    req_guest = create_request(cookies={auth_adapter.session_cookie_name: guest_session_id})
    assert auth_adapter.current_identity(req_guest) == guest_id

    # Distinct sessions for distinct users
    assert admin_session_id != guest_session_id

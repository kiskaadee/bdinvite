import time
from typing import Optional

import pytest
from fastapi import Request, Response
from fastapi.responses import Response as StarletteResponse
from fastapi.testclient import TestClient

from app.auth import (
    Identity,
    InMemorySessionStore,
    OIDCAuthAdapter,
    OIDCClient,
    sign_session_cookie,
    unsign_session_cookie,
)
from app.config import settings
from app.main import app
from app.routes.auth import get_auth_adapter

LIVE_ISSUER = "http://localhost:8088/default"
CLIENT_ID = "bdinvite-client"
CLIENT_SECRET = "bdinvite-secret"
REDIRECT_URI = "http://localhost:8000/birthday/api/auth/callback"


def create_dummy_request(
    headers: dict[str, str] | None = None,
    cookies: dict[str, str] | None = None,
) -> Request:
    """Helper to construct dummy Request instances for unit testing."""
    raw_headers: list[tuple[bytes, bytes]] = [
        (k.lower().encode("latin-1"), v.encode("latin-1"))
        for k, v in (headers or {}).items()
    ]
    if cookies:
        cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())
        raw_headers.append((b"cookie", cookie_header.encode("latin-1")))

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": raw_headers,
    }
    return Request(scope)


@pytest.fixture
def oidc_client() -> OIDCClient:
    return OIDCClient(
        issuer=LIVE_ISSUER,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
    )


@pytest.fixture
def auth_adapter(oidc_client: OIDCClient) -> OIDCAuthAdapter:
    return OIDCAuthAdapter(
        oidc_client=oidc_client,
        session_cookie_name="bdinvite_session",
        session_store=InMemorySessionStore(),
        cookie_secure=False,
        cookie_samesite="lax",
        session_max_age=3600,
        secret_key="test-session-secret",
    )


# ==============================================================================
# Unit Tests: Session Store & Cookie Security
# ==============================================================================


def test_session_store_lifecycle():
    """Verify session creation, retrieval, and explicit deletion."""
    store = InMemorySessionStore()
    identity = Identity(subject="user-1", email="user1@example.com")

    session = store.create_session(identity=identity, max_age_seconds=60)
    assert session.session_id is not None
    assert len(session.session_id) >= 32
    assert session.identity == identity
    assert session.is_authenticated is True
    assert session.is_expired() is False

    retrieved = store.get_session(session.session_id)
    assert retrieved is not None
    assert retrieved.session_id == session.session_id
    assert retrieved.identity == identity

    # Explicit deletion
    assert store.delete_session(session.session_id) is True
    assert store.get_session(session.session_id) is None
    assert store.delete_session(session.session_id) is False


def test_session_store_expiration():
    """Verify that expired sessions are rejected and pruned."""
    store = InMemorySessionStore()
    identity = Identity(subject="user-exp", email="exp@example.com")

    # Create session that expires immediately (max_age_seconds = -1)
    session = store.create_session(identity=identity, max_age_seconds=-1)
    assert session.is_expired() is True

    # Retrieval should return None and prune
    assert store.get_session(session.session_id) is None


def test_session_store_fixation_protection():
    """Verify Session Fixation Barrier in SessionStore: pre-auth session is destroyed upon login."""
    store = InMemorySessionStore()

    # Pre-authentication session (anonymous)
    pre_auth = store.create_session(identity=None, max_age_seconds=300)
    pre_auth_id = pre_auth.session_id
    assert pre_auth.is_authenticated is False
    assert store.get_session(pre_auth_id) is not None

    # Authenticate: create post-auth session providing pre_auth_session_id
    auth_identity = Identity(subject="user-auth", email="auth@example.com")
    post_auth = store.create_session(
        identity=auth_identity,
        max_age_seconds=300,
        pre_auth_session_id=pre_auth_id,
    )
    post_auth_id = post_auth.session_id

    # 1. Fresh identifier generated
    assert post_auth_id != pre_auth_id
    # 2. Pre-auth session ID is eradicated and can NEVER be used
    assert store.get_session(pre_auth_id) is None
    # 3. Post-auth session resolves to authenticated identity
    retrieved_post = store.get_session(post_auth_id)
    assert retrieved_post is not None
    assert retrieved_post.identity == auth_identity


def test_hmac_cookie_signing_and_tamper_detection():
    """Verify HMAC-SHA256 signature verification detects tampering."""
    secret = "my-secret-key"
    session_id = "random_session_token_12345"

    signed = sign_session_cookie(session_id, secret)
    assert "." in signed
    assert signed.startswith(session_id)

    # Valid unsign
    unsigned = unsign_session_cookie(signed, secret)
    assert unsigned == session_id

    # Tampered session ID payload
    tampered_payload = "forged_id" + signed[len(session_id) :]
    assert unsign_session_cookie(tampered_payload, secret) is None

    # Tampered signature
    tampered_sig = signed[:-4] + "dead"
    assert unsign_session_cookie(tampered_sig, secret) is None

    # Wrong secret key
    assert unsign_session_cookie(signed, "wrong-secret-key") is None

    # Malformed cookies
    assert unsign_session_cookie("no-dot-in-string", secret) is None
    assert unsign_session_cookie("", secret) is None
    assert unsign_session_cookie(None, secret) is None


# ==============================================================================
# Unit Tests: Adapter Contract & Security Invariants
# ==============================================================================


def test_adapter_session_cookie_security_invariants(auth_adapter: OIDCAuthAdapter):
    """Verify session cookie enforces HttpOnly=True, SameSite, and configurable Secure flag."""
    response = StarletteResponse()
    auth_adapter.set_session_cookie(response, "test-session-id")

    set_cookie = response.headers.get("set-cookie", "")
    assert "bdinvite_session=" in set_cookie
    # Security Invariant: HttpOnly MUST be True
    assert "httponly" in set_cookie.lower()
    # SameSite must be set
    assert "samesite=lax" in set_cookie.lower()
    # When cookie_secure is False (local/test), Secure attribute is omitted
    assert "secure" not in set_cookie.lower()

    # When cookie_secure is True (production), Secure attribute is enforced
    prod_adapter = OIDCAuthAdapter(
        oidc_client=auth_adapter.oidc_client,
        cookie_secure=True,
    )
    prod_response = StarletteResponse()
    prod_adapter.set_session_cookie(prod_response, "prod-session-id")
    prod_cookie = prod_response.headers.get("set-cookie", "")
    assert "secure" in prod_cookie.lower()
    assert "httponly" in prod_cookie.lower()


def test_adapter_current_identity_resolution(auth_adapter: OIDCAuthAdapter):
    """Verify current_identity resolution across valid, anonymous, tampered, and expired states."""
    identity = Identity(subject="alice-1", email="alice@example.com")

    # 1. Anonymous request (no cookie) -> None
    anon_req = create_dummy_request()
    assert auth_adapter.current_identity(anon_req) is None

    # 2. Valid authenticated session -> Identity
    session = auth_adapter.session_store.create_session(identity=identity)
    signed_cookie = sign_session_cookie(session.session_id, auth_adapter.secret_key)
    valid_req = create_dummy_request(cookies={"bdinvite_session": signed_cookie})
    resolved = auth_adapter.current_identity(valid_req)
    assert resolved == identity

    # 3. Unknown / non-existent session ID -> None
    fake_signed = sign_session_cookie("non-existent-session-id", auth_adapter.secret_key)
    unknown_req = create_dummy_request(cookies={"bdinvite_session": fake_signed})
    assert auth_adapter.current_identity(unknown_req) is None

    # 4. Tampered cookie signature -> None (safely rejected, no crash)
    tampered_cookie = signed_cookie[:-4] + "ffff"
    tampered_req = create_dummy_request(cookies={"bdinvite_session": tampered_cookie})
    assert auth_adapter.current_identity(tampered_req) is None

    # 5. Malformed cookie -> None
    malformed_req = create_dummy_request(cookies={"bdinvite_session": "not-valid;;bad"})
    assert auth_adapter.current_identity(malformed_req) is None

    # 6. Expired session -> None
    expired_session = auth_adapter.session_store.create_session(identity=identity, max_age_seconds=-10)
    exp_cookie = sign_session_cookie(expired_session.session_id, auth_adapter.secret_key)
    exp_req = create_dummy_request(cookies={"bdinvite_session": exp_cookie})
    assert auth_adapter.current_identity(exp_req) is None


def test_adapter_session_fixation_barrier(auth_adapter: OIDCAuthAdapter):
    """Verify that authenticating rotates the session identifier and invalidates the pre-auth session."""
    # Establish pre-authentication session
    pre_session = auth_adapter.session_store.create_session(identity=None)
    pre_id = pre_session.session_id
    pre_signed = sign_session_cookie(pre_id, auth_adapter.secret_key)

    pre_req = create_dummy_request(cookies={"bdinvite_session": pre_signed})
    assert auth_adapter.current_identity(pre_req) is None

    # Successful authentication transitions session
    user_identity = Identity(subject="victim-01", email="victim@example.com")
    resp = StarletteResponse()
    post_session = auth_adapter.create_session(
        identity=user_identity,
        request=pre_req,
        response=resp,
    )
    post_id = post_session.session_id

    # Invariant: pre_auth_session_id != post_auth_session_id
    assert pre_id != post_id

    # Invariant: pre_auth_session_id is defunct and not authenticated
    assert auth_adapter.session_store.get_session(pre_id) is None
    assert auth_adapter.current_identity(pre_req) is None

    # Invariant: post_auth_session_id is valid and authenticated
    post_signed = sign_session_cookie(post_id, auth_adapter.secret_key)
    post_req = create_dummy_request(cookies={"bdinvite_session": post_signed})
    assert auth_adapter.current_identity(post_req) == user_identity


def test_adapter_logout_revocation(auth_adapter: OIDCAuthAdapter):
    """Verify that logout revokes session on server and clears the browser cookie."""
    identity = Identity(subject="bob-1", email="bob@example.com")
    session = auth_adapter.session_store.create_session(identity=identity)
    signed_cookie = sign_session_cookie(session.session_id, auth_adapter.secret_key)

    req = create_dummy_request(cookies={"bdinvite_session": signed_cookie})
    assert auth_adapter.current_identity(req) == identity

    # Terminate session
    logout_resp = auth_adapter.logout(req)
    assert logout_resp.status_code == 302

    # Storage revocation check
    assert auth_adapter.session_store.get_session(session.session_id) is None
    # Subsequent resolution must be anonymous
    assert auth_adapter.current_identity(req) is None

    # Cookie clearance check (Max-Age=0)
    set_cookie_header = logout_resp.headers.get("set-cookie", "")
    assert "bdinvite_session" in set_cookie_header
    assert "max-age=0" in set_cookie_header.lower()


# ==============================================================================
# Integration Tests: HTTP Endpoints (/birthday/api/auth/*)
# ==============================================================================


def test_http_anonymous_request_resolves_to_unauthorized(client: TestClient):
    """Anonymous request to /me returns HTTP 401."""
    resp = client.get("/birthday/api/auth/me")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Not authenticated"


def test_http_login_issues_httponly_samesite_cookie(client: TestClient):
    """Direct login against IdP issues an HttpOnly, SameSite session cookie."""
    resp = client.post(
        "/birthday/api/auth/login",
        json={"username": "guest@example.com", "password": "password123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["subject"] == "guest-001"
    assert data["email"] == "guest@example.com"

    # Verify cookie attributes
    set_cookie = resp.headers.get("set-cookie", "")
    assert "bdinvite_session=" in set_cookie
    assert "httponly" in set_cookie.lower()
    assert "samesite=lax" in set_cookie.lower()


def test_http_session_fixation_rotation_on_login(client: TestClient):
    """Verify that an existing pre-authentication session cookie is rotated upon login."""
    # 1. Start with an anonymous / pre-authentication session
    resp_pre = client.get("/birthday/api/auth/login", follow_redirects=False)
    assert resp_pre.status_code == 302
    pre_auth_cookie = resp_pre.cookies.get("bdinvite_session")
    assert pre_auth_cookie is not None

    # 2. Pre-auth session resolves to unauthorized
    resp_anon = client.get("/birthday/api/auth/me", cookies={"bdinvite_session": pre_auth_cookie})
    assert resp_anon.status_code == 401

    # 3. Authenticate while presenting pre_auth_cookie
    resp_login = client.post(
        "/birthday/api/auth/login",
        json={"username": "admin@example.com", "password": "password123"},
        cookies={"bdinvite_session": pre_auth_cookie},
    )
    assert resp_login.status_code == 200
    post_auth_cookie = resp_login.cookies.get("bdinvite_session")
    assert post_auth_cookie is not None

    # 4. Security Invariant: pre_auth != post_auth
    assert pre_auth_cookie != post_auth_cookie

    # 5. Pre-auth cookie MUST NOT have been promoted
    resp_old = client.get("/birthday/api/auth/me", cookies={"bdinvite_session": pre_auth_cookie})
    assert resp_old.status_code == 401

    # 6. Post-auth cookie resolves to authenticated user
    resp_valid = client.get("/birthday/api/auth/me", cookies={"bdinvite_session": post_auth_cookie})
    assert resp_valid.status_code == 200
    assert resp_valid.json()["subject"] == "admin-001"
    assert "bdinvite_admins" in resp_valid.json()["groups"]


def test_http_tampered_cookie_rejected(client: TestClient):
    """Requests with tampered or forged cookies are safely rejected with HTTP 401."""
    # Attempt request with random tampered cookie
    resp = client.get(
        "/birthday/api/auth/me",
        cookies={"bdinvite_session": "forged_session_id.invalid_signature_hash"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Not authenticated"


def test_http_expired_cookie_rejected(client: TestClient):
    """Requests presenting an expired session cookie are rejected with HTTP 401."""
    adapter = get_auth_adapter()
    expired_session = adapter.session_store.create_session(
        identity=Identity(subject="expired-user", email="exp@test.com"),
        max_age_seconds=-10,
    )
    signed_cookie = sign_session_cookie(expired_session.session_id, adapter.secret_key)

    resp = client.get(
        "/birthday/api/auth/me",
        cookies={"bdinvite_session": signed_cookie},
    )
    assert resp.status_code == 401


def test_http_logout_invalidates_session_and_clears_cookie(client: TestClient):
    """POST /birthday/api/auth/logout invalidates session and clears cookie with Max-Age=0."""
    # 1. Login to obtain session
    login_resp = client.post(
        "/birthday/api/auth/login",
        json={"username": "guest@example.com", "password": "password123"},
    )
    assert login_resp.status_code == 200
    cookie_val = login_resp.cookies.get("bdinvite_session")
    assert cookie_val is not None

    # Verify session is authenticated
    me_resp = client.get("/birthday/api/auth/me", cookies={"bdinvite_session": cookie_val})
    assert me_resp.status_code == 200

    # 2. Logout via POST
    logout_resp = client.post("/birthday/api/auth/logout", cookies={"bdinvite_session": cookie_val})
    assert logout_resp.status_code == 200
    assert logout_resp.json()["status"] == "ok"

    # Verify cookie clearance header
    set_cookie = logout_resp.headers.get("set-cookie", "")
    assert "bdinvite_session" in set_cookie
    assert "max-age=0" in set_cookie.lower()

    # 3. Subsequent request with the same cookie is rejected
    me_after = client.get("/birthday/api/auth/me", cookies={"bdinvite_session": cookie_val})
    assert me_after.status_code == 401

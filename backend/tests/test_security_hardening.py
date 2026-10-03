"""Security Hardening and Deployment Independence verification tests (Checkpoint 8).

Validates adversarial edge cases:
1. Forged / invalid CSRF state returns HTTP 400 Bad Request.
2. Forged / tampered ID token signature returns HTTP 401 Unauthorized.
3. Mismatched or replayed nonce returns HTTP 401 Unauthorized.
4. Missing or invalid PKCE code_verifier returns HTTP 401 Unauthorized.
5. Expired ID token / expired session cookie returns HTTP 401 Unauthorized.
6. Authenticated non-admin user accessing admin APIs returns HTTP 403 Forbidden.
7. Legacy Remote-User header without a valid authenticated session returns HTTP 401 Unauthorized.
8. Deployment independence: Direct Standalone Mode vs Homelab Production Mode.
"""

import base64
import json
import time
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi.testclient import TestClient

from app.auth import (
    Identity,
    InvalidCodeVerifierError,
    InvalidNonceError,
    InvalidStateError,
    OIDCAuthAdapter,
    OIDCClient,
    OIDCConfig,
    OIDCTransaction,
    SessionRecord,
    TokenValidationError,
    get_auth_adapter,
)
from app.config import Settings

FIXTURE_ISSUER = "http://localhost:8088/default"
FIXTURE_CLIENT_ID = "bdinvite-client"
FIXTURE_CLIENT_SECRET = "bdinvite-secret"
FIXTURE_REDIRECT_URI = "http://localhost:8000/birthday/api/auth/callback"


def _obtain_auth_code(
    authorization_url: str,
    username: str = "security_test_user",
    claims: dict | None = None,
) -> tuple[str, str]:
    """Helper to simulate user authentication against the Navikt mock-oauth2-server fixture."""
    parsed_url = urlparse(authorization_url)
    auth_endpoint = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
    query_params = parse_qs(parsed_url.query)
    flat_params = {k: v[0] for k, v in query_params.items()}

    post_data: dict[str, str] = {"username": username}
    if claims:
        post_data["claims"] = json.dumps(claims)

    with httpx.Client() as http_client:
        resp = http_client.post(
            auth_endpoint,
            params=flat_params,
            data=post_data,
            follow_redirects=False,
        )
        assert resp.status_code == 302, f"Expected 302 redirect, got {resp.status_code}: {resp.text}"
        location = resp.headers["location"]

    redirect_parsed = urlparse(location)
    callback_params = parse_qs(redirect_parsed.query)
    assert "code" in callback_params
    assert "state" in callback_params
    return callback_params["code"][0], callback_params["state"][0]


# ==============================================================================
# 1. Adversarial State Rejection (CSRF Mitigation) -> HTTP 400 Bad Request
# ==============================================================================

def test_forged_csrf_state_returns_400(client: TestClient):
    """Forged / unrecognized CSRF state returns HTTP 400 Bad Request."""
    adapter = get_auth_adapter()
    with pytest.raises(InvalidStateError):
        adapter.client.validate_state("forged_state_xyz")

    res = client.get(
        "/birthday/api/auth/callback",
        params={"code": "dummy_auth_code", "state": "forged_malicious_state_xyz"},
    )
    assert res.status_code == 400
    assert "detail" in res.json()


def test_replayed_csrf_state_returns_400(client: TestClient):
    """Replaying an already-consumed CSRF state parameter returns HTTP 400 Bad Request."""
    adapter = get_auth_adapter()
    auth_url, _ = adapter.client.create_authorization_url()
    code, returned_state = _obtain_auth_code(auth_url, username="replay_state_user")

    # First callback succeeds and consumes state
    res1 = client.get(
        "/birthday/api/auth/callback",
        params={"code": code, "state": returned_state},
        follow_redirects=False,
    )
    assert res1.status_code == 302

    # Second callback replaying the exact same state must return HTTP 400
    res2 = client.get(
        "/birthday/api/auth/callback",
        params={"code": code, "state": returned_state},
    )
    assert res2.status_code == 400
    assert "already consumed" in res2.json()["detail"].lower() or "invalid" in res2.json()["detail"].lower()


def test_expired_csrf_state_returns_400(client: TestClient):
    """Authentication transaction that exceeded its TTL returns HTTP 400 Bad Request."""
    adapter = get_auth_adapter()
    _, tx = adapter.client.create_authorization_url()

    # Artificially expire the transaction
    expired_tx = OIDCTransaction(
        state=tx.state,
        nonce=tx.nonce,
        code_verifier=tx.code_verifier,
        created_at=time.time() - 900.0,
        expires_in=600.0,
    )
    adapter.client._transactions[tx.state] = expired_tx

    res = client.get(
        "/birthday/api/auth/callback",
        params={"code": "any_code", "state": tx.state},
    )
    assert res.status_code == 400
    assert "expired" in res.json()["detail"].lower()


# ==============================================================================
# 2. Forged / Tampered ID Token Signature -> HTTP 401 Unauthorized
# ==============================================================================

def test_tampered_id_token_signature_returns_401():
    """Tampered ID token signature raises TokenValidationError (HTTP 401)."""
    adapter = get_auth_adapter()
    auth_url, _ = adapter.client.create_authorization_url()
    code, returned_state = _obtain_auth_code(auth_url, username="tamper_sig_user")

    validated_tx = adapter.client.validate_state(returned_state)
    tokens = adapter.client.exchange_code(code=code, transaction_or_verifier=validated_tx)
    valid_id_token = tokens["id_token"]

    parts = valid_id_token.split(".")
    assert len(parts) == 3
    header_b64, payload_b64, sig_b64 = parts

    # Invert characters in the signature segment
    tampered_sig = ("Z" if sig_b64[-1] != "Z" else "A") + sig_b64[1:]
    tampered_token = f"{header_b64}.{payload_b64}.{tampered_sig}"

    with pytest.raises(TokenValidationError) as exc_info:
        adapter.client.validate_id_token(id_token=tampered_token, nonce=validated_tx.nonce)
    assert exc_info.value.status_code == 401


def test_tampered_id_token_bearer_header_returns_401(client: TestClient):
    """Bearer request containing a forged / tampered ID token signature returns HTTP 401."""
    adapter = get_auth_adapter()
    auth_url, _ = adapter.client.create_authorization_url()
    code, returned_state = _obtain_auth_code(auth_url, username="bearer_tamper_user")

    validated_tx = adapter.client.validate_state(returned_state)
    tokens = adapter.client.exchange_code(code=code, transaction_or_verifier=validated_tx)
    valid_id_token = tokens["id_token"]

    parts = valid_id_token.split(".")
    tampered_token = f"{parts[0]}.{parts[1]}.tampered_signature_bytes_12345"

    res = client.get(
        "/birthday/api/admin/rsvps",
        headers={"Authorization": f"Bearer {tampered_token}"},
    )
    assert res.status_code == 401


def test_alg_none_id_token_rejected_with_401():
    """ID token with 'alg': 'none' is rejected with HTTP 401."""
    adapter = get_auth_adapter()
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode()).decode().rstrip("=")
    payload = base64.urlsafe_b64encode(
        json.dumps({
            "sub": "admin",
            "iss": adapter.client.config.issuer,
            "aud": adapter.client.config.client_id,
            "exp": time.time() + 3600,
        }).encode()
    ).decode().rstrip("=")
    forged_token = f"{header}.{payload}."

    with pytest.raises(TokenValidationError) as exc_info:
        adapter.client.validate_id_token(forged_token)
    assert exc_info.value.status_code == 401


# ==============================================================================
# 3. Mismatched or Replayed Nonce -> HTTP 401 Unauthorized
# ==============================================================================

def test_mismatched_nonce_returns_401():
    """ID token with mismatched nonce claim raises InvalidNonceError (HTTP 401)."""
    adapter = get_auth_adapter()
    auth_url, _ = adapter.client.create_authorization_url()
    code, returned_state = _obtain_auth_code(auth_url, username="nonce_mismatch_user")

    validated_tx = adapter.client.validate_state(returned_state)
    tokens = adapter.client.exchange_code(code=code, transaction_or_verifier=validated_tx)
    id_token = tokens["id_token"]

    with pytest.raises(InvalidNonceError) as exc_info:
        adapter.client.validate_id_token(id_token=id_token, nonce="completely_different_nonce_val")
    assert exc_info.value.status_code == 401
    assert "nonce" in exc_info.value.detail.lower()


def test_missing_nonce_when_expected_returns_401(monkeypatch):
    """ID token missing expected nonce claim raises InvalidNonceError (HTTP 401)."""
    adapter = get_auth_adapter()
    # Mock jwt.decode to return valid claims except missing the required nonce
    mock_claims = {
        "sub": "user123",
        "email": "user@example.com",
        "iss": adapter.client.config.issuer,
        "aud": adapter.client.config.client_id,
        "exp": time.time() + 3600,
    }
    monkeypatch.setattr("jwt.get_unverified_header", lambda token: {"alg": "RS256", "kid": "mock_kid"})
    monkeypatch.setattr("jwt.decode", lambda *args, **kwargs: mock_claims)

    mock_jwk = MagicMock()
    mock_jwk.key = "mock_key"
    mock_keys = MagicMock()
    mock_keys.__getitem__.return_value = mock_jwk
    monkeypatch.setattr(adapter.client, "get_jwks", lambda *args, **kwargs: mock_keys)

    with pytest.raises(InvalidNonceError) as exc_info:
        adapter.client.validate_id_token("dummy.jwt.token", nonce="expected_nonce_123")
    assert exc_info.value.status_code == 401
    assert "nonce" in exc_info.value.detail.lower()


# ==============================================================================
# 4. Missing or Invalid PKCE code_verifier -> HTTP 401 Unauthorized
# ==============================================================================

def test_missing_pkce_code_verifier_returns_401():
    """Missing or empty PKCE code_verifier raises InvalidCodeVerifierError (HTTP 401)."""
    adapter = get_auth_adapter()
    with pytest.raises(InvalidCodeVerifierError) as exc_info:
        adapter.client.exchange_code(code="dummy_code", transaction_or_verifier="")
    assert exc_info.value.status_code == 401
    assert "code_verifier" in exc_info.value.detail.lower()


def test_invalid_pkce_code_verifier_against_idp_returns_401():
    """Invalid PKCE code_verifier rejected by IdP raises InvalidCodeVerifierError (HTTP 401)."""
    adapter = get_auth_adapter()
    auth_url, _ = adapter.client.create_authorization_url()
    code, _ = _obtain_auth_code(auth_url, username="pkce_invalid_user")

    # Mismatched 50-char string that does not hash to the code_challenge
    wrong_verifier = "x" * 50
    with pytest.raises(InvalidCodeVerifierError) as exc_info:
        adapter.client.exchange_code(code=code, transaction_or_verifier=wrong_verifier)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_async_invalid_pkce_code_verifier_returns_401():
    """Asynchronous exchange with invalid PKCE code_verifier raises InvalidCodeVerifierError (HTTP 401)."""
    adapter = get_auth_adapter()
    with pytest.raises(InvalidCodeVerifierError) as exc_info:
        await adapter.client.aexchange_code(code="dummy_code", transaction_or_verifier="")
    assert exc_info.value.status_code == 401


# ==============================================================================
# 5. Expired ID Token / Expired Session Cookie -> HTTP 401 Unauthorized
# ==============================================================================

def test_expired_id_token_validation_returns_401(monkeypatch):
    """Expired ID token raises TokenValidationError (HTTP 401)."""
    adapter = get_auth_adapter()
    import jwt as pyjwt

    monkeypatch.setattr("jwt.get_unverified_header", lambda token: {"alg": "RS256", "kid": "mock_kid"})
    mock_jwk = MagicMock()
    mock_jwk.key = "mock_key"
    mock_keys = MagicMock()
    mock_keys.__getitem__.return_value = mock_jwk
    monkeypatch.setattr(adapter.client, "get_jwks", lambda *args, **kwargs: mock_keys)

    def mock_decode(*args, **kwargs):
        raise pyjwt.ExpiredSignatureError("Signature has expired")

    monkeypatch.setattr("jwt.decode", mock_decode)

    with pytest.raises(TokenValidationError) as exc_info:
        adapter.client.validate_id_token("expired.jwt.token")
    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower()


def test_expired_session_cookie_returns_401(client: TestClient):
    """Expired session cookie is rejected with HTTP 401 Unauthorized on admin API."""
    adapter = get_auth_adapter()
    admin_id = Identity(
        subject="admin-exp",
        email="admin@example.com",
        groups=["bdinvite_admins"],
    )
    # Establish session expired 100 seconds ago
    session_id = "expired_sess_test_123"
    past_time = time.time() - 100.0
    record = SessionRecord(
        session_id=session_id,
        identity=admin_id,
        created_at=past_time - 3600,
        expires_at=past_time,
        last_accessed=past_time,
    )
    adapter.sessions[session_id] = record

    client.cookies.set(adapter.session_cookie_name, session_id)
    res = client.get("/birthday/api/admin/rsvps")
    assert res.status_code == 401

    # Session record must be revoked
    assert session_id not in adapter.sessions


def test_expired_session_cookie_on_auth_me_returns_unauthenticated(client: TestClient):
    """Expired session cookie returns unauthenticated status on /birthday/api/auth/me."""
    adapter = get_auth_adapter()
    guest_id = Identity(
        subject="guest-exp",
        email="guest@example.com",
        groups=["guests"],
    )
    session_id = "expired_me_test_123"
    past_time = time.time() - 50.0
    adapter.sessions[session_id] = SessionRecord(
        session_id=session_id,
        identity=guest_id,
        created_at=past_time - 3600,
        expires_at=past_time,
    )

    client.cookies.set(adapter.session_cookie_name, session_id)
    res = client.get("/birthday/api/auth/me")
    assert res.status_code == 200
    data = res.json()
    assert data["authenticated"] is False
    assert data["identity"] is None


# ==============================================================================
# 6. Authenticated Non-Admin User Accessing Admin APIs -> HTTP 403 Forbidden
# ==============================================================================

def test_authenticated_non_admin_returns_403(client: TestClient, guest_session_cookie):
    """Authenticated non-admin user (guest) accessing admin endpoints returns HTTP 403 Forbidden."""
    for k, v in guest_session_cookie.items():
        client.cookies.set(k, v)

    # 1. GET RSVPs
    res1 = client.get("/birthday/api/admin/rsvps")
    assert res1.status_code == 403
    assert "Forbidden" in res1.json()["detail"] or "bdinvite_admins" in res1.json()["detail"]

    # 2. GET Config
    res2 = client.get("/birthday/api/admin/config")
    assert res2.status_code == 403

    # 3. PUT Config
    res3 = client.put("/birthday/api/admin/config", json={"title": "Hacked Title"})
    assert res3.status_code == 403

    # 4. Export CSV
    res4 = client.get("/birthday/api/admin/export")
    assert res4.status_code == 403

    # 5. Map preview trigger
    res5 = client.post("/birthday/api/admin/map-preview/generate", json={"map_url": "https://maps.google.com"})
    assert res5.status_code == 403

    # 6. Delete RSVP
    res6 = client.delete("/birthday/api/admin/rsvps/1")
    assert res6.status_code == 403


# ==============================================================================
# 7. Legacy Remote-User Header Without Valid Session -> HTTP 401 Unauthorized
# ==============================================================================

def test_legacy_remote_user_header_without_session_returns_401(client: TestClient):
    """Negative gate: legacy Remote-User header without valid session returns HTTP 401."""
    # Direct Remote-User spoofing attempt
    res = client.get(
        "/birthday/api/admin/rsvps",
        headers={"Remote-User": "admin@example.com"},
    )
    assert res.status_code == 401

    # Alternative headers spoofing attempts
    res_alt1 = client.get(
        "/birthday/api/admin/config",
        headers={"X-Remote-User": "admin", "X-Forwarded-User": "admin"},
    )
    assert res_alt1.status_code == 401


def test_legacy_remote_user_with_non_admin_session_returns_403(
    client: TestClient, guest_session_cookie
):
    """Remote-User header sent alongside non-admin session is ignored; session governs -> 403."""
    for k, v in guest_session_cookie.items():
        client.cookies.set(k, v)

    res = client.get(
        "/birthday/api/admin/rsvps",
        headers={"Remote-User": "admin@example.com"},
    )
    assert res.status_code == 403


# ==============================================================================
# 8. Deployment Independence: Standalone vs Homelab Production Mode
# ==============================================================================

def test_standalone_mode_configuration():
    """Verify Direct Standalone Mode environment settings and behavior."""
    standalone_settings = Settings(
        SERVICE_DOMAIN="localhost",
        OIDC_ISSUER="http://localhost:8088/default",
        OIDC_REDIRECT_URI="http://localhost:8000/birthday/api/auth/callback",
        SESSION_COOKIE_SECURE=False,
        SESSION_COOKIE_NAME="bdinvite_session",
    )
    assert standalone_settings.SESSION_COOKIE_SECURE is False
    assert standalone_settings.OIDC_ISSUER == "http://localhost:8088/default"

    # Adapter with secure=False should not set Secure flag on cookie
    client = OIDCClient(
        OIDCConfig(
            issuer=standalone_settings.OIDC_ISSUER,
            client_id=standalone_settings.OIDC_CLIENT_ID,
            redirect_uri=standalone_settings.OIDC_REDIRECT_URI,
        )
    )
    adapter = OIDCAuthAdapter(
        client=client,
        cookie_secure=standalone_settings.SESSION_COOKIE_SECURE,
        session_cookie_name=standalone_settings.SESSION_COOKIE_NAME,
    )
    mock_resp = MagicMock()
    adapter.set_session_cookie(mock_resp, "test_sess_123")
    mock_resp.set_cookie.assert_called_once()
    _, kwargs = mock_resp.set_cookie.call_args
    assert kwargs["secure"] is False
    assert kwargs["httponly"] is True


def test_homelab_production_mode_configuration():
    """Verify Homelab Production Mode environment settings and behavior."""
    prod_settings = Settings(
        SERVICE_DOMAIN="demos.roadtotech.me",
        OIDC_ISSUER="https://auth.roadtotech.me",
        OIDC_CLIENT_ID="bdinvite-prod",
        OIDC_CLIENT_SECRET="secure-prod-secret",
        OIDC_REDIRECT_URI="https://demos.roadtotech.me/birthday/api/auth/callback",
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_NAME="bdinvite_session",
        SESSION_COOKIE_SAMESITE="lax",
    )
    assert prod_settings.SESSION_COOKIE_SECURE is True
    assert prod_settings.SERVICE_DOMAIN == "demos.roadtotech.me"
    assert prod_settings.OIDC_ISSUER == "https://auth.roadtotech.me"

    # Adapter with secure=True must set Secure=True and HttpOnly=True
    client = OIDCClient(
        OIDCConfig(
            issuer=prod_settings.OIDC_ISSUER,
            client_id=prod_settings.OIDC_CLIENT_ID,
            client_secret=prod_settings.OIDC_CLIENT_SECRET,
            redirect_uri=prod_settings.OIDC_REDIRECT_URI,
        )
    )
    adapter = OIDCAuthAdapter(
        client=client,
        cookie_secure=prod_settings.SESSION_COOKIE_SECURE,
        session_cookie_name=prod_settings.SESSION_COOKIE_NAME,
    )
    mock_resp = MagicMock()
    adapter.set_session_cookie(mock_resp, "test_prod_sess_456")
    mock_resp.set_cookie.assert_called_once()
    _, kwargs = mock_resp.set_cookie.call_args
    assert kwargs["secure"] is True
    assert kwargs["httponly"] is True
    assert kwargs["samesite"] == "lax"

import base64
import json
import time
import urllib.parse
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.auth import (
    InvalidPKCEError,
    InvalidStateError,
    InvalidTokenError,
    MismatchedNonceError,
    OIDCClient,
    get_auth_adapter,
)
from app.config import Settings
from tests.conftest import login_client

LIVE_ISSUER = "http://localhost:8088/default"
CLIENT_ID = "bdinvite-client"
CLIENT_SECRET = "bdinvite-secret"
REDIRECT_URI = "http://localhost:8000/birthday/api/auth/callback"


@pytest.fixture
def oidc_client() -> OIDCClient:
    return OIDCClient(
        issuer=LIVE_ISSUER,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
    )


# ==============================================================================
# 1. CSRF State Hardening: Forged / Invalid / Expired State returns HTTP 400
# ==============================================================================


def test_forged_or_invalid_csrf_state_returns_400(
    client: TestClient, oidc_client: OIDCClient
):
    """Forged, tampered, missing, or expired CSRF state returns HTTP 400 Bad Request."""
    # 1. Direct unit assertion: oidc_client rejects unknown state with InvalidStateError (400)
    with pytest.raises(InvalidStateError) as exc_info:
        oidc_client.validate_state("forged_attacker_state_token")
    assert exc_info.value.status_code == 400
    assert "Invalid or expired state" in exc_info.value.detail

    with pytest.raises(InvalidStateError) as exc_info_empty:
        oidc_client.validate_state("")
    assert exc_info_empty.value.status_code == 400

    # 2. HTTP callback endpoint with forged state -> 400 Bad Request
    res_forged = client.get(
        "/birthday/api/auth/callback",
        params={"code": "dummy_authorization_code", "state": "forged_csrf_state"},
    )
    assert res_forged.status_code == 400
    assert "state" in res_forged.json().get("detail", "").lower()

    # 3. HTTP callback endpoint with empty state -> 400 Bad Request
    res_empty = client.get(
        "/birthday/api/auth/callback",
        params={"code": "dummy_authorization_code", "state": ""},
    )
    assert res_empty.status_code == 400


def test_replayed_csrf_state_returns_400(oidc_client: OIDCClient):
    """CSRF state token is single-use: replay after successful validation returns HTTP 400."""
    auth_req = oidc_client.create_authorization_url()
    state = auth_req.state

    # First consumption succeeds
    tx = oidc_client.validate_state(state)
    assert tx.state == state

    # Replaying same state fails with HTTP 400
    with pytest.raises(InvalidStateError) as exc_info:
        oidc_client.validate_state(state)
    assert exc_info.value.status_code == 400


# ==============================================================================
# 2. Cryptographic Signature Hardening: Forged / Tampered Token returns HTTP 401
# ==============================================================================


def test_forged_or_tampered_id_token_signature_returns_401(oidc_client: OIDCClient):
    """Forged or tampered ID token signature is rejected cryptographically with HTTP 401 Unauthorized."""
    # Obtain a genuine token response from the live OIDC test fixture
    token_resp, _ = oidc_client.authenticate_with_password(
        username="admin@example.com",
        password="password123",
    )
    valid_id_token = token_resp.id_token
    parts = valid_id_token.split(".")
    assert len(parts) == 3

    # Case A: Corrupted cryptographic signature
    tampered_sig_token = f"{parts[0]}.{parts[1]}.CORRUPTED_SIGNATURE_BYTES"
    with pytest.raises(InvalidTokenError) as exc_info_sig:
        oidc_client.verify_id_token(tampered_sig_token)
    assert exc_info_sig.value.status_code == 401
    assert "signature is invalid or tampered" in str(exc_info_sig.value.detail).lower()

    # Case B: Tampered payload (privilege escalation attempt) with original signature
    payload_bytes = base64.urlsafe_b64decode(parts[1] + "==")
    claims = json.loads(payload_bytes)
    claims["sub"] = "hacked_admin_identity"
    claims["groups"] = ["bdinvite_admins", "root"]
    tampered_payload_b64 = (
        base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    )
    tampered_token = f"{parts[0]}.{tampered_payload_b64}.{parts[2]}"

    with pytest.raises(InvalidTokenError) as exc_info_tampered:
        oidc_client.verify_id_token(tampered_token)
    assert exc_info_tampered.value.status_code == 401

    # Case C: Malformed non-JWT string
    with pytest.raises(InvalidTokenError) as exc_info_malformed:
        oidc_client.verify_id_token("not-a-valid-jwt-token-at-all")
    assert exc_info_malformed.value.status_code == 401


# ==============================================================================
# 3. Nonce Verification & Replay Protection: Mismatched Nonce returns HTTP 401
# ==============================================================================


def test_mismatched_or_replayed_nonce_returns_401(oidc_client: OIDCClient):
    """Mismatched or missing nonce in ID token returns HTTP 401 Unauthorized."""
    auth_req = oidc_client.create_authorization_url()

    with httpx.Client() as http:
        resp = http.post(
            auth_req.url,
            data={"username": "guest@example.com"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        redirect_url = resp.headers["location"]

    code = urllib.parse.parse_qs(urllib.parse.urlparse(redirect_url).query)["code"][0]
    token_resp = oidc_client.exchange_code(code=code, state=auth_req.state)
    token = token_resp.id_token

    # Case A: Valid token verified against a mismatched expected nonce -> 401
    with pytest.raises(MismatchedNonceError) as exc_info:
        oidc_client.verify_id_token(token, nonce="forged_or_replayed_nonce_999")
    assert exc_info.value.status_code == 401
    assert "does not match expected nonce" in str(exc_info.value.detail).lower()

    # Case B: Correct nonce succeeds
    verified = oidc_client.verify_id_token(token, nonce=auth_req.nonce)
    assert verified["nonce"] == auth_req.nonce


# ==============================================================================
# 4. PKCE Verification: Missing or Invalid code_verifier returns HTTP 401
# ==============================================================================


def test_missing_or_invalid_pkce_code_verifier_returns_401(oidc_client: OIDCClient):
    """Missing, out-of-range, or invalid PKCE code_verifier returns HTTP 401 Unauthorized."""
    # Case A: Missing code_verifier when state is None -> 401
    with pytest.raises(InvalidPKCEError) as exc_missing:
        oidc_client.exchange_code(code="test_code", code_verifier=None)
    assert exc_missing.value.status_code == 401

    # Case B: Empty code_verifier -> 401
    with pytest.raises(InvalidPKCEError) as exc_empty:
        oidc_client.exchange_code(code="test_code", code_verifier="   ")
    assert exc_empty.value.status_code == 401

    # Case C: code_verifier too short (< 43 characters per RFC 7636) -> 401
    with pytest.raises(InvalidPKCEError) as exc_short:
        oidc_client.exchange_code(code="test_code", code_verifier="short_verifier_123")
    assert exc_short.value.status_code == 401

    # Case D: code_verifier too long (> 128 characters) -> 401
    with pytest.raises(InvalidPKCEError) as exc_long:
        oidc_client.exchange_code(code="test_code", code_verifier="a" * 129)
    assert exc_long.value.status_code == 401

    # Case E: code_verifier with invalid characters (non-unreserved) -> 401
    with pytest.raises(InvalidPKCEError) as exc_invalid_chars:
        oidc_client.exchange_code(
            code="test_code",
            code_verifier="valid_length_verifier_with_illegal_characters_$$$$$!@@@#%^&*()",
        )
    assert exc_invalid_chars.value.status_code == 401

    # Case F: Integration with mock OIDC server: valid code exchanged with mismatched code_verifier -> 401
    auth_req = oidc_client.create_authorization_url()
    with httpx.Client() as http:
        resp = http.post(
            auth_req.url,
            data={"username": "guest@example.com"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        code = urllib.parse.parse_qs(
            urllib.parse.urlparse(resp.headers["location"]).query
        )["code"][0]

    with pytest.raises(InvalidPKCEError) as exc_mismatch:
        oidc_client.exchange_code(
            code=code,
            code_verifier="mismatched_code_verifier_that_does_not_hash_to_the_challenge_123456",
            nonce=auth_req.nonce,
        )
    assert exc_mismatch.value.status_code == 401
    assert "pkce verification failed" in str(exc_mismatch.value.detail).lower()


# ==============================================================================
# 5. Token & Session Expiration: Expired ID Token / Cookie returns HTTP 401
# ==============================================================================


def test_expired_id_token_returns_401(
    oidc_client: OIDCClient, monkeypatch: pytest.MonkeyPatch
):
    """Expired ID token is rejected with HTTP 401 Unauthorized."""
    import datetime

    import jwt.api_jwt

    # Obtain a genuine token to get signing key and claims structure
    token_resp, _ = oidc_client.authenticate_with_password(
        username="guest@example.com",
        password="password123",
    )

    # Valid token verified with current time passes
    verified = oidc_client.verify_id_token(token_resp.id_token)
    assert verified["sub"] == "guest-001"

    # Fast forward time into the future past token exp claim
    class FutureDateTime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.datetime(2099, 1, 1, tzinfo=tz)

    monkeypatch.setattr(jwt.api_jwt, "datetime", FutureDateTime)
    with pytest.raises(InvalidTokenError) as exc_info:
        oidc_client.verify_id_token(token_resp.id_token)
    assert exc_info.value.status_code == 401
    assert "expired" in str(exc_info.value.detail).lower()


def test_expired_session_cookie_returns_401(client: TestClient):
    """Expired session cookie returns HTTP 401 Unauthorized across all protected endpoints."""
    login_client(client, email="admin@example.com", groups=["bdinvite_admins"])
    adapter = get_auth_adapter()

    # Manually expire the session in the session store
    cookie_val = client.cookies.get(adapter.session_cookie_name)
    assert cookie_val is not None
    session_id = adapter.parse_session_cookie(cookie_val)
    assert session_id is not None

    session = adapter.session_store.get_session(session_id)
    assert session is not None
    session.created_at = time.time() - 99999  # Far in the past
    session.expires_at = time.time() - 100.0  # Expired

    # Request with expired session returns HTTP 401
    res_me = client.get("/birthday/api/auth/me")
    assert res_me.status_code == 401
    assert res_me.json() == {"detail": "Not authenticated"}

    res_admin = client.get("/birthday/api/admin/rsvps")
    assert res_admin.status_code == 401
    assert res_admin.json() == {"detail": "Not authenticated"}

    res_config = client.get("/birthday/api/admin/config")
    assert res_config.status_code == 401
    assert res_config.json() == {"detail": "Not authenticated"}


def test_tampered_session_cookie_signature_returns_401(client: TestClient):
    """Session cookie with tampered cryptographic signature returns HTTP 401 Unauthorized."""
    login_client(client, email="admin@example.com", groups=["bdinvite_admins"])
    adapter = get_auth_adapter()
    valid_cookie = client.cookies.get(adapter.session_cookie_name)
    assert valid_cookie is not None

    # Tamper cookie signature
    tampered_cookie = valid_cookie[:-6] + "BADSIG"
    client.cookies.set(adapter.session_cookie_name, tampered_cookie)

    res = client.get("/birthday/api/auth/me")
    assert res.status_code == 401

    res_admin = client.get("/birthday/api/admin/rsvps")
    assert res_admin.status_code == 401


# ==============================================================================
# 6. Authorization Barrier: Authenticated Non-Admin returns HTTP 403 Forbidden
# ==============================================================================


def test_authenticated_non_admin_accessing_admin_apis_returns_403(
    guest_client: TestClient,
):
    """Authenticated non-admin user (guest@example.com with groups: ['guests']) receives HTTP 403."""
    admin_endpoints = [
        ("GET", "/birthday/api/admin/rsvps"),
        ("DELETE", "/birthday/api/admin/rsvps/1"),
        ("PATCH", "/birthday/api/admin/rsvps/1"),
        ("GET", "/birthday/api/admin/export"),
        ("GET", "/birthday/api/admin/config"),
        ("PUT", "/birthday/api/admin/config"),
        ("PATCH", "/birthday/api/admin/config"),
        ("POST", "/birthday/api/admin/map-preview/generate"),
    ]
    for method, path in admin_endpoints:
        res = guest_client.request(method, path)
        assert res.status_code == 403, (
            f"{method} {path} must return 403 Forbidden for non-admin"
        )
        assert "Forbidden" in res.json().get("detail", "")


# ==============================================================================
# 7. Legacy Remote-User Header Barrier: Returns HTTP 401 Unauthorized
# ==============================================================================


def test_legacy_remote_user_header_without_session_returns_401(client: TestClient):
    """Legacy Remote-User header without an active authenticated session returns HTTP 401."""
    headers_to_test = [
        {"Remote-User": "admin@example.com"},
        {"Remote-User": "admin", "X-Remote-User": "admin"},
        {"remote-user": "admin@example.com"},
        {"REMOTE_USER": "admin@example.com"},
    ]

    for headers in headers_to_test:
        res_rsvps = client.get("/birthday/api/admin/rsvps", headers=headers)
        assert res_rsvps.status_code == 401
        assert res_rsvps.json() == {"detail": "Not authenticated"}

        res_config = client.get("/birthday/api/admin/config", headers=headers)
        assert res_config.status_code == 401

        res_me = client.get("/birthday/api/auth/me", headers=headers)
        assert res_me.status_code == 401


def test_legacy_remote_user_header_cannot_escalate_non_admin_session(
    guest_client: TestClient,
):
    """An attacker passing Remote-User: admin with an active non-admin session cookie receives HTTP 403."""
    res = guest_client.get(
        "/birthday/api/admin/rsvps",
        headers={
            "Remote-User": "admin@example.com",
            "X-Remote-User": "admin",
            "X-User-Groups": "bdinvite_admins",
        },
    )
    assert res.status_code == 403
    assert "Forbidden" in res.json().get("detail", "")


# ==============================================================================
# 8. Deployment Independence: Direct Standalone vs Homelab Production Mode
# ==============================================================================


def test_deployment_independence_multi_mode_configuration():
    """Verify application configuration correctly handles Direct Standalone and Homelab Production modes."""
    # 1. Direct Standalone Mode (local development / testing)
    dev_settings = Settings(
        OIDC_ISSUER="http://localhost:8088/default",
        OIDC_CLIENT_ID="bdinvite-client",
        OIDC_CLIENT_SECRET="bdinvite-secret",
        OIDC_REDIRECT_URI="http://localhost:8000/birthday/api/auth/callback",
        SESSION_COOKIE_SECURE=False,
        SESSION_COOKIE_NAME="bdinvite_session",
    )
    assert dev_settings.is_standalone is True
    assert dev_settings.is_production is False
    assert dev_settings.SESSION_COOKIE_SECURE is False

    # 2. Homelab Production Mode (behind Traefik TLS proxy with Authelia)
    prod_settings = Settings(
        SERVICE_DOMAIN="demos.roadtotech.me",
        OIDC_ISSUER="https://auth.roadtotech.me",
        OIDC_CLIENT_ID="bdinvite-client",
        OIDC_CLIENT_SECRET="production-secure-secret-key",
        OIDC_REDIRECT_URI="https://demos.roadtotech.me/birthday/api/auth/callback",
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_NAME="bdinvite_session",
    )
    assert prod_settings.is_standalone is False
    assert prod_settings.is_production is True
    assert prod_settings.SESSION_COOKIE_SECURE is True
    assert prod_settings.OIDC_ISSUER == "https://auth.roadtotech.me"
    assert (
        prod_settings.OIDC_REDIRECT_URI
        == "https://demos.roadtotech.me/birthday/api/auth/callback"
    )


# ==============================================================================
# 9. Static Architectural Assertion: Zero Runtime Occurrences of Remote-User
# ==============================================================================


def test_static_architectural_assertion_no_runtime_remote_user():
    """Verify that neither backend/app/ nor frontend/src/ contains runtime references to Remote-User."""
    root_dir = Path(__file__).resolve().parent.parent.parent
    backend_app_dir = root_dir / "backend" / "app"
    frontend_src_dir = root_dir / "frontend" / "src"

    assert backend_app_dir.is_dir()
    assert frontend_src_dir.is_dir()

    # Disallowed patterns in runtime source files
    disallowed = ["remote-user", "remote_user"]

    violations: list[str] = []

    # Check backend runtime source files
    for py_file in backend_app_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8").lower()
        for term in disallowed:
            if term in content:
                violations.append(f"{py_file}: contains '{term}'")

    # Check frontend runtime source files
    for src_file in frontend_src_dir.rglob("*"):
        if src_file.suffix in [".ts", ".tsx", ".js", ".jsx"]:
            content = src_file.read_text(encoding="utf-8").lower()
            for term in disallowed:
                if term in content:
                    violations.append(f"{src_file}: contains '{term}'")

    assert not violations, (
        "Architectural boundary violated by runtime Remote-User occurrences:\n"
        + "\n".join(violations)
    )

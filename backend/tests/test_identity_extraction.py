from dataclasses import FrozenInstanceError
from typing import Optional

from fastapi import Request, Response
from fastapi.responses import RedirectResponse
import httpx
import pytest

from app.auth import (
    AuthPort,
    Identity,
    InvalidTokenError,
    OIDCAuthAdapter,
    OIDCClient,
    OIDCConfig,
    TokenExchangeError,
)

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
        groups_claim="groups",
    )


def create_dummy_request(
    headers: Optional[dict[str, str]] = None,
    cookies: Optional[dict[str, str]] = None,
) -> Request:
    raw_headers = [
        (k.lower().encode("latin-1"), v.encode("latin-1"))
        for k, v in (headers or {}).items()
    ]
    if cookies:
        cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())
        raw_headers.append((b"cookie", cookie_header.encode("latin-1")))

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/birthday/api/admin/rsvps",
        "headers": raw_headers,
    }
    return Request(scope)


# ==============================================================================
# 1. Identity Resolution & Mapping Unit Tests
# ==============================================================================


def test_identity_resolution_standard_claims(oidc_client: OIDCClient):
    """Standard identity claims (sub, email, name, groups) map correctly to Identity domain model."""
    claims = {
        "sub": "user-42",
        "email": "user42@example.com",
        "name": "Douglas Adams",
        "groups": ["author", "scifi"],
    }
    identity = oidc_client.extract_identity(claims)

    assert isinstance(identity, Identity)
    assert identity.subject == "user-42"
    assert identity.email == "user42@example.com"
    assert identity.name == "Douglas Adams"
    assert identity.groups == ["author", "scifi"]
    assert identity.has_group("author") is True
    assert identity.has_group("nonexistent") is False


def test_identity_resolution_missing_email_and_name_defaults(oidc_client: OIDCClient):
    """Missing email falls back to synthetic local address, and missing name defaults to None."""
    claims = {
        "sub": "svc-worker-99",
    }
    identity = oidc_client.extract_identity(claims)

    assert identity.subject == "svc-worker-99"
    assert identity.email == f"svc-worker-99@{CLIENT_ID}.local"
    assert identity.name is None
    assert identity.groups == []


def test_identity_resolution_missing_subject_raises_invalid_token(oidc_client: OIDCClient):
    """Missing or empty sub claim raises InvalidTokenError."""
    with pytest.raises(InvalidTokenError, match="missing required 'sub' claim"):
        oidc_client.extract_identity({})

    with pytest.raises(InvalidTokenError, match="missing required 'sub' claim"):
        oidc_client.extract_identity({"sub": "   ", "email": "valid@example.com"})


def test_identity_groups_extraction_clean_defaults(oidc_client: OIDCClient):
    """Missing, None, non-list, or empty groups claim cleanly defaults to empty list."""
    # Missing groups key
    assert oidc_client.extract_identity({"sub": "u1"}).groups == []

    # None value
    assert oidc_client.extract_identity({"sub": "u1", "groups": None}).groups == []

    # Empty list
    assert oidc_client.extract_identity({"sub": "u1", "groups": []}).groups == []

    # Single string group
    assert oidc_client.extract_identity({"sub": "u1", "groups": "single_role"}).groups == ["single_role"]

    # Tuple / Set collections
    assert oidc_client.extract_identity({"sub": "u1", "groups": ("admin", "editor")}).groups == ["admin", "editor"]

    # Discard non-string, empty strings, and trim whitespace
    claims = {"sub": "u1", "groups": ["  admin  ", "", "  ", 123, None, "editor"]}
    assert oidc_client.extract_identity(claims).groups == ["admin", "editor"]

    # Deduplicate while preserving order
    claims_dup = {"sub": "u1", "groups": ["alpha", "beta", "alpha", "gamma", "beta"]}
    assert oidc_client.extract_identity(claims_dup).groups == ["alpha", "beta", "gamma"]


def test_identity_groups_configurable_claim_path():
    """Group extraction respects configured group claim path, including nested paths."""
    # Custom top-level path
    custom_client = OIDCClient(
        issuer=LIVE_ISSUER,
        client_id=CLIENT_ID,
        groups_claim="roles",
    )
    claims = {"sub": "u1", "roles": ["superadmin", "operator"], "groups": ["ignored"]}
    assert custom_client.extract_identity(claims).groups == ["superadmin", "operator"]

    # Nested path (e.g. Keycloak realm_access.roles)
    nested_client = OIDCClient(
        issuer=LIVE_ISSUER,
        client_id=CLIENT_ID,
        groups_claim="realm_access.roles",
    )
    claims_nested = {
        "sub": "u1",
        "realm_access": {"roles": ["app_admin", "user"]},
    }
    assert nested_client.extract_identity(claims_nested).groups == ["app_admin", "user"]

    # Nested path missing
    assert nested_client.extract_identity({"sub": "u1", "realm_access": {}}).groups == []
    assert nested_client.extract_identity({"sub": "u1"}).groups == []


# ==============================================================================
# 2. Seeded Fixture Users Verification (Live Integration)
# ==============================================================================


def test_live_fixture_admin_user_authentication(oidc_client: OIDCClient):
    """Authenticating with admin@example.com resolves to Identity with bdinvite_admins group."""
    token_resp, identity = oidc_client.authenticate_with_password(
        username="admin@example.com",
        password="password123",
        scopes=["openid", "profile", "email"],
    )

    assert isinstance(identity, Identity)
    assert identity.subject == "admin-001"
    assert identity.email == "admin@example.com"
    assert identity.name == "Admin User"
    assert identity.groups == ["bdinvite_admins"]
    assert identity.has_group("bdinvite_admins") is True
    assert identity.has_group("guests") is False

    # Verify ID token claims match domain model
    assert token_resp.claims["sub"] == "admin-001"
    assert token_resp.claims["email"] == "admin@example.com"
    assert token_resp.claims["groups"] == ["bdinvite_admins"]


def test_live_fixture_guest_user_authentication(oidc_client: OIDCClient):
    """Authenticating with guest@example.com resolves to Identity with guests group."""
    token_resp, identity = oidc_client.authenticate_with_password(
        username="guest@example.com",
        password="password123",
        scopes=["openid", "profile", "email"],
    )

    assert isinstance(identity, Identity)
    assert identity.subject == "guest-001"
    assert identity.email == "guest@example.com"
    assert identity.name == "Guest User"
    assert identity.groups == ["guests"]
    assert identity.has_group("guests") is True
    assert identity.has_group("bdinvite_admins") is False

    # Verify ID token claims match domain model
    assert token_resp.claims["sub"] == "guest-001"
    assert token_resp.claims["email"] == "guest@example.com"
    assert token_resp.claims["groups"] == ["guests"]


# ==============================================================================
# 3. Identity Origin Integrity & Immutability Tests
# ==============================================================================


def test_identity_origin_integrity_rejection_of_unvalidated_request_headers(oidc_client: OIDCClient):
    """Application adapter rejects constructing Identity from raw request headers or client data."""
    adapter = OIDCAuthAdapter(oidc_client=oidc_client)

    # Attacker passes spoofed Remote-User or X-User headers
    spoofed_request = create_dummy_request(
        headers={
            "Remote-User": "admin@example.com",
            "Remote-Groups": "bdinvite_admins",
            "X-Forwarded-User": "admin-001",
        }
    )

    # Adapter must strictly refuse to manufacture an Identity from unvalidated request headers
    resolved = adapter.current_identity(spoofed_request)
    assert resolved is None


def test_identity_origin_integrity_rejection_of_tampered_token(oidc_client: OIDCClient):
    """Identity cannot be extracted from a tampered or forged token."""
    # Obtain a genuine token for admin
    token_resp, _ = oidc_client.authenticate_with_password(
        username="admin@example.com",
        password="password123",
    )
    valid_id_token = token_resp.id_token

    # Case 1: Tampered signature
    tampered_sig_token = valid_id_token[:-10] + "FORGED_SIG"
    with pytest.raises(InvalidTokenError):
        oidc_client.extract_identity_from_token(tampered_sig_token)

    # Case 2: Adapter with tampered token in Authorization header returns None
    bad_request = create_dummy_request(headers={"Authorization": f"Bearer {tampered_sig_token}"})
    adapter = OIDCAuthAdapter(oidc_client=oidc_client)
    assert adapter.current_identity(bad_request) is None


def test_identity_immutability():
    """Identity instance is frozen and cannot be mutated after creation."""
    identity = Identity(
        subject="admin-001",
        email="admin@example.com",
        name="Admin User",
        groups=["bdinvite_admins"],
    )

    with pytest.raises(FrozenInstanceError):
        identity.groups = ["guests"]  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        identity.subject = "hacked-sub"  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        identity.email = "hacked@example.com"  # type: ignore[misc]


# ==============================================================================
# 4. AuthPort Protocol Conformance & Adapter Tests
# ==============================================================================


def test_oidc_auth_adapter_conforms_to_auth_port(oidc_client: OIDCClient):
    """OIDCAuthAdapter satisfies the AuthPort protocol runtime contract."""
    adapter = OIDCAuthAdapter(oidc_client=oidc_client)
    assert isinstance(adapter, AuthPort)


def test_oidc_auth_adapter_current_identity_with_valid_bearer(oidc_client: OIDCClient):
    """OIDCAuthAdapter extracts valid Identity from Authorization: Bearer token."""
    token_resp, expected_identity = oidc_client.authenticate_with_password(
        username="admin@example.com",
        password="password123",
    )

    adapter = OIDCAuthAdapter(oidc_client=oidc_client)
    req = create_dummy_request(headers={"Authorization": f"Bearer {token_resp.id_token}"})

    resolved = adapter.current_identity(req)
    assert resolved == expected_identity
    assert resolved is not None
    assert resolved.subject == "admin-001"
    assert resolved.has_group("bdinvite_admins") is True


def test_oidc_auth_adapter_current_identity_with_valid_cookie(oidc_client: OIDCClient):
    """OIDCAuthAdapter extracts valid Identity from session cookie."""
    token_resp, expected_identity = oidc_client.authenticate_with_password(
        username="guest@example.com",
        password="password123",
    )

    adapter = OIDCAuthAdapter(oidc_client=oidc_client, session_cookie_name="bdinvite_session")
    req = create_dummy_request(cookies={"bdinvite_session": token_resp.id_token})

    resolved = adapter.current_identity(req)
    assert resolved == expected_identity
    assert resolved is not None
    assert resolved.subject == "guest-001"
    assert resolved.has_group("guests") is True


def test_oidc_auth_adapter_login_redirect(oidc_client: OIDCClient):
    """OIDCAuthAdapter login returns 302 redirect to OIDC authorization endpoint."""
    adapter = OIDCAuthAdapter(oidc_client=oidc_client)
    req = create_dummy_request()

    response = adapter.login(req)
    assert isinstance(response, Response)
    assert response.status_code == 302
    assert "location" in response.headers
    assert response.headers["location"].startswith(f"{LIVE_ISSUER}/authorize?")


def test_oidc_auth_adapter_logout_redirect_and_clears_cookie(oidc_client: OIDCClient):
    """OIDCAuthAdapter logout returns 302 redirect and deletes the session cookie."""
    adapter = OIDCAuthAdapter(oidc_client=oidc_client, session_cookie_name="bdinvite_session")
    req = create_dummy_request()

    response = adapter.logout(req)
    assert isinstance(response, Response)
    assert response.status_code == 302
    # Verify cookie deletion header exists
    assert "set-cookie" in response.headers
    assert "bdinvite_session" in response.headers["set-cookie"]

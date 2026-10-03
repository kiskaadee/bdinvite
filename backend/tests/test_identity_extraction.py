"""Tests for OIDC Identity & Group Extraction, Integrity Invariants, and Fixture Users."""

from dataclasses import FrozenInstanceError
import json
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from starlette.requests import Request

from app.auth import (
    Identity,
    OIDCAuthAdapter,
    OIDCClient,
    OIDCConfig,
    TokenValidationError,
    claims_to_identity,
    extract_identity_from_claims,
    resolve_claim_path,
)

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
        "path": "/birthday/api/admin/rsvps",
        "headers": header_list,
        "query_string": b"",
    }
    return Request(scope)


def obtain_auth_code_from_fixture(
    authorization_url: str,
    username: str,
    claims: dict | None = None,
) -> tuple[str, str]:
    parsed_url = urlparse(authorization_url)
    auth_endpoint = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
    query_params = parse_qs(parsed_url.query)

    flat_params = {k: v[0] for k, v in query_params.items()}
    post_data: dict[str, str] = {"username": username}
    if claims:
        post_data["claims"] = json.dumps(claims)

    with httpx.Client() as client:
        resp = client.post(
            auth_endpoint,
            params=flat_params,
            data=post_data,
            follow_redirects=False,
        )
        assert resp.status_code == 302
        location = resp.headers["location"]

    redirect_parsed = urlparse(location)
    callback_params = parse_qs(redirect_parsed.query)
    return callback_params["code"][0], callback_params["state"][0]


# ============================================================================
# 1. Identity Resolution & Mapping Unit Tests
# ============================================================================


def test_resolve_claim_path():
    claims = {
        "groups": ["group1", "group2"],
        "realm_access": {"roles": ["admin", "editor"]},
        "deep": {"nested": {"path": ["value"]}},
    }
    assert resolve_claim_path(claims, "groups") == ["group1", "group2"]
    assert resolve_claim_path(claims, "realm_access.roles") == ["admin", "editor"]
    assert resolve_claim_path(claims, "deep.nested.path") == ["value"]
    assert resolve_claim_path(claims, "nonexistent") is None
    assert resolve_claim_path(claims, "deep.wrong.path") is None


def test_claims_to_identity_standard_mapping():
    claims = {
        "sub": "user_101",
        "email": "user@example.com",
        "name": "Normal User",
        "groups": ["engineering", "security"],
    }
    identity = claims_to_identity(claims)
    assert isinstance(identity, Identity)
    assert identity.subject == "user_101"
    assert identity.email == "user@example.com"
    assert identity.name == "Normal User"
    assert identity.groups == ["engineering", "security"]


def test_claims_to_identity_custom_group_claim_path():
    claims = {
        "sub": "user_custom",
        "email": "custom@example.com",
        "roles": ["operator", "auditor"],
    }
    identity = extract_identity_from_claims(claims, groups_claim="roles")
    assert identity.groups == ["operator", "auditor"]

    # Nested path
    nested_claims = {
        "sub": "user_nested",
        "email": "nested@example.com",
        "resource_access": {"bdinvite": {"roles": ["admin"]}},
    }
    identity_nested = extract_identity_from_claims(
        nested_claims, groups_claim="resource_access.bdinvite.roles"
    )
    assert identity_nested.groups == ["admin"]


def test_claims_to_identity_normalizes_group_types():
    # Single string group
    c1 = {"sub": "u1", "email": "u1@e.com", "groups": "only_one_group"}
    assert claims_to_identity(c1).groups == ["only_one_group"]

    # Comma-separated string
    c2 = {"sub": "u2", "email": "u2@e.com", "groups": "admin, billing, support"}
    assert claims_to_identity(c2).groups == ["admin", "billing", "support"]

    # Non-string elements in list are stringified
    c3 = {"sub": "u3", "email": "u3@e.com", "groups": [123, True, "staff"]}
    assert claims_to_identity(c3).groups == ["123", "True", "staff"]


def test_claims_to_identity_missing_or_empty_groups_defaults_to_empty_list():
    # Absent groups claim
    c1 = {"sub": "u1", "email": "u1@e.com", "name": "No Groups"}
    id1 = claims_to_identity(c1)
    assert id1.groups == []

    # groups is None
    c2 = {"sub": "u2", "email": "u2@e.com", "groups": None}
    id2 = claims_to_identity(c2)
    assert id2.groups == []

    # groups is empty list
    c3 = {"sub": "u3", "email": "u3@e.com", "groups": []}
    id3 = claims_to_identity(c3)
    assert id3.groups == []

    # groups is empty string
    c4 = {"sub": "u4", "email": "u4@e.com", "groups": "   "}
    id4 = claims_to_identity(c4)
    assert id4.groups == []


def test_claims_to_identity_requires_sub():
    with pytest.raises(TokenValidationError) as exc_info:
        claims_to_identity({"email": "nosub@example.com"})
    assert "sub" in str(exc_info.value.detail).lower()

    with pytest.raises(TokenValidationError) as exc_info:
        claims_to_identity({"sub": "   ", "email": "blanksub@example.com"})
    assert "sub" in str(exc_info.value.detail).lower()


def test_claims_to_identity_email_and_name_fallbacks():
    # Fallback to preferred_username
    c1 = {"sub": "usr_abc", "preferred_username": "preferred@example.com"}
    id1 = claims_to_identity(c1)
    assert id1.email == "preferred@example.com"
    assert id1.name is None

    # Fallback to sub@local
    c2 = {"sub": "usr_xyz"}
    id2 = claims_to_identity(c2)
    assert id2.email == "usr_xyz@local"
    assert id2.name is None


# ============================================================================
# 2. Verification Against Seeded Fixture Users
# ============================================================================


def test_fixture_admin_user_password_grant(oidc_client: OIDCClient):
    """Verify authenticating admin@example.com resolves to Identity with bdinvite_admins group."""
    identity, tokens = oidc_client.authenticate_user(
        username="admin@example.com",
        password="password123",
    )
    assert isinstance(identity, Identity)
    assert identity.subject == "admin-001"
    assert identity.email == "admin@example.com"
    assert identity.name == "Admin User"
    assert identity.groups == ["bdinvite_admins"]
    assert "access_token" in tokens
    assert "id_token" in tokens


def test_fixture_guest_user_password_grant(oidc_client: OIDCClient):
    """Verify authenticating guest@example.com resolves to Identity with guests group."""
    identity, tokens = oidc_client.authenticate_user(
        username="guest@example.com",
        password="password123",
    )
    assert isinstance(identity, Identity)
    assert identity.subject == "guest-001"
    assert identity.email == "guest@example.com"
    assert identity.name == "Guest User"
    assert identity.groups == ["guests"]
    assert "access_token" in tokens
    assert "id_token" in tokens


@pytest.mark.asyncio
async def test_async_fixture_admin_and_guest_user(oidc_client: OIDCClient):
    admin_id, _ = await oidc_client.aauthenticate_user("admin@example.com", "password123")
    assert admin_id.subject == "admin-001"
    assert admin_id.groups == ["bdinvite_admins"]

    guest_id, _ = await oidc_client.aauthenticate_user("guest@example.com", "password123")
    assert guest_id.subject == "guest-001"
    assert guest_id.groups == ["guests"]


def test_fixture_admin_authorization_code_flow(oidc_client: OIDCClient):
    """Verify complete authorization code flow with admin fixture user."""
    auth_url, tx = oidc_client.create_authorization_url()
    code, returned_state = obtain_auth_code_from_fixture(auth_url, username="admin@example.com")

    identity, tokens = oidc_client.process_callback(
        code=code,
        state=returned_state,
        extra_params={"username": "admin@example.com"},
    )
    assert identity.subject == "admin-001"
    assert identity.email == "admin@example.com"
    assert identity.name == "Admin User"
    assert identity.groups == ["bdinvite_admins"]


def test_fixture_guest_authorization_code_flow(oidc_client: OIDCClient):
    """Verify complete authorization code flow with guest fixture user."""
    auth_url, tx = oidc_client.create_authorization_url()
    code, returned_state = obtain_auth_code_from_fixture(auth_url, username="guest@example.com")

    identity, tokens = oidc_client.process_callback(
        code=code,
        state=returned_state,
        extra_params={"username": "guest@example.com"},
    )
    assert identity.subject == "guest-001"
    assert identity.email == "guest@example.com"
    assert identity.name == "Guest User"
    assert identity.groups == ["guests"]


# ============================================================================
# 3. Identity Origin Integrity (Authoritative Provenance) Tests
# ============================================================================


def test_identity_origin_integrity_rejects_unvalidated_request_headers(
    oidc_client: OIDCClient,
):
    """Verify that unvalidated request headers (e.g. X-User, X-Email, X-Groups)

    CANNOT forge or inject an Identity. Application code must only trust
    cryptographically verified authentication artifacts.
    """
    adapter = OIDCAuthAdapter(client=oidc_client)

    # 1. Attacker attempts to spoof admin identity via custom headers
    spoof_req = create_request(
        headers={
            "X-User": "admin-001",
            "X-User-Email": "admin@example.com",
            "X-User-Name": "Admin User",
            "X-Groups": "bdinvite_admins",
            "X-Remote-User": "admin@example.com",
            "X-Forwarded-User": "admin-001",
        }
    )
    resolved = adapter.current_identity(spoof_req)
    assert resolved is None, "Adapter must NEVER construct an Identity from raw unvalidated headers"

    # 2. Attacker attempts to forge session cookie with fake ID
    fake_session_req = create_request(cookies={"session_id": "forged_random_session_key"})
    assert adapter.current_identity(fake_session_req) is None

    # 3. Legitimate session established through verified callback succeeds
    legit_identity = Identity(
        subject="admin-001",
        email="admin@example.com",
        name="Admin User",
        groups=["bdinvite_admins"],
    )
    session_id = adapter.establish_session(legit_identity)

    valid_session_req = create_request(cookies={"session_id": session_id})
    assert adapter.current_identity(valid_session_req) == legit_identity


def test_identity_origin_integrity_bearer_token_validation(oidc_client: OIDCClient):
    """Verify Bearer token in Authorization header is strictly cryptographically validated."""
    adapter = OIDCAuthAdapter(client=oidc_client)

    # 1. Genuine token from fixture user
    _, tokens = oidc_client.authenticate_user("admin@example.com", "password123")
    valid_id_token = tokens["id_token"]

    req_with_valid_bearer = create_request(
        headers={"Authorization": f"Bearer {valid_id_token}"}
    )
    resolved = adapter.current_identity(req_with_valid_bearer)
    assert resolved is not None
    assert resolved.subject == "admin-001"
    assert resolved.email == "admin@example.com"
    assert resolved.groups == ["bdinvite_admins"]

    # 2. Tampered token signature fails verification and yields None
    parts = valid_id_token.split(".")
    tampered_sig = ("X" if parts[2][0] != "X" else "Y") + parts[2][1:]
    tampered_token = f"{parts[0]}.{parts[1]}.{tampered_sig}"

    req_with_tampered_bearer = create_request(
        headers={"Authorization": f"Bearer {tampered_token}"}
    )
    assert adapter.current_identity(req_with_tampered_bearer) is None

    # 3. Forged payload with valid signature prefix fails verification
    req_garbage = create_request(headers={"Authorization": "Bearer not.a.valid.jwt"})
    assert adapter.current_identity(req_garbage) is None


# ============================================================================
# 4. Identity Immutability Tests
# ============================================================================


def test_identity_frozen_immutability():
    """Verify that domain Identity instances cannot be mutated at runtime."""
    identity = Identity(
        subject="admin-001",
        email="admin@example.com",
        name="Admin User",
        groups=["bdinvite_admins"],
    )

    with pytest.raises(FrozenInstanceError):
        identity.subject = "hacker"  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        identity.email = "hacker@example.com"  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        identity.name = "Hacker"  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        identity.groups = ["superusers"]  # type: ignore[misc]

"""Tests for FastAPI dependency injection and authorization policies (Checkpoint 5)."""

from collections.abc import Generator
from typing import Annotated, Optional

import pytest
from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.auth import (
    AdminUserDep,
    AuthenticatedUserDep,
    CurrentIdentityDep,
    Identity,
    OIDCAuthAdapter,
    OIDCClient,
    OIDCConfig,
    get_auth_adapter,
    get_current_identity,
    require_admin,
    require_authenticated,
    require_group,
    set_auth_adapter,
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
        "path": "/test",
        "headers": header_list,
        "query_string": b"",
    }
    return Request(scope)


@pytest.fixture
def test_app(auth_adapter: OIDCAuthAdapter) -> FastAPI:
    """Isolated FastAPI test application mounted with test endpoints."""
    app = FastAPI(title="Dependency Test App")
    router = APIRouter()

    @router.get("/me")
    def me_endpoint(identity: CurrentIdentityDep):
        if identity is None:
            return {"authenticated": False, "identity": None}
        return {
            "authenticated": True,
            "identity": {
                "subject": identity.subject,
                "email": identity.email,
                "name": identity.name,
                "groups": identity.groups,
            },
        }

    @router.get("/authenticated")
    def authenticated_endpoint(user: AuthenticatedUserDep):
        return {
            "subject": user.subject,
            "email": user.email,
            "groups": user.groups,
        }

    @router.get("/admin")
    def admin_endpoint(admin: AdminUserDep):
        return {
            "subject": admin.subject,
            "email": admin.email,
            "groups": admin.groups,
        }

    require_staff = require_group("staff")

    @router.get("/staff")
    def staff_endpoint(user: Annotated[Identity, Depends(require_staff)]):
        return {
            "subject": user.subject,
            "email": user.email,
            "groups": user.groups,
        }

    app.include_router(router)
    return app


@pytest.fixture
def client(test_app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(test_app) as c:
        yield c


# ============================================================================
# Unit Tests (Direct Dependency Invocations)
# ============================================================================


def test_get_current_identity_anonymous(auth_adapter: OIDCAuthAdapter):
    """Anonymous request yields None on get_current_identity."""
    req_empty = create_request()
    assert get_current_identity(req_empty, adapter=auth_adapter) is None

    # Default adapter fallback (when adapter argument is omitted)
    assert get_current_identity(req_empty) is None


def test_get_current_identity_with_valid_session(auth_adapter: OIDCAuthAdapter):
    """Valid session cookie yields active Identity on get_current_identity."""
    admin_id, session_id = auth_adapter.authenticate_and_establish_session(
        "admin@example.com", "password123"
    )
    req = create_request(cookies={auth_adapter.session_cookie_name: session_id})
    resolved = get_current_identity(req, adapter=auth_adapter)
    assert resolved == admin_id
    assert resolved is not None
    assert resolved.email == "admin@example.com"
    assert "bdinvite_admins" in resolved.groups


def test_get_current_identity_with_valid_bearer_token(
    auth_adapter: OIDCAuthAdapter, oidc_client: OIDCClient
):
    """Valid Bearer token yields active Identity on get_current_identity."""
    _, tokens = oidc_client.authenticate_user("guest@example.com", "guestpass456")
    id_token = tokens["id_token"]

    req = create_request(headers={"Authorization": f"Bearer {id_token}"})
    resolved = get_current_identity(req, adapter=auth_adapter)
    assert resolved is not None
    assert resolved.email == "guest@example.com"
    assert resolved.groups == ["guests"]


def test_require_authenticated_anonymous_raises_401():
    """Anonymous request (identity=None) raises HTTP 401 on require_authenticated."""
    with pytest.raises(HTTPException) as exc_info:
        require_authenticated(identity=None)
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "Authentication required"
    assert exc_info.value.headers is not None
    assert exc_info.value.headers.get("WWW-Authenticate") == "Bearer"


def test_require_authenticated_success():
    """Authenticated user returns Identity from require_authenticated."""
    identity = Identity(
        subject="sub-123",
        email="user@example.com",
        groups=["guests"],
    )
    result = require_authenticated(identity=identity)
    assert result == identity


def test_require_group_anonymous_raises_401():
    """Anonymous user raises HTTP 401 on require_group."""
    group_dep = require_group("staff")
    with pytest.raises(HTTPException) as exc_info:
        group_dep(identity=None)
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_require_group_missing_group_raises_403():
    """Authenticated user missing the required group raises HTTP 403 Forbidden."""
    group_dep = require_group("staff")
    user = Identity(
        subject="sub-123",
        email="user@example.com",
        groups=["guests"],
    )
    with pytest.raises(HTTPException) as exc_info:
        group_dep(identity=user)
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert "staff" in exc_info.value.detail


def test_require_group_success():
    """Authenticated user possessing the required group returns Identity."""
    group_dep = require_group("staff")
    user = Identity(
        subject="sub-123",
        email="user@example.com",
        groups=["staff", "guests"],
    )
    result = group_dep(identity=user)
    assert result == user


def test_require_admin_anonymous_raises_401():
    """Anonymous request raises HTTP 401 on require_admin."""
    with pytest.raises(HTTPException) as exc_info:
        require_admin(identity=None)
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_require_admin_non_admin_raises_403():
    """Authenticated non-admin user raises HTTP 403 on require_admin."""
    guest_user = Identity(
        subject="guest-001",
        email="guest@example.com",
        groups=["guests"],
    )
    with pytest.raises(HTTPException) as exc_info:
        require_admin(identity=guest_user)
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert "bdinvite_admins" in exc_info.value.detail


def test_require_admin_success():
    """Authenticated admin user successfully yields Identity object on require_admin."""
    admin_user = Identity(
        subject="admin-001",
        email="admin@example.com",
        groups=["bdinvite_admins"],
    )
    result = require_admin(identity=admin_user)
    assert result == admin_user
    assert result.subject == "admin-001"
    assert result.email == "admin@example.com"
    assert result.groups == ["bdinvite_admins"]


# ============================================================================
# FastAPI Integration Tests (End-to-End Dependency Injection via TestClient)
# ============================================================================


def test_api_anonymous_get_current_identity(client: TestClient):
    """Anonymous request to /me yields None identity."""
    resp = client.get("/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["authenticated"] is False
    assert data["identity"] is None


def test_api_authenticated_user_get_current_identity(
    client: TestClient, auth_adapter: OIDCAuthAdapter
):
    """Authenticated user with session cookie resolves Identity on /me."""
    guest_id, session_id = auth_adapter.authenticate_and_establish_session(
        "guest@example.com", "guestpass456"
    )
    client.cookies.set(auth_adapter.session_cookie_name, session_id)

    resp = client.get("/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["authenticated"] is True
    assert data["identity"]["email"] == "guest@example.com"
    assert data["identity"]["groups"] == ["guests"]


def test_api_require_authenticated_anonymous_returns_401(client: TestClient):
    """Anonymous request to /authenticated raises HTTP 401 Unauthorized."""
    resp = client.get("/authenticated")
    assert resp.status_code == 401
    assert resp.headers.get("WWW-Authenticate") == "Bearer"
    assert resp.json()["detail"] == "Authentication required"


def test_api_require_authenticated_with_session_returns_200(
    client: TestClient, auth_adapter: OIDCAuthAdapter
):
    """Authenticated request to /authenticated returns 200 and Identity."""
    _, session_id = auth_adapter.authenticate_and_establish_session(
        "guest@example.com", "guestpass456"
    )
    client.cookies.set(auth_adapter.session_cookie_name, session_id)

    resp = client.get("/authenticated")
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "guest@example.com"


def test_api_require_admin_anonymous_returns_401(client: TestClient):
    """Anonymous request to /admin raises HTTP 401 Unauthorized."""
    resp = client.get("/admin")
    assert resp.status_code == 401
    assert resp.headers.get("WWW-Authenticate") == "Bearer"


def test_api_require_admin_non_admin_returns_403(
    client: TestClient, auth_adapter: OIDCAuthAdapter
):
    """Authenticated non-admin user (guest) raises HTTP 403 Forbidden on /admin."""
    _, session_id = auth_adapter.authenticate_and_establish_session(
        "guest@example.com", "guestpass456"
    )
    client.cookies.set(auth_adapter.session_cookie_name, session_id)

    resp = client.get("/admin")
    assert resp.status_code == 403
    assert "bdinvite_admins" in resp.json()["detail"]


def test_api_require_admin_admin_returns_200(
    client: TestClient, auth_adapter: OIDCAuthAdapter
):
    """Authenticated admin user (bdinvite_admins) succeeds with HTTP 200 on /admin."""
    admin_id, session_id = auth_adapter.authenticate_and_establish_session(
        "admin@example.com", "password123"
    )
    client.cookies.set(auth_adapter.session_cookie_name, session_id)

    resp = client.get("/admin")
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "admin@example.com"
    assert data["groups"] == ["bdinvite_admins"]


def test_api_bearer_token_authentication_flow(
    client: TestClient, oidc_client: OIDCClient
):
    """Bearer token in Authorization header successfully resolves through dependencies."""
    # 1. Guest user Bearer token -> /authenticated succeeds, /admin fails with 403
    _, guest_tokens = oidc_client.authenticate_user(
        "guest@example.com", "guestpass456"
    )
    guest_headers = {"Authorization": f"Bearer {guest_tokens['id_token']}"}

    resp_guest_auth = client.get("/authenticated", headers=guest_headers)
    assert resp_guest_auth.status_code == 200
    assert resp_guest_auth.json()["email"] == "guest@example.com"

    resp_guest_admin = client.get("/admin", headers=guest_headers)
    assert resp_guest_admin.status_code == 403

    # 2. Admin user Bearer token -> /admin succeeds with 200
    _, admin_tokens = oidc_client.authenticate_user("admin@example.com", "password123")
    admin_headers = {"Authorization": f"Bearer {admin_tokens['id_token']}"}

    resp_admin = client.get("/admin", headers=admin_headers)
    assert resp_admin.status_code == 200
    assert resp_admin.json()["email"] == "admin@example.com"
    assert resp_admin.json()["groups"] == ["bdinvite_admins"]


def test_api_dependency_overrides(test_app: FastAPI, client: TestClient):
    """FastAPI dependency overrides function cleanly on get_current_identity."""
    # 1. Override with mock admin identity
    mock_admin = Identity(
        subject="mock-admin",
        email="mockadmin@example.com",
        groups=["bdinvite_admins"],
    )
    test_app.dependency_overrides[get_current_identity] = lambda: mock_admin

    resp = client.get("/admin")
    assert resp.status_code == 200
    assert resp.json()["email"] == "mockadmin@example.com"

    # 2. Override with mock guest identity (missing bdinvite_admins)
    mock_guest = Identity(
        subject="mock-guest",
        email="mockguest@example.com",
        groups=["guests"],
    )
    test_app.dependency_overrides[get_current_identity] = lambda: mock_guest

    resp = client.get("/admin")
    assert resp.status_code == 403

    # 3. Override with anonymous (None)
    test_app.dependency_overrides[get_current_identity] = lambda: None

    resp = client.get("/admin")
    assert resp.status_code == 401

    test_app.dependency_overrides.clear()

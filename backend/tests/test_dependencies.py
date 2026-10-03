from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
import pytest

from app.auth import (
    Identity,
    InMemorySessionStore,
    OIDCAuthAdapter,
    OIDCClient,
    get_auth_adapter,
    get_current_identity,
    require_admin,
    require_authenticated,
    require_group,
    sign_session_cookie,
)

LIVE_ISSUER = "http://localhost:8088/default"
CLIENT_ID = "bdinvite-client"
CLIENT_SECRET = "bdinvite-secret"
REDIRECT_URI = "http://localhost:8000/birthday/api/auth/callback"


def create_dummy_request(
    headers: Optional[dict[str, str]] = None,
    cookies: Optional[dict[str, str]] = None,
) -> Request:
    """Construct a lightweight ASGI Request instance for unit testing dependencies."""
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


@pytest.fixture
def test_app() -> FastAPI:
    """Isolated FastAPI test harness registering dependency endpoints."""
    app = FastAPI(title="Dependency Test Harness")

    @app.get("/test/identity")
    def route_identity(identity: Optional[Identity] = Depends(get_current_identity)):
        if identity is None:
            return {"authenticated": False, "identity": None}
        return {
            "authenticated": True,
            "subject": identity.subject,
            "email": identity.email,
            "groups": identity.groups,
        }

    @app.get("/test/authenticated")
    def route_authenticated(identity: Identity = Depends(require_authenticated)):
        return {
            "subject": identity.subject,
            "email": identity.email,
            "groups": identity.groups,
        }

    @app.get("/test/admin")
    def route_admin(admin: Identity = Depends(require_admin)):
        return {
            "subject": admin.subject,
            "email": admin.email,
            "groups": admin.groups,
        }

    @app.get("/test/custom-group")
    def route_custom_group(member: Identity = Depends(require_group("event_planners"))):
        return {
            "subject": member.subject,
            "groups": member.groups,
        }

    return app


@pytest.fixture
def test_client(test_app: FastAPI) -> TestClient:
    return TestClient(test_app)


# ==============================================================================
# 1. Direct Unit Tests: FastAPI Dependency Functions in Isolation
# ==============================================================================


def test_unit_get_current_identity_anonymous():
    """get_current_identity yields None when request has no authentication credentials."""
    req = create_dummy_request()
    identity = get_current_identity(req)
    assert identity is None


def test_unit_get_current_identity_with_valid_session(auth_adapter: OIDCAuthAdapter):
    """get_current_identity resolves domain Identity when valid session cookie is provided."""
    expected = Identity(
        subject="alice-001",
        email="alice@example.com",
        groups=["users"],
    )
    session = auth_adapter.session_store.create_session(identity=expected)
    signed_cookie = sign_session_cookie(session.session_id, auth_adapter.secret_key)
    req = create_dummy_request(cookies={"bdinvite_session": signed_cookie})

    resolved = get_current_identity(req, adapter=auth_adapter)
    assert resolved == expected


def test_unit_get_current_identity_with_tampered_or_expired_cookie(
    auth_adapter: OIDCAuthAdapter,
):
    """get_current_identity safely yields None for tampered or expired sessions."""
    # 1. Tampered signature
    req_tampered = create_dummy_request(
        cookies={"bdinvite_session": "invalid_session_id.deadbeef"}
    )
    assert get_current_identity(req_tampered, adapter=auth_adapter) is None

    # 2. Expired session
    exp_session = auth_adapter.session_store.create_session(
        identity=Identity(subject="exp-user", email="exp@example.com"),
        max_age_seconds=-1,
    )
    signed_exp = sign_session_cookie(exp_session.session_id, auth_adapter.secret_key)
    req_expired = create_dummy_request(cookies={"bdinvite_session": signed_exp})
    assert get_current_identity(req_expired, adapter=auth_adapter) is None


def test_unit_require_authenticated():
    """require_authenticated returns Identity if present, raises HTTP 401 if anonymous."""
    valid_identity = Identity(
        subject="user-123",
        email="user123@example.com",
        groups=["guests"],
    )

    # Authenticated user passes cleanly
    result = require_authenticated(identity=valid_identity)
    assert result == valid_identity

    # Anonymous user (identity=None) raises HTTP 401
    with pytest.raises(HTTPException) as exc_info:
        require_authenticated(identity=None)
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Not authenticated"

    # Default / un-injected call raises HTTP 401
    with pytest.raises(HTTPException) as exc_info_default:
        require_authenticated()
    assert exc_info_default.value.status_code == 401


def test_unit_require_group_factory():
    """require_group produces dependencies enforcing specific group membership."""
    group_dep = require_group("special_ops")
    assert callable(group_dep)
    assert "special_ops" in group_dep.__name__

    user_with_group = Identity(
        subject="op-1",
        email="op1@example.com",
        groups=["special_ops", "staff"],
    )
    user_without_group = Identity(
        subject="user-2",
        email="user2@example.com",
        groups=["staff"],
    )

    # 1. Authorized member yields Identity
    assert group_dep(identity=user_with_group) == user_with_group

    # 2. Authenticated user missing the group raises HTTP 403
    with pytest.raises(HTTPException) as exc_info_403:
        group_dep(identity=user_without_group)
    assert exc_info_403.value.status_code == 403
    assert "Forbidden" in exc_info_403.value.detail

    # 3. Anonymous caller raises HTTP 401
    with pytest.raises(HTTPException) as exc_info_401:
        group_dep(identity=None)
    assert exc_info_401.value.status_code == 401


def test_unit_require_admin():
    """require_admin enforces bdinvite_admins group membership."""
    admin_identity = Identity(
        subject="admin-1",
        email="admin@example.com",
        groups=["bdinvite_admins"],
    )
    guest_identity = Identity(
        subject="guest-1",
        email="guest@example.com",
        groups=["guests"],
    )

    # Admin yields Identity
    assert require_admin(identity=admin_identity) == admin_identity

    # Non-admin raises HTTP 403
    with pytest.raises(HTTPException) as exc_403:
        require_admin(identity=guest_identity)
    assert exc_403.value.status_code == 403

    # Anonymous raises HTTP 401
    with pytest.raises(HTTPException) as exc_401:
        require_admin(identity=None)
    assert exc_401.value.status_code == 401


# ==============================================================================
# 2. HTTP Integration Tests: FastAPI Dependency Test Harness
# ==============================================================================


def test_http_anonymous_request_yields_none_on_get_current_identity(
    test_client: TestClient,
):
    """Anonymous request yields None on get_current_identity endpoint."""
    resp = test_client.get("/test/identity")
    assert resp.status_code == 200
    assert resp.json() == {"authenticated": False, "identity": None}


def test_http_anonymous_request_raises_401_on_require_authenticated(
    test_client: TestClient,
):
    """Anonymous request raises HTTP 401 Unauthorized on require_authenticated."""
    resp = test_client.get("/test/authenticated")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Not authenticated"


def test_http_anonymous_request_raises_401_on_require_admin(
    test_client: TestClient,
):
    """Anonymous request raises HTTP 401 Unauthorized on require_admin."""
    resp = test_client.get("/test/admin")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Not authenticated"


def test_http_authenticated_non_admin_raises_403_on_require_admin(
    test_client: TestClient,
):
    """Authenticated non-admin user (guest@example.com with groups: ['guests']) raises HTTP 403."""
    adapter = get_auth_adapter()
    guest_identity = Identity(
        subject="guest-001",
        email="guest@example.com",
        groups=["guests"],
    )
    session = adapter.session_store.create_session(identity=guest_identity)
    signed_cookie = sign_session_cookie(session.session_id, adapter.secret_key)
    test_client.cookies.set(adapter.session_cookie_name, signed_cookie)

    # 1. get_current_identity yields the guest identity
    resp_id = test_client.get("/test/identity")
    assert resp_id.status_code == 200
    assert resp_id.json()["authenticated"] is True
    assert resp_id.json()["subject"] == "guest-001"
    assert resp_id.json()["groups"] == ["guests"]

    # 2. require_authenticated succeeds
    resp_auth = test_client.get("/test/authenticated")
    assert resp_auth.status_code == 200
    assert resp_auth.json()["subject"] == "guest-001"

    # 3. require_admin raises HTTP 403 Forbidden
    resp_admin = test_client.get("/test/admin")
    assert resp_admin.status_code == 403
    assert "Forbidden" in resp_admin.json()["detail"]


def test_http_authenticated_admin_yields_identity_on_require_admin(
    test_client: TestClient,
):
    """Authenticated admin user (admin@example.com with groups: ['bdinvite_admins']) yields Identity."""
    adapter = get_auth_adapter()
    admin_identity = Identity(
        subject="admin-001",
        email="admin@example.com",
        groups=["bdinvite_admins"],
    )
    session = adapter.session_store.create_session(identity=admin_identity)
    signed_cookie = sign_session_cookie(session.session_id, adapter.secret_key)
    test_client.cookies.set(adapter.session_cookie_name, signed_cookie)

    # 1. get_current_identity yields admin identity
    resp_id = test_client.get("/test/identity")
    assert resp_id.status_code == 200
    assert resp_id.json()["subject"] == "admin-001"

    # 2. require_authenticated yields admin identity
    resp_auth = test_client.get("/test/authenticated")
    assert resp_auth.status_code == 200
    assert resp_auth.json()["subject"] == "admin-001"

    # 3. require_admin successfully yields the Identity object
    resp_admin = test_client.get("/test/admin")
    assert resp_admin.status_code == 200
    data = resp_admin.json()
    assert data["subject"] == "admin-001"
    assert data["email"] == "admin@example.com"
    assert data["groups"] == ["bdinvite_admins"]


def test_http_custom_group_requirement(test_client: TestClient):
    """require_group enforces arbitrary group membership correctly."""
    adapter = get_auth_adapter()

    # User without event_planners group -> 403
    user_identity = Identity(
        subject="user-planner-no",
        email="planner_no@example.com",
        groups=["volunteers"],
    )
    session_no = adapter.session_store.create_session(identity=user_identity)
    signed_no = sign_session_cookie(session_no.session_id, adapter.secret_key)
    test_client.cookies.set(adapter.session_cookie_name, signed_no)

    resp_denied = test_client.get("/test/custom-group")
    assert resp_denied.status_code == 403

    # User with event_planners group -> 200
    planner_identity = Identity(
        subject="user-planner-yes",
        email="planner_yes@example.com",
        groups=["volunteers", "event_planners"],
    )
    session_yes = adapter.session_store.create_session(identity=planner_identity)
    signed_yes = sign_session_cookie(session_yes.session_id, adapter.secret_key)
    test_client.cookies.set(adapter.session_cookie_name, signed_yes)

    resp_allowed = test_client.get("/test/custom-group")
    assert resp_allowed.status_code == 200
    assert resp_allowed.json()["subject"] == "user-planner-yes"


def test_http_bearer_token_authorization(
    test_client: TestClient,
    oidc_client: OIDCClient,
):
    """Bearer token containing admin groups satisfies require_admin; non-admin raises 403."""
    # 1. Authenticate admin user against IdP to obtain verified ID token
    admin_token_resp, _ = oidc_client.authenticate_with_password(
        username="admin@example.com",
        password="password123",
        scopes=["openid", "profile", "email"],
    )
    admin_headers = {"Authorization": f"Bearer {admin_token_resp.id_token}"}
    resp_admin = test_client.get("/test/admin", headers=admin_headers)
    assert resp_admin.status_code == 200
    assert resp_admin.json()["subject"] == "admin-001"

    # 2. Authenticate guest user against IdP to obtain verified ID token
    guest_token_resp, _ = oidc_client.authenticate_with_password(
        username="guest@example.com",
        password="password123",
        scopes=["openid", "profile", "email"],
    )
    guest_headers = {"Authorization": f"Bearer {guest_token_resp.id_token}"}
    resp_guest = test_client.get("/test/admin", headers=guest_headers)
    assert resp_guest.status_code == 403


def test_http_remote_user_header_spoofing_rejected(test_client: TestClient):
    """Remote-User and other unverified request headers cannot spoof identity or bypass dependencies."""
    spoof_headers = {
        "Remote-User": "admin@example.com",
        "X-Remote-User": "admin-001",
        "X-User-Groups": "bdinvite_admins",
    }

    # All protected dependency endpoints reject unverified headers
    resp_id = test_client.get("/test/identity", headers=spoof_headers)
    assert resp_id.status_code == 200
    assert resp_id.json() == {"authenticated": False, "identity": None}

    resp_auth = test_client.get("/test/authenticated", headers=spoof_headers)
    assert resp_auth.status_code == 401

    resp_admin = test_client.get("/test/admin", headers=spoof_headers)
    assert resp_admin.status_code == 401


def test_fastapi_dependency_overrides(test_app: FastAPI, test_client: TestClient):
    """FastAPI dependency_overrides works as expected with require_admin and get_current_identity."""
    mock_admin = Identity(
        subject="mocked-admin",
        email="mocked@example.com",
        groups=["bdinvite_admins"],
    )

    test_app.dependency_overrides[require_admin] = lambda: mock_admin
    try:
        resp = test_client.get("/test/admin")
        assert resp.status_code == 200
        assert resp.json()["subject"] == "mocked-admin"
    finally:
        test_app.dependency_overrides.clear()

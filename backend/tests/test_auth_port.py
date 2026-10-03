import ast
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Optional

import pytest
from fastapi import Request, Response
from fastapi.responses import RedirectResponse
from starlette.datastructures import Headers

from app.auth import AuthPort, Identity


class MockAuthAdapter:
    """Mock implementation of AuthPort for testing hexagonal boundary contract."""

    def __init__(self, sessions: Optional[dict[str, Identity]] = None):
        self.sessions = sessions or {}

    def current_identity(self, request: Request) -> Optional[Identity]:
        session_id = request.headers.get("X-Session-ID") or request.cookies.get("session_id")
        if session_id and session_id in self.sessions:
            return self.sessions[session_id]
        return None

    def login(self, request: Request) -> Response:
        return RedirectResponse(url="https://auth.example.com/oauth/authorize", status_code=302)

    def logout(self, request: Request) -> Response:
        response = Response(content="logged out", status_code=200)
        response.delete_cookie("session_id")
        return response


class IncompleteAuthAdapter:
    """Incomplete adapter missing logout to test Protocol validation."""

    def current_identity(self, request: Request) -> Optional[Identity]:
        return None

    def login(self, request: Request) -> Response:
        return Response(content="login", status_code=200)


def create_mock_request(headers: Optional[dict[str, str]] = None, cookies: Optional[dict[str, str]] = None) -> Request:
    """Helper to build a Starlette/FastAPI Request instance with mock scope."""
    header_list = [(k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in (headers or {}).items()]
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": header_list,
        "query_string": b"",
    }
    req = Request(scope)
    if cookies:
        cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())
        header_list.append((b"cookie", cookie_header.encode("latin-1")))
        req.scope["headers"] = header_list
    return req


def test_identity_creation_defaults():
    identity = Identity(subject="usr_123", email="user@example.com")
    assert identity.subject == "usr_123"
    assert identity.email == "user@example.com"
    assert identity.name is None
    assert identity.groups == []


def test_identity_creation_full():
    identity = Identity(
        subject="usr_456",
        email="admin@example.com",
        name="Admin User",
        groups=["admins", "organizers"],
    )
    assert identity.subject == "usr_456"
    assert identity.email == "admin@example.com"
    assert identity.name == "Admin User"
    assert identity.groups == ["admins", "organizers"]


def test_identity_none_groups_normalized():
    identity = Identity(subject="usr_789", email="test@example.com", groups=None)  # type: ignore[arg-type]
    assert identity.groups == []


def test_identity_frozen_immutability():
    identity = Identity(subject="usr_123", email="user@example.com")
    with pytest.raises(FrozenInstanceError):
        identity.subject = "usr_999"  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        identity.email = "changed@example.com"  # type: ignore[misc]


def test_identity_equality():
    id1 = Identity(subject="usr_1", email="a@b.com", name="Alice", groups=["user"])
    id2 = Identity(subject="usr_1", email="a@b.com", name="Alice", groups=["user"])
    id3 = Identity(subject="usr_2", email="a@b.com", name="Alice", groups=["user"])

    assert id1 == id2
    assert id1 != id3


def test_auth_port_protocol_conformance():
    adapter = MockAuthAdapter()
    assert isinstance(adapter, AuthPort)
    assert issubclass(MockAuthAdapter, AuthPort)

    incomplete = IncompleteAuthAdapter()
    assert not isinstance(incomplete, AuthPort)
    assert not issubclass(IncompleteAuthAdapter, AuthPort)


def test_auth_port_behavior_with_mock():
    expected_identity = Identity(
        subject="sub_valid",
        email="guest@example.com",
        name="Guest User",
        groups=["guests"],
    )
    adapter = MockAuthAdapter(sessions={"valid_token": expected_identity})

    # Unauthenticated request
    unauth_req = create_mock_request()
    assert adapter.current_identity(unauth_req) is None

    # Authenticated request via header
    auth_req = create_mock_request(headers={"X-Session-ID": "valid_token"})
    resolved = adapter.current_identity(auth_req)
    assert resolved == expected_identity
    assert resolved is not None
    assert resolved.email == "guest@example.com"

    # Login flow
    login_resp = adapter.login(unauth_req)
    assert isinstance(login_resp, Response)
    assert login_resp.status_code == 302
    assert login_resp.headers["location"] == "https://auth.example.com/oauth/authorize"

    # Logout flow
    logout_resp = adapter.logout(auth_req)
    assert isinstance(logout_resp, Response)
    assert logout_resp.status_code == 200


def test_architectural_isolation_zero_prohibited_imports():
    """Verify application domain files do not import OIDC, OAuth, JWT, cryptography, or proxy headers."""
    backend_app_dir = Path(__file__).resolve().parent.parent / "app"
    prohibited_keywords = {"oidc", "oauth", "jwt", "jose", "cryptography"}

    # Files to inspect: routes, models, schemas, and auth port
    domain_paths = [
        backend_app_dir / "models.py",
        backend_app_dir / "schemas.py",
        backend_app_dir / "auth" / "port.py",
    ]
    domain_paths.extend((backend_app_dir / "routes").glob("*.py"))

    for py_file in domain_paths:
        assert py_file.exists(), f"Expected domain file {py_file} to exist"
        tree = ast.parse(py_file.read_text("utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name_lower = alias.name.lower()
                    for prohibited in prohibited_keywords:
                        assert prohibited not in name_lower, (
                            f"Prohibited import '{alias.name}' found in {py_file}"
                        )
            elif isinstance(node, ast.ImportFrom):
                module_name = (node.module or "").lower()
                for prohibited in prohibited_keywords:
                    assert prohibited not in module_name, (
                        f"Prohibited import from '{node.module}' found in {py_file}"
                    )

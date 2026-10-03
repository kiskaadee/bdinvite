from dataclasses import FrozenInstanceError
from typing import Optional

import pytest
from fastapi import Request, Response
from fastapi.responses import RedirectResponse
from starlette.datastructures import Headers

from app.auth import AuthPort, Identity


class MockAuthAdapter:
    """Mock implementation of AuthPort for testing hexagonal boundary compliance."""

    def __init__(self, current_user: Optional[Identity] = None):
        self._current_user = current_user

    def current_identity(self, request: Request) -> Optional[Identity]:
        return self._current_user

    def login(self, request: Request) -> Response:
        return RedirectResponse(url="/auth/login", status_code=302)

    def logout(self, request: Request) -> Response:
        return RedirectResponse(url="/auth/logout", status_code=302)


class IncompleteAuthAdapter:
    """Non-conforming class missing login and logout methods."""

    def current_identity(self, request: Request) -> Optional[Identity]:
        return None


def create_dummy_request(headers: dict[str, str] | None = None) -> Request:
    raw_headers = [
        (k.lower().encode("latin-1"), v.encode("latin-1"))
        for k, v in (headers or {}).items()
    ]
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": raw_headers,
    }
    return Request(scope)


def test_identity_creation_full():
    identity = Identity(
        subject="user-123",
        email="test@example.com",
        name="Test User",
        groups=["admin", "family"],
    )
    assert identity.subject == "user-123"
    assert identity.email == "test@example.com"
    assert identity.name == "Test User"
    assert identity.groups == ["admin", "family"]
    assert identity.has_group("admin") is True
    assert identity.has_group("stranger") is False


def test_identity_creation_defaults():
    identity = Identity(
        subject="user-456",
        email="minimal@example.com",
    )
    assert identity.subject == "user-456"
    assert identity.email == "minimal@example.com"
    assert identity.name is None
    assert identity.groups == []
    assert identity.has_group("admin") is False


def test_identity_immutability():
    identity = Identity(
        subject="user-789",
        email="immutable@example.com",
    )
    with pytest.raises(FrozenInstanceError):
        identity.subject = "new-subject"  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        identity.email = "new@example.com"  # type: ignore[misc]


def test_identity_validation_subject():
    with pytest.raises(ValueError, match="subject must be a non-empty string"):
        Identity(subject="", email="test@example.com")

    with pytest.raises(ValueError, match="subject must be a non-empty string"):
        Identity(subject="   ", email="test@example.com")


def test_identity_validation_email():
    with pytest.raises(ValueError, match="email must be a non-empty string"):
        Identity(subject="user-1", email="")

    with pytest.raises(ValueError, match="email must be a non-empty string"):
        Identity(subject="user-1", email="  ")


def test_identity_validation_name():
    with pytest.raises(TypeError, match="name must be a string or None"):
        Identity(subject="user-1", email="test@example.com", name=123)  # type: ignore[arg-type]


def test_identity_validation_groups():
    with pytest.raises(TypeError, match="groups must be a list of strings"):
        Identity(subject="user-1", email="test@example.com", groups="not-a-list")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="groups items must be strings"):
        Identity(subject="user-1", email="test@example.com", groups=[123])  # type: ignore[list-item]


def test_auth_port_protocol_conformance():
    adapter = MockAuthAdapter()
    assert isinstance(adapter, AuthPort)


def test_auth_port_protocol_non_conformance():
    incomplete = IncompleteAuthAdapter()
    assert not isinstance(incomplete, AuthPort)


def test_auth_port_current_identity_resolution():
    expected_identity = Identity(
        subject="admin-1",
        email="admin@example.com",
        name="Admin",
        groups=["admin"],
    )
    authenticated_port: AuthPort = MockAuthAdapter(current_user=expected_identity)
    unauthenticated_port: AuthPort = MockAuthAdapter(current_user=None)

    req = create_dummy_request()
    assert authenticated_port.current_identity(req) == expected_identity
    assert unauthenticated_port.current_identity(req) is None


def test_auth_port_login_logout_contract():
    port: AuthPort = MockAuthAdapter()
    req = create_dummy_request()

    login_resp = port.login(req)
    assert isinstance(login_resp, Response)
    assert login_resp.status_code == 302
    assert login_resp.headers["location"] == "/auth/login"

    logout_resp = port.logout(req)
    assert isinstance(logout_resp, Response)
    assert logout_resp.status_code == 302
    assert logout_resp.headers["location"] == "/auth/logout"

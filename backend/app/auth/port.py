"""Authentication port and identity abstractions for hexagonal architecture."""

from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable

from fastapi import Request, Response


@dataclass(frozen=True)
class Identity:
    """Domain model representing a validated authenticated user identity.

    Identity Origin Integrity Invariant:
    An Identity instance must only represent validated authentication results
    (such as from an authorized identity provider, cryptographically verified token,
    or trusted authentication adapter). It must never be constructed directly
    from raw, unvalidated client request headers.
    """

    subject: str
    email: str
    name: Optional[str] = None
    groups: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.groups is None:  # type: ignore[reportUnnecessaryComparison]
            object.__setattr__(self, "groups", [])
        elif not isinstance(self.groups, list):
            object.__setattr__(self, "groups", list(self.groups))


@runtime_checkable
class AuthPort(Protocol):
    """Hexagonal inbound/outbound port interface for authentication."""

    def current_identity(self, request: Request) -> Optional[Identity]:
        """Extract and return the verified Identity from the incoming request.

        Returns None if the request is unauthenticated or credentials are invalid.
        """
        ...

    def login(self, request: Request) -> Response:
        """Handle or initiate the authentication flow (e.g. redirecting to an IdP)."""
        ...

    def logout(self, request: Request) -> Response:
        """Handle session termination or logout redirection."""
        ...

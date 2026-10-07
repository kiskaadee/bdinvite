from typing import Protocol, runtime_checkable

from fastapi import Request, Response

from .identity import Identity


@runtime_checkable
class AuthPort(Protocol):
    """Hexagonal Port for Authentication and Identity Management.

    Establishes the boundary between application domain logic and concrete authentication
    mechanisms (such as OIDC, OAuth, ForwardAuth, or session providers).
    """

    def current_identity(self, request: Request) -> Identity | None:
        """Resolve the validated identity associated with the incoming request.

        Returns None if the request is unauthenticated or credentials/session are invalid.
        """
        ...

    def login(self, request: Request) -> Response:
        """Initiate the login flow (e.g. redirect to identity provider or challenge response)."""
        ...

    def logout(self, request: Request) -> Response:
        """Terminate the session or logout flow (e.g. invalidate session cookie or IdP logout redirect)."""
        ...


__all__ = ["AuthPort", "Identity"]

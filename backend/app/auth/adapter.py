from typing import Optional

from fastapi import Request, Response
from fastapi.responses import RedirectResponse

from .identity import Identity
from .oidc import OIDCClient
from .port import AuthPort


class OIDCAuthAdapter(AuthPort):
    """Hexagonal Adapter binding generic OIDC client to the AuthPort domain contract."""

    def __init__(
        self,
        oidc_client: OIDCClient,
        session_cookie_name: str = "session_token",
    ) -> None:
        self.oidc_client = oidc_client
        self.session_cookie_name = session_cookie_name

    def current_identity(self, request: Request) -> Optional[Identity]:
        """Resolve the validated identity associated with the incoming request.

        Identity Origin Integrity:
        Resolves identity strictly from cryptographically verified tokens (Authorization Bearer
        header or session cookie). Request-controlled headers (e.g. Remote-User, X-User) are
        strictly ignored to prevent identity spoofing.
        """
        token: Optional[str] = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        elif self.session_cookie_name in request.cookies:
            token = request.cookies[self.session_cookie_name]

        if not token:
            return None

        try:
            return self.oidc_client.extract_identity_from_token(token)
        except Exception:
            return None

    def login(self, request: Request) -> Response:
        """Initiate the OIDC login flow with 302 redirect."""
        auth_req = self.oidc_client.create_authorization_url()
        return RedirectResponse(url=auth_req.url, status_code=302)

    def logout(self, request: Request) -> Response:
        """Terminate the session and redirect."""
        end_session = self.oidc_client.end_session_endpoint
        target_url = end_session if end_session else "/"
        response = RedirectResponse(url=target_url, status_code=302)
        response.delete_cookie(self.session_cookie_name)
        return response

    def extract_identity(self, claims: dict[str, object]) -> Identity:
        """Delegate identity extraction from verified claims to OIDCClient."""
        return self.oidc_client.extract_identity(claims)


__all__ = ["OIDCAuthAdapter"]

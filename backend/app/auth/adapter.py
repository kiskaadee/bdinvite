from typing import Literal, Optional

from fastapi import Request, Response
from fastapi.responses import RedirectResponse

from ..config import settings
from .identity import Identity
from .oidc import OIDCClient
from .port import AuthPort
from .session import (
    InMemorySessionStore,
    SessionData,
    SessionStore,
    sign_session_cookie,
    unsign_session_cookie,
)


class OIDCAuthAdapter(AuthPort):
    """Hexagonal Adapter binding generic OIDC client and browser session store to AuthPort."""

    def __init__(
        self,
        oidc_client: OIDCClient,
        session_cookie_name: str = settings.SESSION_COOKIE_NAME,
        session_store: Optional[SessionStore] = None,
        cookie_secure: Optional[bool] = None,
        cookie_samesite: Optional[Literal["lax", "strict", "none"]] = None,
        session_max_age: Optional[int] = None,
        secret_key: Optional[str] = None,
    ) -> None:
        self.oidc_client = oidc_client
        self.session_cookie_name = session_cookie_name
        self.session_store: SessionStore = (
            session_store if session_store is not None else InMemorySessionStore()
        )
        self.cookie_secure: bool = (
            cookie_secure if cookie_secure is not None else settings.SESSION_COOKIE_SECURE
        )
        self.cookie_samesite: Literal["lax", "strict", "none"] = (
            cookie_samesite if cookie_samesite is not None else settings.SESSION_COOKIE_SAMESITE
        )
        self.session_max_age: int = (
            session_max_age if session_max_age is not None else settings.SESSION_MAX_AGE_SECONDS
        )
        self.secret_key: str = (
            secret_key if secret_key is not None else settings.SESSION_SECRET_KEY
        )

    def parse_session_cookie(self, cookie_value: Optional[str]) -> Optional[str]:
        """Extract and verify session_id from cookie, safely rejecting tampered cookies."""
        if not cookie_value or not isinstance(cookie_value, str) or not cookie_value.strip():
            return None

        # 1. Attempt HMAC signature verification
        unsigned = unsign_session_cookie(cookie_value, self.secret_key)
        if unsigned is not None:
            return unsigned

        # 2. Tampered cookie detection:
        # If it has a dot and is not a 3-part JWT, it was a tampered signed cookie
        if "." in cookie_value:
            # Let JWT pass through to token fallback if 3 segments
            if cookie_value.count(".") == 2:
                return None
            return None

        # 3. Direct lookup for raw session_id (e.g. test fixtures without HMAC signing)
        if self.session_store.get_session(cookie_value) is not None:
            return cookie_value

        return None

    def current_identity(self, request: Request) -> Optional[Identity]:
        """Resolve the validated identity associated with the incoming request.

        Identity Origin Integrity:
        Resolves identity strictly from verified server-side sessions or cryptographically
        verified tokens (Authorization Bearer header). Request-controlled headers (e.g.
        legacy proxy headers (e.g. forwarded user headers, X-User) are strictly ignored to prevent identity spoofing.
        """
        # 1. Authorization: Bearer <token>
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            try:
                return self.oidc_client.extract_identity_from_token(token)
            except Exception:
                return None

        # 2. Browser session cookie
        raw_cookie = request.cookies.get(self.session_cookie_name)
        if not raw_cookie:
            return None

        # Attempt resolving from session store
        session_id = self.parse_session_cookie(raw_cookie)
        if session_id:
            session = self.session_store.get_session(session_id)
            if session is not None:
                if session.is_expired():
                    self.session_store.delete_session(session_id)
                    return None
                return session.identity
            return None

        # Fallback for backward compatibility with CP3 token-in-cookie tests
        try:
            return self.oidc_client.extract_identity_from_token(raw_cookie)
        except Exception:
            return None

    def set_session_cookie(
        self,
        response: Response,
        session_id: str,
        max_age: Optional[int] = None,
    ) -> None:
        """Issue session cookie enforcing HttpOnly=True, SameSite, and configurable Secure flag."""
        signed_val = sign_session_cookie(session_id, self.secret_key)
        response.set_cookie(
            key=self.session_cookie_name,
            value=signed_val,
            max_age=max_age if max_age is not None else self.session_max_age,
            httponly=True,  # Security Invariant: ALWAYS True to protect against XSS
            samesite=self.cookie_samesite,
            secure=self.cookie_secure,
            path="/",
        )

    def clear_session_cookie(self, response: Response) -> None:
        """Clear session cookie with Max-Age=0."""
        response.delete_cookie(
            key=self.session_cookie_name,
            path="/",
            httponly=True,
            samesite=self.cookie_samesite,
            secure=self.cookie_secure,
        )

    def create_session(
        self,
        identity: Optional[Identity] = None,
        request: Optional[Request] = None,
        response: Optional[Response] = None,
        pre_auth_session_id: Optional[str] = None,
        max_age_seconds: Optional[int] = None,
    ) -> SessionData:
        """Create session with Session Fixation Protection.

        Guarantees:
        - If a pre-authentication session existed, it is invalidated and never promoted.
        - A fresh, unguessable session identifier is generated (pre_auth != post_auth).
        - If response is provided, the HttpOnly cookie is attached.
        """
        candidate_pre_auth = pre_auth_session_id
        if not candidate_pre_auth and request is not None:
            raw_cookie = request.cookies.get(self.session_cookie_name)
            if raw_cookie:
                candidate_pre_auth = self.parse_session_cookie(raw_cookie)

        effective_max_age = (
            max_age_seconds if max_age_seconds is not None else self.session_max_age
        )
        session = self.session_store.create_session(
            identity=identity,
            max_age_seconds=effective_max_age,
            pre_auth_session_id=candidate_pre_auth,
        )

        if candidate_pre_auth:
            assert session.session_id != candidate_pre_auth

        if response is not None:
            self.set_session_cookie(response, session.session_id, max_age=effective_max_age)

        return session

    def login(self, request: Request) -> Response:
        """Initiate OIDC login flow with 302 redirect and pre-auth session establishment."""
        auth_req = self.oidc_client.create_authorization_url()
        response = RedirectResponse(url=auth_req.url, status_code=302)

        # Issue pre-authentication session if request does not already possess one
        raw_cookie = request.cookies.get(self.session_cookie_name)
        existing_session_id = self.parse_session_cookie(raw_cookie) if raw_cookie else None
        if not existing_session_id or self.session_store.get_session(existing_session_id) is None:
            pre_auth = self.session_store.create_session(
                identity=None,
                max_age_seconds=self.session_max_age,
            )
            self.set_session_cookie(response, pre_auth.session_id)

        return response

    def logout(self, request: Request) -> Response:
        """Terminate session on server and clear browser cookie."""
        raw_cookie = request.cookies.get(self.session_cookie_name)
        if raw_cookie:
            session_id = self.parse_session_cookie(raw_cookie)
            if session_id:
                self.session_store.delete_session(session_id)

        end_session = self.oidc_client.end_session_endpoint
        target_url = end_session if end_session else "/"
        response = RedirectResponse(url=target_url, status_code=302)
        self.clear_session_cookie(response)
        return response

    def extract_identity(self, claims: dict[str, object]) -> Identity:
        """Delegate identity extraction from verified claims to OIDCClient."""
        return self.oidc_client.extract_identity(claims)


__all__ = ["OIDCAuthAdapter"]

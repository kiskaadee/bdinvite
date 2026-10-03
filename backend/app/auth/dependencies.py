"""FastAPI dependency injection module for authentication and authorization."""

from collections.abc import Callable
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Request, status

from ..config import settings
from .oidc import OIDCAuthAdapter, OIDCClient, OIDCConfig
from .port import Identity

_auth_adapter: Optional[OIDCAuthAdapter] = None


def get_auth_adapter() -> OIDCAuthAdapter:
    """Provide singleton or cached OIDCAuthAdapter for dependency injection."""
    global _auth_adapter
    if _auth_adapter is None:
        client_config = OIDCConfig(
            issuer=settings.OIDC_ISSUER,
            client_id=settings.OIDC_CLIENT_ID,
            client_secret=settings.OIDC_CLIENT_SECRET,
            redirect_uri=settings.OIDC_REDIRECT_URI,
            groups_claim=settings.OIDC_GROUPS_CLAIM,
            group_claim_path=settings.OIDC_GROUP_CLAIM_PATH,
        )
        client = OIDCClient(client_config)
        _auth_adapter = OIDCAuthAdapter(
            client=client,
            session_cookie_name=settings.SESSION_COOKIE_NAME,
            cookie_secure=settings.SESSION_COOKIE_SECURE,
            cookie_samesite=settings.SESSION_COOKIE_SAMESITE,
            cookie_path=settings.SESSION_COOKIE_PATH,
            cookie_domain=settings.SESSION_COOKIE_DOMAIN,
            session_lifetime=float(settings.SESSION_EXPIRE_SECONDS),
        )
    return _auth_adapter


def set_auth_adapter(adapter: Optional[OIDCAuthAdapter]) -> None:
    """Override the active auth adapter (for test isolation and fixture injection)."""
    global _auth_adapter
    _auth_adapter = adapter


AuthAdapterDep = Annotated[OIDCAuthAdapter, Depends(get_auth_adapter)]


def get_current_identity(
    request: Request,
    adapter: OIDCAuthAdapter = Depends(get_auth_adapter),
) -> Optional[Identity]:
    """Resolve the active Identity from the session or adapter, or None if unauthenticated."""
    if not isinstance(adapter, OIDCAuthAdapter):
        adapter = get_auth_adapter()
    return adapter.current_identity(request)


def require_authenticated(
    identity: Optional[Identity] = Depends(get_current_identity),
) -> Identity:
    """Enforce authentication, raising HTTP 401 Unauthorized if anonymous."""
    if identity is None or not isinstance(identity, Identity):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return identity


def require_group(group_name: str) -> Callable[..., Identity]:
    """Dependency factory enforcing membership in a specified group.

    Raises HTTP 401 Unauthorized if anonymous, and HTTP 403 Forbidden
    if authenticated but missing the required group in identity.groups.
    """

    def _require_group_dependency(
        identity: Optional[Identity] = Depends(get_current_identity),
    ) -> Identity:
        if identity is None or not isinstance(identity, Identity):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if group_name not in identity.groups:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: user is not a member of group '{group_name}'",
            )
        return identity

    _require_group_dependency.__name__ = f"require_group_{group_name}"
    _require_group_dependency.__qualname__ = (
        f"require_group.<locals>.require_group_{group_name}"
    )
    return _require_group_dependency


# Application Authorization Policy:
require_admin: Callable[..., Identity] = require_group("bdinvite_admins")

# Type annotations for endpoint dependency injection
CurrentIdentityDep = Annotated[Optional[Identity], Depends(get_current_identity)]
AuthenticatedUserDep = Annotated[Identity, Depends(require_authenticated)]
AdminUserDep = Annotated[Identity, Depends(require_admin)]

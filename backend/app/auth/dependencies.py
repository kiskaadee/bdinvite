from collections.abc import Callable
from typing import Annotated, Optional, cast

from fastapi import Depends, HTTPException, Request, status
from fastapi.params import Depends as DependsClass

from ..config import settings
from .adapter import OIDCAuthAdapter
from .identity import Identity
from .oidc import OIDCClient
from .session import InMemorySessionStore

_auth_adapter_instance: Optional[OIDCAuthAdapter] = None


def get_auth_adapter() -> OIDCAuthAdapter:
    """Dependency provider returning singleton OIDCAuthAdapter instance."""
    global _auth_adapter_instance
    if _auth_adapter_instance is None:
        client = OIDCClient(
            issuer=settings.OIDC_ISSUER,
            client_id=settings.OIDC_CLIENT_ID,
            client_secret=settings.OIDC_CLIENT_SECRET,
            redirect_uri=settings.OIDC_REDIRECT_URI,
            groups_claim=settings.OIDC_GROUPS_CLAIM,
        )
        _auth_adapter_instance = OIDCAuthAdapter(
            oidc_client=client,
            session_cookie_name=settings.SESSION_COOKIE_NAME,
            session_store=InMemorySessionStore(),
            cookie_secure=settings.SESSION_COOKIE_SECURE,
            cookie_samesite=settings.SESSION_COOKIE_SAMESITE,
            session_max_age=settings.SESSION_MAX_AGE_SECONDS,
            secret_key=settings.SESSION_SECRET_KEY,
        )
    return _auth_adapter_instance


def get_current_identity(
    request: Request,
    adapter: OIDCAuthAdapter = Depends(get_auth_adapter),
) -> Optional[Identity]:
    """Resolves the active Identity from the session/adapter, or None if unauthenticated."""
    resolved_adapter: OIDCAuthAdapter = (
        get_auth_adapter() if isinstance(cast(object, adapter), DependsClass) else adapter
    )
    return resolved_adapter.current_identity(request)


def require_authenticated(
    identity: Optional[Identity] = Depends(get_current_identity),
) -> Identity:
    """Enforces authentication, raising HTTP 401 Unauthorized if anonymous."""
    if isinstance(cast(object, identity), DependsClass) or identity is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return identity


def require_group(group_name: str) -> Callable[..., Identity]:
    """Dependency factory enforcing group membership.

    Raises HTTP 401 Unauthorized if anonymous, and HTTP 403 Forbidden if
    authenticated but missing the required group in identity.groups.
    """

    def _group_dependency(
        identity: Identity = Depends(require_authenticated),
    ) -> Identity:
        if isinstance(cast(object, identity), DependsClass) or identity is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )
        if not identity.has_group(group_name):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: user is not a member of group '{group_name}'",
            )
        return identity

    _group_dependency.__name__ = f"require_group_{group_name}"
    _group_dependency.__doc__ = (
        f"FastAPI dependency requiring membership in '{group_name}' group."
    )
    return _group_dependency


require_admin: Callable[..., Identity] = require_group("bdinvite_admins")

CurrentIdentityDep = Annotated[Optional[Identity], Depends(get_current_identity)]
AuthenticatedDep = Annotated[Identity, Depends(require_authenticated)]
AdminDep = Annotated[Identity, Depends(require_admin)]

__all__ = [
    "AdminDep",
    "AuthenticatedDep",
    "CurrentIdentityDep",
    "get_auth_adapter",
    "get_current_identity",
    "require_admin",
    "require_authenticated",
    "require_group",
]

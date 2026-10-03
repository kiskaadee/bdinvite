"""Authentication and browser session management API routes."""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse

from ..auth import OIDCAuthAdapter, OIDCClient, OIDCConfig
from ..config import settings

router = APIRouter(tags=["Auth"])

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


@router.get(
    "/login",
    summary="Initiate OIDC authentication flow",
    description="Redirects user browser to the configured OIDC provider authorization endpoint.",
)
def login(request: Request, adapter: AuthAdapterDep) -> Response:
    return adapter.login(request)


@router.get(
    "/callback",
    summary="Handle OIDC authentication callback",
    description=(
        "Processes authorization code and state from IdP. "
        "Enforces session fixation barrier by issuing a fresh session identifier "
        "and sets HttpOnly SameSite browser session cookie."
    ),
)
def callback(
    request: Request,
    adapter: AuthAdapterDep,
    code: str = Query(..., description="Authorization code from IdP"),
    state: str = Query(..., description="CSRF state parameter"),
) -> Response:
    target_url = "/birthday/"
    response = RedirectResponse(url=target_url, status_code=status.HTTP_302_FOUND)
    adapter.handle_callback(
        code=code,
        state=state,
        response=response,
        request=request,
    )
    return response


@router.get(
    "/logout",
    summary="Logout user session (Browser redirect)",
    description="Revokes the session on server/storage, clears browser cookie (Max-Age=0), and redirects.",
)
@router.post(
    "/logout",
    summary="Logout user session (API)",
    description="Revokes the session on server/storage, clears browser cookie (Max-Age=0), and returns JSON confirmation.",
)
def logout(request: Request, adapter: AuthAdapterDep) -> Response:
    accept_header = request.headers.get("accept", "")
    if request.method == "POST" or "application/json" in accept_header:
        json_resp = JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"result": "SUCCESS", "message": "Session terminated successfully"},
        )
        return adapter.logout(request, response=json_resp)

    return adapter.logout(request)


@router.get(
    "/session",
    summary="Check authenticated browser session",
    description="Resolves incoming session cookie to verified Identity. Returns None if unauthenticated.",
)
@router.get(
    "/me",
    summary="Check current identity",
    description="Alias for /session returning verified Identity.",
)
def get_session(request: Request, adapter: AuthAdapterDep) -> Response:
    identity = adapter.current_identity(request)
    if identity is None:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"authenticated": False, "identity": None},
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "authenticated": True,
            "identity": {
                "subject": identity.subject,
                "email": identity.email,
                "name": identity.name,
                "groups": identity.groups,
            },
        },
    )

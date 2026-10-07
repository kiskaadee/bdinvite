from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse

from ..auth import Identity, OIDCAuthAdapter
from ..auth.dependencies import get_auth_adapter
from ..schemas import LoginRequest, UserResponse

router = APIRouter(prefix="/auth", tags=["Auth"])


AuthAdapterDep = Annotated[OIDCAuthAdapter, Depends(get_auth_adapter)]


@router.get(
    "/login",
    summary="Iniciar flujo de autenticación OIDC",
    description="Redirige al proveedor de identidad OIDC con parámetros PKCE, nonce y state.",
)
def login_endpoint(
    request: Request,
    adapter: AuthAdapterDep,
):
    return adapter.login(request)


@router.post(
    "/login",
    response_model=UserResponse,
    summary="Autenticación directa de credenciales",
    description="Autentica usuario contra el proveedor OIDC y establece una sesión protegida contra fijación.",
)
def direct_login_endpoint(
    payload: LoginRequest,
    request: Request,
    response: Response,
    adapter: AuthAdapterDep,
):
    try:
        _, identity = adapter.oidc_client.authenticate_with_password(
            username=payload.username,
            password=payload.password,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Credenciales inválidas o error de autenticación: {e}",
        ) from e

    # Rotate pre-authentication session and issue post-auth session cookie
    adapter.create_session(
        identity=identity,
        request=request,
        response=response,
    )

    return UserResponse(
        subject=identity.subject,
        email=identity.email,
        name=identity.name,
        groups=identity.groups,
    )


@router.get(
    "/callback",
    summary="Callback de autorización OIDC",
    description="Procesa la redirección del IdP, intercambia el código de autorización e inicia la sesión.",
)
def callback_endpoint(
    request: Request,
    adapter: AuthAdapterDep,
    code: Annotated[
        str, Query(description="Código de autorización devuelto por el IdP")
    ],
    state: Annotated[str, Query(description="Token de estado para validación CSRF")],
):
    token_response = adapter.oidc_client.exchange_code(code=code, state=state)
    identity = adapter.oidc_client.extract_identity(token_response.claims)

    redirect_response = RedirectResponse(
        url="/birthday/admin", status_code=status.HTTP_302_FOUND
    )
    adapter.create_session(
        identity=identity,
        request=request,
        response=redirect_response,
    )
    return redirect_response


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Obtener identidad de la sesión activa",
    description="Resuelve la identidad del usuario actual a partir de la cookie de sesión o encabezado Bearer.",
)
def me_endpoint(
    request: Request,
    adapter: AuthAdapterDep,
):
    identity: Identity | None = adapter.current_identity(request)
    if identity is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return UserResponse(
        subject=identity.subject,
        email=identity.email,
        name=identity.name,
        groups=identity.groups,
    )


@router.post(
    "/logout",
    summary="Cerrar sesión de usuario (POST)",
    description="Revoca la sesión en el servidor y elimina la cookie de sesión del navegador con Max-Age=0.",
)
def logout_post_endpoint(
    request: Request,
    response: Response,
    adapter: AuthAdapterDep,
):
    raw_cookie = request.cookies.get(adapter.session_cookie_name)
    if raw_cookie:
        session_id = adapter.parse_session_cookie(raw_cookie)
        if session_id:
            adapter.session_store.delete_session(session_id)

    adapter.clear_session_cookie(response)
    return {"status": "ok", "message": "Logged out successfully"}


@router.get(
    "/logout",
    summary="Cerrar sesión de usuario (GET)",
    description="Revoca la sesión y redirige al usuario con la cookie eliminada.",
)
def logout_get_endpoint(
    request: Request,
    adapter: AuthAdapterDep,
):
    return adapter.logout(request)


__all__ = ["get_auth_adapter", "router"]

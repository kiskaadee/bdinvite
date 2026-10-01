import csv
import io
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import (
    InvitationConfigResponse,
    InvitationConfigUpdate,
    RSVPListResponse,
)
from ..services.config import get_config, seed_default_config, update_config
from ..services.rsvp import get_rsvps

router = APIRouter(tags=["Admin"])


def require_admin(
    remote_user: Annotated[
        str | None,
        Header(
            alias="Remote-User",
            description="Identidad de usuario autenticada e inyectada por Authelia ForwardAuth en el proxy Traefik",
            examples=["kiskaadee"],
        ),
    ] = None,
) -> str:
    """Security invariant: require verified Remote-User header from Authelia."""
    if not remote_user:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
        )
    return remote_user


AdminDep = Annotated[str, Depends(require_admin)]
DbDep = Annotated[Session, Depends(get_db)]

ADMIN_401 = {
    401: {
        "description": "No autenticado. Se requiere la cabecera `Remote-User` provista por Authelia ForwardAuth."
    }
}


@router.get(
    "/rsvps",
    response_model=RSVPListResponse,
    summary="Listar asistentes confirmados",
    description=(
        "Obtiene el total y la lista de todos los invitados que han confirmado asistencia. "
        "Permite filtrado por coincidencia parcial (`?search=`) sobre nombre, teléfono o correo."
    ),
    responses={
        200: {"model": RSVPListResponse, "description": "Lista de confirmaciones obtenida."},
        **ADMIN_401,
    },
)
def list_rsvps(
    admin: AdminDep,
    db: DbDep,
    search: Annotated[
        str | None,
        Query(
            description="Término de búsqueda opcional (subcadena en nombre, teléfono o email)",
            examples=["Andrés"],
        ),
    ] = None,
):
    rsvps = get_rsvps(db, search=search)
    return RSVPListResponse(
        count=len(rsvps),
        rsvps=rsvps,  # type: ignore[arg-type]
    )


@router.get(
    "/export",
    summary="Exportar confirmaciones en formato CSV",
    description=(
        "Genera dinámicamente un archivo CSV con las columnas: `name`, `phone`, `email` y `created_at`. "
        "Descarga el archivo directamente con encabezados `Content-Disposition: attachment`."
    ),
    responses={
        200: {
            "content": {"text/csv": {}},
            "description": "Descarga del archivo CSV `rsvps.csv`.",
        },
        **ADMIN_401,
    },
)
def export_rsvps_csv(
    admin: AdminDep,
    db: DbDep,
):
    rsvps = get_rsvps(db)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["name", "phone", "email", "created_at"])

    for item in rsvps:
        created_iso = item.created_at.isoformat() if item.created_at else ""
        writer.writerow([item.name, item.phone, item.email or "", created_iso])

    csv_content = output.getvalue()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="rsvps.csv"'},
    )


@router.get(
    "/config",
    response_model=InvitationConfigResponse,
    summary="Obtener configuración editable",
    description="Retorna el objeto completo de configuración para poblar el formulario de administración.",
    responses={
        200: {"model": InvitationConfigResponse, "description": "Configuración obtenida correctamente."},
        **ADMIN_401,
    },
)
def get_admin_config(
    admin: AdminDep,
    db: DbDep,
):
    config = get_config(db)
    if not config:
        config = seed_default_config(db)
    return config


@router.put(
    "/config",
    response_model=InvitationConfigResponse,
    summary="Actualizar configuración de la invitación",
    description=(
        "Reemplaza los valores de la configuración singleton del evento. "
        "Aplica validación de fecha ISO, hora en formato militar 24h y zona horaria válida IANA. "
        "Los cambios toman efecto de inmediato sin requerir recarga del contenedor."
    ),
    responses={
        200: {"model": InvitationConfigResponse, "description": "Configuración actualizada con éxito."},
        **ADMIN_401,
    },
)
def update_admin_config(
    update_in: InvitationConfigUpdate,
    admin: AdminDep,
    db: DbDep,
):
    updated = update_config(db, update_in)
    return updated

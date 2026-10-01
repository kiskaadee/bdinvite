import csv
import io
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..schemas import (
    GenerateMapPreviewRequest,
    GenerateMapPreviewResponse,
    InvitationConfigResponse,
    InvitationConfigUpdate,
    RSVPAdminItem,
    RSVPListResponse,
    RSVPUpdate,
)
from ..services.config import get_config, seed_default_config, update_config
from ..services.map_preview import generate_map_preview_image, resolve_google_maps_coordinates
from ..services.rsvp import delete_rsvp, get_rsvps, update_rsvp

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


@router.delete(
    "/rsvps/{rsvp_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar confirmación de asistencia",
    description="Elimina permanentemente un registro de RSVP por su identificador.",
    responses={
        204: {"description": "Registro eliminado con éxito."},
        404: {"description": "Registro no encontrado."},
        **ADMIN_401,
    },
)
def delete_rsvp_endpoint(
    rsvp_id: int,
    admin: AdminDep,
    db: DbDep,
):
    deleted = delete_rsvp(db, rsvp_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró el registro con ID {rsvp_id}",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/rsvps/{rsvp_id}",
    response_model=RSVPAdminItem,
    summary="Editar una confirmación de asistencia",
    description="Actualiza el nombre, teléfono o correo de un asistente confirmado.",
    responses={
        200: {"model": RSVPAdminItem, "description": "Registro actualizado exitosamente."},
        400: {"description": "Error de validación en los campos proporcionados."},
        404: {"description": "Registro no encontrado."},
        409: {"description": "El número de teléfono ya está registrado por otro asistente."},
        **ADMIN_401,
    },
)
def update_rsvp_endpoint(
    rsvp_id: int,
    payload: RSVPUpdate,
    admin: AdminDep,
    db: DbDep,
):
    status_res, updated = update_rsvp(db, rsvp_id, payload)

    if status_res == "NOT_FOUND":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró el registro con ID {rsvp_id}",
        )
    if status_res == "DUPLICATE":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El número de teléfono ya está registrado para otro asistente.",
        )
    assert updated is not None
    return updated



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
        created_iso = ""
        if item.created_at:
            dt = item.created_at if item.created_at.tzinfo else item.created_at.replace(tzinfo=UTC)
            created_iso = dt.isoformat()
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
        "Si la URL de Google Maps cambió, valida y regenera automáticamente la vista previa del mapa. "
        "Aplica validación de fecha ISO, hora en formato militar 24h y zona horaria válida IANA. "
        "Los cambios toman efecto de inmediato sin requerir recarga del contenedor."
    ),
    responses={
        200: {"model": InvitationConfigResponse, "description": "Configuración actualizada con éxito."},
        **ADMIN_401,
    },
)
async def update_admin_config(
    update_in: InvitationConfigUpdate,
    admin: AdminDep,
    db: DbDep,
):
    current = get_config(db)
    if not current:
        current = seed_default_config(db)

    # Condition: Trigger generation ONLY if map_url was changed
    if current.map_url != update_in.map_url:
        try:
            fallback = f"{update_in.address_lines}\n{update_in.address_name}"
            lat, lng, _ = await resolve_google_maps_coordinates(
                update_in.map_url, fallback_query=fallback
            )
            await generate_map_preview_image(lat, lng)
            update_in.map_preview_url = f"{settings.BASE_PATH}/api/map-preview.png"
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(err),
            ) from err
        except Exception as err:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al generar la vista previa del mapa: {err}",
            ) from err

    updated = update_config(db, update_in)
    return updated


@router.post(
    "/map-preview/generate",
    response_model=GenerateMapPreviewResponse,
    summary="Regenerar la vista previa del mapa",
    description=(
        "Genera o regenera la imagen del mapa en disco para la URL provista o la configurada actualmente, "
        "sin realizar escrituras innecesarias a la base de datos."
    ),
    responses={
        200: {"model": GenerateMapPreviewResponse, "description": "Vista previa generada exitosamente."},
        **ADMIN_401,
    },
)
async def regenerate_map_preview_endpoint(
    admin: AdminDep,
    db: DbDep,
    payload: GenerateMapPreviewRequest | None = None,
):
    current = get_config(db)
    target_url = payload.map_url.strip() if (payload and payload.map_url) else None
    if not target_url:
        if not current or not current.map_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se proporcionó una URL de Google Maps ni existe una guardada en la configuración.",
            )
        target_url = current.map_url

    try:
        fallback = f"{current.address_lines}\n{current.address_name}" if current else None
        lat, lng, _ = await resolve_google_maps_coordinates(
            target_url, fallback_query=fallback
        )
        await generate_map_preview_image(lat, lng)

        timestamp = int(datetime.now(UTC).timestamp())
        return GenerateMapPreviewResponse(
            map_preview_url=f"{settings.BASE_PATH}/api/map-preview.png?t={timestamp}",
            lat=lat,
            lng=lng,
            message="Vista previa del mapa generada exitosamente.",
        )
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(err),
        ) from err
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al generar la vista previa del mapa: {err}",
        ) from err


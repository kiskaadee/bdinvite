from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import (
    RSVPCreate,
    RSVPDuplicateResponse,
    RSVPErrorResponse,
    RSVPSuccessResponse,
    RSVPValidationErrorResponse,
)
from ..services.rsvp import create_rsvp

router = APIRouter(tags=["RSVP"])

DbDep = Annotated[Session, Depends(get_db)]


@router.post(
    "/rsvp",
    status_code=status.HTTP_201_CREATED,
    summary="Registrar confirmación de asistencia",
    description=(
        "Recibe y procesa la confirmación de asistencia de un invitado. "
        "El número telefónico es normalizado estrictamente al formato móvil colombiano de 10 dígitos "
        "(comenzando en 3). Si el teléfono ya existe en el sistema, retorna un discriminador semántico "
        "`DUPLICATE` con código HTTP 409."
    ),
    responses={
        201: {
            "model": RSVPSuccessResponse,
            "description": "Confirmación registrada exitosamente.",
        },
        409: {
            "model": RSVPDuplicateResponse,
            "description": "El número de teléfono ya ha sido registrado previamente.",
        },
        422: {
            "model": RSVPValidationErrorResponse,
            "description": "Fallo de validación de formato en los datos ingresados.",
        },
        500: {
            "model": RSVPErrorResponse,
            "description": "Error no controlado al persistir en la base de datos.",
        },
    },
)
def submit_rsvp(rsvp_in: RSVPCreate, db: DbDep):
    try:
        result_status, new_rsvp = create_rsvp(db, rsvp_in)
        if result_status == "DUPLICATE":
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={"result": "DUPLICATE"},
            )
        assert new_rsvp is not None
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={"result": "SUCCESS", "name": new_rsvp.name},
        )
    except ValueError as e:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"result": "VALIDATION_ERROR", "errors": {"phone": str(e)}},
        )
    except SQLAlchemyError:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"result": "ERROR"},
        )

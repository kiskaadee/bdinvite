from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import RSVPCreate
from ..services.rsvp import create_rsvp

router = APIRouter(tags=["RSVP"])

DbDep = Annotated[Session, Depends(get_db)]


@router.post("/rsvp", status_code=status.HTTP_201_CREATED)
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

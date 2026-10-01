from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import InvitationConfigResponse
from ..services.config import get_config, seed_default_config

router = APIRouter(tags=["Config"])

DbDep = Annotated[Session, Depends(get_db)]


@router.get("/config", response_model=InvitationConfigResponse)
def read_config(db: DbDep):
    config = get_config(db)
    if not config:
        config = seed_default_config(db)

    if not config:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"result": "ERROR"},
        )
    return config

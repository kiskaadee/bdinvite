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
    remote_user: Annotated[str | None, Header(alias="Remote-User")] = None,
) -> str:
    """Security invariant: require verified Remote-User header from Authelia."""
    if not remote_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return remote_user


AdminDep = Annotated[str, Depends(require_admin)]
DbDep = Annotated[Session, Depends(get_db)]


@router.get("/rsvps", response_model=RSVPListResponse)
def list_rsvps(
    admin: AdminDep,
    db: DbDep,
    search: Annotated[str | None, Query()] = None,
):
    rsvps = get_rsvps(db, search=search)
    return RSVPListResponse(
        count=len(rsvps),
        rsvps=rsvps,  # type: ignore[arg-type]
    )


@router.get("/export")
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


@router.get("/config", response_model=InvitationConfigResponse)
def get_admin_config(
    admin: AdminDep,
    db: DbDep,
):
    config = get_config(db)
    if not config:
        config = seed_default_config(db)
    return config


@router.put("/config", response_model=InvitationConfigResponse)
def update_admin_config(
    update_in: InvitationConfigUpdate,
    admin: AdminDep,
    db: DbDep,
):
    updated = update_config(db, update_in)
    return updated

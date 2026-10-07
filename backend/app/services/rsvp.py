from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import RSVP
from ..schemas import RSVPCreate, RSVPUpdate, normalize_phone


def create_rsvp(db: Session, rsvp_in: RSVPCreate) -> tuple[str, RSVP | None]:
    """Create an RSVP record.

    Returns:
        (status, rsvp_obj) where status is 'SUCCESS' or 'DUPLICATE'.
    Raises:
        ValueError if phone or field normalization fails.
    """
    normalized_phone = normalize_phone(rsvp_in.phone)

    # Check existence beforehand or rely on DB IntegrityError
    existing = db.execute(
        select(RSVP).where(RSVP.phone == normalized_phone)
    ).scalar_one_or_none()
    if existing:
        return "DUPLICATE", None

    new_rsvp = RSVP(
        name=rsvp_in.name,
        phone=normalized_phone,
        email=rsvp_in.email,
    )

    try:
        db.add(new_rsvp)
        db.commit()
        db.refresh(new_rsvp)
        return "SUCCESS", new_rsvp
    except IntegrityError:
        db.rollback()
        return "DUPLICATE", None
    except Exception:
        db.rollback()
        raise


def get_rsvps(db: Session, search: str | None = None) -> list[RSVP]:
    """Retrieve RSVPs, optionally filtered by search term."""
    query = select(RSVP).order_by(RSVP.created_at.desc())
    if search:
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                RSVP.name.ilike(term),
                RSVP.phone.ilike(term),
                RSVP.email.ilike(term),
            )
        )
    return list(db.execute(query).scalars().all())


def get_rsvp_count(db: Session) -> int:
    """Get total count of RSVPs."""
    query = select(RSVP)
    return len(list(db.execute(query).scalars().all()))


def delete_rsvp(db: Session, rsvp_id: int) -> bool:
    """Delete an RSVP record by its ID. Returns True if deleted, False if not found."""
    rsvp = db.execute(select(RSVP).where(RSVP.id == rsvp_id)).scalar_one_or_none()
    if not rsvp:
        return False
    db.delete(rsvp)
    db.commit()
    return True


def update_rsvp(
    db: Session,
    rsvp_id: int,
    update_in: RSVPUpdate,
) -> tuple[str, RSVP | None]:
    """Update an RSVP record using validated RSVPUpdate schema.

    Returns:
        ("SUCCESS", rsvp)
        ("NOT_FOUND", None)
        ("DUPLICATE", None)
    """
    rsvp = db.execute(select(RSVP).where(RSVP.id == rsvp_id)).scalar_one_or_none()
    if not rsvp:
        return "NOT_FOUND", None

    if update_in.phone is not None:
        existing = db.execute(
            select(RSVP).where(RSVP.phone == update_in.phone, RSVP.id != rsvp_id)
        ).scalar_one_or_none()
        if existing:
            return "DUPLICATE", None
        rsvp.phone = update_in.phone

    if update_in.name is not None:
        rsvp.name = update_in.name

    if update_in.email is not None:
        rsvp.email = update_in.email

    try:
        db.commit()
        db.refresh(rsvp)
        return "SUCCESS", rsvp
    except IntegrityError:
        db.rollback()
        return "DUPLICATE", None
    except Exception:
        db.rollback()
        raise

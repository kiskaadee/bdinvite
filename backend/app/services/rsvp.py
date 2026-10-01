import re

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import RSVP
from ..schemas import RSVPCreate


def normalize_phone(raw: str) -> str:
    """Normalize Colombian mobile numbers.

    Rules:
    1. Strip all non-digit characters.
    2. If starts with '57' and has 12 digits, strip '57'.
    3. Must be exactly 10 digits and start with '3'.
    """
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("57") and len(digits) == 12:
        digits = digits[2:]

    if len(digits) != 10 or not digits.startswith("3"):
        raise ValueError("Formato de teléfono inválido")

    return digits


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

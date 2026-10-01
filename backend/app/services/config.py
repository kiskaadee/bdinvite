from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import InvitationConfig
from ..schemas import InvitationConfigUpdate


def seed_default_config(db: Session) -> InvitationConfig:
    """Ensure the singleton config row (id=1) exists with default values."""
    config = db.execute(
        select(InvitationConfig).where(InvitationConfig.id == 1)
    ).scalar_one_or_none()

    if not config:
        config = InvitationConfig(id=1)
        db.add(config)
        db.commit()
        db.refresh(config)

    return config


def get_config(db: Session) -> InvitationConfig | None:
    """Retrieve the current invitation config."""
    return db.execute(
        select(InvitationConfig).where(InvitationConfig.id == 1)
    ).scalar_one_or_none()


def update_config(db: Session, update_in: InvitationConfigUpdate) -> InvitationConfig:
    """Update the invitation config singleton."""
    config = get_config(db)
    if not config:
        config = seed_default_config(db)

    for field, value in update_in.model_dump().items():
        setattr(config, field, value)

    config.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(config)
    return config

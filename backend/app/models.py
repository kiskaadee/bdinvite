from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class RSVP(Base):
    __tablename__ = "rsvps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(
        String(20), nullable=False, unique=True, index=True
    )
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class InvitationConfig(Base):
    __tablename__ = "invitation_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    title: Mapped[str] = mapped_column(
        String(200), nullable=False, default="Birthday Party"
    )
    invitation_text: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        default="You're invited to the birthday party honoring",
    )
    honoree_name: Mapped[str] = mapped_column(
        String(200), nullable=False, default="Isabelle Snow"
    )
    event_date: Mapped[str] = mapped_column(
        String(20), nullable=False, default="2026-10-28"
    )
    event_time: Mapped[str] = mapped_column(String(10), nullable=False, default="19:00")
    event_timezone: Mapped[str] = mapped_column(
        String(50), nullable=False, default="America/Bogota"
    )
    address_name: Mapped[str] = mapped_column(
        String(200), nullable=False, default="Fresco Ristorante"
    )
    address_lines: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="514 S Brand Blvd\nGlendale, CA 91204",
    )
    map_preview_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        default="https://tile.openstreetmap.org/15/8802/13443.png",
    )
    map_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        default="https://maps.google.com/?q=Fresco+Ristorante+Glendale+CA",
    )
    rsvp_heading: Mapped[str] = mapped_column(
        String(100), nullable=False, default="¿Nos vemos?"
    )
    rsvp_cta: Mapped[str] = mapped_column(
        String(100), nullable=False, default="CONFIRMA TU ASISTENCIA"
    )
    submit_label: Mapped[str] = mapped_column(
        String(100), nullable=False, default="TE VEO AHÍ"
    )
    msg_success: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
        default="¡Perfecto! Tu asistencia ha sido confirmada.",
    )
    msg_success_greeting: Mapped[str] = mapped_column(
        String(100), nullable=False, default="Gracias, {name}."
    )
    msg_duplicate: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
        default="Parece que ya tenemos tus datos registrados.",
    )
    msg_error: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
        default="No pudimos registrar tu asistencia. Inténtalo nuevamente.",
    )
    msg_config_error: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
        default="No pudimos cargar la invitación. Inténtalo nuevamente.",
    )
    countdown_label: Mapped[str] = mapped_column(
        String(100), nullable=False, default="NOS VEMOS EN"
    )
    countdown_in_progress: Mapped[str] = mapped_column(
        String(100), nullable=False, default="EVENTO EN CURSO"
    )
    countdown_finished: Mapped[str] = mapped_column(
        String(100), nullable=False, default="EVENTO FINALIZADO"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

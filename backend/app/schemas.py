import re
from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RSVPCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., min_length=1, max_length=50)
    email: str | None = Field(default=None, max_length=255)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: str) -> str:
        cleaned = " ".join(v.strip().split())
        if not cleaned:
            raise ValueError("El nombre no puede estar vacío.")
        return cleaned

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = v.strip()
        if not cleaned:
            return None
        # Basic email regex
        email_regex = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
        if not re.match(email_regex, cleaned):
            raise ValueError("Formato de correo electrónico inválido")
        return cleaned.lower()


class RSVPSuccessResponse(BaseModel):
    result: Literal["SUCCESS"] = "SUCCESS"
    name: str


class RSVPDuplicateResponse(BaseModel):
    result: Literal["DUPLICATE"] = "DUPLICATE"


class RSVPValidationErrorResponse(BaseModel):
    result: Literal["VALIDATION_ERROR"] = "VALIDATION_ERROR"
    errors: dict[str, str]


class RSVPErrorResponse(BaseModel):
    result: Literal["ERROR"] = "ERROR"


class RSVPAdminItem(BaseModel):
    id: int
    name: str
    phone: str
    email: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RSVPListResponse(BaseModel):
    count: int
    rsvps: list[RSVPAdminItem]


class InvitationConfigBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    invitation_text: str = Field(..., min_length=1, max_length=500)
    honoree_name: str = Field(..., min_length=1, max_length=200)
    event_date: str = Field(..., description="ISO 8601 Date YYYY-MM-DD")
    event_time: str = Field(..., description="24-hour time HH:MM")
    event_timezone: str = Field(..., description="IANA timezone identifier")
    address_name: str = Field(..., min_length=1, max_length=200)
    address_lines: str = Field(..., min_length=1)
    map_preview_url: str = Field(..., min_length=1, max_length=500)
    map_url: str = Field(..., min_length=1, max_length=500)
    rsvp_heading: str = Field(..., min_length=1, max_length=100)
    rsvp_cta: str = Field(..., min_length=1, max_length=100)
    submit_label: str = Field(..., min_length=1, max_length=100)
    msg_success: str = Field(..., min_length=1, max_length=300)
    msg_success_greeting: str = Field(..., min_length=1, max_length=100)
    msg_duplicate: str = Field(..., min_length=1, max_length=300)
    msg_error: str = Field(..., min_length=1, max_length=300)
    msg_config_error: str = Field(..., min_length=1, max_length=300)
    countdown_label: str = Field(..., min_length=1, max_length=100)
    countdown_in_progress: str = Field(..., min_length=1, max_length=100)
    countdown_finished: str = Field(..., min_length=1, max_length=100)

    @field_validator("event_date")
    @classmethod
    def validate_event_date(cls, v: str) -> str:
        match = re.match(r"^\d{4}-\d{2}-\d{2}$", v.strip())
        if not match:
            raise ValueError("La fecha debe estar en formato YYYY-MM-DD")
        try:
            date.fromisoformat(v.strip())
        except ValueError as err:
            raise ValueError("Fecha de evento inválida") from err
        return v.strip()

    @field_validator("event_time")
    @classmethod
    def validate_event_time(cls, v: str) -> str:
        match = re.match(r"^([01]\d|2[0-3]):([0-5]\d)$", v.strip())
        if not match:
            raise ValueError("La hora debe estar en formato HH:MM (24 horas)")
        return v.strip()

    @field_validator("event_timezone")
    @classmethod
    def validate_event_timezone(cls, v: str) -> str:
        clean = v.strip()
        try:
            ZoneInfo(clean)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError(f"Zona horaria IANA desconocida: {clean}")
        return clean


class InvitationConfigUpdate(InvitationConfigBase):
    pass


class InvitationConfigResponse(InvitationConfigBase):
    id: int = 1
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

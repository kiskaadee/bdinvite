import re
from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class RSVPCreate(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Nombre completo del invitado",
        examples=["Andrés García"],
    )
    phone: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Número móvil en formato colombiano (10 dígitos, con o sin prefijo +57)",
        examples=["+57 300 123 4567"],
    )
    email: str | None = Field(
        default=None,
        max_length=255,
        description="Correo electrónico opcional para confirmación y recordatorios",
        examples=["andres@example.com"],
    )

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: str) -> str:
        cleaned = " ".join(v.strip().split())
        if not cleaned:
            raise ValueError("El nombre no puede estar vacío.")
        return cleaned

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return normalize_phone(v)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = v.strip()
        if not cleaned:
            return None
        email_regex = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
        if not re.match(email_regex, cleaned):
            raise ValueError("Formato de correo electrónico inválido")
        return cleaned.lower()


class RSVPUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Nombre completo del invitado",
        examples=["Andrés García"],
    )
    phone: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
        description="Número móvil en formato colombiano (10 dígitos, con o sin prefijo +57)",
        examples=["+57 300 123 4567"],
    )
    email: str | None = Field(
        default=None,
        max_length=255,
        description="Correo electrónico opcional para confirmación y recordatorios",
        examples=["andres@example.com"],
    )

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = " ".join(v.strip().split())
        if not cleaned:
            raise ValueError("El nombre no puede estar vacío.")
        return cleaned

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return normalize_phone(v)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = v.strip()
        if not cleaned:
            return None
        email_regex = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
        if not re.match(email_regex, cleaned):
            raise ValueError("Formato de correo electrónico inválido")
        return cleaned.lower()




class RSVPSuccessResponse(BaseModel):
    result: Literal["SUCCESS"] = Field(
        default="SUCCESS",
        description="Discriminador semántico de confirmación exitosa",
    )
    name: str = Field(
        ...,
        description="Nombre del invitado registrado",
        examples=["Andrés García"],
    )


class RSVPDuplicateResponse(BaseModel):
    result: Literal["DUPLICATE"] = Field(
        default="DUPLICATE",
        description="Indica que el número de teléfono móvil ya tiene una confirmación registrada",
    )


class RSVPValidationErrorResponse(BaseModel):
    result: Literal["VALIDATION_ERROR"] = Field(
        default="VALIDATION_ERROR",
        description="Indica error de validación en los datos enviados",
    )
    errors: dict[str, str] = Field(
        ...,
        description="Mapa de nombres de campos con sus respectivos mensajes de error",
        examples=[{"phone": "Formato de teléfono inválido"}],
    )


class RSVPErrorResponse(BaseModel):
    result: Literal["ERROR"] = Field(
        default="ERROR",
        description="Error interno no controlado durante el procesamiento",
    )


class RSVPAdminItem(BaseModel):
    id: int = Field(..., description="Identificador único del registro en base de datos", examples=[1])
    name: str = Field(..., description="Nombre completo del asistente", examples=["Ana García"])
    phone: str = Field(..., description="Número telefónico normalizado a 10 dígitos", examples=["3001234567"])
    email: str | None = Field(default=None, description="Correo electrónico registrado", examples=["ana@example.com"])
    created_at: datetime = Field(..., description="Marca de tiempo UTC de la confirmación")

    model_config = ConfigDict(from_attributes=True)


class RSVPListResponse(BaseModel):
    count: int = Field(..., description="Cantidad total de confirmaciones encontradas", examples=[37])
    rsvps: list[RSVPAdminItem] = Field(..., description="Lista de asistentes confirmados")


class InvitationConfigBase(BaseModel):
    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Título principal de la portada (tipografía script grande)",
        examples=["Birthday Party"],
    )
    invitation_text: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Texto introductorio de la invitación",
        examples=["You're invited to the birthday party honoring"],
    )
    honoree_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Nombre del homenajeado(a)",
        examples=["Isabelle Snow"],
    )
    event_date: str = Field(
        ...,
        description="Fecha del evento en formato ISO 8601 (YYYY-MM-DD)",
        examples=["2026-10-28"],
    )
    event_time: str = Field(
        ...,
        description="Hora de inicio del evento en formato 24 horas (HH:MM)",
        examples=["19:00"],
    )
    event_timezone: str = Field(
        ...,
        description="Identificador de zona horaria IANA para el cálculo exacto de la cuenta regresiva",
        examples=["America/Bogota"],
    )
    address_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Nombre del restaurante, salón o recinto",
        examples=["Fresco Ristorante"],
    )
    address_lines: str = Field(
        ...,
        min_length=1,
        description="Líneas de dirección del lugar (separadas por salto de línea)",
        examples=["514 S Brand Blvd\nGlendale, CA 91204"],
    )
    map_preview_url: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="URL de la imagen miniatura que se muestra en el widget circular",
        examples=["https://tile.openstreetmap.org/15/8802/13443.png"],
    )
    map_url: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Enlace externo a Google Maps u otro servicio de navegación",
        examples=["https://maps.google.com/?q=Fresco+Ristorante+Glendale+CA"],
    )
    rsvp_heading: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Encabezado del formulario de confirmación",
        examples=["¿Nos vemos?"],
    )
    rsvp_cta: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Texto del botón CTA en la portada que desplaza al formulario",
        examples=["CONFIRMA TU ASISTENCIA"],
    )
    submit_label: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Texto del botón de envío del formulario",
        examples=["TE VEO AHÍ"],
    )
    msg_success: str = Field(
        ...,
        min_length=1,
        max_length=300,
        description="Mensaje principal tras confirmar asistencia",
        examples=["¡Perfecto! Tu asistencia ha sido confirmada."],
    )
    msg_success_greeting: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Saludo personalizado; {name} se reemplaza con el nombre del invitado",
        examples=["Gracias, {name}."],
    )
    msg_duplicate: str = Field(
        ...,
        min_length=1,
        max_length=300,
        description="Mensaje mostrado si el número ya está registrado",
        examples=["Parece que ya tenemos tus datos registrados."],
    )
    msg_error: str = Field(
        ...,
        min_length=1,
        max_length=300,
        description="Mensaje en caso de fallo general del servidor",
        examples=["No pudimos registrar tu asistencia. Inténtalo nuevamente."],
    )
    msg_config_error: str = Field(
        ...,
        min_length=1,
        max_length=300,
        description="Mensaje si la configuración no puede cargarse en el navegador",
        examples=["No pudimos cargar la invitación. Inténtalo nuevamente."],
    )
    countdown_label: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Etiqueta superior del contador regresivo",
        examples=["NOS VEMOS EN"],
    )
    countdown_in_progress: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Texto mostrado cuando el evento está ocurriendo en tiempo real",
        examples=["EVENTO EN CURSO"],
    )
    countdown_finished: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Texto mostrado cuando el evento ha culminado",
        examples=["EVENTO FINALIZADO"],
    )

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

    @field_validator("map_url")
    @classmethod
    def validate_map_url(cls, v: str) -> str:
        from .services.map_preview import validate_google_maps_url_format

        clean = v.strip()
        validate_google_maps_url_format(clean)
        return clean


class InvitationConfigUpdate(InvitationConfigBase):
    pass


class InvitationConfigResponse(InvitationConfigBase):
    id: int = Field(default=1, description="Identificador único del registro singleton (siempre 1)")
    updated_at: datetime | None = Field(default=None, description="Última modificación en UTC")

    model_config = ConfigDict(from_attributes=True)


class GenerateMapPreviewRequest(BaseModel):
    map_url: str | None = Field(
        default=None,
        description="URL de Google Maps a procesar. Si se omite, se usa la configurada actualmente.",
        examples=["https://maps.app.goo.gl/abcd1234efgh5678"],
    )


class GenerateMapPreviewResponse(BaseModel):
    map_preview_url: str = Field(description="URL para acceder a la imagen de vista previa generada")
    lat: float = Field(description="Latitud resuelta")
    lng: float = Field(description="Longitud resuelta")
    message: str = Field(default="Vista previa generada con éxito")

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import Base, SessionLocal, engine
from .routes import admin, auth, config, rsvp
from .services.config import seed_default_config


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Ensure tables are created on startup
    Base.metadata.create_all(bind=engine)
    # Seed default configuration row
    with SessionLocal() as db:
        seed_default_config(db)
    yield


app = FastAPI(
    title="Birthday Invitation API",
    version="1.0.0",
    description=(
        "API REST para la invitación interactiva de cumpleaños con sistema RSVP.\n\n"
        "### Arquitectura de Seguridad\n"
        "- **Rutas Públicas (`/birthday/api/*`)**: Acceso abierto para los invitados.\n"
        "- **Rutas Administrativas (`/birthday/api/admin/*`)**: Protegidas por autenticación de sesión OIDC "
        "y autorización basada en grupos (`bdinvite_admins`)."
    ),
    openapi_tags=[
        {
            "name": "RSVP",
            "description": "Registro y validación de confirmación de asistencia para invitados.",
        },
        {
            "name": "Config",
            "description": "Consulta pública de la configuración singleton del evento.",
        },
        {
            "name": "Admin",
            "description": "Gestión de asistentes, descarga CSV y edición de contenido protegida por autenticación y grupo administrativo.",
        },
    ],
    lifespan=lifespan,
    docs_url="/birthday/api/docs",
    openapi_url="/birthday/api/openapi.json",
)


@app.get("/docs", include_in_schema=False)
async def redirect_to_docs():
    return RedirectResponse(url="/birthday/api/docs")


# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handler to normalize validation errors into our contract
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors: dict[str, str] = {}
    for err in exc.errors():
        loc = err.get("loc", [])
        field = str(loc[-1]) if loc else "general"
        msg = err.get("msg", "Entrada inválida")
        # Clean standard Pydantic error prefixes if present
        msg = msg.removeprefix("Value error, ")
        errors[field] = msg

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"result": "VALIDATION_ERROR", "errors": errors},
    )


# Register API routes with exact path prefixes per specification
app.include_router(rsvp.router, prefix="/birthday/api")
app.include_router(config.router, prefix="/birthday/api")
app.include_router(auth.router, prefix="/birthday/api")
app.include_router(admin.router, prefix="/birthday/api/admin")


@app.get(
    "/birthday/api/map-preview.png",
    tags=["Config"],
    summary="Obtener imagen de vista previa del mapa generada",
    description="Retorna el archivo PNG de vista previa del mapa generado centrado en la ubicación.",
)
async def get_map_preview():
    if settings.map_preview_file.exists():
        return FileResponse(
            settings.map_preview_file,
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=300"},
        )
    return RedirectResponse(
        url="https://tile.openstreetmap.org/15/8802/13443.png",
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )


# Static files and SPA serving
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
ASSETS_DIR = os.path.join(STATIC_DIR, "assets")

if os.path.isdir(ASSETS_DIR):
    app.mount("/birthday/assets", StaticFiles(directory=ASSETS_DIR), name="assets")


@app.get("/birthday", include_in_schema=False)
async def redirect_birthday_slash():
    return RedirectResponse(url="/birthday/", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@app.get("/birthday/", include_in_schema=False)
@app.get("/birthday/{full_path:path}", include_in_schema=False)
async def spa_catch_all(full_path: str = ""):
    if full_path:
        requested_file = os.path.join(STATIC_DIR, full_path)
        if os.path.isfile(requested_file):
            return FileResponse(requested_file)

    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.isfile(index_file):
        return FileResponse(index_file)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "service": "bdinvite",
            "status": "ready",
            "message": "Frontend static assets not yet compiled in this environment.",
        },
    )

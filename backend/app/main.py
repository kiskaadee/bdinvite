import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .database import Base, SessionLocal, engine
from .routes import admin, config, rsvp
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
    lifespan=lifespan,
    docs_url="/birthday/api/docs",
    openapi_url="/birthday/api/openapi.json",
)

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
app.include_router(admin.router, prefix="/birthday/api/admin")


# Static files and SPA serving
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
ASSETS_DIR = os.path.join(STATIC_DIR, "assets")

if os.path.isdir(ASSETS_DIR):
    app.mount("/birthday/assets", StaticFiles(directory=ASSETS_DIR), name="assets")


@app.get("/birthday")
@app.get("/birthday/{full_path:path}")
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

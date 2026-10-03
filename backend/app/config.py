from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    SERVICE_NAME: str = "bdinvite"
    SERVICE_DOMAIN: str = "demos.roadtotech.me"
    BASE_PATH: str = "/birthday"
    APP_PORT: int = 8000
    DATABASE_URL: str = "sqlite:///./data/bdinvite.db"
    DATA_DIR: str = "./data"

    # OIDC & Auth Settings
    OIDC_ISSUER: str = "http://localhost:8088/default"
    OIDC_CLIENT_ID: str = "bdinvite-client"
    OIDC_CLIENT_SECRET: str | None = "bdinvite-secret"
    OIDC_REDIRECT_URI: str = "http://localhost:8000/birthday/api/auth/callback"
    OIDC_GROUPS_CLAIM: str = "groups"
    OIDC_GROUP_CLAIM_PATH: str | None = None

    # Browser Session Management Settings
    SESSION_COOKIE_NAME: str = "bdinvite_session"
    SESSION_COOKIE_SECURE: bool = False
    SESSION_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    SESSION_COOKIE_PATH: str = "/"
    SESSION_COOKIE_DOMAIN: str | None = None
    SESSION_EXPIRE_SECONDS: int = 86400

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def data_path(self) -> Path:
        return Path(self.DATA_DIR).resolve()

    @property
    def map_preview_file(self) -> Path:
        return self.data_path / "map_preview.png"


settings = Settings()


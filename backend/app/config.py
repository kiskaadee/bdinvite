from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """BDInvite Application Configuration.

    Supports two primary deployment modes:
    1. Direct Standalone Mode (local dev & testing):
       - Direct HTTP access on port 8000
       - OIDC_ISSUER pointing to local IdP (e.g. mock-oauth2-server or Keycloak)
       - SESSION_COOKIE_SECURE = False
       - OIDC_REDIRECT_URI = "http://localhost:8000/birthday/api/auth/callback"
    2. Homelab Production Mode:
       - Deployed behind Traefik reverse proxy terminating TLS
       - OIDC_ISSUER pointing to Authelia (e.g. https://auth.roadtotech.me)
       - SESSION_COOKIE_SECURE = True (required for HTTPS cookie transmission)
       - SESSION_COOKIE_NAME = "bdinvite_session" (or prefixed "__Host-bdinvite_session")
       - OIDC_REDIRECT_URI = "https://demos.roadtotech.me/birthday/api/auth/callback"
    """

    SERVICE_NAME: str = "bdinvite"
    SERVICE_DOMAIN: str = "demos.roadtotech.me"
    BASE_PATH: str = "/birthday"
    APP_PORT: int = 8000
    DATABASE_URL: str = "sqlite:///./data/bdinvite.db"
    DATA_DIR: str = "./data"

    # OIDC Provider & SSO Settings
    OIDC_ISSUER: str = "http://localhost:8088/default"
    OIDC_CLIENT_ID: str = "bdinvite-client"
    OIDC_CLIENT_SECRET: str = "bdinvite-secret"
    OIDC_REDIRECT_URI: str = "http://localhost:8000/birthday/api/auth/callback"
    OIDC_GROUPS_CLAIM: str = "groups"

    # Browser Session & Cookie Security Settings
    SESSION_COOKIE_NAME: str = "bdinvite_session"
    SESSION_COOKIE_SECURE: bool = False
    SESSION_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_MAX_AGE_SECONDS: int = 86400
    SESSION_SECRET_KEY: str = "bdinvite-session-secret-key-change-in-prod"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def is_standalone(self) -> bool:
        """Returns True if operating in direct standalone (development) mode."""
        return not self.SESSION_COOKIE_SECURE and (
            "localhost" in self.OIDC_ISSUER or "127.0.0.1" in self.OIDC_ISSUER
        )

    @property
    def is_production(self) -> bool:
        """Returns True if operating in secure homelab production mode."""
        return self.SESSION_COOKIE_SECURE

    @property
    def data_path(self) -> Path:
        return Path(self.DATA_DIR).resolve()

    @property
    def map_preview_file(self) -> Path:
        return self.data_path / "map_preview.png"


settings = Settings()


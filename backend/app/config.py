from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application and deployment configuration supporting multi-mode deployment.

    BDInvite supports two primary operational deployment modes via environment variables:

    1. Direct Standalone Mode (Local Development & Testing):
       - Runs directly or in lightweight container with direct port binding (e.g. 8000).
       - Integrates directly with any standard OIDC identity provider (e.g. mock-oauth2-server,
         local Keycloak, or Dex).
       - Insecure session cookies (`SESSION_COOKIE_SECURE=False`) allow local HTTP testing.
       - Example:
           OIDC_ISSUER="http://localhost:8088/default"
           OIDC_REDIRECT_URI="http://localhost:8000/birthday/api/auth/callback"
           SESSION_COOKIE_SECURE=false

    2. Homelab Production Mode (Reverse Proxy & Edge Ingress):
       - Deployed behind Traefik reverse proxy terminating TLS on edge domain.
       - Integrates with central Homelab OIDC Provider (such as Authelia, Keycloak, or Authentik).
       - Secure session cookies (`SESSION_COOKIE_SECURE=True`) enforce HTTPS-only transmission.
       - Zero trust in unvalidated client headers (e.g. legacy proxy headers are completely ignored).
       - Example:
           SERVICE_DOMAIN="demos.roadtotech.me"
           OIDC_ISSUER="https://auth.roadtotech.me"
           OIDC_CLIENT_ID="bdinvite"
           OIDC_CLIENT_SECRET="<secret>"
           OIDC_REDIRECT_URI="https://demos.roadtotech.me/birthday/api/auth/callback"
           SESSION_COOKIE_SECURE=true
           SESSION_COOKIE_NAME="bdinvite_session"
    """

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


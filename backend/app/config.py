from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    SERVICE_NAME: str = "bdinvite"
    SERVICE_DOMAIN: str = "demos.roadtotech.me"
    BASE_PATH: str = "/birthday"
    APP_PORT: int = 8000
    DATABASE_URL: str = "sqlite:///./data/bdinvite.db"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

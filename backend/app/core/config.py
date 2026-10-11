"""Application settings loaded from environment variables / .env file."""

from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application configuration.

    Values come from environment variables (or an optional .env file).
    See .env.example for the documented keys.

    Phase 1 scope: application metadata and CORS only. Database and
    Firebase settings are intentionally absent - they belong to later
    phases and will be added only when actually used.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Roamlary API"
    app_env: str = "development"
    app_version: str = "1.0.0"
    app_host: str = "127.0.0.1"
    app_port: int = 8000

    api_v1_prefix: str = "/api/v1"

    # Comma-separated list in the environment variable, parsed to a list.
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://10.0.2.2:3000",
    ]

    # Database (Phase 2). SQLAlchemy URL format:
    #   postgresql+psycopg://USER:PASSWORD@localhost:5432/DATABASE_NAME
    # Real credentials live in .env (gitignored). The default below uses a
    # placeholder password; nothing connects until the database layer is
    # actually used, so the app and its tests still run without PostgreSQL.
    database_url: str = "postgresql+psycopg://roamlary:change-me@localhost:5432/roamlary_dev"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


settings = Settings()

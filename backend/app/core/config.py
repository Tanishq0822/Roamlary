"""Application settings loaded from environment variables / .env file."""

from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application configuration.

    Values come from environment variables (or an optional .env file).
    See .env.example for the documented keys.

    Scope grows one phase at a time and each setting is added only when it
    is actually used: app metadata + CORS (Phase 1), database_url (Phase 2),
    JWT authentication (Phase 3). Firebase settings are still intentionally
    absent - they belong to a later phase and will be added only when used.
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

    # Authentication (Phase 3). Local JWT signing.
    # jwt_secret_key: the server-side secret used to sign access tokens
    # (HS256). EMPTY by default on purpose - auth endpoints FAIL CLOSED
    # (503) until a real secret is set, so a usable signing key is never
    # hard-coded. The public health endpoint does not depend on this and
    # still starts. Set it in .env via the generation command in README.
    jwt_secret_key: str = ""
    # Short access-token lifetime for the prototype. Refresh tokens are
    # NOT implemented (out of scope for Phase 3).
    access_token_expire_minutes: int = 60

    # AI travel companion (Phase 13). All EMPTY/neutral by default: with
    # no provider configured the /ai/chat endpoint answers with an
    # explicit "unavailable" message instead of fabricating content.
    # `mock` is reserved for tests (deterministic, no network). Keys stay
    # server-side (never in responses, logs, or the repo).
    ai_provider: str = "none"
    ai_api_key: str = ""
    ai_timeout_seconds: int = 20

    # Pay-per-post provider (Phase 14). `none` (default) means no payment
    # provider is configured: paid publishing stays explicitly
    # pending/unavailable, never faked. `mock` is reserved for tests
    # (deterministic, no network). Keys stay server-side (never in
    # responses, logs, or the repo).
    billing_provider: str = "none"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


settings = Settings()

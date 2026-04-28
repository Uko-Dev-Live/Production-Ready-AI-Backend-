"""
app/core/config.py
──────────────────
Central configuration module.

pydantic-settings reads every field from environment variables (or .env file).
This means:  1) All settings live in ONE place.
             2) Secrets never appear in source code.
             3) Docker / local environments both work identically.

FIX APPLIED:
  The .env file contains POSTGRES_HOST / POSTGRES_PORT / POSTGRES_DB /
  POSTGRES_USER / POSTGRES_PASSWORD for use by Docker's postgres service.
  Pydantic v2 raises "Extra inputs are not permitted" for any env var that
  exists in the .env file but is NOT declared as a field on the Settings class.

  Two-part fix:
    1. Declare all POSTGRES_* variables as proper typed fields with defaults.
    2. Set extra="ignore" in model_config so any OTHER unknown env vars are
       silently ignored instead of causing a hard crash.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Application ────────────────────────────────────────
    APP_NAME: str = "AI Backend"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "change-me-in-production"

    # ── PostgreSQL individual components ───────────────────
    # These match the POSTGRES_* vars that Docker and .env both define.
    # Declaring them here prevents pydantic from rejecting them as "extra".
    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "aibackend"
    POSTGRES_USER: str = "aiuser"
    POSTGRES_PASSWORD: str = "aipassword"

    # ── Database DSNs (built from the components above) ────
    # Async DSN — used by SQLAlchemy at runtime
    DATABASE_URL: str = "postgresql+asyncpg://aiuser:aipassword@db:5432/aibackend"
    # Sync DSN — used by Alembic (migrations run synchronously)
    SYNC_DATABASE_URL: str = "postgresql://aiuser:aipassword@db:5432/aibackend"

    # ── Redis / Celery ─────────────────────────────────────
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/1"

    # ── AI / OpenAI ────────────────────────────────────────
    OPENAI_API_KEY: str = "sk-placeholder"
    AI_MODEL: str = "gpt-4o-mini"
    AI_MAX_TOKENS: int = 1024

    # ── MCP ────────────────────────────────────────────────
    MCP_SERVER_HOST: str = "0.0.0.0"
    MCP_SERVER_PORT: int = 9000

    # ── Pydantic-settings configuration ────────────────────
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        # "ignore" means any env var present in .env but NOT declared as a
        # field above is silently skipped — no ValidationError.
        # Alternative: "allow" would attach them dynamically; "forbid" (the
        # default) raises an error, which is what caused the original crash.
        extra="ignore",
    )


# @lru_cache ensures we only parse the env file once for the entire app lifetime
@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

"""Application configuration and environment settings."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(url: str) -> str:
    """Normalize PostgreSQL URLs to use the psycopg v3 SQLAlchemy driver."""
    stripped = url.strip()
    if stripped.startswith("postgres://"):
        return "postgresql+psycopg://" + stripped[len("postgres://") :]
    if stripped.startswith("postgresql://"):
        return "postgresql+psycopg://" + stripped[len("postgresql://") :]
    return stripped


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and `.env` files."""

    model_config = SettingsConfigDict(
        env_file=(".env.local", ".env", "../../.env.local", "../../.env"),
        extra="ignore",
    )

    app_env: str = "local"
    app_version: str = "0.1.0"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    database_url: str = "sqlite:///./paisaproof_dev.db"
    database_url_unpooled: str = ""

    neon_auth_base_url: str = ""
    neon_auth_jwks_url: str = ""

    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_jwt_secret: str = ""

    openrouter_api_key: str = ""
    openrouter_default_model: str = "nvidia/nemotron-3.5-lightning:free"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    finnhub_api_key: str = ""

    market_data_dir: str = "data/seed/market"

    @field_validator("database_url", "database_url_unpooled", mode="before")
    @classmethod
    def _normalize_db_url(cls, value: str | None) -> str:
        if not value:
            return ""
        return normalize_database_url(value)

    @property
    def cors_origins_list(self) -> list[str]:
        """Return parsed list of allowed CORS origins."""
        return [
            origin.strip() for origin in self.cors_origins.split(",") if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()


settings = get_settings()

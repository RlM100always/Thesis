"""Application configuration loaded from environment variables.

Development defaults to a local SQLite database so the project remains easy to
run. Production must provide a PostgreSQL ``DATABASE_URL`` and secrets through
the deployment environment; no credential is committed to the repository.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "B-SMART"
    app_env: str = "development"
    auth_mode: str = "development"
    database_url: str = "sqlite:///./bsmart.db"
    jwt_secret: str = Field(default="development-only-change-me-32-bytes", min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    def validate_runtime(self) -> None:
        if self.is_production and self.auth_mode != "jwt":
            raise RuntimeError("Production requires AUTH_MODE=jwt")
        if self.is_production and self.jwt_secret == "development-only-change-me-32-bytes":
            raise RuntimeError("JWT_SECRET must be changed in production")
        if self.is_production and self.database_url.startswith("sqlite"):
            raise RuntimeError("Production requires PostgreSQL DATABASE_URL")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_runtime()
    return settings

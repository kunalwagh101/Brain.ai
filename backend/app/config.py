from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="BRAIN_",
        case_sensitive=False,
        extra="ignore",
    )

    environment: str = "development"
    app_name: str = "Brain API"
    api_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://brain:brain@localhost:5432/brain"
    cors_origins: str = "http://localhost:3000"
    app_secret: str = "dev-only-change-me"
    workos_client_id: str | None = None
    workos_issuer: str = "https://api.workos.com"
    workos_audience: str | None = None

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def auth_audience(self) -> str | None:
        return self.workos_audience or self.workos_client_id

    @model_validator(mode="after")
    def validate_production_safety(self) -> "Settings":
        if self.environment.lower() == "production":
            if self.app_secret == "dev-only-change-me":
                raise ValueError("BRAIN_APP_SECRET must be changed in production")
            if "*" in self.allowed_origins:
                raise ValueError("Wildcard CORS is not allowed in production")
            if not self.workos_client_id:
                raise ValueError("BRAIN_WORKOS_CLIENT_ID is required in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

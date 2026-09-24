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
    aws_region: str = "us-east-1"
    secrets_prefix: str = "brain"
    slack_client_id: str | None = None
    slack_client_secret: str | None = None
    slack_signing_secret: str | None = None
    slack_redirect_uri: str | None = None
    github_app_id: str | None = None
    github_app_slug: str | None = None
    github_client_id: str | None = None
    github_callback_url: str | None = None
    github_app_secret_ref: str | None = None
    embedding_api_url: str | None = None
    embedding_model: str | None = None
    embedding_secret_ref: str | None = None
    embedding_timeout_seconds: float = 8.0
    ai_provider_allowed_hosts: str = ""
    ai_provider_timeout_seconds: float = 30.0
    log_level: str = "INFO"
    metrics_enabled: bool = True
    metrics_bearer_token: str | None = None
    otel_service_name: str = "brain-api"
    otel_exporter_otlp_endpoint: str | None = None

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def allowed_ai_provider_hosts(self) -> set[str]:
        return {
            host.strip().lower()
            for host in self.ai_provider_allowed_hosts.split(",")
            if host.strip()
        }

    @property
    def auth_audience(self) -> str | None:
        return self.workos_audience or self.workos_client_id

    @model_validator(mode="after")
    def validate_production_safety(self) -> "Settings":
        slack_oauth_values = (
            self.slack_client_id,
            self.slack_client_secret,
            self.slack_redirect_uri,
        )
        if any(slack_oauth_values) and not all(slack_oauth_values):
            raise ValueError(
                "BRAIN_SLACK_CLIENT_ID, BRAIN_SLACK_CLIENT_SECRET and "
                "BRAIN_SLACK_REDIRECT_URI must be configured together"
            )

        github_values = (
            self.github_app_id,
            self.github_app_slug,
            self.github_client_id,
            self.github_callback_url,
            self.github_app_secret_ref,
        )
        if any(github_values) and not all(github_values):
            raise ValueError(
                "BRAIN_GITHUB_APP_ID, BRAIN_GITHUB_APP_SLUG, BRAIN_GITHUB_CLIENT_ID, "
                "BRAIN_GITHUB_CALLBACK_URL and BRAIN_GITHUB_APP_SECRET_REF must be "
                "configured together"
            )

        embedding_values = (self.embedding_api_url, self.embedding_model)
        if any(embedding_values) and not all(embedding_values):
            raise ValueError(
                "BRAIN_EMBEDDING_API_URL and BRAIN_EMBEDDING_MODEL must be configured together"
            )
        if self.embedding_timeout_seconds <= 0 or self.embedding_timeout_seconds > 30:
            raise ValueError("BRAIN_EMBEDDING_TIMEOUT_SECONDS must be > 0 and <= 30")
        if self.ai_provider_timeout_seconds <= 0 or self.ai_provider_timeout_seconds > 120:
            raise ValueError("BRAIN_AI_PROVIDER_TIMEOUT_SECONDS must be > 0 and <= 120")
        if self.log_level.upper() not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("BRAIN_LOG_LEVEL must be a standard logging level")
        if not self.otel_service_name.strip():
            raise ValueError("BRAIN_OTEL_SERVICE_NAME must not be empty")

        if self.environment.lower() == "production":
            if self.app_secret == "dev-only-change-me":
                raise ValueError("BRAIN_APP_SECRET must be changed in production")
            if "*" in self.allowed_origins:
                raise ValueError("Wildcard CORS is not allowed in production")
            if not self.workos_client_id:
                raise ValueError("BRAIN_WORKOS_CLIENT_ID is required in production")
            if not self.aws_region.strip():
                raise ValueError("BRAIN_AWS_REGION is required in production")
            if not self.secrets_prefix.strip("/"):
                raise ValueError("BRAIN_SECRETS_PREFIX must not be empty in production")
            if self.metrics_enabled and not self.metrics_bearer_token:
                raise ValueError(
                    "BRAIN_METRICS_BEARER_TOKEN is required when metrics are enabled in production"
                )
            if self.otel_exporter_otlp_endpoint and not self.otel_exporter_otlp_endpoint.startswith(
                "https://"
            ):
                raise ValueError("Production OTLP export must use HTTPS")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

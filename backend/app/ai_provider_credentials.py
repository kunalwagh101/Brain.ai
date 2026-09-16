import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai_gateway_models import AIProviderConfiguration, AIProviderStatus
from app.ai_provider_adapter import AIGatewayError
from app.secrets import SecretStore, SecretStoreError

MAX_AI_CREDENTIAL_FIELDS = 16
MAX_AI_CREDENTIAL_FIELD_LENGTH = 128
MAX_AI_CREDENTIAL_VALUE_LENGTH = 8192


def _validated_credentials(credentials: dict[str, str]) -> dict[str, str]:
    if not credentials or len(credentials) > MAX_AI_CREDENTIAL_FIELDS:
        raise AIGatewayError("AI provider credentials have an invalid shape")
    sanitized: dict[str, str] = {}
    for key, value in credentials.items():
        clean_key = key.strip()
        if not clean_key or len(clean_key) > MAX_AI_CREDENTIAL_FIELD_LENGTH:
            raise AIGatewayError("AI provider credential field name is invalid")
        if not isinstance(value, str) or not value or len(value) > MAX_AI_CREDENTIAL_VALUE_LENGTH:
            raise AIGatewayError("AI provider credential field value is invalid")
        sanitized[clean_key] = value
    api_key = sanitized.get("api_key")
    if not isinstance(api_key, str) or not api_key.strip():
        raise AIGatewayError("AI provider credentials require api_key")
    return sanitized


def rotate_ai_provider_credentials(
    db: Session,
    *,
    secret_store: SecretStore,
    organization_id: uuid.UUID,
    provider_configuration_id: uuid.UUID,
    credentials: dict[str, str],
) -> AIProviderConfiguration:
    provider = db.scalar(
        select(AIProviderConfiguration).where(
            AIProviderConfiguration.id == provider_configuration_id,
            AIProviderConfiguration.organization_id == organization_id,
        )
    )
    if provider is None:
        raise AIGatewayError("AI provider configuration not found")
    if provider.status not in {AIProviderStatus.ENABLED, AIProviderStatus.DISABLED}:
        raise AIGatewayError("AI provider credentials cannot rotate after revocation starts")
    if not provider.secret_ref:
        raise AIGatewayError("AI provider has no credential secret reference")

    sanitized = _validated_credentials(credentials)
    try:
        secret_store.replace_secret(provider.secret_ref, sanitized)
    except SecretStoreError as exc:
        raise AIGatewayError("AI provider credential rotation failed") from exc

    provider.credential_rotated_at = datetime.now(UTC)
    db.commit()
    db.refresh(provider)
    return provider

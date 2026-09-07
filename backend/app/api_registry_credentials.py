import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api_registry_models import APICredentialGrant, APIGrantStatus
from app.secrets import SecretStore, SecretStoreError


class APIRegistryCredentialError(RuntimeError):
    """Raised when a governed API credential cannot be safely used."""


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def load_active_api_credentials(
    db: Session,
    *,
    secret_store: SecretStore,
    organization_id: uuid.UUID,
    grant_id: uuid.UUID,
    at: datetime | None = None,
) -> dict[str, str]:
    grant = db.scalar(
        select(APICredentialGrant).where(
            APICredentialGrant.id == grant_id,
            APICredentialGrant.organization_id == organization_id,
        )
    )
    if grant is None:
        raise APIRegistryCredentialError("API grant not found")

    moment = _utc(at) if at is not None else datetime.now(UTC)
    if grant.status != APIGrantStatus.ACTIVE:
        raise APIRegistryCredentialError("API grant is not active")
    if grant.expires_at is not None and _utc(grant.expires_at) <= moment:
        raise APIRegistryCredentialError("API grant has expired")
    if not grant.secret_ref:
        raise APIRegistryCredentialError("API grant has no credential reference")

    try:
        credentials = secret_store.load_connection_secret(grant.secret_ref)
    except SecretStoreError as exc:
        raise APIRegistryCredentialError("API credential is unavailable") from exc
    if not credentials:
        raise APIRegistryCredentialError("API credential is empty")
    return credentials

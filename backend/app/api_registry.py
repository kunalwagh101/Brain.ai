import logging
import re
import uuid
from datetime import UTC, datetime
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api_registry_models import (
    APICredentialGrant,
    APIGrantHistory,
    APIGrantHistoryAction,
    APIGrantStatus,
    APIService,
    APIUsageObservation,
)
from app.models import Membership, User
from app.secrets import SecretStore, SecretStoreError

logger = logging.getLogger("brain.api_registry")
_SERVICE_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_GRANT_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,95}$")
_SCOPE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_ENVIRONMENT_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_COMPONENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")


class APIRegistryError(ValueError):
    """Raised when external API registry state or input is invalid."""


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _now() -> datetime:
    return datetime.now(UTC)


def _normalize_service_key(value: str) -> str:
    normalized = value.strip().lower()
    if not _SERVICE_KEY_RE.fullmatch(normalized):
        raise APIRegistryError("API service key contains unsupported characters")
    return normalized


def _normalize_grant_key(value: str) -> str:
    normalized = value.strip().lower()
    if not _GRANT_KEY_RE.fullmatch(normalized):
        raise APIRegistryError("API grant key contains unsupported characters")
    return normalized


def _normalize_environment(value: str) -> str:
    environment = value.strip().lower()
    if not _ENVIRONMENT_RE.fullmatch(environment):
        raise APIRegistryError("API environment contains unsupported characters")
    return environment


def _normalize_scopes(scopes: list[str]) -> list[str]:
    normalized: set[str] = set()
    for scope in scopes:
        item = scope.strip()
        if not _SCOPE_RE.fullmatch(item):
            raise APIRegistryError("API scope contains unsupported characters")
        normalized.add(item)
    if not normalized:
        raise APIRegistryError("At least one API scope is required")
    if len(normalized) > 128:
        raise APIRegistryError("API scope count exceeds the supported limit")
    return sorted(normalized)


def _validate_credentials(credentials: dict[str, str]) -> dict[str, str]:
    if not credentials or len(credentials) > 32:
        raise APIRegistryError("API credentials have an invalid shape")
    sanitized: dict[str, str] = {}
    for key, value in credentials.items():
        clean_key = key.strip()
        if not clean_key or len(clean_key) > 128:
            raise APIRegistryError("API credential field name is invalid")
        if not isinstance(value, str) or not value or len(value) > 8192:
            raise APIRegistryError("API credential field value is invalid")
        sanitized[clean_key] = value
    return sanitized


def _normalize_optional_url(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise APIRegistryError("API base URL must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password or parsed.fragment:
        raise APIRegistryError("API base URL contains unsupported credentials or fragment")
    return normalized


def _active_org_member(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
) -> User:
    user = db.scalar(
        select(User)
        .join(Membership, Membership.user_id == User.id)
        .where(
            Membership.organization_id == organization_id,
            Membership.user_id == user_id,
            User.status == "active",
        )
    )
    if user is None:
        raise APIRegistryError("API grant owner must be an active organization member")
    return user


def _assert_metadata_mutable(grant: APICredentialGrant) -> None:
    if grant.status not in {APIGrantStatus.ACTIVE, APIGrantStatus.DISABLED}:
        raise APIRegistryError("API grant metadata is immutable after revocation or expiry")


def _history(
    db: Session,
    *,
    grant: APICredentialGrant,
    action: APIGrantHistoryAction,
    actor_user_id: uuid.UUID | None,
    reason: str | None = None,
    previous_status: APIGrantStatus | None = None,
    new_status: APIGrantStatus | None = None,
    previous_owner_user_id: uuid.UUID | None = None,
    new_owner_user_id: uuid.UUID | None = None,
    previous_scopes: list[str] | None = None,
    new_scopes: list[str] | None = None,
    previous_environment: str | None = None,
    new_environment: str | None = None,
) -> None:
    clean_reason = " ".join(reason.strip().split())[:512] if reason else None
    db.add(
        APIGrantHistory(
            organization_id=grant.organization_id,
            grant_id=grant.id,
            action=action,
            actor_user_id=actor_user_id,
            previous_status=previous_status.value if previous_status else None,
            new_status=new_status.value if new_status else None,
            previous_owner_user_id=previous_owner_user_id,
            new_owner_user_id=new_owner_user_id,
            previous_scopes=previous_scopes,
            new_scopes=new_scopes,
            previous_environment=previous_environment,
            new_environment=new_environment,
            reason=clean_reason,
        )
    )


def create_api_service(
    db: Session,
    *,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    service_key: str,
    display_name: str,
    provider_name: str,
    base_url: str | None,
) -> APIService:
    key = _normalize_service_key(service_key)
    name = " ".join(display_name.strip().split())[:160]
    provider = " ".join(provider_name.strip().split())[:160]
    if not name or not provider:
        raise APIRegistryError("API service display name and provider are required")
    service = APIService(
        organization_id=organization_id,
        service_key=key,
        display_name=name,
        provider_name=provider,
        base_url=_normalize_optional_url(base_url),
        created_by_user_id=actor_user_id,
    )
    db.add(service)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise APIRegistryError("API service already exists") from exc
    db.refresh(service)
    return service


def create_api_grant(
    db: Session,
    *,
    secret_store: SecretStore,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    service_id: uuid.UUID,
    grant_key: str,
    display_name: str,
    owner_user_id: uuid.UUID,
    environment: str,
    scopes: list[str],
    expires_at: datetime | None,
    credentials: dict[str, str],
) -> APICredentialGrant:
    service = db.scalar(
        select(APIService).where(
            APIService.id == service_id,
            APIService.organization_id == organization_id,
        )
    )
    if service is None:
        raise APIRegistryError("API service not found")
    _active_org_member(db, organization_id=organization_id, user_id=owner_user_id)
    key = _normalize_grant_key(grant_key)
    name = " ".join(display_name.strip().split())[:160]
    if not name:
        raise APIRegistryError("API grant display name is required")
    normalized_expiry = _utc(expires_at) if expires_at is not None else None
    if normalized_expiry is not None and normalized_expiry <= _now():
        raise APIRegistryError("API grant expiry must be in the future")
    normalized_credentials = _validate_credentials(credentials)
    grant_id = uuid.uuid4()
    try:
        secret_ref = secret_store.store_api_credential_secret(
            organization_id=organization_id,
            grant_id=grant_id,
            service_key=service.service_key,
            credentials=normalized_credentials,
        )
    except SecretStoreError as exc:
        raise APIRegistryError("API credential storage failed") from exc

    grant = APICredentialGrant(
        id=grant_id,
        organization_id=organization_id,
        service_id=service.id,
        grant_key=key,
        display_name=name,
        owner_user_id=owner_user_id,
        environment=_normalize_environment(environment),
        scopes=_normalize_scopes(scopes),
        secret_ref=secret_ref,
        status=APIGrantStatus.ACTIVE,
        expires_at=normalized_expiry,
        usage_count=0,
        created_by_user_id=actor_user_id,
    )
    db.add(grant)
    _history(
        db,
        grant=grant,
        action=APIGrantHistoryAction.CREATED,
        actor_user_id=actor_user_id,
        new_status=APIGrantStatus.ACTIVE,
        new_owner_user_id=owner_user_id,
        new_scopes=list(grant.scopes),
        new_environment=grant.environment,
    )
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        try:
            secret_store.schedule_delete(secret_ref)
        except SecretStoreError:
            logger.exception(
                "Failed to clean up orphaned API credential secret",
                extra={"grant_id": str(grant_id)},
            )
        raise APIRegistryError("API grant could not be persisted") from exc
    db.refresh(grant)
    return grant


def get_api_grant(
    db: Session,
    *,
    organization_id: uuid.UUID,
    grant_id: uuid.UUID,
) -> APICredentialGrant:
    grant = db.scalar(
        select(APICredentialGrant).where(
            APICredentialGrant.id == grant_id,
            APICredentialGrant.organization_id == organization_id,
        )
    )
    if grant is None:
        raise APIRegistryError("API grant not found")
    return grant


def change_api_grant_owner(
    db: Session,
    *,
    organization_id: uuid.UUID,
    grant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    owner_user_id: uuid.UUID,
    reason: str | None,
) -> APICredentialGrant:
    grant = get_api_grant(db, organization_id=organization_id, grant_id=grant_id)
    _assert_metadata_mutable(grant)
    _active_org_member(db, organization_id=organization_id, user_id=owner_user_id)
    previous = grant.owner_user_id
    if previous == owner_user_id:
        return grant
    grant.owner_user_id = owner_user_id
    _history(
        db,
        grant=grant,
        action=APIGrantHistoryAction.OWNER_CHANGED,
        actor_user_id=actor_user_id,
        previous_owner_user_id=previous,
        new_owner_user_id=owner_user_id,
        reason=reason,
    )
    db.commit()
    db.refresh(grant)
    return grant


def change_api_grant_scopes(
    db: Session,
    *,
    organization_id: uuid.UUID,
    grant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    scopes: list[str],
    reason: str | None,
) -> APICredentialGrant:
    grant = get_api_grant(db, organization_id=organization_id, grant_id=grant_id)
    _assert_metadata_mutable(grant)
    new_scopes = _normalize_scopes(scopes)
    previous = list(grant.scopes)
    if previous == new_scopes:
        return grant
    grant.scopes = new_scopes
    _history(
        db,
        grant=grant,
        action=APIGrantHistoryAction.SCOPES_CHANGED,
        actor_user_id=actor_user_id,
        previous_scopes=previous,
        new_scopes=new_scopes,
        reason=reason,
    )
    db.commit()
    db.refresh(grant)
    return grant


def change_api_grant_environment(
    db: Session,
    *,
    organization_id: uuid.UUID,
    grant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    environment: str,
    reason: str | None,
) -> APICredentialGrant:
    grant = get_api_grant(db, organization_id=organization_id, grant_id=grant_id)
    _assert_metadata_mutable(grant)
    new_environment = _normalize_environment(environment)
    previous = grant.environment
    if previous == new_environment:
        return grant
    grant.environment = new_environment
    _history(
        db,
        grant=grant,
        action=APIGrantHistoryAction.ENVIRONMENT_CHANGED,
        actor_user_id=actor_user_id,
        previous_environment=previous,
        new_environment=new_environment,
        reason=reason,
    )
    db.commit()
    db.refresh(grant)
    return grant


def set_api_grant_enabled(
    db: Session,
    *,
    organization_id: uuid.UUID,
    grant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    enabled: bool,
    reason: str | None,
) -> APICredentialGrant:
    grant = get_api_grant(db, organization_id=organization_id, grant_id=grant_id)
    if grant.status not in {APIGrantStatus.ACTIVE, APIGrantStatus.DISABLED}:
        raise APIRegistryError("API grant cannot be re-enabled after revocation or expiry")
    if enabled and grant.expires_at is not None and _utc(grant.expires_at) <= _now():
        raise APIRegistryError("API grant has expired")
    new_status = APIGrantStatus.ACTIVE if enabled else APIGrantStatus.DISABLED
    previous = grant.status
    if previous == new_status:
        return grant
    grant.status = new_status
    _history(
        db,
        grant=grant,
        action=(
            APIGrantHistoryAction.ENABLED
            if enabled
            else APIGrantHistoryAction.DISABLED
        ),
        actor_user_id=actor_user_id,
        previous_status=previous,
        new_status=new_status,
        reason=reason,
    )
    db.commit()
    db.refresh(grant)
    return grant


def rotate_api_grant_credentials(
    db: Session,
    *,
    secret_store: SecretStore,
    organization_id: uuid.UUID,
    grant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    credentials: dict[str, str],
    reason: str | None,
) -> APICredentialGrant:
    grant = get_api_grant(db, organization_id=organization_id, grant_id=grant_id)
    if grant.status not in {APIGrantStatus.ACTIVE, APIGrantStatus.DISABLED}:
        raise APIRegistryError("API grant credentials cannot rotate after revocation starts")
    if grant.expires_at is not None and _utc(grant.expires_at) <= _now():
        raise APIRegistryError("API grant has expired")
    if not grant.secret_ref:
        raise APIRegistryError("API grant has no credential secret reference")
    try:
        secret_store.replace_secret(grant.secret_ref, _validate_credentials(credentials))
    except SecretStoreError as exc:
        raise APIRegistryError("API credential rotation failed") from exc
    grant.credential_rotated_at = _now()
    _history(
        db,
        grant=grant,
        action=APIGrantHistoryAction.CREDENTIAL_ROTATED,
        actor_user_id=actor_user_id,
        reason=reason,
    )
    db.commit()
    db.refresh(grant)
    return grant


def revoke_api_grant(
    db: Session,
    *,
    secret_store: SecretStore,
    organization_id: uuid.UUID,
    grant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    reason: str | None,
) -> APICredentialGrant:
    grant = get_api_grant(db, organization_id=organization_id, grant_id=grant_id)
    if grant.status == APIGrantStatus.REVOKED:
        return grant
    if grant.status == APIGrantStatus.EXPIRED:
        raise APIRegistryError("Expired API grant is already unusable")
    previous = grant.status
    grant.status = APIGrantStatus.REVOKING
    _history(
        db,
        grant=grant,
        action=APIGrantHistoryAction.REVOKE_STARTED,
        actor_user_id=actor_user_id,
        previous_status=previous,
        new_status=APIGrantStatus.REVOKING,
        reason=reason,
    )
    db.commit()

    reference = grant.secret_ref
    if reference:
        try:
            secret_store.schedule_delete(reference)
        except SecretStoreError as exc:
            grant.status = APIGrantStatus.REVOKE_FAILED
            _history(
                db,
                grant=grant,
                action=APIGrantHistoryAction.REVOKE_FAILED,
                actor_user_id=actor_user_id,
                previous_status=APIGrantStatus.REVOKING,
                new_status=APIGrantStatus.REVOKE_FAILED,
                reason=reason,
            )
            db.commit()
            raise APIRegistryError("API grant revocation is incomplete") from exc

    grant.status = APIGrantStatus.REVOKED
    grant.secret_ref = None
    grant.revoked_at = _now()
    _history(
        db,
        grant=grant,
        action=APIGrantHistoryAction.REVOKED,
        actor_user_id=actor_user_id,
        previous_status=APIGrantStatus.REVOKING,
        new_status=APIGrantStatus.REVOKED,
        reason=reason,
    )
    db.commit()
    db.refresh(grant)
    return grant


def expire_due_api_grants(
    db: Session,
    *,
    organization_id: uuid.UUID | None = None,
    at: datetime | None = None,
    limit: int = 100,
) -> int:
    moment = _utc(at) if at is not None else _now()
    filters = [
        APICredentialGrant.status.in_((APIGrantStatus.ACTIVE, APIGrantStatus.DISABLED)),
        APICredentialGrant.expires_at.is_not(None),
        APICredentialGrant.expires_at <= moment,
    ]
    if organization_id is not None:
        filters.append(APICredentialGrant.organization_id == organization_id)
    query = (
        select(APICredentialGrant)
        .where(*filters)
        .order_by(APICredentialGrant.expires_at, APICredentialGrant.id)
        .limit(limit)
    )
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        query = query.with_for_update(skip_locked=True)
    grants = list(db.scalars(query))
    for grant in grants:
        previous = grant.status
        grant.status = APIGrantStatus.EXPIRED
        grant.expired_at = moment
        _history(
            db,
            grant=grant,
            action=APIGrantHistoryAction.EXPIRED,
            actor_user_id=None,
            previous_status=previous,
            new_status=APIGrantStatus.EXPIRED,
            reason="configured_expiry_reached",
        )
        db.commit()
    return len(grants)


def record_api_usage(
    db: Session,
    *,
    organization_id: uuid.UUID,
    grant_id: uuid.UUID,
    observation_key: str,
    caller_component: str,
    operation_label: str | None,
    success: bool,
    latency_ms: int | None,
    observed_at: datetime | None = None,
) -> APIUsageObservation:
    grant_query = select(APICredentialGrant).where(
        APICredentialGrant.id == grant_id,
        APICredentialGrant.organization_id == organization_id,
    )
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        grant_query = grant_query.with_for_update()
    grant = db.scalar(grant_query)
    if grant is None:
        raise APIRegistryError("API grant not found")
    key = observation_key.strip()
    if not key or len(key) > 160:
        raise APIRegistryError("API usage observation key is invalid")
    component = caller_component.strip()
    if not _COMPONENT_RE.fullmatch(component):
        raise APIRegistryError("API usage caller component is invalid")
    label = " ".join(operation_label.strip().split())[:160] if operation_label else None
    if latency_ms is not None and not 0 <= latency_ms <= 86_400_000:
        raise APIRegistryError("API usage latency is outside the supported range")
    existing = db.scalar(
        select(APIUsageObservation).where(
            APIUsageObservation.grant_id == grant.id,
            APIUsageObservation.observation_key == key,
        )
    )
    if existing is not None:
        return existing

    moment = _utc(observed_at) if observed_at is not None else _now()
    observation = APIUsageObservation(
        organization_id=organization_id,
        grant_id=grant.id,
        observation_key=key,
        caller_component=component,
        operation_label=label,
        success=success,
        latency_ms=latency_ms,
        observed_at=moment,
    )
    db.add(observation)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        concurrent = db.scalar(
            select(APIUsageObservation).where(
                APIUsageObservation.grant_id == grant.id,
                APIUsageObservation.observation_key == key,
            )
        )
        if concurrent is None:
            raise
        return concurrent
    grant.usage_count += 1
    if grant.last_used_at is None or _utc(grant.last_used_at) <= moment:
        grant.last_used_at = moment
        grant.last_usage_success = success
        grant.last_usage_latency_ms = latency_ms
    db.commit()
    db.refresh(observation)
    return observation

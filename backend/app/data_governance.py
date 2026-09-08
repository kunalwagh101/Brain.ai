import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.data_governance_models import (
    DataDeletionRequest,
    DeletionScope,
    DeletionStatus,
    DerivedRetentionTombstone,
    OrganizationRetentionPolicy,
    RetentionRun,
    RetentionRunStatus,
    SecurityAuditEvent,
)
from app.models import (
    CanonicalEvent,
    IntegrationConnection,
    IntegrationStatus,
    RawEvent,
    SourceIdentity,
    SourceIdentityObservation,
    SourceIdentityState,
)

MAX_RETENTION_BATCH = 500
_DELETION_STALE_AFTER = timedelta(minutes=15)
_SENSITIVE_METADATA_TERMS = (
    "api_key",
    "apikey",
    "authorization",
    "access_token",
    "refresh_token",
    "password",
    "secret",
    "credential",
)


class DataGovernanceError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def _normalize_optional_days(value: int | None, field: str) -> int | None:
    if value is None:
        return None
    if value < 1 or value > 36_500:
        raise DataGovernanceError(f"{field} must be between 1 and 36500 days")
    return value


def _normalized_metadata(metadata: dict[str, object] | None) -> dict[str, object]:
    if not metadata:
        return {}
    clean: dict[str, object] = {}
    for key, value in metadata.items():
        safe_key = str(key).strip()[:64]
        if not safe_key:
            continue
        normalized_key = safe_key.lower().replace("-", "_")
        if any(term in normalized_key for term in _SENSITIVE_METADATA_TERMS):
            raise DataGovernanceError("Audit metadata contains a sensitive field name")
        if value is None or isinstance(value, (bool, int, float)):
            clean[safe_key] = value
        elif isinstance(value, (str, uuid.UUID)):
            clean[safe_key] = str(value)[:512]
    return clean


def _audit_payload(
    *,
    organization_id: uuid.UUID,
    event_key: str,
    event_type: str,
    outcome: str,
    actor_user_id: uuid.UUID | None,
    resource_type: str | None,
    resource_id: str | uuid.UUID | None,
    request_id: str | None,
    metadata: dict[str, object] | None,
) -> tuple[dict[str, object], str]:
    normalized_key = event_key.strip()[:255]
    normalized_type = event_type.strip()[:128]
    normalized_outcome = outcome.strip()[:32]
    if not normalized_key or not normalized_type or not normalized_outcome:
        raise DataGovernanceError("Audit event key/type/outcome are required")
    normalized_metadata = _normalized_metadata(metadata)
    payload: dict[str, object] = {
        "organization_id": str(organization_id),
        "event_key": normalized_key,
        "event_type": normalized_type,
        "outcome": normalized_outcome,
        "actor_user_id": str(actor_user_id) if actor_user_id else None,
        "resource_type": resource_type[:128] if resource_type else None,
        "resource_id": str(resource_id)[:512] if resource_id is not None else None,
        "request_id": request_id[:128] if request_id else None,
        "metadata": normalized_metadata,
    }
    digest = hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode()
    ).hexdigest()
    return payload, digest


def append_audit_event(
    db: Session,
    *,
    organization_id: uuid.UUID,
    event_key: str,
    event_type: str,
    outcome: str,
    actor_user_id: uuid.UUID | None,
    resource_type: str | None = None,
    resource_id: str | uuid.UUID | None = None,
    request_id: str | None = None,
    metadata: dict[str, object] | None = None,
) -> SecurityAuditEvent:
    payload, digest = _audit_payload(
        organization_id=organization_id,
        event_key=event_key,
        event_type=event_type,
        outcome=outcome,
        actor_user_id=actor_user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        request_id=request_id,
        metadata=metadata,
    )
    normalized_key = str(payload["event_key"])
    existing = db.scalar(
        select(SecurityAuditEvent).where(
            SecurityAuditEvent.organization_id == organization_id,
            SecurityAuditEvent.event_key == normalized_key,
        )
    )
    if existing is not None:
        if existing.payload_sha256 != digest:
            raise DataGovernanceError(
                "Audit event key was reused with different content"
            )
        db.commit()
        return existing

    event = SecurityAuditEvent(
        organization_id=organization_id,
        event_key=normalized_key,
        event_type=str(payload["event_type"]),
        outcome=str(payload["outcome"]),
        actor_user_id=actor_user_id,
        resource_type=payload["resource_type"],
        resource_id=payload["resource_id"],
        request_id=payload["request_id"],
        metadata_json=payload["metadata"],
        payload_sha256=digest,
    )
    try:
        with db.begin_nested():
            db.add(event)
            db.flush()
    except IntegrityError:
        existing = db.scalar(
            select(SecurityAuditEvent).where(
                SecurityAuditEvent.organization_id == organization_id,
                SecurityAuditEvent.event_key == normalized_key,
            )
        )
        if existing is None:
            raise
        if existing.payload_sha256 != digest:
            raise DataGovernanceError(
                "Audit event key was reused with different content"
            )
        db.commit()
        return existing
    db.commit()
    db.refresh(event)
    return event


def set_retention_policy(
    db: Session,
    *,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    raw_event_days: int | None,
    derived_content_days: int | None,
    audit_event_days: int | None,
    legal_hold: bool,
    request_id: str | None = None,
) -> OrganizationRetentionPolicy:
    raw_days = _normalize_optional_days(raw_event_days, "raw_event_days")
    derived_days = _normalize_optional_days(
        derived_content_days,
        "derived_content_days",
    )
    audit_days = _normalize_optional_days(audit_event_days, "audit_event_days")
    policy = db.scalar(
        select(OrganizationRetentionPolicy).where(
            OrganizationRetentionPolicy.organization_id == organization_id
        )
    )
    if policy is None:
        policy = OrganizationRetentionPolicy(
            organization_id=organization_id,
            updated_by_user_id=actor_user_id,
        )
        db.add(policy)
        db.flush()
    policy.raw_event_days = raw_days
    policy.derived_content_days = derived_days
    policy.audit_event_days = audit_days
    policy.legal_hold = legal_hold
    policy.updated_by_user_id = actor_user_id
    append_audit_event(
        db,
        organization_id=organization_id,
        event_key=f"retention.policy:{request_id or uuid.uuid4()}",
        event_type="retention.policy.updated",
        outcome="succeeded",
        actor_user_id=actor_user_id,
        resource_type="retention_policy",
        resource_id=policy.id,
        request_id=request_id,
        metadata={
            "raw_event_days": raw_days,
            "derived_content_days": derived_days,
            "audit_event_days": audit_days,
            "legal_hold": legal_hold,
        },
    )
    db.refresh(policy)
    return policy


def _source_locator_integrations(
    db: Session,
    *,
    organization_id: uuid.UUID,
    source_provider: str,
    object_type: str,
    object_external_id: str,
) -> set[uuid.UUID]:
    canonical_ids = set(
        db.scalars(
            select(CanonicalEvent.integration_connection_id).where(
                CanonicalEvent.organization_id == organization_id,
                CanonicalEvent.source_provider == source_provider,
                CanonicalEvent.object_type == object_type,
                CanonicalEvent.object_external_id == object_external_id,
            )
        )
    )
    tombstone_ids = set(
        db.scalars(
            select(DerivedRetentionTombstone.integration_connection_id).where(
                DerivedRetentionTombstone.organization_id == organization_id,
                DerivedRetentionTombstone.source_provider == source_provider,
                DerivedRetentionTombstone.object_type == object_type,
                DerivedRetentionTombstone.object_external_id == object_external_id,
            )
        )
    )
    return canonical_ids | tombstone_ids


def _resolve_source_integration(
    db: Session,
    *,
    organization_id: uuid.UUID,
    source_provider: str,
    object_type: str,
    object_external_id: str,
    integration_connection_id: uuid.UUID | None,
) -> uuid.UUID:
    if integration_connection_id is not None:
        connection = db.scalar(
            select(IntegrationConnection).where(
                IntegrationConnection.id == integration_connection_id,
                IntegrationConnection.organization_id == organization_id,
            )
        )
        if connection is None:
            raise DataGovernanceError("Integration connection not found")
        if connection.provider != source_provider:
            raise DataGovernanceError(
                "Source provider does not match the integration connection"
            )
        return integration_connection_id

    candidates = _source_locator_integrations(
        db,
        organization_id=organization_id,
        source_provider=source_provider,
        object_type=object_type,
        object_external_id=object_external_id,
    )
    if len(candidates) == 1:
        return next(iter(candidates))
    if not candidates:
        raise DataGovernanceError(
            "Source-object deletion requires integration_connection_id when "
            "the target has no discoverable evidence"
        )
    raise DataGovernanceError(
        "Source-object deletion requires integration_connection_id when the "
        "same source locator exists in multiple integrations"
    )


def create_deletion_request(
    db: Session,
    *,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    request_key: str,
    scope: DeletionScope,
    reason: str,
    integration_connection_id: uuid.UUID | None = None,
    source_provider: str | None = None,
    object_type: str | None = None,
    object_external_id: str | None = None,
    request_id: str | None = None,
) -> DataDeletionRequest:
    normalized_key = request_key.strip()[:128]
    normalized_reason = " ".join(reason.strip().split())[:512]
    if not normalized_key or not normalized_reason:
        raise DataGovernanceError("Deletion request key and reason are required")
    policy = db.scalar(
        select(OrganizationRetentionPolicy).where(
            OrganizationRetentionPolicy.organization_id == organization_id
        )
    )
    if policy is not None and policy.legal_hold:
        raise DataGovernanceError("Deletion is blocked by the organization legal hold")

    if scope == DeletionScope.INTEGRATION:
        if integration_connection_id is None:
            raise DataGovernanceError(
                "Integration deletion requires integration_connection_id"
            )
        connection = db.scalar(
            select(IntegrationConnection).where(
                IntegrationConnection.id == integration_connection_id,
                IntegrationConnection.organization_id == organization_id,
            )
        )
        if connection is None:
            raise DataGovernanceError("Integration connection not found")
        if connection.status != IntegrationStatus.REVOKED:
            raise DataGovernanceError(
                "Integration must be fully revoked before data deletion"
            )
        target_reference = f"integration:{integration_connection_id}"
        source_provider = None
        object_type = None
        object_external_id = None
    elif scope == DeletionScope.SOURCE_OBJECT:
        source_provider = (source_provider or "").strip()[:40]
        object_type = (object_type or "").strip()[:64]
        object_external_id = (object_external_id or "").strip()[:512]
        if not source_provider or not object_type or not object_external_id:
            raise DataGovernanceError(
                "Source-object deletion requires provider, object_type and "
                "object_external_id"
            )
        integration_connection_id = _resolve_source_integration(
            db,
            organization_id=organization_id,
            source_provider=source_provider,
            object_type=object_type,
            object_external_id=object_external_id,
            integration_connection_id=integration_connection_id,
        )
        target_reference = (
            f"source:{integration_connection_id}:{source_provider}:"
            f"{object_type}:{object_external_id}"
        )
    else:
        raise DataGovernanceError("Unsupported deletion scope")

    existing = db.scalar(
        select(DataDeletionRequest).where(
            DataDeletionRequest.organization_id == organization_id,
            DataDeletionRequest.request_key == normalized_key,
        )
    )
    if existing is not None:
        same = (
            existing.scope == scope
            and existing.target_reference == target_reference
            and existing.integration_connection_id == integration_connection_id
            and existing.source_provider == source_provider
            and existing.object_type == object_type
            and existing.object_external_id == object_external_id
        )
        if not same:
            raise DataGovernanceError(
                "Deletion request key was reused for a different target"
            )
        return existing

    deletion_request = DataDeletionRequest(
        organization_id=organization_id,
        request_key=normalized_key,
        scope=scope,
        target_reference=target_reference,
        integration_connection_id=integration_connection_id,
        source_provider=source_provider,
        object_type=object_type,
        object_external_id=object_external_id,
        requested_by_user_id=actor_user_id,
        reason=normalized_reason,
    )
    db.add(deletion_request)
    db.flush()
    append_audit_event(
        db,
        organization_id=organization_id,
        event_key=f"deletion.requested:{deletion_request.id}",
        event_type="data.deletion.requested",
        outcome="accepted",
        actor_user_id=actor_user_id,
        resource_type="data_deletion_request",
        resource_id=deletion_request.id,
        request_id=request_id,
        metadata={
            "scope": scope.value,
            "request_key": normalized_key,
            "target_reference": target_reference,
        },
    )
    db.refresh(deletion_request)
    return deletion_request


def _sanitize_orphan_source_identities(
    db: Session,
    organization_id: uuid.UUID,
) -> int:
    identities = list(
        db.scalars(
            select(SourceIdentity).where(
                SourceIdentity.organization_id == organization_id
            )
        )
    )
    changed = 0
    for identity in identities:
        observation = db.scalar(
            select(SourceIdentityObservation.id)
            .where(SourceIdentityObservation.source_identity_id == identity.id)
            .limit(1)
        )
        if observation is not None:
            continue
        if (
            identity.display_name is None
            and identity.email is None
            and identity.resolved_user_id is None
            and identity.state == SourceIdentityState.UNRESOLVED
        ):
            continue
        identity.display_name = None
        identity.email = None
        identity.email_verified = False
        identity.resolved_user_id = None
        identity.resolution_method = None
        identity.state = SourceIdentityState.UNRESOLVED
        changed += 1
    return changed


def _completion_digest(
    deletion_request: DataDeletionRequest,
    *,
    raw_ids: list[uuid.UUID],
    canonical_ids: list[uuid.UUID],
) -> str:
    payload = {
        "request_id": str(deletion_request.id),
        "request_key": deletion_request.request_key,
        "scope": deletion_request.scope.value,
        "target_reference": deletion_request.target_reference,
        "raw_event_ids": sorted(str(item) for item in raw_ids),
        "canonical_event_ids": sorted(str(item) for item in canonical_ids),
    }
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def _source_object_target_ids(
    db: Session,
    deletion_request: DataDeletionRequest,
) -> tuple[list[uuid.UUID], list[uuid.UUID]]:
    if deletion_request.integration_connection_id is None:
        raise DataGovernanceError(
            "Source-object deletion has no integration scope"
        )
    canonical_rows = list(
        db.execute(
            select(CanonicalEvent.id, CanonicalEvent.raw_event_id).where(
                CanonicalEvent.organization_id == deletion_request.organization_id,
                CanonicalEvent.integration_connection_id
                == deletion_request.integration_connection_id,
                CanonicalEvent.source_provider == deletion_request.source_provider,
                CanonicalEvent.object_type == deletion_request.object_type,
                CanonicalEvent.object_external_id
                == deletion_request.object_external_id,
            )
        )
    )
    canonical_ids = [row[0] for row in canonical_rows]
    raw_ids = [row[1] for row in canonical_rows]
    retained_raw_ids = list(
        db.scalars(
            select(DerivedRetentionTombstone.raw_event_id).where(
                DerivedRetentionTombstone.organization_id
                == deletion_request.organization_id,
                DerivedRetentionTombstone.integration_connection_id
                == deletion_request.integration_connection_id,
                DerivedRetentionTombstone.source_provider
                == deletion_request.source_provider,
                DerivedRetentionTombstone.object_type
                == deletion_request.object_type,
                DerivedRetentionTombstone.object_external_id
                == deletion_request.object_external_id,
            )
        )
    )
    raw_ids.extend(retained_raw_ids)
    return canonical_ids, list(dict.fromkeys(raw_ids))


def execute_deletion_request(
    db: Session,
    *,
    organization_id: uuid.UUID,
    deletion_request_id: uuid.UUID,
    request_id: str | None = None,
) -> DataDeletionRequest:
    query = select(DataDeletionRequest).where(
        DataDeletionRequest.id == deletion_request_id,
        DataDeletionRequest.organization_id == organization_id,
    )
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        query = query.with_for_update()
    deletion_request = db.scalar(query)
    if deletion_request is None:
        raise DataGovernanceError("Deletion request not found")
    if deletion_request.status == DeletionStatus.COMPLETED:
        return deletion_request

    policy = db.scalar(
        select(OrganizationRetentionPolicy).where(
            OrganizationRetentionPolicy.organization_id == organization_id
        )
    )
    if policy is not None and policy.legal_hold:
        raise DataGovernanceError("Deletion is blocked by the organization legal hold")

    deletion_request.status = DeletionStatus.PROCESSING
    deletion_request.started_at = _now()
    deletion_request.error_code = None
    db.commit()

    try:
        if deletion_request.scope == DeletionScope.INTEGRATION:
            if deletion_request.integration_connection_id is None:
                raise DataGovernanceError(
                    "Deletion request has no integration target"
                )
            connection = db.scalar(
                select(IntegrationConnection).where(
                    IntegrationConnection.id
                    == deletion_request.integration_connection_id,
                    IntegrationConnection.organization_id == organization_id,
                )
            )
            if (
                connection is not None
                and connection.status != IntegrationStatus.REVOKED
            ):
                raise DataGovernanceError(
                    "Integration must remain revoked during deletion"
                )
            raw_ids = list(
                db.scalars(
                    select(RawEvent.id).where(
                        RawEvent.organization_id == organization_id,
                        RawEvent.integration_connection_id
                        == deletion_request.integration_connection_id,
                    )
                )
            )
            canonical_ids = list(
                db.scalars(
                    select(CanonicalEvent.id).where(
                        CanonicalEvent.organization_id == organization_id,
                        CanonicalEvent.integration_connection_id
                        == deletion_request.integration_connection_id,
                    )
                )
            )
        else:
            canonical_ids, raw_ids = _source_object_target_ids(
                db,
                deletion_request,
            )

        digest = _completion_digest(
            deletion_request,
            raw_ids=raw_ids,
            canonical_ids=canonical_ids,
        )
        if canonical_ids:
            db.execute(
                delete(CanonicalEvent).where(
                    CanonicalEvent.organization_id == organization_id,
                    CanonicalEvent.id.in_(canonical_ids),
                )
            )
        if raw_ids:
            db.execute(
                delete(RawEvent).where(
                    RawEvent.organization_id == organization_id,
                    RawEvent.id.in_(raw_ids),
                )
            )
        _sanitize_orphan_source_identities(db, organization_id)
        deletion_request.raw_events_deleted = len(raw_ids)
        deletion_request.canonical_events_deleted = len(canonical_ids)
        deletion_request.completion_digest = digest
        deletion_request.status = DeletionStatus.COMPLETED
        deletion_request.completed_at = _now()
        append_audit_event(
            db,
            organization_id=organization_id,
            event_key=f"deletion.completed:{deletion_request.id}",
            event_type="data.deletion.completed",
            outcome="succeeded",
            actor_user_id=deletion_request.requested_by_user_id,
            resource_type="data_deletion_request",
            resource_id=deletion_request.id,
            request_id=request_id,
            metadata={
                "scope": deletion_request.scope.value,
                "target_reference": deletion_request.target_reference,
                "raw_events_deleted": deletion_request.raw_events_deleted,
                "canonical_events_deleted": (
                    deletion_request.canonical_events_deleted
                ),
                "completion_digest": deletion_request.completion_digest,
            },
        )
        db.refresh(deletion_request)
    except (DataGovernanceError, SQLAlchemyError) as exc:
        db.rollback()
        failed = db.scalar(
            select(DataDeletionRequest).where(
                DataDeletionRequest.id == deletion_request_id,
                DataDeletionRequest.organization_id == organization_id,
            )
        )
        if failed is not None:
            failed.status = DeletionStatus.FAILED
            failed.error_code = type(exc).__name__[:128]
            db.commit()
        if isinstance(exc, DataGovernanceError):
            raise
        raise DataGovernanceError("Data deletion execution failed") from exc
    return deletion_request


def _retention_cutoff(days: int, at: datetime) -> datetime:
    return at - timedelta(days=days)


def _skip_locked(query, db: Session):
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        return query.with_for_update(skip_locked=True)
    return query


def _deleted_count(rowcount: int | None, fallback: int) -> int:
    return rowcount if rowcount is not None and rowcount >= 0 else fallback


def _derived_retention_rows(
    db: Session,
    *,
    organization_id: uuid.UUID,
    cutoff: datetime,
    limit: int,
):
    query = (
        select(
            CanonicalEvent.id,
            CanonicalEvent.raw_event_id,
            CanonicalEvent.integration_connection_id,
            CanonicalEvent.source_provider,
            CanonicalEvent.object_type,
            CanonicalEvent.object_external_id,
        )
        .join(RawEvent, RawEvent.id == CanonicalEvent.raw_event_id)
        .where(
            CanonicalEvent.organization_id == organization_id,
            func.coalesce(
                CanonicalEvent.occurred_at,
                CanonicalEvent.created_at,
            )
            < cutoff,
        )
        .order_by(CanonicalEvent.created_at, CanonicalEvent.id)
        .limit(limit)
    )
    return list(db.execute(_skip_locked(query, db)))


def _stage_derived_tombstones(
    db: Session,
    *,
    organization_id: uuid.UUID,
    rows,
    purged_at: datetime,
) -> None:
    for row in rows:
        raw_event_id = row[1]
        existing = db.scalar(
            select(DerivedRetentionTombstone).where(
                DerivedRetentionTombstone.raw_event_id == raw_event_id
            )
        )
        if existing is not None:
            locator_matches = (
                existing.organization_id == organization_id
                and existing.integration_connection_id == row[2]
                and existing.source_provider == row[3]
                and existing.object_type == row[4]
                and existing.object_external_id == row[5]
            )
            if not locator_matches:
                raise DataGovernanceError(
                    "Derived-retention tombstone locator mismatch"
                )
            continue
        db.add(
            DerivedRetentionTombstone(
                organization_id=organization_id,
                raw_event_id=raw_event_id,
                integration_connection_id=row[2],
                source_provider=row[3],
                object_type=row[4],
                object_external_id=row[5],
                purged_at=purged_at,
            )
        )


def run_retention_once(
    db: Session,
    *,
    organization_id: uuid.UUID,
    at: datetime | None = None,
    limit: int = MAX_RETENTION_BATCH,
    actor_user_id: uuid.UUID | None = None,
    request_id: str | None = None,
) -> RetentionRun | None:
    if limit < 1 or limit > MAX_RETENTION_BATCH:
        raise DataGovernanceError(
            f"Retention limit must be 1-{MAX_RETENTION_BATCH}"
        )
    policy = db.scalar(
        select(OrganizationRetentionPolicy).where(
            OrganizationRetentionPolicy.organization_id == organization_id
        )
    )
    if policy is None:
        return None
    now = at or _now()
    run = RetentionRun(
        organization_id=organization_id,
        raw_event_days=policy.raw_event_days,
        derived_content_days=policy.derived_content_days,
        audit_event_days=policy.audit_event_days,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    if policy.legal_hold:
        run.status = RetentionRunStatus.COMPLETED
        run.completed_at = now
        append_audit_event(
            db,
            organization_id=organization_id,
            event_key=f"retention.run:{run.id}",
            event_type="retention.run.skipped",
            outcome="legal_hold",
            actor_user_id=actor_user_id,
            resource_type="retention_run",
            resource_id=run.id,
            request_id=request_id,
            metadata={"legal_hold": True},
        )
        db.refresh(run)
        return run

    try:
        if policy.raw_event_days is not None:
            raw_cutoff = _retention_cutoff(policy.raw_event_days, now)
            raw_query = (
                select(RawEvent.id)
                .where(
                    RawEvent.organization_id == organization_id,
                    func.coalesce(
                        RawEvent.source_timestamp,
                        RawEvent.received_at,
                    )
                    < raw_cutoff,
                )
                .order_by(RawEvent.received_at, RawEvent.id)
                .limit(limit)
            )
            raw_ids = list(db.scalars(_skip_locked(raw_query, db)))
            if raw_ids:
                canonical_ids = list(
                    db.scalars(
                        select(CanonicalEvent.id).where(
                            CanonicalEvent.organization_id == organization_id,
                            CanonicalEvent.raw_event_id.in_(raw_ids),
                        )
                    )
                )
                if canonical_ids:
                    db.execute(
                        delete(CanonicalEvent).where(
                            CanonicalEvent.id.in_(canonical_ids)
                        )
                    )
                result = db.execute(
                    delete(RawEvent).where(
                        RawEvent.organization_id == organization_id,
                        RawEvent.id.in_(raw_ids),
                    )
                )
                run.raw_events_deleted = _deleted_count(
                    result.rowcount,
                    len(raw_ids),
                )

        if policy.derived_content_days is not None:
            derived_cutoff = _retention_cutoff(
                policy.derived_content_days,
                now,
            )
            rows = _derived_retention_rows(
                db,
                organization_id=organization_id,
                cutoff=derived_cutoff,
                limit=limit,
            )
            _stage_derived_tombstones(
                db,
                organization_id=organization_id,
                rows=rows,
                purged_at=now,
            )
            derived_ids = [row[0] for row in rows]
            if derived_ids:
                result = db.execute(
                    delete(CanonicalEvent).where(
                        CanonicalEvent.organization_id == organization_id,
                        CanonicalEvent.id.in_(derived_ids),
                    )
                )
                run.derived_events_deleted = _deleted_count(
                    result.rowcount,
                    len(derived_ids),
                )

        if policy.audit_event_days is not None:
            audit_cutoff = _retention_cutoff(policy.audit_event_days, now)
            audit_query = (
                select(SecurityAuditEvent.id)
                .where(
                    SecurityAuditEvent.organization_id == organization_id,
                    SecurityAuditEvent.created_at < audit_cutoff,
                )
                .order_by(
                    SecurityAuditEvent.created_at,
                    SecurityAuditEvent.id,
                )
                .limit(limit)
            )
            audit_ids = list(db.scalars(_skip_locked(audit_query, db)))
            if audit_ids:
                result = db.execute(
                    delete(SecurityAuditEvent).where(
                        SecurityAuditEvent.organization_id == organization_id,
                        SecurityAuditEvent.id.in_(audit_ids),
                    )
                )
                run.audit_events_deleted = _deleted_count(
                    result.rowcount,
                    len(audit_ids),
                )

        _sanitize_orphan_source_identities(db, organization_id)
        run.status = RetentionRunStatus.COMPLETED
        run.completed_at = now
        append_audit_event(
            db,
            organization_id=organization_id,
            event_key=f"retention.run:{run.id}",
            event_type="retention.run.completed",
            outcome="succeeded",
            actor_user_id=actor_user_id,
            resource_type="retention_run",
            resource_id=run.id,
            request_id=request_id,
            metadata={
                "raw_events_deleted": run.raw_events_deleted,
                "derived_events_deleted": run.derived_events_deleted,
                "audit_events_deleted": run.audit_events_deleted,
            },
        )
        db.refresh(run)
        return run
    except (DataGovernanceError, SQLAlchemyError) as exc:
        db.rollback()
        failed = db.scalar(select(RetentionRun).where(RetentionRun.id == run.id))
        if failed is not None:
            failed.status = RetentionRunStatus.FAILED
            failed.error_code = type(exc).__name__[:128]
            failed.completed_at = now
            db.commit()
        if isinstance(exc, DataGovernanceError):
            raise
        raise DataGovernanceError("Retention execution failed") from exc


def pending_deletion_requests(
    db: Session,
    *,
    organization_id: uuid.UUID,
    limit: int = 50,
    at: datetime | None = None,
) -> list[DataDeletionRequest]:
    if limit < 1 or limit > 500:
        raise DataGovernanceError("Deletion batch limit must be 1-500")
    stale_before = (at or _now()) - _DELETION_STALE_AFTER
    query = (
        select(DataDeletionRequest)
        .where(
            DataDeletionRequest.organization_id == organization_id,
            or_(
                DataDeletionRequest.status.in_(
                    [DeletionStatus.PENDING, DeletionStatus.FAILED]
                ),
                (
                    (DataDeletionRequest.status == DeletionStatus.PROCESSING)
                    & (DataDeletionRequest.started_at < stale_before)
                ),
            ),
        )
        .order_by(DataDeletionRequest.created_at, DataDeletionRequest.id)
        .limit(limit)
    )
    return list(db.scalars(_skip_locked(query, db)))

import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.canonical_events import canonicalize_raw_event
from app.data_governance import (
    DataGovernanceError,
    append_audit_event,
    create_deletion_request,
    execute_deletion_request,
    pending_deletion_requests,
    run_retention_once,
    set_retention_policy,
)
from app.data_governance_models import (
    DataDeletionRequest,
    DeletionScope,
    DeletionStatus,
    DerivedRetentionTombstone,
    SecurityAuditEvent,
)
from app.models import (
    CanonicalEvent,
    IntegrationConnection,
    IntegrationHealth,
    IntegrationStatus,
    Membership,
    MembershipRole,
    Organization,
    RawEvent,
    User,
)
from app.permissions import Permission, role_has_permission
from app.raw_events import persist_raw_event
from app.search_models import SearchDocument


def _enable_foreign_keys(db: Session) -> None:
    db.execute(text("PRAGMA foreign_keys=ON"))
    db.commit()


def _seed(db: Session, suffix: str):
    owner = User(email=f"governance-owner-{suffix}@example.com")
    admin = User(email=f"governance-admin-{suffix}@example.com")
    executive = User(email=f"governance-exec-{suffix}@example.com")
    member = User(email=f"governance-member-{suffix}@example.com")
    organization = Organization(name=f"Governance {suffix}", slug=f"governance-{suffix}")
    db.add_all([owner, admin, executive, member, organization])
    db.flush()
    db.add_all(
        [
            Membership(
                organization_id=organization.id,
                user_id=owner.id,
                role=MembershipRole.OWNER,
            ),
            Membership(
                organization_id=organization.id,
                user_id=admin.id,
                role=MembershipRole.ADMIN,
            ),
            Membership(
                organization_id=organization.id,
                user_id=executive.id,
                role=MembershipRole.EXECUTIVE,
            ),
            Membership(
                organization_id=organization.id,
                user_id=member.id,
                role=MembershipRole.MEMBER,
            ),
        ]
    )
    connection = IntegrationConnection(
        organization_id=organization.id,
        provider="slack",
        external_account_id=f"workspace-{suffix}",
        display_name=f"Slack {suffix}",
        status=IntegrationStatus.ACTIVE,
        health=IntegrationHealth.HEALTHY,
        scopes=["channels:history"],
        provider_metadata={},
        secret_ref=f"arn:test:{suffix}",
        created_by_user_id=owner.id,
    )
    db.add(connection)
    db.commit()
    return organization, owner, admin, executive, member, connection


def _message_evidence(
    db: Session,
    *,
    organization: Organization,
    connection: IntegrationConnection,
    event_id: str,
    message_ts: str,
    occurred_at: datetime,
):
    payload = {
        "event": {
            "type": "message",
            "channel": "C-governance",
            "user": "U-governance",
            "text": "Decision: retain only governed evidence.",
            "ts": message_ts,
            "event_ts": message_ts,
        }
    }
    persisted = persist_raw_event(
        db,
        organization_id=organization.id,
        integration_connection_id=connection.id,
        provider="slack",
        source_event_id=event_id,
        source_event_type="message",
        delivery_kind="webhook",
        raw_payload=json.dumps(payload).encode(),
        content_type="application/json",
        source_visibility="organization",
        source_acl=[],
        source_timestamp=occurred_at,
    )
    canonical = canonicalize_raw_event(db, persisted.event)
    assert canonical.event is not None
    document = SearchDocument(
        organization_id=organization.id,
        canonical_event_id=canonical.event.id,
        integration_connection_id=connection.id,
        source_provider="slack",
        source_visibility="organization",
        source_acl=[],
        channel_id="C-governance",
        repository_id=None,
        object_type=canonical.event.object_type,
        object_external_id=canonical.event.object_external_id,
        title="Governance decision",
        content="Decision: retain only governed evidence.",
        provenance={"source_event_id": event_id},
        occurred_at=occurred_at,
    )
    db.add(document)
    db.commit()
    return persisted.event, canonical.event, document


def test_data_governance_permission_is_owner_admin_only() -> None:
    assert role_has_permission(MembershipRole.OWNER, Permission.DATA_GOVERNANCE_MANAGE)
    assert role_has_permission(MembershipRole.ADMIN, Permission.DATA_GOVERNANCE_MANAGE)
    assert not role_has_permission(
        MembershipRole.EXECUTIVE,
        Permission.DATA_GOVERNANCE_MANAGE,
    )
    assert not role_has_permission(MembershipRole.MANAGER, Permission.DATA_GOVERNANCE_MANAGE)
    assert not role_has_permission(MembershipRole.MEMBER, Permission.DATA_GOVERNANCE_MANAGE)
    assert not role_has_permission(MembershipRole.GUEST, Permission.DATA_GOVERNANCE_MANAGE)


def test_audit_event_is_idempotent_and_event_key_cannot_change_meaning(
    db_session: Session,
) -> None:
    organization, owner, _, _, _, _ = _seed(db_session, "audit-idempotent")
    first = append_audit_event(
        db_session,
        organization_id=organization.id,
        event_key="stable-event-key",
        event_type="security.test",
        outcome="succeeded",
        actor_user_id=owner.id,
        resource_type="test",
        resource_id="one",
        metadata={"code": "safe"},
    )
    replay = append_audit_event(
        db_session,
        organization_id=organization.id,
        event_key="stable-event-key",
        event_type="security.test",
        outcome="succeeded",
        actor_user_id=owner.id,
        resource_type="test",
        resource_id="one",
        metadata={"code": "safe"},
    )
    assert replay.id == first.id

    with pytest.raises(DataGovernanceError, match="reused with different content"):
        append_audit_event(
            db_session,
            organization_id=organization.id,
            event_key="stable-event-key",
            event_type="security.test",
            outcome="failed",
            actor_user_id=owner.id,
        )


def test_source_object_deletion_removes_evidence_and_suppresses_reingestion(
    db_session: Session,
) -> None:
    _enable_foreign_keys(db_session)
    organization, owner, _, _, _, connection = _seed(db_session, "source-delete")
    now = datetime.now(UTC)
    raw, canonical, document = _message_evidence(
        db_session,
        organization=organization,
        connection=connection,
        event_id="event-delete-1",
        message_ts="1710000000.000100",
        occurred_at=now,
    )
    raw_id = raw.id
    canonical_id = canonical.id
    document_id = document.id
    deletion = create_deletion_request(
        db_session,
        organization_id=organization.id,
        actor_user_id=owner.id,
        request_key="delete-message-1",
        scope=DeletionScope.SOURCE_OBJECT,
        reason="customer deletion request",
        source_provider=canonical.source_provider,
        object_type=canonical.object_type,
        object_external_id=canonical.object_external_id,
    )
    completed = execute_deletion_request(
        db_session,
        organization_id=organization.id,
        deletion_request_id=deletion.id,
    )
    assert completed.status == DeletionStatus.COMPLETED
    assert completed.raw_events_deleted == 1
    assert completed.canonical_events_deleted == 1
    assert completed.completion_digest is not None
    assert completed.target_reference.startswith(
        f"source:{connection.id}:slack:message:"
    )

    db_session.expire_all()
    assert db_session.get(RawEvent, raw_id) is None
    assert db_session.get(CanonicalEvent, canonical_id) is None
    assert db_session.get(SearchDocument, document_id) is None

    replay_payload = {
        "event": {
            "type": "message",
            "channel": "C-governance",
            "user": "U-governance",
            "text": "Decision: retain only governed evidence.",
            "ts": "1710000000.000100",
            "event_ts": "1710000000.000100",
        }
    }
    replay = persist_raw_event(
        db_session,
        organization_id=organization.id,
        integration_connection_id=connection.id,
        provider="slack",
        source_event_id="event-delete-2",
        source_event_type="message",
        delivery_kind="webhook",
        raw_payload=json.dumps(replay_payload).encode(),
        content_type="application/json",
        source_visibility="organization",
        source_acl=[],
        source_timestamp=now,
    )
    replay_raw_id = replay.event.id
    result = canonicalize_raw_event(db_session, replay.event)
    assert result.event is None
    db_session.expire_all()
    assert db_session.get(RawEvent, replay_raw_id) is None


def test_derived_retention_keeps_raw_but_prevents_rebuild(db_session: Session) -> None:
    _enable_foreign_keys(db_session)
    organization, owner, _, _, _, connection = _seed(db_session, "derived-retention")
    now = datetime.now(UTC)
    raw, canonical, document = _message_evidence(
        db_session,
        organization=organization,
        connection=connection,
        event_id="event-derived-old",
        message_ts="1600000000.000100",
        occurred_at=now - timedelta(days=90),
    )
    raw_id = raw.id
    canonical_id = canonical.id
    document_id = document.id
    set_retention_policy(
        db_session,
        organization_id=organization.id,
        actor_user_id=owner.id,
        raw_event_days=None,
        derived_content_days=30,
        audit_event_days=None,
        legal_hold=False,
    )
    run = run_retention_once(db_session, organization_id=organization.id, at=now)
    assert run is not None
    assert run.derived_events_deleted == 1

    db_session.expire_all()
    retained_raw = db_session.get(RawEvent, raw_id)
    assert retained_raw is not None
    assert db_session.get(CanonicalEvent, canonical_id) is None
    assert db_session.get(SearchDocument, document_id) is None
    tombstone = db_session.scalar(
        select(DerivedRetentionTombstone).where(
            DerivedRetentionTombstone.raw_event_id == raw_id
        )
    )
    assert tombstone is not None
    rebuilt = canonicalize_raw_event(db_session, retained_raw)
    assert rebuilt.event is None


def test_raw_retention_deletes_raw_and_canonical_chain(db_session: Session) -> None:
    _enable_foreign_keys(db_session)
    organization, owner, _, _, _, connection = _seed(db_session, "raw-retention")
    now = datetime.now(UTC)
    raw, canonical, _ = _message_evidence(
        db_session,
        organization=organization,
        connection=connection,
        event_id="event-raw-old",
        message_ts="1500000000.000100",
        occurred_at=now - timedelta(days=90),
    )
    set_retention_policy(
        db_session,
        organization_id=organization.id,
        actor_user_id=owner.id,
        raw_event_days=30,
        derived_content_days=None,
        audit_event_days=None,
        legal_hold=False,
    )
    run = run_retention_once(db_session, organization_id=organization.id, at=now)
    assert run is not None
    assert run.raw_events_deleted == 1
    db_session.expire_all()
    assert db_session.get(RawEvent, raw.id) is None
    assert db_session.get(CanonicalEvent, canonical.id) is None


def test_legal_hold_blocks_deletion_and_retention_purge(db_session: Session) -> None:
    _enable_foreign_keys(db_session)
    organization, owner, _, _, _, connection = _seed(db_session, "legal-hold")
    now = datetime.now(UTC)
    raw, _, _ = _message_evidence(
        db_session,
        organization=organization,
        connection=connection,
        event_id="event-held",
        message_ts="1400000000.000100",
        occurred_at=now - timedelta(days=365),
    )
    set_retention_policy(
        db_session,
        organization_id=organization.id,
        actor_user_id=owner.id,
        raw_event_days=1,
        derived_content_days=1,
        audit_event_days=1,
        legal_hold=True,
    )
    run = run_retention_once(db_session, organization_id=organization.id, at=now)
    assert run is not None
    assert run.raw_events_deleted == 0
    assert run.derived_events_deleted == 0
    db_session.expire_all()
    assert db_session.get(RawEvent, raw.id) is not None

    with pytest.raises(DataGovernanceError, match="legal hold"):
        create_deletion_request(
            db_session,
            organization_id=organization.id,
            actor_user_id=owner.id,
            request_key="blocked-delete",
            scope=DeletionScope.SOURCE_OBJECT,
            reason="blocked by hold",
            source_provider="slack",
            object_type="message",
            object_external_id="C-governance:1400000000.000100",
        )


def test_audit_retention_deletes_only_expired_audit_rows(db_session: Session) -> None:
    organization, owner, _, _, _, _ = _seed(db_session, "audit-retention")
    now = datetime.now(UTC)
    old_event = SecurityAuditEvent(
        organization_id=organization.id,
        event_key="old-audit-event",
        event_type="security.old",
        outcome="succeeded",
        actor_user_id=owner.id,
        metadata_json={},
        payload_sha256="a" * 64,
        created_at=now - timedelta(days=90),
    )
    db_session.add(old_event)
    db_session.commit()
    set_retention_policy(
        db_session,
        organization_id=organization.id,
        actor_user_id=owner.id,
        raw_event_days=None,
        derived_content_days=None,
        audit_event_days=30,
        legal_hold=False,
    )
    run = run_retention_once(db_session, organization_id=organization.id, at=now)
    assert run is not None
    assert run.audit_events_deleted == 1
    assert db_session.get(SecurityAuditEvent, old_event.id) is None
    completion = db_session.scalar(
        select(SecurityAuditEvent).where(
            SecurityAuditEvent.event_key == f"retention.run:{run.id}"
        )
    )
    assert completion is not None


def test_integration_deletion_requires_revocation_and_is_tenant_scoped(
    db_session: Session,
) -> None:
    organization, owner, _, _, _, connection = _seed(db_session, "integration-a")
    other, other_owner, _, _, _, other_connection = _seed(db_session, "integration-b")
    with pytest.raises(DataGovernanceError, match="fully revoked"):
        create_deletion_request(
            db_session,
            organization_id=organization.id,
            actor_user_id=owner.id,
            request_key="active-integration",
            scope=DeletionScope.INTEGRATION,
            reason="should fail",
            integration_connection_id=connection.id,
        )
    connection.status = IntegrationStatus.REVOKED
    db_session.commit()
    accepted = create_deletion_request(
        db_session,
        organization_id=organization.id,
        actor_user_id=owner.id,
        request_key="revoked-integration",
        scope=DeletionScope.INTEGRATION,
        reason="retire source",
        integration_connection_id=connection.id,
    )
    assert accepted.target_reference == f"integration:{connection.id}"

    other_connection.status = IntegrationStatus.REVOKED
    db_session.commit()
    with pytest.raises(DataGovernanceError, match="not found"):
        create_deletion_request(
            db_session,
            organization_id=organization.id,
            actor_user_id=owner.id,
            request_key="cross-tenant",
            scope=DeletionScope.INTEGRATION,
            reason="must fail",
            integration_connection_id=other_connection.id,
        )
    assert other_owner.id != owner.id
    assert other.id != organization.id


def test_stale_processing_deletion_is_recoverable(db_session: Session) -> None:
    organization, owner, _, _, _, _ = _seed(db_session, "stale")
    request = DataDeletionRequest(
        organization_id=organization.id,
        request_key="stale-request",
        scope=DeletionScope.SOURCE_OBJECT,
        target_reference="source:slack:message:C1:1",
        source_provider="slack",
        object_type="message",
        object_external_id="C1:1",
        status=DeletionStatus.PROCESSING,
        requested_by_user_id=owner.id,
        reason="recover worker",
        started_at=datetime.now(UTC) - timedelta(minutes=20),
    )
    db_session.add(request)
    db_session.commit()
    pending = pending_deletion_requests(
        db_session,
        organization_id=organization.id,
        at=datetime.now(UTC),
    )
    assert request.id in {item.id for item in pending}

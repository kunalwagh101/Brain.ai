import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.canonical_events import canonicalize_raw_event
from app.data_governance import (
    create_deletion_request,
    execute_deletion_request,
    run_retention_once,
    set_retention_policy,
)
from app.data_governance_models import (
    DeletionScope,
    DeletionStatus,
    DerivedRetentionTombstone,
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
from app.raw_events import persist_raw_event


def test_source_deletion_finds_raw_after_derived_retention(
    db_session: Session,
) -> None:
    db_session.execute(text("PRAGMA foreign_keys=ON"))
    owner = User(email="retained-raw-owner@example.com")
    organization = Organization(
        name="Retained Raw Org",
        slug="retained-raw-org",
    )
    db_session.add_all([owner, organization])
    db_session.flush()
    db_session.add(
        Membership(
            organization_id=organization.id,
            user_id=owner.id,
            role=MembershipRole.OWNER,
        )
    )
    connection = IntegrationConnection(
        organization_id=organization.id,
        provider="slack",
        external_account_id="retained-workspace",
        display_name="Retained Slack",
        status=IntegrationStatus.ACTIVE,
        health=IntegrationHealth.HEALTHY,
        scopes=["channels:history"],
        provider_metadata={},
        secret_ref="arn:test:retained-raw",
        created_by_user_id=owner.id,
    )
    db_session.add(connection)
    db_session.commit()

    occurred_at = datetime.now(UTC) - timedelta(days=90)
    message_ts = "1600000000.000100"
    raw_result = persist_raw_event(
        db_session,
        organization_id=organization.id,
        integration_connection_id=connection.id,
        provider="slack",
        source_event_id="retained-raw-event",
        source_event_type="message",
        delivery_kind="webhook",
        raw_payload=json.dumps(
            {
                "event": {
                    "type": "message",
                    "channel": "C-retained",
                    "user": "U-retained",
                    "text": "Decision: remove this evidence later.",
                    "ts": message_ts,
                    "event_ts": message_ts,
                }
            }
        ).encode(),
        content_type="application/json",
        source_visibility="organization",
        source_acl=[],
        source_timestamp=occurred_at,
    )
    canonical_result = canonicalize_raw_event(db_session, raw_result.event)
    assert canonical_result.event is not None
    canonical = canonical_result.event
    raw_id = raw_result.event.id
    canonical_id = canonical.id
    object_external_id = canonical.object_external_id

    set_retention_policy(
        db_session,
        organization_id=organization.id,
        actor_user_id=owner.id,
        raw_event_days=None,
        derived_content_days=30,
        audit_event_days=None,
        legal_hold=False,
    )
    run = run_retention_once(
        db_session,
        organization_id=organization.id,
        at=datetime.now(UTC),
    )
    assert run is not None
    assert run.derived_events_deleted == 1
    db_session.expire_all()
    assert db_session.get(RawEvent, raw_id) is not None
    assert db_session.get(CanonicalEvent, canonical_id) is None

    tombstone = db_session.scalar(
        select(DerivedRetentionTombstone).where(
            DerivedRetentionTombstone.raw_event_id == raw_id
        )
    )
    assert tombstone is not None
    assert tombstone.source_provider == "slack"
    assert tombstone.object_type == "message"
    assert tombstone.object_external_id == object_external_id

    deletion = create_deletion_request(
        db_session,
        organization_id=organization.id,
        actor_user_id=owner.id,
        request_key="delete-retained-raw",
        scope=DeletionScope.SOURCE_OBJECT,
        reason="customer requested deletion",
        source_provider="slack",
        object_type="message",
        object_external_id=object_external_id,
    )
    completed = execute_deletion_request(
        db_session,
        organization_id=organization.id,
        deletion_request_id=deletion.id,
    )

    assert completed.status == DeletionStatus.COMPLETED
    assert completed.raw_events_deleted == 1
    assert completed.canonical_events_deleted == 0
    db_session.expire_all()
    assert db_session.get(RawEvent, raw_id) is None

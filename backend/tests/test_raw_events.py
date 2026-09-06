import hashlib

import pytest
from sqlalchemy.orm import Session

from app.models import (
    IntegrationConnection,
    IntegrationHealth,
    IntegrationStatus,
    Membership,
    MembershipRole,
    Organization,
    RawEvent,
    User,
)
from app.raw_events import MAX_RAW_EVENT_BYTES, RawEventRejectedError, persist_raw_event


def _seed_connection(db: Session) -> tuple[Organization, IntegrationConnection, User]:
    user = User(email="raw-owner@example.com")
    organization = Organization(name="Acme", slug="raw-acme")
    db.add_all([user, organization])
    db.flush()
    db.add(
        Membership(
            organization_id=organization.id,
            user_id=user.id,
            role=MembershipRole.OWNER,
        )
    )
    connection = IntegrationConnection(
        organization_id=organization.id,
        provider="slack",
        external_account_id="T-RAW",
        display_name="Acme Slack",
        status=IntegrationStatus.ACTIVE,
        health=IntegrationHealth.HEALTHY,
        scopes=["channels:history"],
        secret_ref="arn:secret:raw",
        created_by_user_id=user.id,
    )
    db.add(connection)
    db.commit()
    return organization, connection, user


def test_raw_event_preserves_exact_bytes_and_checksum(db_session: Session) -> None:
    organization, connection, _ = _seed_connection(db_session)
    raw = b'{"event":{"text":"hello  world"},"event_id":"Ev1"}\n'

    result = persist_raw_event(
        db_session,
        organization_id=organization.id,
        integration_connection_id=connection.id,
        provider="slack",
        source_event_id="Ev1",
        source_event_type="message",
        delivery_kind="webhook",
        raw_payload=raw,
        content_type="application/json",
        source_visibility="private_channel",
        source_acl=["U1", "U2", "U1"],
    )

    assert result.created is True
    event = db_session.query(RawEvent).one()
    assert event.raw_payload == raw
    assert event.payload_sha256 == hashlib.sha256(raw).hexdigest()
    assert event.source_acl == ["U1", "U2"]


def test_raw_event_retry_is_idempotent(db_session: Session) -> None:
    organization, connection, _ = _seed_connection(db_session)
    kwargs = {
        "organization_id": organization.id,
        "integration_connection_id": connection.id,
        "provider": "slack",
        "source_event_id": "Ev-retry",
        "source_event_type": "message",
        "delivery_kind": "webhook",
        "raw_payload": b'{"event_id":"Ev-retry"}',
        "content_type": "application/json",
        "source_visibility": "public_channel",
        "source_acl": [],
    }

    first = persist_raw_event(db_session, **kwargs)
    second = persist_raw_event(db_session, **kwargs)

    assert first.created is True
    assert second.created is False
    assert first.event.id == second.event.id
    assert db_session.query(RawEvent).count() == 1


def test_raw_event_rejects_oversized_payload(db_session: Session) -> None:
    organization, connection, _ = _seed_connection(db_session)

    with pytest.raises(RawEventRejectedError):
        persist_raw_event(
            db_session,
            organization_id=organization.id,
            integration_connection_id=connection.id,
            provider="slack",
            source_event_id="Ev-large",
            source_event_type="message",
            delivery_kind="webhook",
            raw_payload=b"x" * (MAX_RAW_EVENT_BYTES + 1),
            content_type="application/json",
            source_visibility="public_channel",
            source_acl=[],
        )

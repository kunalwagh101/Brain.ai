import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.canonical_events import CANONICAL_EVENT_SCHEMA_VERSION, canonicalize_raw_event
from app.models import (
    CanonicalEvent,
    IntegrationConnection,
    IntegrationHealth,
    IntegrationStatus,
    Organization,
    RawEventStatus,
    User,
)
from app.raw_events import persist_raw_event


def _seed_connection(db: Session, *, provider: str) -> tuple[Organization, IntegrationConnection]:
    user = User(email=f"canonical-{provider}@example.com")
    organization = Organization(name=f"Canonical {provider}", slug=f"canonical-{provider}")
    db.add_all([user, organization])
    db.flush()
    connection = IntegrationConnection(
        organization_id=organization.id,
        provider=provider,
        external_account_id=f"{provider}-account",
        display_name=f"{provider.title()} account",
        status=IntegrationStatus.ACTIVE,
        health=IntegrationHealth.HEALTHY,
        scopes=[],
        provider_metadata={},
        secret_ref="arn:secret:test" if provider != "github" else None,
        created_by_user_id=user.id,
    )
    db.add(connection)
    db.commit()
    return organization, connection


def test_slack_backfill_message_maps_to_versioned_canonical_event(db_session: Session) -> None:
    organization, connection = _seed_connection(db_session, provider="slack")
    payload = json.dumps(
        {
            "team_id": "T123",
            "channel_id": "C123",
            "message": {
                "ts": "1720000000.123",
                "user": "U123",
                "text": "Production launch is approved",
                "thread_ts": "1719999999.999",
            },
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    persisted = persist_raw_event(
        db_session,
        organization_id=organization.id,
        integration_connection_id=connection.id,
        provider="slack",
        source_event_id="history:C123:1720000000.123",
        source_event_type="message",
        delivery_kind="backfill",
        raw_payload=payload,
        content_type="application/json",
        source_visibility="private_channel",
        source_acl=["U123", "U456"],
    )

    result = canonicalize_raw_event(db_session, persisted.event)

    assert result.created is True
    assert result.quarantined is False
    assert result.event is not None
    assert result.event.schema_version == CANONICAL_EVENT_SCHEMA_VERSION == 1
    assert result.event.event_type == "message.created"
    assert result.event.actor_type == "slack_user"
    assert result.event.actor_external_id == "U123"
    assert result.event.object_type == "message"
    assert result.event.object_external_id == "C123:1720000000.123"
    assert result.event.source_provider == "slack"
    assert result.event.source_acl == ["U123", "U456"]
    assert result.event.provenance["raw_event_id"] == str(persisted.event.id)
    assert result.event.provenance["payload_sha256"] == persisted.event.payload_sha256
    assert result.event.event_metadata["thread_ts"] == "1719999999.999"
    assert persisted.event.processing_status == RawEventStatus.PROCESSED


def test_canonicalization_is_idempotent_per_raw_event(db_session: Session) -> None:
    organization, connection = _seed_connection(db_session, provider="slack")
    persisted = persist_raw_event(
        db_session,
        organization_id=organization.id,
        integration_connection_id=connection.id,
        provider="slack",
        source_event_id="event-one",
        source_event_type="message",
        delivery_kind="backfill",
        raw_payload=b'{"channel_id":"C1","message":{"ts":"1.0","user":"U1"}}',
        content_type="application/json",
        source_visibility="public_channel",
        source_acl=[],
    )

    first = canonicalize_raw_event(db_session, persisted.event)
    second = canonicalize_raw_event(db_session, persisted.event)

    assert first.created is True
    assert second.created is False
    count = db_session.scalar(select(func.count()).select_from(CanonicalEvent))
    assert count == 1


def test_unsupported_event_is_quarantined_without_losing_raw_evidence(
    db_session: Session,
) -> None:
    organization, connection = _seed_connection(db_session, provider="slack")
    raw_payload = b'{"event":{"type":"reaction_added"}}'
    persisted = persist_raw_event(
        db_session,
        organization_id=organization.id,
        integration_connection_id=connection.id,
        provider="slack",
        source_event_id="unsupported-one",
        source_event_type="reaction_added",
        delivery_kind="webhook",
        raw_payload=raw_payload,
        content_type="application/json",
        source_visibility="public_channel",
        source_acl=[],
    )

    result = canonicalize_raw_event(db_session, persisted.event)

    assert result.event is None
    assert result.quarantined is True
    assert persisted.event.processing_status == RawEventStatus.QUARANTINED
    assert persisted.event.last_error_code == "unsupported_slack_event:reaction_added"
    assert persisted.event.raw_payload == raw_payload
    assert db_session.scalar(select(func.count()).select_from(CanonicalEvent)) == 0


def test_github_pull_request_preserves_repository_acl_and_provenance(
    db_session: Session,
) -> None:
    organization, connection = _seed_connection(db_session, provider="github")
    raw_payload = json.dumps(
        {
            "action": "opened",
            "installation": {"id": 42},
            "sender": {"id": 7, "login": "octocat"},
            "repository": {
                "id": 101,
                "full_name": "acme/private-repo",
                "visibility": "private",
                "private": True,
            },
            "pull_request": {
                "id": 555,
                "number": 9,
                "title": "Ship canonical events",
                "state": "open",
                "html_url": "https://github.com/acme/private-repo/pull/9",
                "created_at": "2026-09-06T12:00:00Z",
            },
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    persisted = persist_raw_event(
        db_session,
        organization_id=organization.id,
        integration_connection_id=connection.id,
        provider="github",
        source_event_id="delivery-123",
        source_event_type="pull_request",
        delivery_kind="webhook",
        raw_payload=raw_payload,
        content_type="application/json",
        source_visibility="private_repository",
        source_acl=["github:repository:101"],
    )

    result = canonicalize_raw_event(db_session, persisted.event)

    assert result.event is not None
    assert result.event.event_type == "pull_request.opened"
    assert result.event.actor_external_id == "7"
    assert result.event.actor_display_name == "octocat"
    assert result.event.object_external_id == "555"
    assert result.event.object_display_name == "Ship canonical events"
    assert result.event.source_visibility == "private_repository"
    assert result.event.source_acl == ["github:repository:101"]
    assert result.event.provenance["raw_event_id"] == str(persisted.event.id)
    assert result.event.event_metadata["repository"] == "acme/private-repo"

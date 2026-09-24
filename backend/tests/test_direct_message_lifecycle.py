import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.data_governance import run_retention_once, set_retention_policy
from app.data_governance_models import SecurityAuditEvent
from app.direct_message_models import (
    DirectMessage,
    DirectMessageRevision,
)
from app.main import app
from app.models import (
    CanonicalEvent,
    Membership,
    MembershipRole,
    Organization,
    RawEvent,
    User,
)
from app.search_models import SearchDocument


def _seed(db: Session):
    alice = User(email="dm-life-alice@example.com", display_name="Alice")
    bob = User(email="dm-life-bob@example.com", display_name="Bob")
    owner = User(email="dm-life-owner@example.com", display_name="Owner")
    organization = Organization(name="DM Lifecycle Org", slug="dm-lifecycle-org")
    db.add_all([alice, bob, owner, organization])
    db.flush()
    db.add_all(
        [
            Membership(
                organization_id=organization.id,
                user_id=alice.id,
                role=MembershipRole.MEMBER,
            ),
            Membership(
                organization_id=organization.id,
                user_id=bob.id,
                role=MembershipRole.MEMBER,
            ),
            Membership(
                organization_id=organization.id,
                user_id=owner.id,
                role=MembershipRole.OWNER,
            ),
        ]
    )
    db.commit()
    return organization, alice, bob, owner


def _as(user: User) -> None:
    app.dependency_overrides[get_current_user] = lambda: user


def _clear() -> None:
    app.dependency_overrides.pop(get_current_user, None)


def _create_dm(
    client: TestClient,
    organization: Organization,
    actor: User,
    target: User,
):
    _as(actor)
    try:
        response = client.post(
            f"/api/v1/organizations/{organization.id}/direct-messages",
            json={"target_email": target.email},
        )
    finally:
        _clear()
    assert response.status_code == 201
    return response.json()


def _send(
    client: TestClient,
    organization: Organization,
    conversation_id: str,
    actor: User,
    body: str,
    key: str,
):
    _as(actor)
    try:
        response = client.post(
            f"/api/v1/organizations/{organization.id}/direct-messages/"
            f"{conversation_id}/messages",
            json={"body": body},
            headers={"Idempotency-Key": key},
        )
    finally:
        _clear()
    assert response.status_code == 201
    return response.json()


def _lifecycle_counts(db: Session, organization_id: uuid.UUID) -> dict[str, int]:
    return {
        "raw": int(
            db.scalar(
                select(func.count(RawEvent.id)).where(
                    RawEvent.organization_id == organization_id
                )
            )
            or 0
        ),
        "canonical": int(
            db.scalar(
                select(func.count(CanonicalEvent.id)).where(
                    CanonicalEvent.organization_id == organization_id
                )
            )
            or 0
        ),
        "search": int(
            db.scalar(
                select(func.count(SearchDocument.id)).where(
                    SearchDocument.organization_id == organization_id
                )
            )
            or 0
        ),
    }


def test_dm_author_edit_is_revisioned_and_stale_or_non_author_mutation_fails(
    client: TestClient,
    db_session: Session,
) -> None:
    organization, alice, bob, owner = _seed(db_session)
    conversation = _create_dm(client, organization, alice, bob)
    created = _send(
        client,
        organization,
        conversation["id"],
        alice,
        "Original private wording",
        "dm-life-edit",
    )
    endpoint = (
        f"/api/v1/organizations/{organization.id}/direct-messages/"
        f"{conversation['id']}/messages/{created['id']}"
    )

    _as(alice)
    try:
        edited = client.patch(
            endpoint,
            json={
                "body": "Corrected private wording",
                "expected_revision": 1,
            },
        )
        stale = client.patch(
            endpoint,
            json={
                "body": "Stale overwrite",
                "expected_revision": 1,
            },
        )
    finally:
        _clear()

    assert edited.status_code == 200
    assert edited.json()["body"] == "Corrected private wording"
    assert edited.json()["revision"] == 2
    assert edited.json()["edited_at"] is not None
    assert edited.json()["can_edit"] is True
    assert stale.status_code == 409

    revision = db_session.scalar(
        select(DirectMessageRevision).where(
            DirectMessageRevision.message_id == uuid.UUID(created["id"])
        )
    )
    assert revision is not None
    assert revision.revision == 1
    assert revision.action == "edit"
    assert revision.body == "Original private wording"

    for actor in (bob, owner):
        _as(actor)
        try:
            denied = client.patch(
                endpoint,
                json={
                    "body": "Must not be accepted",
                    "expected_revision": 2,
                },
            )
        finally:
            _clear()
        assert denied.status_code == 404


def test_dm_retraction_returns_tombstone_clears_unread_and_creates_no_company_evidence(
    client: TestClient,
    db_session: Session,
) -> None:
    organization, alice, bob, _ = _seed(db_session)
    conversation = _create_dm(client, organization, alice, bob)
    before = _lifecycle_counts(db_session, organization.id)
    created = _send(
        client,
        organization,
        conversation["id"],
        alice,
        "Private message to retract",
        "dm-life-retract",
    )

    _as(bob)
    try:
        before_unread = client.get(
            f"/api/v1/organizations/{organization.id}/direct-messages"
        )
    finally:
        _clear()
    assert before_unread.json()[0]["unread_count"] == 1
    assert before_unread.json()[0]["first_unread_message_id"] == created["id"]

    endpoint = (
        f"/api/v1/organizations/{organization.id}/direct-messages/"
        f"{conversation['id']}/messages/{created['id']}"
    )
    _as(alice)
    try:
        retracted = client.request(
            "DELETE",
            endpoint,
            json={"expected_revision": 1},
        )
    finally:
        _clear()
    assert retracted.status_code == 200
    assert retracted.json()["revision"] == 2
    assert retracted.json()["deleted_at"] is not None
    assert retracted.json()["body"] == ""
    assert retracted.json()["body_sha256"] == ""
    assert retracted.json()["can_edit"] is False
    assert retracted.json()["can_delete"] is False

    _as(bob)
    try:
        after_unread = client.get(
            f"/api/v1/organizations/{organization.id}/direct-messages"
        )
        tombstone = client.get(endpoint)
    finally:
        _clear()
    assert after_unread.status_code == 200
    assert after_unread.json()[0]["unread_count"] == 0
    assert after_unread.json()[0]["first_unread_message_id"] is None
    assert tombstone.status_code == 200
    assert tombstone.json()["body"] == ""
    assert tombstone.json()["deleted_at"] is not None

    after = _lifecycle_counts(db_session, organization.id)
    assert after == before
    dm_lifecycle_audit = db_session.scalar(
        select(SecurityAuditEvent.id)
        .where(
            SecurityAuditEvent.organization_id == organization.id,
            SecurityAuditEvent.event_type.like("direct_message.%"),
        )
        .limit(1)
    )
    assert dm_lifecycle_audit is None

    revision = db_session.scalar(
        select(DirectMessageRevision).where(
            DirectMessageRevision.message_id == uuid.UUID(created["id"])
        )
    )
    assert revision is not None
    assert revision.action == "retract"
    assert revision.body == "Private message to retract"


def test_reactivated_participant_cannot_mutate_old_private_epoch(
    client: TestClient,
    db_session: Session,
) -> None:
    organization, alice, bob, owner = _seed(db_session)
    conversation = _create_dm(client, organization, alice, bob)
    old = _send(
        client,
        organization,
        conversation["id"],
        alice,
        "Old epoch author message",
        "dm-life-old-epoch",
    )
    membership = db_session.scalar(
        select(Membership).where(
            Membership.organization_id == organization.id,
            Membership.user_id == alice.id,
        )
    )
    assert membership is not None

    _as(owner)
    try:
        downgrade = client.post(
            f"/api/v1/organizations/{organization.id}/memberships/"
            f"{membership.id}/role",
            json={"role": "guest"},
        )
        restore = client.post(
            f"/api/v1/organizations/{organization.id}/memberships/"
            f"{membership.id}/role",
            json={"role": "member"},
        )
    finally:
        _clear()
    assert downgrade.status_code == 200
    assert restore.status_code == 200

    reopened = _create_dm(client, organization, alice, bob)
    assert reopened["id"] == conversation["id"]

    endpoint = (
        f"/api/v1/organizations/{organization.id}/direct-messages/"
        f"{conversation['id']}/messages/{old['id']}"
    )
    _as(alice)
    try:
        edit = client.patch(
            endpoint,
            json={"body": "Must stay hidden", "expected_revision": 1},
        )
        retract = client.request(
            "DELETE",
            endpoint,
            json={"expected_revision": 1},
        )
    finally:
        _clear()
    assert edit.status_code == 404
    assert retract.status_code == 404


def test_private_retention_deletes_dm_revision_with_message(
    client: TestClient,
    db_session: Session,
) -> None:
    organization, alice, bob, owner = _seed(db_session)
    conversation = _create_dm(client, organization, alice, bob)
    created = _send(
        client,
        organization,
        conversation["id"],
        alice,
        "Retention original",
        "dm-life-retention",
    )
    endpoint = (
        f"/api/v1/organizations/{organization.id}/direct-messages/"
        f"{conversation['id']}/messages/{created['id']}"
    )
    _as(alice)
    try:
        edited = client.patch(
            endpoint,
            json={"body": "Retention current", "expected_revision": 1},
        )
    finally:
        _clear()
    assert edited.status_code == 200

    message_id = uuid.UUID(created["id"])
    message = db_session.get(DirectMessage, message_id)
    revision = db_session.scalar(
        select(DirectMessageRevision).where(
            DirectMessageRevision.message_id == message_id
        )
    )
    assert message is not None
    assert revision is not None
    now = datetime.now(UTC)
    message.created_at = now - timedelta(days=90)
    db_session.commit()

    revision_id = revision.id
    set_retention_policy(
        db_session,
        organization_id=organization.id,
        actor_user_id=owner.id,
        raw_event_days=None,
        derived_content_days=None,
        audit_event_days=None,
        private_message_days=30,
        legal_hold=True,
    )
    held = run_retention_once(
        db_session,
        organization_id=organization.id,
        at=now,
    )
    assert held is not None
    assert held.private_messages_deleted == 0
    db_session.expire_all()
    assert db_session.get(DirectMessage, message_id) is not None
    assert db_session.get(DirectMessageRevision, revision_id) is not None

    set_retention_policy(
        db_session,
        organization_id=organization.id,
        actor_user_id=owner.id,
        raw_event_days=None,
        derived_content_days=None,
        audit_event_days=None,
        private_message_days=30,
        legal_hold=False,
    )
    run = run_retention_once(
        db_session,
        organization_id=organization.id,
        at=now,
    )
    assert run is not None
    assert run.private_messages_deleted == 1
    db_session.expire_all()
    assert db_session.get(DirectMessage, message_id) is None
    assert db_session.get(DirectMessageRevision, revision_id) is None

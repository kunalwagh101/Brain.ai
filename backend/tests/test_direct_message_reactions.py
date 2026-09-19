import uuid

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.data_governance_models import SecurityAuditEvent
from app.direct_message_models import DirectMessageReaction
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
    alice = User(email="dm-react-alice@example.com", display_name="Alice")
    bob = User(email="dm-react-bob@example.com", display_name="Bob")
    owner = User(email="dm-react-owner@example.com", display_name="Owner")
    organization = Organization(name="DM Reaction Org", slug=f"dm-reaction-{uuid.uuid4().hex[:8]}")
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


def _conversation(client: TestClient, organization: Organization, actor: User, target: User):
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
            headers={"Idempotency-Key": key},
            json={"body": body},
        )
    finally:
        _clear()
    assert response.status_code == 201
    return response.json()


def _company_counts(db: Session, organization_id: uuid.UUID) -> dict[str, int]:
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
        "audit": int(
            db.scalar(
                select(func.count(SecurityAuditEvent.id)).where(
                    SecurityAuditEvent.organization_id == organization_id,
                    SecurityAuditEvent.event_type.like("direct_message.%"),
                )
            )
            or 0
        ),
    }


def test_dm_reactions_are_participant_private_idempotent_and_aggregate_only(
    client: TestClient,
    db_session: Session,
) -> None:
    organization, alice, bob, owner = _seed(db_session)
    conversation = _conversation(client, organization, alice, bob)
    message = _send(
        client,
        organization,
        conversation["id"],
        alice,
        "Private reaction target",
        "dm-reaction-target",
    )
    base = (
        f"/api/v1/organizations/{organization.id}/direct-messages/"
        f"{conversation['id']}/messages/{message['id']}"
    )
    before = _company_counts(db_session, organization.id)

    _as(alice)
    try:
        first = client.put(f"{base}/reaction", json={"reaction": "👍"})
        duplicate = client.put(f"{base}/reaction", json={"reaction": "👍"})
        alice_read = client.get(base)
    finally:
        _clear()
    assert first.status_code == 200
    assert duplicate.status_code == 200
    assert first.json() == {"reaction": "👍", "count": 1, "reacted_by_me": True}
    assert duplicate.json() == first.json()
    _as(alice)
    try:
        spaced = client.put(f"{base}/reaction", json={"reaction": " ✅ "})
    finally:
        _clear()
    assert spaced.status_code == 200
    assert spaced.json() == {"reaction": "✅", "count": 1, "reacted_by_me": True}
    assert alice_read.json()["reactions"] == [
        {"reaction": "👍", "count": 1, "reacted_by_me": True}
    ]

    row_count = db_session.scalar(
        select(func.count(DirectMessageReaction.id)).where(
            DirectMessageReaction.message_id == uuid.UUID(message["id"])
        )
    )
    assert row_count == 1

    _as(bob)
    try:
        bob_add = client.put(f"{base}/reaction", json={"reaction": "👍"})
        bob_read = client.get(base)
    finally:
        _clear()
    assert bob_add.status_code == 200
    assert bob_add.json() == {"reaction": "👍", "count": 2, "reacted_by_me": True}
    assert bob_read.json()["reactions"] == [
        {"reaction": "👍", "count": 2, "reacted_by_me": True}
    ]

    _as(owner)
    try:
        hidden = client.put(f"{base}/reaction", json={"reaction": "👍"})
    finally:
        _clear()
    assert hidden.status_code == 404

    _as(alice)
    try:
        invalid = client.put(f"{base}/reaction", json={"reaction": "🔥"})
        removed = client.request("DELETE", f"{base}/reaction", json={"reaction": "👍"})
        alice_after = client.get(base)
    finally:
        _clear()
    assert invalid.status_code == 400
    assert removed.status_code == 204
    assert alice_after.json()["reactions"] == [
        {"reaction": "👍", "count": 1, "reacted_by_me": False}
    ]
    assert _company_counts(db_session, organization.id) == before


def test_dm_reaction_old_epoch_and_retracted_message_fail_closed_and_cascade(
    client: TestClient,
    db_session: Session,
) -> None:
    organization, alice, bob, owner = _seed(db_session)
    conversation = _conversation(client, organization, alice, bob)
    old = _send(
        client,
        organization,
        conversation["id"],
        alice,
        "Old epoch private target",
        "dm-reaction-old",
    )
    old_base = (
        f"/api/v1/organizations/{organization.id}/direct-messages/"
        f"{conversation['id']}/messages/{old['id']}"
    )
    _as(alice)
    try:
        assert client.put(
            f"{old_base}/reaction",
            json={"reaction": "✅"},
        ).status_code == 200
    finally:
        _clear()

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
            f"/api/v1/organizations/{organization.id}/memberships/{membership.id}/role",
            json={"role": "guest"},
        )
        restore = client.post(
            f"/api/v1/organizations/{organization.id}/memberships/{membership.id}/role",
            json={"role": "member"},
        )
    finally:
        _clear()
    assert downgrade.status_code == 200
    assert restore.status_code == 200
    reopened = _conversation(client, organization, alice, bob)
    assert reopened["id"] == conversation["id"]

    _as(alice)
    try:
        old_epoch = client.put(f"{old_base}/reaction", json={"reaction": "👍"})
    finally:
        _clear()
    assert old_epoch.status_code == 404

    new = _send(
        client,
        organization,
        conversation["id"],
        alice,
        "New epoch private target",
        "dm-reaction-new",
    )
    new_base = (
        f"/api/v1/organizations/{organization.id}/direct-messages/"
        f"{conversation['id']}/messages/{new['id']}"
    )
    _as(bob)
    try:
        added = client.put(f"{new_base}/reaction", json={"reaction": "❤️"})
    finally:
        _clear()
    assert added.status_code == 200

    _as(alice)
    try:
        retracted = client.request(
            "DELETE",
            new_base,
            json={"expected_revision": new["revision"]},
        )
    finally:
        _clear()
    assert retracted.status_code == 200

    remaining = db_session.scalar(
        select(func.count(DirectMessageReaction.id)).where(
            DirectMessageReaction.message_id == uuid.UUID(new["id"])
        )
    )
    assert remaining == 0

    _as(bob)
    try:
        denied = client.put(f"{new_base}/reaction", json={"reaction": "❤️"})
        tombstone = client.get(new_base)
    finally:
        _clear()
    assert denied.status_code == 404
    assert tombstone.status_code == 200
    assert tombstone.json()["reactions"] == []

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.direct_message_models import DirectConversation, DirectMessage
from app.main import app
from app.models import Membership, MembershipRole, Organization, User


def _seed(db: Session):
    alice = User(email="dm-epoch-alice@example.com", display_name="Alice")
    bob = User(email="dm-epoch-bob@example.com", display_name="Bob")
    owner = User(email="dm-epoch-owner@example.com", display_name="Owner")
    organization = Organization(name="DM Epoch Org", slug="dm-epoch-org")
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
    sender: User,
    target: User,
):
    _as(sender)
    try:
        response = client.post(
            f"/api/v1/organizations/{organization.id}/direct-messages",
            json={"target_email": target.email},
        )
    finally:
        _clear()
    assert response.status_code == 201
    return response.json()


def _membership(db: Session, organization: Organization, user: User) -> Membership:
    membership = db.scalar(
        select(Membership).where(
            Membership.organization_id == organization.id,
            Membership.user_id == user.id,
        )
    )
    assert membership is not None
    return membership


def _visible_sequence(conversation: DirectConversation, user: User) -> int:
    if conversation.participant_a_user_id == user.id:
        return conversation.participant_a_visible_from_sequence
    assert conversation.participant_b_user_id == user.id
    return conversation.participant_b_visible_from_sequence


def test_reactivation_uses_monotonic_sequence_epoch_and_rejects_old_idempotency_key(
    client: TestClient,
    db_session: Session,
) -> None:
    organization, alice, bob, owner = _seed(db_session)
    created = _create_dm(client, organization, alice, bob)
    conversation_id = uuid.UUID(created["id"])

    _as(alice)
    try:
        old = client.post(
            f"/api/v1/organizations/{organization.id}/direct-messages/"
            f"{conversation_id}/messages",
            json={"body": "Old epoch message"},
            headers={"Idempotency-Key": "epoch-key"},
        )
    finally:
        _clear()
    assert old.status_code == 201

    old_message = db_session.get(DirectMessage, uuid.UUID(old.json()["id"]))
    conversation = db_session.get(DirectConversation, conversation_id)
    assert old_message is not None and conversation is not None
    assert old_message.sequence == 1
    assert conversation.next_message_sequence == 2

    membership = _membership(db_session, organization, alice)
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
    assert uuid.UUID(reopened["id"]) == conversation_id
    db_session.expire_all()
    conversation = db_session.get(DirectConversation, conversation_id)
    assert conversation is not None
    assert _visible_sequence(conversation, alice) == 2

    _as(alice)
    try:
        replay_old_key = client.post(
            f"/api/v1/organizations/{organization.id}/direct-messages/"
            f"{conversation_id}/messages",
            json={"body": "Must not replay old epoch"},
            headers={"Idempotency-Key": "epoch-key"},
        )
        fresh = client.post(
            f"/api/v1/organizations/{organization.id}/direct-messages/"
            f"{conversation_id}/messages",
            json={"body": "Fresh epoch message"},
            headers={"Idempotency-Key": "fresh-epoch-key"},
        )
        alice_history = client.get(
            f"/api/v1/organizations/{organization.id}/direct-messages/"
            f"{conversation_id}/messages"
        )
    finally:
        _clear()
    assert replay_old_key.status_code == 409
    assert fresh.status_code == 201
    assert [item["body"] for item in alice_history.json()] == ["Fresh epoch message"]

    fresh_message = db_session.get(DirectMessage, uuid.UUID(fresh.json()["id"]))
    db_session.expire_all()
    conversation = db_session.get(DirectConversation, conversation_id)
    assert fresh_message is not None and conversation is not None
    assert fresh_message.sequence == 2
    assert conversation.next_message_sequence == 3

    _as(bob)
    try:
        bob_history = client.get(
            f"/api/v1/organizations/{organization.id}/direct-messages/"
            f"{conversation_id}/messages"
        )
    finally:
        _clear()
    assert [item["body"] for item in bob_history.json()] == [
        "Old epoch message",
        "Fresh epoch message",
    ]


def test_membership_removal_and_readd_do_not_silently_restore_old_dm_history(
    client: TestClient,
    db_session: Session,
) -> None:
    organization, alice, bob, owner = _seed(db_session)
    created = _create_dm(client, organization, alice, bob)
    conversation_id = uuid.UUID(created["id"])

    _as(alice)
    try:
        old = client.post(
            f"/api/v1/organizations/{organization.id}/direct-messages/"
            f"{conversation_id}/messages",
            json={"body": "History before removal"},
            headers={"Idempotency-Key": "before-removal"},
        )
    finally:
        _clear()
    assert old.status_code == 201

    membership = _membership(db_session, organization, alice)
    _as(owner)
    try:
        removed = client.delete(
            f"/api/v1/organizations/{organization.id}/memberships/{membership.id}"
        )
        readded = client.post(
            f"/api/v1/organizations/{organization.id}/memberships",
            json={"user_email": alice.email, "role": "member"},
        )
    finally:
        _clear()
    assert removed.status_code == 204
    assert readded.status_code == 201

    _as(alice)
    try:
        before_reinitiation = client.get(
            f"/api/v1/organizations/{organization.id}/direct-messages"
        )
    finally:
        _clear()
    assert before_reinitiation.status_code == 200
    assert before_reinitiation.json() == []

    reopened = _create_dm(client, organization, alice, bob)
    assert uuid.UUID(reopened["id"]) == conversation_id

    _as(alice)
    try:
        hidden_history = client.get(
            f"/api/v1/organizations/{organization.id}/direct-messages/"
            f"{conversation_id}/messages"
        )
        fresh = client.post(
            f"/api/v1/organizations/{organization.id}/direct-messages/"
            f"{conversation_id}/messages",
            json={"body": "History after explicit restart"},
            headers={"Idempotency-Key": "after-removal-restart"},
        )
    finally:
        _clear()
    assert hidden_history.status_code == 200
    assert hidden_history.json() == []
    assert fresh.status_code == 201

    _as(bob)
    try:
        bob_history = client.get(
            f"/api/v1/organizations/{organization.id}/direct-messages/"
            f"{conversation_id}/messages"
        )
    finally:
        _clear()
    assert [item["body"] for item in bob_history.json()] == [
        "History before removal",
        "History after explicit restart",
    ]

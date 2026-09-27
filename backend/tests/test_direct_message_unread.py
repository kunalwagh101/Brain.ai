import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.direct_message_models import DirectConversation
from app.main import app
from app.models import Membership, MembershipRole, Organization, User


def _seed(db: Session):
    alice = User(email="dm-unread-alice@example.com", display_name="Alice")
    bob = User(email="dm-unread-bob@example.com", display_name="Bob")
    owner = User(email="dm-unread-owner@example.com", display_name="Owner")
    organization = Organization(name="DM Unread Org", slug="dm-unread-org")
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


def _create(client: TestClient, organization: Organization, actor: User, target: User):
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


def _list(client: TestClient, organization: Organization, actor: User):
    _as(actor)
    try:
        return client.get(
            f"/api/v1/organizations/{organization.id}/direct-messages"
        )
    finally:
        _clear()


def test_dm_unread_is_per_participant_excludes_own_and_marks_monotonically(
    client: TestClient,
    db_session: Session,
) -> None:
    organization, alice, bob, _ = _seed(db_session)
    conversation = _create(client, organization, alice, bob)
    conversation_id = conversation["id"]

    first = _send(
        client,
        organization,
        conversation_id,
        alice,
        "First private update",
        "dm-unread-first",
    )
    second = _send(
        client,
        organization,
        conversation_id,
        alice,
        "Second private update",
        "dm-unread-second",
    )

    alice_list = _list(client, organization, alice)
    bob_list = _list(client, organization, bob)
    assert alice_list.status_code == 200
    assert bob_list.status_code == 200
    assert alice_list.json()[0]["unread_count"] == 0
    assert alice_list.json()[0]["first_unread_message_id"] is None
    assert bob_list.json()[0]["unread_count"] == 2
    assert bob_list.json()[0]["first_unread_message_id"] == first["id"]
    assert bob_list.json()[0]["latest_message_id"] == second["id"]

    _as(bob)
    try:
        read_first = client.post(
            f"/api/v1/organizations/{organization.id}/direct-messages/"
            f"{conversation_id}/read",
            json={"through_message_id": first["id"]},
        )
        read_second = client.post(
            f"/api/v1/organizations/{organization.id}/direct-messages/"
            f"{conversation_id}/read",
            json={"through_message_id": second["id"]},
        )
        stale = client.post(
            f"/api/v1/organizations/{organization.id}/direct-messages/"
            f"{conversation_id}/read",
            json={"through_message_id": first["id"]},
        )
    finally:
        _clear()

    assert read_first.status_code == 200
    assert read_first.json()["unread_count"] == 1
    assert read_first.json()["first_unread_message_id"] == second["id"]
    assert read_second.json()["unread_count"] == 0
    assert read_second.json()["first_unread_message_id"] is None
    assert stale.json()["unread_count"] == 0

    stored = db_session.get(DirectConversation, uuid.UUID(conversation_id))
    assert stored is not None
    bob_cursor = (
        stored.participant_a_last_read_sequence
        if stored.participant_a_user_id == bob.id
        else stored.participant_b_last_read_sequence
    )
    assert bob_cursor == second["sequence"]


def test_exact_dm_unread_target_is_participant_only(
    client: TestClient,
    db_session: Session,
) -> None:
    organization, alice, bob, owner = _seed(db_session)
    conversation = _create(client, organization, alice, bob)
    message = _send(
        client,
        organization,
        conversation["id"],
        alice,
        "Participant-only exact target",
        "dm-exact-target",
    )
    endpoint = (
        f"/api/v1/organizations/{organization.id}/direct-messages/"
        f"{conversation['id']}/messages/{message['id']}"
    )

    _as(bob)
    try:
        visible = client.get(endpoint)
    finally:
        _clear()
    assert visible.status_code == 200
    assert visible.json()["body"] == "Participant-only exact target"

    _as(owner)
    try:
        hidden = client.get(endpoint)
    finally:
        _clear()
    assert hidden.status_code == 404


def test_dm_reactivation_resets_read_cursor_before_new_visibility_epoch(
    client: TestClient,
    db_session: Session,
) -> None:
    organization, alice, bob, owner = _seed(db_session)
    conversation = _create(client, organization, alice, bob)
    old = _send(
        client,
        organization,
        conversation["id"],
        bob,
        "Old private epoch",
        "dm-old-epoch",
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

    reopened = _create(client, organization, alice, bob)
    assert reopened["id"] == conversation["id"]
    assert reopened["unread_count"] == 0
    assert reopened["first_unread_message_id"] is None

    _as(alice)
    try:
        old_target = client.get(
            f"/api/v1/organizations/{organization.id}/direct-messages/"
            f"{conversation['id']}/messages/{old['id']}"
        )
    finally:
        _clear()
    assert old_target.status_code == 404

    new = _send(
        client,
        organization,
        conversation["id"],
        bob,
        "New private epoch",
        "dm-new-epoch",
    )
    alice_list = _list(client, organization, alice)
    assert alice_list.status_code == 200
    assert alice_list.json()[0]["unread_count"] == 1
    assert alice_list.json()[0]["first_unread_message_id"] == new["id"]

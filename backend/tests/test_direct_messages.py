import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.data_governance import run_retention_once, set_retention_policy
from app.data_governance_models import SecurityAuditEvent
from app.direct_message_models import DirectConversation, DirectMessage
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
    alice = User(email="dm-alice@example.com", display_name="Alice")
    bob = User(email="dm-bob@example.com", display_name="Bob")
    owner = User(email="dm-owner@example.com", display_name="Owner")
    admin = User(email="dm-admin@example.com", display_name="Admin")
    executive = User(email="dm-executive@example.com", display_name="Executive")
    guest = User(email="dm-guest@example.com", display_name="Guest")
    outsider = User(email="dm-outsider@example.com", display_name="Outsider")
    organization = Organization(name="DM Org", slug="dm-org")
    other_org = Organization(name="Other DM Org", slug="other-dm-org")
    db.add_all(
        [
            alice,
            bob,
            owner,
            admin,
            executive,
            guest,
            outsider,
            organization,
            other_org,
        ]
    )
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
                user_id=guest.id,
                role=MembershipRole.GUEST,
            ),
            Membership(
                organization_id=other_org.id,
                user_id=outsider.id,
                role=MembershipRole.OWNER,
            ),
        ]
    )
    db.commit()
    return organization, alice, bob, owner, admin, executive, guest, outsider


def _as(user: User):
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


def test_direct_messages_are_participant_only_and_not_projected_to_company_memory(
    client: TestClient,
    db_session: Session,
) -> None:
    organization, alice, bob, owner, admin, executive, _, _ = _seed(db_session)
    before = {
        "raw": db_session.scalar(select(func.count(RawEvent.id))) or 0,
        "canonical": db_session.scalar(select(func.count(CanonicalEvent.id))) or 0,
        "search": db_session.scalar(select(func.count(SearchDocument.id))) or 0,
    }

    created = _create_dm(client, organization, alice, bob)
    conversation_id = created["id"]
    assert created["other_email"] == bob.email
    assert created["can_send"] is True

    reverse = _create_dm(client, organization, bob, alice)
    assert reverse["id"] == conversation_id

    _as(alice)
    try:
        first = client.post(
            f"/api/v1/organizations/{organization.id}/direct-messages/"
            f"{conversation_id}/messages",
            json={"body": "Private design note"},
            headers={"Idempotency-Key": "dm-message-1"},
        )
        duplicate = client.post(
            f"/api/v1/organizations/{organization.id}/direct-messages/"
            f"{conversation_id}/messages",
            json={"body": "Private design note"},
            headers={"Idempotency-Key": "dm-message-1"},
        )
    finally:
        _clear()
    assert first.status_code == 201
    assert duplicate.status_code == 201
    assert first.json()["id"] == duplicate.json()["id"]
    assert first.json()["is_mine"] is True

    _as(bob)
    try:
        messages = client.get(
            f"/api/v1/organizations/{organization.id}/direct-messages/"
            f"{conversation_id}/messages"
        )
    finally:
        _clear()
    assert messages.status_code == 200
    assert [item["body"] for item in messages.json()] == ["Private design note"]
    assert messages.json()[0]["is_mine"] is False

    for nonparticipant in (owner, admin, executive):
        _as(nonparticipant)
        try:
            hidden = client.get(
                f"/api/v1/organizations/{organization.id}/direct-messages/"
                f"{conversation_id}/messages"
            )
            listed = client.get(
                f"/api/v1/organizations/{organization.id}/direct-messages"
            )
        finally:
            _clear()
        assert hidden.status_code == 404
        assert listed.status_code == 200
        assert listed.json() == []

    after = {
        "raw": db_session.scalar(select(func.count(RawEvent.id))) or 0,
        "canonical": db_session.scalar(select(func.count(CanonicalEvent.id))) or 0,
        "search": db_session.scalar(select(func.count(SearchDocument.id))) or 0,
    }
    assert after == before
    dm_audit = db_session.scalar(
        select(SecurityAuditEvent.id)
        .where(
            SecurityAuditEvent.organization_id == organization.id,
            SecurityAuditEvent.event_type.like("direct_message.%"),
        )
        .limit(1)
    )
    assert dm_audit is None


def test_direct_message_target_must_be_current_message_capable_member(
    client: TestClient,
    db_session: Session,
) -> None:
    organization, alice, _, _, _, _, guest, outsider = _seed(db_session)
    _as(alice)
    try:
        self_dm = client.post(
            f"/api/v1/organizations/{organization.id}/direct-messages",
            json={"target_email": alice.email},
        )
        guest_dm = client.post(
            f"/api/v1/organizations/{organization.id}/direct-messages",
            json={"target_email": guest.email},
        )
        cross_tenant = client.post(
            f"/api/v1/organizations/{organization.id}/direct-messages",
            json={"target_email": outsider.email},
        )
    finally:
        _clear()

    assert self_dm.status_code == 409
    assert guest_dm.status_code == 404
    assert cross_tenant.status_code == 404


def test_role_downgrade_revokes_old_dm_until_explicit_reinitiation(
    client: TestClient,
    db_session: Session,
) -> None:
    organization, alice, bob, owner, _, _, _, _ = _seed(db_session)
    conversation = _create_dm(client, organization, alice, bob)
    conversation_id = conversation["id"]

    _as(alice)
    try:
        old = client.post(
            f"/api/v1/organizations/{organization.id}/direct-messages/"
            f"{conversation_id}/messages",
            json={"body": "History before role downgrade"},
            headers={"Idempotency-Key": "before-downgrade"},
        )
    finally:
        _clear()
    assert old.status_code == 201

    alice_membership = _membership(db_session, organization, alice)
    _as(owner)
    try:
        downgrade = client.post(
            f"/api/v1/organizations/{organization.id}/memberships/"
            f"{alice_membership.id}/role",
            json={"role": "guest"},
        )
        restore = client.post(
            f"/api/v1/organizations/{organization.id}/memberships/"
            f"{alice_membership.id}/role",
            json={"role": "member"},
        )
    finally:
        _clear()
    assert downgrade.status_code == 200
    assert restore.status_code == 200

    _as(alice)
    try:
        after_restore = client.get(
            f"/api/v1/organizations/{organization.id}/direct-messages"
        )
        guessed_old = client.get(
            f"/api/v1/organizations/{organization.id}/direct-messages/"
            f"{conversation_id}/messages"
        )
    finally:
        _clear()
    assert after_restore.status_code == 200
    assert after_restore.json() == []
    assert guessed_old.status_code == 404

    _as(bob)
    try:
        bob_list = client.get(
            f"/api/v1/organizations/{organization.id}/direct-messages"
        )
        bob_history = client.get(
            f"/api/v1/organizations/{organization.id}/direct-messages/"
            f"{conversation_id}/messages"
        )
        blocked_send = client.post(
            f"/api/v1/organizations/{organization.id}/direct-messages/"
            f"{conversation_id}/messages",
            json={"body": "Cannot send while Alice side remains revoked"},
        )
    finally:
        _clear()
    assert bob_list.status_code == 200
    assert bob_list.json()[0]["can_send"] is False
    assert [item["body"] for item in bob_history.json()] == ["History before role downgrade"]
    assert blocked_send.status_code == 409

    reopened = _create_dm(client, organization, alice, bob)
    assert reopened["id"] == conversation_id
    assert reopened["can_send"] is True

    _as(alice)
    try:
        alice_reopened_history = client.get(
            f"/api/v1/organizations/{organization.id}/direct-messages/"
            f"{conversation_id}/messages"
        )
        new_message = client.post(
            f"/api/v1/organizations/{organization.id}/direct-messages/"
            f"{conversation_id}/messages",
            json={"body": "New epoch message"},
            headers={"Idempotency-Key": "after-reopen"},
        )
    finally:
        _clear()
    assert alice_reopened_history.status_code == 200
    assert alice_reopened_history.json() == []
    assert new_message.status_code == 201

    _as(bob)
    try:
        bob_after_reopen = client.get(
            f"/api/v1/organizations/{organization.id}/direct-messages/"
            f"{conversation_id}/messages"
        )
    finally:
        _clear()
    assert [item["body"] for item in bob_after_reopen.json()] == [
        "History before role downgrade",
        "New epoch message",
    ]


def test_role_downgrade_removes_dm_list_read_and_send_access(
    client: TestClient,
    db_session: Session,
) -> None:
    organization, alice, bob, owner, _, _, _, _ = _seed(db_session)
    conversation = _create_dm(client, organization, alice, bob)
    conversation_id = conversation["id"]
    alice_membership = _membership(db_session, organization, alice)

    _as(owner)
    try:
        downgrade = client.post(
            f"/api/v1/organizations/{organization.id}/memberships/"
            f"{alice_membership.id}/role",
            json={"role": "guest"},
        )
    finally:
        _clear()
    assert downgrade.status_code == 200

    _as(alice)
    try:
        listed = client.get(
            f"/api/v1/organizations/{organization.id}/direct-messages"
        )
        read = client.get(
            f"/api/v1/organizations/{organization.id}/direct-messages/"
            f"{conversation_id}/messages"
        )
        send = client.post(
            f"/api/v1/organizations/{organization.id}/direct-messages/"
            f"{conversation_id}/messages",
            json={"body": "Must be denied after downgrade"},
        )
    finally:
        _clear()

    assert listed.status_code == 403
    assert read.status_code == 403
    assert send.status_code == 403


def test_private_message_retention_is_explicit_and_legal_hold_safe(
    client: TestClient,
    db_session: Session,
) -> None:
    organization, alice, bob, owner, _, _, _, _ = _seed(db_session)
    conversation = _create_dm(client, organization, alice, bob)
    conversation_id = uuid.UUID(conversation["id"])

    _as(alice)
    try:
        old_response = client.post(
            f"/api/v1/organizations/{organization.id}/direct-messages/"
            f"{conversation_id}/messages",
            json={"body": "Old private message"},
            headers={"Idempotency-Key": "dm-old"},
        )
        recent_response = client.post(
            f"/api/v1/organizations/{organization.id}/direct-messages/"
            f"{conversation_id}/messages",
            json={"body": "Recent private message"},
            headers={"Idempotency-Key": "dm-recent"},
        )
    finally:
        _clear()
    assert old_response.status_code == 201
    assert recent_response.status_code == 201

    old_message_id = uuid.UUID(old_response.json()["id"])
    recent_message_id = uuid.UUID(recent_response.json()["id"])
    now = datetime.now(UTC)
    old_message = db_session.get(DirectMessage, old_message_id)
    recent_message = db_session.get(DirectMessage, recent_message_id)
    stored_conversation = db_session.get(DirectConversation, conversation_id)
    assert old_message is not None
    assert recent_message is not None
    assert stored_conversation is not None
    old_message.created_at = now - timedelta(days=90)
    recent_message.created_at = now - timedelta(days=2)
    stored_conversation.updated_at = now - timedelta(days=2)
    db_session.commit()

    set_retention_policy(
        db_session,
        organization_id=organization.id,
        actor_user_id=owner.id,
        raw_event_days=None,
        derived_content_days=None,
        audit_event_days=None,
        private_message_days=None,
        legal_hold=False,
    )
    no_policy_purge = run_retention_once(
        db_session,
        organization_id=organization.id,
        at=now,
    )
    assert no_policy_purge is not None
    assert no_policy_purge.private_messages_deleted == 0
    assert db_session.get(DirectMessage, old_message_id) is not None

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
    assert db_session.get(DirectMessage, old_message_id) is not None

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
    purged = run_retention_once(
        db_session,
        organization_id=organization.id,
        at=now,
    )
    assert purged is not None
    assert purged.private_message_days == 30
    assert purged.private_messages_deleted == 1
    db_session.expire_all()
    assert db_session.get(DirectMessage, old_message_id) is None
    assert db_session.get(DirectMessage, recent_message_id) is not None
    assert db_session.get(DirectConversation, conversation_id) is not None

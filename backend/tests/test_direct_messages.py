from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.main import app
from app.models import CanonicalEvent, Membership, MembershipRole, Organization, RawEvent, User
from app.search_models import SearchDocument


def _seed(db: Session):
    alice = User(email="dm-alice@example.com", display_name="Alice")
    bob = User(email="dm-bob@example.com", display_name="Bob")
    owner = User(email="dm-owner@example.com", display_name="Owner")
    executive = User(email="dm-executive@example.com", display_name="Executive")
    guest = User(email="dm-guest@example.com", display_name="Guest")
    outsider = User(email="dm-outsider@example.com", display_name="Outsider")
    organization = Organization(name="DM Org", slug="dm-org")
    other_org = Organization(name="Other DM Org", slug="other-dm-org")
    db.add_all([alice, bob, owner, executive, guest, outsider, organization, other_org])
    db.flush()
    db.add_all(
        [
            Membership(organization_id=organization.id, user_id=alice.id, role=MembershipRole.MEMBER),
            Membership(organization_id=organization.id, user_id=bob.id, role=MembershipRole.MEMBER),
            Membership(organization_id=organization.id, user_id=owner.id, role=MembershipRole.OWNER),
            Membership(organization_id=organization.id, user_id=executive.id, role=MembershipRole.EXECUTIVE),
            Membership(organization_id=organization.id, user_id=guest.id, role=MembershipRole.GUEST),
            Membership(organization_id=other_org.id, user_id=outsider.id, role=MembershipRole.OWNER),
        ]
    )
    db.commit()
    return organization, alice, bob, owner, executive, guest, outsider


def _as(user: User):
    app.dependency_overrides[get_current_user] = lambda: user


def _clear() -> None:
    app.dependency_overrides.pop(get_current_user, None)


def test_direct_messages_are_participant_only_and_not_projected_to_company_memory(
    client: TestClient,
    db_session: Session,
) -> None:
    organization, alice, bob, owner, executive, _, _ = _seed(db_session)
    before = {
        "raw": db_session.scalar(select(func.count(RawEvent.id))) or 0,
        "canonical": db_session.scalar(select(func.count(CanonicalEvent.id))) or 0,
        "search": db_session.scalar(select(func.count(SearchDocument.id))) or 0,
    }

    _as(alice)
    try:
        created = client.post(
            f"/api/v1/organizations/{organization.id}/direct-messages",
            json={"target_email": bob.email},
        )
    finally:
        _clear()
    assert created.status_code == 201
    conversation_id = created.json()["id"]
    assert created.json()["other_email"] == bob.email

    _as(bob)
    try:
        reverse = client.post(
            f"/api/v1/organizations/{organization.id}/direct-messages",
            json={"target_email": alice.email},
        )
    finally:
        _clear()
    assert reverse.status_code == 201
    assert reverse.json()["id"] == conversation_id

    _as(alice)
    try:
        first = client.post(
            f"/api/v1/organizations/{organization.id}/direct-messages/{conversation_id}/messages",
            json={"body": "Private design note"},
            headers={"Idempotency-Key": "dm-message-1"},
        )
        duplicate = client.post(
            f"/api/v1/organizations/{organization.id}/direct-messages/{conversation_id}/messages",
            json={"body": "Private design note"},
            headers={"Idempotency-Key": "dm-message-1"},
        )
    finally:
        _clear()
    assert first.status_code == 201
    assert duplicate.status_code == 201
    assert first.json()["id"] == duplicate.json()["id"]

    _as(bob)
    try:
        messages = client.get(
            f"/api/v1/organizations/{organization.id}/direct-messages/{conversation_id}/messages"
        )
    finally:
        _clear()
    assert messages.status_code == 200
    assert [item["body"] for item in messages.json()] == ["Private design note"]

    for nonparticipant in (owner, executive):
        _as(nonparticipant)
        try:
            hidden = client.get(
                f"/api/v1/organizations/{organization.id}/direct-messages/{conversation_id}/messages"
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


def test_direct_message_target_must_be_current_message_capable_member(
    client: TestClient,
    db_session: Session,
) -> None:
    organization, alice, _, _, _, guest, outsider = _seed(db_session)
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

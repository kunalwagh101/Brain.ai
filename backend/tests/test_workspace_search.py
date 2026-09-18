import uuid

from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.main import app
from app.models import Membership, MembershipRole, Organization, User


def _as(user: User) -> None:
    app.dependency_overrides[get_current_user] = lambda: user


def _seed(db: Session):
    organization = Organization(
        name="Workspace Search Org",
        slug=f"workspace-search-{uuid.uuid4().hex[:8]}",
    )
    owner = User(
        email=f"search-owner-{uuid.uuid4().hex[:8]}@example.com",
        display_name="Search Owner",
    )
    member = User(
        email=f"search-member-{uuid.uuid4().hex[:8]}@example.com",
        display_name="Search Member",
    )
    db.add_all([organization, owner, member])
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
                user_id=member.id,
                role=MembershipRole.MEMBER,
            ),
        ]
    )
    db.commit()
    return organization, owner, member


def test_workspace_search_finds_native_message_then_hides_it_after_revoke(
    db_session: Session,
    client,
) -> None:
    organization, owner, member = _seed(db_session)
    sentinel = f"quasar-{uuid.uuid4().hex}"

    _as(owner)
    created_channel = client.post(
        f"/api/v1/organizations/{organization.id}/native-channels",
        json={"name": "restricted-search", "visibility": "restricted"},
    )
    assert created_channel.status_code == 201
    channel_id = created_channel.json()["id"]

    invited = client.post(
        f"/api/v1/organizations/{organization.id}/native-channels/{channel_id}/members",
        json={"email": member.email, "access": "read"},
    )
    assert invited.status_code == 201

    posted = client.post(
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel_id}/messages",
        headers={"Idempotency-Key": "workspace-search-native"},
        json={"body": f"Workspace search sentinel {sentinel}"},
    )
    assert posted.status_code == 201
    message_id = posted.json()["id"]

    _as(member)
    found = client.get(
        f"/api/v1/organizations/{organization.id}/search",
        params={"q": sentinel, "mode": "keyword", "limit": 12},
    )
    assert found.status_code == 200
    matching = [
        item
        for item in found.json()["results"]
        if item["object_external_id"] == message_id
    ]
    assert len(matching) == 1
    assert matching[0]["source_provider"] == "brain_native"
    assert matching[0]["provenance"]["channel_id"] == channel_id

    _as(owner)
    revoked = client.delete(
        f"/api/v1/organizations/{organization.id}/native-channels/"
        f"{channel_id}/members/{member.id}"
    )
    assert revoked.status_code == 204

    _as(member)
    hidden = client.get(
        f"/api/v1/organizations/{organization.id}/search",
        params={"q": sentinel, "mode": "keyword", "limit": 12},
    )
    assert hidden.status_code == 200
    assert all(
        item["object_external_id"] != message_id
        for item in hidden.json()["results"]
    )

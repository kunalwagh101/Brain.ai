import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.main import app
from app.models import Membership, MembershipRole, Organization, ResourceGrant, User
from app.native_chat_models import NativeChannel
from app.native_workspace_models import NativeTeam


def _seed(db: Session, suffix: str):
    organization = Organization(
        name=f"Team Org {suffix}",
        slug=f"team-org-{suffix}-{uuid.uuid4().hex[:6]}",
    )
    owner = User(
        email=f"team-owner-{suffix}-{uuid.uuid4().hex[:6]}@example.com",
        display_name="Owner",
    )
    member = User(
        email=f"team-member-{suffix}-{uuid.uuid4().hex[:6]}@example.com",
        display_name="Member",
    )
    other = User(
        email=f"team-other-{suffix}-{uuid.uuid4().hex[:6]}@example.com",
        display_name="Other",
    )
    guest = User(
        email=f"team-guest-{suffix}-{uuid.uuid4().hex[:6]}@example.com",
        display_name="Guest",
    )
    db.add_all([organization, owner, member, other, guest])
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
            Membership(
                organization_id=organization.id,
                user_id=other.id,
                role=MembershipRole.MEMBER,
            ),
            Membership(
                organization_id=organization.id,
                user_id=guest.id,
                role=MembershipRole.GUEST,
            ),
        ]
    )
    db.commit()
    return organization, owner, member, other, guest


def _as(user: User) -> None:
    app.dependency_overrides[get_current_user] = lambda: user


def test_team_lifecycle_is_tenant_scoped_revisioned_and_manager_only(
    db_session: Session,
    client,
) -> None:
    organization, owner, member, other, guest = _seed(db_session, "lifecycle")

    _as(member)
    created = client.post(
        f"/api/v1/organizations/{organization.id}/native-teams",
        json={"name": "Backend", "description": "Backend engineering"},
    )
    assert created.status_code == 201
    team = created.json()
    assert team["revision"] == 1
    assert team["can_manage"] is True

    duplicate = client.post(
        f"/api/v1/organizations/{organization.id}/native-teams",
        json={"name": "Backend", "description": None},
    )
    assert duplicate.status_code == 409

    _as(other)
    denied = client.patch(
        f"/api/v1/organizations/{organization.id}/native-teams/{team['id']}",
        json={
            "name": "Backend Platform",
            "description": None,
            "expected_revision": team["revision"],
        },
    )
    assert denied.status_code == 404

    _as(owner)
    edited = client.patch(
        f"/api/v1/organizations/{organization.id}/native-teams/{team['id']}",
        json={
            "name": "Backend Platform",
            "description": "Core services",
            "expected_revision": team["revision"],
        },
    )
    assert edited.status_code == 200
    assert edited.json()["revision"] == 2
    assert edited.json()["slug"] == "backend-platform"

    stale = client.patch(
        f"/api/v1/organizations/{organization.id}/native-teams/{team['id']}",
        json={
            "name": "Stale",
            "description": None,
            "expected_revision": 1,
        },
    )
    assert stale.status_code == 409

    archived = client.post(
        f"/api/v1/organizations/{organization.id}/native-teams/{team['id']}/archive",
        json={"expected_revision": edited.json()["revision"]},
    )
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    assert archived.json()["archived_at"] is not None
    assert archived.json()["revision"] == 3

    active_list = client.get(
        f"/api/v1/organizations/{organization.id}/native-teams"
    )
    all_list = client.get(
        f"/api/v1/organizations/{organization.id}/native-teams",
        params={"include_archived": "true"},
    )
    assert active_list.status_code == 200
    assert all(item["id"] != team["id"] for item in active_list.json())
    assert any(item["id"] == team["id"] for item in all_list.json())

    restored = client.post(
        f"/api/v1/organizations/{organization.id}/native-teams/{team['id']}/restore",
        json={"expected_revision": archived.json()["revision"]},
    )
    assert restored.status_code == 200
    assert restored.json()["status"] == "active"
    assert restored.json()["archived_at"] is None

    _as(guest)
    forbidden = client.post(
        f"/api/v1/organizations/{organization.id}/native-teams",
        json={"name": "Guest Team"},
    )
    assert forbidden.status_code == 403


def test_team_metadata_never_changes_channel_or_resource_grants(
    db_session: Session,
    client,
) -> None:
    organization, owner, member, _, _ = _seed(db_session, "acl")

    _as(owner)
    channel = client.post(
        f"/api/v1/organizations/{organization.id}/native-channels",
        json={
            "name": "Restricted Backend",
            "description": "ACL baseline",
            "visibility": "restricted",
        },
    )
    assert channel.status_code == 201
    channel_id = uuid.UUID(channel.json()["id"])

    invitation = client.post(
        f"/api/v1/organizations/{organization.id}/native-channels/{channel_id}/members",
        json={"email": member.email, "access": "read"},
    )
    assert invitation.status_code == 200

    channel_count_before = int(
        db_session.scalar(
            select(func.count(NativeChannel.id)).where(
                NativeChannel.organization_id == organization.id
            )
        )
        or 0
    )
    grant_rows_before = set(
        db_session.execute(
            select(
                ResourceGrant.resource_type,
                ResourceGrant.resource_id,
                ResourceGrant.user_id,
                ResourceGrant.access,
            ).where(ResourceGrant.organization_id == organization.id)
        ).all()
    )

    created = client.post(
        f"/api/v1/organizations/{organization.id}/native-teams",
        json={"name": "Platform", "description": "Navigation only"},
    )
    assert created.status_code == 201
    team = created.json()
    archived = client.post(
        f"/api/v1/organizations/{organization.id}/native-teams/{team['id']}/archive",
        json={"expected_revision": team["revision"]},
    )
    assert archived.status_code == 200

    assert int(
        db_session.scalar(
            select(func.count(NativeChannel.id)).where(
                NativeChannel.organization_id == organization.id
            )
        )
        or 0
    ) == channel_count_before
    grant_rows_after = set(
        db_session.execute(
            select(
                ResourceGrant.resource_type,
                ResourceGrant.resource_id,
                ResourceGrant.user_id,
                ResourceGrant.access,
            ).where(ResourceGrant.organization_id == organization.id)
        ).all()
    )
    assert grant_rows_after == grant_rows_before
    assert db_session.scalar(
        select(func.count(NativeTeam.id)).where(
            NativeTeam.organization_id == organization.id
        )
    ) == 1


def test_team_cross_tenant_mutation_fails_closed(
    db_session: Session,
    client,
) -> None:
    first, first_owner, _, _, _ = _seed(db_session, "tenant-a")
    second, second_owner, _, _, _ = _seed(db_session, "tenant-b")

    _as(second_owner)
    created = client.post(
        f"/api/v1/organizations/{second.id}/native-teams",
        json={"name": "Second Org Team"},
    )
    assert created.status_code == 201

    _as(first_owner)
    response = client.patch(
        f"/api/v1/organizations/{first.id}/native-teams/{created.json()['id']}",
        json={
            "name": "Cross tenant",
            "description": None,
            "expected_revision": created.json()["revision"],
        },
    )
    assert response.status_code == 404

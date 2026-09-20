import uuid

import pytest

from sqlalchemy import func, select
from sqlalchemy.orm import Session

import app.native_chat as native_chat_module
import app.native_workspace as native_workspace_module
from app.auth import get_current_user
from app.main import app
from app.models import (
    Membership,
    MembershipRole,
    Organization,
    ResourceAccessLevel,
    ResourceGrant,
    User,
)
from app.native_chat_models import NativeChannel, NativeChannelMembership
from app.native_workspace_models import NativeChannelGroup, NativeTeam
from app.work_graph_models import WorkGraphNode


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

def test_channel_group_moves_preserve_acl_and_resource_grants(
    db_session: Session,
    client,
) -> None:
    organization, owner, member, other, _ = _seed(db_session, "groups")
    _as(owner)
    team = client.post(
        f"/api/v1/organizations/{organization.id}/native-teams",
        json={"name": "Engineering"},
    ).json()
    group = client.post(
        f"/api/v1/organizations/{organization.id}/native-teams/"
        f"{team['id']}/groups",
        json={"name": "Backend Services"},
    )
    assert group.status_code == 201
    group_row = group.json()

    channel = client.post(
        f"/api/v1/organizations/{organization.id}/native-channels",
        json={
            "name": "Production Backend",
            "visibility": "restricted",
            "description": "Sensitive backend channel",
        },
    )
    assert channel.status_code == 201
    channel_id = uuid.UUID(channel.json()["id"])
    invited = client.post(
        f"/api/v1/organizations/{organization.id}/native-channels/"
        f"{channel_id}/members",
        json={"email": member.email, "access": "read"},
    )
    assert invited.status_code == 200

    memberships_before = set(
        db_session.execute(
            select(
                NativeChannelMembership.user_id,
                NativeChannelMembership.access,
                NativeChannelMembership.revoked_at,
            ).where(
                NativeChannelMembership.organization_id == organization.id,
                NativeChannelMembership.channel_id == channel_id,
            )
        ).all()
    )
    grants_before = set(
        db_session.execute(
            select(
                ResourceGrant.resource_type,
                ResourceGrant.resource_id,
                ResourceGrant.user_id,
                ResourceGrant.access,
            ).where(ResourceGrant.organization_id == organization.id)
        ).all()
    )

    assigned = client.patch(
        f"/api/v1/organizations/{organization.id}/native-teams/"
        f"channel-assignment/{channel_id}",
        json={
            "team_id": team["id"],
            "channel_group_id": group_row["id"],
        },
    )
    assert assigned.status_code == 200
    assert assigned.json()["team_id"] == team["id"]
    assert assigned.json()["channel_group_id"] == group_row["id"]

    db_session.expire_all()
    stored = db_session.get(NativeChannel, channel_id)
    assert stored is not None
    assert str(stored.team_id) == team["id"]
    assert str(stored.channel_group_id) == group_row["id"]
    assert set(
        db_session.execute(
            select(
                NativeChannelMembership.user_id,
                NativeChannelMembership.access,
                NativeChannelMembership.revoked_at,
            ).where(
                NativeChannelMembership.organization_id == organization.id,
                NativeChannelMembership.channel_id == channel_id,
            )
        ).all()
    ) == memberships_before
    assert set(
        db_session.execute(
            select(
                ResourceGrant.resource_type,
                ResourceGrant.resource_id,
                ResourceGrant.user_id,
                ResourceGrant.access,
            ).where(ResourceGrant.organization_id == organization.id)
        ).all()
    ) == grants_before

    _as(member)
    denied = client.patch(
        f"/api/v1/organizations/{organization.id}/native-teams/"
        f"channel-assignment/{channel_id}",
        json={"team_id": None, "channel_group_id": None},
    )
    assert denied.status_code == 404

    _as(owner)
    archived = client.post(
        f"/api/v1/organizations/{organization.id}/native-teams/"
        f"{team['id']}/groups/{group_row['id']}/archive",
        json={"expected_revision": group_row["revision"]},
    )
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"

    groups = client.get(
        f"/api/v1/organizations/{organization.id}/native-teams/groups"
    )
    assert all(item["id"] != group_row["id"] for item in groups.json())
    visible_channels = client.get(
        f"/api/v1/organizations/{organization.id}/native-channels"
    )
    visible = next(item for item in visible_channels.json() if item["id"] == str(channel_id))
    assert visible["team_id"] == team["id"]
    assert visible["channel_group_id"] == group_row["id"]

    rejected_archived_target = client.patch(
        f"/api/v1/organizations/{organization.id}/native-teams/"
        f"channel-assignment/{channel_id}",
        json={
            "team_id": team["id"],
            "channel_group_id": group_row["id"],
        },
    )
    assert rejected_archived_target.status_code == 404

    unassigned = client.patch(
        f"/api/v1/organizations/{organization.id}/native-teams/"
        f"channel-assignment/{channel_id}",
        json={"team_id": None, "channel_group_id": None},
    )
    assert unassigned.status_code == 200
    assert unassigned.json()["team_id"] is None
    assert unassigned.json()["channel_group_id"] is None


def test_channel_group_team_scope_and_stale_revision_fail_closed(
    db_session: Session,
    client,
) -> None:
    organization, owner, member, _, _ = _seed(db_session, "group-scope")
    _as(owner)
    first_team = client.post(
        f"/api/v1/organizations/{organization.id}/native-teams",
        json={"name": "First Team"},
    ).json()
    second_team = client.post(
        f"/api/v1/organizations/{organization.id}/native-teams",
        json={"name": "Second Team"},
    ).json()
    group = client.post(
        f"/api/v1/organizations/{organization.id}/native-teams/"
        f"{first_team['id']}/groups",
        json={"name": "API"},
    )
    assert group.status_code == 201
    current = group.json()

    edited = client.patch(
        f"/api/v1/organizations/{organization.id}/native-teams/"
        f"{first_team['id']}/groups/{current['id']}",
        json={"name": "Platform API", "expected_revision": current["revision"]},
    )
    assert edited.status_code == 200
    stale = client.patch(
        f"/api/v1/organizations/{organization.id}/native-teams/"
        f"{first_team['id']}/groups/{current['id']}",
        json={"name": "Stale", "expected_revision": current["revision"]},
    )
    assert stale.status_code == 409

    wrong_team = client.patch(
        f"/api/v1/organizations/{organization.id}/native-teams/"
        f"{second_team['id']}/groups/{current['id']}",
        json={
            "name": "Cross Team",
            "expected_revision": edited.json()["revision"],
        },
    )
    assert wrong_team.status_code == 404

    _as(member)
    denied_create = client.post(
        f"/api/v1/organizations/{organization.id}/native-teams/"
        f"{first_team['id']}/groups",
        json={"name": "No Authority"},
    )
    assert denied_create.status_code == 404

def test_channel_administration_is_revisioned_read_only_when_archived_and_syncs_track(
    db_session: Session,
    client,
) -> None:
    organization, owner, member, other, _ = _seed(db_session, "channel-admin")

    _as(member)
    created = client.post(
        f"/api/v1/organizations/{organization.id}/native-channels",
        json={
            "name": "launch-room",
            "description": "Original description",
            "visibility": "organization",
        },
    )
    assert created.status_code == 201
    channel = created.json()
    assert channel["settings_revision"] == 1
    assert channel["can_manage"] is True

    _as(other)
    denied = client.patch(
        f"/api/v1/organizations/{organization.id}/native-channels/{channel['id']}/settings",
        json={
            "name": "stolen-name",
            "description": None,
            "expected_revision": 1,
        },
    )
    assert denied.status_code == 404

    _as(owner)
    edited = client.patch(
        f"/api/v1/organizations/{organization.id}/native-channels/{channel['id']}/settings",
        json={
            "name": "release-room",
            "description": "Release coordination",
            "expected_revision": 1,
        },
    )
    assert edited.status_code == 200
    edited_body = edited.json()
    assert edited_body["name"] == "release-room"
    assert edited_body["slug"] == "release-room"
    assert edited_body["settings_revision"] == 2

    stored = db_session.get(NativeChannel, uuid.UUID(channel["id"]))
    assert stored is not None
    assert stored.work_graph_node_id is not None
    track = db_session.get(WorkGraphNode, stored.work_graph_node_id)
    assert track is not None
    assert track.display_name == "release-room"
    assert track.attributes["channel_slug"] == "release-room"

    stale = client.patch(
        f"/api/v1/organizations/{organization.id}/native-channels/{channel['id']}/settings",
        json={
            "name": "stale-name",
            "description": None,
            "expected_revision": 1,
        },
    )
    assert stale.status_code == 409

    visibility_change = client.patch(
        f"/api/v1/organizations/{organization.id}/native-channels/{channel['id']}/settings",
        json={
            "name": "release-room",
            "description": "No visibility conversion",
            "expected_revision": edited_body["settings_revision"],
            "visibility": "restricted",
        },
    )
    assert visibility_change.status_code == 422

    archived = client.post(
        f"/api/v1/organizations/{organization.id}/native-channels/{channel['id']}/archive",
        json={"expected_revision": edited_body["settings_revision"]},
    )
    assert archived.status_code == 200
    archived_body = archived.json()
    assert archived_body["status"] == "archived"
    assert archived_body["can_post"] is False
    assert archived_body["archived_at"] is not None

    active_channels = client.get(
        f"/api/v1/organizations/{organization.id}/native-channels"
    )
    archived_channels = client.get(
        f"/api/v1/organizations/{organization.id}/native-channels",
        params={"include_archived": "true"},
    )
    assert all(item["id"] != channel["id"] for item in active_channels.json())
    assert any(item["id"] == channel["id"] for item in archived_channels.json())

    still_readable = client.get(
        f"/api/v1/organizations/{organization.id}/native-channels/{channel['id']}"
    )
    assert still_readable.status_code == 200
    assert still_readable.json()["status"] == "archived"

    blocked_post = client.post(
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel['id']}/messages",
        headers={"Idempotency-Key": "archived-channel-write"},
        json={"body": "must not post while archived"},
    )
    assert blocked_post.status_code == 404

    restored = client.post(
        f"/api/v1/organizations/{organization.id}/native-channels/{channel['id']}/restore",
        json={"expected_revision": archived_body["settings_revision"]},
    )
    assert restored.status_code == 200
    assert restored.json()["status"] == "active"
    assert restored.json()["can_post"] is True

    allowed_post = client.post(
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel['id']}/messages",
        headers={"Idempotency-Key": "restored-channel-write"},
        json={"body": "posting works after restore"},
    )
    assert allowed_post.status_code == 201


def test_restricted_member_access_updates_membership_and_resource_grants_consistently(
    db_session: Session,
    client,
) -> None:
    organization, owner, member, _, _ = _seed(db_session, "member-access")
    _as(owner)
    created = client.post(
        f"/api/v1/organizations/{organization.id}/native-channels",
        json={
            "name": "restricted-admin",
            "description": "permission test",
            "visibility": "restricted",
        },
    )
    assert created.status_code == 201
    channel_id = uuid.UUID(created.json()["id"])

    invited = client.post(
        f"/api/v1/organizations/{organization.id}/native-channels/{channel_id}/members",
        json={"email": member.email, "access": "read"},
    )
    assert invited.status_code == 200
    assert invited.json()["access"] == "read"

    membership = db_session.scalar(
        select(NativeChannelMembership).where(
            NativeChannelMembership.organization_id == organization.id,
            NativeChannelMembership.channel_id == channel_id,
            NativeChannelMembership.user_id == member.id,
            NativeChannelMembership.revoked_at.is_(None),
        )
    )
    assert membership is not None
    assert membership.access == ResourceAccessLevel.READ

    channel = db_session.get(NativeChannel, channel_id)
    assert channel is not None
    assert channel.work_graph_node_id is not None

    def track_grant_access():
        row = db_session.scalar(
            select(ResourceGrant).where(
                ResourceGrant.organization_id == organization.id,
                ResourceGrant.resource_type == "work_graph.node",
                ResourceGrant.resource_id == str(channel.work_graph_node_id),
                ResourceGrant.user_id == member.id,
            )
        )
        return None if row is None else row.access

    assert track_grant_access() == ResourceAccessLevel.READ

    promoted = client.put(
        f"/api/v1/organizations/{organization.id}/native-channels/{channel_id}/members/{member.id}",
        json={"access": "write"},
    )
    assert promoted.status_code == 200
    assert promoted.json()["access"] == "write"
    db_session.expire_all()
    membership = db_session.scalar(
        select(NativeChannelMembership).where(
            NativeChannelMembership.organization_id == organization.id,
            NativeChannelMembership.channel_id == channel_id,
            NativeChannelMembership.user_id == member.id,
            NativeChannelMembership.revoked_at.is_(None),
        )
    )
    assert membership is not None
    assert membership.access == ResourceAccessLevel.WRITE
    assert track_grant_access() == ResourceAccessLevel.WRITE

    demoted = client.put(
        f"/api/v1/organizations/{organization.id}/native-channels/{channel_id}/members/{member.id}",
        json={"access": "read"},
    )
    assert demoted.status_code == 200
    db_session.expire_all()
    membership = db_session.scalar(
        select(NativeChannelMembership).where(
            NativeChannelMembership.organization_id == organization.id,
            NativeChannelMembership.channel_id == channel_id,
            NativeChannelMembership.user_id == member.id,
            NativeChannelMembership.revoked_at.is_(None),
        )
    )
    assert membership is not None
    assert membership.access == ResourceAccessLevel.READ
    assert track_grant_access() == ResourceAccessLevel.READ


def test_team_creation_rolls_back_when_audit_persistence_fails(
    db_session: Session,
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    organization, _, member, _, _ = _seed(db_session, "team-audit-rollback")
    _as(member)

    def fail_audit(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(native_workspace_module, "append_audit_event", fail_audit)

    with pytest.raises(RuntimeError, match="audit unavailable"):
        client.post(
            f"/api/v1/organizations/{organization.id}/native-teams",
            json={"name": "Must Roll Back", "description": "No orphan mutation"},
        )

    assert db_session.scalar(
        select(func.count(NativeTeam.id)).where(
            NativeTeam.organization_id == organization.id,
            NativeTeam.slug == "must-roll-back",
        )
    ) == 0


def test_channel_settings_and_member_access_roll_back_when_audit_fails(
    db_session: Session,
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    organization, owner, member, _, _ = _seed(db_session, "channel-audit-rollback")
    _as(owner)
    created = client.post(
        f"/api/v1/organizations/{organization.id}/native-channels",
        json={
            "name": "audit-safe-channel",
            "description": "before",
            "visibility": "restricted",
        },
    )
    assert created.status_code == 201
    channel_id = uuid.UUID(created.json()["id"])

    invited = client.post(
        f"/api/v1/organizations/{organization.id}/native-channels/{channel_id}/members",
        json={"email": member.email, "access": "read"},
    )
    assert invited.status_code == 200

    def fail_audit(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(native_chat_module, "append_audit_event", fail_audit)

    with pytest.raises(RuntimeError, match="audit unavailable"):
        client.patch(
            f"/api/v1/organizations/{organization.id}/native-channels/{channel_id}/settings",
            json={
                "name": "must-not-stick",
                "description": "after",
                "expected_revision": created.json()["settings_revision"],
            },
        )

    db_session.expire_all()
    channel = db_session.get(NativeChannel, channel_id)
    assert channel is not None
    assert channel.name == "audit-safe-channel"
    assert channel.description == "before"
    assert channel.settings_revision == created.json()["settings_revision"]

    with pytest.raises(RuntimeError, match="audit unavailable"):
        client.put(
            f"/api/v1/organizations/{organization.id}/native-channels/"
            f"{channel_id}/members/{member.id}",
            json={"access": "write"},
        )

    db_session.expire_all()
    membership = db_session.scalar(
        select(NativeChannelMembership).where(
            NativeChannelMembership.organization_id == organization.id,
            NativeChannelMembership.channel_id == channel_id,
            NativeChannelMembership.user_id == member.id,
            NativeChannelMembership.revoked_at.is_(None),
        )
    )
    assert membership is not None
    assert membership.access == ResourceAccessLevel.READ

    channel = db_session.get(NativeChannel, channel_id)
    assert channel is not None
    assert channel.work_graph_node_id is not None
    grant = db_session.scalar(
        select(ResourceGrant).where(
            ResourceGrant.organization_id == organization.id,
            ResourceGrant.resource_type == "work_graph.node",
            ResourceGrant.resource_id == str(channel.work_graph_node_id),
            ResourceGrant.user_id == member.id,
        )
    )
    assert grant is not None
    assert grant.access == ResourceAccessLevel.READ

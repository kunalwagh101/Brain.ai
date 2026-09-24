from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

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
from app.native_chat_models import (
    NativeChannel,
    NativeChannelMembership,
    NativeChannelStatus,
    NativeChannelVisibility,
)


def _seed(db: Session):
    owner = User(email="membership-owner@example.com")
    owner_two = User(email="membership-owner-two@example.com")
    admin = User(email="membership-admin@example.com")
    member = User(email="membership-member@example.com")
    organization = Organization(name="Membership Governance", slug="membership-governance")
    db.add_all([owner, owner_two, admin, member, organization])
    db.flush()
    memberships = {
        "owner": Membership(
            organization_id=organization.id,
            user_id=owner.id,
            role=MembershipRole.OWNER,
        ),
        "owner_two": Membership(
            organization_id=organization.id,
            user_id=owner_two.id,
            role=MembershipRole.OWNER,
        ),
        "admin": Membership(
            organization_id=organization.id,
            user_id=admin.id,
            role=MembershipRole.ADMIN,
        ),
        "member": Membership(
            organization_id=organization.id,
            user_id=member.id,
            role=MembershipRole.MEMBER,
        ),
    }
    db.add_all(list(memberships.values()))
    db.commit()
    return organization, owner, owner_two, admin, member, memberships


def _auth(user: User) -> None:
    app.dependency_overrides[get_current_user] = lambda: user


def _clear() -> None:
    app.dependency_overrides.pop(get_current_user, None)


def test_admin_can_manage_regular_member_but_not_owner_or_admin(
    client: TestClient,
    db_session: Session,
) -> None:
    organization, owner, _, admin, _, memberships = _seed(db_session)
    _auth(admin)
    try:
        promote_regular = client.post(
            f"/api/v1/organizations/{organization.id}/memberships/{memberships['member'].id}/role",
            json={"role": "manager"},
        )
        mutate_owner = client.post(
            f"/api/v1/organizations/{organization.id}/memberships/{memberships['owner'].id}/role",
            json={"role": "member"},
        )
        assign_admin = client.post(
            f"/api/v1/organizations/{organization.id}/memberships/{memberships['member'].id}/role",
            json={"role": "admin"},
        )
    finally:
        _clear()

    assert promote_regular.status_code == 200
    assert promote_regular.json()["role"] == "manager"
    assert mutate_owner.status_code == 403
    assert assign_admin.status_code == 403
    assert owner.id is not None


def test_last_owner_cannot_be_demoted_or_removed(
    client: TestClient,
    db_session: Session,
) -> None:
    organization, owner, _, _, _, memberships = _seed(db_session)
    db_session.delete(memberships["owner_two"])
    db_session.commit()
    _auth(owner)
    try:
        demote = client.post(
            f"/api/v1/organizations/{organization.id}/memberships/{memberships['owner'].id}/role",
            json={"role": "admin"},
        )
        remove = client.delete(
            f"/api/v1/organizations/{organization.id}/memberships/{memberships['owner'].id}"
        )
    finally:
        _clear()

    assert demote.status_code == 409
    assert remove.status_code == 409
    persisted = db_session.scalar(
        select(Membership).where(Membership.id == memberships["owner"].id)
    )
    assert persisted is not None
    assert persisted.role == MembershipRole.OWNER


def test_membership_removal_clears_dormant_resource_and_channel_access(
    client: TestClient,
    db_session: Session,
) -> None:
    organization, owner, _, _, member, memberships = _seed(db_session)
    channel = NativeChannel(
        organization_id=organization.id,
        name="restricted-admin-test",
        slug="restricted-admin-test",
        description=None,
        visibility=NativeChannelVisibility.RESTRICTED,
        status=NativeChannelStatus.ACTIVE,
        created_by_user_id=owner.id,
    )
    db_session.add(channel)
    db_session.flush()
    channel_membership = NativeChannelMembership(
        organization_id=organization.id,
        channel_id=channel.id,
        user_id=member.id,
        access=ResourceAccessLevel.WRITE,
        granted_by_user_id=owner.id,
    )
    grant = ResourceGrant(
        organization_id=organization.id,
        resource_type="work_graph.node",
        resource_id="test-node",
        user_id=member.id,
        access=ResourceAccessLevel.READ,
        created_by_user_id=owner.id,
    )
    db_session.add_all([channel_membership, grant])
    db_session.commit()

    _auth(owner)
    try:
        response = client.delete(
            f"/api/v1/organizations/{organization.id}/memberships/{memberships['member'].id}"
        )
    finally:
        _clear()

    assert response.status_code == 204
    assert db_session.scalar(
        select(Membership.id).where(Membership.id == memberships["member"].id)
    ) is None
    assert db_session.scalar(
        select(ResourceGrant.id).where(
            ResourceGrant.organization_id == organization.id,
            ResourceGrant.user_id == member.id,
        )
    ) is None
    revoked_channel_membership = db_session.scalar(
        select(NativeChannelMembership).where(
            NativeChannelMembership.id == channel_membership.id
        )
    )
    assert revoked_channel_membership is not None
    assert revoked_channel_membership.revoked_at is not None

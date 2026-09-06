import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.main import app
from app.models import Membership, MembershipRole, Organization, User


def _use_user(user: User) -> None:
    app.dependency_overrides[get_current_user] = lambda: user


def test_authenticated_user_creates_organization_as_owner(
    client: TestClient, db_session: Session
) -> None:
    user = User(email="owner@example.com")
    db_session.add(user)
    db_session.commit()
    _use_user(user)

    response = client.post("/api/v1/organizations", json={"name": "Acme", "slug": "acme"})

    assert response.status_code == 201
    organization_id = uuid.UUID(response.json()["id"])
    membership = db_session.query(Membership).filter_by(organization_id=organization_id).one()
    assert membership.user_id == user.id
    assert membership.role == MembershipRole.OWNER


def test_owner_can_add_existing_user_membership(client: TestClient, db_session: Session) -> None:
    owner = User(email="owner@example.com")
    member = User(email="member@example.com")
    organization = Organization(name="Acme", slug="acme")
    db_session.add_all([owner, member, organization])
    db_session.flush()
    db_session.add(
        Membership(
            organization_id=organization.id,
            user_id=owner.id,
            role=MembershipRole.OWNER,
        )
    )
    db_session.commit()
    _use_user(owner)

    response = client.post(
        f"/api/v1/organizations/{organization.id}/memberships",
        json={"user_email": "member@example.com", "role": "member"},
    )

    assert response.status_code == 201
    assert response.json()["user_id"] == str(member.id)
    assert response.json()["role"] == "member"


def test_admin_can_add_normal_member(client: TestClient, db_session: Session) -> None:
    admin = User(email="admin@example.com")
    target = User(email="target@example.com")
    organization = Organization(name="Acme", slug="acme")
    db_session.add_all([admin, target, organization])
    db_session.flush()
    db_session.add(
        Membership(
            organization_id=organization.id,
            user_id=admin.id,
            role=MembershipRole.ADMIN,
        )
    )
    db_session.commit()
    _use_user(admin)

    response = client.post(
        f"/api/v1/organizations/{organization.id}/memberships",
        json={"user_email": target.email, "role": "member"},
    )

    assert response.status_code == 201


def test_admin_cannot_assign_admin_or_owner(client: TestClient, db_session: Session) -> None:
    admin = User(email="admin@example.com")
    target = User(email="target@example.com")
    organization = Organization(name="Acme", slug="acme")
    db_session.add_all([admin, target, organization])
    db_session.flush()
    db_session.add(
        Membership(
            organization_id=organization.id,
            user_id=admin.id,
            role=MembershipRole.ADMIN,
        )
    )
    db_session.commit()
    _use_user(admin)

    response = client.post(
        f"/api/v1/organizations/{organization.id}/memberships",
        json={"user_email": target.email, "role": "admin"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Only owners can assign owner or admin roles"}


def test_cross_tenant_organization_read_returns_not_found(
    client: TestClient, db_session: Session
) -> None:
    outsider = User(email="outsider@example.com")
    organization = Organization(name="Secret", slug="secret")
    db_session.add_all([outsider, organization])
    db_session.commit()
    _use_user(outsider)

    response = client.get(f"/api/v1/organizations/{organization.id}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Organization not found"}


def test_member_cannot_add_membership(client: TestClient, db_session: Session) -> None:
    member = User(email="member@example.com")
    target = User(email="target@example.com")
    organization = Organization(name="Acme", slug="acme")
    db_session.add_all([member, target, organization])
    db_session.flush()
    db_session.add(
        Membership(
            organization_id=organization.id,
            user_id=member.id,
            role=MembershipRole.MEMBER,
        )
    )
    db_session.commit()
    _use_user(member)

    response = client.post(
        f"/api/v1/organizations/{organization.id}/memberships",
        json={"user_email": "target@example.com", "role": "member"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Permission denied"}


def test_guest_cannot_list_memberships(client: TestClient, db_session: Session) -> None:
    guest = User(email="guest@example.com")
    organization = Organization(name="Acme", slug="acme")
    db_session.add_all([guest, organization])
    db_session.flush()
    db_session.add(
        Membership(
            organization_id=organization.id,
            user_id=guest.id,
            role=MembershipRole.GUEST,
        )
    )
    db_session.commit()
    _use_user(guest)

    response = client.get(f"/api/v1/organizations/{organization.id}/memberships")

    assert response.status_code == 403


def test_admin_can_create_list_and_delete_resource_grant(
    client: TestClient, db_session: Session
) -> None:
    admin = User(email="admin-acl@example.com")
    member = User(email="member-acl@example.com")
    organization = Organization(name="ACL Org", slug="acl-org")
    db_session.add_all([admin, member, organization])
    db_session.flush()
    db_session.add_all(
        [
            Membership(
                organization_id=organization.id,
                user_id=admin.id,
                role=MembershipRole.ADMIN,
            ),
            Membership(
                organization_id=organization.id,
                user_id=member.id,
                role=MembershipRole.MEMBER,
            ),
        ]
    )
    db_session.commit()
    _use_user(admin)

    created = client.post(
        f"/api/v1/organizations/{organization.id}/resource-grants",
        json={
            "resource_type": "slack.channel",
            "resource_id": "C-private",
            "user_id": str(member.id),
            "access": "read",
        },
    )
    assert created.status_code == 201
    grant_id = created.json()["id"]

    listed = client.get(
        f"/api/v1/organizations/{organization.id}/resource-grants",
        params={"resource_type": "slack.channel", "resource_id": "C-private"},
    )
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [grant_id]

    deleted = client.delete(
        f"/api/v1/organizations/{organization.id}/resource-grants/{grant_id}"
    )
    assert deleted.status_code == 204


def test_member_cannot_manage_resource_acl(client: TestClient, db_session: Session) -> None:
    member = User(email="acl-member@example.com")
    target = User(email="acl-target@example.com")
    organization = Organization(name="ACL Org", slug="acl-member-org")
    db_session.add_all([member, target, organization])
    db_session.flush()
    db_session.add_all(
        [
            Membership(
                organization_id=organization.id,
                user_id=member.id,
                role=MembershipRole.MEMBER,
            ),
            Membership(
                organization_id=organization.id,
                user_id=target.id,
                role=MembershipRole.MEMBER,
            ),
        ]
    )
    db_session.commit()
    _use_user(member)

    response = client.post(
        f"/api/v1/organizations/{organization.id}/resource-grants",
        json={
            "resource_type": "project",
            "resource_id": "p1",
            "user_id": str(target.id),
            "access": "read",
        },
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Permission denied"}


def test_acl_target_must_be_same_organization(client: TestClient, db_session: Session) -> None:
    owner = User(email="acl-owner@example.com")
    outsider = User(email="acl-outsider@example.com")
    organization = Organization(name="ACL Org", slug="acl-target-org")
    db_session.add_all([owner, outsider, organization])
    db_session.flush()
    db_session.add(
        Membership(
            organization_id=organization.id,
            user_id=owner.id,
            role=MembershipRole.OWNER,
        )
    )
    db_session.commit()
    _use_user(owner)

    response = client.post(
        f"/api/v1/organizations/{organization.id}/resource-grants",
        json={
            "resource_type": "document",
            "resource_id": "doc-1",
            "user_id": str(outsider.id),
            "access": "read",
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Target member not found"}


@pytest.mark.parametrize(
    ("role", "can_read_memberships", "can_manage_memberships"),
    [
        (MembershipRole.OWNER, True, True),
        (MembershipRole.ADMIN, True, True),
        (MembershipRole.EXECUTIVE, True, False),
        (MembershipRole.MANAGER, True, False),
        (MembershipRole.MEMBER, True, False),
        (MembershipRole.GUEST, False, False),
    ],
)
def test_every_role_is_enforced_at_protected_membership_routes(
    client: TestClient,
    db_session: Session,
    role: MembershipRole,
    can_read_memberships: bool,
    can_manage_memberships: bool,
) -> None:
    actor = User(email=f"matrix-{role.value}@example.com")
    target = User(email=f"matrix-target-{role.value}@example.com")
    organization = Organization(name="Matrix Org", slug=f"matrix-{role.value}")
    db_session.add_all([actor, target, organization])
    db_session.flush()
    db_session.add(
        Membership(
            organization_id=organization.id,
            user_id=actor.id,
            role=role,
        )
    )
    db_session.commit()
    _use_user(actor)

    read_response = client.get(f"/api/v1/organizations/{organization.id}/memberships")
    assert read_response.status_code == (200 if can_read_memberships else 403)

    manage_response = client.post(
        f"/api/v1/organizations/{organization.id}/memberships",
        json={"user_email": target.email, "role": "member"},
    )
    assert manage_response.status_code == (201 if can_manage_memberships else 403)

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
    organization_id = response.json()["id"]
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


def test_non_owner_cannot_add_membership(client: TestClient, db_session: Session) -> None:
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
    assert response.json() == {"detail": "Owner role required"}

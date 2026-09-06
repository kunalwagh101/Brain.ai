import logging

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import (
    Membership,
    MembershipRole,
    Organization,
    ResourceAccessLevel,
    ResourceGrant,
    User,
)
from app.permissions import (
    Permission,
    ROLE_PERMISSIONS,
    authorize_resource,
    require_resource_permission,
    role_has_permission,
)


def _seed_member(db: Session, role: MembershipRole = MembershipRole.MEMBER):
    user = User(email=f"{role.value}@example.com")
    organization = Organization(name="Acme", slug=f"acme-{role.value}")
    db.add_all([user, organization])
    db.flush()
    db.add(Membership(organization_id=organization.id, user_id=user.id, role=role))
    db.commit()
    return user, organization


def test_role_permission_matrix_covers_every_role() -> None:
    assert set(ROLE_PERMISSIONS) == set(MembershipRole)
    assert role_has_permission(MembershipRole.OWNER, Permission.RESOURCE_ACL_MANAGE)
    assert role_has_permission(MembershipRole.ADMIN, Permission.MEMBERSHIP_MANAGE)
    assert role_has_permission(MembershipRole.EXECUTIVE, Permission.AUDIT_READ)
    assert role_has_permission(MembershipRole.MANAGER, Permission.RESOURCE_WRITE)
    assert role_has_permission(MembershipRole.MEMBER, Permission.AI_USE)
    assert not role_has_permission(MembershipRole.GUEST, Permission.MEMBERSHIP_READ)
    assert not role_has_permission(MembershipRole.GUEST, Permission.RESOURCE_WRITE)


def test_restricted_resource_requires_explicit_grant(db_session: Session) -> None:
    user, organization = _seed_member(db_session)

    with pytest.raises(HTTPException) as denied:
        authorize_resource(
            db=db_session,
            organization_id=organization.id,
            user=user,
            permission=Permission.RESOURCE_READ,
            resource_type="slack.channel",
            resource_id="C123",
        )
    assert denied.value.status_code == 404

    db_session.add(
        ResourceGrant(
            organization_id=organization.id,
            resource_type="slack.channel",
            resource_id="C123",
            user_id=user.id,
            access=ResourceAccessLevel.READ,
            created_by_user_id=user.id,
        )
    )
    db_session.commit()

    context = authorize_resource(
        db=db_session,
        organization_id=organization.id,
        user=user,
        permission=Permission.RESOURCE_READ,
        resource_type="slack.channel",
        resource_id="C123",
    )
    assert context.user_id == user.id


def test_write_grant_implies_read_but_read_grant_does_not_imply_write(db_session: Session) -> None:
    user, organization = _seed_member(db_session, MembershipRole.MANAGER)
    db_session.add(
        ResourceGrant(
            organization_id=organization.id,
            resource_type="project",
            resource_id="p1",
            user_id=user.id,
            access=ResourceAccessLevel.READ,
            created_by_user_id=user.id,
        )
    )
    db_session.commit()

    with pytest.raises(HTTPException) as denied:
        authorize_resource(
            db=db_session,
            organization_id=organization.id,
            user=user,
            permission=Permission.RESOURCE_WRITE,
            resource_type="project",
            resource_id="p1",
        )
    assert denied.value.status_code == 404

    grant = db_session.query(ResourceGrant).one()
    grant.access = ResourceAccessLevel.WRITE
    db_session.commit()

    authorize_resource(
        db=db_session,
        organization_id=organization.id,
        user=user,
        permission=Permission.RESOURCE_READ,
        resource_type="project",
        resource_id="p1",
    )


def test_guest_cannot_write_even_with_write_grant(db_session: Session) -> None:
    user, organization = _seed_member(db_session, MembershipRole.GUEST)
    db_session.add(
        ResourceGrant(
            organization_id=organization.id,
            resource_type="project",
            resource_id="p1",
            user_id=user.id,
            access=ResourceAccessLevel.WRITE,
            created_by_user_id=user.id,
        )
    )
    db_session.commit()

    with pytest.raises(HTTPException) as denied:
        authorize_resource(
            db=db_session,
            organization_id=organization.id,
            user=user,
            permission=Permission.RESOURCE_WRITE,
            resource_type="project",
            resource_id="p1",
        )
    assert denied.value.status_code == 403


def test_inactive_user_is_denied(db_session: Session) -> None:
    user, organization = _seed_member(db_session)
    user.status = "suspended"
    db_session.commit()

    with pytest.raises(HTTPException) as denied:
        authorize_resource(
            db=db_session,
            organization_id=organization.id,
            user=user,
            permission=Permission.RESOURCE_READ,
            resource_type="project",
            resource_id="p1",
            restricted=False,
        )
    assert denied.value.status_code == 403


def test_denial_emits_security_audit_event(db_session: Session, caplog) -> None:
    user, organization = _seed_member(db_session, MembershipRole.GUEST)

    with caplog.at_level(logging.WARNING, logger="brain.security"):
        with pytest.raises(HTTPException):
            authorize_resource(
                db=db_session,
                organization_id=organization.id,
                user=user,
                permission=Permission.RESOURCE_WRITE,
                resource_type="project",
                resource_id="p1",
            )

    assert any('"event":"authorization.decision"' in record.message for record in caplog.records)
    assert any('"reason":"role_denied"' in record.message for record in caplog.records)


def test_resource_dependency_denies_before_endpoint_body(db_session: Session) -> None:
    user, organization = _seed_member(db_session)
    called = {"value": False}
    probe = FastAPI()

    probe.dependency_overrides[get_current_user] = lambda: user
    probe.dependency_overrides[get_db] = lambda: db_session

    @probe.get(
        "/organizations/{organization_id}/resources/{resource_type}/{resource_id}",
        dependencies=[Depends(require_resource_permission(Permission.RESOURCE_READ))],
    )
    def guarded_endpoint(
        organization_id: str,
        resource_type: str,
        resource_id: str,
    ) -> dict[str, bool]:
        called["value"] = True
        return {"called": True}

    with TestClient(probe) as client:
        response = client.get(
            f"/organizations/{organization.id}/resources/slack.channel/C-private"
        )

    assert response.status_code == 404
    assert called["value"] is False

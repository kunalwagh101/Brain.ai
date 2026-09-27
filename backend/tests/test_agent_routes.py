import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent_models import AgentDefinition
from app.auth import get_current_user
from app.main import app
from app.models import Membership, MembershipRole, Organization, User


def _seed_user(db: Session, role: MembershipRole, suffix: str):
    user = User(email=f"agent-route-{role.value}-{suffix}@example.com")
    organization = Organization(
        name=f"Agent Route {suffix}",
        slug=f"agent-route-{suffix}",
    )
    db.add_all([user, organization])
    db.flush()
    db.add(
        Membership(
            organization_id=organization.id,
            user_id=user.id,
            role=role,
        )
    )
    db.commit()
    return user, organization


def test_member_cannot_create_agent_definition_before_service_execution(
    client: TestClient,
    db_session: Session,
) -> None:
    member, organization = _seed_user(db_session, MembershipRole.MEMBER, "manage")
    app.dependency_overrides[get_current_user] = lambda: member
    try:
        response = client.post(
            f"/api/v1/organizations/{organization.id}/agents/definitions",
            json={
                "name": "Forbidden agent",
                "provider_configuration_id": str(uuid.uuid4()),
                "model_configuration_id": str(uuid.uuid4()),
                "max_steps": 4,
                "tool_policies": [],
            },
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 403
    assert db_session.scalar(
        select(AgentDefinition.id).where(
            AgentDefinition.organization_id == organization.id
        )
    ) is None


def test_guest_cannot_start_agent_run(
    client: TestClient,
    db_session: Session,
) -> None:
    guest, organization = _seed_user(db_session, MembershipRole.GUEST, "run")
    app.dependency_overrides[get_current_user] = lambda: guest
    try:
        response = client.post(
            f"/api/v1/organizations/{organization.id}/agents/definitions/{uuid.uuid4()}/runs",
            json={"objective": "This must not start"},
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 403

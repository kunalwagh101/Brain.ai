import hashlib
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.agent_models import AgentDefinition, AgentRun, AgentRunStatus
from app.auth import get_current_user
from app.main import app
from app.models import Membership, MembershipRole, Organization, User
from app.secrets import get_secret_store


class ProbeSecretStore:
    def __init__(self) -> None:
        self.load_calls = 0

    def load_connection_secret(self, reference: str) -> dict[str, str]:
        del reference
        self.load_calls += 1
        return {"api_key": "must-not-be-loaded"}


def test_disabled_agent_blocks_advance_before_provider_access(
    client: TestClient,
    db_session: Session,
) -> None:
    member = User(email="agent-disabled-member@example.com")
    owner = User(email="agent-disabled-owner@example.com")
    organization = Organization(name="Disabled Agent Org", slug="disabled-agent-org")
    db_session.add_all([member, owner, organization])
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
                user_id=owner.id,
                role=MembershipRole.OWNER,
            ),
        ]
    )
    definition = AgentDefinition(
        organization_id=organization.id,
        name="Disabled agent",
        description=None,
        provider_configuration_id=uuid.uuid4(),
        model_configuration_id=uuid.uuid4(),
        enabled=False,
        max_steps=4,
        created_by_user_id=owner.id,
    )
    db_session.add(definition)
    db_session.flush()
    objective = "Do not continue this disabled run"
    run = AgentRun(
        organization_id=organization.id,
        agent_definition_id=definition.id,
        requested_by_user_id=member.id,
        status=AgentRunStatus.READY,
        objective_sha256=hashlib.sha256(objective.encode()).hexdigest(),
        objective_char_count=len(objective),
        step_count=0,
    )
    db_session.add(run)
    db_session.commit()

    store = ProbeSecretStore()
    app.dependency_overrides[get_current_user] = lambda: member
    app.dependency_overrides[get_secret_store] = lambda: store
    try:
        response = client.post(
            f"/api/v1/organizations/{organization.id}/agents/runs/{run.id}/advance",
            json={"objective": objective},
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_secret_store, None)

    assert response.status_code == 409
    assert response.json()["detail"] == "Agent definition is disabled"
    assert store.load_calls == 0

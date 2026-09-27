import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent_models import (
    AgentDefinition,
    AgentRun,
    AgentStep,
    AgentStepStatus,
    AgentToolPolicy,
    AgentToolPolicyMode,
)
from app.ai_gateway_models import (
    AIModelConfiguration,
    AIProviderAdapterKind,
    AIProviderConfiguration,
    AIProviderStatus,
)
from app.auth import get_current_user
from app.main import app
from app.models import Membership, MembershipRole, Organization, ResourceAccessLevel, User
from app.native_chat_models import (
    NativeChannel,
    NativeChannelMembership,
    NativeChannelStatus,
    NativeChannelVisibility,
)
from app.work_graph_models import WorkGraphNode, WorkGraphNodeType


def _seed(db: Session, suffix: str):
    owner = User(email=f"workspace-owner-{suffix}@example.com")
    member = User(email=f"workspace-member-{suffix}@example.com")
    other = User(email=f"workspace-other-{suffix}@example.com")
    organization = Organization(
        name=f"Workspace agents {suffix}",
        slug=f"workspace-agents-{suffix}",
    )
    db.add_all([owner, member, other, organization])
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
        ]
    )
    provider = AIProviderConfiguration(
        organization_id=organization.id,
        provider_key=f"workspace-provider-{suffix}",
        display_name="Workspace Provider",
        adapter_kind=AIProviderAdapterKind.OPENAI_CHAT_COMPLETIONS,
        api_url="https://ai.example.com/v1/chat/completions",
        secret_ref=None,
        status=AIProviderStatus.ENABLED,
        created_by_user_id=owner.id,
    )
    db.add(provider)
    db.flush()
    model = AIModelConfiguration(
        organization_id=organization.id,
        provider_configuration_id=provider.id,
        model_key="workspace-model-v1",
        display_name="Workspace Model V1",
        enabled=True,
        max_output_tokens=2000,
        created_by_user_id=owner.id,
    )
    db.add(model)
    db.flush()
    definition = AgentDefinition(
        organization_id=organization.id,
        name="Engineering Agent",
        description="Governed engineering helper",
        provider_configuration_id=provider.id,
        model_configuration_id=model.id,
        enabled=True,
        max_steps=4,
        created_by_user_id=owner.id,
    )
    db.add(definition)
    db.flush()
    db.add_all(
        [
            AgentToolPolicy(
                organization_id=organization.id,
                agent_definition_id=definition.id,
                tool_name="search.query",
                policy=AgentToolPolicyMode.READ,
                created_by_user_id=owner.id,
            ),
            AgentToolPolicy(
                organization_id=organization.id,
                agent_definition_id=definition.id,
                tool_name="work_graph.create_work_item",
                policy=AgentToolPolicyMode.ACT_WITH_APPROVAL,
                created_by_user_id=owner.id,
            ),
        ]
    )
    project = WorkGraphNode(
        organization_id=organization.id,
        node_type=WorkGraphNodeType.PROJECT,
        stable_key=f"project:test:{suffix}",
        display_name="Brain Backend",
        source_visibility="organization",
        source_acl=[],
        attributes={
            "provider": "github",
            "repository_id": "repo-123",
            "repository": "kunalwagh101/Brain.ai",
        },
    )
    db.add(project)
    db.commit()
    return organization, owner, member, other, provider, model, definition, project


def _auth(user: User) -> None:
    app.dependency_overrides[get_current_user] = lambda: user


def _clear_auth() -> None:
    app.dependency_overrides.pop(get_current_user, None)


def test_workspace_run_is_project_scoped_and_requester_private(
    client: TestClient,
    db_session: Session,
) -> None:
    organization, _, member, other, _, _, definition, project = _seed(
        db_session, "project"
    )
    _auth(member)
    try:
        created = client.post(
            f"/api/v1/organizations/{organization.id}/agent-workspace/runs",
            json={
                "agent_definition_id": str(definition.id),
                "objective": (
                    "Inspect the visible backend project and propose the next governed work item."
                ),
                "project_node_id": str(project.id),
            },
        )
        assert created.status_code == 201
        payload = created.json()
        assert payload["context"]["available"] is True
        assert payload["context"]["project"]["node_id"] == str(project.id)
        assert payload["context"]["project"]["repository_id"] == "repo-123"
        assert payload["agent_name"] == "Engineering Agent"
        assert payload["provider_display_name"] == "Workspace Provider"
        assert payload["model_display_name"] == "Workspace Model V1"
        assert payload["objective_char_count"] > 0
        assert "objective" not in payload
        assert "secret_ref" not in str(payload)

        workspace = client.get(
            f"/api/v1/organizations/{organization.id}/agent-workspace"
        )
        assert workspace.status_code == 200
        assert [item["id"] for item in workspace.json()["runs"]] == [payload["id"]]
        policy = next(
            item
            for item in workspace.json()["agents"][0]["tool_policies"]
            if item["tool_name"] == "work_graph.create_work_item"
        )
        assert policy["risk"] == "high_risk_action"
        assert policy["approval_required"] is True

        _auth(other)
        isolated = client.get(
            f"/api/v1/organizations/{organization.id}/agent-workspace"
        )
        assert isolated.status_code == 200
        assert isolated.json()["runs"] == []
    finally:
        _clear_auth()


def test_restricted_project_is_rejected_before_run_creation(
    client: TestClient,
    db_session: Session,
) -> None:
    organization, _, member, _, _, _, definition, project = _seed(
        db_session, "restricted-project"
    )
    project.source_visibility = "restricted"
    db_session.commit()
    _auth(member)
    try:
        response = client.post(
            f"/api/v1/organizations/{organization.id}/agent-workspace/runs",
            json={
                "agent_definition_id": str(definition.id),
                "objective": "This must not bind to hidden context.",
                "project_node_id": str(project.id),
            },
        )
    finally:
        _clear_auth()

    assert response.status_code == 404
    assert db_session.scalar(
        select(AgentRun.id).where(
            AgentRun.organization_id == organization.id,
            AgentRun.requested_by_user_id == member.id,
        )
    ) is None


def test_cross_tenant_project_context_is_not_an_existence_oracle(
    client: TestClient,
    db_session: Session,
) -> None:
    organization_a, _, member_a, _, _, _, definition_a, _ = _seed(
        db_session, "tenant-a"
    )
    _, _, _, _, _, _, _, project_b = _seed(db_session, "tenant-b")
    _auth(member_a)
    try:
        response = client.post(
            f"/api/v1/organizations/{organization_a.id}/agent-workspace/runs",
            json={
                "agent_definition_id": str(definition_a.id),
                "objective": "Do not reveal the other tenant.",
                "project_node_id": str(project_b.id),
            },
        )
    finally:
        _clear_auth()
    assert response.status_code == 404


def test_revoked_channel_context_is_redacted_from_existing_run(
    client: TestClient,
    db_session: Session,
) -> None:
    organization, owner, member, _, _, _, definition, _ = _seed(
        db_session, "channel-revoke"
    )
    channel = NativeChannel(
        organization_id=organization.id,
        name="private-engineering",
        slug="private-engineering",
        description="Restricted engineering channel",
        visibility=NativeChannelVisibility.RESTRICTED,
        status=NativeChannelStatus.ACTIVE,
        created_by_user_id=owner.id,
    )
    db_session.add(channel)
    db_session.flush()
    membership = NativeChannelMembership(
        organization_id=organization.id,
        channel_id=channel.id,
        user_id=member.id,
        access=ResourceAccessLevel.WRITE,
        granted_by_user_id=owner.id,
    )
    db_session.add(membership)
    db_session.commit()

    _auth(member)
    try:
        created = client.post(
            f"/api/v1/organizations/{organization.id}/agent-workspace/runs",
            json={
                "agent_definition_id": str(definition.id),
                "objective": "Work only in the restricted engineering channel context.",
                "native_channel_id": str(channel.id),
            },
        )
        assert created.status_code == 201
        run_id = created.json()["id"]
        assert created.json()["context"]["channel"]["name"] == "private-engineering"

        membership.revoked_at = datetime.now(UTC)
        db_session.commit()
        after_revoke = client.get(
            f"/api/v1/organizations/{organization.id}/agent-workspace/runs/{run_id}"
        )
    finally:
        _clear_auth()

    assert after_revoke.status_code == 200
    assert after_revoke.json()["context"]["available"] is False
    assert after_revoke.json()["context"]["channel"] is None


def test_waiting_high_risk_step_is_explicit_in_workspace_read_model(
    client: TestClient,
    db_session: Session,
) -> None:
    organization, _, member, _, _, _, definition, project = _seed(
        db_session, "approval"
    )
    _auth(member)
    try:
        created = client.post(
            f"/api/v1/organizations/{organization.id}/agent-workspace/runs",
            json={
                "agent_definition_id": str(definition.id),
                "objective": "Propose a governed work item.",
                "project_node_id": str(project.id),
            },
        )
        assert created.status_code == 201
        run_id = uuid.UUID(created.json()["id"])
        step = AgentStep(
            organization_id=organization.id,
            run_id=run_id,
            sequence=1,
            tool_name="work_graph.create_work_item",
            policy=AgentToolPolicyMode.ACT_WITH_APPROVAL,
            status=AgentStepStatus.WAITING_APPROVAL,
            arguments_json={"key": "review-auth", "display_name": "Review auth boundary"},
            arguments_sha256="a" * 64,
            proposal_reason="Create a tracked review item",
            approval_expires_at=datetime.now(UTC),
        )
        db_session.add(step)
        run = db_session.get(AgentRun, run_id)
        assert run is not None
        run.step_count = 1
        db_session.commit()

        response = client.get(
            f"/api/v1/organizations/{organization.id}/agent-workspace/runs/{run_id}"
        )
    finally:
        _clear_auth()

    assert response.status_code == 200
    step_payload = response.json()["steps"][0]
    assert step_payload["status"] == "waiting_approval"
    assert step_payload["policy"] == "act_with_approval"
    assert step_payload["arguments"]["key"] == "review-auth"


def test_guest_cannot_open_agent_workspace(
    client: TestClient,
    db_session: Session,
) -> None:
    organization, _, _, _, _, _, _, _ = _seed(db_session, "guest")
    guest = User(email="workspace-guest@example.com")
    db_session.add(guest)
    db_session.flush()
    db_session.add(
        Membership(
            organization_id=organization.id,
            user_id=guest.id,
            role=MembershipRole.GUEST,
        )
    )
    db_session.commit()
    _auth(guest)
    try:
        response = client.get(
            f"/api/v1/organizations/{organization.id}/agent-workspace"
        )
    finally:
        _clear_auth()
    assert response.status_code == 403

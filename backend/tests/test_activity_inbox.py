import hashlib
import uuid

from sqlalchemy.orm import Session

from app.agent_models import (
    AgentDefinition,
    AgentRun,
    AgentRunStatus,
    AgentStep,
    AgentStepStatus,
    AgentToolPolicyMode,
)
from app.agent_workspace_models import AgentRunContext
from app.ai_gateway_models import (
    AIModelConfiguration,
    AIProviderAdapterKind,
    AIProviderConfiguration,
)
from app.auth import get_current_user
from app.main import app
from app.models import (
    IntegrationConnection,
    IntegrationHealth,
    Membership,
    MembershipRole,
    Organization,
    User,
)
from app.project_status_models import ProjectProgressItem, ProjectWorkState
from app.work_graph_models import WorkGraphNode, WorkGraphNodeType


def _seed(db: Session):
    organization = Organization(name="Inbox Org", slug=f"inbox-{uuid.uuid4().hex[:8]}")
    owner = User(email=f"inbox-owner-{uuid.uuid4().hex[:8]}@example.com", display_name="Owner")
    member = User(email=f"inbox-member-{uuid.uuid4().hex[:8]}@example.com", display_name="Member")
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


def _as(user: User) -> None:
    app.dependency_overrides[get_current_user] = lambda: user


def _provider_agent(db: Session, organization: Organization, owner: User) -> AgentDefinition:
    provider = AIProviderConfiguration(
        organization_id=organization.id,
        provider_key=f"activity-{uuid.uuid4().hex[:6]}",
        display_name="Activity test provider",
        adapter_kind=AIProviderAdapterKind.OPENAI_CHAT_COMPLETIONS,
        api_url="https://example.invalid/v1/chat/completions",
        created_by_user_id=owner.id,
    )
    db.add(provider)
    db.flush()
    model = AIModelConfiguration(
        organization_id=organization.id,
        provider_configuration_id=provider.id,
        model_key="activity-test-model",
        display_name="Activity test model",
        enabled=True,
        created_by_user_id=owner.id,
    )
    db.add(model)
    db.flush()
    agent = AgentDefinition(
        organization_id=organization.id,
        name=f"Activity agent {uuid.uuid4().hex[:6]}",
        provider_configuration_id=provider.id,
        model_configuration_id=model.id,
        enabled=True,
        max_steps=4,
        created_by_user_id=owner.id,
    )
    db.add(agent)
    db.flush()
    return agent


def test_preferences_are_personal_and_hide_disabled_integration_failures(
    db_session: Session,
    client,
) -> None:
    organization, owner, member = _seed(db_session)
    integration = IntegrationConnection(
        organization_id=organization.id,
        provider="slack",
        external_account_id=f"workspace-{uuid.uuid4().hex[:8]}",
        display_name="Company Slack",
        health=IntegrationHealth.ERROR,
        last_error_code="sync_failed",
        created_by_user_id=owner.id,
    )
    db_session.add(integration)
    db_session.commit()

    _as(owner)
    response = client.get(f"/api/v1/organizations/{organization.id}/activity")
    assert response.status_code == 200
    item = next(item for item in response.json()["items"] if item["kind"] == "integration_failure")
    assert str(integration.id) in item["href"]
    assert integration.external_account_id not in response.text
    assert "sync_failed" not in response.text

    preferences = client.get(f"/api/v1/organizations/{organization.id}/activity/preferences")
    assert preferences.status_code == 200
    assert all(preferences.json().values())
    disabled = client.put(
        f"/api/v1/organizations/{organization.id}/activity/preferences",
        json={"integration_failures": False},
    )
    assert disabled.status_code == 200
    assert disabled.json()["integration_failures"] is False
    hidden = client.get(f"/api/v1/organizations/{organization.id}/activity")
    assert all(item["kind"] != "integration_failure" for item in hidden.json()["items"])

    _as(member)
    member_preferences = client.get(
        f"/api/v1/organizations/{organization.id}/activity/preferences"
    )
    assert member_preferences.status_code == 200
    assert member_preferences.json()["integration_failures"] is True
    member_activity = client.get(f"/api/v1/organizations/{organization.id}/activity")
    assert all(item["kind"] != "integration_failure" for item in member_activity.json()["items"])


def test_generic_unread_channel_activity_links_to_exact_latest_message(
    db_session: Session,
    client,
) -> None:
    organization, owner, member = _seed(db_session)
    _as(owner)
    channel_response = client.post(
        f"/api/v1/organizations/{organization.id}/native-channels",
        json={"name": f"inbox-{uuid.uuid4().hex[:6]}", "visibility": "organization"},
    )
    assert channel_response.status_code == 201
    channel_id = channel_response.json()["id"]
    message_response = client.post(
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel_id}/messages",
        headers={"Idempotency-Key": "activity-inbox-generic"},
        json={"body": "generic unread body must not be copied"},
    )
    assert message_response.status_code == 201
    message_id = message_response.json()["id"]

    _as(member)
    activity = client.get(f"/api/v1/organizations/{organization.id}/activity")
    assert activity.status_code == 200
    item = next(item for item in activity.json()["items"] if item["kind"] == "channel_activity")
    assert f"channelId={channel_id}" in item["href"]
    assert f"messageId={message_id}" in item["href"]
    assert "generic unread body must not be copied" not in activity.text


def test_project_and_agent_items_recheck_current_permissions_and_link_exact_context(
    db_session: Session,
    client,
) -> None:
    organization, owner, member = _seed(db_session)
    project = WorkGraphNode(
        organization_id=organization.id,
        node_type=WorkGraphNodeType.PROJECT,
        stable_key=f"project:{uuid.uuid4()}",
        display_name="Activity Project",
        source_visibility="organization",
        source_acl=[],
        attributes={},
    )
    work_item = WorkGraphNode(
        organization_id=organization.id,
        node_type=WorkGraphNodeType.WORK_ITEM,
        stable_key=f"work:{uuid.uuid4()}",
        display_name="Ship inbox",
        source_visibility="organization",
        source_acl=[],
        attributes={},
    )
    db_session.add_all([project, work_item])
    db_session.flush()
    progress = ProjectProgressItem(
        organization_id=organization.id,
        project_node_id=project.id,
        work_item_node_id=work_item.id,
        state=ProjectWorkState.IN_PROGRESS,
        weight=1,
        note="inbox work",
        updated_by_user_id=owner.id,
    )
    db_session.add(progress)

    agent = _provider_agent(db_session, organization, owner)
    digest = hashlib.sha256(b"activity objective").hexdigest()
    completed = AgentRun(
        organization_id=organization.id,
        agent_definition_id=agent.id,
        requested_by_user_id=member.id,
        status=AgentRunStatus.COMPLETED,
        objective_sha256=digest,
        objective_char_count=18,
        completed_at=progress.updated_at,
    )
    approval = AgentRun(
        organization_id=organization.id,
        agent_definition_id=agent.id,
        requested_by_user_id=member.id,
        status=AgentRunStatus.WAITING_APPROVAL,
        objective_sha256=digest,
        objective_char_count=18,
    )
    db_session.add_all([completed, approval])
    db_session.flush()
    db_session.add_all(
        [
            AgentRunContext(
                organization_id=organization.id,
                run_id=completed.id,
                project_node_id=project.id,
            ),
            AgentRunContext(
                organization_id=organization.id,
                run_id=approval.id,
                project_node_id=project.id,
            ),
        ]
    )
    step = AgentStep(
        organization_id=organization.id,
        run_id=approval.id,
        sequence=1,
        tool_name="github.create_pull_request",
        policy=AgentToolPolicyMode.ACT_WITH_APPROVAL,
        status=AgentStepStatus.WAITING_APPROVAL,
        arguments_json={},
        arguments_sha256=hashlib.sha256(b"{}").hexdigest(),
    )
    db_session.add(step)
    db_session.commit()

    _as(member)
    member_activity = client.get(f"/api/v1/organizations/{organization.id}/activity")
    assert member_activity.status_code == 200
    completed_item = next(
        item for item in member_activity.json()["items"] if item["kind"] == "agent_completed"
    )
    assert f"agentRunId={completed.id}" in completed_item["href"]
    assert all(item["kind"] != "agent_approval" for item in member_activity.json()["items"])
    project_item = next(
        item for item in member_activity.json()["items"] if item["kind"] == "project_update"
    )
    assert f"projectId={project.id}" in project_item["href"]

    _as(owner)
    owner_activity = client.get(f"/api/v1/organizations/{organization.id}/activity")
    assert owner_activity.status_code == 200
    approval_item = next(
        item for item in owner_activity.json()["items"] if item["kind"] == "agent_approval"
    )
    assert f"agentRunId={approval.id}" in approval_item["href"]
    assert f"agentStepId={step.id}" in approval_item["href"]

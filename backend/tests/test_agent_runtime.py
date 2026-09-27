import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent_models import (
    AgentRunStatus,
    AgentStep,
    AgentStepStatus,
    AgentToolPolicyMode,
)
from app.agent_runtime import (
    AgentRuntimeError,
    advance_agent_run,
    create_agent_definition,
    create_agent_run,
    decide_agent_step,
)
from app.ai_gateway import (
    AIProviderResult,
    create_model_configuration,
    create_provider_configuration,
)
from app.ai_gateway_models import AIProviderAdapterKind
from app.data_governance_models import SecurityAuditEvent
from app.models import Membership, MembershipRole, Organization, User
from app.permissions import Permission, role_has_permission
from app.secrets import SecretStoreError
from app.work_graph_models import WorkGraphNode


class FakeSecretStore:
    def __init__(self) -> None:
        self.values: dict[str, dict[str, str]] = {}

    def store_ai_provider_secret(
        self,
        *,
        organization_id: uuid.UUID,
        provider_configuration_id: uuid.UUID,
        provider: str,
        credentials: dict[str, str],
    ) -> str:
        reference = f"arn:test:agent:{organization_id}:{provider}:{provider_configuration_id}"
        self.values[reference] = dict(credentials)
        return reference

    def load_connection_secret(self, reference: str) -> dict[str, str]:
        value = self.values.get(reference)
        if value is None:
            raise SecretStoreError("missing")
        return dict(value)

    def schedule_delete(self, reference: str) -> None:
        self.values.pop(reference, None)


class PlannerAdapter:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = list(outputs)
        self.calls = 0

    def invoke(self, **kwargs) -> AIProviderResult:
        del kwargs
        self.calls += 1
        if not self.outputs:
            raise AssertionError("PlannerAdapter received an unexpected call")
        return AIProviderResult(
            output_text=self.outputs.pop(0),
            provider_request_id=f"planner-{self.calls}",
            input_tokens=10,
            output_tokens=5,
        )


def _seed(db: Session, suffix: str):
    owner = User(email=f"agent-owner-{suffix}@example.com")
    member = User(email=f"agent-member-{suffix}@example.com")
    other = User(email=f"agent-other-{suffix}@example.com")
    organization = Organization(name=f"Agent Org {suffix}", slug=f"agent-{suffix}")
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
    db.commit()
    store = FakeSecretStore()
    provider = create_provider_configuration(
        db,
        secret_store=store,
        organization_id=organization.id,
        actor_user_id=owner.id,
        provider_key=f"agent-ai-{suffix}",
        display_name="Agent AI",
        adapter_kind=AIProviderAdapterKind.OPENAI_CHAT_COMPLETIONS,
        api_url="https://ai.example.com/v1/chat/completions",
        credentials={"api_key": "agent-test-key"},
    )
    model = create_model_configuration(
        db,
        organization_id=organization.id,
        actor_user_id=owner.id,
        provider_configuration_id=provider.id,
        model_key="planner-v1",
        display_name="Planner V1",
        enabled=True,
        max_output_tokens=2000,
    )
    return organization, owner, member, other, store, provider, model


def _definition(
    db: Session,
    *,
    organization: Organization,
    owner: User,
    provider_id: uuid.UUID,
    model_id: uuid.UUID,
    policies: dict[str, AgentToolPolicyMode],
):
    return create_agent_definition(
        db,
        organization_id=organization.id,
        actor_user_id=owner.id,
        name=f"Agent {uuid.uuid4()}",
        description="Governed test agent",
        provider_configuration_id=provider_id,
        model_configuration_id=model_id,
        max_steps=4,
        tool_policies=policies,
    )


def test_agent_permissions_separate_use_and_management() -> None:
    assert role_has_permission(MembershipRole.OWNER, Permission.AGENT_MANAGE)
    assert role_has_permission(MembershipRole.ADMIN, Permission.AGENT_MANAGE)
    assert not role_has_permission(MembershipRole.MEMBER, Permission.AGENT_MANAGE)
    assert role_has_permission(MembershipRole.MEMBER, Permission.AGENT_USE)
    assert not role_has_permission(MembershipRole.GUEST, Permission.AGENT_USE)


def test_high_risk_tool_cannot_be_downgraded_to_direct_act(db_session: Session) -> None:
    organization, owner, _, _, store, provider, model = _seed(db_session, "policy")
    del store
    with pytest.raises(AgentRuntimeError, match="cannot be assigned"):
        _definition(
            db_session,
            organization=organization,
            owner=owner,
            provider_id=provider.id,
            model_id=model.id,
            policies={"work_graph.create_work_item": AgentToolPolicyMode.ACT},
        )


def test_missing_policy_defaults_to_deny_and_is_audited(db_session: Session) -> None:
    organization, owner, member, _, store, provider, model = _seed(db_session, "deny")
    definition = _definition(
        db_session,
        organization=organization,
        owner=owner,
        provider_id=provider.id,
        model_id=model.id,
        policies={},
    )
    objective = "Find the current launch status"
    run = create_agent_run(
        db_session,
        organization_id=organization.id,
        agent_definition_id=definition.id,
        requested_by_user_id=member.id,
        objective=objective,
    )
    adapter = PlannerAdapter(
        ['{"action":"tool","tool":"search.query","arguments":{"query":"launch"}}']
    )

    with pytest.raises(AgentRuntimeError, match="denied tool"):
        advance_agent_run(
            db_session,
            secret_store=store,
            organization_id=organization.id,
            run_id=run.id,
            user_id=member.id,
            role=MembershipRole.MEMBER,
            objective=objective,
            planner_adapter=adapter,
        )

    db_session.expire_all()
    denied = db_session.scalar(select(AgentStep).where(AgentStep.run_id == run.id))
    assert denied is not None
    assert denied.status == AgentStepStatus.DENIED
    assert denied.arguments_json == {}
    assert db_session.scalar(
        select(SecurityAuditEvent).where(
            SecurityAuditEvent.organization_id == organization.id,
            SecurityAuditEvent.event_type == "agent.tool.denied",
        )
    ) is not None


def test_objective_digest_prevents_run_goal_substitution(db_session: Session) -> None:
    organization, owner, member, _, store, provider, model = _seed(db_session, "objective")
    definition = _definition(
        db_session,
        organization=organization,
        owner=owner,
        provider_id=provider.id,
        model_id=model.id,
        policies={},
    )
    run = create_agent_run(
        db_session,
        organization_id=organization.id,
        agent_definition_id=definition.id,
        requested_by_user_id=member.id,
        objective="Original objective",
    )
    with pytest.raises(AgentRuntimeError, match="does not match"):
        advance_agent_run(
            db_session,
            secret_store=store,
            organization_id=organization.id,
            run_id=run.id,
            user_id=member.id,
            role=MembershipRole.MEMBER,
            objective="Different objective",
            planner_adapter=PlannerAdapter([]),
        )


def test_other_member_cannot_continue_someone_elses_run(db_session: Session) -> None:
    organization, owner, member, other, store, provider, model = _seed(db_session, "isolation")
    definition = _definition(
        db_session,
        organization=organization,
        owner=owner,
        provider_id=provider.id,
        model_id=model.id,
        policies={},
    )
    run = create_agent_run(
        db_session,
        organization_id=organization.id,
        agent_definition_id=definition.id,
        requested_by_user_id=member.id,
        objective="Private run objective",
    )
    with pytest.raises(AgentRuntimeError, match="not found"):
        advance_agent_run(
            db_session,
            secret_store=store,
            organization_id=organization.id,
            run_id=run.id,
            user_id=other.id,
            role=MembershipRole.MEMBER,
            objective="Private run objective",
            planner_adapter=PlannerAdapter([]),
        )


def test_high_risk_action_pauses_then_executes_after_explicit_approval(
    db_session: Session,
) -> None:
    organization, owner, member, _, store, provider, model = _seed(db_session, "approval")
    definition = _definition(
        db_session,
        organization=organization,
        owner=owner,
        provider_id=provider.id,
        model_id=model.id,
        policies={
            "work_graph.create_work_item": AgentToolPolicyMode.ACT_WITH_APPROVAL,
        },
    )
    objective = "Create a work item called Security review"
    run = create_agent_run(
        db_session,
        organization_id=organization.id,
        agent_definition_id=definition.id,
        requested_by_user_id=member.id,
        objective=objective,
    )
    proposal = PlannerAdapter(
        [
            '{"action":"tool","tool":"work_graph.create_work_item",'
            '"arguments":{"key":"security-review","display_name":"Security review"},'
            '"reason":"The user requested this work item"}'
        ]
    )
    first = advance_agent_run(
        db_session,
        secret_store=store,
        organization_id=organization.id,
        run_id=run.id,
        user_id=member.id,
        role=MembershipRole.MEMBER,
        objective=objective,
        planner_adapter=proposal,
    )
    assert first.run.status == AgentRunStatus.WAITING_APPROVAL
    step = db_session.scalar(select(AgentStep).where(AgentStep.run_id == run.id))
    assert step is not None
    assert step.status == AgentStepStatus.WAITING_APPROVAL
    assert step.arguments_json["key"] == "security-review"
    node = db_session.scalar(
        select(WorkGraphNode).where(
            WorkGraphNode.stable_key.like("%security-review")
        )
    )
    assert node is None

    decide_agent_step(
        db_session,
        organization_id=organization.id,
        run_id=run.id,
        step_id=step.id,
        user_id=member.id,
        approve=True,
        reason="Approved after reviewing the proposed work item",
    )
    final = advance_agent_run(
        db_session,
        secret_store=store,
        organization_id=organization.id,
        run_id=run.id,
        user_id=member.id,
        role=MembershipRole.MEMBER,
        objective=objective,
        planner_adapter=PlannerAdapter(
            ['{"action":"final","answer":"The approved work item was created."}']
        ),
    )
    assert final.run.status == AgentRunStatus.COMPLETED
    assert final.final_output == "The approved work item was created."
    db_session.expire_all()
    executed_step = db_session.get(AgentStep, step.id)
    assert executed_step is not None
    assert executed_step.status == AgentStepStatus.SUCCEEDED
    assert executed_step.arguments_json == {}
    assert db_session.scalar(
        select(WorkGraphNode).where(
            WorkGraphNode.organization_id == organization.id,
            WorkGraphNode.stable_key == "manual:work_item:security-review",
        )
    ) is not None
    event_types = set(
        db_session.scalars(
            select(SecurityAuditEvent.event_type).where(
                SecurityAuditEvent.organization_id == organization.id,
                SecurityAuditEvent.event_type.in_(
                    [
                        "agent.approval.requested",
                        "agent.approval.approved",
                        "agent.tool.succeeded",
                    ]
                ),
            )
        )
    )
    assert event_types == {
        "agent.approval.requested",
        "agent.approval.approved",
        "agent.tool.succeeded",
    }


def test_rejected_approval_clears_arguments_and_cancels_run(db_session: Session) -> None:
    organization, owner, member, _, store, provider, model = _seed(db_session, "reject")
    definition = _definition(
        db_session,
        organization=organization,
        owner=owner,
        provider_id=provider.id,
        model_id=model.id,
        policies={
            "work_graph.create_work_item": AgentToolPolicyMode.ACT_WITH_APPROVAL,
        },
    )
    objective = "Create a work item"
    run = create_agent_run(
        db_session,
        organization_id=organization.id,
        agent_definition_id=definition.id,
        requested_by_user_id=member.id,
        objective=objective,
    )
    advance_agent_run(
        db_session,
        secret_store=store,
        organization_id=organization.id,
        run_id=run.id,
        user_id=member.id,
        role=MembershipRole.MEMBER,
        objective=objective,
        planner_adapter=PlannerAdapter(
            [
                '{"action":"tool","tool":"work_graph.create_work_item",'
                '"arguments":{"key":"do-not-create","display_name":"Do not create"}}'
            ]
        ),
    )
    step = db_session.scalar(select(AgentStep).where(AgentStep.run_id == run.id))
    assert step is not None
    decide_agent_step(
        db_session,
        organization_id=organization.id,
        run_id=run.id,
        step_id=step.id,
        user_id=member.id,
        approve=False,
        reason="Not approved",
    )
    db_session.expire_all()
    persisted_run = db_session.get(type(run), run.id)
    persisted_step = db_session.get(AgentStep, step.id)
    assert persisted_run is not None
    assert persisted_run.status == AgentRunStatus.CANCELLED
    assert persisted_step is not None
    assert persisted_step.status == AgentStepStatus.REJECTED
    assert persisted_step.arguments_json == {}
    assert db_session.scalar(
        select(WorkGraphNode).where(WorkGraphNode.stable_key.like("%do-not-create"))
    ) is None

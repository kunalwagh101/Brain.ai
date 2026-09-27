import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.ai_gateway_models import (
    AIModelConfiguration,
    AIProviderAdapterKind,
    AIProviderConfiguration,
    AIRequestRecord,
    AIRequestStatus,
)
from app.ai_usage import create_budget_policy
from app.ai_usage_models import AIBudgetScopeType
from app.executive_overview import build_executive_overview
from app.models import (
    Membership,
    MembershipRole,
    Organization,
    ResourceAccessLevel,
    ResourceGrant,
    User,
)
from app.work_graph_models import WorkGraphNode, WorkGraphNodeType


def test_hidden_work_graph_budget_never_leaks_target_to_executive(
    db_session: Session,
) -> None:
    owner = User(email=f"hidden-budget-owner-{uuid.uuid4()}@example.com")
    executive = User(email=f"hidden-budget-exec-{uuid.uuid4()}@example.com")
    member = User(email=f"hidden-budget-member-{uuid.uuid4()}@example.com")
    organization = Organization(
        name="Hidden Budget Org",
        slug=f"hidden-budget-{uuid.uuid4().hex[:8]}",
    )
    db_session.add_all([owner, executive, member, organization])
    db_session.flush()
    db_session.add_all(
        [
            Membership(
                organization_id=organization.id,
                user_id=owner.id,
                role=MembershipRole.OWNER,
            ),
            Membership(
                organization_id=organization.id,
                user_id=executive.id,
                role=MembershipRole.EXECUTIVE,
            ),
            Membership(
                organization_id=organization.id,
                user_id=member.id,
                role=MembershipRole.MEMBER,
            ),
        ]
    )
    restricted_project = WorkGraphNode(
        organization_id=organization.id,
        node_type=WorkGraphNodeType.PROJECT,
        stable_key="hidden-project",
        display_name="Hidden Acquisition",
        source_visibility="private_repository",
        source_acl=["github:repository:secret-991"],
        attributes={"provider": "github", "repository_id": "secret-991"},
    )
    db_session.add(restricted_project)
    db_session.flush()
    db_session.add(
        ResourceGrant(
            organization_id=organization.id,
            resource_type="work_graph.node",
            resource_id=str(restricted_project.id),
            user_id=owner.id,
            access=ResourceAccessLevel.READ,
            created_by_user_id=owner.id,
        )
    )

    provider = AIProviderConfiguration(
        organization_id=organization.id,
        provider_key="provider-hidden-budget",
        display_name="Provider",
        adapter_kind=AIProviderAdapterKind.OPENAI_CHAT_COMPLETIONS,
        api_url="https://ai.example.com/v1/chat/completions",
        secret_ref="arn:test:hidden-budget",
        created_by_user_id=owner.id,
    )
    db_session.add(provider)
    db_session.flush()
    model = AIModelConfiguration(
        organization_id=organization.id,
        provider_configuration_id=provider.id,
        model_key="model-hidden-budget",
        display_name="Model",
        enabled=True,
        max_output_tokens=100,
        created_by_user_id=owner.id,
    )
    db_session.add(model)
    db_session.flush()

    policy = create_budget_policy(
        db_session,
        organization_id=organization.id,
        actor_user_id=owner.id,
        scope_type=AIBudgetScopeType.WORK_GRAPH_NODE,
        scope_target_id=restricted_project.id,
        limit_nano_usd=1_000_000,
        warning_threshold_percent=80,
        hard_limit=False,
        enabled=True,
    )
    now = datetime.now(UTC)
    db_session.add(
        AIRequestRecord(
            organization_id=organization.id,
            user_id=member.id,
            provider_configuration_id=provider.id,
            model_configuration_id=model.id,
            provider_key=provider.provider_key,
            model_key=model.model_key,
            attribution_node_id=restricted_project.id,
            attribution_node_type=WorkGraphNodeType.PROJECT.value,
            status=AIRequestStatus.SUCCEEDED,
            input_char_count=10,
            output_char_count=5,
            input_tokens=None,
            cached_input_tokens=None,
            output_tokens=None,
            latency_ms=10,
            provider_request_id="hidden-budget-request",
            completed_at=now,
            created_at=now - timedelta(seconds=1),
        )
    )
    db_session.commit()

    owner_view = build_executive_overview(
        db_session,
        organization_id=organization.id,
        user_id=owner.id,
        role=MembershipRole.OWNER,
        at=now + timedelta(seconds=1),
    )
    executive_view = build_executive_overview(
        db_session,
        organization_id=organization.id,
        user_id=executive.id,
        role=MembershipRole.EXECUTIVE,
        at=now + timedelta(seconds=1),
    )

    assert any(item.budget_policy_id == policy.id for item in owner_view.budget_warnings)
    assert all(item.budget_policy_id != policy.id for item in executive_view.budget_warnings)
    assert all(
        item.scope_target_id != restricted_project.id
        for item in executive_view.budget_warnings
    )
    assert all(
        risk.project_node_id != restricted_project.id
        for risk in executive_view.risks
    )
    assert all(
        item.project_node_id != restricted_project.id
        for item in executive_view.portfolio
    )

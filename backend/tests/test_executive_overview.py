import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai_gateway_models import (
    AIModelConfiguration,
    AIProviderAdapterKind,
    AIProviderConfiguration,
    AIRequestRecord,
    AIRequestStatus,
)
from app.ai_usage import create_budget_policy, create_model_rate_card, materialize_request_cost
from app.ai_usage_models import AIBudgetScopeType
from app.api_registry_models import (
    APICredentialGrant,
    APIGrantStatus,
    APIService,
    APIUsageObservation,
)
from app.auth import get_current_user
from app.executive_overview import build_executive_overview
from app.main import app
from app.models import Membership, MembershipRole, Organization, User
from app.work_graph import create_manual_node
from app.work_graph_models import WorkGraphNode, WorkGraphNodeType


def _seed(db: Session, suffix: str):
    owner = User(email=f"overview-owner-{suffix}@example.com")
    executive = User(email=f"overview-exec-{suffix}@example.com")
    member = User(email=f"overview-member-{suffix}@example.com")
    organization = Organization(
        name=f"Overview Org {suffix}",
        slug=f"overview-{suffix}-{uuid.uuid4().hex[:6]}",
    )
    db.add_all([owner, executive, member, organization])
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
    db.commit()
    return organization, owner, executive, member


def _provider_model(db: Session, organization: Organization, owner: User, suffix: str):
    provider = AIProviderConfiguration(
        organization_id=organization.id,
        provider_key=f"openai-{suffix}",
        display_name="OpenAI",
        adapter_kind=AIProviderAdapterKind.OPENAI_CHAT_COMPLETIONS,
        api_url="https://api.openai.com/v1/chat/completions",
        secret_ref="arn:test:openai",
        created_by_user_id=owner.id,
    )
    db.add(provider)
    db.flush()
    model = AIModelConfiguration(
        organization_id=organization.id,
        provider_configuration_id=provider.id,
        model_key=f"model-{suffix}",
        display_name="Model",
        enabled=True,
        max_output_tokens=1024,
        created_by_user_id=owner.id,
    )
    db.add(model)
    db.commit()
    return provider, model


def test_overview_filters_restricted_projects_and_never_emits_productivity_score(
    db_session: Session,
) -> None:
    organization, owner, executive, _ = _seed(db_session, "permissions")
    public_project = create_manual_node(
        db_session,
        organization_id=organization.id,
        node_type=WorkGraphNodeType.PROJECT,
        key="public-project",
        display_name="Public Project",
        actor_user_id=owner.id,
    )
    restricted_project = WorkGraphNode(
        organization_id=organization.id,
        node_type=WorkGraphNodeType.PROJECT,
        stable_key="restricted-project",
        display_name="Restricted Project",
        source_visibility="private_repository",
        source_acl=["github:repository:991"],
        attributes={"provider": "github", "repository_id": "991"},
    )
    db_session.add(restricted_project)
    db_session.commit()

    overview = build_executive_overview(
        db_session,
        organization_id=organization.id,
        user_id=executive.id,
        role=MembershipRole.EXECUTIVE,
    )

    assert overview.visible_project_count == 1
    assert [item.project_node_id for item in overview.portfolio] == [public_project.id]
    assert overview.employee_productivity_score is None
    assert all(item.project_node_id != restricted_project.id for item in overview.portfolio)


def test_overview_uses_exact_ai_cost_budget_math_and_real_api_usage(
    db_session: Session,
) -> None:
    organization, owner, executive, member = _seed(db_session, "accounting")
    provider, model = _provider_model(db_session, organization, owner, "accounting")
    now = datetime.now(UTC)
    create_model_rate_card(
        db_session,
        organization_id=organization.id,
        actor_user_id=owner.id,
        provider_configuration_id=provider.id,
        model_configuration_id=model.id,
        input_nano_usd_per_token=100,
        cached_input_nano_usd_per_token=50,
        output_nano_usd_per_token=200,
        source_label="test pricing",
        effective_from=now - timedelta(days=1),
        effective_to=None,
    )
    budget = create_budget_policy(
        db_session,
        organization_id=organization.id,
        actor_user_id=owner.id,
        scope_type=AIBudgetScopeType.ORGANIZATION,
        scope_target_id=None,
        limit_nano_usd=10_000,
        warning_threshold_percent=80,
        hard_limit=False,
        enabled=True,
    )
    request = AIRequestRecord(
        organization_id=organization.id,
        user_id=member.id,
        provider_configuration_id=provider.id,
        model_configuration_id=model.id,
        provider_key=provider.provider_key,
        model_key=model.model_key,
        attribution_node_id=None,
        attribution_node_type=None,
        status=AIRequestStatus.SUCCEEDED,
        input_char_count=100,
        output_char_count=20,
        input_tokens=100,
        cached_input_tokens=20,
        output_tokens=10,
        latency_ms=250,
        provider_request_id="provider-request-1",
        completed_at=now,
    )
    db_session.add(request)
    db_session.commit()
    materialize_request_cost(db_session, request=request)

    service = APIService(
        organization_id=organization.id,
        service_key="crm",
        display_name="CRM API",
        provider_name="CRM Provider",
        base_url="https://crm.example.com",
        created_by_user_id=owner.id,
    )
    db_session.add(service)
    db_session.flush()
    grant = APICredentialGrant(
        organization_id=organization.id,
        service_id=service.id,
        grant_key="crm-production",
        display_name="CRM production",
        owner_user_id=owner.id,
        environment="production",
        scopes=["read"],
        secret_ref="arn:test:crm",
        status=APIGrantStatus.ACTIVE,
        created_by_user_id=owner.id,
    )
    db_session.add(grant)
    db_session.flush()
    db_session.add_all(
        [
            APIUsageObservation(
                organization_id=organization.id,
                grant_id=grant.id,
                observation_key="call-1",
                caller_component="worker",
                operation_label="sync",
                success=True,
                latency_ms=40,
                observed_at=now,
            ),
            APIUsageObservation(
                organization_id=organization.id,
                grant_id=grant.id,
                observation_key="call-2",
                caller_component="worker",
                operation_label="sync",
                success=False,
                latency_ms=70,
                observed_at=now,
            ),
        ]
    )
    db_session.commit()

    overview = build_executive_overview(
        db_session,
        organization_id=organization.id,
        user_id=executive.id,
        role=MembershipRole.EXECUTIVE,
        at=now + timedelta(seconds=1),
    )

    # 80 uncached * 100 + 20 cached * 50 + 10 output * 200 = 11,000.
    assert overview.ai_spend.known_spend_nano_usd == 11_000
    assert overview.ai_spend.unknown_cost_requests == 0
    assert overview.ai_spend.cost_complete is True
    assert overview.ai_spend.by_provider[0].provider_configuration_id == provider.id
    assert overview.ai_spend.by_provider[0].known_spend_nano_usd == 11_000
    assert len(overview.budget_warnings) == 1
    warning = overview.budget_warnings[0]
    assert warning.budget_policy_id == budget.id
    assert warning.percent_used == 110.0
    assert warning.exhausted is True
    assert warning.warning_active is True

    assert overview.api_usage.observation_count == 2
    assert overview.api_usage.succeeded_count == 1
    assert overview.api_usage.failed_count == 1
    assert overview.api_usage.active_grant_count == 1
    assert overview.api_usage.known_spend_nano_usd is None
    assert overview.api_usage.cost_status == "not_modeled"
    assert overview.api_usage.by_service[0].service_id == service.id


def test_unknown_ai_cost_is_not_silently_reported_as_complete_spend(
    db_session: Session,
) -> None:
    organization, owner, executive, member = _seed(db_session, "unknown-cost")
    provider, model = _provider_model(db_session, organization, owner, "unknown-cost")
    now = datetime.now(UTC)
    db_session.add(
        AIRequestRecord(
            organization_id=organization.id,
            user_id=member.id,
            provider_configuration_id=provider.id,
            model_configuration_id=model.id,
            provider_key=provider.provider_key,
            model_key=model.model_key,
            status=AIRequestStatus.SUCCEEDED,
            input_char_count=10,
            output_char_count=5,
            input_tokens=None,
            cached_input_tokens=None,
            output_tokens=None,
            latency_ms=100,
            provider_request_id="unknown-cost-request",
            completed_at=now,
        )
    )
    db_session.commit()

    overview = build_executive_overview(
        db_session,
        organization_id=organization.id,
        user_id=executive.id,
        role=MembershipRole.EXECUTIVE,
        at=now + timedelta(seconds=1),
    )

    assert overview.ai_spend.known_spend_nano_usd == 0
    assert overview.ai_spend.unknown_cost_requests == 1
    assert overview.ai_spend.cost_complete is False
    assert overview.ai_spend.provenance.complete is False
    assert any(risk.key == "ai_cost_incomplete" for risk in overview.risks)


def test_executive_overview_route_requires_audit_read(
    client: TestClient,
    db_session: Session,
) -> None:
    organization, _, executive, member = _seed(db_session, "route")

    app.dependency_overrides[get_current_user] = lambda: member
    try:
        denied = client.get(
            f"/api/v1/organizations/{organization.id}/executive-overview"
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert denied.status_code == 403

    app.dependency_overrides[get_current_user] = lambda: executive
    try:
        allowed = client.get(
            f"/api/v1/organizations/{organization.id}/executive-overview"
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert allowed.status_code == 200
    payload = allowed.json()
    assert payload["employee_productivity_score"] is None
    assert payload["ai_spend"]["known_spend_nano_usd"] == 0
    assert payload["api_usage"]["cost_status"] == "not_modeled"

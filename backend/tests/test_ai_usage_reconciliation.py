from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai_gateway_models import (
    AIModelConfiguration,
    AIProviderAdapterKind,
    AIProviderConfiguration,
    AIProviderStatus,
    AIRequestRecord,
    AIRequestStatus,
)
from app.ai_usage import create_model_rate_card
from app.ai_usage_models import AICostResolutionStatus, AIUsageCostRecord
from app.ai_usage_reconciliation import reconcile_usage_costs
from app.models import Membership, MembershipRole, Organization, User


def test_unknown_rate_cost_can_be_resolved_after_rate_is_added(
    db_session: Session,
) -> None:
    owner = User(email="usage-reconcile-owner@example.com")
    member = User(email="usage-reconcile-member@example.com")
    organization = Organization(name="Usage Reconcile", slug="usage-reconcile")
    db_session.add_all([owner, member, organization])
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
                user_id=member.id,
                role=MembershipRole.MEMBER,
            ),
        ]
    )
    provider = AIProviderConfiguration(
        organization_id=organization.id,
        provider_key="reconcile-provider",
        display_name="Reconcile Provider",
        adapter_kind=AIProviderAdapterKind.OPENAI_CHAT_COMPLETIONS,
        api_url="https://ai.example.com/v1/chat/completions",
        secret_ref="arn:test:reconcile",
        status=AIProviderStatus.ENABLED,
        created_by_user_id=owner.id,
    )
    db_session.add(provider)
    db_session.flush()
    model = AIModelConfiguration(
        organization_id=organization.id,
        provider_configuration_id=provider.id,
        model_key="reconcile-model",
        display_name="Reconcile Model",
        enabled=True,
        max_output_tokens=100,
        created_by_user_id=owner.id,
    )
    db_session.add(model)
    db_session.flush()
    request = AIRequestRecord(
        organization_id=organization.id,
        user_id=member.id,
        provider_configuration_id=provider.id,
        model_configuration_id=model.id,
        provider_key=provider.provider_key,
        model_key=model.model_key,
        status=AIRequestStatus.SUCCEEDED,
        input_char_count=10,
        output_char_count=2,
        input_tokens=100,
        output_tokens=10,
        latency_ms=25,
        completed_at=datetime.now(UTC),
    )
    db_session.add(request)
    db_session.commit()

    processed, resolved, remaining = reconcile_usage_costs(
        db_session,
        organization_id=organization.id,
        limit=100,
    )
    assert (processed, resolved, remaining) == (1, 0, 1)
    cost = db_session.scalar(
        select(AIUsageCostRecord).where(AIUsageCostRecord.request_id == request.id)
    )
    assert cost is not None
    assert cost.status == AICostResolutionStatus.UNKNOWN
    assert cost.unknown_reason == "rate_card_unavailable"

    create_model_rate_card(
        db_session,
        organization_id=organization.id,
        actor_user_id=owner.id,
        provider_configuration_id=provider.id,
        model_configuration_id=model.id,
        input_nano_usd_per_token=100,
        output_nano_usd_per_token=500,
        source_label="approved rate",
        effective_from=datetime.now(UTC) - timedelta(days=1),
        effective_to=None,
    )
    processed, resolved, remaining = reconcile_usage_costs(
        db_session,
        organization_id=organization.id,
        limit=100,
    )
    assert (processed, resolved, remaining) == (1, 1, 0)
    db_session.refresh(cost)
    assert cost.status == AICostResolutionStatus.CALCULATED
    assert cost.unknown_reason is None
    assert cost.input_cost_nano_usd == 10_000
    assert cost.output_cost_nano_usd == 5_000
    assert cost.total_cost_nano_usd == 15_000

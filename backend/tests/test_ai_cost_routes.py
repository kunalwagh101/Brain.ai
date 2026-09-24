from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai_gateway_models import (
    AIModelConfiguration,
    AIProviderAdapterKind,
    AIProviderConfiguration,
    AIProviderStatus,
    AIRequestRecord,
    AIRequestStatus,
)
from app.ai_usage_models import (
    AICostResolutionStatus,
    AIModelRateCard,
    AIUsageCostRecord,
)
from app.auth import get_current_user
from app.database import get_db
from app.main import app
from app.models import Membership, MembershipRole, Organization, User


def test_owner_can_read_exact_request_cost_without_cross_request_inference(
    client: TestClient,
    db_session: Session,
) -> None:
    owner = User(email="request-cost-owner@example.com")
    organization = Organization(name="Request Cost", slug="request-cost")
    db_session.add_all([owner, organization])
    db_session.flush()
    db_session.add(
        Membership(
            organization_id=organization.id,
            user_id=owner.id,
            role=MembershipRole.OWNER,
        )
    )
    provider = AIProviderConfiguration(
        organization_id=organization.id,
        provider_key="openai",
        display_name="OpenAI",
        adapter_kind=AIProviderAdapterKind.OPENAI_CHAT_COMPLETIONS,
        api_url="https://api.openai.com/v1/chat/completions",
        secret_ref="arn:test:openai",
        status=AIProviderStatus.ENABLED,
        created_by_user_id=owner.id,
    )
    db_session.add(provider)
    db_session.flush()
    model = AIModelConfiguration(
        organization_id=organization.id,
        provider_configuration_id=provider.id,
        model_key="gpt-5.6-terra",
        display_name="GPT-5.6 Terra",
        enabled=True,
        max_output_tokens=8192,
        created_by_user_id=owner.id,
    )
    db_session.add(model)
    db_session.flush()
    rate = AIModelRateCard(
        organization_id=organization.id,
        provider_configuration_id=provider.id,
        model_configuration_id=model.id,
        input_nano_usd_per_token=2_000,
        cached_input_nano_usd_per_token=200,
        output_nano_usd_per_token=12_000,
        source_label="test",
        effective_from=datetime.now(UTC),
        effective_to=None,
        created_by_user_id=owner.id,
    )
    db_session.add(rate)
    db_session.flush()
    request = AIRequestRecord(
        organization_id=organization.id,
        user_id=owner.id,
        provider_configuration_id=provider.id,
        model_configuration_id=model.id,
        provider_key="openai",
        model_key="gpt-5.6-terra",
        status=AIRequestStatus.SUCCEEDED,
        input_char_count=10,
        output_char_count=2,
        input_tokens=100,
        cached_input_tokens=40,
        output_tokens=10,
        latency_ms=25,
        completed_at=datetime.now(UTC),
    )
    db_session.add(request)
    db_session.flush()
    db_session.add(
        AIUsageCostRecord(
            organization_id=organization.id,
            request_id=request.id,
            rate_card_id=rate.id,
            status=AICostResolutionStatus.CALCULATED,
            unknown_reason=None,
            input_cost_nano_usd=128_000,
            output_cost_nano_usd=120_000,
            total_cost_nano_usd=248_000,
        )
    )
    db_session.commit()

    app.dependency_overrides[get_current_user] = lambda: owner
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        response = client.get(
            f"/api/v1/organizations/{organization.id}/ai/requests/{request.id}/cost"
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json() == {
        "request_id": str(request.id),
        "rate_card_id": str(rate.id),
        "cost_status": "calculated",
        "unknown_reason": None,
        "input_tokens": 100,
        "cached_input_tokens": 40,
        "output_tokens": 10,
        "input_cost_nano_usd": 128_000,
        "output_cost_nano_usd": 120_000,
        "total_cost_nano_usd": 248_000,
    }

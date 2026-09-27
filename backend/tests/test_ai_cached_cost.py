import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai_gateway_models import AIProviderAdapterKind, AIRequestRecord
from app.ai_provider_adapter import AIProviderResult, OpenAIChatCompletionsAdapter
from app.ai_provider_registry import (
    create_model_configuration,
    create_provider_configuration,
    invoke_ai,
)
from app.ai_usage import create_model_rate_card, usage_summary
from app.ai_usage_models import AICostResolutionStatus, AIUsageCostRecord
from app.models import Membership, MembershipRole, Organization, User
from app.secrets import SecretStoreError


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb

    def read(self, size: int = -1) -> bytes:
        return self._payload if size < 0 else self._payload[:size]


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
        reference = f"arn:test:{organization_id}:{provider}:{provider_configuration_id}"
        self.values[reference] = dict(credentials)
        return reference

    def load_connection_secret(self, reference: str) -> dict[str, str]:
        value = self.values.get(reference)
        if value is None:
            raise SecretStoreError("missing")
        return dict(value)

    def schedule_delete(self, reference: str) -> None:
        self.values.pop(reference, None)


class CachedAdapter:
    def __init__(
        self,
        *,
        input_tokens: int | None,
        cached_input_tokens: int | None,
        output_tokens: int | None,
    ) -> None:
        self.input_tokens = input_tokens
        self.cached_input_tokens = cached_input_tokens
        self.output_tokens = output_tokens

    def invoke(self, **kwargs) -> AIProviderResult:
        del kwargs
        return AIProviderResult(
            output_text="ok",
            provider_request_id="provider-request",
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            cached_input_tokens=self.cached_input_tokens,
        )


def _runtime(db: Session, suffix: str):
    owner = User(email=f"cached-owner-{suffix}@example.com")
    member = User(email=f"cached-member-{suffix}@example.com")
    organization = Organization(name=f"Cached Cost {suffix}", slug=f"cached-cost-{suffix}")
    db.add_all([owner, member, organization])
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

    store = FakeSecretStore()
    provider = create_provider_configuration(
        db,
        secret_store=store,
        organization_id=organization.id,
        actor_user_id=owner.id,
        provider_key=f"cached-provider-{suffix}",
        display_name="Cached Provider",
        adapter_kind=AIProviderAdapterKind.OPENAI_CHAT_COMPLETIONS,
        api_url="https://ai.example.com/v1/chat/completions",
        credentials={"api_key": "secret"},
    )
    model = create_model_configuration(
        db,
        organization_id=organization.id,
        actor_user_id=owner.id,
        provider_configuration_id=provider.id,
        model_key=f"cached-model-{suffix}",
        display_name="Cached Model",
        enabled=True,
        max_output_tokens=128,
    )
    return organization, owner, member, store, provider, model


def _rate(
    db: Session,
    *,
    organization,
    owner,
    provider,
    model,
    cached_rate: int | None,
) -> None:
    create_model_rate_card(
        db,
        organization_id=organization.id,
        actor_user_id=owner.id,
        provider_configuration_id=provider.id,
        model_configuration_id=model.id,
        input_nano_usd_per_token=2_000,
        cached_input_nano_usd_per_token=cached_rate,
        output_nano_usd_per_token=12_000,
        source_label="test pricing",
        effective_from=datetime.now(UTC) - timedelta(days=1),
        effective_to=None,
    )


def _invoke(db: Session, *, runtime, adapter: CachedAdapter):
    organization, _, member, store, provider, model = runtime
    return invoke_ai(
        db,
        secret_store=store,
        organization_id=organization.id,
        user_id=member.id,
        role=MembershipRole.MEMBER,
        provider_configuration_id=provider.id,
        model_configuration_id=model.id,
        input_text="question",
        system_text=None,
        max_output_tokens=64,
        attribution_node_id=None,
        adapter=adapter,
        timeout_seconds=1,
    )


def test_openai_adapter_captures_cached_prompt_tokens(monkeypatch) -> None:
    def fake_open(request, timeout):
        del request, timeout
        return FakeResponse(
            {
                "id": "req-cache",
                "choices": [{"message": {"content": "answer"}}],
                "usage": {
                    "prompt_tokens": 120,
                    "completion_tokens": 15,
                    "prompt_tokens_details": {"cached_tokens": 80},
                },
            }
        )

    monkeypatch.setattr("app.ai_provider_adapter._open_provider_request", fake_open)
    result = OpenAIChatCompletionsAdapter().invoke(
        api_url="https://api.openai.com/v1/chat/completions",
        api_key="secret",
        model="gpt-5.6-terra",
        input_text="hello",
        system_text=None,
        max_output_tokens=64,
        timeout_seconds=1,
    )
    assert result.input_tokens == 120
    assert result.cached_input_tokens == 80
    assert result.output_tokens == 15


def test_cached_input_uses_distinct_rate_and_is_auditable(db_session: Session) -> None:
    runtime = _runtime(db_session, "exact")
    organization, owner, _, _, provider, model = runtime
    _rate(
        db_session,
        organization=organization,
        owner=owner,
        provider=provider,
        model=model,
        cached_rate=200,
    )
    result = _invoke(
        db_session,
        runtime=runtime,
        adapter=CachedAdapter(
            input_tokens=1_000,
            cached_input_tokens=400,
            output_tokens=100,
        ),
    )

    request = db_session.get(AIRequestRecord, result.request_id)
    assert request is not None
    assert request.cached_input_tokens == 400
    cost = db_session.scalar(
        select(AIUsageCostRecord).where(AIUsageCostRecord.request_id == result.request_id)
    )
    assert cost is not None
    assert cost.status == AICostResolutionStatus.CALCULATED
    assert cost.input_cost_nano_usd == 1_280_000
    assert cost.output_cost_nano_usd == 1_200_000
    assert cost.total_cost_nano_usd == 2_480_000

    now = datetime.now(UTC)
    rows = usage_summary(
        db_session,
        organization_id=organization.id,
        start=now - timedelta(days=1),
        end=now + timedelta(days=1),
        dimension="model",
    )
    assert len(rows) == 1
    assert rows[0].input_tokens == 1_000
    assert rows[0].cached_input_tokens == 400


def test_distinct_cached_rate_fails_closed_when_usage_detail_missing(
    db_session: Session,
) -> None:
    runtime = _runtime(db_session, "missing")
    organization, owner, _, _, provider, model = runtime
    _rate(
        db_session,
        organization=organization,
        owner=owner,
        provider=provider,
        model=model,
        cached_rate=200,
    )
    result = _invoke(
        db_session,
        runtime=runtime,
        adapter=CachedAdapter(
            input_tokens=100,
            cached_input_tokens=None,
            output_tokens=10,
        ),
    )
    cost = db_session.scalar(
        select(AIUsageCostRecord).where(AIUsageCostRecord.request_id == result.request_id)
    )
    assert cost is not None
    assert cost.status == AICostResolutionStatus.UNKNOWN
    assert cost.unknown_reason == "cached_token_usage_unavailable"


def test_invalid_cached_count_fails_closed_instead_of_undercharging(
    db_session: Session,
) -> None:
    runtime = _runtime(db_session, "invalid")
    organization, owner, _, _, provider, model = runtime
    _rate(
        db_session,
        organization=organization,
        owner=owner,
        provider=provider,
        model=model,
        cached_rate=200,
    )
    result = _invoke(
        db_session,
        runtime=runtime,
        adapter=CachedAdapter(
            input_tokens=100,
            cached_input_tokens=101,
            output_tokens=10,
        ),
    )
    cost = db_session.scalar(
        select(AIUsageCostRecord).where(AIUsageCostRecord.request_id == result.request_id)
    )
    assert cost is not None
    assert cost.status == AICostResolutionStatus.UNKNOWN
    assert cost.unknown_reason == "invalid_token_usage"


def test_single_tier_provider_remains_backward_compatible(db_session: Session) -> None:
    runtime = _runtime(db_session, "single")
    organization, owner, _, _, provider, model = runtime
    _rate(
        db_session,
        organization=organization,
        owner=owner,
        provider=provider,
        model=model,
        cached_rate=None,
    )
    result = _invoke(
        db_session,
        runtime=runtime,
        adapter=CachedAdapter(
            input_tokens=100,
            cached_input_tokens=None,
            output_tokens=10,
        ),
    )
    cost = db_session.scalar(
        select(AIUsageCostRecord).where(AIUsageCostRecord.request_id == result.request_id)
    )
    assert cost is not None
    assert cost.status == AICostResolutionStatus.CALCULATED
    assert cost.input_cost_nano_usd == 200_000
    assert cost.output_cost_nano_usd == 120_000
    assert cost.total_cost_nano_usd == 320_000

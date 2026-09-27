import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai_gateway_models import AIProviderAdapterKind, AIRequestRecord
from app.ai_provider_adapter import AIGatewayError, AIProviderResult
from app.ai_provider_registry import (
    create_model_configuration,
    create_provider_configuration,
    invoke_ai,
)
from app.ai_usage import (
    AIUsageError,
    budget_snapshot,
    create_budget_policy,
    create_model_rate_card,
    materialize_request_cost,
    usage_summary,
)
from app.ai_usage_models import (
    AIBudgetAlert,
    AIBudgetScopeType,
    AICostResolutionStatus,
    AIUsageCostRecord,
)
from app.auth import get_current_user
from app.database import get_db
from app.main import app
from app.models import Membership, MembershipRole, Organization, User
from app.secrets import SecretStoreError


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


class CountingAdapter:
    def __init__(
        self,
        *,
        input_tokens: int | None = 60,
        output_tokens: int | None = 0,
    ) -> None:
        self.calls = 0
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens

    def invoke(self, **kwargs) -> AIProviderResult:
        del kwargs
        self.calls += 1
        return AIProviderResult(
            output_text="ok",
            provider_request_id=f"provider-{self.calls}",
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
        )


def _seed(db: Session, suffix: str):
    owner = User(email=f"usage-owner-{suffix}@example.com")
    member = User(email=f"usage-member-{suffix}@example.com")
    executive = User(email=f"usage-exec-{suffix}@example.com")
    organization = Organization(name=f"Usage Org {suffix}", slug=f"usage-{suffix}")
    db.add_all([owner, member, executive, organization])
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
                user_id=executive.id,
                role=MembershipRole.EXECUTIVE,
            ),
        ]
    )
    db.commit()
    return organization, owner, member, executive


def _provider_model(
    db: Session,
    *,
    store: FakeSecretStore,
    organization: Organization,
    owner: User,
    suffix: str,
):
    provider = create_provider_configuration(
        db,
        secret_store=store,
        organization_id=organization.id,
        actor_user_id=owner.id,
        provider_key=f"provider-{suffix}",
        display_name="Provider",
        adapter_kind=AIProviderAdapterKind.OPENAI_CHAT_COMPLETIONS,
        api_url="https://ai.example.com/v1/chat/completions",
        credentials={"api_key": "secret"},
    )
    model = create_model_configuration(
        db,
        organization_id=organization.id,
        actor_user_id=owner.id,
        provider_configuration_id=provider.id,
        model_key=f"model-{suffix}",
        display_name="Model",
        enabled=True,
        max_output_tokens=100,
    )
    return provider, model


def _rate(
    db: Session,
    *,
    organization: Organization,
    owner: User,
    provider_id: uuid.UUID,
    model_id: uuid.UUID,
    input_rate: int,
    output_rate: int,
):
    return create_model_rate_card(
        db,
        organization_id=organization.id,
        actor_user_id=owner.id,
        provider_configuration_id=provider_id,
        model_configuration_id=model_id,
        input_nano_usd_per_token=input_rate,
        output_nano_usd_per_token=output_rate,
        source_label="provider pricing 2026-09",
        effective_from=datetime.now(UTC) - timedelta(days=1),
        effective_to=None,
    )


def _invoke(
    db: Session,
    *,
    store: FakeSecretStore,
    organization: Organization,
    member: User,
    provider_id: uuid.UUID,
    model_id: uuid.UUID,
    adapter: CountingAdapter,
):
    return invoke_ai(
        db,
        secret_store=store,
        organization_id=organization.id,
        user_id=member.id,
        role=MembershipRole.MEMBER,
        provider_configuration_id=provider_id,
        model_configuration_id=model_id,
        input_text="summarise status",
        system_text=None,
        max_output_tokens=None,
        attribution_node_id=None,
        adapter=adapter,
        timeout_seconds=1,
    )


def test_cost_is_exact_integer_nano_usd_and_idempotent(db_session: Session) -> None:
    organization, owner, member, _ = _seed(db_session, "exact")
    store = FakeSecretStore()
    provider, model = _provider_model(
        db_session,
        store=store,
        organization=organization,
        owner=owner,
        suffix="exact",
    )
    _rate(
        db_session,
        organization=organization,
        owner=owner,
        provider_id=provider.id,
        model_id=model.id,
        input_rate=150,
        output_rate=600,
    )
    adapter = CountingAdapter(input_tokens=1000, output_tokens=100)
    result = _invoke(
        db_session,
        store=store,
        organization=organization,
        member=member,
        provider_id=provider.id,
        model_id=model.id,
        adapter=adapter,
    )

    request = db_session.get(AIRequestRecord, result.request_id)
    assert request is not None
    cost = db_session.scalar(
        select(AIUsageCostRecord).where(AIUsageCostRecord.request_id == request.id)
    )
    assert cost is not None
    assert cost.status == AICostResolutionStatus.CALCULATED
    assert cost.input_cost_nano_usd == 150_000
    assert cost.output_cost_nano_usd == 60_000
    assert cost.total_cost_nano_usd == 210_000
    assert materialize_request_cost(db_session, request=request).id == cost.id


def test_missing_tokens_and_missing_rate_are_explicit_unknowns(db_session: Session) -> None:
    organization, owner, member, _ = _seed(db_session, "unknown")
    store = FakeSecretStore()
    provider, model = _provider_model(
        db_session,
        store=store,
        organization=organization,
        owner=owner,
        suffix="unknown",
    )
    _rate(
        db_session,
        organization=organization,
        owner=owner,
        provider_id=provider.id,
        model_id=model.id,
        input_rate=150,
        output_rate=600,
    )
    tokenless = CountingAdapter(input_tokens=None, output_tokens=None)
    first = _invoke(
        db_session,
        store=store,
        organization=organization,
        member=member,
        provider_id=provider.id,
        model_id=model.id,
        adapter=tokenless,
    )
    first_cost = db_session.scalar(
        select(AIUsageCostRecord).where(AIUsageCostRecord.request_id == first.request_id)
    )
    assert first_cost is not None
    assert first_cost.status == AICostResolutionStatus.UNKNOWN
    assert first_cost.unknown_reason == "token_usage_unavailable"
    assert first_cost.total_cost_nano_usd is None

    provider_two, model_two = _provider_model(
        db_session,
        store=store,
        organization=organization,
        owner=owner,
        suffix="no-rate",
    )
    second = _invoke(
        db_session,
        store=store,
        organization=organization,
        member=member,
        provider_id=provider_two.id,
        model_id=model_two.id,
        adapter=CountingAdapter(),
    )
    second_cost = db_session.scalar(
        select(AIUsageCostRecord).where(AIUsageCostRecord.request_id == second.request_id)
    )
    assert second_cost is not None
    assert second_cost.status == AICostResolutionStatus.UNKNOWN
    assert second_cost.unknown_reason == "rate_card_unavailable"
    assert second_cost.total_cost_nano_usd is None


def test_overlapping_rate_windows_are_rejected(db_session: Session) -> None:
    organization, owner, _, _ = _seed(db_session, "overlap")
    store = FakeSecretStore()
    provider, model = _provider_model(
        db_session,
        store=store,
        organization=organization,
        owner=owner,
        suffix="overlap",
    )
    start = datetime.now(UTC) - timedelta(days=10)
    end = datetime.now(UTC) + timedelta(days=10)
    create_model_rate_card(
        db_session,
        organization_id=organization.id,
        actor_user_id=owner.id,
        provider_configuration_id=provider.id,
        model_configuration_id=model.id,
        input_nano_usd_per_token=100,
        output_nano_usd_per_token=200,
        source_label="rate one",
        effective_from=start,
        effective_to=end,
    )
    with pytest.raises(AIUsageError, match="overlaps"):
        create_model_rate_card(
            db_session,
            organization_id=organization.id,
            actor_user_id=owner.id,
            provider_configuration_id=provider.id,
            model_configuration_id=model.id,
            input_nano_usd_per_token=110,
            output_nano_usd_per_token=210,
            source_label="rate two",
            effective_from=datetime.now(UTC),
            effective_to=None,
        )


def test_cross_tenant_budget_target_is_rejected(db_session: Session) -> None:
    organization, owner, _, _ = _seed(db_session, "budget-a")
    other, other_owner, _, _ = _seed(db_session, "budget-b")
    store = FakeSecretStore()
    other_provider, _ = _provider_model(
        db_session,
        store=store,
        organization=other,
        owner=other_owner,
        suffix="other",
    )
    with pytest.raises(AIUsageError, match="not found"):
        create_budget_policy(
            db_session,
            organization_id=organization.id,
            actor_user_id=owner.id,
            scope_type=AIBudgetScopeType.PROVIDER,
            scope_target_id=other_provider.id,
            limit_nano_usd=1_000,
            warning_threshold_percent=80,
            hard_limit=True,
            enabled=True,
        )


def test_threshold_alerts_deduplicate_and_hard_budget_blocks_before_provider(
    db_session: Session,
) -> None:
    organization, owner, member, _ = _seed(db_session, "budget")
    store = FakeSecretStore()
    provider, model = _provider_model(
        db_session,
        store=store,
        organization=organization,
        owner=owner,
        suffix="budget",
    )
    _rate(
        db_session,
        organization=organization,
        owner=owner,
        provider_id=provider.id,
        model_id=model.id,
        input_rate=1,
        output_rate=0,
    )
    policy = create_budget_policy(
        db_session,
        organization_id=organization.id,
        actor_user_id=owner.id,
        scope_type=AIBudgetScopeType.ORGANIZATION,
        scope_target_id=None,
        limit_nano_usd=100,
        warning_threshold_percent=50,
        hard_limit=True,
        enabled=True,
    )
    adapter = CountingAdapter(input_tokens=60, output_tokens=0)
    _invoke(
        db_session,
        store=store,
        organization=organization,
        member=member,
        provider_id=provider.id,
        model_id=model.id,
        adapter=adapter,
    )
    first_snapshot = budget_snapshot(db_session, policy=policy, at=datetime.now(UTC))
    assert first_snapshot.known_spend_nano_usd == 60
    assert first_snapshot.exhausted is False

    _invoke(
        db_session,
        store=store,
        organization=organization,
        member=member,
        provider_id=provider.id,
        model_id=model.id,
        adapter=adapter,
    )
    second_snapshot = budget_snapshot(db_session, policy=policy, at=datetime.now(UTC))
    assert second_snapshot.known_spend_nano_usd == 120
    assert second_snapshot.exhausted is True
    alerts = list(
        db_session.scalars(
            select(AIBudgetAlert).where(AIBudgetAlert.budget_policy_id == policy.id)
        )
    )
    assert {alert.threshold_percent for alert in alerts} == {50, 100}
    assert len(alerts) == 2

    with pytest.raises(AIGatewayError, match="budget exhausted"):
        _invoke(
            db_session,
            store=store,
            organization=organization,
            member=member,
            provider_id=provider.id,
            model_id=model.id,
            adapter=adapter,
        )
    assert adapter.calls == 2


def test_unknown_cost_keeps_budget_enforcement_incomplete_not_zero(
    db_session: Session,
) -> None:
    organization, owner, member, _ = _seed(db_session, "unknown-budget")
    store = FakeSecretStore()
    provider, model = _provider_model(
        db_session,
        store=store,
        organization=organization,
        owner=owner,
        suffix="unknown-budget",
    )
    policy = create_budget_policy(
        db_session,
        organization_id=organization.id,
        actor_user_id=owner.id,
        scope_type=AIBudgetScopeType.ORGANIZATION,
        scope_target_id=None,
        limit_nano_usd=1_000,
        warning_threshold_percent=80,
        hard_limit=True,
        enabled=True,
    )
    _invoke(
        db_session,
        store=store,
        organization=organization,
        member=member,
        provider_id=provider.id,
        model_id=model.id,
        adapter=CountingAdapter(input_tokens=None, output_tokens=None),
    )
    snapshot = budget_snapshot(db_session, policy=policy, at=datetime.now(UTC))
    assert snapshot.known_spend_nano_usd == 0
    assert snapshot.unknown_cost_requests == 1
    assert snapshot.enforcement_complete is False
    assert snapshot.exhausted is False


def test_usage_summary_preserves_unknown_attribution_group(db_session: Session) -> None:
    organization, owner, member, _ = _seed(db_session, "summary")
    store = FakeSecretStore()
    provider, model = _provider_model(
        db_session,
        store=store,
        organization=organization,
        owner=owner,
        suffix="summary",
    )
    _rate(
        db_session,
        organization=organization,
        owner=owner,
        provider_id=provider.id,
        model_id=model.id,
        input_rate=2,
        output_rate=0,
    )
    _invoke(
        db_session,
        store=store,
        organization=organization,
        member=member,
        provider_id=provider.id,
        model_id=model.id,
        adapter=CountingAdapter(input_tokens=10, output_tokens=0),
    )
    now = datetime.now(UTC)
    provider_rows = usage_summary(
        db_session,
        organization_id=organization.id,
        start=now - timedelta(days=1),
        end=now + timedelta(days=1),
        dimension="provider",
    )
    assert len(provider_rows) == 1
    assert provider_rows[0].request_count == 1
    assert provider_rows[0].total_cost_nano_usd == 20

    attribution_rows = usage_summary(
        db_session,
        organization_id=organization.id,
        start=now - timedelta(days=1),
        end=now + timedelta(days=1),
        dimension="work_graph_node",
    )
    assert len(attribution_rows) == 1
    assert attribution_rows[0].dimension_id is None
    assert attribution_rows[0].dimension_label is None


def test_member_cannot_read_org_usage_but_executive_can(
    db_session: Session,
    client,
) -> None:
    organization, _, member, executive = _seed(db_session, "permission")

    app.dependency_overrides[get_current_user] = lambda: member
    app.dependency_overrides[get_db] = lambda: db_session
    denied = client.get(f"/api/v1/organizations/{organization.id}/ai/usage/summary")
    assert denied.status_code == 403

    app.dependency_overrides[get_current_user] = lambda: executive
    allowed = client.get(f"/api/v1/organizations/{organization.id}/ai/usage/summary")
    assert allowed.status_code == 200
    assert allowed.json()["rows"] == []

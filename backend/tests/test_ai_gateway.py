import logging
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai_gateway import (
    AIGatewayError,
    AIInvocationError,
    AIProviderCallError,
    AIProviderResult,
    create_model_configuration,
    create_provider_configuration,
    invoke_ai,
    revoke_provider_configuration,
    set_model_enabled,
    set_provider_enabled,
    validate_provider_api_url,
)
from app.ai_gateway_models import (
    AIProviderAdapterKind,
    AIProviderStatus,
    AIRequestRecord,
    AIRequestStatus,
)
from app.config import Settings
from app.models import Membership, MembershipRole, Organization, User
from app.permissions import Permission, role_has_permission
from app.secrets import SecretStoreError
from app.work_graph import create_manual_node
from app.work_graph_models import WorkGraphNodeType


class FakeSecretStore:
    def __init__(self) -> None:
        self.values: dict[str, dict[str, str]] = {}
        self.deleted: list[str] = []
        self.fail_delete = False
        self.store_calls = 0

    def store_ai_provider_secret(
        self,
        *,
        organization_id: uuid.UUID,
        provider_configuration_id: uuid.UUID,
        provider: str,
        credentials: dict[str, str],
    ) -> str:
        self.store_calls += 1
        reference = (
            f"arn:test:ai:{organization_id}:{provider}:{provider_configuration_id}"
        )
        self.values[reference] = dict(credentials)
        return reference

    def load_connection_secret(self, reference: str) -> dict[str, str]:
        value = self.values.get(reference)
        if value is None:
            raise SecretStoreError("missing")
        return dict(value)

    def schedule_delete(self, reference: str) -> None:
        if self.fail_delete:
            raise SecretStoreError("delete failed")
        self.deleted.append(reference)
        self.values.pop(reference, None)


class FakeAdapter:
    def __init__(self) -> None:
        self.calls = 0
        self.last_api_key: str | None = None
        self.last_input: str | None = None

    def invoke(
        self,
        *,
        api_url: str,
        api_key: str,
        model: str,
        input_text: str,
        system_text: str | None,
        max_output_tokens: int | None,
        timeout_seconds: float,
    ) -> AIProviderResult:
        del api_url, model, system_text, max_output_tokens, timeout_seconds
        self.calls += 1
        self.last_api_key = api_key
        self.last_input = input_text
        return AIProviderResult(
            output_text="safe answer",
            provider_request_id="req-provider-1",
            input_tokens=17,
            output_tokens=4,
        )


class FailingAdapter:
    def __init__(self, code: str = "provider_timeout") -> None:
        self.code = code
        self.calls = 0

    def invoke(self, **kwargs) -> AIProviderResult:
        del kwargs
        self.calls += 1
        raise AIProviderCallError(self.code)


def _seed(db: Session, suffix: str):
    owner = User(email=f"ai-owner-{suffix}@example.com")
    member = User(email=f"ai-member-{suffix}@example.com")
    organization = Organization(name=f"AI Org {suffix}", slug=f"ai-{suffix}")
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
    return organization, owner, member


def _provider_and_model(
    db: Session,
    *,
    store: FakeSecretStore,
    organization: Organization,
    owner: User,
):
    provider = create_provider_configuration(
        db,
        secret_store=store,
        organization_id=organization.id,
        actor_user_id=owner.id,
        provider_key="acme-ai",
        display_name="Acme AI",
        adapter_kind=AIProviderAdapterKind.OPENAI_CHAT_COMPLETIONS,
        api_url="https://ai.example.com/v1/chat/completions",
        credentials={"api_key": "top-secret-key"},
    )
    model = create_model_configuration(
        db,
        organization_id=organization.id,
        actor_user_id=owner.id,
        provider_configuration_id=provider.id,
        model_key="model-v1",
        display_name="Model V1",
        enabled=True,
        max_output_tokens=500,
    )
    return provider, model


def test_ai_management_permission_is_admin_only() -> None:
    assert role_has_permission(MembershipRole.OWNER, Permission.AI_MANAGE)
    assert role_has_permission(MembershipRole.ADMIN, Permission.AI_MANAGE)
    assert not role_has_permission(MembershipRole.EXECUTIVE, Permission.AI_MANAGE)
    assert not role_has_permission(MembershipRole.MANAGER, Permission.AI_MANAGE)
    assert not role_has_permission(MembershipRole.MEMBER, Permission.AI_MANAGE)
    assert role_has_permission(MembershipRole.MEMBER, Permission.AI_USE)
    assert not role_has_permission(MembershipRole.GUEST, Permission.AI_USE)


def test_provider_persists_secret_reference_not_plaintext(db_session: Session) -> None:
    organization, owner, _ = _seed(db_session, "secret")
    store = FakeSecretStore()
    provider, _ = _provider_and_model(
        db_session,
        store=store,
        organization=organization,
        owner=owner,
    )

    assert provider.secret_ref is not None
    assert provider.secret_ref in store.values
    assert store.values[provider.secret_ref]["api_key"] == "top-secret-key"
    assert "top-secret-key" not in provider.api_url
    assert "top-secret-key" not in provider.display_name
    assert not hasattr(provider, "api_key")


def test_successful_invoke_records_metadata_without_prompt_or_completion(
    db_session: Session,
    caplog,
) -> None:
    organization, owner, member = _seed(db_session, "success")
    store = FakeSecretStore()
    provider, model = _provider_and_model(
        db_session,
        store=store,
        organization=organization,
        owner=owner,
    )
    adapter = FakeAdapter()
    sensitive_prompt = "customer-secret-context-123"

    with caplog.at_level(logging.DEBUG):
        result = invoke_ai(
            db_session,
            secret_store=store,
            organization_id=organization.id,
            user_id=member.id,
            role=MembershipRole.MEMBER,
            provider_configuration_id=provider.id,
            model_configuration_id=model.id,
            input_text=sensitive_prompt,
            system_text="answer briefly",
            max_output_tokens=None,
            attribution_node_id=None,
            adapter=adapter,
            timeout_seconds=1,
        )

    record = db_session.get(AIRequestRecord, result.request_id)
    assert record is not None
    assert record.status == AIRequestStatus.SUCCEEDED
    assert record.organization_id == organization.id
    assert record.user_id == member.id
    assert record.provider_key == "acme-ai"
    assert record.model_key == "model-v1"
    assert record.input_tokens == 17
    assert record.output_tokens == 4
    assert record.output_char_count == len("safe answer")
    assert record.provider_request_id == "req-provider-1"
    assert not hasattr(record, "input_text")
    assert not hasattr(record, "output_text")
    assert adapter.last_api_key == "top-secret-key"
    assert adapter.last_input == sensitive_prompt
    assert all(sensitive_prompt not in item.message for item in caplog.records)
    assert all("top-secret-key" not in item.message for item in caplog.records)


def test_provider_failure_records_safe_error_without_response_body(
    db_session: Session,
) -> None:
    organization, owner, member = _seed(db_session, "failure")
    store = FakeSecretStore()
    provider, model = _provider_and_model(
        db_session,
        store=store,
        organization=organization,
        owner=owner,
    )
    adapter = FailingAdapter("provider_timeout")

    with pytest.raises(AIInvocationError) as failed:
        invoke_ai(
            db_session,
            secret_store=store,
            organization_id=organization.id,
            user_id=member.id,
            role=MembershipRole.MEMBER,
            provider_configuration_id=provider.id,
            model_configuration_id=model.id,
            input_text="hello",
            system_text=None,
            max_output_tokens=None,
            attribution_node_id=None,
            adapter=adapter,
            timeout_seconds=1,
        )
    assert failed.value.code == "provider_timeout"
    record = db_session.get(AIRequestRecord, failed.value.request_id)
    assert record is not None
    assert record.status == AIRequestStatus.FAILED
    assert record.error_code == "provider_timeout"
    assert record.completed_at is not None
    assert adapter.calls == 1


def test_disabled_provider_or_model_fails_before_external_call(
    db_session: Session,
) -> None:
    organization, owner, member = _seed(db_session, "disabled")
    store = FakeSecretStore()
    provider, model = _provider_and_model(
        db_session,
        store=store,
        organization=organization,
        owner=owner,
    )
    adapter = FakeAdapter()
    set_provider_enabled(
        db_session,
        organization_id=organization.id,
        provider_configuration_id=provider.id,
        enabled=False,
    )
    with pytest.raises(AIGatewayError, match="disabled"):
        invoke_ai(
            db_session,
            secret_store=store,
            organization_id=organization.id,
            user_id=member.id,
            role=MembershipRole.MEMBER,
            provider_configuration_id=provider.id,
            model_configuration_id=model.id,
            input_text="hello",
            system_text=None,
            max_output_tokens=None,
            attribution_node_id=None,
            adapter=adapter,
        )
    assert adapter.calls == 0

    set_provider_enabled(
        db_session,
        organization_id=organization.id,
        provider_configuration_id=provider.id,
        enabled=True,
    )
    set_model_enabled(
        db_session,
        organization_id=organization.id,
        model_configuration_id=model.id,
        enabled=False,
    )
    with pytest.raises(AIGatewayError, match="disabled"):
        invoke_ai(
            db_session,
            secret_store=store,
            organization_id=organization.id,
            user_id=member.id,
            role=MembershipRole.MEMBER,
            provider_configuration_id=provider.id,
            model_configuration_id=model.id,
            input_text="hello",
            system_text=None,
            max_output_tokens=None,
            attribution_node_id=None,
            adapter=adapter,
        )
    assert adapter.calls == 0


def test_cross_tenant_provider_cannot_be_invoked(db_session: Session) -> None:
    organization, owner, _ = _seed(db_session, "tenant-a")
    other_organization, _, other_member = _seed(db_session, "tenant-b")
    store = FakeSecretStore()
    provider, model = _provider_and_model(
        db_session,
        store=store,
        organization=organization,
        owner=owner,
    )
    adapter = FakeAdapter()

    with pytest.raises(AIGatewayError, match="not found"):
        invoke_ai(
            db_session,
            secret_store=store,
            organization_id=other_organization.id,
            user_id=other_member.id,
            role=MembershipRole.MEMBER,
            provider_configuration_id=provider.id,
            model_configuration_id=model.id,
            input_text="hello",
            system_text=None,
            max_output_tokens=None,
            attribution_node_id=None,
            adapter=adapter,
        )
    assert adapter.calls == 0
    assert db_session.scalar(select(AIRequestRecord.id)) is None


def test_attribution_must_be_visible_same_org_project_or_work_item(
    db_session: Session,
) -> None:
    organization, owner, member = _seed(db_session, "attribution")
    other_organization, other_owner, _ = _seed(db_session, "attribution-other")
    store = FakeSecretStore()
    provider, model = _provider_and_model(
        db_session,
        store=store,
        organization=organization,
        owner=owner,
    )
    project = create_manual_node(
        db_session,
        organization_id=organization.id,
        node_type=WorkGraphNodeType.PROJECT,
        key="atlas",
        display_name="Atlas",
        actor_user_id=owner.id,
    )
    other_project = create_manual_node(
        db_session,
        organization_id=other_organization.id,
        node_type=WorkGraphNodeType.PROJECT,
        key="other",
        display_name="Other",
        actor_user_id=other_owner.id,
    )
    adapter = FakeAdapter()

    result = invoke_ai(
        db_session,
        secret_store=store,
        organization_id=organization.id,
        user_id=member.id,
        role=MembershipRole.MEMBER,
        provider_configuration_id=provider.id,
        model_configuration_id=model.id,
        input_text="status",
        system_text=None,
        max_output_tokens=None,
        attribution_node_id=project.id,
        adapter=adapter,
    )
    record = db_session.get(AIRequestRecord, result.request_id)
    assert record is not None
    assert record.attribution_node_id == project.id
    assert record.attribution_node_type == WorkGraphNodeType.PROJECT.value

    with pytest.raises(AIGatewayError, match="not found"):
        invoke_ai(
            db_session,
            secret_store=store,
            organization_id=organization.id,
            user_id=member.id,
            role=MembershipRole.MEMBER,
            provider_configuration_id=provider.id,
            model_configuration_id=model.id,
            input_text="status",
            system_text=None,
            max_output_tokens=None,
            attribution_node_id=other_project.id,
            adapter=adapter,
        )


def test_revoke_fails_closed_even_if_secret_deletion_fails(db_session: Session) -> None:
    organization, owner, member = _seed(db_session, "revoke")
    store = FakeSecretStore()
    provider, model = _provider_and_model(
        db_session,
        store=store,
        organization=organization,
        owner=owner,
    )
    store.fail_delete = True

    with pytest.raises(AIGatewayError, match="revocation is incomplete"):
        revoke_provider_configuration(
            db_session,
            secret_store=store,
            organization_id=organization.id,
            provider_configuration_id=provider.id,
        )
    db_session.refresh(provider)
    assert provider.status == AIProviderStatus.DISABLED

    adapter = FakeAdapter()
    with pytest.raises(AIGatewayError, match="disabled"):
        invoke_ai(
            db_session,
            secret_store=store,
            organization_id=organization.id,
            user_id=member.id,
            role=MembershipRole.MEMBER,
            provider_configuration_id=provider.id,
            model_configuration_id=model.id,
            input_text="hello",
            system_text=None,
            max_output_tokens=None,
            attribution_node_id=None,
            adapter=adapter,
        )
    assert adapter.calls == 0


def test_production_provider_url_requires_https_and_allowlisted_host() -> None:
    settings = Settings(
        environment="production",
        app_secret="production-secret",
        workos_client_id="client_123",
        ai_provider_allowed_hosts="api.approved.example",
    )
    assert (
        validate_provider_api_url(
            "https://api.approved.example/v1/chat/completions",
            settings=settings,
        )
        == "https://api.approved.example/v1/chat/completions"
    )
    with pytest.raises(AIGatewayError, match="HTTPS"):
        validate_provider_api_url(
            "http://api.approved.example/v1/chat/completions",
            settings=settings,
        )
    with pytest.raises(AIGatewayError, match="not approved"):
        validate_provider_api_url(
            "https://169.254.169.254/latest/meta-data",
            settings=settings,
        )

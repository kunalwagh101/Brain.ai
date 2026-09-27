import hashlib
import json
import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai_gateway import (
    AIProviderResult,
    create_model_configuration,
    create_provider_configuration,
)
from app.ai_gateway_models import AIProviderAdapterKind, AIRequestRecord
from app.ask_brain import AskBrainError, ask_company_question
from app.auth import get_current_user
from app.main import app
from app.models import (
    CanonicalEvent,
    IntegrationConnection,
    IntegrationStatus,
    Membership,
    MembershipRole,
    Organization,
    RawEvent,
    User,
)
from app.search import SearchMode, project_search_document
from app.secrets import SecretStoreError, get_secret_store


class FakeSecretStore:
    def __init__(self) -> None:
        self.values: dict[str, dict[str, str]] = {}
        self.load_calls = 0

    def store_ai_provider_secret(
        self,
        *,
        organization_id: uuid.UUID,
        provider_configuration_id: uuid.UUID,
        provider: str,
        credentials: dict[str, str],
    ) -> str:
        reference = (
            f"arn:test:ask:{organization_id}:{provider}:{provider_configuration_id}"
        )
        self.values[reference] = dict(credentials)
        return reference

    def load_connection_secret(self, reference: str) -> dict[str, str]:
        self.load_calls += 1
        try:
            return dict(self.values[reference])
        except KeyError as exc:
            raise SecretStoreError("missing") from exc

    def schedule_delete(self, reference: str) -> None:
        self.values.pop(reference, None)


class JSONAdapter:
    def __init__(self, output: dict[str, object]) -> None:
        self.output = output
        self.calls = 0
        self.last_input: str | None = None
        self.last_system: str | None = None

    def invoke(self, **kwargs) -> AIProviderResult:
        self.calls += 1
        self.last_input = kwargs["input_text"]
        self.last_system = kwargs["system_text"]
        return AIProviderResult(
            output_text=json.dumps(self.output),
            provider_request_id="ask-provider-1",
            input_tokens=50,
            output_tokens=20,
        )


def _seed_org(db: Session, suffix: str) -> tuple[Organization, User, User]:
    owner = User(email=f"ask-owner-{suffix}@example.com")
    member = User(email=f"ask-member-{suffix}@example.com")
    organization = Organization(name=f"Ask {suffix}", slug=f"ask-{suffix}")
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
        provider_key="ask-provider",
        display_name="Ask Provider",
        adapter_kind=AIProviderAdapterKind.OPENAI_CHAT_COMPLETIONS,
        api_url="https://ai.example.com/v1/chat/completions",
        credentials={"api_key": "ask-secret"},
    )
    model = create_model_configuration(
        db,
        organization_id=organization.id,
        actor_user_id=owner.id,
        provider_configuration_id=provider.id,
        model_key="ask-model",
        display_name="Ask Model",
        enabled=True,
        max_output_tokens=500,
    )
    return provider, model


def _add_github_evidence(
    db: Session,
    *,
    organization: Organization,
    owner: User,
    object_id: str,
    text: str,
) -> IntegrationConnection:
    connection = IntegrationConnection(
        organization_id=organization.id,
        provider="github",
        external_account_id=f"ask-{object_id}",
        display_name=f"Ask {object_id}",
        scopes=[],
        provider_metadata={},
        created_by_user_id=owner.id,
    )
    db.add(connection)
    db.flush()

    payload = json.dumps(
        {
            "action": "opened",
            "repository": {"id": object_id, "full_name": "brain/ask"},
            "pull_request": {
                "id": object_id,
                "title": text,
                "body": text,
            },
        }
    ).encode()
    raw = RawEvent(
        organization_id=organization.id,
        integration_connection_id=connection.id,
        provider="github",
        source_event_id=f"ask-source-{object_id}",
        source_event_type="pull_request",
        delivery_kind="webhook",
        source_timestamp=datetime.now(UTC),
        content_type="application/json",
        payload_sha256=hashlib.sha256(payload).hexdigest(),
        raw_payload=payload,
        source_visibility="public_repository",
        source_acl=[],
    )
    db.add(raw)
    db.flush()
    event = CanonicalEvent(
        organization_id=organization.id,
        raw_event_id=raw.id,
        integration_connection_id=connection.id,
        schema_version=1,
        event_type="pull_request.opened",
        action="opened",
        actor_type="github_user",
        actor_external_id="ask-user",
        actor_display_name="Ask User",
        object_type="pull_request",
        object_external_id=object_id,
        object_display_name=text,
        source_provider="github",
        source_event_id=raw.source_event_id,
        source_event_type=raw.source_event_type,
        occurred_at=datetime.now(UTC),
        source_visibility="public_repository",
        source_acl=[],
        provenance={"raw_event_id": str(raw.id)},
        event_metadata={"repository_id": object_id, "repository": "brain/ask"},
    )
    db.add(event)
    db.commit()
    project_search_document(db, event)
    return connection


def _ask(
    db: Session,
    *,
    store: FakeSecretStore,
    organization: Organization,
    member: User,
    provider_id: uuid.UUID,
    model_id: uuid.UUID,
    adapter: JSONAdapter,
    question: str = "authentication",
):
    return ask_company_question(
        db,
        secret_store=store,
        organization_id=organization.id,
        user_id=member.id,
        role=MembershipRole.MEMBER,
        provider_configuration_id=provider_id,
        model_configuration_id=model_id,
        question=question,
        search_mode=SearchMode.KEYWORD,
        search_limit=8,
        embedding_client=None,
        embedding_model=None,
        attribution_node_id=None,
        max_output_tokens=500,
        adapter=adapter,
        timeout_seconds=1,
    )


def test_no_authorised_evidence_returns_no_answer_without_provider_call(
    db_session: Session,
) -> None:
    organization, _, member = _seed_org(db_session, "empty")
    store = FakeSecretStore()
    adapter = JSONAdapter(
        {
            "status": "answer",
            "claims": [{"text": "should not run", "citations": ["E1"]}],
            "uncertainty": None,
        }
    )

    result = ask_company_question(
        db_session,
        secret_store=store,
        organization_id=organization.id,
        user_id=member.id,
        role=MembershipRole.MEMBER,
        provider_configuration_id=uuid.uuid4(),
        model_configuration_id=uuid.uuid4(),
        question="missing evidence",
        search_mode=SearchMode.KEYWORD,
        search_limit=8,
        embedding_client=None,
        embedding_model=None,
        attribution_node_id=None,
        max_output_tokens=500,
        adapter=adapter,
    )

    assert result.status == "insufficient_evidence"
    assert result.answer is None
    assert result.ai_request_id is None
    assert result.citations == ()
    assert adapter.calls == 0
    assert store.load_calls == 0
    assert db_session.query(AIRequestRecord).count() == 0


def test_answer_uses_only_server_supplied_authorised_citations(
    db_session: Session,
) -> None:
    organization, owner, member = _seed_org(db_session, "grounded")
    _add_github_evidence(
        db_session,
        organization=organization,
        owner=owner,
        object_id="101",
        text="authentication middleware merged",
    )
    store = FakeSecretStore()
    provider, model = _provider_and_model(
        db_session,
        store=store,
        organization=organization,
        owner=owner,
    )
    adapter = JSONAdapter(
        {
            "status": "answer",
            "claims": [
                {
                    "text": "The authentication middleware was merged.",
                    "citations": ["E1"],
                }
            ],
            "uncertainty": None,
        }
    )

    result = _ask(
        db_session,
        store=store,
        organization=organization,
        member=member,
        provider_id=provider.id,
        model_id=model.id,
        adapter=adapter,
    )

    assert result.status == "answer"
    assert result.answer == "The authentication middleware was merged. [E1]"
    assert [citation.evidence_id for citation in result.citations] == ["E1"]
    assert result.citations[0].object_external_id == "101"
    assert adapter.calls == 1
    assert adapter.last_input is not None
    prompt = json.loads(adapter.last_input)
    assert prompt["question"] == "authentication"
    assert prompt["evidence"][0]["id"] == "E1"
    assert prompt["evidence"][0]["object_external_id"] == "101"
    assert adapter.last_system is not None
    assert "untrusted data" in adapter.last_system


@pytest.mark.parametrize(
    "output",
    [
        {
            "status": "answer",
            "claims": [{"text": "Unsupported.", "citations": ["E999"]}],
            "uncertainty": None,
        },
        {
            "status": "answer",
            "claims": [{"text": "Uncited.", "citations": []}],
            "uncertainty": None,
        },
        {"status": "answer", "claims": [], "uncertainty": None},
        {"status": "answer", "claims": "not-a-list", "uncertainty": None},
    ],
)
def test_invalid_or_uncited_model_output_fails_closed(
    db_session: Session,
    output: dict[str, object],
) -> None:
    organization, owner, member = _seed_org(db_session, uuid.uuid4().hex[:8])
    _add_github_evidence(
        db_session,
        organization=organization,
        owner=owner,
        object_id="102",
        text="authentication policy approved",
    )
    store = FakeSecretStore()
    provider, model = _provider_and_model(
        db_session,
        store=store,
        organization=organization,
        owner=owner,
    )
    adapter = JSONAdapter(output)

    with pytest.raises(AskBrainError, match="invalid_model_output"):
        _ask(
            db_session,
            store=store,
            organization=organization,
            member=member,
            provider_id=provider.id,
            model_id=model.id,
            adapter=adapter,
        )


def test_cross_tenant_evidence_never_enters_model_context(db_session: Session) -> None:
    organization, owner, member = _seed_org(db_session, "tenant-a")
    other_organization, other_owner, _ = _seed_org(db_session, "tenant-b")
    _add_github_evidence(
        db_session,
        organization=organization,
        owner=owner,
        object_id="201",
        text="authentication public fact",
    )
    _add_github_evidence(
        db_session,
        organization=other_organization,
        owner=other_owner,
        object_id="202",
        text="authentication SECRET_OTHER_TENANT",
    )
    store = FakeSecretStore()
    provider, model = _provider_and_model(
        db_session,
        store=store,
        organization=organization,
        owner=owner,
    )
    adapter = JSONAdapter(
        {
            "status": "answer",
            "claims": [{"text": "Public fact.", "citations": ["E1"]}],
            "uncertainty": None,
        }
    )

    _ask(
        db_session,
        store=store,
        organization=organization,
        member=member,
        provider_id=provider.id,
        model_id=model.id,
        adapter=adapter,
    )

    assert adapter.last_input is not None
    assert "SECRET_OTHER_TENANT" not in adapter.last_input
    assert "authentication public fact" in adapter.last_input


def test_revoked_source_is_not_sent_to_model(db_session: Session) -> None:
    organization, owner, member = _seed_org(db_session, "revoked")
    connection = _add_github_evidence(
        db_session,
        organization=organization,
        owner=owner,
        object_id="301",
        text="authentication revoked source",
    )
    connection.status = IntegrationStatus.REVOKED
    db_session.commit()
    store = FakeSecretStore()
    adapter = JSONAdapter(
        {
            "status": "answer",
            "claims": [{"text": "Must not run.", "citations": ["E1"]}],
            "uncertainty": None,
        }
    )

    result = ask_company_question(
        db_session,
        secret_store=store,
        organization_id=organization.id,
        user_id=member.id,
        role=MembershipRole.MEMBER,
        provider_configuration_id=uuid.uuid4(),
        model_configuration_id=uuid.uuid4(),
        question="authentication",
        search_mode=SearchMode.KEYWORD,
        search_limit=8,
        embedding_client=None,
        embedding_model=None,
        attribution_node_id=None,
        max_output_tokens=500,
        adapter=adapter,
    )

    assert result.status == "insufficient_evidence"
    assert adapter.calls == 0
    assert result.citations == ()


def test_model_can_explicitly_return_insufficient_evidence(db_session: Session) -> None:
    organization, owner, member = _seed_org(db_session, "model-no-answer")
    _add_github_evidence(
        db_session,
        organization=organization,
        owner=owner,
        object_id="401",
        text="authentication mentioned without decision status",
    )
    store = FakeSecretStore()
    provider, model = _provider_and_model(
        db_session,
        store=store,
        organization=organization,
        owner=owner,
    )
    adapter = JSONAdapter(
        {
            "status": "insufficient_evidence",
            "claims": [],
            "uncertainty": "The evidence does not establish whether it shipped.",
        }
    )

    result = _ask(
        db_session,
        store=store,
        organization=organization,
        member=member,
        provider_id=provider.id,
        model_id=model.id,
        adapter=adapter,
    )

    assert result.status == "insufficient_evidence"
    assert result.answer is None
    assert result.citations == ()
    assert "does not establish" in (result.uncertainty or "")


def test_guest_cannot_call_ask_brain(
    client: TestClient,
    db_session: Session,
) -> None:
    guest = User(email="ask-guest@example.com")
    organization = Organization(name="Ask Guest", slug="ask-guest")
    db_session.add_all([guest, organization])
    db_session.flush()
    db_session.add(
        Membership(
            organization_id=organization.id,
            user_id=guest.id,
            role=MembershipRole.GUEST,
        )
    )
    db_session.commit()
    store = FakeSecretStore()
    app.dependency_overrides[get_current_user] = lambda: guest
    app.dependency_overrides[get_secret_store] = lambda: store
    try:
        response = client.post(
            f"/api/v1/organizations/{organization.id}/ask-brain",
            json={
                "question": "What shipped?",
                "provider_configuration_id": str(uuid.uuid4()),
                "model_configuration_id": str(uuid.uuid4()),
            },
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_secret_store, None)

    assert response.status_code == 403
    assert store.load_calls == 0

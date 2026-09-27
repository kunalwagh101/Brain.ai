import uuid

from sqlalchemy.orm import Session

from app.ai_gateway_models import AIProviderAdapterKind
from app.ai_provider_adapter import AIProviderResult
from app.ai_provider_registry import create_model_configuration, create_provider_configuration
from app.ask_brain import ask_company_question
from app.evidence_ingestion import ingest_evidence
from app.evidence_models import EvidenceKind, EvidenceVisibility
from app.models import Membership, MembershipRole, Organization, User
from app.search import SearchMode
from app.secrets import SecretStoreError


class FakeSecretStore:
    def __init__(self) -> None:
        self.values: dict[str, dict[str, str]] = {}
        self.loads = 0

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
        self.loads += 1
        value = self.values.get(reference)
        if value is None:
            raise SecretStoreError("missing")
        return dict(value)

    def schedule_delete(self, reference: str) -> None:
        self.values.pop(reference, None)


class CitingAdapter:
    def __init__(self) -> None:
        self.calls = 0

    def invoke(self, **kwargs) -> AIProviderResult:
        del kwargs
        self.calls += 1
        return AIProviderResult(
            output_text=(
                '{"status":"answer","claims":[{"text":"Atlas ships Friday.",'
                '"citations":["E1"]}],"uncertainty":null}'
            ),
            provider_request_id="provider-request",
            input_tokens=100,
            cached_input_tokens=0,
            output_tokens=20,
        )


def _seed(db: Session):
    owner = User(email="ask-doc-owner@example.com")
    member = User(email="ask-doc-member@example.com")
    other = User(email="ask-doc-other@example.com")
    organization = Organization(name="Ask Docs", slug="ask-docs")
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
    return organization, owner, member, other


def _runtime(db: Session, *, organization, owner, store: FakeSecretStore):
    provider = create_provider_configuration(
        db,
        secret_store=store,
        organization_id=organization.id,
        actor_user_id=owner.id,
        provider_key="test-provider",
        display_name="Test provider",
        adapter_kind=AIProviderAdapterKind.OPENAI_CHAT_COMPLETIONS,
        api_url="https://ai.example.com/v1/chat/completions",
        credentials={"api_key": "secret"},
    )
    model = create_model_configuration(
        db,
        organization_id=organization.id,
        actor_user_id=owner.id,
        provider_configuration_id=provider.id,
        model_key="test-model",
        display_name="Test model",
        enabled=True,
        max_output_tokens=256,
    )
    return provider, model


def test_ask_brain_cites_authorized_generic_document(db_session: Session) -> None:
    organization, owner, member, _ = _seed(db_session)
    source = ingest_evidence(
        db_session,
        organization_id=organization.id,
        actor_user_id=member.id,
        kind=EvidenceKind.DOCUMENT,
        title="Atlas launch plan",
        filename="atlas.txt",
        media_type="text/plain",
        content=b"Project Atlas launch is approved for Friday after the guarded release check.",
        visibility=EvidenceVisibility.ORGANIZATION,
        occurred_at=None,
        idempotency_key="ask-doc-source",
    )
    store = FakeSecretStore()
    provider, model = _runtime(
        db_session,
        organization=organization,
        owner=owner,
        store=store,
    )
    adapter = CitingAdapter()

    result = ask_company_question(
        db_session,
        secret_store=store,
        organization_id=organization.id,
        user_id=member.id,
        role=MembershipRole.MEMBER,
        provider_configuration_id=provider.id,
        model_configuration_id=model.id,
        question="When does Atlas launch?",
        search_mode=SearchMode.KEYWORD,
        search_limit=8,
        embedding_client=None,
        embedding_model=None,
        attribution_node_id=None,
        max_output_tokens=128,
        adapter=adapter,
        timeout_seconds=1,
    )

    assert result.status == "answer"
    assert adapter.calls == 1
    assert result.citations
    citation = result.citations[0]
    assert citation.source_provider == "generic_upload"
    assert citation.object_external_id == str(source.id)
    assert citation.provenance["source_sha256"] == source.content_sha256


def test_ask_brain_does_not_call_provider_for_restricted_document_without_access(
    db_session: Session,
) -> None:
    organization, owner, member, other = _seed(db_session)
    ingest_evidence(
        db_session,
        organization_id=organization.id,
        actor_user_id=member.id,
        kind=EvidenceKind.TRANSCRIPT,
        title="Private Atlas review",
        filename="private-atlas.txt",
        media_type="text/plain",
        content=b"Atlas has a private blocker that must not be exposed to other members.",
        visibility=EvidenceVisibility.RESTRICTED,
        occurred_at=None,
        idempotency_key="ask-private-source",
    )
    store = FakeSecretStore()
    provider, model = _runtime(
        db_session,
        organization=organization,
        owner=owner,
        store=store,
    )
    adapter = CitingAdapter()

    result = ask_company_question(
        db_session,
        secret_store=store,
        organization_id=organization.id,
        user_id=other.id,
        role=MembershipRole.MEMBER,
        provider_configuration_id=provider.id,
        model_configuration_id=model.id,
        question="What is the Atlas blocker?",
        search_mode=SearchMode.KEYWORD,
        search_limit=8,
        embedding_client=None,
        embedding_model=None,
        attribution_node_id=None,
        max_output_tokens=128,
        adapter=adapter,
        timeout_seconds=1,
    )

    assert result.status == "insufficient_evidence"
    assert result.ai_request_id is None
    assert adapter.calls == 0
    assert store.loads == 0

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai_gateway_models import AIProviderAdapterKind, AIProviderStatus
from app.ai_provider_registry import create_provider_configuration
from app.auth import get_current_user
from app.main import app
from app.models import Membership, MembershipRole, Organization, User
from app.secrets import SecretStoreError, get_secret_store


class FakeSecretStore:
    def __init__(self) -> None:
        self.values: dict[str, dict[str, str]] = {}
        self.fail_replace = False

    def store_ai_provider_secret(
        self,
        *,
        organization_id: uuid.UUID,
        provider_configuration_id: uuid.UUID,
        provider: str,
        credentials: dict[str, str],
    ) -> str:
        reference = f"arn:test:ai:{organization_id}:{provider}:{provider_configuration_id}"
        self.values[reference] = dict(credentials)
        return reference

    def replace_secret(self, reference: str, credentials: dict[str, str]) -> None:
        if self.fail_replace:
            raise SecretStoreError("replace failed")
        if reference not in self.values:
            raise SecretStoreError("missing")
        self.values[reference] = dict(credentials)

    def schedule_delete(self, reference: str) -> None:
        self.values.pop(reference, None)

    def load_connection_secret(self, reference: str) -> dict[str, str]:
        return dict(self.values[reference])


def _seed(db: Session):
    owner = User(email="rotate-ai-owner@example.com")
    member = User(email="rotate-ai-member@example.com")
    organization = Organization(name="Rotate AI", slug="rotate-ai")
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


def _auth(user: User) -> None:
    app.dependency_overrides[get_current_user] = lambda: user


def _clear() -> None:
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_secret_store, None)


def test_owner_rotates_ai_provider_credential_without_secret_echo(
    client: TestClient,
    db_session: Session,
) -> None:
    organization, owner, _ = _seed(db_session)
    store = FakeSecretStore()
    provider = create_provider_configuration(
        db_session,
        secret_store=store,
        organization_id=organization.id,
        actor_user_id=owner.id,
        provider_key="openai-primary",
        display_name="Primary AI",
        adapter_kind=AIProviderAdapterKind.OPENAI_CHAT_COMPLETIONS,
        api_url="https://api.openai.com/v1/chat/completions",
        credentials={"api_key": "old-secret"},
    )
    assert provider.secret_ref is not None

    _auth(owner)
    app.dependency_overrides[get_secret_store] = lambda: store
    try:
        response = client.post(
            f"/api/v1/organizations/{organization.id}/ai/providers/{provider.id}/rotate",
            json={"credentials": {"api_key": "new-secret"}},
        )
    finally:
        _clear()

    assert response.status_code == 200
    assert response.json()["credential_rotated_at"] is not None
    assert "secret_ref" not in response.text
    assert "new-secret" not in response.text
    assert store.values[provider.secret_ref] == {"api_key": "new-secret"}


def test_non_admin_cannot_rotate_ai_provider_credential(
    client: TestClient,
    db_session: Session,
) -> None:
    organization, owner, member = _seed(db_session)
    store = FakeSecretStore()
    provider = create_provider_configuration(
        db_session,
        secret_store=store,
        organization_id=organization.id,
        actor_user_id=owner.id,
        provider_key="member-denied",
        display_name="Member denied",
        adapter_kind=AIProviderAdapterKind.OPENAI_CHAT_COMPLETIONS,
        api_url="https://ai.example.com/v1/chat/completions",
        credentials={"api_key": "old-secret"},
    )

    _auth(member)
    app.dependency_overrides[get_secret_store] = lambda: store
    try:
        response = client.post(
            f"/api/v1/organizations/{organization.id}/ai/providers/{provider.id}/rotate",
            json={"credentials": {"api_key": "must-not-write"}},
        )
    finally:
        _clear()

    assert response.status_code == 403
    assert store.values[provider.secret_ref]["api_key"] == "old-secret"


def test_revoked_ai_provider_cannot_rotate_and_store_failure_is_safe(
    client: TestClient,
    db_session: Session,
) -> None:
    organization, owner, _ = _seed(db_session)
    store = FakeSecretStore()
    provider = create_provider_configuration(
        db_session,
        secret_store=store,
        organization_id=organization.id,
        actor_user_id=owner.id,
        provider_key="rotation-states",
        display_name="Rotation states",
        adapter_kind=AIProviderAdapterKind.OPENAI_CHAT_COMPLETIONS,
        api_url="https://ai.example.com/v1/chat/completions",
        credentials={"api_key": "old-secret"},
    )

    _auth(owner)
    app.dependency_overrides[get_secret_store] = lambda: store
    store.fail_replace = True
    try:
        failed = client.post(
            f"/api/v1/organizations/{organization.id}/ai/providers/{provider.id}/rotate",
            json={"credentials": {"api_key": "new-secret"}},
        )
    finally:
        _clear()
    assert failed.status_code == 503
    db_session.refresh(provider)
    assert provider.credential_rotated_at is None
    assert store.values[provider.secret_ref]["api_key"] == "old-secret"

    provider.status = AIProviderStatus.REVOKED
    db_session.commit()
    _auth(owner)
    app.dependency_overrides[get_secret_store] = lambda: store
    store.fail_replace = False
    try:
        revoked = client.post(
            f"/api/v1/organizations/{organization.id}/ai/providers/{provider.id}/rotate",
            json={"credentials": {"api_key": "must-not-write"}},
        )
    finally:
        _clear()
    assert revoked.status_code == 409
    assert store.values[provider.secret_ref]["api_key"] == "old-secret"

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.main import app
from app.models import Membership, MembershipRole, Organization, User
from app.secrets import get_secret_store


class ProbeSecretStore:
    def __init__(self) -> None:
        self.store_calls = 0
        self.load_calls = 0

    def store_ai_provider_secret(self, **kwargs) -> str:
        del kwargs
        self.store_calls += 1
        return "arn:test:ai"

    def load_connection_secret(self, reference: str) -> dict[str, str]:
        del reference
        self.load_calls += 1
        return {"api_key": "should-never-be-used"}

    def schedule_delete(self, reference: str) -> None:
        del reference


def _seed_user(db: Session, role: MembershipRole, suffix: str):
    user = User(email=f"ai-route-{role.value}-{suffix}@example.com")
    organization = Organization(
        name=f"AI Route {suffix}",
        slug=f"ai-route-{suffix}",
    )
    db.add_all([user, organization])
    db.flush()
    db.add(
        Membership(
            organization_id=organization.id,
            user_id=user.id,
            role=role,
        )
    )
    db.commit()
    return user, organization


def test_member_cannot_manage_ai_provider_before_secret_storage(
    client: TestClient,
    db_session: Session,
) -> None:
    member, organization = _seed_user(db_session, MembershipRole.MEMBER, "manage")
    store = ProbeSecretStore()
    app.dependency_overrides[get_current_user] = lambda: member
    app.dependency_overrides[get_secret_store] = lambda: store
    try:
        response = client.post(
            f"/api/v1/organizations/{organization.id}/ai/providers",
            json={
                "provider_key": "acme",
                "display_name": "Acme",
                "adapter_kind": "openai_chat_completions",
                "api_url": "https://ai.example.com/v1/chat/completions",
                "credentials": {"api_key": "must-not-store"},
            },
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_secret_store, None)

    assert response.status_code == 403
    assert store.store_calls == 0
    assert store.load_calls == 0


def test_guest_cannot_invoke_ai_before_secret_or_provider_execution(
    client: TestClient,
    db_session: Session,
) -> None:
    guest, organization = _seed_user(db_session, MembershipRole.GUEST, "invoke")
    store = ProbeSecretStore()
    app.dependency_overrides[get_current_user] = lambda: guest
    app.dependency_overrides[get_secret_store] = lambda: store
    try:
        response = client.post(
            f"/api/v1/organizations/{organization.id}/ai/invoke",
            json={
                "provider_configuration_id": str(uuid.uuid4()),
                "model_configuration_id": str(uuid.uuid4()),
                "input_text": "do not execute",
            },
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_secret_store, None)

    assert response.status_code == 403
    assert store.store_calls == 0
    assert store.load_calls == 0

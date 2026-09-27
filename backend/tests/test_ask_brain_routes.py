import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.main import app
from app.models import Membership, MembershipRole, Organization, User
from app.secrets import get_secret_store


class ProbeSecretStore:
    def __init__(self) -> None:
        self.load_calls = 0

    def load_connection_secret(self, reference: str) -> dict[str, str]:
        del reference
        self.load_calls += 1
        return {"api_key": "must-not-load"}


def test_whitespace_question_is_client_error_before_provider_access(
    client: TestClient,
    db_session: Session,
) -> None:
    user = User(email="ask-route-whitespace@example.com")
    organization = Organization(name="Ask Route", slug="ask-route-whitespace")
    db_session.add_all([user, organization])
    db_session.flush()
    db_session.add(
        Membership(
            organization_id=organization.id,
            user_id=user.id,
            role=MembershipRole.MEMBER,
        )
    )
    db_session.commit()

    store = ProbeSecretStore()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_secret_store] = lambda: store
    try:
        response = client.post(
            f"/api/v1/organizations/{organization.id}/ask-brain",
            json={
                "question": "   ",
                "provider_configuration_id": str(uuid.uuid4()),
                "model_configuration_id": str(uuid.uuid4()),
            },
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_secret_store, None)

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "question_required"
    assert store.load_calls == 0

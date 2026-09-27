from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai_gateway_models import (
    AIModelConfiguration,
    AIProviderAdapterKind,
    AIProviderConfiguration,
    AIProviderStatus,
)
from app.auth import get_current_user
from app.main import app
from app.models import Membership, MembershipRole, Organization, User


def _member(db: Session, *, role: MembershipRole, suffix: str):
    user = User(email=f"runtime-{suffix}@example.com")
    organization = Organization(name=f"Runtime {suffix}", slug=f"runtime-{suffix}")
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


def test_current_organizations_returns_only_authenticated_memberships(
    client: TestClient,
    db_session: Session,
) -> None:
    user, organization = _member(db_session, role=MembershipRole.MEMBER, suffix="mine")
    _, other = _member(db_session, role=MembershipRole.OWNER, suffix="other")
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        response = client.get("/api/v1/organizations")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(organization.id),
            "slug": organization.slug,
            "name": organization.name,
            "role": "member",
        }
    ]
    assert str(other.id) not in response.text


def test_ai_user_can_discover_enabled_runtime_without_admin_metadata(
    client: TestClient,
    db_session: Session,
) -> None:
    user, organization = _member(db_session, role=MembershipRole.MEMBER, suffix="options")
    provider = AIProviderConfiguration(
        organization_id=organization.id,
        provider_key="openai",
        display_name="OpenAI",
        adapter_kind=AIProviderAdapterKind.OPENAI_CHAT_COMPLETIONS,
        api_url="https://api.openai.com/v1/chat/completions",
        secret_ref="arn:test:secret",
        status=AIProviderStatus.ENABLED,
        created_by_user_id=user.id,
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
        created_by_user_id=user.id,
    )
    disabled_model = AIModelConfiguration(
        organization_id=organization.id,
        provider_configuration_id=provider.id,
        model_key="disabled-model",
        display_name="Disabled model",
        enabled=False,
        max_output_tokens=1024,
        created_by_user_id=user.id,
    )
    db_session.add_all([model, disabled_model])
    db_session.commit()

    app.dependency_overrides[get_current_user] = lambda: user
    try:
        response = client.get(
            f"/api/v1/organizations/{organization.id}/ai/runtime-options"
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    assert response.json() == [
        {
            "provider_configuration_id": str(provider.id),
            "provider_key": "openai",
            "provider_display_name": "OpenAI",
            "model_configuration_id": str(model.id),
            "model_key": "gpt-5.6-terra",
            "model_display_name": "GPT-5.6 Terra",
            "max_output_tokens": 8192,
        }
    ]
    assert "api_url" not in response.text
    assert "secret" not in response.text
    assert "disabled-model" not in response.text


def test_guest_cannot_discover_ai_runtime_options(
    client: TestClient,
    db_session: Session,
) -> None:
    guest, organization = _member(db_session, role=MembershipRole.GUEST, suffix="guest")
    app.dependency_overrides[get_current_user] = lambda: guest
    try:
        response = client.get(
            f"/api/v1/organizations/{organization.id}/ai/runtime-options"
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 403

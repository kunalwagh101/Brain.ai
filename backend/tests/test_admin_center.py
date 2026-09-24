from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai_gateway_models import (
    AIModelConfiguration,
    AIProviderAdapterKind,
    AIProviderConfiguration,
    AIProviderStatus,
)
from app.api_registry_models import APICredentialGrant, APIGrantStatus, APIService
from app.auth import get_current_user
from app.main import app
from app.models import (
    IntegrationConnection,
    IntegrationHealth,
    IntegrationStatus,
    Membership,
    MembershipRole,
    Organization,
    User,
)


def _seed(db: Session):
    owner = User(email="admin-center-owner@example.com", display_name="Admin Owner")
    member = User(email="admin-center-member@example.com", display_name="Normal Member")
    organization = Organization(name="Admin Center Org", slug="admin-center-org")
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

    integration = IntegrationConnection(
        organization_id=organization.id,
        provider="slack",
        external_account_id="workspace-secret-id",
        display_name="Company Slack",
        status=IntegrationStatus.ACTIVE,
        health=IntegrationHealth.HEALTHY,
        scopes=["channels:history"],
        provider_metadata={"safe": "metadata"},
        secret_ref="arn:aws:secretsmanager:test:integration-secret",
        created_by_user_id=owner.id,
    )
    db.add(integration)

    provider = AIProviderConfiguration(
        organization_id=organization.id,
        provider_key="openai-primary",
        display_name="Primary AI",
        adapter_kind=AIProviderAdapterKind.OPENAI_CHAT_COMPLETIONS,
        api_url="https://api.openai.com/v1/chat/completions",
        secret_ref="arn:aws:secretsmanager:test:ai-secret",
        status=AIProviderStatus.ENABLED,
        created_by_user_id=owner.id,
    )
    db.add(provider)
    db.flush()
    model = AIModelConfiguration(
        organization_id=organization.id,
        provider_configuration_id=provider.id,
        model_key="test-model",
        display_name="Test Model",
        enabled=True,
        max_output_tokens=4096,
        created_by_user_id=owner.id,
    )
    db.add(model)

    service = APIService(
        organization_id=organization.id,
        service_key="apollo",
        display_name="Apollo",
        provider_name="Apollo.io",
        base_url="https://api.apollo.io",
        created_by_user_id=owner.id,
    )
    db.add(service)
    db.flush()
    grant = APICredentialGrant(
        organization_id=organization.id,
        service_id=service.id,
        grant_key="apollo-prod",
        display_name="Apollo Production",
        owner_user_id=owner.id,
        environment="production",
        scopes=["people.read"],
        secret_ref="arn:aws:secretsmanager:test:api-secret",
        status=APIGrantStatus.ACTIVE,
        usage_count=7,
        created_by_user_id=owner.id,
    )
    db.add(grant)
    db.commit()
    return organization, owner, member


def test_owner_gets_safe_admin_center_aggregate(
    client: TestClient,
    db_session: Session,
) -> None:
    organization, owner, _ = _seed(db_session)
    app.dependency_overrides[get_current_user] = lambda: owner
    try:
        response = client.get(
            f"/api/v1/organizations/{organization.id}/admin-center"
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["member_count"] == 2
    assert payload["summary"]["integration_count"] == 1
    assert payload["summary"]["ai_provider_count"] == 1
    assert payload["summary"]["enabled_ai_model_count"] == 1
    assert payload["summary"]["active_api_grant_count"] == 1
    assert payload["members"][0]["email"] in {
        "admin-center-owner@example.com",
        "admin-center-member@example.com",
    }
    assert payload["integrations"][0]["display_name"] == "Company Slack"
    assert payload["ai_providers"][0]["models"][0]["model_key"] == "test-model"
    assert payload["api_services"][0]["grants"][0]["credential_present"] is True

    serialized = response.text.lower()
    assert "secret_ref" not in serialized
    assert "credentials" not in serialized
    assert "integration-secret" not in serialized
    assert "ai-secret" not in serialized
    assert "api-secret" not in serialized
    assert "workspace-secret-id" not in serialized


def test_normal_member_cannot_open_admin_center(
    client: TestClient,
    db_session: Session,
) -> None:
    organization, _, member = _seed(db_session)
    app.dependency_overrides[get_current_user] = lambda: member
    try:
        response = client.get(
            f"/api/v1/organizations/{organization.id}/admin-center"
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 403

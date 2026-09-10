import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api_registry_models import (
    APICredentialGrant,
    APIGrantStatus,
    APIService,
    APIUsageObservation,
)
from app.auth import get_current_user
from app.main import app
from app.models import Membership, MembershipRole, Organization, User


def _seed(db: Session):
    owner = User(email=f"api-usage-owner-{uuid.uuid4()}@example.com")
    executive = User(email=f"api-usage-exec-{uuid.uuid4()}@example.com")
    member = User(email=f"api-usage-member-{uuid.uuid4()}@example.com")
    organization = Organization(
        name="API Usage Drilldown",
        slug=f"api-usage-drilldown-{uuid.uuid4().hex[:8]}",
    )
    db.add_all([owner, executive, member, organization])
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
                user_id=executive.id,
                role=MembershipRole.EXECUTIVE,
            ),
            Membership(
                organization_id=organization.id,
                user_id=member.id,
                role=MembershipRole.MEMBER,
            ),
        ]
    )
    service = APIService(
        organization_id=organization.id,
        service_key="calendar",
        display_name="Calendar API",
        provider_name="Calendar Provider",
        base_url="https://calendar.example.com",
        created_by_user_id=owner.id,
    )
    db.add(service)
    db.flush()
    grant = APICredentialGrant(
        organization_id=organization.id,
        service_id=service.id,
        grant_key="calendar-production",
        display_name="Calendar production",
        owner_user_id=owner.id,
        environment="production",
        scopes=["read"],
        secret_ref="arn:test:must-not-return",
        status=APIGrantStatus.ACTIVE,
        created_by_user_id=owner.id,
    )
    db.add(grant)
    db.flush()
    observation = APIUsageObservation(
        organization_id=organization.id,
        grant_id=grant.id,
        observation_key="calendar-call-1",
        caller_component="sync-worker",
        operation_label="list-events",
        success=True,
        latency_ms=25,
        observed_at=datetime.now(UTC),
    )
    db.add(observation)
    db.commit()
    return organization, executive, member, service, grant, observation


def test_organization_api_usage_drilldown_requires_audit_read_and_never_returns_secret(
    client: TestClient,
    db_session: Session,
) -> None:
    organization, executive, member, service, grant, observation = _seed(db_session)
    path = f"/api/v1/organizations/{organization.id}/api-registry/usage"

    app.dependency_overrides[get_current_user] = lambda: member
    try:
        denied = client.get(path)
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert denied.status_code == 403

    app.dependency_overrides[get_current_user] = lambda: executive
    try:
        allowed = client.get(path)
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert allowed.status_code == 200
    payload = allowed.json()
    assert len(payload) == 1
    assert payload[0]["id"] == str(observation.id)
    assert payload[0]["grant_id"] == str(grant.id)
    assert payload[0]["service_id"] == str(service.id)
    assert payload[0]["service_key"] == "calendar"
    assert "secret_ref" not in payload[0]
    assert "credential" not in payload[0]

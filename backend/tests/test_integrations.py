import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.integrations import IntegrationNotSyncableError, connection_can_sync, record_sync_success
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
from app.secrets import SecretStoreError, get_secret_store


class FakeSecretStore:
    def __init__(self) -> None:
        self.stored: list[dict[str, object]] = []
        self.deleted: list[str] = []
        self.fail_delete = False

    def store_connection_secret(
        self,
        *,
        organization_id: uuid.UUID,
        connection_id: uuid.UUID,
        provider: str,
        credentials: dict[str, str],
    ) -> str:
        self.stored.append(
            {
                "organization_id": organization_id,
                "connection_id": connection_id,
                "provider": provider,
                "credentials": credentials,
            }
        )
        return f"arn:aws:secretsmanager:us-east-1:123456789012:secret:{connection_id}"

    def load_connection_secret(self, reference: str) -> dict[str, str]:
        return {"reference": reference}

    def schedule_delete(self, reference: str) -> None:
        if self.fail_delete:
            raise SecretStoreError("delete failed")
        self.deleted.append(reference)


def _use_user(user: User) -> None:
    app.dependency_overrides[get_current_user] = lambda: user


def _use_secret_store(store: FakeSecretStore) -> None:
    app.dependency_overrides[get_secret_store] = lambda: store


def _seed_org(
    db: Session,
    *,
    role: MembershipRole = MembershipRole.OWNER,
    slug: str = "acme",
) -> tuple[User, Organization]:
    user = User(email=f"{role.value}-{slug}@example.com")
    organization = Organization(name=slug.title(), slug=slug)
    db.add_all([user, organization])
    db.flush()
    db.add(Membership(organization_id=organization.id, user_id=user.id, role=role))
    db.commit()
    return user, organization


def test_admin_creates_connection_without_persisting_plaintext_credentials(
    client: TestClient,
    db_session: Session,
) -> None:
    admin, organization = _seed_org(db_session, role=MembershipRole.ADMIN)
    store = FakeSecretStore()
    _use_user(admin)
    _use_secret_store(store)

    response = client.post(
        f"/api/v1/organizations/{organization.id}/integrations",
        json={
            "provider": "slack",
            "external_account_id": "T123",
            "display_name": "Acme Slack",
            "scopes": ["channels:read", "channels:read"],
            "credentials": {"access_token": "xoxb-realistic-secret"},
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["provider"] == "slack"
    assert body["scopes"] == ["channels:read"]
    assert "credentials" not in body
    assert "secret_ref" not in body
    assert "xoxb-realistic-secret" not in response.text

    connection = db_session.query(IntegrationConnection).one()
    assert connection.organization_id == organization.id
    assert connection.secret_ref.startswith("arn:aws:secretsmanager:")
    assert not hasattr(connection, "credentials")
    assert store.stored[0]["credentials"] == {"access_token": "xoxb-realistic-secret"}


def test_duplicate_connection_is_rejected_before_secret_creation(
    client: TestClient,
    db_session: Session,
) -> None:
    owner, organization = _seed_org(db_session)
    store = FakeSecretStore()
    _use_user(owner)
    _use_secret_store(store)
    payload = {
        "provider": "github",
        "external_account_id": "installation-42",
        "display_name": "Acme GitHub",
        "credentials": {"installation_token": "token-1"},
    }

    first = client.post(f"/api/v1/organizations/{organization.id}/integrations", json=payload)
    second = client.post(f"/api/v1/organizations/{organization.id}/integrations", json=payload)

    assert first.status_code == 201
    assert second.status_code == 409
    assert len(store.stored) == 1


def test_member_cannot_manage_integrations(client: TestClient, db_session: Session) -> None:
    member, organization = _seed_org(db_session, role=MembershipRole.MEMBER)
    store = FakeSecretStore()
    _use_user(member)
    _use_secret_store(store)

    response = client.post(
        f"/api/v1/organizations/{organization.id}/integrations",
        json={
            "provider": "slack",
            "external_account_id": "T123",
            "display_name": "Acme Slack",
            "credentials": {"access_token": "secret"},
        },
    )

    assert response.status_code == 403
    assert store.stored == []


def test_cross_tenant_integration_list_is_hidden(client: TestClient, db_session: Session) -> None:
    outsider, _ = _seed_org(db_session, slug="outside")
    _, target = _seed_org(db_session, slug="target")
    _use_user(outsider)
    _use_secret_store(FakeSecretStore())

    response = client.get(f"/api/v1/organizations/{target.id}/integrations")

    assert response.status_code == 404
    assert response.json() == {"detail": "Organization not found"}


def test_revoke_disables_sync_and_removes_database_secret_reference(
    client: TestClient,
    db_session: Session,
) -> None:
    owner, organization = _seed_org(db_session)
    store = FakeSecretStore()
    _use_user(owner)
    _use_secret_store(store)
    connection = IntegrationConnection(
        organization_id=organization.id,
        provider="slack",
        external_account_id="T123",
        display_name="Acme Slack",
        status=IntegrationStatus.ACTIVE,
        health=IntegrationHealth.HEALTHY,
        scopes=["channels:read"],
        secret_ref="arn:secret:one",
        created_by_user_id=owner.id,
    )
    db_session.add(connection)
    db_session.commit()

    response = client.post(
        f"/api/v1/organizations/{organization.id}/integrations/{connection.id}/revoke"
    )

    assert response.status_code == 200
    db_session.refresh(connection)
    assert connection.status == IntegrationStatus.REVOKED
    assert connection.secret_ref is None
    assert connection.revoked_at is not None
    assert connection_can_sync(connection) is False
    assert store.deleted == ["arn:secret:one"]


def test_failed_secret_delete_leaves_connection_non_syncable(
    client: TestClient,
    db_session: Session,
) -> None:
    owner, organization = _seed_org(db_session)
    store = FakeSecretStore()
    store.fail_delete = True
    _use_user(owner)
    _use_secret_store(store)
    connection = IntegrationConnection(
        organization_id=organization.id,
        provider="github",
        external_account_id="installation-42",
        display_name="Acme GitHub",
        status=IntegrationStatus.ACTIVE,
        health=IntegrationHealth.UNKNOWN,
        scopes=[],
        secret_ref="arn:secret:two",
        created_by_user_id=owner.id,
    )
    db_session.add(connection)
    db_session.commit()

    response = client.post(
        f"/api/v1/organizations/{organization.id}/integrations/{connection.id}/revoke"
    )

    assert response.status_code == 503
    db_session.refresh(connection)
    assert connection.status == IntegrationStatus.REVOKE_FAILED
    assert connection_can_sync(connection) is False
    assert connection.secret_ref == "arn:secret:two"


def test_sync_success_persists_health_and_cursor(db_session: Session) -> None:
    owner, organization = _seed_org(db_session)
    connection = IntegrationConnection(
        organization_id=organization.id,
        provider="github",
        external_account_id="installation-42",
        display_name="Acme GitHub",
        status=IntegrationStatus.ACTIVE,
        health=IntegrationHealth.UNKNOWN,
        scopes=[],
        secret_ref="arn:secret:three",
        created_by_user_id=owner.id,
    )
    db_session.add(connection)
    db_session.commit()

    record_sync_success(db_session, connection, cursor="cursor-123")

    assert connection.health == IntegrationHealth.HEALTHY
    assert connection.sync_cursor == "cursor-123"
    assert connection.last_synced_at is not None

    connection.status = IntegrationStatus.REVOKED
    db_session.commit()
    with pytest.raises(IntegrationNotSyncableError):
        record_sync_success(db_session, connection, cursor="cursor-456")

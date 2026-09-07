import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api_registry import (
    APIRegistryError,
    change_api_grant_owner,
    change_api_grant_scopes,
    create_api_grant,
    create_api_service,
    expire_due_api_grants,
    record_api_usage,
    revoke_api_grant,
    rotate_api_grant_credentials,
    set_api_grant_enabled,
)
from app.api_registry_models import (
    APICredentialGrant,
    APIGrantHistory,
    APIGrantHistoryAction,
    APIGrantStatus,
    APIUsageObservation,
)
from app.auth import get_current_user
from app.database import get_db
from app.main import app
from app.models import Membership, MembershipRole, Organization, User
from app.permissions import Permission, role_has_permission
from app.secrets import SecretStoreError, get_secret_store


class FakeSecretStore:
    def __init__(self) -> None:
        self.values: dict[str, dict[str, str]] = {}
        self.deleted: list[str] = []
        self.fail_delete = False
        self.replacements = 0

    def store_api_credential_secret(
        self,
        *,
        organization_id: uuid.UUID,
        grant_id: uuid.UUID,
        service_key: str,
        credentials: dict[str, str],
    ) -> str:
        reference = f"arn:test:api:{organization_id}:{service_key}:{grant_id}"
        self.values[reference] = dict(credentials)
        return reference

    def replace_secret(self, reference: str, credentials: dict[str, str]) -> None:
        if reference not in self.values:
            raise SecretStoreError("missing")
        self.values[reference] = dict(credentials)
        self.replacements += 1

    def schedule_delete(self, reference: str) -> None:
        if self.fail_delete:
            raise SecretStoreError("delete failed")
        self.deleted.append(reference)
        self.values.pop(reference, None)

    def load_connection_secret(self, reference: str) -> dict[str, str]:
        value = self.values.get(reference)
        if value is None:
            raise SecretStoreError("missing")
        return dict(value)


def _seed(db: Session, suffix: str):
    owner = User(email=f"api-owner-{suffix}@example.com")
    admin = User(email=f"api-admin-{suffix}@example.com")
    executive = User(email=f"api-exec-{suffix}@example.com")
    member = User(email=f"api-member-{suffix}@example.com")
    organization = Organization(name=f"API Org {suffix}", slug=f"api-{suffix}")
    db.add_all([owner, admin, executive, member, organization])
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
                user_id=admin.id,
                role=MembershipRole.ADMIN,
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
    db.commit()
    return organization, owner, admin, executive, member


def _service_and_grant(
    db: Session,
    *,
    store: FakeSecretStore,
    organization: Organization,
    owner: User,
    suffix: str,
    expires_at: datetime | None = None,
):
    service = create_api_service(
        db,
        organization_id=organization.id,
        actor_user_id=owner.id,
        service_key=f"crm-{suffix}",
        display_name="CRM API",
        provider_name="CRM Vendor",
        base_url="https://api.example.com",
    )
    grant = create_api_grant(
        db,
        secret_store=store,
        organization_id=organization.id,
        actor_user_id=owner.id,
        service_id=service.id,
        grant_key=f"crm-prod-{suffix}",
        display_name="CRM production credential",
        owner_user_id=owner.id,
        environment="production",
        scopes=["contacts.read", "contacts.write"],
        expires_at=expires_at,
        credentials={"api_key": "must-not-persist"},
    )
    return service, grant


def test_api_manage_is_owner_admin_only() -> None:
    assert role_has_permission(MembershipRole.OWNER, Permission.API_MANAGE)
    assert role_has_permission(MembershipRole.ADMIN, Permission.API_MANAGE)
    assert not role_has_permission(MembershipRole.EXECUTIVE, Permission.API_MANAGE)
    assert not role_has_permission(MembershipRole.MANAGER, Permission.API_MANAGE)
    assert not role_has_permission(MembershipRole.MEMBER, Permission.API_MANAGE)


def test_grant_persists_only_secret_reference_and_created_history(db_session: Session) -> None:
    organization, owner, _, _, _ = _seed(db_session, "secret")
    store = FakeSecretStore()
    _, grant = _service_and_grant(
        db_session,
        store=store,
        organization=organization,
        owner=owner,
        suffix="secret",
    )

    assert grant.secret_ref is not None
    assert store.values[grant.secret_ref]["api_key"] == "must-not-persist"
    assert not hasattr(grant, "api_key")
    history = list(
        db_session.scalars(
            select(APIGrantHistory).where(APIGrantHistory.grant_id == grant.id)
        )
    )
    assert len(history) == 1
    assert history[0].action == APIGrantHistoryAction.CREATED
    assert "must-not-persist" not in str(history[0].reason)


def test_cross_tenant_service_and_owner_are_rejected(db_session: Session) -> None:
    organization, owner, _, _, _ = _seed(db_session, "tenant-a")
    other, other_owner, _, _, _ = _seed(db_session, "tenant-b")
    store = FakeSecretStore()
    other_service = create_api_service(
        db_session,
        organization_id=other.id,
        actor_user_id=other_owner.id,
        service_key="other",
        display_name="Other",
        provider_name="Other",
        base_url=None,
    )

    with pytest.raises(APIRegistryError, match="not found"):
        create_api_grant(
            db_session,
            secret_store=store,
            organization_id=organization.id,
            actor_user_id=owner.id,
            service_id=other_service.id,
            grant_key="wrong-service",
            display_name="Wrong",
            owner_user_id=owner.id,
            environment="production",
            scopes=["read"],
            expires_at=None,
            credentials={"api_key": "secret"},
        )

    service = create_api_service(
        db_session,
        organization_id=organization.id,
        actor_user_id=owner.id,
        service_key="same-org",
        display_name="Same org",
        provider_name="Vendor",
        base_url=None,
    )
    with pytest.raises(APIRegistryError, match="active organization member"):
        create_api_grant(
            db_session,
            secret_store=store,
            organization_id=organization.id,
            actor_user_id=owner.id,
            service_id=service.id,
            grant_key="wrong-owner",
            display_name="Wrong owner",
            owner_user_id=other_owner.id,
            environment="production",
            scopes=["read"],
            expires_at=None,
            credentials={"api_key": "secret"},
        )


def test_owner_scope_changes_are_immutable_history(db_session: Session) -> None:
    organization, owner, admin, _, _ = _seed(db_session, "history")
    store = FakeSecretStore()
    _, grant = _service_and_grant(
        db_session,
        store=store,
        organization=organization,
        owner=owner,
        suffix="history",
    )
    change_api_grant_owner(
        db_session,
        organization_id=organization.id,
        grant_id=grant.id,
        actor_user_id=owner.id,
        owner_user_id=admin.id,
        reason="ownership moved",
    )
    change_api_grant_scopes(
        db_session,
        organization_id=organization.id,
        grant_id=grant.id,
        actor_user_id=owner.id,
        scopes=["contacts.read"],
        reason="least privilege",
    )

    history = list(
        db_session.scalars(
            select(APIGrantHistory)
            .where(APIGrantHistory.grant_id == grant.id)
            .order_by(APIGrantHistory.created_at, APIGrantHistory.id)
        )
    )
    assert [item.action for item in history] == [
        APIGrantHistoryAction.CREATED,
        APIGrantHistoryAction.OWNER_CHANGED,
        APIGrantHistoryAction.SCOPES_CHANGED,
    ]
    assert history[1].previous_owner_user_id == owner.id
    assert history[1].new_owner_user_id == admin.id
    assert history[2].previous_scopes == ["contacts.read", "contacts.write"]
    assert history[2].new_scopes == ["contacts.read"]


def test_rotation_never_writes_credential_values_to_history(db_session: Session) -> None:
    organization, owner, _, _, _ = _seed(db_session, "rotation")
    store = FakeSecretStore()
    _, grant = _service_and_grant(
        db_session,
        store=store,
        organization=organization,
        owner=owner,
        suffix="rotation",
    )
    reference = grant.secret_ref
    assert reference is not None

    rotate_api_grant_credentials(
        db_session,
        secret_store=store,
        organization_id=organization.id,
        grant_id=grant.id,
        actor_user_id=owner.id,
        credentials={"api_key": "rotated-super-secret"},
        reason="scheduled rotation",
    )
    assert store.values[reference]["api_key"] == "rotated-super-secret"
    assert store.replacements == 1
    db_session.refresh(grant)
    assert grant.credential_rotated_at is not None
    history = db_session.scalar(
        select(APIGrantHistory)
        .where(
            APIGrantHistory.grant_id == grant.id,
            APIGrantHistory.action == APIGrantHistoryAction.CREDENTIAL_ROTATED,
        )
        .limit(1)
    )
    assert history is not None
    assert "rotated-super-secret" not in str(history.reason)


def test_revocation_failure_is_fail_closed_and_retryable(db_session: Session) -> None:
    organization, owner, _, _, _ = _seed(db_session, "revoke")
    store = FakeSecretStore()
    _, grant = _service_and_grant(
        db_session,
        store=store,
        organization=organization,
        owner=owner,
        suffix="revoke",
    )
    store.fail_delete = True
    with pytest.raises(APIRegistryError, match="incomplete"):
        revoke_api_grant(
            db_session,
            secret_store=store,
            organization_id=organization.id,
            grant_id=grant.id,
            actor_user_id=owner.id,
            reason="security response",
        )
    db_session.refresh(grant)
    assert grant.status == APIGrantStatus.REVOKE_FAILED
    with pytest.raises(APIRegistryError, match="cannot be re-enabled"):
        set_api_grant_enabled(
            db_session,
            organization_id=organization.id,
            grant_id=grant.id,
            actor_user_id=owner.id,
            enabled=True,
            reason=None,
        )
    with pytest.raises(APIRegistryError, match="cannot rotate"):
        rotate_api_grant_credentials(
            db_session,
            secret_store=store,
            organization_id=organization.id,
            grant_id=grant.id,
            actor_user_id=owner.id,
            credentials={"api_key": "new"},
            reason=None,
        )

    store.fail_delete = False
    revoke_api_grant(
        db_session,
        secret_store=store,
        organization_id=organization.id,
        grant_id=grant.id,
        actor_user_id=owner.id,
        reason="retry",
    )
    db_session.refresh(grant)
    assert grant.status == APIGrantStatus.REVOKED
    assert grant.secret_ref is None
    assert grant.revoked_at is not None


def test_expiry_transition_is_idempotent_and_audited_once(db_session: Session) -> None:
    organization, owner, _, _, _ = _seed(db_session, "expiry")
    store = FakeSecretStore()
    _, grant = _service_and_grant(
        db_session,
        store=store,
        organization=organization,
        owner=owner,
        suffix="expiry",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    past = datetime.now(UTC) + timedelta(hours=2)
    assert expire_due_api_grants(
        db_session,
        organization_id=organization.id,
        at=past,
        limit=10,
    ) == 1
    assert expire_due_api_grants(
        db_session,
        organization_id=organization.id,
        at=past,
        limit=10,
    ) == 0
    db_session.refresh(grant)
    assert grant.status == APIGrantStatus.EXPIRED
    assert grant.expired_at is not None
    events = list(
        db_session.scalars(
            select(APIGrantHistory).where(
                APIGrantHistory.grant_id == grant.id,
                APIGrantHistory.action == APIGrantHistoryAction.EXPIRED,
            )
        )
    )
    assert len(events) == 1


def test_usage_observation_is_idempotent_and_records_post_revoke_evidence(
    db_session: Session,
) -> None:
    organization, owner, _, _, _ = _seed(db_session, "usage")
    store = FakeSecretStore()
    _, grant = _service_and_grant(
        db_session,
        store=store,
        organization=organization,
        owner=owner,
        suffix="usage",
    )
    first = record_api_usage(
        db_session,
        organization_id=organization.id,
        grant_id=grant.id,
        observation_key="request-1",
        caller_component="crm.sync",
        operation_label="contacts.list",
        success=True,
        latency_ms=25,
    )
    replay = record_api_usage(
        db_session,
        organization_id=organization.id,
        grant_id=grant.id,
        observation_key="request-1",
        caller_component="crm.sync",
        operation_label="contacts.list",
        success=True,
        latency_ms=25,
    )
    assert replay.id == first.id
    db_session.refresh(grant)
    assert grant.usage_count == 1

    revoke_api_grant(
        db_session,
        secret_store=store,
        organization_id=organization.id,
        grant_id=grant.id,
        actor_user_id=owner.id,
        reason="retired",
    )
    record_api_usage(
        db_session,
        organization_id=organization.id,
        grant_id=grant.id,
        observation_key="request-after-revoke",
        caller_component="crm.sync",
        operation_label="contacts.list",
        success=False,
        latency_ms=5,
    )
    db_session.refresh(grant)
    assert grant.usage_count == 2
    assert grant.last_usage_success is False
    assert db_session.scalar(select(APIUsageObservation).where(
        APIUsageObservation.observation_key == "request-after-revoke"
    )) is not None


def test_registry_routes_do_not_return_secret_ref_and_member_cannot_read(
    db_session: Session,
    client,
) -> None:
    organization, owner, _, executive, member = _seed(db_session, "routes")
    store = FakeSecretStore()
    service, grant = _service_and_grant(
        db_session,
        store=store,
        organization=organization,
        owner=owner,
        suffix="routes",
    )
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_secret_store] = lambda: store

    app.dependency_overrides[get_current_user] = lambda: member
    denied = client.get(f"/api/v1/organizations/{organization.id}/api-registry/grants")
    assert denied.status_code == 403

    app.dependency_overrides[get_current_user] = lambda: executive
    allowed = client.get(f"/api/v1/organizations/{organization.id}/api-registry/grants")
    assert allowed.status_code == 200
    payload = allowed.json()
    assert len(payload) == 1
    assert payload[0]["id"] == str(grant.id)
    assert payload[0]["service_id"] == str(service.id)
    assert payload[0]["credential_present"] is True
    assert "secret_ref" not in payload[0]
    assert "must-not-persist" not in str(payload)

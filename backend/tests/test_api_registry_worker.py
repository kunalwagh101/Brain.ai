from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.api_registry import create_api_grant, create_api_service
from app.api_registry_models import APIGrantStatus
from app.api_registry_worker import run_once
from app.models import Membership, MembershipRole, Organization, User
from app.secrets import SecretStoreError


class FakeSecretStore:
    def __init__(self) -> None:
        self.values: dict[str, dict[str, str]] = {}
        self.fail_delete = False

    def store_api_credential_secret(
        self,
        *,
        organization_id,
        grant_id,
        service_key,
        credentials,
    ) -> str:
        reference = f"arn:test:{organization_id}:{service_key}:{grant_id}"
        self.values[reference] = dict(credentials)
        return reference

    def schedule_delete(self, reference: str) -> None:
        if self.fail_delete:
            raise SecretStoreError("delete failed")
        self.values.pop(reference, None)


class _SessionContext:
    def __init__(self, db: Session) -> None:
        self.db = db

    def __enter__(self) -> Session:
        return self.db

    def __exit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb


def _seed_expiring_grant(db: Session, store: FakeSecretStore):
    owner = User(email="api-worker-owner@example.com")
    organization = Organization(name="API Worker Org", slug="api-worker-org")
    db.add_all([owner, organization])
    db.flush()
    db.add(
        Membership(
            organization_id=organization.id,
            user_id=owner.id,
            role=MembershipRole.OWNER,
        )
    )
    db.commit()
    service = create_api_service(
        db,
        organization_id=organization.id,
        actor_user_id=owner.id,
        service_key="worker-service",
        display_name="Worker Service",
        provider_name="Vendor",
        base_url=None,
    )
    grant = create_api_grant(
        db,
        secret_store=store,
        organization_id=organization.id,
        actor_user_id=owner.id,
        service_id=service.id,
        grant_key="worker-grant",
        display_name="Worker Grant",
        owner_user_id=owner.id,
        environment="production",
        scopes=["read"],
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        credentials={"api_key": "secret"},
    )
    grant.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()
    return grant


def test_expiry_cleanup_failure_stays_expired_and_retries(
    db_session: Session,
    monkeypatch,
) -> None:
    store = FakeSecretStore()
    grant = _seed_expiring_grant(db_session, store)
    reference = grant.secret_ref
    assert reference is not None

    monkeypatch.setattr(
        "app.api_registry_worker.get_session_factory",
        lambda: lambda: _SessionContext(db_session),
    )
    monkeypatch.setattr("app.api_registry_worker.get_secret_store", lambda: store)
    store.fail_delete = True

    expired, cleaned, failed = run_once(batch_size=10)
    assert (expired, cleaned, failed) == (1, 0, 1)
    db_session.refresh(grant)
    assert grant.status == APIGrantStatus.EXPIRED
    assert grant.secret_ref == reference

    store.fail_delete = False
    expired, cleaned, failed = run_once(batch_size=10)
    assert (expired, cleaned, failed) == (0, 1, 0)
    db_session.refresh(grant)
    assert grant.status == APIGrantStatus.EXPIRED
    assert grant.secret_ref is None

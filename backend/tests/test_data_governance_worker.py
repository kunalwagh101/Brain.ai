from sqlalchemy.orm import Session

from app.data_governance import create_deletion_request, set_retention_policy
from app.data_governance_models import DeletionScope, DeletionStatus
from app.data_governance_worker import run_once
from app.models import Membership, MembershipRole, Organization, User


class _SessionContext:
    def __init__(self, db: Session) -> None:
        self.db = db

    def __enter__(self) -> Session:
        return self.db

    def __exit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb


def test_worker_runs_retention_and_completes_pending_deletion(
    db_session: Session,
    monkeypatch,
) -> None:
    owner = User(email="governance-worker-owner@example.com")
    organization = Organization(
        name="Governance Worker Org",
        slug="governance-worker-org",
    )
    db_session.add_all([owner, organization])
    db_session.flush()
    db_session.add(
        Membership(
            organization_id=organization.id,
            user_id=owner.id,
            role=MembershipRole.OWNER,
        )
    )
    db_session.commit()

    set_retention_policy(
        db_session,
        organization_id=organization.id,
        actor_user_id=owner.id,
        raw_event_days=None,
        derived_content_days=None,
        audit_event_days=None,
        legal_hold=False,
    )
    deletion = create_deletion_request(
        db_session,
        organization_id=organization.id,
        actor_user_id=owner.id,
        request_key="worker-delete-empty-object",
        scope=DeletionScope.SOURCE_OBJECT,
        reason="verify worker execution",
        source_provider="slack",
        object_type="message",
        object_external_id="C1:1710000000.000100",
    )

    monkeypatch.setattr(
        "app.data_governance_worker.get_session_factory",
        lambda: lambda: _SessionContext(db_session),
    )

    retention_runs, deletions_completed, failures = run_once(batch_size=10)

    assert (retention_runs, deletions_completed, failures) == (1, 1, 0)
    db_session.refresh(deletion)
    assert deletion.status == DeletionStatus.COMPLETED
    assert deletion.completion_digest is not None

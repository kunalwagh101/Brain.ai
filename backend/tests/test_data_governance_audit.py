import uuid

import pytest
from sqlalchemy.orm import Session

from app.data_governance import DataGovernanceError, append_audit_event
from app.data_governance_models import SecurityAuditEvent
from app.models import Organization, User


def test_audit_metadata_rejects_secret_shaped_fields(db_session: Session) -> None:
    actor = User(email="audit-secret-guard@example.com")
    organization = Organization(name="Audit Guard", slug="audit-guard")
    db_session.add_all([actor, organization])
    db_session.commit()

    with pytest.raises(DataGovernanceError, match="sensitive field name"):
        append_audit_event(
            db_session,
            organization_id=organization.id,
            event_key="secret-metadata-test",
            event_type="security.test",
            outcome="denied",
            actor_user_id=actor.id,
            metadata={"api_key": "must-never-persist"},
        )

    assert db_session.query(SecurityAuditEvent).count() == 0


def test_audit_actor_uuid_survives_user_row_deletion(db_session: Session) -> None:
    actor = User(email="audit-deleted-actor@example.com")
    organization = Organization(name="Audit Actor", slug="audit-actor")
    db_session.add_all([actor, organization])
    db_session.commit()
    actor_id = actor.id

    event = append_audit_event(
        db_session,
        organization_id=organization.id,
        event_key="actor-reference-test",
        event_type="security.test",
        outcome="succeeded",
        actor_user_id=actor_id,
    )
    event_id = event.id

    db_session.delete(actor)
    db_session.commit()
    db_session.expire_all()

    retained = db_session.get(SecurityAuditEvent, event_id)
    assert retained is not None
    assert retained.actor_user_id == uuid.UUID(str(actor_id))

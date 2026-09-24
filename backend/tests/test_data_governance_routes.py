from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.data_governance_models import SecurityAuditEvent
from app.main import app
from app.models import Membership, MembershipRole, Organization, User


def _seed(db: Session, suffix: str):
    owner = User(email=f"route-owner-{suffix}@example.com")
    executive = User(email=f"route-exec-{suffix}@example.com")
    member = User(email=f"route-member-{suffix}@example.com")
    organization = Organization(name=f"Route Org {suffix}", slug=f"route-org-{suffix}")
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
    db.commit()
    return organization, owner, executive, member


def test_governance_routes_separate_audit_read_from_mutation(
    db_session: Session,
    client,
) -> None:
    organization, owner, executive, member = _seed(db_session, "permissions")
    base = f"/api/v1/organizations/{organization.id}/data-governance"

    app.dependency_overrides[get_current_user] = lambda: member
    member_read = client.get(f"{base}/audit-events")
    assert member_read.status_code == 403
    denial = db_session.scalar(
        select(SecurityAuditEvent)
        .where(
            SecurityAuditEvent.organization_id == organization.id,
            SecurityAuditEvent.event_type == "authorization.denied",
        )
        .order_by(SecurityAuditEvent.created_at.desc())
        .limit(1)
    )
    assert denial is not None
    assert denial.actor_user_id == member.id
    assert denial.metadata_json["permission"] == "audit.read"

    app.dependency_overrides[get_current_user] = lambda: executive
    executive_read = client.get(f"{base}/audit-events")
    assert executive_read.status_code == 200
    executive_mutation = client.put(
        f"{base}/retention-policy",
        json={
            "raw_event_days": 30,
            "derived_content_days": 30,
            "audit_event_days": 365,
            "legal_hold": False,
        },
    )
    assert executive_mutation.status_code == 403

    app.dependency_overrides[get_current_user] = lambda: owner
    owner_mutation = client.put(
        f"{base}/retention-policy",
        json={
            "raw_event_days": 30,
            "derived_content_days": 30,
            "audit_event_days": 365,
            "legal_hold": False,
        },
        headers={"X-Request-ID": "retention-policy-test"},
    )
    assert owner_mutation.status_code == 200
    payload = owner_mutation.json()
    assert payload["raw_event_days"] == 30
    assert payload["derived_content_days"] == 30
    assert payload["audit_event_days"] == 365
    assert payload["legal_hold"] is False

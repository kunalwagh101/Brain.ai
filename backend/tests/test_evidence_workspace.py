import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.evidence_models import EvidenceSource, EvidenceSourceStatus
from app.main import app
from app.models import (
    IntegrationConnection,
    IntegrationStatus,
    Membership,
    MembershipRole,
    Organization,
    User,
)


def _seed(db: Session, suffix: str):
    owner = User(email=f"evidence-workspace-owner-{suffix}@example.com")
    member = User(email=f"evidence-workspace-member-{suffix}@example.com")
    other = User(email=f"evidence-workspace-other-{suffix}@example.com")
    organization = Organization(
        name=f"Evidence workspace {suffix}",
        slug=f"evidence-workspace-{suffix}",
    )
    db.add_all([owner, member, other, organization])
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
            Membership(
                organization_id=organization.id,
                user_id=other.id,
                role=MembershipRole.MEMBER,
            ),
        ]
    )
    db.commit()
    return organization, owner, member, other


def _upload(client, organization, user, *, title: str, visibility: str, key: str):
    app.dependency_overrides[get_current_user] = lambda: user
    return client.post(
        f"/api/v1/organizations/{organization.id}/evidence/uploads",
        headers={"Idempotency-Key": key},
        data={
            "kind": "document",
            "title": title,
            "visibility": visibility,
        },
        files={"file": (f"{key}.txt", f"Evidence for {title}".encode(), "text/plain")},
    )


def test_workspace_list_limit_is_applied_after_permission_filter(
    db_session: Session,
    client,
) -> None:
    organization, _, member, other = _seed(db_session, "limit")
    visible = _upload(
        client,
        organization,
        member,
        title="Visible source",
        visibility="organization",
        key="visible-source",
    )
    hidden = _upload(
        client,
        organization,
        other,
        title="Hidden restricted source",
        visibility="restricted",
        key="hidden-source",
    )
    assert visible.status_code == 201
    assert hidden.status_code == 201

    visible_source = db_session.get(EvidenceSource, uuid.UUID(visible.json()["id"]))
    hidden_source = db_session.get(EvidenceSource, uuid.UUID(hidden.json()["id"]))
    assert visible_source is not None
    assert hidden_source is not None
    base = datetime.now(UTC)
    visible_source.created_at = base
    hidden_source.created_at = base + timedelta(seconds=1)
    db_session.commit()

    app.dependency_overrides[get_current_user] = lambda: member
    response = client.get(
        f"/api/v1/organizations/{organization.id}/evidence",
        params={"limit": 1},
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["id"] == visible.json()["id"]
    assert payload[0]["title"] == "Visible source"
    assert payload[0]["retrieval_available"] is True


def test_workspace_evidence_exposes_server_computed_delete_capability(
    db_session: Session,
    client,
) -> None:
    organization, owner, member, other = _seed(db_session, "delete-capability")
    uploaded = _upload(
        client,
        organization,
        member,
        title="Lifecycle source",
        visibility="organization",
        key="lifecycle-source",
    )
    assert uploaded.status_code == 201
    source_id = uploaded.json()["id"]
    assert uploaded.json()["can_delete"] is True
    assert uploaded.json()["retrieval_available"] is True

    app.dependency_overrides[get_current_user] = lambda: other
    other_read = client.get(f"/api/v1/organizations/{organization.id}/evidence/{source_id}")
    assert other_read.status_code == 200
    assert other_read.json()["can_delete"] is False

    forged_delete = client.delete(
        f"/api/v1/organizations/{organization.id}/evidence/{source_id}"
    )
    assert forged_delete.status_code == 404
    source = db_session.get(EvidenceSource, uuid.UUID(source_id))
    assert source is not None
    assert source.status == EvidenceSourceStatus.ACTIVE

    app.dependency_overrides[get_current_user] = lambda: owner
    owner_read = client.get(f"/api/v1/organizations/{organization.id}/evidence/{source_id}")
    assert owner_read.status_code == 200
    assert owner_read.json()["can_delete"] is True

    app.dependency_overrides[get_current_user] = lambda: member
    deleted = client.delete(f"/api/v1/organizations/{organization.id}/evidence/{source_id}")
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "deleted"
    assert deleted.json()["can_delete"] is False
    assert deleted.json()["retrieval_available"] is False


def test_revoked_integration_is_not_presented_as_retrievable_or_reactivated(
    db_session: Session,
    client,
) -> None:
    organization, _, member, _ = _seed(db_session, "revoked")
    uploaded = _upload(
        client,
        organization,
        member,
        title="Revoked source",
        visibility="organization",
        key="revoked-source",
    )
    assert uploaded.status_code == 201
    source = db_session.get(EvidenceSource, uuid.UUID(uploaded.json()["id"]))
    assert source is not None
    connection = db_session.get(IntegrationConnection, source.integration_connection_id)
    assert connection is not None
    connection.status = IntegrationStatus.REVOKED
    connection.revoked_at = datetime.now(UTC)
    db_session.commit()

    app.dependency_overrides[get_current_user] = lambda: member
    response = client.get(f"/api/v1/organizations/{organization.id}/evidence")
    assert response.status_code == 200
    payload = next(item for item in response.json() if item["id"] == str(source.id))
    assert payload["status"] == "active"
    assert payload["integration_status"] == "revoked"
    assert payload["retrieval_available"] is False

    blocked_upload = _upload(
        client,
        organization,
        member,
        title="Must not reactivate",
        visibility="organization",
        key="must-not-reactivate",
    )
    assert blocked_upload.status_code == 409
    db_session.refresh(connection)
    assert connection.status == IntegrationStatus.REVOKED


def test_cross_tenant_source_id_does_not_bypass_organization_boundary(
    db_session: Session,
    client,
) -> None:
    organization_a, _, member_a, _ = _seed(db_session, "tenant-a")
    _, _, member_b, _ = _seed(db_session, "tenant-b")
    uploaded = _upload(
        client,
        organization_a,
        member_a,
        title="Tenant A source",
        visibility="organization",
        key="tenant-a-source",
    )
    assert uploaded.status_code == 201
    source_id = uploaded.json()["id"]

    app.dependency_overrides[get_current_user] = lambda: member_b
    read = client.get(
        f"/api/v1/organizations/{organization_a.id}/evidence/{source_id}"
    )
    delete = client.delete(
        f"/api/v1/organizations/{organization_a.id}/evidence/{source_id}"
    )
    listing = client.get(f"/api/v1/organizations/{organization_a.id}/evidence")

    assert read.status_code == 404
    assert delete.status_code == 404
    assert listing.status_code == 404

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.main import app
from app.models import Membership, MembershipRole, Organization, User
from app.work_graph_models import WorkGraphNode, WorkGraphNodeType


def _seed_member(db: Session):
    user = User(email=f"workspace-{uuid.uuid4()}@example.com")
    organization = Organization(
        name="Workspace Navigation",
        slug=f"workspace-{uuid.uuid4().hex[:8]}",
    )
    db.add_all([user, organization])
    db.flush()
    db.add(
        Membership(
            organization_id=organization.id,
            user_id=user.id,
            role=MembershipRole.MEMBER,
        )
    )
    db.commit()
    return organization, user


def test_workspace_navigation_returns_only_visible_projects_and_tracks(
    client: TestClient,
    db_session: Session,
) -> None:
    organization, user = _seed_member(db_session)
    visible_project = WorkGraphNode(
        organization_id=organization.id,
        node_type=WorkGraphNodeType.PROJECT,
        stable_key=f"project:visible:{uuid.uuid4()}",
        display_name="Visible Project",
        source_visibility="organization",
        source_acl=[],
        attributes={"provider": "github"},
    )
    visible_track = WorkGraphNode(
        organization_id=organization.id,
        node_type=WorkGraphNodeType.TRACK,
        stable_key=f"track:visible:{uuid.uuid4()}",
        display_name="Visible Track",
        source_visibility="organization",
        source_acl=[],
        attributes={"provider": "slack"},
    )
    restricted_track = WorkGraphNode(
        organization_id=organization.id,
        node_type=WorkGraphNodeType.TRACK,
        stable_key=f"track:restricted:{uuid.uuid4()}",
        display_name="Secret Track",
        source_visibility="restricted",
        source_acl=[],
        attributes={"provider": "generic_upload"},
    )
    db_session.add_all([visible_project, visible_track, restricted_track])
    db_session.commit()

    app.dependency_overrides[get_current_user] = lambda: user
    try:
        response = client.get(
            f"/api/v1/organizations/{organization.id}/workspace-navigation"
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    payload = response.json()
    assert [item["display_name"] for item in payload["projects"]] == ["Visible Project"]
    assert [item["display_name"] for item in payload["tracks"]] == ["Visible Track"]
    assert "Secret Track" not in response.text


def test_workspace_navigation_hides_other_tenant(
    client: TestClient,
    db_session: Session,
) -> None:
    organization, _ = _seed_member(db_session)
    other_organization, outsider = _seed_member(db_session)

    app.dependency_overrides[get_current_user] = lambda: outsider
    try:
        response = client.get(
            f"/api/v1/organizations/{organization.id}/workspace-navigation"
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 404
    assert response.json()["detail"] == "Organization not found"
    assert str(other_organization.id) not in response.text

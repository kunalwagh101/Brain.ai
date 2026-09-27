import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.main import app
from app.models import Membership, MembershipRole, Organization, User
from app.work_graph import create_manual_edge, create_manual_node
from app.work_graph_models import WorkGraphEdgeType, WorkGraphNodeType


def _seed_project(db: Session):
    user = User(email=f"project-route-{uuid.uuid4()}@example.com")
    organization = Organization(
        name="Project Route",
        slug=f"project-route-{uuid.uuid4().hex[:8]}",
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
    project = create_manual_node(
        db,
        organization_id=organization.id,
        node_type=WorkGraphNodeType.PROJECT,
        key=f"project-{uuid.uuid4().hex[:8]}",
        display_name="Atlas",
        actor_user_id=user.id,
    )
    work_item = create_manual_node(
        db,
        organization_id=organization.id,
        node_type=WorkGraphNodeType.WORK_ITEM,
        key=f"item-{uuid.uuid4().hex[:8]}",
        display_name="API release",
        actor_user_id=user.id,
    )
    create_manual_edge(
        db,
        organization_id=organization.id,
        source_node_id=project.id,
        target_node_id=work_item.id,
        edge_type=WorkGraphEdgeType.CONTAINS,
        actor_user_id=user.id,
        reason="Atlas release work",
    )
    return organization, user, project, work_item


def test_project_status_route_serializes_structured_progress(
    client: TestClient,
    db_session: Session,
) -> None:
    organization, user, project, work_item = _seed_project(db_session)
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        response = client.put(
            (
                f"/api/v1/organizations/{organization.id}/project-status/"
                f"{project.id}/progress-items/{work_item.id}"
            ),
            json={"state": "done", "weight": 2, "note": "Reviewed"},
        )
        listed = client.get(
            f"/api/v1/organizations/{organization.id}/project-status"
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["project_node_id"] == str(project.id)
    assert payload["progress_percent"] == 100.0
    assert payload["progress_basis"] == "visible_configured_work_items"
    assert payload["status"] == "done"
    assert payload["progress_items"][0]["state"] == "done"
    assert payload["progress_items"][0]["weight"] == 2

    assert listed.status_code == 200
    assert listed.json()[0]["project_node_id"] == str(project.id)


def test_project_status_route_hides_other_tenant_project(
    client: TestClient,
    db_session: Session,
) -> None:
    organization, _, project, _ = _seed_project(db_session)
    outsider = User(email=f"project-outsider-{uuid.uuid4()}@example.com")
    other = Organization(
        name="Other Project Org",
        slug=f"project-other-{uuid.uuid4().hex[:8]}",
    )
    db_session.add_all([outsider, other])
    db_session.flush()
    db_session.add(
        Membership(
            organization_id=other.id,
            user_id=outsider.id,
            role=MembershipRole.MEMBER,
        )
    )
    db_session.commit()

    app.dependency_overrides[get_current_user] = lambda: outsider
    try:
        response = client.get(
            f"/api/v1/organizations/{organization.id}/project-status/{project.id}"
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 404
    assert response.json()["detail"] == "Organization not found"

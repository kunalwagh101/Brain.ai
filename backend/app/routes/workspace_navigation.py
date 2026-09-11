import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.permissions import AuthorizationContext, Permission, require_organization_permission
from app.work_graph import node_visible_to_user
from app.work_graph_models import WorkGraphNode, WorkGraphNodeType

router = APIRouter(
    prefix="/organizations/{organization_id}/workspace-navigation",
    tags=["workspace-navigation"],
)
_read_workspace = require_organization_permission(Permission.RESOURCE_READ)


class WorkspaceNavigationNode(BaseModel):
    node_id: uuid.UUID
    kind: Literal["project", "track"]
    display_name: str | None
    source_visibility: str
    provider: str | None


class WorkspaceNavigationRead(BaseModel):
    projects: list[WorkspaceNavigationNode]
    tracks: list[WorkspaceNavigationNode]


def _navigation_node(node: WorkGraphNode) -> WorkspaceNavigationNode:
    provider = node.attributes.get("provider")
    return WorkspaceNavigationNode(
        node_id=node.id,
        kind="project" if node.node_type == WorkGraphNodeType.PROJECT else "track",
        display_name=node.display_name,
        source_visibility=node.source_visibility,
        provider=provider if isinstance(provider, str) else None,
    )


@router.get("", response_model=WorkspaceNavigationRead)
def workspace_navigation(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read_workspace)],
    db: Annotated[Session, Depends(get_db)],
    limit_per_kind: Annotated[int, Query(ge=1, le=500)] = 200,
) -> WorkspaceNavigationRead:
    candidates = list(
        db.scalars(
            select(WorkGraphNode)
            .where(
                WorkGraphNode.organization_id == organization_id,
                WorkGraphNode.node_type.in_(
                    (WorkGraphNodeType.PROJECT, WorkGraphNodeType.TRACK)
                ),
            )
            .order_by(WorkGraphNode.display_name, WorkGraphNode.id)
        )
    )

    projects: list[WorkspaceNavigationNode] = []
    tracks: list[WorkspaceNavigationNode] = []
    for node in candidates:
        if not node_visible_to_user(
            db,
            node,
            user_id=authorization.user_id,
            role=authorization.role,
        ):
            continue

        target = projects if node.node_type == WorkGraphNodeType.PROJECT else tracks
        if len(target) >= limit_per_kind:
            continue
        target.append(_navigation_node(node))

    return WorkspaceNavigationRead(projects=projects, tracks=tracks)

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.permissions import AuthorizationContext, Permission, require_organization_permission
from app.work_graph import (
    WorkGraphError,
    create_manual_edge,
    create_manual_node,
    reconcile_work_graph,
    traverse_work_graph,
)
from app.work_graph_models import WorkGraphEdge, WorkGraphEdgeType, WorkGraphNode, WorkGraphNodeType

router = APIRouter(
    prefix="/organizations/{organization_id}/work-graph",
    tags=["work-graph"],
)
_read_graph = require_organization_permission(Permission.RESOURCE_READ)
_write_graph = require_organization_permission(Permission.RESOURCE_WRITE)


class GraphNodeCreate(BaseModel):
    node_type: WorkGraphNodeType
    key: str = Field(min_length=1, max_length=255, pattern=r"^[A-Za-z0-9._:-]+$")
    display_name: str = Field(min_length=1, max_length=512)


class GraphEdgeCreate(BaseModel):
    source_node_id: uuid.UUID
    target_node_id: uuid.UUID
    edge_type: WorkGraphEdgeType
    reason: str = Field(min_length=1, max_length=500)


class GraphNodeRead(BaseModel):
    id: uuid.UUID
    node_type: WorkGraphNodeType
    stable_key: str
    display_name: str | None
    source_visibility: str
    canonical_event_id: uuid.UUID | None
    source_identity_id: uuid.UUID | None
    user_id: uuid.UUID | None
    attributes: dict[str, object]

    model_config = {"from_attributes": True}


class GraphEdgeRead(BaseModel):
    id: uuid.UUID
    source_node_id: uuid.UUID
    target_node_id: uuid.UUID
    edge_type: WorkGraphEdgeType
    source_kind: str
    evidence_state: str
    confidence: float
    provenance: dict[str, object]
    canonical_event_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class GraphTraversalRead(BaseModel):
    nodes: list[GraphNodeRead]
    edges: list[GraphEdgeRead]


class GraphReconcileRead(BaseModel):
    processed: int
    remaining: int


@router.post("/nodes", response_model=GraphNodeRead, status_code=status.HTTP_201_CREATED)
def create_node(
    organization_id: uuid.UUID,
    payload: GraphNodeCreate,
    authorization: Annotated[AuthorizationContext, Depends(_write_graph)],
    db: Annotated[Session, Depends(get_db)],
) -> WorkGraphNode:
    try:
        return create_manual_node(
            db,
            organization_id=organization_id,
            node_type=payload.node_type,
            key=payload.key,
            display_name=payload.display_name,
            actor_user_id=authorization.user_id,
        )
    except WorkGraphError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/edges", response_model=GraphEdgeRead, status_code=status.HTTP_201_CREATED)
def create_edge(
    organization_id: uuid.UUID,
    payload: GraphEdgeCreate,
    authorization: Annotated[AuthorizationContext, Depends(_write_graph)],
    db: Annotated[Session, Depends(get_db)],
) -> WorkGraphEdge:
    try:
        return create_manual_edge(
            db,
            organization_id=organization_id,
            source_node_id=payload.source_node_id,
            target_node_id=payload.target_node_id,
            edge_type=payload.edge_type,
            actor_user_id=authorization.user_id,
            reason=payload.reason,
        )
    except WorkGraphError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/nodes/{node_id}/neighbors", response_model=GraphTraversalRead)
def graph_neighbors(
    organization_id: uuid.UUID,
    node_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read_graph)],
    db: Annotated[Session, Depends(get_db)],
    depth: Annotated[int, Query(ge=0, le=3)] = 1,
) -> GraphTraversalRead:
    result = traverse_work_graph(
        db,
        organization_id=organization_id,
        start_node_id=node_id,
        user_id=authorization.user_id,
        role=authorization.role,
        depth=depth,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Graph node not found",
        )
    nodes, edges = result
    return GraphTraversalRead(
        nodes=[GraphNodeRead.model_validate(node) for node in nodes],
        edges=[GraphEdgeRead.model_validate(edge) for edge in edges],
    )


@router.post("/reconcile", response_model=GraphReconcileRead)
def reconcile_graph(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_write_graph)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> GraphReconcileRead:
    del authorization
    processed, remaining = reconcile_work_graph(
        db,
        organization_id=organization_id,
        limit=limit,
    )
    return GraphReconcileRead(processed=processed, remaining=remaining)

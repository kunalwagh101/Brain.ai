import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.data_governance import append_audit_event
from app.decision_memory import list_visible_memory_candidates
from app.decision_memory_models import DecisionMemoryCandidate, MemoryKind, MemoryState
from app.models import MembershipRole
from app.project_status_models import ProjectProgressItem, ProjectWorkState
from app.search import _base_query as _authorized_search_documents_query
from app.search_models import SearchDocument
from app.work_graph import node_visible_to_user, traverse_work_graph
from app.work_graph_models import WorkGraphEdge, WorkGraphEdgeType, WorkGraphNode, WorkGraphNodeType


class ProjectStatusError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ProjectEvidence:
    document_id: uuid.UUID
    canonical_event_id: uuid.UUID
    work_graph_node_id: uuid.UUID | None
    source_provider: str
    object_type: str
    object_external_id: str
    title: str
    occurred_at: datetime | None
    provenance: dict[str, object]


@dataclass(frozen=True, slots=True)
class ProjectMemory:
    id: uuid.UUID
    kind: MemoryKind
    state: MemoryState
    summary: str
    confidence: float
    work_graph_node_id: uuid.UUID | None
    canonical_event_id: uuid.UUID
    search_document_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class ProjectProgress:
    id: uuid.UUID
    work_item_node_id: uuid.UUID
    work_item_name: str
    state: ProjectWorkState
    weight: int
    note: str | None
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ProjectStatusSnapshot:
    project_node_id: uuid.UUID
    project_name: str
    progress_percent: float | None
    progress_basis: str
    status: str
    progress_items: tuple[ProjectProgress, ...]
    active_blockers: tuple[ProjectMemory, ...]
    confirmed_decisions: tuple[ProjectMemory, ...]
    candidate_memories: tuple[ProjectMemory, ...]
    evidence: tuple[ProjectEvidence, ...]


def _visible_project(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    role: MembershipRole,
    project_node_id: uuid.UUID,
) -> WorkGraphNode | None:
    project = db.scalar(
        select(WorkGraphNode).where(
            WorkGraphNode.id == project_node_id,
            WorkGraphNode.organization_id == organization_id,
            WorkGraphNode.node_type == WorkGraphNodeType.PROJECT,
        )
    )
    if project is None:
        return None
    if not node_visible_to_user(db, project, user_id=user_id, role=role):
        return None
    return project


def _visible_work_item(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    role: MembershipRole,
    work_item_node_id: uuid.UUID,
) -> WorkGraphNode | None:
    work_item = db.scalar(
        select(WorkGraphNode).where(
            WorkGraphNode.id == work_item_node_id,
            WorkGraphNode.organization_id == organization_id,
            WorkGraphNode.node_type == WorkGraphNodeType.WORK_ITEM,
        )
    )
    if work_item is None:
        return None
    if not node_visible_to_user(db, work_item, user_id=user_id, role=role):
        return None
    return work_item


def _project_links_work_item(
    db: Session,
    *,
    organization_id: uuid.UUID,
    project_node_id: uuid.UUID,
    work_item_node_id: uuid.UUID,
) -> bool:
    allowed_types = (
        WorkGraphEdgeType.CONTAINS,
        WorkGraphEdgeType.RELATED_TO,
        WorkGraphEdgeType.DEPENDS_ON,
    )
    edge = db.scalar(
        select(WorkGraphEdge.id)
        .where(
            WorkGraphEdge.organization_id == organization_id,
            WorkGraphEdge.edge_type.in_(allowed_types),
            or_(
                (
                    (WorkGraphEdge.source_node_id == project_node_id)
                    & (WorkGraphEdge.target_node_id == work_item_node_id)
                ),
                (
                    (WorkGraphEdge.source_node_id == work_item_node_id)
                    & (WorkGraphEdge.target_node_id == project_node_id)
                ),
            ),
        )
        .limit(1)
    )
    return edge is not None


def upsert_project_progress_item(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    role: MembershipRole,
    project_node_id: uuid.UUID,
    work_item_node_id: uuid.UUID,
    state: ProjectWorkState,
    weight: int,
    note: str | None,
    request_id: str | None = None,
) -> ProjectProgressItem:
    project = _visible_project(
        db,
        organization_id=organization_id,
        user_id=user_id,
        role=role,
        project_node_id=project_node_id,
    )
    work_item = _visible_work_item(
        db,
        organization_id=organization_id,
        user_id=user_id,
        role=role,
        work_item_node_id=work_item_node_id,
    )
    if project is None or work_item is None:
        raise ProjectStatusError("Project or work item not found")
    if not _project_links_work_item(
        db,
        organization_id=organization_id,
        project_node_id=project.id,
        work_item_node_id=work_item.id,
    ):
        raise ProjectStatusError("Work item is not linked to this project")
    if weight < 1 or weight > 10_000:
        raise ProjectStatusError("Weight must be between 1 and 10000")
    normalized_note = " ".join(note.strip().split())[:1000] if note else None

    item = db.scalar(
        select(ProjectProgressItem)
        .where(
            ProjectProgressItem.organization_id == organization_id,
            ProjectProgressItem.project_node_id == project.id,
            ProjectProgressItem.work_item_node_id == work_item.id,
        )
        .with_for_update()
    )
    action = "updated"
    if item is None:
        action = "created"
        item = ProjectProgressItem(
            organization_id=organization_id,
            project_node_id=project.id,
            work_item_node_id=work_item.id,
            updated_by_user_id=user_id,
        )
        db.add(item)
    item.state = state
    item.weight = weight
    item.note = normalized_note
    item.updated_by_user_id = user_id
    db.flush()
    append_audit_event(
        db,
        organization_id=organization_id,
        event_key=f"project.progress.{action}:{item.id}:{uuid.uuid4()}",
        event_type=f"project.progress.{action}",
        outcome="succeeded",
        actor_user_id=user_id,
        resource_type="project_progress_item",
        resource_id=item.id,
        request_id=request_id,
        metadata={
            "project_node_id": project.id,
            "work_item_node_id": work_item.id,
            "state": state.value,
            "weight": weight,
        },
    )
    db.refresh(item)
    return item


def delete_project_progress_item(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    role: MembershipRole,
    project_node_id: uuid.UUID,
    work_item_node_id: uuid.UUID,
    request_id: str | None = None,
) -> None:
    if _visible_project(
        db,
        organization_id=organization_id,
        user_id=user_id,
        role=role,
        project_node_id=project_node_id,
    ) is None:
        raise ProjectStatusError("Project or work item not found")
    item = db.scalar(
        select(ProjectProgressItem)
        .where(
            ProjectProgressItem.organization_id == organization_id,
            ProjectProgressItem.project_node_id == project_node_id,
            ProjectProgressItem.work_item_node_id == work_item_node_id,
        )
        .with_for_update()
    )
    if item is None:
        raise ProjectStatusError("Project progress item not found")
    item_id = item.id
    db.delete(item)
    db.flush()
    append_audit_event(
        db,
        organization_id=organization_id,
        event_key=f"project.progress.deleted:{item_id}:{uuid.uuid4()}",
        event_type="project.progress.deleted",
        outcome="succeeded",
        actor_user_id=user_id,
        resource_type="project_progress_item",
        resource_id=item_id,
        request_id=request_id,
        metadata={
            "project_node_id": project_node_id,
            "work_item_node_id": work_item_node_id,
        },
    )


def _visible_progress_items(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    role: MembershipRole,
    project_node_id: uuid.UUID,
) -> list[tuple[ProjectProgressItem, WorkGraphNode]]:
    rows = list(
        db.scalars(
            select(ProjectProgressItem).where(
                ProjectProgressItem.organization_id == organization_id,
                ProjectProgressItem.project_node_id == project_node_id,
            )
        )
    )
    visible: list[tuple[ProjectProgressItem, WorkGraphNode]] = []
    for row in rows:
        node = _visible_work_item(
            db,
            organization_id=organization_id,
            user_id=user_id,
            role=role,
            work_item_node_id=row.work_item_node_id,
        )
        if node is not None:
            visible.append((row, node))
    return visible


def _visible_project_evidence_node_ids(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    role: MembershipRole,
    project_node_id: uuid.UUID,
) -> set[uuid.UUID]:
    traversal = traverse_work_graph(
        db,
        organization_id=organization_id,
        start_node_id=project_node_id,
        user_id=user_id,
        role=role,
        depth=2,
        max_nodes=500,
    )
    if traversal is None:
        return set()
    nodes, _ = traversal
    return {
        node.id
        for node in nodes
        if node.node_type == WorkGraphNodeType.EVIDENCE
    }


def _visible_project_evidence(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    evidence_node_ids: set[uuid.UUID],
) -> list[SearchDocument]:
    if not evidence_node_ids:
        return []
    return list(
        db.scalars(
            _authorized_search_documents_query(
                db,
                organization_id=organization_id,
                user_id=user_id,
            )
            .where(SearchDocument.work_graph_node_id.in_(evidence_node_ids))
            .order_by(SearchDocument.occurred_at.desc(), SearchDocument.id.desc())
        )
    )


def _memory_view(candidate: DecisionMemoryCandidate) -> ProjectMemory:
    return ProjectMemory(
        id=candidate.id,
        kind=candidate.kind,
        state=candidate.state,
        summary=candidate.summary,
        confidence=candidate.confidence,
        work_graph_node_id=candidate.work_graph_node_id,
        canonical_event_id=candidate.canonical_event_id,
        search_document_id=candidate.search_document_id,
    )


def build_project_status(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    role: MembershipRole,
    project_node_id: uuid.UUID,
) -> ProjectStatusSnapshot | None:
    project = _visible_project(
        db,
        organization_id=organization_id,
        user_id=user_id,
        role=role,
        project_node_id=project_node_id,
    )
    if project is None:
        return None

    visible_progress = _visible_progress_items(
        db,
        organization_id=organization_id,
        user_id=user_id,
        role=role,
        project_node_id=project.id,
    )
    evidence_node_ids = _visible_project_evidence_node_ids(
        db,
        organization_id=organization_id,
        user_id=user_id,
        role=role,
        project_node_id=project.id,
    )
    evidence_documents = _visible_project_evidence(
        db,
        organization_id=organization_id,
        user_id=user_id,
        evidence_node_ids=evidence_node_ids,
    )
    visible_evidence_ids = {
        document.work_graph_node_id
        for document in evidence_documents
        if document.work_graph_node_id is not None
    }

    memories = list_visible_memory_candidates(
        db,
        organization_id=organization_id,
        user_id=user_id,
        kind=None,
        state=None,
        limit=500,
    )
    project_memories = [
        candidate
        for candidate in memories
        if candidate.work_graph_node_id in visible_evidence_ids
    ]
    blockers = tuple(
        _memory_view(candidate)
        for candidate in project_memories
        if candidate.kind == MemoryKind.BLOCKER
        and candidate.state == MemoryState.CONFIRMED
    )
    decisions = tuple(
        _memory_view(candidate)
        for candidate in project_memories
        if candidate.kind == MemoryKind.DECISION
        and candidate.state == MemoryState.CONFIRMED
    )
    candidates = tuple(
        _memory_view(candidate)
        for candidate in project_memories
        if candidate.state == MemoryState.CANDIDATE
    )

    progress_items = tuple(
        ProjectProgress(
            id=row.id,
            work_item_node_id=node.id,
            work_item_name=node.display_name or node.stable_key,
            state=row.state,
            weight=row.weight,
            note=row.note,
            updated_at=row.updated_at,
        )
        for row, node in visible_progress
    )
    if progress_items:
        total_weight = sum(item.weight for item in progress_items)
        done_weight = sum(
            item.weight for item in progress_items if item.state == ProjectWorkState.DONE
        )
        progress_percent = round((done_weight / total_weight) * 100.0, 2)
        progress_basis = "visible_configured_work_items"
    else:
        progress_percent = None
        progress_basis = "unconfigured"

    if blockers or any(item.state == ProjectWorkState.BLOCKED for item in progress_items):
        status = "blocked"
    elif not progress_items:
        status = "unconfigured"
    elif all(item.state == ProjectWorkState.DONE for item in progress_items):
        status = "done"
    elif any(
        item.state in {ProjectWorkState.IN_PROGRESS, ProjectWorkState.DONE}
        for item in progress_items
    ):
        status = "in_progress"
    else:
        status = "not_started"

    evidence = tuple(
        ProjectEvidence(
            document_id=document.id,
            canonical_event_id=document.canonical_event_id,
            work_graph_node_id=document.work_graph_node_id,
            source_provider=document.source_provider,
            object_type=document.object_type,
            object_external_id=document.object_external_id,
            title=document.title,
            occurred_at=document.occurred_at,
            provenance=dict(document.provenance),
        )
        for document in evidence_documents
    )
    return ProjectStatusSnapshot(
        project_node_id=project.id,
        project_name=project.display_name or project.stable_key,
        progress_percent=progress_percent,
        progress_basis=progress_basis,
        status=status,
        progress_items=progress_items,
        active_blockers=blockers,
        confirmed_decisions=decisions,
        candidate_memories=candidates,
        evidence=evidence,
    )


def list_project_statuses(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    role: MembershipRole,
    limit: int,
) -> list[ProjectStatusSnapshot]:
    projects = list(
        db.scalars(
            select(WorkGraphNode)
            .where(
                WorkGraphNode.organization_id == organization_id,
                WorkGraphNode.node_type == WorkGraphNodeType.PROJECT,
            )
            .order_by(WorkGraphNode.display_name, WorkGraphNode.id)
            .limit(limit)
        )
    )
    snapshots: list[ProjectStatusSnapshot] = []
    for project in projects:
        if not node_visible_to_user(db, project, user_id=user_id, role=role):
            continue
        snapshot = build_project_status(
            db,
            organization_id=organization_id,
            user_id=user_id,
            role=role,
            project_node_id=project.id,
        )
        if snapshot is not None:
            snapshots.append(snapshot)
    return snapshots

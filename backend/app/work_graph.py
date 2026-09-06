import uuid
from collections import deque

from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    CanonicalEvent,
    MembershipRole,
    ResourceAccessLevel,
    ResourceGrant,
    SlackChannelAuthorization,
    SourceIdentity,
    User,
)
from app.work_graph_models import (
    WorkGraphEdge,
    WorkGraphEdgeSource,
    WorkGraphEdgeType,
    WorkGraphEvidenceState,
    WorkGraphNode,
    WorkGraphNodeType,
)

PUBLIC_VISIBILITIES = frozenset({"organization", "public_channel", "public_repository"})
ADMIN_ROLES = frozenset({MembershipRole.OWNER, MembershipRole.ADMIN})
MANUAL_NODE_TYPES = frozenset(
    {
        WorkGraphNodeType.PROJECT,
        WorkGraphNodeType.TRACK,
        WorkGraphNodeType.WORK_ITEM,
    }
)
MANUAL_EDGE_TYPES = frozenset(
    {
        WorkGraphEdgeType.CONTAINS,
        WorkGraphEdgeType.DEPENDS_ON,
        WorkGraphEdgeType.RELATED_TO,
    }
)


class WorkGraphError(ValueError):
    """Raised when a graph mutation would violate graph or tenant invariants."""


def _visibility_rank(value: str) -> int:
    if value in PUBLIC_VISIBILITIES:
        return 0
    if value == "private_channel":
        return 1
    return 2


def _merge_visibility(existing: str, incoming: str) -> str:
    return incoming if _visibility_rank(incoming) > _visibility_rank(existing) else existing


def _get_or_create_node(
    db: Session,
    *,
    organization_id: uuid.UUID,
    node_type: WorkGraphNodeType,
    stable_key: str,
    display_name: str | None = None,
    canonical_event_id: uuid.UUID | None = None,
    source_identity_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    source_visibility: str = "organization",
    source_acl: list[str] | None = None,
    attributes: dict[str, object] | None = None,
) -> WorkGraphNode:
    node = db.scalar(
        select(WorkGraphNode).where(
            WorkGraphNode.organization_id == organization_id,
            WorkGraphNode.stable_key == stable_key,
        )
    )
    if node is None:
        node = WorkGraphNode(
            organization_id=organization_id,
            node_type=node_type,
            stable_key=stable_key,
            display_name=display_name,
            canonical_event_id=canonical_event_id,
            source_identity_id=source_identity_id,
            user_id=user_id,
            source_visibility=source_visibility,
            source_acl=sorted(set(source_acl or [])),
            attributes=attributes or {},
        )
        try:
            with db.begin_nested():
                db.add(node)
                db.flush()
        except IntegrityError:
            node = db.scalar(
                select(WorkGraphNode).where(
                    WorkGraphNode.organization_id == organization_id,
                    WorkGraphNode.stable_key == stable_key,
                )
            )
            if node is None:
                raise

    if node.node_type != node_type:
        raise WorkGraphError("Stable graph key cannot change node type")
    if display_name:
        node.display_name = display_name
    node.source_visibility = _merge_visibility(
        node.source_visibility,
        source_visibility,
    )
    if source_acl:
        node.source_acl = sorted(set(node.source_acl) | set(source_acl))
    if attributes:
        node.attributes = {**node.attributes, **attributes}
    if canonical_event_id is not None:
        node.canonical_event_id = canonical_event_id
    if source_identity_id is not None:
        node.source_identity_id = source_identity_id
    if user_id is not None:
        node.user_id = user_id
    return node


def _get_or_create_edge(
    db: Session,
    *,
    organization_id: uuid.UUID,
    source_node: WorkGraphNode,
    target_node: WorkGraphNode,
    edge_type: WorkGraphEdgeType,
    source_kind: WorkGraphEdgeSource,
    evidence_state: WorkGraphEvidenceState,
    confidence: float,
    provenance_key: str,
    provenance: dict[str, object],
    canonical_event_id: uuid.UUID | None = None,
    created_by_user_id: uuid.UUID | None = None,
) -> WorkGraphEdge:
    if (
        source_node.organization_id != organization_id
        or target_node.organization_id != organization_id
    ):
        raise WorkGraphError("Cross-tenant graph edges are prohibited")

    edge = db.scalar(
        select(WorkGraphEdge).where(
            WorkGraphEdge.organization_id == organization_id,
            WorkGraphEdge.provenance_key == provenance_key,
        )
    )
    if edge is None:
        edge = WorkGraphEdge(
            organization_id=organization_id,
            source_node_id=source_node.id,
            target_node_id=target_node.id,
            edge_type=edge_type,
            source_kind=source_kind,
            evidence_state=evidence_state,
            confidence=confidence,
            provenance_key=provenance_key,
            provenance=provenance,
            canonical_event_id=canonical_event_id,
            created_by_user_id=created_by_user_id,
        )
        try:
            with db.begin_nested():
                db.add(edge)
                db.flush()
        except IntegrityError:
            edge = db.scalar(
                select(WorkGraphEdge).where(
                    WorkGraphEdge.organization_id == organization_id,
                    WorkGraphEdge.provenance_key == provenance_key,
                )
            )
            if edge is None:
                raise

    if (
        edge.source_node_id != source_node.id
        or edge.target_node_id != target_node.id
        or edge.edge_type != edge_type
    ):
        raise WorkGraphError("Provenance key already identifies a different graph edge")
    return edge


def _canonical_edge(
    db: Session,
    *,
    event: CanonicalEvent,
    source_node: WorkGraphNode,
    target_node: WorkGraphNode,
    edge_type: WorkGraphEdgeType,
) -> WorkGraphEdge:
    provenance_key = (
        f"canonical:{event.id}:{edge_type.value}:{source_node.id}:{target_node.id}"
    )
    return _get_or_create_edge(
        db,
        organization_id=event.organization_id,
        source_node=source_node,
        target_node=target_node,
        edge_type=edge_type,
        source_kind=WorkGraphEdgeSource.CANONICAL,
        evidence_state=WorkGraphEvidenceState.VERIFIED,
        confidence=1.0,
        provenance_key=provenance_key,
        provenance={
            "canonical_event_id": str(event.id),
            "source_provider": event.source_provider,
            "source_event_id": event.source_event_id,
        },
        canonical_event_id=event.id,
    )


def sync_source_identity_node(
    db: Session,
    identity: SourceIdentity,
    *,
    commit: bool = True,
) -> WorkGraphNode:
    source_node = _get_or_create_node(
        db,
        organization_id=identity.organization_id,
        node_type=WorkGraphNodeType.PERSON,
        stable_key=f"person:source_identity:{identity.id}",
        display_name=identity.display_name,
        source_identity_id=identity.id,
        attributes={
            "identity_kind": "source",
            "provider": identity.provider,
            "state": identity.state.value,
        },
    )
    db.execute(
        delete(WorkGraphEdge).where(
            WorkGraphEdge.organization_id == identity.organization_id,
            WorkGraphEdge.source_node_id == source_node.id,
            WorkGraphEdge.edge_type == WorkGraphEdgeType.RESOLVES_TO,
        )
    )

    if identity.resolved_user_id is not None:
        user = db.get(User, identity.resolved_user_id)
        if user is None:
            raise WorkGraphError("Resolved identity references a missing Brain user")
        user_node = _get_or_create_node(
            db,
            organization_id=identity.organization_id,
            node_type=WorkGraphNodeType.PERSON,
            stable_key=f"person:user:{user.id}",
            display_name=user.display_name or user.email,
            user_id=user.id,
            attributes={"identity_kind": "brain_user"},
        )
        _get_or_create_edge(
            db,
            organization_id=identity.organization_id,
            source_node=source_node,
            target_node=user_node,
            edge_type=WorkGraphEdgeType.RESOLVES_TO,
            source_kind=WorkGraphEdgeSource.IDENTITY,
            evidence_state=WorkGraphEvidenceState.VERIFIED,
            confidence=1.0,
            provenance_key=(
                f"identity:{identity.id}:resolves_to:{identity.resolved_user_id}"
            ),
            provenance={
                "source_identity_id": str(identity.id),
                "resolution_method": identity.resolution_method,
            },
        )

    if commit:
        db.commit()
        db.refresh(source_node)
    return source_node


def project_canonical_event(db: Session, event: CanonicalEvent) -> WorkGraphNode:
    metadata = event.event_metadata or {}
    evidence_attributes: dict[str, object] = {
        "event_type": event.event_type,
        "object_type": event.object_type,
        "source_provider": event.source_provider,
        "integration_connection_id": str(event.integration_connection_id),
    }
    channel_id = metadata.get("channel_id")
    if isinstance(channel_id, str) and channel_id:
        evidence_attributes["channel_id"] = channel_id
    repository_id = metadata.get("repository_id")
    if repository_id not in (None, ""):
        evidence_attributes["repository_id"] = str(repository_id)

    evidence = _get_or_create_node(
        db,
        organization_id=event.organization_id,
        node_type=WorkGraphNodeType.EVIDENCE,
        stable_key=f"evidence:canonical:{event.id}",
        display_name=event.object_display_name or event.event_type,
        canonical_event_id=event.id,
        source_visibility=event.source_visibility,
        source_acl=list(event.source_acl),
        attributes=evidence_attributes,
    )

    if event.source_identity_id is not None:
        identity = db.get(SourceIdentity, event.source_identity_id)
        if identity is not None and identity.organization_id == event.organization_id:
            source_person = sync_source_identity_node(db, identity, commit=False)
            _canonical_edge(
                db,
                event=event,
                source_node=source_person,
                target_node=evidence,
                edge_type=WorkGraphEdgeType.PERFORMED,
            )

    if event.source_provider == "slack" and isinstance(channel_id, str) and channel_id:
        track = _get_or_create_node(
            db,
            organization_id=event.organization_id,
            node_type=WorkGraphNodeType.TRACK,
            stable_key=f"track:slack:{event.integration_connection_id}:{channel_id}",
            display_name=f"Slack channel {channel_id}",
            source_visibility=event.source_visibility,
            source_acl=list(event.source_acl),
            attributes={
                "provider": "slack",
                "channel_id": channel_id,
                "integration_connection_id": str(event.integration_connection_id),
            },
        )
        _canonical_edge(
            db,
            event=event,
            source_node=track,
            target_node=evidence,
            edge_type=WorkGraphEdgeType.SUPPORTED_BY,
        )

    if event.source_provider == "github":
        repository_name = metadata.get("repository")
        repository_key = (
            str(repository_id)
            if repository_id not in (None, "")
            else repository_name if isinstance(repository_name, str) else None
        )
        if repository_key:
            project = _get_or_create_node(
                db,
                organization_id=event.organization_id,
                node_type=WorkGraphNodeType.PROJECT,
                stable_key=(
                    f"project:github:{event.integration_connection_id}:"
                    f"{repository_key}"
                ),
                display_name=(
                    repository_name
                    if isinstance(repository_name, str)
                    else repository_key
                ),
                source_visibility=event.source_visibility,
                source_acl=list(event.source_acl),
                attributes={
                    "provider": "github",
                    "repository_id": (
                        str(repository_id)
                        if repository_id not in (None, "")
                        else None
                    ),
                    "integration_connection_id": str(event.integration_connection_id),
                },
            )
            _canonical_edge(
                db,
                event=event,
                source_node=project,
                target_node=evidence,
                edge_type=WorkGraphEdgeType.SUPPORTED_BY,
            )

            if event.object_type != "repository":
                work_item = _get_or_create_node(
                    db,
                    organization_id=event.organization_id,
                    node_type=WorkGraphNodeType.WORK_ITEM,
                    stable_key=(
                        f"work_item:github:{event.integration_connection_id}:"
                        f"{event.object_type}:{event.object_external_id}"
                    ),
                    display_name=event.object_display_name or event.object_external_id,
                    source_visibility=event.source_visibility,
                    source_acl=list(event.source_acl),
                    attributes={
                        "provider": "github",
                        "object_type": event.object_type,
                        "object_external_id": event.object_external_id,
                        "repository_id": (
                            str(repository_id)
                            if repository_id not in (None, "")
                            else None
                        ),
                        "integration_connection_id": str(
                            event.integration_connection_id
                        ),
                    },
                )
                _canonical_edge(
                    db,
                    event=event,
                    source_node=project,
                    target_node=work_item,
                    edge_type=WorkGraphEdgeType.CONTAINS,
                )
                _canonical_edge(
                    db,
                    event=event,
                    source_node=work_item,
                    target_node=evidence,
                    edge_type=WorkGraphEdgeType.SUPPORTED_BY,
                )

    db.commit()
    db.refresh(evidence)
    return evidence


def create_manual_node(
    db: Session,
    *,
    organization_id: uuid.UUID,
    node_type: WorkGraphNodeType,
    key: str,
    display_name: str,
    actor_user_id: uuid.UUID,
) -> WorkGraphNode:
    if node_type not in MANUAL_NODE_TYPES:
        raise WorkGraphError("Manual nodes may only be projects, tracks or work items")
    normalized_key = key.strip().lower()
    if not normalized_key:
        raise WorkGraphError("Graph node key is required")
    node = _get_or_create_node(
        db,
        organization_id=organization_id,
        node_type=node_type,
        stable_key=f"manual:{node_type.value}:{normalized_key}",
        display_name=display_name.strip(),
        attributes={
            "source": "manual",
            "created_by_user_id": str(actor_user_id),
        },
    )
    db.commit()
    db.refresh(node)
    return node


def create_manual_edge(
    db: Session,
    *,
    organization_id: uuid.UUID,
    source_node_id: uuid.UUID,
    target_node_id: uuid.UUID,
    edge_type: WorkGraphEdgeType,
    actor_user_id: uuid.UUID,
    reason: str,
) -> WorkGraphEdge:
    if edge_type not in MANUAL_EDGE_TYPES:
        raise WorkGraphError("This edge type cannot be created manually")
    source_node = db.get(WorkGraphNode, source_node_id)
    target_node = db.get(WorkGraphNode, target_node_id)
    if (
        source_node is None
        or target_node is None
        or source_node.organization_id != organization_id
        or target_node.organization_id != organization_id
    ):
        raise WorkGraphError("Both graph nodes must belong to the organization")
    if (
        source_node.node_type == WorkGraphNodeType.PERSON
        or target_node.node_type == WorkGraphNodeType.PERSON
    ):
        raise WorkGraphError("Manual edges cannot assert person identity relationships")

    edge = _get_or_create_edge(
        db,
        organization_id=organization_id,
        source_node=source_node,
        target_node=target_node,
        edge_type=edge_type,
        source_kind=WorkGraphEdgeSource.MANUAL,
        evidence_state=WorkGraphEvidenceState.VERIFIED,
        confidence=1.0,
        provenance_key=(
            f"manual:{source_node.id}:{edge_type.value}:{target_node.id}"
        ),
        provenance={
            "actor_user_id": str(actor_user_id),
            "reason": reason.strip()[:500],
        },
        created_by_user_id=actor_user_id,
    )
    db.commit()
    db.refresh(edge)
    return edge


def _has_resource_grant(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    resource_type: str,
    resource_id: str,
) -> bool:
    grant = db.scalar(
        select(ResourceGrant.id)
        .where(
            ResourceGrant.organization_id == organization_id,
            ResourceGrant.user_id == user_id,
            ResourceGrant.resource_type == resource_type,
            ResourceGrant.resource_id == resource_id,
            ResourceGrant.access.in_(
                (ResourceAccessLevel.READ, ResourceAccessLevel.WRITE)
            ),
        )
        .limit(1)
    )
    return grant is not None


def _current_private_slack_access(
    db: Session,
    node: WorkGraphNode,
    *,
    user_id: uuid.UUID,
) -> bool:
    channel_id = node.attributes.get("channel_id")
    connection_value = node.attributes.get("integration_connection_id")
    if not isinstance(channel_id, str) or not isinstance(connection_value, str):
        return False
    try:
        connection_id = uuid.UUID(connection_value)
    except ValueError:
        return False

    authorization = db.scalar(
        select(SlackChannelAuthorization).where(
            SlackChannelAuthorization.organization_id == node.organization_id,
            SlackChannelAuthorization.integration_connection_id == connection_id,
            SlackChannelAuthorization.channel_id == channel_id,
            SlackChannelAuthorization.is_private.is_(True),
        )
    )
    if authorization is None or not authorization.member_ids:
        return False

    slack_identity = db.scalar(
        select(SourceIdentity.id)
        .where(
            SourceIdentity.organization_id == node.organization_id,
            SourceIdentity.provider == "slack",
            SourceIdentity.resolved_user_id == user_id,
            SourceIdentity.external_id.in_(authorization.member_ids),
        )
        .limit(1)
    )
    return slack_identity is not None


def node_visible_to_user(
    db: Session,
    node: WorkGraphNode,
    *,
    user_id: uuid.UUID,
    role: MembershipRole,
) -> bool:
    if role in ADMIN_ROLES or node.source_visibility in PUBLIC_VISIBILITIES:
        return True
    if _has_resource_grant(
        db,
        organization_id=node.organization_id,
        user_id=user_id,
        resource_type="work_graph.node",
        resource_id=str(node.id),
    ):
        return True

    if node.source_visibility == "private_channel":
        return _current_private_slack_access(db, node, user_id=user_id)

    for marker in node.source_acl:
        prefix = "github:repository:"
        if marker.startswith(prefix):
            repository_id = marker.removeprefix(prefix)
            if _has_resource_grant(
                db,
                organization_id=node.organization_id,
                user_id=user_id,
                resource_type="github.repository",
                resource_id=repository_id,
            ):
                return True
    return False


def traverse_work_graph(
    db: Session,
    *,
    organization_id: uuid.UUID,
    start_node_id: uuid.UUID,
    user_id: uuid.UUID,
    role: MembershipRole,
    depth: int,
    max_nodes: int = 100,
) -> tuple[list[WorkGraphNode], list[WorkGraphEdge]] | None:
    if depth < 0 or depth > 3:
        raise WorkGraphError("Traversal depth must be between 0 and 3")
    start = db.scalar(
        select(WorkGraphNode).where(
            WorkGraphNode.id == start_node_id,
            WorkGraphNode.organization_id == organization_id,
        )
    )
    if start is None or not node_visible_to_user(
        db,
        start,
        user_id=user_id,
        role=role,
    ):
        return None

    nodes: dict[uuid.UUID, WorkGraphNode] = {start.id: start}
    edges: dict[uuid.UUID, WorkGraphEdge] = {}
    queue: deque[tuple[uuid.UUID, int]] = deque([(start.id, 0)])

    while queue and len(nodes) < max_nodes:
        current_id, current_depth = queue.popleft()
        if current_depth >= depth:
            continue
        candidates = list(
            db.scalars(
                select(WorkGraphEdge).where(
                    WorkGraphEdge.organization_id == organization_id,
                    or_(
                        WorkGraphEdge.source_node_id == current_id,
                        WorkGraphEdge.target_node_id == current_id,
                    ),
                )
            )
        )
        for edge in candidates:
            neighbor_id = (
                edge.target_node_id
                if edge.source_node_id == current_id
                else edge.source_node_id
            )
            neighbor = db.scalar(
                select(WorkGraphNode).where(
                    WorkGraphNode.id == neighbor_id,
                    WorkGraphNode.organization_id == organization_id,
                )
            )
            if neighbor is None or not node_visible_to_user(
                db,
                neighbor,
                user_id=user_id,
                role=role,
            ):
                continue
            nodes[neighbor.id] = neighbor
            edges[edge.id] = edge
            if current_depth + 1 < depth and len(nodes) < max_nodes:
                queue.append((neighbor.id, current_depth + 1))

    return list(nodes.values()), list(edges.values())


def reconcile_work_graph(
    db: Session,
    *,
    organization_id: uuid.UUID,
    limit: int,
) -> tuple[int, int]:
    projected_event_ids = select(WorkGraphNode.canonical_event_id).where(
        WorkGraphNode.organization_id == organization_id,
        WorkGraphNode.canonical_event_id.is_not(None),
    )
    events = list(
        db.scalars(
            select(CanonicalEvent)
            .where(
                CanonicalEvent.organization_id == organization_id,
                ~CanonicalEvent.id.in_(projected_event_ids),
            )
            .order_by(CanonicalEvent.created_at, CanonicalEvent.id)
            .limit(limit)
        )
    )
    for event in events:
        project_canonical_event(db, event)

    remaining = db.scalar(
        select(func.count())
        .select_from(CanonicalEvent)
        .where(
            CanonicalEvent.organization_id == organization_id,
            ~CanonicalEvent.id.in_(projected_event_ids),
        )
    )
    return len(events), int(remaining or 0)

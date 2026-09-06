import json
import math
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from sqlalchemy import and_, cast, func, literal, or_, select, tuple_
from sqlalchemy.orm import Session

from app.embeddings import EmbeddingClient, EmbeddingError
from app.models import (
    CanonicalEvent,
    IntegrationConnection,
    IntegrationStatus,
    RawEvent,
    ResourceAccessLevel,
    ResourceGrant,
    SlackChannelAuthorization,
    SourceIdentity,
)
from app.search_models import SearchDocument, SearchEmbeddingStatus, Vector, vector_literal
from app.work_graph_models import WorkGraphNode

PUBLIC_VISIBILITIES = frozenset({"organization", "public_channel", "public_repository"})


class SearchMode(StrEnum):
    KEYWORD = "keyword"
    HYBRID = "hybrid"


@dataclass(frozen=True, slots=True)
class SearchHit:
    document: SearchDocument
    score: float


@dataclass(frozen=True, slots=True)
class SearchResponseData:
    hits: list[SearchHit]
    semantic_status: str


def _payload(raw: RawEvent) -> dict[str, object]:
    try:
        value = json.loads(raw.raw_payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if value else None


def _github_text(raw: RawEvent, payload: dict[str, object]) -> str:
    if raw.source_event_type.startswith("backfill."):
        objects = [_dict(payload.get("item")), _dict(payload.get("repository"))]
    else:
        objects = [
            _dict(payload.get("pull_request")),
            _dict(payload.get("issue")),
            _dict(payload.get("deployment")),
            _dict(payload.get("deployment_status")),
            _dict(payload.get("workflow_run")),
            _dict(payload.get("repository")),
        ]
    fields = ("title", "body", "name", "message", "description", "state", "ref")
    values: list[str] = []
    for obj in objects:
        for field in fields:
            value = _text(obj.get(field))
            if value and value not in values:
                values.append(value)
    commits = payload.get("commits")
    if isinstance(commits, list):
        for commit in commits[:100]:
            message = _text(_dict(commit).get("message"))
            if message and message not in values:
                values.append(message)
    return "\n".join(values)


def _searchable_content(event: CanonicalEvent, raw: RawEvent) -> tuple[str, str]:
    title = (event.object_display_name or event.event_type or "").strip()[:1024]
    if event.source_provider == "slack":
        content = _text((event.event_metadata or {}).get("text")) or ""
    elif event.source_provider == "github":
        content = _github_text(raw, _payload(raw))
    else:
        content = ""
    return title, content[:100_000]


def project_search_document(db: Session, event: CanonicalEvent) -> SearchDocument:
    existing = db.scalar(
        select(SearchDocument).where(SearchDocument.canonical_event_id == event.id)
    )
    raw = db.get(RawEvent, event.raw_event_id)
    if raw is None:
        raise RuntimeError("Canonical event references missing raw evidence")

    metadata = event.event_metadata or {}
    channel_id = metadata.get("channel_id")
    repository_id = metadata.get("repository_id")
    evidence_node = db.scalar(
        select(WorkGraphNode).where(WorkGraphNode.canonical_event_id == event.id)
    )
    title, content = _searchable_content(event, raw)
    deleted = event.action == "deleted" or event.event_type.endswith(".deleted")

    if deleted:
        prior = list(
            db.scalars(
                select(SearchDocument).where(
                    SearchDocument.organization_id == event.organization_id,
                    SearchDocument.integration_connection_id == event.integration_connection_id,
                    SearchDocument.source_provider == event.source_provider,
                    SearchDocument.object_type == event.object_type,
                    SearchDocument.object_external_id == event.object_external_id,
                )
            )
        )
        for document in prior:
            document.is_deleted = True
            document.content = ""
            document.embedding = None
            document.embedding_model = None
            document.embedding_status = SearchEmbeddingStatus.PENDING

    if existing is None:
        existing = SearchDocument(
            organization_id=event.organization_id,
            canonical_event_id=event.id,
            integration_connection_id=event.integration_connection_id,
            work_graph_node_id=evidence_node.id if evidence_node else None,
            source_provider=event.source_provider,
            source_visibility=event.source_visibility,
            source_acl=list(event.source_acl),
            channel_id=channel_id if isinstance(channel_id, str) else None,
            repository_id=str(repository_id) if repository_id not in (None, "") else None,
            object_type=event.object_type,
            object_external_id=event.object_external_id,
            title=title,
            content="" if deleted else content,
            provenance={
                **event.provenance,
                "source_event_id": event.source_event_id,
                "source_event_type": event.source_event_type,
                "object_external_id": event.object_external_id,
            },
            occurred_at=event.occurred_at,
            is_deleted=deleted,
            embedding_status=SearchEmbeddingStatus.PENDING,
        )
        db.add(existing)
    else:
        changed = existing.title != title or existing.content != content
        existing.work_graph_node_id = evidence_node.id if evidence_node else existing.work_graph_node_id
        existing.source_visibility = event.source_visibility
        existing.source_acl = list(event.source_acl)
        existing.channel_id = channel_id if isinstance(channel_id, str) else None
        existing.repository_id = str(repository_id) if repository_id not in (None, "") else None
        existing.title = title
        existing.content = "" if deleted else content
        existing.is_deleted = deleted
        if changed and not deleted:
            existing.embedding = None
            existing.embedding_model = None
            existing.embedding_status = SearchEmbeddingStatus.PENDING
            existing.embedding_attempts = 0
            existing.next_retry_at = None
            existing.last_error_code = None
    db.commit()
    db.refresh(existing)
    return existing


def reconcile_search_documents(
    db: Session,
    *,
    organization_id: uuid.UUID,
    limit: int,
) -> tuple[int, int]:
    projected_ids = select(SearchDocument.canonical_event_id).where(
        SearchDocument.organization_id == organization_id
    )
    events = list(
        db.scalars(
            select(CanonicalEvent)
            .where(
                CanonicalEvent.organization_id == organization_id,
                ~CanonicalEvent.id.in_(projected_ids),
            )
            .order_by(CanonicalEvent.created_at, CanonicalEvent.id)
            .limit(limit)
        )
    )
    for event in events:
        project_search_document(db, event)
    remaining = db.scalar(
        select(func.count())
        .select_from(CanonicalEvent)
        .where(
            CanonicalEvent.organization_id == organization_id,
            ~CanonicalEvent.id.in_(projected_ids),
        )
    )
    return len(events), int(remaining or 0)


def _authorization_predicate(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
):
    slack_ids = list(
        db.scalars(
            select(SourceIdentity.external_id).where(
                SourceIdentity.organization_id == organization_id,
                SourceIdentity.provider == "slack",
                SourceIdentity.resolved_user_id == user_id,
            )
        )
    )
    channel_rows = list(
        db.scalars(
            select(SlackChannelAuthorization).where(
                SlackChannelAuthorization.organization_id == organization_id
            )
        )
    )
    public_channels = [
        (row.integration_connection_id, row.channel_id)
        for row in channel_rows
        if not row.is_private
    ]
    private_channels = [
        (row.integration_connection_id, row.channel_id)
        for row in channel_rows
        if row.is_private and any(source_id in row.member_ids for source_id in slack_ids)
    ]

    grants = list(
        db.scalars(
            select(ResourceGrant).where(
                ResourceGrant.organization_id == organization_id,
                ResourceGrant.user_id == user_id,
                ResourceGrant.access.in_((ResourceAccessLevel.READ, ResourceAccessLevel.WRITE)),
            )
        )
    )
    github_repository_ids = [
        grant.resource_id for grant in grants if grant.resource_type == "github.repository"
    ]
    graph_node_ids: list[uuid.UUID] = []
    for grant in grants:
        if grant.resource_type != "work_graph.node":
            continue
        try:
            graph_node_ids.append(uuid.UUID(grant.resource_id))
        except ValueError:
            continue

    slack_tuple = tuple_(SearchDocument.integration_connection_id, SearchDocument.channel_id)
    clauses = [
        and_(
            SearchDocument.source_provider != "slack",
            SearchDocument.source_visibility.in_(("organization", "public_repository")),
        )
    ]
    if public_channels:
        clauses.append(
            and_(
                SearchDocument.source_provider == "slack",
                SearchDocument.source_visibility == "public_channel",
                slack_tuple.in_(public_channels),
            )
        )
    if private_channels:
        clauses.append(
            and_(
                SearchDocument.source_provider == "slack",
                SearchDocument.source_visibility == "private_channel",
                slack_tuple.in_(private_channels),
            )
        )
    restricted_access = []
    if github_repository_ids:
        restricted_access.append(SearchDocument.repository_id.in_(github_repository_ids))
    if graph_node_ids:
        restricted_access.append(SearchDocument.work_graph_node_id.in_(graph_node_ids))
    if restricted_access:
        clauses.append(
            and_(
                SearchDocument.source_provider != "slack",
                or_(*restricted_access),
            )
        )
    return or_(*clauses)


def _base_query(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
):
    return (
        select(SearchDocument)
        .join(
            IntegrationConnection,
            IntegrationConnection.id == SearchDocument.integration_connection_id,
        )
        .where(
            SearchDocument.organization_id == organization_id,
            SearchDocument.is_deleted.is_(False),
            IntegrationConnection.organization_id == organization_id,
            IntegrationConnection.status == IntegrationStatus.ACTIVE,
            _authorization_predicate(
                db,
                organization_id=organization_id,
                user_id=user_id,
            ),
        )
    )


def _keyword_hits(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    query: str,
    limit: int,
) -> list[SearchHit]:
    base = _base_query(db, organization_id=organization_id, user_id=user_id)
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        ts_query = func.plainto_tsquery("simple", query)
        vector = func.to_tsvector(
            "simple",
            func.coalesce(SearchDocument.title, "") + literal(" ") + func.coalesce(SearchDocument.content, ""),
        )
        score = func.ts_rank_cd(vector, ts_query)
        rows = db.execute(
            base.add_columns(score.label("rank"))
            .where(vector.op("@@")(ts_query))
            .order_by(score.desc(), SearchDocument.occurred_at.desc().nullslast())
            .limit(limit)
        ).all()
        return [SearchHit(document=row[0], score=float(row.rank or 0.0)) for row in rows]

    pattern = f"%{query}%"
    documents = list(
        db.scalars(
            base.where(
                or_(SearchDocument.title.ilike(pattern), SearchDocument.content.ilike(pattern))
            )
            .order_by(SearchDocument.occurred_at.desc())
            .limit(limit)
        )
    )
    lowered = query.casefold()
    return [
        SearchHit(
            document=document,
            score=float(
                2 * document.title.casefold().count(lowered)
                + document.content.casefold().count(lowered)
            ),
        )
        for document in documents
    ]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return -1.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return -1.0
    return dot / (left_norm * right_norm)


def _semantic_hits(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    query_embedding: list[float],
    model: str,
    limit: int,
) -> list[SearchHit]:
    base = _base_query(db, organization_id=organization_id, user_id=user_id).where(
        SearchDocument.embedding.is_not(None),
        SearchDocument.embedding_status == SearchEmbeddingStatus.READY,
        SearchDocument.embedding_model == model,
    )
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        distance = SearchDocument.embedding.op("<=>")(
            cast(literal(vector_literal(query_embedding)), Vector())
        )
        rows = db.execute(
            base.add_columns(distance.label("distance"))
            .order_by(distance.asc())
            .limit(limit)
        ).all()
        return [
            SearchHit(document=row[0], score=max(0.0, 1.0 - float(row.distance)))
            for row in rows
        ]

    documents = list(db.scalars(base))
    hits = [
        SearchHit(
            document=document,
            score=_cosine_similarity(document.embedding or [], query_embedding),
        )
        for document in documents
    ]
    hits.sort(key=lambda hit: hit.score, reverse=True)
    return hits[:limit]


def search_documents(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    query: str,
    mode: SearchMode,
    limit: int,
    embedding_client: EmbeddingClient | None,
    embedding_model: str | None,
) -> SearchResponseData:
    keyword = _keyword_hits(
        db,
        organization_id=organization_id,
        user_id=user_id,
        query=query,
        limit=max(limit * 3, 20),
    )
    if mode == SearchMode.KEYWORD:
        return SearchResponseData(hits=keyword[:limit], semantic_status="not_requested")
    if embedding_client is None or embedding_model is None:
        return SearchResponseData(hits=keyword[:limit], semantic_status="unconfigured")
    try:
        query_embedding = embedding_client.embed([query], model=embedding_model)[0]
    except (EmbeddingError, IndexError):
        return SearchResponseData(hits=keyword[:limit], semantic_status="degraded")

    semantic = _semantic_hits(
        db,
        organization_id=organization_id,
        user_id=user_id,
        query_embedding=query_embedding,
        model=embedding_model,
        limit=max(limit * 3, 20),
    )
    scores: dict[uuid.UUID, float] = {}
    documents: dict[uuid.UUID, SearchDocument] = {}
    for rank, hit in enumerate(keyword, start=1):
        scores[hit.document.id] = scores.get(hit.document.id, 0.0) + 1.0 / (60 + rank)
        documents[hit.document.id] = hit.document
    for rank, hit in enumerate(semantic, start=1):
        scores[hit.document.id] = scores.get(hit.document.id, 0.0) + 1.0 / (60 + rank)
        documents[hit.document.id] = hit.document
    ordered = sorted(scores, key=scores.get, reverse=True)
    return SearchResponseData(
        hits=[SearchHit(document=documents[item], score=scores[item]) for item in ordered[:limit]],
        semantic_status="ready",
    )


def process_embedding_batch(
    db: Session,
    *,
    embedding_client: EmbeddingClient,
    model: str,
    limit: int,
    max_attempts: int = 5,
) -> tuple[int, int]:
    now = datetime.now(UTC)
    stale_before = now - timedelta(minutes=10)
    db.query(SearchDocument).filter(
        SearchDocument.embedding_status == SearchEmbeddingStatus.PROCESSING,
        SearchDocument.claimed_at < stale_before,
    ).update(
        {
            SearchDocument.embedding_status: SearchEmbeddingStatus.FAILED,
            SearchDocument.claimed_at: None,
            SearchDocument.next_retry_at: now,
            SearchDocument.last_error_code: "stale_claim",
        },
        synchronize_session=False,
    )
    db.commit()

    criteria = [
        SearchDocument.is_deleted.is_(False),
        SearchDocument.embedding_attempts < max_attempts,
        SearchDocument.embedding_status.in_(
            (SearchEmbeddingStatus.PENDING, SearchEmbeddingStatus.FAILED)
        ),
        or_(SearchDocument.next_retry_at.is_(None), SearchDocument.next_retry_at <= now),
    ]
    stmt = select(SearchDocument).where(*criteria).order_by(SearchDocument.created_at).limit(limit)
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        stmt = stmt.with_for_update(skip_locked=True)
    documents = list(db.scalars(stmt))
    if not documents:
        return 0, 0
    for document in documents:
        document.embedding_status = SearchEmbeddingStatus.PROCESSING
        document.claimed_at = now
        document.embedding_attempts += 1
    db.commit()

    try:
        vectors = embedding_client.embed(
            [document.searchable_text() for document in documents],
            model=model,
        )
        if len(vectors) != len(documents):
            raise EmbeddingError("embedding_response_count_mismatch")
    except EmbeddingError as exc:
        failure_time = datetime.now(UTC)
        for document in documents:
            document.embedding_status = SearchEmbeddingStatus.FAILED
            document.claimed_at = None
            document.last_error_code = str(exc)[:128]
            delay = min(3600, 60 * (2 ** max(0, document.embedding_attempts - 1)))
            document.next_retry_at = failure_time + timedelta(seconds=delay)
        db.commit()
        return 0, len(documents)

    for document, vector in zip(documents, vectors, strict=True):
        document.embedding = vector
        document.embedding_model = model
        document.embedding_status = SearchEmbeddingStatus.READY
        document.claimed_at = None
        document.next_retry_at = None
        document.last_error_code = None
    db.commit()
    return len(documents), 0

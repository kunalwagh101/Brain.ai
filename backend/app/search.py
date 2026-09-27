import json
import math
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from sqlalchemy import and_, cast, func, literal, or_, select, tuple_, update
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

_KEYWORD_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_QUESTION_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "are",
        "can",
        "could",
        "did",
        "do",
        "does",
        "how",
        "is",
        "me",
        "the",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "would",
    }
)


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
    if event.source_provider in {"slack", "brain_native"}:
        content = _text((event.event_metadata or {}).get("text")) or ""
    elif event.source_provider == "github":
        content = _github_text(raw, _payload(raw))
    else:
        content = ""
    return title, content[:100_000]


def _reset_embedding(document: SearchDocument) -> None:
    document.embedding = None
    document.embedding_model = None
    document.embedding_status = SearchEmbeddingStatus.PENDING
    document.embedding_attempts = 0
    document.next_retry_at = None
    document.claimed_at = None
    document.last_error_code = None


def _hide_deleted_object_versions(db: Session, event: CanonicalEvent) -> None:
    previous = list(
        db.scalars(
            select(SearchDocument).where(
                SearchDocument.organization_id == event.organization_id,
                SearchDocument.integration_connection_id
                == event.integration_connection_id,
                SearchDocument.source_provider == event.source_provider,
                SearchDocument.object_type == event.object_type,
                SearchDocument.object_external_id == event.object_external_id,
            )
        )
    )
    for document in previous:
        document.is_deleted = True
        document.content = ""
        _reset_embedding(document)


def project_search_document(
    db: Session,
    event: CanonicalEvent,
    *,
    commit: bool = True,
) -> SearchDocument:
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
    native_revision = (
        event.source_provider == "brain_native"
        and event.action in {"updated", "deleted"}
    )

    if deleted or native_revision:
        _hide_deleted_object_versions(db, event)

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
            repository_id=(
                str(repository_id) if repository_id not in (None, "") else None
            ),
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
        if evidence_node is not None:
            existing.work_graph_node_id = evidence_node.id
        existing.source_visibility = event.source_visibility
        existing.source_acl = list(event.source_acl)
        existing.channel_id = channel_id if isinstance(channel_id, str) else None
        existing.repository_id = (
            str(repository_id) if repository_id not in (None, "") else None
        )
        existing.title = title
        existing.content = "" if deleted else content
        existing.is_deleted = deleted
        if changed and not deleted:
            _reset_embedding(existing)

    if commit:
        db.commit()
        db.refresh(existing)
    else:
        db.flush()
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


def _live_slack_channels(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
) -> tuple[list[tuple[uuid.UUID, str]], list[tuple[uuid.UUID, str]]]:
    slack_ids = set(
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
        if row.is_private
        and any(source_id in row.member_ids for source_id in slack_ids)
    ]
    return public_channels, private_channels


def _live_resource_grants(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
) -> tuple[list[str], list[uuid.UUID]]:
    grants = list(
        db.scalars(
            select(ResourceGrant).where(
                ResourceGrant.organization_id == organization_id,
                ResourceGrant.user_id == user_id,
                ResourceGrant.access.in_(
                    (ResourceAccessLevel.READ, ResourceAccessLevel.WRITE)
                ),
            )
        )
    )
    repository_ids = [
        grant.resource_id
        for grant in grants
        if grant.resource_type == "github.repository"
    ]
    graph_node_ids: list[uuid.UUID] = []
    for grant in grants:
        if grant.resource_type != "work_graph.node":
            continue
        try:
            graph_node_ids.append(uuid.UUID(grant.resource_id))
        except ValueError:
            continue
    return repository_ids, graph_node_ids


def _authorization_predicate(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
):
    public_channels, private_channels = _live_slack_channels(
        db,
        organization_id=organization_id,
        user_id=user_id,
    )
    repository_ids, graph_node_ids = _live_resource_grants(
        db,
        organization_id=organization_id,
        user_id=user_id,
    )

    slack_tuple = tuple_(
        SearchDocument.integration_connection_id,
        SearchDocument.channel_id,
    )
    clauses = [
        and_(
            SearchDocument.source_provider != "slack",
            SearchDocument.source_visibility.in_(
                ("organization", "public_repository")
            ),
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
    if repository_ids:
        restricted_access.append(SearchDocument.repository_id.in_(repository_ids))
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
    base = _base_query(
        db,
        organization_id=organization_id,
        user_id=user_id,
    )
    terms = [
        token
        for token in _KEYWORD_TOKEN_RE.findall(query)
        if token.casefold() not in _QUESTION_STOP_WORDS
    ]
    if not terms:
        terms = _KEYWORD_TOKEN_RE.findall(query)
    normalized_query = " ".join(terms) or query
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        ts_query = func.plainto_tsquery("simple", normalized_query)
        vector = func.to_tsvector(
            "simple",
            func.coalesce(SearchDocument.title, "")
            + literal(" ")
            + func.coalesce(SearchDocument.content, ""),
        )
        score = func.ts_rank_cd(vector, ts_query)
        rows = db.execute(
            base.add_columns(score.label("rank"))
            .where(vector.op("@@")(ts_query))
            .order_by(
                score.desc(),
                SearchDocument.occurred_at.desc().nullslast(),
            )
            .limit(limit)
        ).all()
        return [
            SearchHit(document=row[0], score=float(row.rank or 0.0))
            for row in rows
        ]

    term_predicates = [
        or_(
            SearchDocument.title.ilike(f"%{term}%"),
            SearchDocument.content.ilike(f"%{term}%"),
        )
        for term in terms
    ]
    documents = list(
        db.scalars(
            base.where(and_(*term_predicates))
            .order_by(SearchDocument.occurred_at.desc())
            .limit(limit)
        )
    )
    lowered_terms = [term.casefold() for term in terms]
    return [
        SearchHit(
            document=document,
            score=float(
                sum(
                    2 * document.title.casefold().count(term)
                    + document.content.casefold().count(term)
                    for term in lowered_terms
                )
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
    base = _base_query(
        db,
        organization_id=organization_id,
        user_id=user_id,
    ).where(
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
            SearchHit(
                document=row[0],
                score=max(0.0, 1.0 - float(row.distance)),
            )
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
        return SearchResponseData(
            hits=keyword[:limit],
            semantic_status="not_requested",
        )
    if embedding_client is None or embedding_model is None:
        return SearchResponseData(
            hits=keyword[:limit],
            semantic_status="unconfigured",
        )

    try:
        query_embedding = embedding_client.embed(
            [query], model=embedding_model
        )[0]
    except (EmbeddingError, IndexError):
        return SearchResponseData(
            hits=keyword[:limit],
            semantic_status="degraded",
        )

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
        scores[hit.document.id] = (
            scores.get(hit.document.id, 0.0) + 1.0 / (60 + rank)
        )
        documents[hit.document.id] = hit.document
    for rank, hit in enumerate(semantic, start=1):
        scores[hit.document.id] = (
            scores.get(hit.document.id, 0.0) + 1.0 / (60 + rank)
        )
        documents[hit.document.id] = hit.document

    ordered = sorted(
        scores,
        key=lambda document_id: scores[document_id],
        reverse=True,
    )
    return SearchResponseData(
        hits=[
            SearchHit(
                document=documents[document_id],
                score=scores[document_id],
            )
            for document_id in ordered[:limit]
        ],
        semantic_status="ready",
    )


def _recover_stale_claims(db: Session, *, now: datetime) -> None:
    stale_before = now - timedelta(minutes=10)
    db.execute(
        update(SearchDocument)
        .where(
            SearchDocument.embedding_status == SearchEmbeddingStatus.PROCESSING,
            SearchDocument.claimed_at.is_not(None),
            SearchDocument.claimed_at < stale_before,
        )
        .values(
            embedding_status=SearchEmbeddingStatus.FAILED,
            claimed_at=None,
            next_retry_at=now,
            last_error_code="stale_claim",
        )
    )
    db.commit()


def _claim_embedding_batch(
    db: Session,
    *,
    now: datetime,
    limit: int,
    max_attempts: int,
) -> list[SearchDocument]:
    statement = (
        select(SearchDocument)
        .where(
            SearchDocument.is_deleted.is_(False),
            SearchDocument.embedding_attempts < max_attempts,
            SearchDocument.embedding_status.in_(
                (SearchEmbeddingStatus.PENDING, SearchEmbeddingStatus.FAILED)
            ),
            or_(
                SearchDocument.next_retry_at.is_(None),
                SearchDocument.next_retry_at <= now,
            ),
        )
        .order_by(SearchDocument.created_at, SearchDocument.id)
        .limit(limit)
    )
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        statement = statement.with_for_update(skip_locked=True)

    documents = list(db.scalars(statement))
    for document in documents:
        document.embedding_status = SearchEmbeddingStatus.PROCESSING
        document.claimed_at = now
        document.embedding_attempts += 1
    if documents:
        db.commit()
    return documents


def _mark_embedding_failure(
    db: Session,
    documents: list[SearchDocument],
    error_code: str,
) -> None:
    failure_time = datetime.now(UTC)
    for document in documents:
        document.embedding_status = SearchEmbeddingStatus.FAILED
        document.claimed_at = None
        document.last_error_code = error_code[:128]
        exponent = max(0, document.embedding_attempts - 1)
        delay = min(3600, 60 * (2**exponent))
        document.next_retry_at = failure_time + timedelta(seconds=delay)
    db.commit()


def process_embedding_batch(
    db: Session,
    *,
    embedding_client: EmbeddingClient,
    model: str,
    limit: int,
    max_attempts: int = 5,
) -> tuple[int, int]:
    now = datetime.now(UTC)
    _recover_stale_claims(db, now=now)
    documents = _claim_embedding_batch(
        db,
        now=now,
        limit=limit,
        max_attempts=max_attempts,
    )
    if not documents:
        return 0, 0

    try:
        vectors = embedding_client.embed(
            [document.searchable_text() for document in documents],
            model=model,
        )
        if len(vectors) != len(documents):
            raise EmbeddingError("embedding_response_count_mismatch")
    except EmbeddingError as exc:
        _mark_embedding_failure(db, documents, str(exc))
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

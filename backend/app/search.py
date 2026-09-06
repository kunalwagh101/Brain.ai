import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import and_, exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import CanonicalEvent, MembershipRole
from app.search_models import SearchDocument
from app.work_graph import node_visible_to_user
from app.work_graph_models import WorkGraphNode, WorkGraphNodeType

SEARCH_TEXT_MAX_CHARS = 65_536
MAX_QUERY_TERMS = 20
MAX_CANDIDATES_SCANNED = 1_000


@dataclass(frozen=True, slots=True)
class SearchResult:
    canonical_event_id: uuid.UUID
    source_provider: str
    source_event_id: str
    event_type: str
    object_type: str
    object_external_id: str
    title: str
    snippet: str
    occurred_at: datetime | None
    provenance: dict[str, object]


def _append_text(parts: list[str], value: Any, *, depth: int = 0) -> None:
    if depth > 4:
        return
    if isinstance(value, str):
        text = " ".join(value.split())
        if text:
            parts.append(text)
        return
    if isinstance(value, dict):
        for key in sorted(value):
            _append_text(parts, value[key], depth=depth + 1)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _append_text(parts, item, depth=depth + 1)


def canonical_search_text(event: CanonicalEvent) -> str:
    parts: list[str] = [
        event.event_type,
        event.action,
        event.actor_type,
        event.object_type,
        event.object_external_id,
        event.source_provider,
        event.source_event_type,
    ]
    if event.actor_display_name:
        parts.append(event.actor_display_name)
    if event.object_display_name:
        parts.append(event.object_display_name)
    _append_text(parts, event.event_metadata)
    return " ".join(parts)[:SEARCH_TEXT_MAX_CHARS]


def index_canonical_event(
    db: Session,
    event: CanonicalEvent,
    *,
    commit: bool = True,
) -> tuple[SearchDocument, bool]:
    document = db.scalar(
        select(SearchDocument).where(SearchDocument.canonical_event_id == event.id)
    )
    if document is not None:
        return document, False

    document = SearchDocument(
        organization_id=event.organization_id,
        canonical_event_id=event.id,
        source_provider=event.source_provider,
        event_type=event.event_type,
        object_type=event.object_type,
        search_text=canonical_search_text(event),
    )
    try:
        with db.begin_nested():
            db.add(document)
            db.flush()
    except IntegrityError:
        document = db.scalar(
            select(SearchDocument).where(SearchDocument.canonical_event_id == event.id)
        )
        if document is None:
            raise
        return document, False

    if commit:
        db.commit()
        db.refresh(document)
    return document, True


def reconcile_search_documents(
    db: Session,
    *,
    organization_id: uuid.UUID,
    limit: int,
) -> tuple[int, int]:
    indexed = exists(
        select(SearchDocument.id).where(
            SearchDocument.canonical_event_id == CanonicalEvent.id
        )
    )
    events = list(
        db.scalars(
            select(CanonicalEvent)
            .where(
                CanonicalEvent.organization_id == organization_id,
                ~indexed,
            )
            .order_by(CanonicalEvent.created_at, CanonicalEvent.id)
            .limit(limit)
        )
    )
    created = 0
    for event in events:
        _, was_created = index_canonical_event(db, event, commit=False)
        created += int(was_created)
    db.commit()

    remaining = db.scalar(
        select(func.count())
        .select_from(CanonicalEvent)
        .where(
            CanonicalEvent.organization_id == organization_id,
            ~exists(
                select(SearchDocument.id).where(
                    SearchDocument.canonical_event_id == CanonicalEvent.id
                )
            ),
        )
    )
    return created, int(remaining or 0)


def _query_terms(query: str) -> list[str]:
    terms = [term.casefold() for term in re.findall(r"[\w.-]+", query, flags=re.UNICODE)]
    return list(dict.fromkeys(terms))[:MAX_QUERY_TERMS]


def _snippet(text: str, terms: list[str], *, max_chars: int = 280) -> str:
    normalized = text.casefold()
    positions = [normalized.find(term) for term in terms if term and normalized.find(term) >= 0]
    start = max(0, (min(positions) if positions else 0) - 80)
    end = min(len(text), start + max_chars)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{text[start:end].strip()}{suffix}"


def _candidate_statement(
    db: Session,
    *,
    organization_id: uuid.UUID,
    query: str,
):
    statement = (
        select(SearchDocument, CanonicalEvent, WorkGraphNode)
        .join(CanonicalEvent, CanonicalEvent.id == SearchDocument.canonical_event_id)
        .join(
            WorkGraphNode,
            and_(
                WorkGraphNode.organization_id == SearchDocument.organization_id,
                WorkGraphNode.canonical_event_id == CanonicalEvent.id,
                WorkGraphNode.node_type == WorkGraphNodeType.EVIDENCE,
            ),
        )
        .where(SearchDocument.organization_id == organization_id)
    )

    if db.get_bind().dialect.name == "postgresql":
        vector = func.to_tsvector("simple", SearchDocument.search_text)
        tsquery = func.websearch_to_tsquery("simple", query)
        rank = func.ts_rank_cd(vector, tsquery)
        return statement.where(vector.op("@@")(tsquery)).order_by(
            rank.desc(),
            CanonicalEvent.occurred_at.desc(),
            CanonicalEvent.id,
        )

    terms = _query_terms(query)
    for term in terms:
        statement = statement.where(func.lower(SearchDocument.search_text).contains(term))
    return statement.order_by(CanonicalEvent.occurred_at.desc(), CanonicalEvent.id)


def search_evidence(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    role: MembershipRole,
    query: str,
    limit: int,
) -> list[SearchResult]:
    terms = _query_terms(query)
    if not terms:
        return []

    statement = _candidate_statement(
        db,
        organization_id=organization_id,
        query=query,
    )
    results: list[SearchResult] = []
    scanned = 0
    page_size = min(max(limit * 4, 25), 100)

    while len(results) < limit and scanned < MAX_CANDIDATES_SCANNED:
        rows = db.execute(statement.offset(scanned).limit(page_size)).all()
        if not rows:
            break
        scanned += len(rows)

        for document, event, evidence_node in rows:
            if not node_visible_to_user(
                db,
                evidence_node,
                user_id=user_id,
                role=role,
            ):
                continue
            results.append(
                SearchResult(
                    canonical_event_id=event.id,
                    source_provider=event.source_provider,
                    source_event_id=event.source_event_id,
                    event_type=event.event_type,
                    object_type=event.object_type,
                    object_external_id=event.object_external_id,
                    title=event.object_display_name or event.event_type,
                    snippet=_snippet(document.search_text, terms),
                    occurred_at=event.occurred_at,
                    provenance=dict(event.provenance),
                )
            )
            if len(results) >= limit:
                break

        if len(rows) < page_size:
            break

    return results

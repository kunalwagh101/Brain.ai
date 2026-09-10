import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.decision_memory_models import (
    DecisionMemoryCandidate,
    DecisionMemoryExtraction,
    DecisionMemoryReview,
    MemoryKind,
    MemoryReviewAction,
    MemoryState,
)
from app.models import CanonicalEvent
from app.search import _base_query as _authorized_search_documents_query
from app.search_models import SearchDocument

EXTRACTION_METHOD = "deterministic"
EXTRACTION_VERSION = "explicit-markers-v1"
MAX_SEGMENTS = 400
MAX_CANDIDATES_PER_DOCUMENT = 20
MAX_SUMMARY_LENGTH = 1000

_SEGMENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
_DECISION_PATTERNS: tuple[tuple[re.Pattern[str], float], ...] = (
    (
        re.compile(r"(?i)^\s*(?:final\s+)?decision\s*:\s*(?P<body>.+)$"),
        0.99,
    ),
    (
        re.compile(
            r"(?i)\bwe\s+(?:have\s+)?decided\s+"
            r"(?:to\s+|that\s+)?(?P<body>.+)$"
        ),
        0.97,
    ),
    (
        re.compile(
            r"(?i)\bthe\s+decision\s+is\s+"
            r"(?:to\s+|that\s+)?(?P<body>.+)$"
        ),
        0.97,
    ),
    (
        re.compile(r"(?i)\bwe\s+(?:have\s+)?agreed\s+to\s+(?P<body>.+)$"),
        0.94,
    ),
)
_BLOCKER_PATTERNS: tuple[tuple[re.Pattern[str], float], ...] = (
    (
        re.compile(r"(?i)^\s*blocker\s*:\s*(?P<body>.+)$"),
        0.99,
    ),
    (
        re.compile(
            r"(?i)\b(?:is|are|we(?:'re|\s+are)?)\s+"
            r"blocked\s+by\s+(?P<body>.+)$"
        ),
        0.97,
    ),
    (
        re.compile(r"(?i)\bblocked\s+because\s+(?P<body>.+)$"),
        0.96,
    ),
    (
        re.compile(
            r"(?i)\b(?:cannot|can't)\s+proceed\s+until\s+(?P<body>.+)$"
        ),
        0.95,
    ),
    (
        re.compile(
            r"(?i)\bwe(?:'re|\s+are)\s+waiting\s+on\s+(?P<body>.+)$"
        ),
        0.91,
    ),
)


class DecisionMemoryError(ValueError):
    """Raised when a decision-memory operation violates state or tenant rules."""


@dataclass(frozen=True, slots=True)
class ExtractedMemory:
    kind: MemoryKind
    summary: str
    confidence: float
    fingerprint: str


@dataclass(frozen=True, slots=True)
class ProjectionResult:
    processed: bool
    created: int
    emitted: int


def _normalize_summary(value: str) -> str:
    value = " ".join(value.strip().split())
    value = value.strip(" \t\r\n-–—:;,.")
    return value[:MAX_SUMMARY_LENGTH].strip()


def _fingerprint(kind: MemoryKind, summary: str) -> str:
    normalized = " ".join(summary.casefold().split())
    payload = f"{kind.value}\n{normalized}".encode()
    return hashlib.sha256(payload).hexdigest()


def _extract_from_segment(segment: str) -> list[ExtractedMemory]:
    extracted: list[ExtractedMemory] = []
    for kind, patterns in (
        (MemoryKind.DECISION, _DECISION_PATTERNS),
        (MemoryKind.BLOCKER, _BLOCKER_PATTERNS),
    ):
        for pattern, confidence in patterns:
            match = pattern.search(segment)
            if match is None:
                continue
            summary = _normalize_summary(match.group("body"))
            if len(summary) < 3:
                break
            extracted.append(
                ExtractedMemory(
                    kind=kind,
                    summary=summary,
                    confidence=confidence,
                    fingerprint=_fingerprint(kind, summary),
                )
            )
            break
    return extracted


def extract_decision_blocker_candidates(
    document: SearchDocument,
) -> list[ExtractedMemory]:
    if document.is_deleted:
        return []
    text = "\n".join(part for part in (document.title, document.content) if part)
    segments = [
        segment.strip()
        for segment in _SEGMENT_SPLIT.split(text)
        if segment.strip()
    ]
    seen: set[tuple[MemoryKind, str]] = set()
    extracted: list[ExtractedMemory] = []
    for segment in segments[:MAX_SEGMENTS]:
        for candidate in _extract_from_segment(segment):
            key = (candidate.kind, candidate.fingerprint)
            if key in seen:
                continue
            seen.add(key)
            extracted.append(candidate)
            if len(extracted) >= MAX_CANDIDATES_PER_DOCUMENT:
                return extracted
    return extracted


def _document_digest(document: SearchDocument) -> str:
    payload = f"{document.title}\n{document.content}".encode()
    return hashlib.sha256(payload).hexdigest()


def _candidate_has_human_history(db: Session, candidate_id: uuid.UUID) -> bool:
    review_id = db.scalar(
        select(DecisionMemoryReview.id)
        .where(DecisionMemoryReview.candidate_id == candidate_id)
        .limit(1)
    )
    return review_id is not None


def _locked_search_document(
    db: Session,
    *,
    organization_id: uuid.UUID,
    document_id: uuid.UUID,
) -> SearchDocument:
    document = db.scalar(
        select(SearchDocument)
        .where(
            SearchDocument.id == document_id,
            SearchDocument.organization_id == organization_id,
        )
        .with_for_update()
    )
    if document is None:
        raise DecisionMemoryError("Search evidence is unavailable")
    return document


def project_memory_candidates(
    db: Session,
    document: SearchDocument,
) -> ProjectionResult:
    document = _locked_search_document(
        db,
        organization_id=document.organization_id,
        document_id=document.id,
    )
    digest = _document_digest(document)
    extraction = db.scalar(
        select(DecisionMemoryExtraction).where(
            DecisionMemoryExtraction.search_document_id == document.id
        )
    )
    if (
        extraction is not None
        and extraction.extraction_version == EXTRACTION_VERSION
        and extraction.content_sha256 == digest
    ):
        return ProjectionResult(
            processed=False,
            created=0,
            emitted=extraction.candidate_count,
        )

    emitted = extract_decision_blocker_candidates(document)
    emitted_keys = {(item.kind, item.fingerprint) for item in emitted}
    existing = list(
        db.scalars(
            select(DecisionMemoryCandidate).where(
                DecisionMemoryCandidate.organization_id == document.organization_id,
                DecisionMemoryCandidate.canonical_event_id
                == document.canonical_event_id,
                DecisionMemoryCandidate.extraction_method == EXTRACTION_METHOD,
            )
        )
    )
    for candidate in existing:
        key = (candidate.kind, candidate.fingerprint)
        if (
            key not in emitted_keys
            and candidate.state == MemoryState.CANDIDATE
            and not _candidate_has_human_history(db, candidate.id)
        ):
            candidate.state = MemoryState.SUPERSEDED

    created = 0
    for item in emitted:
        candidate = db.scalar(
            select(DecisionMemoryCandidate).where(
                DecisionMemoryCandidate.organization_id == document.organization_id,
                DecisionMemoryCandidate.canonical_event_id
                == document.canonical_event_id,
                DecisionMemoryCandidate.kind == item.kind,
                DecisionMemoryCandidate.fingerprint == item.fingerprint,
            )
        )
        if candidate is None:
            candidate = DecisionMemoryCandidate(
                organization_id=document.organization_id,
                canonical_event_id=document.canonical_event_id,
                search_document_id=document.id,
                work_graph_node_id=document.work_graph_node_id,
                kind=item.kind,
                state=MemoryState.CANDIDATE,
                summary=item.summary,
                confidence=item.confidence,
                extraction_method=EXTRACTION_METHOD,
                extraction_version=EXTRACTION_VERSION,
                fingerprint=item.fingerprint,
            )
            db.add(candidate)
            created += 1
            continue

        candidate.search_document_id = document.id
        candidate.work_graph_node_id = document.work_graph_node_id
        has_human_history = _candidate_has_human_history(db, candidate.id)
        if not has_human_history:
            candidate.summary = item.summary
            candidate.confidence = item.confidence
        candidate.extraction_method = EXTRACTION_METHOD
        candidate.extraction_version = EXTRACTION_VERSION
        if candidate.state == MemoryState.SUPERSEDED and not has_human_history:
            candidate.state = MemoryState.CANDIDATE

    now = datetime.now(UTC)
    if extraction is None:
        extraction = DecisionMemoryExtraction(
            organization_id=document.organization_id,
            search_document_id=document.id,
            extraction_version=EXTRACTION_VERSION,
            content_sha256=digest,
            candidate_count=len(emitted),
            processed_at=now,
        )
        db.add(extraction)
    else:
        extraction.extraction_version = EXTRACTION_VERSION
        extraction.content_sha256 = digest
        extraction.candidate_count = len(emitted)
        extraction.processed_at = now

    db.commit()
    return ProjectionResult(processed=True, created=created, emitted=len(emitted))


def reconcile_memory_candidates(
    db: Session,
    *,
    organization_id: uuid.UUID,
    limit: int,
) -> tuple[int, int, int]:
    needs_processing = or_(
        DecisionMemoryExtraction.id.is_(None),
        DecisionMemoryExtraction.extraction_version != EXTRACTION_VERSION,
        SearchDocument.updated_at > DecisionMemoryExtraction.processed_at,
    )
    documents = list(
        db.scalars(
            select(SearchDocument)
            .outerjoin(
                DecisionMemoryExtraction,
                DecisionMemoryExtraction.search_document_id == SearchDocument.id,
            )
            .where(
                SearchDocument.organization_id == organization_id,
                SearchDocument.is_deleted.is_(False),
                needs_processing,
            )
            .order_by(SearchDocument.created_at, SearchDocument.id)
            .limit(limit)
        )
    )
    created = 0
    for document in documents:
        created += project_memory_candidates(db, document).created

    remaining = db.scalar(
        select(func.count())
        .select_from(SearchDocument)
        .outerjoin(
            DecisionMemoryExtraction,
            DecisionMemoryExtraction.search_document_id == SearchDocument.id,
        )
        .where(
            SearchDocument.organization_id == organization_id,
            SearchDocument.is_deleted.is_(False),
            needs_processing,
        )
    )
    return len(documents), created, int(remaining or 0)


def _visible_candidate_ids(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
):
    visible_documents = (
        _authorized_search_documents_query(
            db,
            organization_id=organization_id,
            user_id=user_id,
        )
        .with_only_columns(SearchDocument.id)
        .subquery()
    )
    return select(DecisionMemoryCandidate.id).where(
        DecisionMemoryCandidate.organization_id == organization_id,
        DecisionMemoryCandidate.search_document_id.in_(
            select(visible_documents.c.id)
        ),
    )


def list_visible_memory_candidates(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    kind: MemoryKind | None,
    state: MemoryState | None,
    limit: int,
) -> list[DecisionMemoryCandidate]:
    query = select(DecisionMemoryCandidate).where(
        DecisionMemoryCandidate.id.in_(
            _visible_candidate_ids(
                db,
                organization_id=organization_id,
                user_id=user_id,
            )
        )
    )
    if kind is not None:
        query = query.where(DecisionMemoryCandidate.kind == kind)
    if state is not None:
        query = query.where(DecisionMemoryCandidate.state == state)
    else:
        query = query.where(
            DecisionMemoryCandidate.state.notin_(
                (MemoryState.REJECTED, MemoryState.SUPERSEDED)
            )
        )
    return list(
        db.scalars(
            query.order_by(DecisionMemoryCandidate.created_at.desc()).limit(limit)
        )
    )


def get_visible_memory_candidate(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    candidate_id: uuid.UUID,
) -> DecisionMemoryCandidate | None:
    return db.scalar(
        select(DecisionMemoryCandidate).where(
            DecisionMemoryCandidate.id == candidate_id,
            DecisionMemoryCandidate.id.in_(
                _visible_candidate_ids(
                    db,
                    organization_id=organization_id,
                    user_id=user_id,
                )
            ),
        )
    )


def _locked_visible_memory_candidate(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    candidate_id: uuid.UUID,
) -> DecisionMemoryCandidate | None:
    return db.scalar(
        select(DecisionMemoryCandidate)
        .where(
            DecisionMemoryCandidate.id == candidate_id,
            DecisionMemoryCandidate.id.in_(
                _visible_candidate_ids(
                    db,
                    organization_id=organization_id,
                    user_id=user_id,
                )
            ),
        )
        .with_for_update()
    )


def _transition_state(
    candidate: DecisionMemoryCandidate,
    action: MemoryReviewAction,
) -> MemoryState:
    state = candidate.state
    if action == MemoryReviewAction.CONFIRM and state == MemoryState.CANDIDATE:
        return MemoryState.CONFIRMED
    if action == MemoryReviewAction.REJECT and state in {
        MemoryState.CANDIDATE,
        MemoryState.CONFIRMED,
    }:
        return MemoryState.REJECTED
    if (
        action == MemoryReviewAction.RESOLVE
        and candidate.kind == MemoryKind.BLOCKER
        and state == MemoryState.CONFIRMED
    ):
        return MemoryState.RESOLVED
    if action == MemoryReviewAction.REOPEN and state == MemoryState.REJECTED:
        return MemoryState.CANDIDATE
    if (
        action == MemoryReviewAction.REOPEN
        and candidate.kind == MemoryKind.BLOCKER
        and state == MemoryState.RESOLVED
    ):
        return MemoryState.CONFIRMED
    if action == MemoryReviewAction.EDIT and state in {
        MemoryState.CANDIDATE,
        MemoryState.CONFIRMED,
        MemoryState.RESOLVED,
    }:
        return state
    raise DecisionMemoryError(
        f"Action {action.value} is not allowed from state {state.value}"
    )


def review_memory_candidate(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    candidate_id: uuid.UUID,
    action: MemoryReviewAction,
    reason: str,
    summary: str | None,
) -> DecisionMemoryCandidate:
    candidate = _locked_visible_memory_candidate(
        db,
        organization_id=organization_id,
        user_id=user_id,
        candidate_id=candidate_id,
    )
    if candidate is None:
        raise DecisionMemoryError("Memory candidate not found")

    normalized_reason = " ".join(reason.strip().split())[:1000]
    if not normalized_reason:
        raise DecisionMemoryError("Review reason is required")
    previous_state = candidate.state
    previous_summary = candidate.summary
    new_state = _transition_state(candidate, action)
    new_summary = previous_summary
    if action == MemoryReviewAction.EDIT:
        if summary is None:
            raise DecisionMemoryError("Edited summary is required")
        new_summary = _normalize_summary(summary)
        if len(new_summary) < 3:
            raise DecisionMemoryError("Edited summary is too short")
    elif summary is not None:
        raise DecisionMemoryError("Summary may only be supplied for edit action")

    candidate.state = new_state
    candidate.summary = new_summary
    db.add(
        DecisionMemoryReview(
            organization_id=organization_id,
            candidate_id=candidate.id,
            actor_user_id=user_id,
            action=action,
            previous_state=previous_state,
            new_state=new_state,
            previous_summary=previous_summary,
            new_summary=new_summary,
            reason=normalized_reason,
        )
    )
    db.commit()
    db.refresh(candidate)
    return candidate


def list_memory_reviews(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    candidate_id: uuid.UUID,
) -> list[DecisionMemoryReview] | None:
    candidate = get_visible_memory_candidate(
        db,
        organization_id=organization_id,
        user_id=user_id,
        candidate_id=candidate_id,
    )
    if candidate is None:
        return None
    return list(
        db.scalars(
            select(DecisionMemoryReview)
            .where(
                DecisionMemoryReview.organization_id == organization_id,
                DecisionMemoryReview.candidate_id == candidate_id,
            )
            .order_by(DecisionMemoryReview.created_at, DecisionMemoryReview.id)
        )
    )


def memory_candidate_evidence(
    db: Session,
    candidate: DecisionMemoryCandidate,
) -> tuple[CanonicalEvent, SearchDocument]:
    event = db.get(CanonicalEvent, candidate.canonical_event_id)
    document = (
        db.get(SearchDocument, candidate.search_document_id)
        if candidate.search_document_id is not None
        else None
    )
    if event is None or document is None:
        raise DecisionMemoryError("Memory candidate evidence is unavailable")
    if (
        event.organization_id != candidate.organization_id
        or document.organization_id != candidate.organization_id
    ):
        raise DecisionMemoryError("Memory candidate evidence tenant mismatch")
    return event, document

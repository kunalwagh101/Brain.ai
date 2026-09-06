import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import RawEvent, RawEventStatus

MAX_RAW_EVENT_BYTES = 2_000_000


class RawEventRejectedError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RawEventPersistResult:
    event: RawEvent
    created: bool


def persist_raw_event(
    db: Session,
    *,
    organization_id: uuid.UUID,
    integration_connection_id: uuid.UUID,
    provider: str,
    source_event_id: str,
    source_event_type: str,
    delivery_kind: str,
    raw_payload: bytes,
    content_type: str,
    source_visibility: str,
    source_acl: list[str],
    source_timestamp: datetime | None = None,
) -> RawEventPersistResult:
    if not raw_payload:
        raise RawEventRejectedError("Raw event payload must not be empty")
    if len(raw_payload) > MAX_RAW_EVENT_BYTES:
        raise RawEventRejectedError("Raw event payload exceeds the ingestion limit")
    if not source_event_id or len(source_event_id) > 255:
        raise RawEventRejectedError("source_event_id must be 1-255 characters")
    if not source_event_type or len(source_event_type) > 128:
        raise RawEventRejectedError("source_event_type must be 1-128 characters")
    if not delivery_kind or len(delivery_kind) > 32:
        raise RawEventRejectedError("delivery_kind must be 1-32 characters")
    if not source_visibility or len(source_visibility) > 32:
        raise RawEventRejectedError("source_visibility must be 1-32 characters")

    event = RawEvent(
        organization_id=organization_id,
        integration_connection_id=integration_connection_id,
        provider=provider,
        source_event_id=source_event_id,
        source_event_type=source_event_type,
        delivery_kind=delivery_kind,
        source_timestamp=source_timestamp,
        content_type=content_type[:128] or "application/octet-stream",
        payload_sha256=hashlib.sha256(raw_payload).hexdigest(),
        raw_payload=raw_payload,
        source_visibility=source_visibility,
        source_acl=list(dict.fromkeys(source_acl)),
        processing_status=RawEventStatus.RECEIVED,
        processing_attempts=0,
    )
    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(RawEvent).where(
                RawEvent.integration_connection_id == integration_connection_id,
                RawEvent.source_event_id == source_event_id,
            )
        )
        if existing is None:
            raise
        return RawEventPersistResult(event=existing, created=False)

    db.refresh(event)
    return RawEventPersistResult(event=event, created=True)
